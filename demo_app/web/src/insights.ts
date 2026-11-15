import { gd } from "./api";
import { PRODUCTS, productsOf, type Format, type Product, type ProductKpi } from "./products";
import type { PersonaId } from "./types";

/** Where each number lives in GoodData, so a tile or driver opens the dashboard at that visualization. */
export interface Target {
  dashboard: string;
  viz: string;
  vizTitle: string;
  dashTitle: string;
}

export interface Kpi {
  id: string;
  label: string;
  metric: string;
  format: Format;
  goodWhenUp: boolean;
  target: Target;
  product: string;
  cur?: number;
  prev?: number;
}

const T = (dashboard: string, dashTitle: string, viz: string, vizTitle: string): Target => ({ dashboard, dashTitle, viz, vizTitle });

const toKpi = (p: Product, x: ProductKpi): Kpi => ({
  id: x.metric,
  label: x.label,
  metric: x.metric,
  format: x.format,
  goodWhenUp: x.goodWhenUp,
  product: p.name,
  target: T(p.dashboard, p.dashTitle, x.viz, x.label),
});

/** Round-robin over the products: the first KPI of each product, then the second one, ... */
function roundRobin(products: Product[], pick: (p: Product) => ProductKpi[]): Kpi[] {
  const out: Kpi[] = [];
  const depth = Math.max(0, ...products.map((p) => pick(p).length));
  for (let i = 0; i < depth; i++) for (const p of products) if (pick(p)[i]) out.push(toKpi(p, pick(p)[i]));
  return out;
}

// key drivers: the lead KPI sliced by location and by job role (both labels exist on every product's data)
const DIMS = [
  { id: "location", label: "locations.location_id.location_name", noun: "Location", target: (p: Product) => T(p.dashboard, p.dashTitle, p.byLocation.viz, p.byLocation.title) },
  { id: "job_role", label: "job_roles.job_role_id.job_title", noun: "Job role", target: (p: Product) => T(p.dashboard, p.dashTitle, p.byRole.viz, p.byRole.title) },
];

export interface Driver {
  dim: string;
  noun: string;
  member: string;
  cur: number;
  prev: number;
  delta: number;
  share: number; // of the lead KPI's total change, signed (0 for rates, where shares do not add up)
  format: Format;
  target: Target;
}

export interface Insights {
  period: { cur: string; prev: string };
  /** the data product the headline and the drivers come from */
  lead?: Product;
  kpis: Kpi[];
  watch: Kpi[];
  drivers: Driver[];
}

// ------------------------------------------------------------------ execution (as the persona)

const DATE_DATASET = "activity_date";

const measure = (lid: string, metric: string, quarter: number) => ({
  localIdentifier: lid,
  definition: {
    measure: {
      item: { identifier: { id: metric, type: "metric" } },
      filters: [{ relativeDateFilter: { dataset: { identifier: { id: DATE_DATASET, type: "dataset" } }, granularity: "QUARTER", from: quarter, to: quarter } }],
    },
  },
});

async function execute(persona: PersonaId, ws: string, execution: any, dims: any[]) {
  const r = await gd(persona, `/api/v1/actions/workspaces/${ws}/execution/afm/execute`, {
    method: "POST",
    body: JSON.stringify({ execution: { filters: [], ...execution }, resultSpec: { dimensions: dims } }),
  });
  return gd(persona, `/api/v1/actions/workspaces/${ws}/execution/afm/execute/result/${r.executionResponse.links.executionResult}`);
}

const num = (v: any) => (v === null || v === undefined || v === "" ? undefined : Number(v));

/**
 * One execution per KPI: a metric of a product the user is not entitled to fails the whole execution (403),
 * so each is asked on its own and the ones the user cannot see are dropped. At most `max` are kept, in order.
 */
async function kpiValues(persona: PersonaId, ws: string, list: Kpi[], max: number): Promise<Kpi[]> {
  const res = await Promise.all(
    list.map((k) =>
      execute(persona, ws, { attributes: [], measures: [measure("c", k.metric, -1), measure("p", k.metric, -2)] }, [{ localIdentifier: "d0", itemIdentifiers: ["measureGroup"] }])
        .then((r) => ({ ...k, cur: num(r.data[0]), prev: num(r.data[1]) }))
        .catch(() => null),
    ),
  );
  return res.filter((k): k is NonNullable<typeof k> => !!k && (k.cur !== undefined || k.prev !== undefined)).slice(0, max);
}

