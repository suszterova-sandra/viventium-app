#!/usr/bin/env python3
"""
Build one GoodData publisher document (business report, v2) per Viventium data product, and optionally deploy.

    python3 publisher/build_reports.py            # write publisher/<dp_id>_report.json
    python3 publisher/build_reports.py --deploy   # also create/update the documents in the parent workspace
    python3 publisher/build_reports.py dp_payroll --deploy

- Every report uses only visualizations of its own data product (same rule as the dashboards), so the
  object-level permissions of gooddata/apply_permissions.py apply to reports too.
- Colours and images come from the active workspace theme ({theme.colors.*}, {theme.assets.images.*},
  theme/build_themes.py), so the same report renders in Viventium purple in the parent and in each client's
  brand in the child workspaces. The cover visual is the product image {theme.assets.images.<dp_id>}.
- Layout rules follow conference_env/publisher/build_ecommerce_report.py (no small text spacers, transparent
  image spacers for padding, paragraph text styles with bold markdown as headings).
- The "What to look for" panels are reading guides, not data claims; AI takeaways supply the numbers.
"""
import itertools
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "gooddata"))
import build_analytics as ba  # noqa: E402

HOST = os.environ.get("GD_HOST", "https://sandrasuszterova.demo.cloud.gooddata.com")
PARENT_WS = "a60f79ad0a99473fafe4d043228d5bd7"

BG, CARD, PANEL = ("{theme.colors.backgrounds.page}", "{theme.colors.backgrounds.card}",
                   "{theme.colors.backgrounds.panel}")
ACCENT, TXT, TXT2, MUTED = ("{theme.colors.texts.accent}", "{theme.colors.texts.default}",
                            "{theme.colors.texts.muted}", "{theme.colors.texts.subtle}")
DEFAULT_DATE = ba.DATE
DATE_OF = {"ats_ttf_by_role": "req_opened_date", "ats_ttf_trend": "req_filled_date"}
_spacer = itertools.count(1)
_page = "page"

ba.build_visuals()
VIS = ba.VIS
TITLES = {k: v["title"] for k, v in VIS.items()}

