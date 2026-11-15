import { Fragment, type CSSProperties } from "react";
import { agentAccess, useApp } from "../AppContext";
import { agentStyle, KEY_PERMS, SKILL_LABEL } from "../constants";
import { Icon } from "../icons";
import { logoTile, themeVars } from "../theme";
import type { OverviewWorkspace } from "../types";

const personaLabel = (name: string, id: string) => (id === "admin" ? "Admin" : name);

function WsCard({ w, isParent }: { w: OverviewWorkspace; isParent?: boolean }) {
  const { overview, personas, personaWsPerms, navigate } = useApp();
  const t = w.themeId ? overview.themes[w.themeId] : undefined;
  const v = themeVars(t);
  const comp = t?.palette.complementary || {};
  const style = {
    "--t-bg": v["--ws-surface"],
    "--t-text": v["--ws-text"],
    "--t-muted": v["--ws-muted"],
    "--t-panel": v["--ws-panel"],
    "--t-line": v["--ws-line"],
    "--t-primary": v["--ws-primary"],
  } as CSSProperties;
  const wdf = overview.wdfs.map((f) => ({ f, vals: f.values[w.id] })).filter((x) => x.vals);
  const people = personas.filter((p) => p.id !== "admin" && personaWsPerms(p.id, w.id).length);

  return (
    <button className={`ws-card ${isParent ? "parent" : ""}`} style={style} onClick={() => navigate({ view: "ws", ws: w.id, tab: "home" })}>
      <div className="band" style={t?.cover ? { backgroundImage: `url('${t.cover}')` } : undefined}>
        <div className={`logo ${t?.logo ? "" : "dark"}`} style={{ background: logoTile(t) }}>
          {t?.logo ? <img src={t.logo} alt="" /> : <span style={{ color: v["--ws-primary"], fontWeight: 800 }}>GD</span>}
        </div>
      </div>
      <div className="body">
        <div className="t">{w.name}</div>
        <div className="s">{isParent ? "Viventium template · source of the shared model" : "Client workspace · inherits from the template"}</div>
        <dl className="kv">
          <dt>Theme</dt>
          <dd>
            <span className="swatches">
              {[t?.palette.primary?.base, comp.c0, comp.c2, comp.c9].filter(Boolean).map((c, i) => (
                <i key={i} style={{ background: c }} />
              ))}
            </span>
            <span className="tchip">{t?.name || w.themeId || "default"}</span>
          </dd>
          {isParent ? (
            <>
              <dt>Data</dt>
              <dd>
                <span className="tchip">All clients</span>
              </dd>
            </>
          ) : (
            wdf.map((x) => (
              <Fragment key={x.f.id}>
                <dt>{x.f.title}</dt>
                <dd>
                  {x.vals.map((val) => (
                    <span key={val} className="tchip">{val}</span>
                  ))}
                </dd>
              </Fragment>
            ))
          )}
          <dt>Content</dt>
          <dd>
            <span className="tchip">{w.dashboards.length} dashboards {isParent ? "authored" : "inherited"}</span>
            <span className="tchip">data product reports</span>
          </dd>
          <dt>Users</dt>
          <dd className="people">
            {people.length ? (
              people.map((p) => (
                <span key={p.id} className={`avatar sm ${p.tierKey}`} title={`${p.name} · ${p.role}: ${personaWsPerms(p.id, w.id).slice(0, 2).join(", ")}`}>
                  {p.initials}
                </span>
              ))
            ) : (
              <span className="tchip">admins only</span>
            )}
          </dd>
        </dl>
      </div>
    </button>
  );
}

/** Parent → one drop per child column (viewBox 300 wide). */
function connectorPath(n: number) {
  if (n < 1) return "M150 0 V36";
  const xs = Array.from({ length: n }, (_, i) => (300 / n) * (i + 0.5));
  return `M150 0 V14 M${xs[0]} 14 H${xs[n - 1]} ${xs.map((x) => `M${x} 14 V36`).join(" ")}`;
}

