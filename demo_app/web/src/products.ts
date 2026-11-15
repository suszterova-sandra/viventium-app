/**
 * Viventium data products as the app uses them: one dashboard, one Publisher report, the headline KPIs and
 * the visualizations a number opens. Mirrors gooddata/data_products.json and analytics/visualisations.
 * Users only see the products they are entitled to (object-level permissions per dp_* user group).
 */
export type Format = "money" | "count" | "pct" | "num";

export interface ProductKpi {
  metric: string;
  label: string;
  format: Format;
  goodWhenUp: boolean;
  viz: string;
}

export interface Product {
  name: string;
  dashboard: string;
  dashTitle: string;
  report: string;
  /** headline KPIs (the dashboard's <prefix>_k_* headlines), most important first */
  kpis: ProductKpi[];
  /** secondary numbers for the watch list */
  watch: ProductKpi[];
  /** visualizations a key driver opens */
  byLocation: { viz: string; title: string };
  byRole: { viz: string; title: string };
}

const k = (metric: string, label: string, format: Format, goodWhenUp: boolean, viz: string): ProductKpi => ({ metric, label, format, goodWhenUp, viz });

const slug = (name: string) => name.toLowerCase().replace(/&/g, " ").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
const P = (name: string, dashboard: string, dashTitle: string, kpis: ProductKpi[], watch: ProductKpi[], byLocation: [string, string], byRole: [string, string]): Product => ({
  name,
  dashboard,
  dashTitle,
  report: `dp_${slug(name)}_report`,
  kpis,
  watch,
  byLocation: { viz: byLocation[0], title: byLocation[1] },
  byRole: { viz: byRole[0], title: byRole[1] },
});

