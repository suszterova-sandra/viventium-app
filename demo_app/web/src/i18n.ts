export type Lang = "en" | "de" | "fr";

export const LANGS: { id: Lang; label: string; flag: string; locale: string; name: string }[] = [
  { id: "en", label: "EN", flag: "🇬🇧", locale: "en-US", name: "English" },
  { id: "de", label: "DE", flag: "🇩🇪", locale: "de-DE", name: "German" },
  { id: "fr", label: "FR", flag: "🇫🇷", locale: "fr-FR", name: "French" },
];

const D = {
  home: ["Home", "Startseite", "Accueil"],
  controlCenter: ["Control Center", "Kontrollzentrum", "Centre de contrôle"],
  administration: ["Administration", "Verwaltung", "Administration"],
  workspaces: ["Workspaces", "Arbeitsbereiche", "Espaces de travail"],
  signedInAs: ["Signed in as", "Angemeldet als", "Connecté en tant que"],
  parent: ["parent", "Eltern", "parent"],
  tenant: ["client", "Kunde", "client"],
  dashboards: ["Dashboards", "Dashboards", "Tableaux de bord"],
  aiReport: ["AI Report", "KI-Bericht", "Rapport IA"],
  analyze: ["Analyze", "Analysieren", "Analyser"],
  aiAssistant: ["AI Assistant", "KI-Assistent", "Assistant IA"],
  askAi: ["Ask AI", "KI fragen", "Demander à l'IA"],
  askAiAbout: ["Ask AI about this", "KI dazu fragen", "Interroger l'IA"],
  openDashboard: ["Open {d} dashboard", "Dashboard {d} öffnen", "Ouvrir le tableau de bord {d}"],
  openOverview: ["Open overview", "Übersicht öffnen", "Ouvrir la vue d'ensemble"],
  aiBusinessReport: ["AI data product report", "KI-Bericht zum Datenprodukt", "Rapport IA du produit de données"],
  goodMorning: ["Good morning", "Guten Morgen", "Bonjour"],
  goodAfternoon: ["Good afternoon", "Guten Tag", "Bon après-midi"],
  goodEvening: ["Good evening", "Guten Abend", "Bonsoir"],
  grew: ["rose", "stieg um", "a augmenté de"],
  fell: ["fell", "sank um", "a baissé de"],
  metricIn: ["{m} {dir} {pct} to {val} in {q}", "{m} {dir} {pct} auf {val} in {q}", "{m} {dir} {pct} pour atteindre {val} au {q}"],
  added: ["added", "brachte", "a ajouté"],
  tookAway: ["took away", "kostete", "a retiré"],
  ofChange: ["of the change", "der Veränderung", "de la variation"],
  comparedWith: ["Compared with {q}.", "Im Vergleich zu {q}.", "Par rapport au {q}."],
  overviewFallback: ["Here's your workforce at a glance", "Ihre Belegschaft auf einen Blick", "Vos effectifs en un coup d'œil"],
  vsIn: ["vs {v} in {q}", "ggü. {v} in {q}", "vs {v} au {q}"],
  keyDrivers: ["Key drivers", "Wichtigste Treiber", "Facteurs clés"],
  keyDriversSub: ["What moved {m} from {a} to {b}. Click to open the visualization.", "Was {m} von {a} bis {b} bewegt hat. Klicken öffnet die Visualisierung.", "Ce qui a fait bouger {m} de {a} à {b}. Cliquez pour ouvrir la visualisation."],
  noDriver: ["No single location or job role stands out this quarter.", "In diesem Quartal sticht kein Standort und keine Rolle hervor.", "Aucun site ni poste ne se démarque ce trimestre."],
  aiBriefing: ["AI briefing", "KI-Briefing", "Synthèse IA"],
  aiBriefingSub: ["GoodData AI · written for {u}", "GoodData KI · erstellt für {u}", "GoodData IA · rédigé pour {u}"],
  readingOverview: ["Reading the {d} dashboard…", "Dashboard {d} wird gelesen…", "Lecture du tableau de bord {d}…"],
  readFull: ["Read full briefing", "Ganzes Briefing lesen", "Lire la synthèse complète"],
  showLess: ["Show less", "Weniger anzeigen", "Afficher moins"],
  watchList: ["Watch list", "Beobachtungsliste", "À surveiller"],
  location: ["Location", "Standort", "Site"],
  jobRole: ["Job role", "Rolle", "Poste"],
  aiLockedTitle: ["AI is part of the AI tier", "KI ist Teil der KI-Stufe", "L'IA fait partie de l'offre IA"],
  aiLockedText: ["{u} has no AI Assistant permission in this workspace. The AI Assistant, AI briefings and agents come with Viventium's AI tier.", "{u} hat in diesem Arbeitsbereich keine KI-Assistent-Berechtigung. KI-Assistent, KI-Briefings und Agenten gehören zur KI-Stufe von Viventium.", "{u} n'a pas le droit Assistant IA dans cet espace. L'assistant IA, les synthèses IA et les agents font partie de l'offre IA de Viventium."],
  shared: ["Shared", "Geteilt", "Partagés"],
  private: ["Private", "Privat", "Privés"],
  newDashboard: ["New dashboard", "Neues Dashboard", "Nouveau tableau de bord"],
  newDashboardHint: ["Drag a visualization into the layout, then Save. New dashboards start private.", "Visualisierung in das Layout ziehen und speichern. Neue Dashboards sind zunächst privat.", "Faites glisser une visualisation puis enregistrez. Les nouveaux tableaux de bord sont privés."],
  refreshList: ["Refresh list", "Liste aktualisieren", "Actualiser"],
  agenticSummary: ["Agentic summary", "Agentische Zusammenfassung", "Synthèse agentique"],
  openInGoodData: ["Open in GoodData", "In GoodData öffnen", "Ouvrir dans GoodData"],
  summary: ["Summary", "Zusammenfassung", "Synthèse"],
  keyPoints: ["Key points", "Kernpunkte", "Points clés"],
  clickForKda: ["click one to run key driver analysis", "klicken für eine Treiberanalyse", "cliquez pour analyser les facteurs clés"],
  areasToWatch: ["Areas to watch", "Im Blick behalten", "Points de vigilance"],
  why: ["Why?", "Warum?", "Pourquoi ?"],
  regenerate: ["Regenerate", "Neu erstellen", "Régénérer"],
  hide: ["Hide", "Ausblenden", "Masquer"],
  summarizing: ["Summarizing dashboard", "Dashboard wird zusammengefasst", "Synthèse du tableau de bord"],
  kda: ["Key driver analysis", "Treiberanalyse", "Analyse des facteurs clés"],
  runningKda: ["Running GoodData key driver analysis…", "GoodData-Treiberanalyse läuft…", "Analyse des facteurs clés en cours…"],
  significant: ["significant", "signifikant", "significatif"],
  ofChangeShort: ["of change", "der Änderung", "de la variation"],
  discussSummary: ["Discuss with the AI Assistant", "Mit dem KI-Assistenten besprechen", "En discuter avec l'assistant IA"],
  askWhatToDo: ["Ask the AI Assistant what to do", "KI-Assistent fragen, was zu tun ist", "Demander à l'assistant IA quoi faire"],
  exportPdf: ["Export PDF", "PDF exportieren", "Exporter en PDF"],
  loadingDashboards: ["Loading dashboards…", "Dashboards werden geladen…", "Chargement des tableaux de bord…"],
  noDashboards: ["No dashboards yet", "Noch keine Dashboards", "Aucun tableau de bord"],
} as const;

export type Key = keyof typeof D;
const IDX: Record<Lang, number> = { en: 0, de: 1, fr: 2 };

export function translate(lang: Lang, key: Key, vars?: Record<string, string>) {
  let s: string = D[key][IDX[lang]];
  for (const [k, v] of Object.entries(vars || {})) s = s.replace(`{${k}}`, v);
  return s;
}

export const languageName = (lang: Lang) => LANGS.find((l) => l.id === lang)!.name;
export const localeOf = (lang: Lang) => LANGS.find((l) => l.id === lang)!.locale;
