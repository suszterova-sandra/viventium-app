# Viventium tech session: multi-tenancy demo runbook (Mon, Nov 16, 2026)

The design comes from the multi-tenancy brief. The demo has 3 parts:
1. an **AI workspace**
2. a **limited (shared) workspace**
3. **different accesses** inside the same workspaces

Everything shown is enforced by GoodData, not the front end. The portal only switches which user's API token it uses.

## Setup (before the call)

```bash
cd viventium
set -a; . ./.env; set +a
python3 tenancy/reconcile.py --tokens      # idempotent; recreates the 6 personas' tokens
python3 tenancy/verify_personas.py         # must end with ALL CHECKS PASSED
python3 demo_app/server.py                 # terminal 1
cd demo_app/web && npm run dev             # terminal 2 -> http://localhost:5173
```

## The workspaces

| Workspace | Tier (brief) | Clients | Isolation |
|---|---|---|---|
| Viventium (parent) | Template, internal | all | admin only, unfiltered |
| `riverstone` | **AI tier, dedicated** | Riverstone (enterprise SNF, 4 facilities) | workspace data filter = riverstone |
| `hearthside` | **Analytics tier, dedicated** | HearthSide (home care) | workspace data filter = hearthside |
| `shard_base_01` | **Base shard, shared** | Maple Hollow, Willowbend, Little Oak | the workspace data filter lists the 3 clients (backstop). Each client is a user group with a client user data filter. |

`tenancy/tenant_mapping.csv` is the tenant mapping table from section 7 of the brief. `tenancy/reconcile.py` is the pipeline that applies it.
Moving a client from the shard to its own workspace (upgrade or acquisition) means editing one row and re-running the script.

## The personas

| Persona | Workspace | Tier permissions | Role → data products | Locations |
|---|---|---|---|---|
| Paula Grant, Payroll Director | riverstone | ANALYZE, EXPORT, automations, **AI** | Payroll, On-Demand Pay, ACA, Benefits, HR | all 4 (enterprise roll-up) |
| Marcus Lee, HR Recruiter | riverstone | VIEW + **AI** | Applicant Tracking, Onboarding | Brooklyn only |
| Diana Ortiz, Scheduler | hearthside | ANALYZE, EXPORT (no AI) | Scheduling, Time & Attendance | Queens only |
| Ken Watanabe, Payroll Specialist | shard_base_01 | VIEW only | Payroll, On-Demand Pay | all Maple Hollow facilities |
| Grace Mensah, HR & Benefits | shard_base_01 | VIEW only | HR, Benefits, LMS, Exclusion Monitoring | Willowbend Knoxville only |
| Ana Reyes, Scheduler | shard_base_01 | VIEW only | Scheduling, Time & Attendance | all Little Oak clinics |

## Part 1: AI workspace (Paula → Marcus)

1. **Admin (Control Center):** the parent template and its children. Each child has its own theme and its own workspace data filter value. The shard has 3 values.
   - **Say:** "Build once in the parent, every workspace inherits it. 11 data products, one per Viventium product."
2. **Paula (AI tier):** Home → Payroll dashboard → ask the AI Assistant, e.g. "Why did overtime go up at Riverstone?".
   - She sees all 4 facilities: the enterprise roll-up for CCH- or MFA-type clients.
   - She has ANALYZE, so she can build her own dashboards. That's why AI and Analytics clients get a dedicated workspace: what they save is visible to their own users only.
3. **Marcus (same workspace, VIEW + AI):** only Applicant Tracking and Onboarding, and only the Brooklyn facility.
   - His AI summary of Applicant Tracking reports 1,342 applications. That's Brooklyn only; Riverstone overall has about 4,560.
   - **Say:** "The AI respects the same data filters. Ask it about payroll and the dashboard doesn't exist for him."
   - **Say:** "AI is a per-user permission (USE_AI_ASSISTANT), so it can be tiered inside a dedicated workspace."

## Part 2: limited workspace (Ken → Grace → Ana, same `shard_base_01`)

1. **Ken:** view only. Only Payroll and On-Demand Pay; the dashboards he didn't buy or isn't entitled to don't exist for him.
   - The Client filter shows only Maple Hollow, although 3 clients share the workspace.
   - No Analyze, no AI, no export.
2. **Grace (same workspace):** HR, Benefits, LMS and Exclusion Monitoring, Knoxville only (the location user data filter). No pay rates: column-level permission.
3. **Ana (same workspace):** Scheduling and Time & Attendance for Little Oak.
4. **Say:** "One workspace serves many small clients. Isolation is 2 layers:
   - the workspace data filter of the shard is the backstop, so an error stays inside the shard
   - the client user data filter separates the clients inside it

   That's how 6,500 small clients fit in a few shards instead of 9,000 workspaces."

## Part 3: different accesses (the 4 layers)

| Layer | Mechanism | Shown by |
|---|---|---|
| Tenant | Workspace data filter (dedicated); user group + user data filter (shard) | Ken / Grace / Ana side by side |
| Location | User data filter per user | Marcus (Brooklyn), Diana (Queens), Grace (Knoxville) vs Paula (all) |
| Product × role | Object permissions of the data-product groups `dp_*`, set once on the parent and inherited | Each persona's dashboard list |
| Field sensitivity | Column-level permission: `hourly_rate` and `annual_salary` only for Payroll | Diana in Analyze: no pay-rate fields in the catalog; Paula has them |
| Tier | Workspace permissions VIEW / ANALYZE / EXPORT / USE_AI_ASSISTANT | Analyze tab locked for VIEW users, AI only in the AI tier |

## Open questions from the brief this answers

- **Can dashboard permissions be set on inherited dashboards?** Yes. They're set on the parent and enforced in every child, including the shard. Verified per persona.
- **Can AI be turned off per user or group inside a workspace?** Yes, with the USE_AI_ASSISTANT workspace permission. Marcus has VIEW + AI, while Ken in the shard has no AI endpoint at all.
- **Does the AI leak across filters?** No. Answers are computed with the user's data filters, so Marcus's summary covers Brooklyn only.

## Still open (don't claim)

- Column-level security is used here and works on this org. Confirm that it's GA for their contract.
- The automation quota is shared per workspace. This DEMO org has 20 automations and 10 daily scheduled exports, which are not production values.
- AI catalog noise: the AI in a workspace sees every metric there. Hiding objects by permission reduces this, but product-bundle templates are the clean answer for AI workspaces.
- Load at payroll-day peaks wasn't tested here; it's a PoC success criterion.

## Proof without the portal

`python3 tenancy/verify_personas.py` acts as each persona with their own token and checks:
- visible workspaces, permissions and dashboards
- client and location isolation
- that other products are refused
- pay-rate visibility

The last run ended with **ALL CHECKS PASSED** (30 of 30).
