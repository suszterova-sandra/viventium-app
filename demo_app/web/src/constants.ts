import type { IconName } from "./icons";

export const AGENT_STYLE: Record<string, { ico: IconName; bg: string; fg: string; short: string }> = {
  "viventium-summary-agent": { ico: "summary", bg: "#EDE9FE", fg: "#5B21B6", short: "Summary" },
  "viventium-next-steps-agent": { ico: "compass", bg: "#FEF3C7", fg: "#B45309", short: "Next steps" },
  "viventium-compliance-agent": { ico: "shield", bg: "#DCFCE7", fg: "#15803D", short: "Compliance" },
};

export const agentStyle = (id: string) => AGENT_STYLE[id] || { ico: "bot" as IconName, bg: "#F1F5F9", fg: "#334155", short: "Assistant" };

/** Viventium's own agents (AI Hub) carry this id prefix. */
export const isViventiumAgent = (id: string) => id.startsWith("viventium-");

export const PLAYBOOK = [
  {
    agent: "viventium-summary-agent",
    title: "Summarize",
    sub: "What happened and why",
    prompt: "Summarize the workforce over the last 3 months: overtime %, call-off rate, turnover and gross pay. Which facility or job role stands out?",
  },
  {
    agent: "viventium-next-steps-agent",
    title: "Next steps",
    sub: "Who does what this week",
    prompt: "Based on these results, what should the administrator, DON, scheduler and payroll team do in the next two weeks to bring overtime and call-offs down?",
  },
  {
    agent: "viventium-compliance-agent",
    title: "Compliance check",
    sub: "Risks with exposure",
    prompt: "Where are we exposed? Check the ACA offer rate against the 95% test, penalty exposure, exclusion screening matches and overtime by facility.",
  },
];

export const SKILL_LABEL: Record<string, string> = {
  visualization: "Visualization",
  key_driver_analysis: "Key drivers",
  alert: "Alerts",
  knowledge: "Knowledge",
  schedule_export: "Scheduled exports",
  anomaly_detection: "Anomalies",
  what_if_analysis: "What-if",
  forecasting: "Forecasting",
  metric: "Metrics",
  clustering: "Clustering",
  dashboard_builder: "Dashboard builder",
  dashboard_editor: "Dashboard editor",
  visualization_summary: "Viz summary",
  dashboard_summary: "Dashboard summary",
  report_builder: "Report builder",
  document_builder: "Document builder",
};

export const KEY_PERMS = ["MANAGE", "ANALYZE", "VIEW"];