# ---------------------------------------------------------------- report content per data product
# kpis: 4 headline visualizations; main: chart next to the KPIs;
# pages: (title, lead, left vis, right vis, reading guide)
PRODUCTS = {
    "Applicant Tracking": dict(
        kicker="RECRUITING", summary="Applications, hiring funnel, sources, job board ROI and time to fill.",
        kpis=["ats_k_apps", "ats_k_hires", "ats_k_dth", "ats_k_spend"], main="ats_trend",
        main_guide="Hires rising slower than applications means a leaky funnel, not a sourcing problem.\n\n"
                   "**Ask:** which roles take longest from apply to start?",
        pages=[("Hiring Funnel & Sources", "Where candidates come from and where they drop out.",
                "ats_funnel", "ats_by_source",
                "The biggest step down is usually screening - often candidates who never answer.\n\n"
                "Referrals bring fewer applicants but more hires.\n\n**Ask:** is speed to first contact the fix?"),
               ("Job Boards & Time to Fill", "Sponsored spend efficiency and how long positions stay open.",
                "ats_boards", "ats_ttf_by_role",
                "Compare cost per apply across boards before raising budgets.\n\n"
                "Licensed roles (RN, BCBA, therapists) fill slowest.\n\n**Ask:** where would a sign-on bonus pay off?")]),
    "Onboarding": dict(
        kicker="ONBOARDING", summary="How fast new hires complete paperwork, screenings and credentials.",
        kpis=["ob_k_hires", "ob_k_rate", "ob_k_ontime", "ob_k_days"], main="ob_days_trend",
        main_guide="Fewer days from offer to completion means new hires can start on day one.\n\n"
                   "**Ask:** which steps still need HR to chase people?",
        pages=[("Where Onboarding Slows Down", "On-time rate by category and the slowest tasks.",
                "ob_by_category", "ob_by_task",
                "Background checks and fingerprinting depend on vendors, not the new hire.\n\n"
                "Credential uploads are the most common late item for clinical roles.\n\n"
                "**Ask:** can these start at offer instead of at hire?"),
               ("Channels & Locations", "Mobile self-service adoption and onboarding by location.",
                "ob_via", "ob_by_location",
                "Mobile completion keeps rising - tasks done on the phone finish faster.\n\n"
                "**Ask:** which locations lag on on-time completion?")]),
    "Scheduling": dict(
        kicker="SCHEDULING", summary="Call-offs, coverage, agency dependency and open shifts.",
        kpis=["sch_k_hours", "sch_k_calloff", "sch_k_cover", "sch_k_agency"], main="sch_agency_trend",
        main_guide="Agency shifts are the most expensive way to cover a call-off; internal pickups the cheapest.\n\n"
                   "Falling agency cost with stable coverage means staff pick up more shifts in the app.\n\n"
                   "**Ask:** which roles still depend on agencies?",
        pages=[("How Call-Offs Get Covered", "Coverage outcome over time and call-offs by weekday.",
                "sch_coverage", "sch_calloff_dow",
                "Internal pickups should grow while agency and uncovered shrink.\n\n"
                "Weekends and winter months carry the most call-offs.\n\n**Ask:** do weekend incentives help?"),
               ("Roles & Locations", "Which roles call off most and how each location staffs.",
                "sch_calloff_role", "sch_by_location",
                "Direct care roles call off most - and are hardest to replace.\n\n"
                "Missed visits in home-based care are a client-experience risk.\n\n**Ask:** where is coverage weakest?")]),
    "Time & Attendance": dict(
        kicker="TIME & ATTENDANCE", summary="Hours, overtime, punctuality and mobile / geofenced punches.",
        kpis=["ta_k_hours", "ta_k_ot", "ta_k_late", "ta_k_missed"], main="ta_trend",
        main_guide="Overtime above a few percent of hours usually points to open positions.\n\n"
                   "**Ask:** is overtime planned (extra shifts) or caused by call-offs?",
        pages=[("Overtime & Punctuality", "Where overtime sits and when people clock in late.",
                "ta_ot_role", "ta_late_dow",
                "Home care aides carry the most overtime - and wage parity makes it costlier.\n\n"
                "**Ask:** does lateness cluster on specific days?"),
               ("Clock Methods & Locations", "The move to mobile GPS punches and attendance by location.",
                "ta_method", "ta_by_location",
                "Mobile punches with geofencing support EVV compliance and cut missed punches.\n\n"
                "**Ask:** which locations still rely on kiosks or IVR?")]),
    "Payroll": dict(
        kicker="PAYROLL", summary="Cost of labor: earnings mix, overtime, differentials, wage parity and taxes.",
        kpis=["pr_k_gross", "pr_k_cost", "pr_k_ot", "pr_k_avg"], main="pr_composition",
        main_guide="Regular pay should dominate; growing OT, retro or bonus slices need a reason.\n\n"
                   "Blended-rate OT is the FLSA true-up for employees with differentials.\n\n"
                   "**Ask:** what drives the change versus last period?",
        pages=[("Gross to Net & Overtime", "Where gross pay goes and which roles earn overtime.",
                "pr_gross_to_net", "pr_ot_role",
                "On-Demand Pay repayments come out of net pay - watch for heavy users.\n\n"
                "**Ask:** is overtime concentrated in a few roles?"),
               ("Payment Methods & Locations", "How people are paid and the cost of labor per location.",
                "pr_method", "pr_by_location",
                "Pay cards help unbanked staff; paper checks cost the most to run.\n\n"
                "**Ask:** which location has the highest employer cost per employee?")]),
    "On-Demand Pay": dict(
        kicker="ON-DEMAND PAY", summary="Earned wage access: adoption, draws, amounts and instant transfers.",
        kpis=["odp_k_amount", "odp_k_draws", "odp_k_users", "odp_k_avg"], main="odp_trend",
        main_guide="Usage growing after launch shows staff value faster access to earned pay.\n\n"
                   "**Ask:** does On-Demand Pay help retention in high-turnover roles?",
        pages=[("Who Uses It and When", "Draw amounts by role and requests by weekday.",
                "odp_by_role", "odp_dow",
                "Hourly direct care staff are the heaviest users.\n\n"
                "Requests peak before the weekend.\n\n**Ask:** is it promoted in recruiting?"),
               ("Transfers & Locations", "Instant vs next-day transfers and usage per location.",
                "odp_type", "odp_by_location",
                "Instant transfers carry a fee - a high share means urgent needs.\n\n"
                "**Ask:** which locations have low adoption?")]),
    "Benefits": dict(
        kicker="BENEFITS", summary="Participation, plan mix, employer cost and open enrollment.",
        kpis=["ben_k_elig", "ben_k_med", "ben_k_401k", "ben_k_er"], main="ben_by_plan",
        main_guide="Plan mix drives cost: PPO costs most, HDHP least.\n\n"
                   "**Ask:** is participation high enough to keep the plan affordable?",
        pages=[("Cost & Coverage", "Employer vs employee cost by plan type and medical coverage tiers.",
                "ben_cost_type", "ben_tier",
                "The employer pays most of medical; vision is fully employee-paid.\n\n"
                "Family coverage is the most expensive tier.\n\n**Ask:** is the contribution strategy competitive?"),
               ("Locations", "Participation and cost per location.", "ben_by_location", "ben_cost_type",
                "Low participation can mean low pay relative to premiums.\n\n"
                "**Ask:** which locations need open enrollment support?")]),
    "ACA Compliance": dict(
        kicker="ACA COMPLIANCE", summary="Full-time counts, the 95% offer test, affordability and penalty exposure.",
        kpis=["aca_k_ft", "aca_k_offer", "aca_k_risk", "aca_k_exp"], main="aca_offer_trend",
        main_guide="The offer rate must stay at or above 95% of full-time employees every month.\n\n"
                   "**Ask:** which months fell short and why?",
        pages=[("Workforce Status & 1095-C", "ACA status per month and Line 14 offer codes.",
                "aca_status_trend", "aca_line14",
                "Variable-hour staff who reach 130 hours on average become full-time for ACA.\n\n"
                "Line 14 1H for a full-time employee is a red flag.\n\n**Ask:** are look-back results acted on?"),
               ("Exposure by Location", "Where penalty risk sits.", "aca_by_location", "aca_line16",
                "Exposure usually comes from missed offers, not unaffordable plans.\n\n"
                "**Ask:** which locations need an offer audit before filing?")]),
    "LMS": dict(
        kicker="LEARNING", summary="Training compliance: completion, on-time rate, CEUs and mobile learning.",
        kpis=["lms_k_rate", "lms_k_ontime", "lms_k_ceu", "lms_k_score"], main="lms_trend",
        main_guide="Orientation follows hiring; annual compliance follows hire anniversaries.\n\n"
                   "**Ask:** are surveyors going to find overdue mandatory training?",
        pages=[("Compliance by Category", "Completion by course category and the learning device.",
                "lms_by_category", "lms_device",
                "Compliance courses should be near 100%; development courses are optional.\n\n"
                "**Ask:** does mobile learning lift completion for field staff?"),
               ("Locations", "Training KPIs per location.", "lms_by_location", "lms_by_category",
                "Low on-time rates usually mean courses are assigned too close to the deadline.\n\n"
                "**Ask:** which locations need reminders?")]),
    "Exclusion Monitoring": dict(
        kicker="EXCLUSION MONITORING", summary="OIG, SAM and State Medicaid screening, matches and resolution.",
        kpis=["exc_k_checks", "exc_k_emps", "exc_k_pot", "exc_k_conf"], main="exc_trend",
        main_guide="Every employee is screened before hire and every month after.\n\n"
                   "**Ask:** is screening coverage complete for all lists?",
        pages=[("Matches & Resolution", "Potential matches by outcome and confirmed exclusions.",
                "exc_matches", "exc_confirmed_table",
                "Most potential matches are false positives - resolve them fast.\n\n"
                "A confirmed match means billing risk for services that person provided.\n\n"
                "**Ask:** how quickly was each confirmed match removed?"),
               ("Screening by Location", "Coverage and outcomes per location.", "exc_by_location", "exc_type",
                "Pre-hire checks stop excluded people before they start.\n\n**Ask:** any location with gaps?")]),
    "HR": dict(
        kicker="HR & WORKFORCE", summary="Headcount, hires, turnover, termination reasons and HR case support.",
        kpis=["hr_k_hires", "hr_k_terms", "hr_k_turn", "hr_k_early"], main="hr_hc_trend",
        main_guide="Post-acute care turnover is high; first-90-day exits are the most preventable.\n\n"
                   "**Ask:** is headcount growing where demand grows?",
        pages=[("Turnover", "Hires vs terminations and turnover by role.", "hr_flow", "hr_turn_role",
                "Direct care roles turn over fastest and drive recruiting cost.\n\n"
                "**Ask:** which roles lose people in the first 90 days?"),
               ("Why People Leave & HR Support", "Termination reasons and HR cases by category.",
                "hr_reasons", "hr_case_cat",
                "Pay and schedule flexibility top the voluntary reasons.\n\n"
                "Viventium HR experts handle most policy, leave and wage-hour questions.\n\n"
                "**Ask:** which reasons can scheduling or On-Demand Pay address?")]),
}


