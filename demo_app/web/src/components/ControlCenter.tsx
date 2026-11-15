import { type CSSProperties } from "react";
import { agentAccess, useApp } from "../AppContext";
import { agentStyle, SKILL_LABEL } from "../constants";
import { Icon, type IconName } from "../icons";
import { logoTile, themeVars } from "../theme";
import type { OverviewWorkspace, Persona, TierKey } from "../types";

/** client_id (workspace data filter value) -> name, as in tenancy/tenant_mapping.csv */
const CLIENT_NAMES: Record<string, string> = {
  riverstone: "Riverstone Health Partners",
  hearthside: "HearthSide Home Care",
  maplehollow: "Maple Hollow Senior Living",
  willowbend: "Willowbend Home Health & Hospice",
  littleoak: "Little Oak Behavioral Health",
};
const clientName = (id: string) => CLIENT_NAMES[id] || id;

const TIERS: { key: Exclude<TierKey, "admin">; title: string; what: string; isolation: string; can: string }[] = [
  {
    key: "ai",
    title: "AI tier",
    what: "Dedicated workspace per client. Self-service plus the AI Assistant and AI agents.",
    isolation: "Workspace data filter = this client only",
    can: "ANALYZE / VIEW + AI Assistant, per user",
  },
  {
    key: "analytics",
    title: "Analytics tier",
    what: "Dedicated workspace per client. Users build their own reports and dashboards, no AI.",
    isolation: "Workspace data filter = this client only",
    can: "ANALYZE, EXPORT",
  },
  {
    key: "base",
    title: "Base shard",
    what: "One shared workspace for many small clients. Ready-made dashboards, view only.",
    isolation: "Workspace data filter = the shard's clients (backstop) + a client data filter per user group",
    can: "VIEW only",
  },
];

const LAYERS: { icon: IconName; title: string; question: string; how: string; example: string }[] = [
  { icon: "shield", title: "Client", question: "Whose data?", how: "Workspace data filter (dedicated) · user group + data filter (shard)", example: "Ken sees only Maple Hollow, although 3 clients share his workspace" },
  { icon: "pin", title: "Location", question: "Which facilities?", how: "User data filter per user", example: "Marcus: Brooklyn only · Paula: all 4 facilities" },
  { icon: "dashboard", title: "Product × role", question: "Which dashboards?", how: "Data-product user groups, granted once on the template, inherited", example: "A recruiter gets Applicant Tracking + Onboarding, nothing else" },
  { icon: "lock", title: "Sensitive fields", question: "Which columns?", how: "Column-level permission", example: "Hourly rate and salary only for payroll roles" },
  { icon: "sparkles", title: "Tier", question: "What can they do?", how: "Workspace permissions VIEW / ANALYZE / AI", example: "AI only in the AI tier; Analyze locked for view-only users" },
];

const has = (perms: string[], ...want: string[]) => perms.includes("MANAGE") || want.some((w) => perms.includes(w));

function Check({ on, label }: { on: boolean; label?: string }) {
  return on ? <span className="cc-yes" title={label}>✓</span> : <span className="cc-no" title={label}>—</span>;
}

function WsCard({ w, isParent, users }: { w: OverviewWorkspace; isParent?: boolean; users: Persona[] }) {
  const { overview, navigate } = useApp();
  const t = w.themeId ? overview.themes[w.themeId] : undefined;
  const v = themeVars(t);
  const style = {
    "--t-bg": v["--ws-surface"],
    "--t-text": v["--ws-text"],
    "--t-muted": v["--ws-muted"],
    "--t-panel": v["--ws-panel"],
    "--t-line": v["--ws-line"],
    "--t-primary": v["--ws-primary"],
  } as CSSProperties;
  const clients = overview.wdfs.flatMap((f) => f.values[w.id] || []);

  return (
    <button className={`ws-card ${isParent ? "parent" : ""}`} style={style} onClick={() => navigate({ view: "ws", ws: w.id, tab: "home" })}>
      <div className="band" style={t?.cover ? { backgroundImage: `url('${t.cover}')` } : undefined}>
        <div className={`logo ${t?.logo ? "" : "dark"}`} style={{ background: logoTile(t) }}>
          {t?.logo ? <img src={t.logo} alt="" /> : <span style={{ color: v["--ws-primary"], fontWeight: 800 }}>GD</span>}
        </div>
      </div>
      <div className="body">
        <div className="t">{w.name.split(" · ")[0]}</div>
        <div className="s">
          <code>{w.id.length > 20 ? "parent" : w.id}</code> · {w.dashboards.length} dashboards {isParent ? "authored here" : "inherited"}
        </div>
        <dl className="kv">
          <dt>{isParent ? "Data" : clients.length > 1 ? "Clients" : "Client"}</dt>
          <dd>
            {isParent ? <span className="tchip">All clients, unfiltered</span> : clients.map((c) => <span key={c} className="tchip">{clientName(c)}</span>)}
          </dd>
          <dt>Users</dt>
          <dd className="people">
            {users.length ? (
              users.map((p) => (
                <span key={p.id} className={`avatar sm ${p.tierKey}`} title={`${p.name} · ${p.role}`}>
                  {p.initials}
                </span>
              ))
            ) : (
              <span className="tchip">{isParent ? "Viventium admins" : "—"}</span>
            )}
          </dd>
        </dl>
      </div>
    </button>
  );
}