async function dimDrivers(persona: PersonaId, ws: string, lead: Kpi, product: Product, dim: (typeof DIMS)[number]): Promise<Omit<Driver, "share">[]> {
  const res = await execute(
    persona,
    ws,
    { attributes: [{ localIdentifier: "a", label: { identifier: { id: dim.label, type: "label" } } }], measures: [measure("c", lead.metric, -1), measure("p", lead.metric, -2)] },
    [
      { localIdentifier: "d0", itemIdentifiers: ["a"] },
      { localIdentifier: "d1", itemIdentifiers: ["measureGroup"] },
    ],
  );
  const headers = res.dimensionHeaders?.[0]?.headerGroups?.[0]?.headers || [];
  return headers
    .map((h: any, i: number) => {
      const cur = num(res.data[i][0]) || 0;
      const prev = num(res.data[i][1]) || 0;
      return { dim: dim.id, noun: dim.noun, member: h.attributeHeader.labelValue ?? "(empty)", cur, prev, delta: cur - prev, format: lead.format, target: dim.target(product) };
    })
    .filter((d: any) => d.member && d.member !== "_");
}

function quarterLabel(offset: number) {
  const now = new Date();
  let q = Math.floor(now.getMonth() / 3) + offset;
  let y = now.getFullYear();
  while (q < 0) {
    q += 4;
    y -= 1;
  }
  return `Q${q + 1} ${y}`;
}

const cache = new Map<string, Promise<Insights>>();

/** Home page numbers for a persona, built from their data products (see products.ts). */
export function loadInsights(persona: PersonaId, ws: string, productNames: string[]): Promise<Insights> {
  const key = `${persona}|${ws}`;
  if (!cache.has(key)) {
    const p = (async () => {
      const products = productsOf(productNames);
      const [kpis, watch] = await Promise.all([
        kpiValues(persona, ws, roundRobin(products, (x) => x.kpis), 4),
        kpiValues(persona, ws, roundRobin(products, (x) => x.watch), 4),
      ]);
      const leadKpi = kpis[0];
      const lead = leadKpi ? PRODUCTS[leadKpi.product] : products[0];
      const perDim = leadKpi && lead ? await Promise.all(DIMS.map((d) => dimDrivers(persona, ws, leadKpi, lead, d).catch(() => []))) : [];
      const total = leadKpi ? (leadKpi.cur || 0) - (leadKpi.prev || 0) : 0;
      const additive = leadKpi && leadKpi.format !== "pct" && leadKpi.format !== "num";
      // a dimension with one member explains nothing; keep the biggest movers, at most 2 per dimension
      const candidates = perDim
        .filter((list) => list.length > 1)
        .flatMap((list) => [...list].sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 2))
        .filter((d) => Math.abs(d.delta) > 0)
        .sort((a, b) => Math.abs(b.delta) / (Math.abs(b.prev) || 1) - Math.abs(a.delta) / (Math.abs(a.prev) || 1));
      const drivers: Driver[] = [];
      for (const d of candidates) {
        if (drivers.length >= 4) break;
        if (drivers.filter((x) => x.dim === d.dim).length >= 2) continue;
        drivers.push({ ...d, share: additive && total ? d.delta / Math.abs(total) : 0 });
      }
      return { period: { cur: quarterLabel(-1), prev: quarterLabel(-2) }, lead, kpis, watch, drivers };
    })();
    p.catch(() => cache.delete(key));
    cache.set(key, p);
  }
  return cache.get(key)!;
}

// ------------------------------------------------------------------ formatting

export function fmt(v: number | undefined, f: Kpi["format"]) {
  if (v === undefined || Number.isNaN(v)) return "—";
  if (f === "pct") return `${(Math.abs(v) <= 1.5 ? v * 100 : v).toFixed(1)}%`;
  const a = Math.abs(v);
  if (f === "count" && a < 1e4) return `${v < 0 ? "−" : ""}${Math.round(a).toLocaleString()}`;
  if (f === "num" && a < 1e4) return `${v < 0 ? "−" : ""}${a.toFixed(1)}`;
  const s = a >= 1e9 ? `${(a / 1e9).toFixed(1)}B` : a >= 1e6 ? `${(a / 1e6).toFixed(1)}M` : a >= 1e3 ? `${(a / 1e3).toFixed(a >= 1e5 ? 0 : 1)}K` : a.toFixed(0);
  return `${v < 0 ? "−" : ""}${f === "money" ? "$" : ""}${s}`;
}

export function change(k: { cur?: number; prev?: number; format: Kpi["format"] }) {
  if (k.cur === undefined || k.prev === undefined) return null;
  if (k.format === "pct") {
    const pp = ((Math.abs(k.cur) <= 1.5 ? 100 : 1) * (k.cur - k.prev));
    return { up: pp >= 0, text: `${pp >= 0 ? "+" : "−"}${Math.abs(pp).toFixed(1)} pp` };
  }
  if (!k.prev) return null;
  const pct = ((k.cur - k.prev) / Math.abs(k.prev)) * 100;
  return { up: pct >= 0, text: `${pct >= 0 ? "+" : "−"}${Math.abs(pct).toFixed(1)}%` };
}

/** A change in the metric's own unit: percentage points for rates. */
export function fmtDelta(v: number, f: Kpi["format"]) {
  if (f === "pct") return `${(Math.abs(v) <= 1.5 ? v * 100 : v).toFixed(1)} pp`;
  return fmt(v, f);
}