# ---------------------------------------------------------------- primitives

def text(tid, markdown, text_style="normalText", proportion=None, **style):
    node = {"type": "text", "id": tid, "markdown": markdown, "style": {"text_style": text_style, **style}}
    if proportion is not None:
        node["proportion"] = proportion
    return node


def heading(tid, label, text_style="largeText", proportion=None, as_title=False, **style):
    node = text(tid, f"**{label}**", text_style, proportion, **style)
    if as_title:
        node["type"] = "title"
    return node


def image(iid, source, proportion=None, fit="contain", h="left", v="center"):
    node = {"type": "image", "id": iid, "decorative": True, "source": source,
            "style": {"fit": fit, "horizontal_align": h, "vertical_align": v}}
    if proportion is not None:
        node["proportion"] = proportion
    return node


def rule(proportion):
    return image(f"{_page}_rule{next(_spacer)}", "{theme.assets.images.accent_bar}", proportion)


def spacer(proportion):
    return image(f"{_page}_gap{next(_spacer)}", "{theme.assets.images.spacer}", proportion, h="center")


def card(children, background=CARD, proportion=None, pad=None):
    if pad:
        side, top, bottom = pad
        body = {"type": "column", "proportion": 1, "children": children}
        inner = {"type": "row", "proportion": 10, "children": [spacer(side), body, spacer(side)]} if side else \
            {"type": "column", "proportion": 10, "children": children}
        children = ([spacer(top)] if top else []) + [inner] + ([spacer(bottom)] if bottom else [])
    node = {"type": "column", "style": {"background_color": background}, "children": children}
    if proportion is not None:
        node["proportion"] = proportion
    return node