export function ControlCenter() {
  const { overview: o, personas, personaWsPerms, groupName, switchPersona, toast } = useApp();
  const parent = o.workspaces.find((w) => w.isParent);
  const users = personas.filter((p) => p.id !== "admin");
  const usersIn = (wsId: string) => users.filter((p) => p.workspace === wsId);
  const tierOf = (w: OverviewWorkspace) => usersIn(w.id)[0]?.tierKey;
  const children = o.workspaces.filter((w) => !w.isParent).sort((a, b) => a.name.localeCompare(b.name));
  const unused = children.filter((w) => !tierOf(w));
  const featured = o.agents.filter((a) => a.conference);
  const permsOf = (p: Persona) => {
    const live = personaWsPerms(p.id, p.workspace);
    return live.length ? live : p.permissions;
  };

  return (
    <div className="page cc">
      <section className="cc-hero">
        <div>
          <div className="chip glass" style={{ marginBottom: 10 }}>Viventium internal · admin view</div>
          <h1>One template, three tiers</h1>
          <p>
            The data model, 11 data-product dashboards and reports are built once in the template and inherited by every client workspace. The tier decides
            whether a client gets its own workspace or shares one; data filters and permissions decide what each user sees.
          </p>
        </div>
        <div className="stats">
          <div className="stat"><b>3</b><span>tiers</span></div>
          <div className="stat"><b>{children.length - unused.length}</b><span>client workspaces</span></div>
          <div className="stat"><b>{Object.keys(CLIENT_NAMES).length}</b><span>clients</span></div>
          <div className="stat"><b>{users.length}</b><span>demo users</span></div>
        </div>
      </section>

      <div className="section-title">
        <h2>1 · Workspaces by tier</h2>
        <span className="muted small">Click a workspace to open it as admin. Switch user at the top to see it as that user.</span>
      </div>
      <div className="cc-template">
        {parent && <WsCard w={parent} isParent users={[]} />}
        <div className="cc-template-note">
          <b>Template (parent workspace)</b>
          <p>Shared data model, metrics, 11 dashboards (one per data product) and publisher reports. Viventium staff only; no client data filter.</p>
        </div>
      </div>
      <div className="cc-lanes">
        {TIERS.map((tier) => {
          const wss = children.filter((w) => tierOf(w) === tier.key);
          return (
            <div key={tier.key} className={`cc-lane ${tier.key}`}>
              <div className="cc-lane-h">
                <span className={`tier-badge ${tier.key}`}>{tier.title}</span>
                <p>{tier.what}</p>
                <dl>
                  <dt>Isolation</dt>
                  <dd>{tier.isolation}</dd>
                  <dt>Permissions</dt>
                  <dd>{tier.can}</dd>
                </dl>
              </div>
              {wss.map((w) => (
                <WsCard key={w.id} w={w} users={usersIn(w.id)} />
              ))}
            </div>
          );
        })}
      </div>
      {unused.length > 0 && (
        <p className="muted small" style={{ margin: "10px 2px 0" }}>
          Not used in this demo: {unused.map((w) => w.name).join(", ")} (earlier one-workspace-per-client setup).
        </p>
      )}

      <div className="section-title">
        <h2>2 · Five access layers</h2>
        <span className="muted small">Every workspace uses the same layers. All are enforced by GoodData, not by this app.</span>
      </div>
      <div className="cc-layers">
        {LAYERS.map((l) => (
          <div key={l.title} className="card cc-layer">
            <div className="cc-layer-h">
              <Icon name={l.icon} size={16} /> <b>{l.title}</b>
            </div>
            <div className="cc-layer-q">{l.question}</div>
            <div className="cc-layer-how">{l.how}</div>
            <div className="muted small">{l.example}</div>
          </div>
        ))}
      </div>

      <div className="section-title">
        <h2>3 · Who sees what</h2>
        <span className="muted small">One row per user, as GoodData resolves it. “View as” switches to that user.</span>
      </div>
      <div className="card">
        <table className="matrix cc-who">
          <thead>
            <tr>
              <th>User</th>
              <th>Workspace</th>
              <th>Client data</th>
              <th>Locations</th>
              <th>Data products (dashboards)</th>
              <th className="c">Build own</th>
              <th className="c">AI</th>
              <th className="c">Pay rates</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {TIERS.flatMap((tier) => users.filter((p) => p.tierKey === tier.key)).map((p) => {
              const perms = permsOf(p);
              const shard = p.tierKey === "base";
              return (
                <tr key={p.id}>
                  <td>
                    <div className="who">
                      <span className={`avatar ${p.tierKey}`}>{p.initials}</span>
                      <div>
                        <b>{p.name}</b>
                        <small>{p.role.split(" · ")[0]}</small>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className={`tier-badge ${p.tierKey}`}>{p.tier}</span>
                    <small className="cc-sub"><code>{p.workspace}</code></small>
                  </td>
                  <td>
                    <b>{p.client}</b>
                    <small className="cc-sub">{shard ? "only this client, in a shared workspace" : "whole workspace"}</small>
                  </td>
                  <td>{p.locations.join(", ")}</td>
                  <td>
                    <div className="cc-products">
                      {p.products.map((x) => (
                        <span key={x} className="chip muted">{x}</span>
                      ))}
                    </div>
                  </td>
                  <td className="c"><Check on={has(perms, "ANALYZE")} label="ANALYZE" /></td>
                  <td className="c"><Check on={has(perms, "USE_AI_ASSISTANT")} label="USE_AI_ASSISTANT" /></td>
                  <td className="c"><Check on={p.products.includes("Payroll")} label="column-level permission" /></td>
                  <td>
                    <button
                      className="btn"
                      disabled={!p.available}
                      onClick={() => switchPersona(p.id, null).then(() => toast(`Now viewing as ${p.name}`))}
                    >
                      View as →
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="section-title">
        <h2>4 · AI agents</h2>
        <span className="muted small">Configured once in AI Hub and assigned to user groups: only the AI-tier client (and Viventium admins) can use them.</span>
      </div>
      <div className="card">
        <table className="matrix">
          <thead>
            <tr>
              <th>Agent</th>
              <th>Skills</th>
              <th>Assigned to</th>
              {personas.map((p) => (
                <th key={p.id} className="c" title={`${p.name} · ${p.tier}`}>
                  <span className={`avatar sm ${p.tierKey}`} style={{ margin: "0 auto" }}>{p.initials}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {featured.map((a) => {
              const st = agentStyle(a.id);
              return (
                <tr key={a.id}>
                  <td>
                    <div className="agent-name">
                      <span className="ico" style={{ background: st.bg, color: st.fg }}><Icon name={st.ico} size={16} /></span>
                      <div>
                        <b>{a.name}</b>
                        <div className="muted small" style={{ maxWidth: 320 }}>{a.description}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div className="skills">
                      {(a.skills || []).slice(0, 4).map((s) => (
                        <span key={s} className="skill">{SKILL_LABEL[s] || s}</span>
                      ))}
                    </div>
                  </td>
                  <td>
                    {a.availableToAll ? (
                      <span className="chip ok">Everyone</span>
                    ) : (
                      a.groups.map((g) => (
                        <span key={g} className="chip muted" style={{ marginRight: 4 }}>{groupName(g)}</span>
                      ))
                    )}
                  </td>
                  {personas.map((p) => (
                    <td key={p.id} className="c">
                      <Check on={agentAccess(o, a, p.id)} />
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ height: 40 }} />
    </div>
  );
}
