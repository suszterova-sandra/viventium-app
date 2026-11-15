import { gd } from "./api";
import type { PersonaId } from "./types";

/**
 * Agentic dashboard summary (as in goodsalesv4's DashboardAgenticSummary), rebuilt on the REST API
 * because dashboards here are iframes: GoodData's AI summary in a fixed structure, and key points that
 * run key driver (change) analysis for the metric they mention, all as the current user.
 */

const FORMAT_HINT = [
  "Structure the answer with exactly these three markdown sections and nothing else:",
  "## Summary - 2 to 3 sentences with the headline numbers for the filtered period.",
  "## Key Insights - 3 to 5 bullets; start each bullet with the metric name in bold, exactly as it is named on the dashboard, followed by its value and change.",
  "## Areas to Watch - 2 or 3 short, actionable recommendations, one per bullet.",
  "Use **bold** for key figures.",
].join("\n");

export interface ParsedSummary {
  summary: string;
  insights: string[];
  recommendations: string[];
  generatedAt?: string;
  visualizations: number;
}

const stripBullet = (line: string) => line.replace(/^\s*(?:[-*•]|\d+\.)\s+/, "").trim();

export function parseSummary(md: string): Omit<ParsedSummary, "visualizations"> {
  const sections = new Map<string, string[]>();
  let current = "summary";
  for (const line of md.split("\n")) {
    const heading = line.match(/^#{1,4}\s+(.+)$/);
    if (heading) {
      current = heading[1].trim().toLowerCase();
      continue;
    }
    if (line.trim()) sections.set(current, [...(sections.get(current) ?? []), line]);
  }
  const find = (...keys: string[]) => [...sections.entries()].find(([h]) => keys.some((k) => h.includes(k)))?.[1] ?? [];
  return {
    summary: find("summary").map(stripBullet).join(" "),
    insights: find("insight", "highlight").map(stripBullet).filter(Boolean),
    recommendations: find("watch", "recommend").map(stripBullet).filter(Boolean),
  };
}

const summaries = new Map<string, Promise<ParsedSummary>>();

export function dashboardSummary(persona: PersonaId, ws: string, dashboardId: string, force = false, language = "English") {
  const key = `${persona}|${ws}|${dashboardId}|${language}`;
  if (force || !summaries.has(key)) {
    // GoodData's AI summary occasionally fails with a 5xx under load: retry twice before giving up
    const call = (attempt: number): Promise<any> =>
      gd(persona, `/api/v1/ai/workspaces/${ws}/summary`, {
        method: "POST",
        body: JSON.stringify({ dashboardId, formatHint: `${FORMAT_HINT}\nKeep the three section headings in English, but write all other text in ${language}.` }),
      }).catch(async (e) => {
        if (e.status >= 500 && attempt < 2) {
          await new Promise((r) => setTimeout(r, 1500 * (attempt + 1)));
          return call(attempt + 1);
        }
        throw e;
      });
    const p = call(0).then((r) => ({ ...parseSummary(r.summary), generatedAt: r.generatedAt, visualizations: r.visualizationsIncluded?.length || 0 }));
    p.catch(() => summaries.delete(key));
    summaries.set(key, p);
  }
  return summaries.get(key)!;
}

// ------------------------------------------------------------------ metrics: tie a key point to a metric

export interface Metric {
  id: string;
  title: string;
}

const normalize = (t: string) => t.toLowerCase().replace(/[^a-z0-9%]+/g, " ").trim();
const metricLists = new Map<string, Promise<Metric[]>>();

export function workspaceMetrics(persona: PersonaId, ws: string) {
  const key = `${persona}|${ws}`;
  if (!metricLists.has(key)) {
    const p = gd(persona, `/api/v1/entities/workspaces/${ws}/metrics?size=500&origin=ALL`).then((r) =>
      r.data.map((m: any) => ({ id: m.id, title: m.attributes.title || m.id })),
    );
    p.catch(() => metricLists.delete(key));
    metricLists.set(key, p);
  }
  return metricLists.get(key)!;
}

// common dashboard wording -> metric id, checked before the fuzzy title match
const ALIASES: [RegExp, string][] = [
  [/overtime %|overtime percent|overtime share|\bot %|overtime rate/, "ta_ot_pct"],
  [/ot pay|overtime pay/, "pr_ot_share"],
  [/overtime hours/, "ta_ot_hours"],
  [/overtime/, "ta_ot_pct"],
  [/call ?offs? rate|call ?off|no.?show/, "sch_calloff_rate"],
  [/agency/, "sch_agency_cost"],
  [/coverage/, "sch_coverage_rate"],
  [/uncovered|missed visits/, "sch_uncovered"],
  [/scheduled hours/, "sch_scheduled_hours"],
  [/worked hours/, "ta_worked_hours"],
  [/late punch|tardiness|\blate\b/, "ta_late_rate"],
  [/missed punch/, "ta_missed_punch_rate"],
  [/early turnover/, "hr_early_turnover"],
  [/voluntary turnover/, "hr_vol_turnover"],
  [/turnover|attrition/, "hr_turnover"],
  [/terminations?|separations?/, "hr_terms"],
  [/headcount/, "hr_headcount_eom"],
  [/gross pay|payroll cost|gross wages/, "pr_gross"],
  [/net pay/, "pr_net"],
  [/employer cost|labor cost|cost of labor/, "pr_total_cost"],
  [/employer taxes/, "pr_er_taxes"],
  [/paycheck/, "pr_avg_check"],
  [/time to fill/, "ats_time_to_fill"],
  [/days to hire/, "ats_days_to_hire"],
  [/applications?|applicants?/, "ats_applications"],
  [/open req|requisitions?/, "ats_open_reqs"],
  [/first contact/, "ats_hours_first_contact"],
  [/job spend|sponsored/, "ats_spend"],
  [/\bhires?\b|new hires/, "hr_hires"],
  [/offer rate|95%|aca offer/, "aca_offer_rate"],
  [/penalty|exposure/, "aca_exposure"],
  [/affordab/, "aca_affordability"],
  [/medical participation|take.?up/, "ben_med_participation"],
  [/401 ?k/, "ben_401k_participation"],
  [/on.?demand|amount advanced|draws?/, "odp_amount"],
  [/onboarding|onboarded/, "ob_new_hires"],
  [/training completion|completion rate|courses?/, "lms_completion_rate"],
  [/ceu/, "lms_ceu"],
  [/confirmed match/, "exc_confirmed"],
  [/exclusion|potential match/, "exc_potential"],
];

/** The metric a key point talks about: its bold lead first, then aliases, then the longest title match. */
export function matchMetric(text: string, metrics: Metric[]): Metric | undefined {
  const lead = normalize(text.match(/\*\*(.+?)\*\*/)?.[1] ?? "");
  const body = normalize(text);
  const byId = new Map(metrics.map((m) => [m.id, m]));
  for (const probe of [lead, body]) {
    for (const [re, id] of ALIASES) if (re.test(probe) && byId.has(id)) return byId.get(id);
  }
  let best: { m: Metric; score: number } | undefined;
  for (const m of metrics) {
    const name = normalize(m.title);
    if (name.length < 4) continue;
    const score = lead === name ? 1000 + name.length : body.includes(name) ? name.length : 0;
    if (score > (best?.score ?? 0)) best = { m, score };
  }
  return best?.m;
}

// ------------------------------------------------------------------ key driver analysis

export interface DriverChange {
  attribute: string;
  value: string;
  analyzed: number;
  reference: number;
  delta: number;
  significant: boolean;
  share: number; // of the overall change
}

export interface KdaResult {
  metric: Metric;
  period: { reference: string; analyzed: string };
  overall: { reference: number; analyzed: number };
  drivers: DriverChange[];
  restricted: number;
}

/** Quarter labels in the API's format (YYYY-Q), for the dashboards' default "last quarter" filter. */
export function lastQuarters() {
  const now = new Date();
  const toQ = (offset: number) => {
    let q = Math.floor(now.getMonth() / 3) + offset;
    let y = now.getFullYear();
    while (q < 0) {
      q += 4;
      y -= 1;
    }
    return { api: `${y}-${q + 1}`, label: `Q${q + 1} ${y}` };
  };
  return { analyzed: toQ(-1), reference: toQ(-2) };
}

const pretty = (id: string) => id.replace(/^.*\./, "").replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const kdaCache = new Map<string, Promise<KdaResult>>();

export function keyDrivers(persona: PersonaId, ws: string, metric: Metric) {
  const key = `${persona}|${ws}|${metric.id}`;
  if (!kdaCache.has(key)) {
    const p = (async () => {
      const { analyzed, reference } = lastQuarters();
      const start = await gd(persona, `/api/v1/actions/workspaces/${ws}/execution/computeChangeAnalysis`, {
        method: "POST",
        body: JSON.stringify({
          measure: { localIdentifier: "m", definition: { measure: { item: { identifier: { id: metric.id, type: "metric" } } } } },
          dateAttribute: { localIdentifier: "d", label: { identifier: { id: "activity_date.quarter", type: "label" } } },
          referencePeriod: reference.api,
          analyzedPeriod: analyzed.api,
        }),
      });
      const rid = start.links.executionResult;
      let res: any;
      for (let i = 0; i < 60; i++) {
        res = await gd(persona, `/api/v1/actions/workspaces/${ws}/execution/computeChangeAnalysis/result/${rid}`).catch((e) => {
          if (e.status === 404 || e.status === 202) return null;
          throw e;
        });
        if (res?.data) break;
        await new Promise((r) => setTimeout(r, 2000));
      }
      const rows: any[] = res?.data || [];
      const overall = rows[0]
        ? { reference: rows[0].overallMetricValueInReferencePeriod, analyzed: rows[0].overallMetricValueInAnalyzedPeriod }
        : { reference: 0, analyzed: 0 };
      const total = overall.analyzed - overall.reference;
      // an attribute with a single value just repeats the total; it explains nothing
      // technical attributes (ids, images, coordinates, e-mails) are not business drivers
      const NOISE = /(^|[._])(id|image|img|url|email|latitude|longitude|pushpin|code)([._]|$)|image|pushpin/i;
      const informative = rows.filter(
        (r) => (r.attributeValuesChangeStd > 0 || r.isSignificantChange) && !NOISE.test(r.attributeRef?.identifier?.id || r.attributeName || ""),
      );
      const ranked = [...informative].sort((a, b) => Number(b.isSignificantChange) - Number(a.isSignificantChange) || b.metricValueDeltaAbs - a.metricValueDeltaAbs);
      const seen = new Set<string>();
      const perAttribute = new Map<string, number>();
      const drivers: DriverChange[] = [];
      for (const r of ranked) {
        const k = `${r.attributeName}|${r.attributeValue}`;
        if (seen.has(k) || (perAttribute.get(r.attributeName) ?? 0) >= 2) continue;
        seen.add(k);
        perAttribute.set(r.attributeName, (perAttribute.get(r.attributeName) ?? 0) + 1);
        drivers.push({
          attribute: pretty(r.attributeRef?.identifier?.id || r.attributeName),
          value: r.attributeValue,
          analyzed: r.metricValueInAnalyzedPeriod,
          reference: r.metricValueInReferencePeriod,
          delta: r.metricValueDelta,
          significant: r.isSignificantChange,
          share: total ? r.metricValueDelta / Math.abs(total) : 0,
        });
        if (drivers.length >= 6) break;
      }
      return {
        metric,
        period: { reference: reference.label, analyzed: analyzed.label },
        overall,
        drivers,
        restricted: res?.restrictedCount || 0,
      };
    })();
    p.catch(() => kdaCache.delete(key));
    kdaCache.set(key, p);
  }
  return kdaCache.get(key)!;
}