def plain_row(children, proportion):
    return {"type": "row", "proportion": proportion, "children": children}


def viz(vid, visualization):
    return {"type": "visualization", "id": vid, "visualization": visualization,
            "date": DATE_OF.get(visualization, DEFAULT_DATE)}


def kpi_tile(visualization):
    return card([
        heading(f"{_page}_{visualization}_lbl", TITLES[visualization].upper(), "smallText", 0.55,
                text_color=TXT2, horizontal_align="center", vertical_align="bottom"),
        {"type": "column", "proportion": 3.6, "children": [viz(f"{_page}_{visualization}", visualization)]},
    ], pad=(0, 0.35, 0.35))


def chart_card(vid, visualization, proportion=None):
    return card([
        heading(f"{vid}_lbl", TITLES[visualization], "normalText", 1, text_color=TXT,
                horizontal_align="center", vertical_align="center"),
        {"type": "column", "proportion": 8, "children": [viz(vid, visualization)]},
    ], proportion=proportion)


def insight(body, proportion=1.3, label="What to look for"):
    return card([
        heading(f"{_page}_ih", label, "normalText", 1, text_color=ACCENT, vertical_align="center"),
        text(f"{_page}_ib", body, "smallText", 5.5, text_color=TXT2),
    ], background=PANEL, proportion=proportion, pad=(0.07, 0.3, 0.3))


def footer(label):
    return {"type": "row", "proportion": 0.6, "children": [
        image(f"{_page}_logo", "{theme.assets.images.logo}", 2, v="bottom"),
        {"type": "text", "id": f"{_page}_section", "proportion": 5, "decorative": True, "markdown": label,
         "style": {"text_style": "smallText", "horizontal_align": "center", "vertical_align": "bottom"}},
        {"type": "text", "id": f"{_page}_pageno", "proportion": 2, "decorative": True,
         "markdown": "{currentPageNumber} / {totalPages}",
         "style": {"text_style": "smallText", "horizontal_align": "right", "vertical_align": "bottom"}}]}


def content_page(page_id, label, kicker, title, lead, body_rows):
    global _page
    _page = page_id
    children = [
        {"type": "column", "proportion": 2.0, "children": [
            text(f"{page_id}_kicker", kicker, "smallText", 0.8, text_color=ACCENT, vertical_align="bottom"),
            heading(f"{page_id}_title", title, "largeText", 1.3, as_title=True, text_color=TXT,
                    vertical_align="center"),
            text(f"{page_id}_lead", lead, "normalText", 1, vertical_align="top")]},
        rule(0.05),
        *body_rows(),
        footer(label),
    ]
    return {"id": page_id, "kind": "content", "style": {"background_color": BG},
            "layout": {"type": "column", "children": children}}


