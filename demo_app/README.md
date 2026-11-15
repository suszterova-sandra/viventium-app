# Viventium demo app

React (Vite + TypeScript) portal around the **Viventium** workspaces on `sandrasuszterova.demo.cloud.gooddata.com`:
one template workspace (Viventium) and client workspaces delivered in tiers. Switch between real users in one
click; every number, dashboard, report and AI answer comes back with that user's own GoodData permissions.

## Run

```bash
# once
python3 demo_app/setup_agents.py     # creates/updates the 3 Viventium agents in AI Hub (idempotent)
python3 demo_app/setup_tokens.py     # API tokens for the personas in tenancy/personas.csv -> demo_app/.tokens.json (skips existing)
cd demo_app/web && npm install

# every time (two terminals)
python3 demo_app/server.py           # backend on 127.0.0.1:8765 (tokens + GoodData proxy)
cd demo_app/web && npm run dev       # UI on http://localhost:5173
```

The admin token comes from `../.env` (`GOODDATA_API_TOKEN`). Keep Vite on port 5173: it is an allowed origin of the
organization. `npm run build` produces `web/dist`, which `server.py` also serves on :8765.

Static build (GitHub Pages, no backend): `VITE_STATIC=1 VITE_BASE=/viventium-app/ npx vite build`. Client users
use the tokens from `.tokens.json` compiled into the build; the admin signs in with a GoodData login, otherwise
visitors see the snapshot in `web/public/overview.json` (`python3 demo_app/snapshot_overview.py`, no tokens in it).

## Personas

| User | Client · workspace | Tier | Data products | Locations | AI |
|---|---|---|---|---|---|
| Sandra Suszterova (`admin`) | Viventium internal admin · template | Internal | all 11 | all clients | yes, all 3 agents |
| Paula Grant (`viv.riverstone.payroll`) | Riverstone Health Partners · `riverstone` | AI tier, ANALYZE | Payroll, On-Demand Pay, ACA Compliance, Benefits, HR | all 4 | Summary, Next steps, Compliance |
| Marcus Lee (`viv.riverstone.recruiter`) | Riverstone Health Partners · `riverstone` | AI tier, VIEW | Applicant Tracking, Onboarding | Brooklyn, NY | Summary, Next steps |
| Diana Ortiz (`viv.hearthside.scheduler`) | HearthSide Home Care · `hearthside` | Analytics tier, ANALYZE | Scheduling, Time & Attendance | Flushing, NY (Queens) | locked |
| Ken Watanabe (`viv.maplehollow.payroll`) | Maple Hollow Senior Living · `shard_base_01` | Base shard, VIEW | Payroll, On-Demand Pay | all 4 | locked |
| Grace Mensah (`viv.willowbend.hr`) | Willowbend Home Health & Hospice · `shard_base_01` | Base shard, VIEW | HR, Benefits, LMS, Exclusion Monitoring | Knoxville, TN | locked |
| Ana Reyes (`viv.littleoak.scheduler`) | Little Oak Behavioral Health · `shard_base_01` | Base shard, VIEW | Scheduling, Time & Attendance | all 3 | locked |

The persona list is built by `server.py` from `../tenancy/personas.csv`, `tenant_mapping.csv` and
`demo_data/csv/locations.csv` (and hard-coded in `web/src/staticBackend.ts` for the static build). The top bar
shows every user with tier and client; the people icon next to it opens "who is who" with products, locations,
permissions and each persona's story.

## What it shows

| Screen | Story |
|---|---|
| **Home** | Welcome page for the user's workspace. Up to 4 KPIs and a 4-item watch list picked from the user's data products (`web/src/products.ts`), last quarter vs the one before on `activity_date`; the headline and the key drivers are the first KPI sliced by location and job role. Each tile opens the product dashboard at its headline visualization. AI briefing of the first product's dashboard (AI tier only). KPIs of products the user is not entitled to fail with 403 and are skipped. |
| **Control Center** (admin) | Template → client workspaces, each in its own theme, with its `client_id` filter value (`wdf__client_id`), access matrix per user and the AI Hub agent matrix. "View as →" jumps into a user. |
| **Dashboards** | The user's product dashboards (Shared / Private), **+ New dashboard** for ANALYZE users, and an agentic summary above each dashboard for AI-tier users. |
| **AI Report** | The Publisher report of the user's first data product (`dp_<product>_report`), with a picker when the user has several products; **Export PDF** runs as the user. |
| **Analyze** | Analytical Designer for ANALYZE users; VIEW users get a locked screen. |
| **AI Assistant** | GoodData's `GenAIAssistant` docked on the right, built per user from their token. Users without `USE_AI_ASSISTANT` on the workspace (Analytics tier, Base shard) get "AI is part of the AI tier" instead. |

## AI Hub agents (`setup_agents.py`)

| Agent | Assigned to |
|---|---|
| `viventium-summary-agent`: workforce summary (overtime, call-offs, turnover, pay) | `client_riverstone`, `adminGroup` |
| `viventium-next-steps-agent`: two-week action plan, alerts, scheduled exports | `client_riverstone`, `adminGroup` |
| `viventium-compliance-agent`: ACA offer rate/exposure, exclusion matches, overtime risk | `adminGroup`, `dp_aca_compliance` |

## How access is enforced

Nothing is filtered in the front end. Every `/gd/...` call carries `X-Persona`; `server.py` swaps in that user's
API token and proxies to GoodData, so workspaces, permissions, data products, agents and AI answers come back
exactly as GoodData resolves them for that user. Embedded iframes get the same token through GoodData's
`listeningForApiToken` → `setApiToken` handshake (`src/api.ts`). The server binds to 127.0.0.1 and hands tokens
to the browser: keep it local.
