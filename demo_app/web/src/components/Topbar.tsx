import { useEffect, useRef, useState } from "react";
import { useApp } from "../AppContext";
import type { ColorMode } from "../theme";
import { useChatbot } from "./Chatbot";
import { LANGS, type Lang } from "../i18n";
import { adminLoginUrl, STATIC } from "../staticBackend";
import { Icon } from "../icons";
import type { Persona, TierKey } from "../types";

const TIER_SHORT: Record<TierKey, string> = { admin: "Internal", ai: "AI tier", analytics: "Analytics", base: "Base shard" };

export function Topbar({ mode, onSetMode }: { mode: ColorMode; onSetMode: (m: ColorMode) => void }) {
  const { personas, persona, switchPersona, route, toast, lang, setLang, t, brand } = useApp();
  const chatbot = useChatbot();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const [whoOpen, setWhoOpen] = useState(false);
  const whoRef = useRef<HTMLDivElement>(null);

  const pick = (p: Persona) => {
    setWhoOpen(false);
    if (STATIC && p.id === "admin" && !p.available) {
      window.location.href = adminLoginUrl(); // GoodData login, then back here as the admin
      return;
    }
    if (p.id !== persona.id) switchPersona(p.id, route).then(() => toast(`${p.name} · ${p.role}`));
  };

  useEffect(() => {
    if (!whoOpen) return;
    const close = (e: MouseEvent) => !whoRef.current?.contains(e.target as Node) && setWhoOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [whoOpen]);
  // dark mode belongs to the platform pages; tenant pages and tenant users always carry the store's brand
  const darkAvailable = !brand.theme && route.view !== "ws";

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent) => !menuRef.current?.contains(e.target as Node) && setMenuOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menuOpen]);

  return (
    <header className="topbar">
      <div className="crumbs">
        {route.view === "home" && <b>{t("home")}</b>}
        {route.view === "control" && <b>{t("controlCenter")}</b>}
      </div>
      <div className="top-right">
        <button className={`ai-top-btn ${chatbot.isOpen ? "on" : ""}`} onClick={() => (chatbot.isOpen ? chatbot.close() : chatbot.open())}>
          <Icon name="sparkles" size={15} /> {t("aiAssistant")}
        </button>

        <div className="persona-switch" role="tablist" aria-label="Switch user">
          {personas.map((p) => (
            <button
              key={p.id}
              role="tab"
              aria-selected={p.id === persona.id}
              className={p.id === persona.id ? "active" : ""}
              disabled={!p.available && !(STATIC && p.id === "admin")}
              title={`${p.name} · ${p.role}\n${p.tier} · ${p.products.join(", ")}\n${p.locations.join(", ")}${!p.available && STATIC && p.id === "admin" ? "\nSign in with your GoodData account" : ""}`}
              onClick={() => pick(p)}
            >
              <span className={`avatar sm ${p.tierKey}`}>{p.initials}</span>
              <span className="ps-text">
                <span className="ps-name">{p.id === "admin" ? "Admin" : p.name.split(" ")[0]}</span>
                <span className="ps-sub">
                  {TIER_SHORT[p.tierKey]} · {p.client.split(" ")[0]}
                </span>
              </span>
            </button>
          ))}
        </div>

        <div className="who-menu" ref={whoRef}>
          <button className={`icon-btn ${whoOpen ? "on" : ""}`} onClick={() => setWhoOpen((o) => !o)} aria-label="Who is who" aria-expanded={whoOpen} title="Who is who">
            <Icon name="users" size={17} />
          </button>
          {whoOpen && (
            <div className="who-panel" role="menu">
              {personas.map((p) => (
                <button key={p.id} className={`who-card ${p.id === persona.id ? "on" : ""}`} disabled={!p.available && !(STATIC && p.id === "admin")} onClick={() => pick(p)}>
                  <span className={`avatar ${p.tierKey}`}>{p.initials}</span>
                  <span className="wc-main">
                    <span className="wc-head">
                      <b>{p.name}</b> <span className={`tier-badge ${p.tierKey}`}>{p.tier}</span>
                    </span>
                    <span className="wc-role">{p.role}</span>
                    <span className="wc-chips">
                      {p.products.map((x) => (
                        <span key={x} className="wc-chip">{x}</span>
                      ))}
                    </span>
                    <span className="wc-meta">
                      <Icon name="pin" size={12} /> {p.locations.join(", ")} · {p.permissions.map((x) => x.replace(/_/g, " ")).join(", ")}
                    </span>
                    <span className="wc-story">{p.tagline}</span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* language: always visible, it switches the app, the dashboards and the translated metadata */}
        <div className="lang-seg" role="radiogroup" aria-label="Language">
          <Icon name="globe" size={15} />
          {LANGS.map((l) => (
            <button key={l.id} role="radio" aria-checked={l.id === lang} className={l.id === lang ? "on" : ""} onClick={() => setLang(l.id as Lang)} title={l.name}>
              {l.label}
            </button>
          ))}
        </div>

        <div className="settings" ref={menuRef}>
          <button className={`icon-btn ${menuOpen ? "on" : ""}`} onClick={() => setMenuOpen((o) => !o)} aria-label="Appearance" aria-expanded={menuOpen} title="Appearance">
            <Icon name="settings" size={17} />
          </button>
          {menuOpen && (
            <div className="settings-menu" role="menu">
              <div className="sm-label">
                <Icon name="sun" size={14} /> Appearance
              </div>
              <div className="seg">
                <button className={mode === "light" || !darkAvailable ? "on" : ""} onClick={() => onSetMode("light")}>
                  <Icon name="sun" size={14} /> Light
                </button>
                <button className={mode === "dark" && darkAvailable ? "on" : ""} disabled={!darkAvailable} onClick={() => onSetMode("dark")}>
                  <Icon name="moon" size={14} /> Dark
                </button>
              </div>
              {!darkAvailable && <div className="sm-hint">Pages use the workspace brand theme.</div>}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