def cover(dp_id, title, summary, kicker):
    global _page
    _page = pid = "page_cover"
    return {"id": pid, "kind": "cover", "style": {"background_color": BG},
            "layout": {"type": "row", "children": [
                card([
                    spacer(1.6),
                    text("cover_kicker", f"{kicker}  ·  {{documentDateRange}}", "smallText", 0.6,
                         text_color=ACCENT, vertical_align="bottom"),
                    heading("cover_title", title, "largeText", 1.4, as_title=True, text_color=TXT,
                            vertical_align="center"),
                    rule(0.08),
                    text("cover_meta", summary, "normalText", 1.3, text_color=TXT2, vertical_align="top"),
                    image("cover_logo", "{theme.assets.images.logo}", 0.6, v="bottom")],
                    background=BG, proportion=1, pad=(0.08, 0.3, 0.3)),
                {"type": "column", "proportion": 1.25, "style": {"background_color": CARD}, "children": [
                    image("cover_hero", f"{{theme.assets.images.{dp_id}}}", fit="contain", h="center")]}]}}


def build(product, cfg, dp_id):
    title = f"{product} Report"
    label = f"Viventium  ·  {product}"
    k = cfg["kicker"]
    pages = [cover(dp_id, title, cfg["summary"], k),
             content_page("page_glance", label, k, "At a Glance", "Headline results for the period.", lambda: [
                 plain_row([kpi_tile(v) for v in cfg["kpis"]], 4.0),
                 plain_row([chart_card("v_main", cfg["main"], proportion=2.7), insight(cfg["main_guide"])], 5.0)])]
    for i, (ptitle, lead, left, right, guide) in enumerate(cfg["pages"], 1):
        pages.append(content_page(f"page_{i}", label, k, ptitle, lead, lambda l=left, r=right, g=guide: [
            plain_row([chart_card(f"v_{i}_l", l), chart_card(f"v_{i}_r", r), insight(g, proportion=0.75)], 8)]))
    # data product isolation: every visualization must belong to this product
    used = set(re.findall(r'"visualization": "([a-z0-9_]+)"', json.dumps(pages)))
    foreign = [v for v in used if VIS[v]["tags"] != [product]]
    if foreign:
        raise SystemExit(f"{product} report uses visualizations of other products: {foreign}")
    return {
        "type": "document", "id": f"{dp_id}_report", "version": "2", "title": title, "description": cfg["summary"],
        "tags": [product],
        "period": {"granularity": "MONTH", "from": -5, "to": -1},
        "content": {
            "defaults": {"page_size": "widescreen", "takeaway": {"generation": {"instructions": (
                f"Act as a professional workforce analyst for a post-acute care provider (skilled nursing, senior "
                f"living, home care, home health & hospice, ABA). This report covers {product}. Write short "
                f"messages, max 255 characters. Explain what stands behind the numbers (locations, roles, "
                f"staffing, compliance) more than restating the numbers themselves.")}}},
            "sections": [{"id": "section_main", "pages": pages}],
        },
    }


# ---------------------------------------------------------------- deploy (authoring format -> API format)

def camel(k):
    parts = k.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def to_api(node):
    if isinstance(node, list):
        return [to_api(x) for x in node]
    if not isinstance(node, dict):
        return node
    if node.get("type") == "visualization":
        return {"type": "visualization", "id": node["id"],
                "visualization": {"identifier": node["visualization"], "type": "insight"},
                "dateDataSet": {"identifier": node["date"], "type": "dataSet"}}
    return {camel(k): to_api(v) for k, v in node.items()}


def api(method, path, body=None):
    req = urllib.request.Request(HOST + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {os.environ['GOODDATA_API_TOKEN']}",
                                          "Content-Type": "application/vnd.gooddata.api+json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


def deploy(doc):
    p = doc["period"]
    attrs = {"title": doc["title"], "description": doc["description"], "tags": doc["tags"], "version": "2",
             "period": {"granularity": f"GDC.time.{p['granularity'].lower()}", "from": p["from"], "to": p["to"],
                        "type": "relative"},
             "content": to_api(doc["content"])}
    body = {"data": {"id": doc["id"], "type": "document", "attributes": attrs}}
    code, resp = api("PUT", f"/api/v1/entities/workspaces/{PARENT_WS}/documents/{doc['id']}", body)
    if code == 404:
        code, resp = api("POST", f"/api/v1/entities/workspaces/{PARENT_WS}/documents", body)
    return code, resp


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    for product, cfg in PRODUCTS.items():
        dp_id = ba.slug(product)
        if only and dp_id not in only:
            continue
        doc = build(product, cfg, dp_id)
        (HERE / f"{dp_id}_report.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        msg = f"{dp_id}_report.json"
        if "--deploy" in sys.argv:
            code, resp = deploy(doc)
            msg += f"  -> {code}" + ("" if code in (200, 201) else f" {resp}")
        print(msg)


if __name__ == "__main__":
    main()