export function ControlCenter() {
  const { overview: o, personas, personaWsPerms, groupName, switchPersona, toast } = useApp();
  const parent = o.workspaces.find((w) => w.isParent);
  const children = o.workspaces.filter((w) => !w.isParent).sort((a, b) => a.name.localeCompare(b.name));
  const ordered = [...(parent ? [parent] : []), ...children];
  const featured = o.agents.filter((a) => a.conference);
  // the org also hosts other demos: list only the other agents someone in this demo can reach
  const demoGroups = new Set(Object.values(o.members).flat());
  const others = o.agents.filter((a) => !a.conference && (a.availableToAll || a.groups.some((g) => demoGroups.has(g))));

  return (
    <div className="page">
      <section className="cc-hero">
        <div>
          <div className="chip glass" style={{ marginBottom: 10 }}>Admin perspective</div>
          <h1>{parent?.name || "Parent workspace"}</h1>
          <p>One governed workforce model for post-acute care clients, delivered in tiers: AI and Analytics clients get a dedicated, branded workspace; Base clients share a view-only shard. Each user sees only their client's rows, their data products and the AI agents their tier includes.</p>
        </div>
        <div className="stats">
          <div className="stat"><b>{children.length}</b><span>client workspaces</span></div>
          <div className="stat"><b>{parent?.dashboards.length || 0}</b><span>shared dashboards</span></div>
          <div className="stat"><b>{o.wdfs.length}</b><span>data filters</span></div>
          <div className="stat"><b>{featured.length}</b><span>custom agents</span></div>
        </div>
      </section>

      <div className="section-title">
        <h2>Workspace hierarchy</h2>
        <span className="muted small">Children inherit the model, dashboards and the data product reports from the template; theme and client data filter are set per workspace. Click a card to open it.</span>
      </div>
      <div className="tree">
        <div className="parent-row">{parent && <WsCard w={parent} isParent />}</div>
        <div className="connector">
          <svg preserveAspectRatio="none" viewBox="0 0 300 36">
            <path d={connectorPath(children.length)} stroke="var(--ws-muted)" strokeWidth="1" fill="none" vectorEffect="non-scaling-stroke" />
          </svg>
        </div>
        <div className="children" style={{ "--cols": Math.max(children.length, 1) } as CSSProperties}>
          {children.map((c) => (
            <WsCard key={c.id} w={c} />
          ))}
        </div>
      </div>

      <div className="section-title">
        <h2>Who sees what</h2>
        <span className="muted small">Workspace permissions resolved through user groups. Switch user in the top right to see each scenario live.</span>
      </div>
      <div className="card">
        <table className="matrix">
          <thead>
            <tr>
              <th>User</th>
              <th>Groups</th>
              {ordered.map((w) => (
                <th key={w.id}>{w.name}</th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {personas.map((p) => (
              <tr key={p.id}>
                <td>
                  <div className="who">
                    <span className={`avatar ${p.tierKey}`}>{p.initials}</span>
                    <div>
                      <b>{p.name}</b> <span className={`tier-badge ${p.tierKey}`}>{p.tier}</span>
                      <small>{p.role}</small>
                      <small>{p.products.join(" · ")} — {p.locations.join(", ")}</small>
                    </div>
                  </div>
                </td>
                <td>
                  {(o.members[p.id] || []).map((g) => (
                    <span key={g} className="chip muted" style={{ marginRight: 4 }}>{groupName(g)}</span>
                  ))}
                </td>
                {ordered.map((w) => {
                  const perms = personaWsPerms(p.id, w.id);
                  return (
                    <td key={w.id}>
                      {perms.length ? (
                        perms.map((x) => (
                          <span key={x} className={`perm ${KEY_PERMS.includes(x) ? "key" : ""}`}>{x.replace(/_/g, " ")}</span>
                        ))
                      ) : (
                        <span className="none">no access</span>
                      )}
                    </td>
                  );
                })}
                <td>
                  {p.id !== "admin" && (
                    <button
                      className="btn"
                      disabled={!p.available}
                      title={p.available ? "" : "Run setup_tokens.py"}
                      onClick={() => switchPersona(p.id, null).then(() => toast(`Now viewing as ${p.name}`))}
                    >
                      View as →
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-title">
        <h2>AI Hub agents</h2>
        <span className="muted small">Agents are configured once in AI Hub and assigned to user groups. The three Viventium agents are assigned to the AI-tier client and admins only.</span>
      </div>
      <div className="card">
        <table className="matrix">
          <thead>
            <tr>
              <th>Agent</th>
              <th>Skills</th>
              <th>Assigned to</th>
              {personas.map((p) => (
                <th key={p.id} style={{ textAlign: "center" }}>{personaLabel(p.name, p.id)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...featured, ...others].map((a) => {
              const st = agentStyle(a.id);
              return (
                <tr key={a.id} className={a.conference ? "featured-row" : ""}>
                  <td>
                    <div className="agent-name">
                      <span className="ico" style={{ background: st.bg, color: st.fg }}><Icon name={st.ico} size={16} /></span>
                      <div>
                        <b>{a.name}</b> {a.conference && <span className="badge-hub">new</span>}
                        <div className="muted small" style={{ maxWidth: 360 }}>{a.description}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div className="skills">
                      {(a.skills || []).map((s) => (
                        <span key={s} className="skill">{SKILL_LABEL[s] || s}</span>
                      ))}
                    </div>
                  </td>
                  <td>
                    {a.availableToAll ? (
                      <span className="chip ok">Everyone</span>
                    ) : a.groups.length ? (
                      a.groups.map((g) => (
                        <span key={g} className="chip muted" style={{ marginRight: 4 }}>{groupName(g)}</span>
                      ))
                    ) : (
                      <span className="none">nobody</span>
                    )}
                  </td>
                  {personas.map((p) => (
                    <td key={p.id} style={{ textAlign: "center" }}>
                      {agentAccess(o, a, p.id) ? <span className="yes">✓</span> : <span className="none">—</span>}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted small" style={{ margin: "14px 2px 40px" }}>
        Data filters:{" "}
        {o.wdfs.map((f, i) => (
          <span key={f.id}>
            {i > 0 && ", "}
            <b>{f.title}</b> (<code>{f.column}</code>)
          </span>
        ))}
        .
      </p>
    </div>
  );
}