export const PRODUCTS: Record<string, Product> = Object.fromEntries(
  [
    P(
      "Payroll",
      "p05_payroll",
      "Payroll",
      [k("pr_gross", "Gross pay", "money", true, "pr_k_gross"), k("pr_total_cost", "Total employer cost", "money", false, "pr_k_cost")],
      [k("pr_ot_share", "OT pay % of gross", "pct", false, "pr_k_ot"), k("pr_avg_check", "Avg gross per paycheck", "money", true, "pr_k_avg")],
      ["pr_by_location", "Cost of Labor by Location"],
      ["pr_ot_role", "Overtime Pay by Job Role"],
    ),
    P(
      "HR",
      "p11_hr",
      "HR & Workforce",
      [k("hr_hires", "Hires", "count", true, "hr_k_hires"), k("hr_terms", "Terminations", "count", false, "hr_k_terms")],
      [k("hr_turnover", "Annualized turnover", "pct", false, "hr_k_turn"), k("hr_early_turnover", "Early turnover (90 days)", "pct", false, "hr_k_early")],
      ["hr_by_location", "Workforce by Location"],
      ["hr_turn_role", "Turnover by Job Role"],
    ),
    P(
      "Scheduling",
      "p03_scheduling",
      "Scheduling",
      [k("sch_calloff_rate", "Call-off rate", "pct", false, "sch_k_calloff"), k("sch_agency_cost", "Agency cost", "money", false, "sch_k_agency")],
      [k("sch_coverage_rate", "Coverage rate", "pct", true, "sch_k_cover"), k("sch_uncovered", "Uncovered / missed visits", "count", false, "sch_k_uncovered")],
      ["sch_by_location", "Scheduling by Location"],
      ["sch_calloff_role", "Call-Off Rate by Job Role"],
    ),
    P(
      "Applicant Tracking",
      "p01_applicant_tracking",
      "Applicant Tracking",
      [k("ats_applications", "Applications", "count", true, "ats_k_apps"), k("ats_hires", "Hires", "count", true, "ats_k_hires")],
      [k("ats_days_to_hire", "Avg days to hire", "num", false, "ats_k_dth"), k("ats_hours_first_contact", "Hours to first contact", "num", false, "ats_k_contact")],
      ["ats_by_source", "Applications & Hires by Source"],
      ["ats_ttf_by_role", "Time to Fill by Job Role"],
    ),
    P(
      "Time & Attendance",
      "p04_time_attendance",
      "Time & Attendance",
      [k("ta_ot_pct", "Overtime %", "pct", false, "ta_k_ot"), k("ta_worked_hours", "Worked hours", "count", true, "ta_k_hours")],
      [k("ta_late_rate", "Late punch rate", "pct", false, "ta_k_late"), k("ta_missed_punch_rate", "Missed punch rate", "pct", false, "ta_k_missed")],
      ["ta_by_location", "Attendance by Location"],
      ["ta_ot_role", "Overtime % by Job Role"],
    ),
    P(
      "Benefits",
      "p07_benefits",
      "Benefits Administration",
      [k("ben_med_participation", "Medical participation", "pct", true, "ben_k_med"), k("ben_er_cost", "Employer monthly cost", "money", false, "ben_k_er")],
      [k("ben_401k_participation", "401(k) participation", "pct", true, "ben_k_401k"), k("ben_er_share", "Employer cost share", "pct", false, "ben_k_share")],
      ["ben_by_location", "Benefits by Location"],
      ["ben_by_plan", "Enrollment by Plan"],
    ),
    P(
      "ACA Compliance",
      "p08_aca",
      "ACA Compliance",
      [k("aca_offer_rate", "ACA offer rate", "pct", true, "aca_k_offer"), k("aca_exposure", "Penalty exposure", "money", false, "aca_k_exp")],
      [k("aca_affordability", "Affordability rate", "pct", true, "aca_k_aff"), k("aca_risk_months", "At-risk employee-months", "count", false, "aca_k_risk")],
      ["aca_by_location", "ACA by Location"],
      ["aca_risk_table", "Employees at Penalty Risk"],
    ),
    P(
      "On-Demand Pay",
      "p06_on_demand_pay",
      "On-Demand Pay",
      [k("odp_amount", "Amount advanced", "money", true, "odp_k_amount"), k("odp_users", "Active ODP users", "count", true, "odp_k_users")],
      [k("odp_avg_draw", "Avg draw", "money", false, "odp_k_avg"), k("odp_instant_share", "Instant transfer %", "pct", true, "odp_k_instant")],
      ["odp_by_location", "On-Demand Pay by Location"],
      ["odp_by_role", "Amount Advanced by Job Role"],
    ),
    P(
      "Onboarding",
      "p02_onboarding",
      "Onboarding",
      [k("ob_new_hires", "New hires onboarded", "count", true, "ob_k_hires"), k("ob_on_time_rate", "On-time completion", "pct", true, "ob_k_ontime")],
      [k("ob_avg_days", "Avg days to complete", "num", false, "ob_k_days"), k("ob_completion_rate", "Task completion rate", "pct", true, "ob_k_rate")],
      ["ob_by_location", "Onboarding by Location"],
      ["ob_by_task", "Avg Days by Task"],
    ),
    P(
      "LMS",
      "p09_lms",
      "Learning (LMS)",
      [k("lms_completion_rate", "Training completion", "pct", true, "lms_k_rate"), k("lms_ceu", "CEUs earned", "num", true, "lms_k_ceu")],
      [k("lms_on_time_rate", "On-time completion", "pct", true, "lms_k_ontime"), k("lms_hours", "Training hours", "count", true, "lms_k_hours")],
      ["lms_by_location", "Training by Location"],
      ["lms_by_category", "Completion Rate by Course Category"],
    ),
    P(
      "Exclusion Monitoring",
      "p10_exclusion_monitoring",
      "Exclusion Monitoring",
      [k("exc_checks", "Exclusion checks", "count", true, "exc_k_checks"), k("exc_potential", "Potential matches", "count", false, "exc_k_pot")],
      [k("exc_confirmed", "Confirmed matches", "count", false, "exc_k_conf"), k("exc_days_to_resolve", "Avg days to resolve", "num", false, "exc_k_days")],
      ["exc_by_location", "Screening by Location"],
      ["exc_matches", "Potential Matches by List & Outcome"],
    ),
  ].map((p) => [p.name, p]),
);

/** The persona's products that the app knows, in the persona's order. */
export const productsOf = (names: string[] | undefined) => (names || []).map((n) => PRODUCTS[n]).filter(Boolean) as Product[];

/** The Publisher report of the persona's first data product. */
export const reportOf = (names: string[] | undefined, fallback = "dp_payroll_report") => productsOf(names)[0]?.report || fallback;
