#!/usr/bin/env python3
"""
Build the Viventium GoodData workspace as code (gd CLI / analytics-as-code YAML).

    python3 build_analytics.py      -> ../analytics/{datasets,metrics,visualisations,dashboards}/*.yaml

Logical model rules
  * every fact table references `employees` only (single join path); location / job role / client are
    reached via employees -> locations -> clients and employees -> job_roles
  * ATS facts (applications, job_postings) reference `requisitions` -> locations, job_roles
  * one shared date dimension `activity_date` ("Date") is the main date of every fact table, so one
    dashboard date filter works everywhere; dimensions use their own role-playing dates
  * every tenant table carries the workspace data filter `client_id` on column wdf__client_id
One dashboard per Viventium product.
"""
import json
import os
import shutil

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "analytics")
WDF = [{"filter_id": "client_id", "source_column": "wdf__client_id", "data_type": "STRING"}]
DATE = "activity_date"

# ---------------------------------------------------------------------------
# Logical data model
# ---------------------------------------------------------------------------
DATES = {
    DATE: ("Date", "Main date of every product: shift / work / check / request / application / assignment / "
                   "screening / case / snapshot date depending on the dataset."),
    "hire_date": ("Hire Date", "Employee hire date."),
    "termination_date": ("Termination Date", "Employee termination date (1900-01-01 = still employed)."),
    "req_opened_date": ("Requisition Opened Date", "Date the job requisition was opened."),
    "req_filled_date": ("Requisition Filled Date", "Date the requisition was filled (1900-01-01 = not filled)."),
}
GRAN = ["DAY", "DAY_OF_WEEK", "DAY_OF_MONTH", "DAY_OF_YEAR", "WEEK", "WEEK_OF_YEAR", "MONTH", "MONTH_OF_YEAR",
        "QUARTER", "QUARTER_OF_YEAR", "YEAR"]

S, I, N, D = "STRING", "INT", "NUMERIC", "DATE"


def _load_schema():
    src = open(os.path.join(HERE, "..", "demo_data", "generate.py")).read()
    head = src.split("# ---------------------------------------------------------------------------\n# Tenants")[0]
    ns = {"__file__": os.path.join(HERE, "..", "demo_data", "generate.py"), "__name__": "schema"}
    exec(compile(head, "generate.py", "exec"), ns)
    return ns["SCHEMA"]


PHYS = {t: dict(cols) for t, cols in _load_schema().items()}


def gd_type(table, col):
    t = PHYS[table][col].upper()
    if t.startswith("VARCHAR"):
        return S
    if t.startswith("INT"):
        return I
    if t.startswith("NUMERIC"):
        return N
    if t.startswith("DATE"):
        return D
    raise ValueError((table, col, t))

# table: title, description, pk column, pk title, pk labels [(col, title, value_type)],
#        attributes [(col, title, type)], facts [(col, title)], refs [(dataset, fk col, target attr)],
#        dates [(date dataset, col)], wdf
MODEL = {
    "clients": dict(
        title="Clients", desc="Viventium clients (tenants). Each child workspace sees only its own client.",
        pk=("client_id", "Client"), labels=[("client_name", "Client Name", "TEXT")],
        attrs=[("industry", "Industry", S), ("industry_segment", "Industry Segment", S),
               ("headquarters_city", "HQ City", S), ("headquarters_state", "HQ State", S), ("plan_tier", "Plan Tier", S)]),
    "locations": dict(
        title="Locations", desc="Facilities, branches and clinics of each client with map coordinates.",
        pk=("location_id", "Location"),
        labels=[("location_name", "Location Name", "TEXT"), ("latitude", "Latitude", "GEO_LATITUDE"),
                ("longitude", "Longitude", "GEO_LONGITUDE")],
        attrs=[("location_type", "Location Type", S), ("city", "City", S), ("state", "State Code", S),
               ("state_name", "State", S), ("postal_code", "Postal Code", S), ("region", "Region", S),
               ("capacity_unit", "Capacity Unit", S)],
        facts=[("licensed_capacity", "Licensed Capacity")],
        refs=[("clients", "client_id", "clients.client_id")]),
    "job_roles": dict(
        title="Job Roles", desc="Job roles across post-acute care (global reference, shared by all clients).",
        pk=("job_role_id", "Job Role"), labels=[("job_title", "Job Title", "TEXT")],
        attrs=[("job_family", "Job Family", S), ("department", "Department", S), ("is_clinical", "Clinical Role", S),
               ("license_required", "License Required", S), ("flsa_status", "FLSA Status", S),
               ("pay_type", "Role Pay Type", S), ("work_setting", "Work Setting", S)], wdf=False),
    "employees": dict(
        title="Employees", desc="Employees of each location, including placeholder rows for open and agency shifts "
                                "(Is Placeholder = Yes).",
        pk=("employee_id", "Employee"), labels=[("full_name", "Employee Name", "TEXT")],
        attrs=[("employee_number", "Employee Number", S), ("gender", "Gender", S), ("age_band", "Age Band", S),
               ("employment_type", "Employment Type", S), ("pay_type", "Pay Type", S),
               ("employment_status", "Employment Status", S), ("termination_type", "Termination Type", S),
               ("termination_reason", "Termination Reason", S), ("rehire_eligible", "Rehire Eligible", S),
               ("recruitment_source", "Recruitment Source", S), ("preferred_shift", "Preferred Shift", S),
               ("uses_mobile_app", "Uses Mobile App", S), ("odp_enrolled", "On-Demand Pay Enrolled", S),
               ("is_placeholder", "Is Placeholder", S)],
        facts=[("hourly_rate", "Hourly Rate"), ("annual_salary", "Annual Salary"), ("fte", "FTE")],
        refs=[("locations", "location_id", "locations.location_id"), ("job_roles", "job_role_id", "job_roles.job_role_id")],
        dates=[("hire_date", "hire_date"), ("termination_date", "termination_date")]),
    "pay_periods": dict(
        title="Pay Periods", desc="Bi-weekly pay periods (global).", pk=("pay_period_id", "Pay Period"),
        labels=[("pay_period_label", "Pay Period Label", "TEXT")],
        attrs=[("pay_year", "Pay Year", I), ("period_number", "Period Number", I)], wdf=False),
    "benefit_plans": dict(
        title="Benefit Plans", desc="Benefit plans offered by each client, incl. Waived / Election Pending rows.",
        pk=("benefit_plan_id", "Benefit Plan"), labels=[("plan_name", "Plan Name", "TEXT")],
        attrs=[("plan_type", "Plan Type", S), ("carrier", "Carrier", S), ("network_type", "Network Type", S)]),
    "courses": dict(
        title="Courses", desc="LMS course catalog (global).", pk=("course_id", "Course"),
        labels=[("course_title", "Course Title", "TEXT")],
        attrs=[("course_category", "Course Category", S), ("delivery_format", "Delivery Format", S),
               ("is_state_mandated", "State Mandated", S)],
        facts=[("duration_minutes", "Course Duration (min)"), ("ceu_credits", "Course CEU Credits")], wdf=False),
    "requisitions": dict(
        title="Requisitions", desc="Job requisitions (Applicant Tracking).", pk=("requisition_id", "Requisition"),
        attrs=[("requisition_reason", "Requisition Reason", S), ("priority", "Requisition Priority", S),
               ("requisition_status", "Requisition Status", S)],
        facts=[("openings", "Openings"), ("days_open", "Days Open"), ("days_to_fill", "Days to Fill"),
               ("sign_on_bonus", "Sign-On Bonus")],
        refs=[("locations", "location_id", "locations.location_id"), ("job_roles", "job_role_id", "job_roles.job_role_id")],
        dates=[("req_opened_date", "opened_date"), ("req_filled_date", "filled_date")]),
    "job_postings": dict(
        title="Job Postings", desc="Requisition postings on job boards incl. sponsored spend (Job Sponsorships).",
        pk=("posting_id", "Posting"), attrs=[("job_board", "Job Board", S), ("is_sponsored", "Sponsored", S)],
        facts=[("sponsorship_spend", "Sponsorship Spend"), ("impressions", "Impressions"), ("clicks", "Clicks"),
               ("applies", "Board Applies")],
        refs=[("requisitions", "requisition_id", "requisitions.requisition_id")], dates=[(DATE, "posted_date")]),
    "applications": dict(
        title="Applications", desc="Candidate applications and their hiring funnel stage.",
        pk=("application_id", "Application"), labels=[("candidate_name", "Candidate Name", "TEXT")],
        attrs=[("application_source", "Application Source", S), ("apply_device", "Apply Device", S),
               ("highest_stage", "Highest Stage", S), ("application_status", "Application Status", S)],
        facts=[("hours_to_first_contact", "Hours to First Contact"), ("days_to_hire", "Days to Hire"),
               ("is_screened", "Is Screened"), ("is_interviewed", "Is Interviewed"), ("is_offered", "Is Offered"),
               ("is_hired", "Is Hired")],
        refs=[("requisitions", "requisition_id", "requisitions.requisition_id")], dates=[(DATE, "applied_date")]),
    "onboarding_tasks": dict(
        title="Onboarding Tasks", desc="New-hire onboarding tasks.", pk=("onboarding_task_id", "Onboarding Task"),
        attrs=[("task_name", "Task", S), ("task_category", "Task Category", S),
               ("responsible_party", "Responsible Party", S), ("task_status", "Task Status", S),
               ("completed_via", "Completed Via", S)],
        facts=[("days_to_complete", "Days to Complete"), ("is_completed", "Task Completed"),
               ("is_overdue", "Task Overdue"), ("completed_on_time", "Task Completed On Time")],
        refs=[("employees", "employee_id", "employees.employee_id")], dates=[(DATE, "assigned_date")]),
    "shifts": dict(
        title="Shifts", desc="Scheduled shifts, visits and session blocks incl. call-offs, coverage, agency and open shifts.",
        pk=("shift_id", "Shift"),
        attrs=[("shift_type", "Shift Type", S), ("shift_status", "Shift Status", S), ("fill_method", "Fill Method", S),
               ("coverage_outcome", "Coverage Outcome", S), ("is_weekend", "Weekend Shift", S)],
        facts=[("scheduled_hours", "Scheduled Hours"), ("visit_count", "Visits"), ("publish_lead_days", "Publish Lead Days"),
               ("agency_cost", "Agency Cost")],
        refs=[("employees", "employee_id", "employees.employee_id")], dates=[(DATE, "shift_date")]),
    "timecards": dict(
        title="Timecards", desc="Clock-in / clock-out records of worked shifts.", pk=("timecard_id", "Timecard"),
        attrs=[("clock_method", "Clock Method", S), ("within_geofence", "Within Geofence", S),
               ("manager_edited", "Manager Edited", S), ("approval_status", "Approval Status", S)],
        facts=[("scheduled_hours", "Timecard Scheduled Hours"), ("worked_hours", "Worked Hours"),
               ("regular_hours", "Regular Hours"), ("overtime_hours", "Overtime Hours"),
               ("break_minutes", "Break Minutes"), ("late_minutes", "Late Minutes"), ("is_late", "Is Late"),
               ("is_early_out", "Is Early Out"), ("is_missed_punch", "Is Missed Punch")],
        refs=[("employees", "employee_id", "employees.employee_id")], dates=[(DATE, "work_date")]),
    "payroll": dict(
        title="Payroll", desc="Pay statements per employee and pay period.", pk=("payroll_id", "Pay Statement"),
        attrs=[("payment_method", "Payment Method", S)],
        facts=[("regular_hours", "Paid Regular Hours"), ("overtime_hours", "Paid Overtime Hours"),
               ("pto_hours", "PTO Hours"), ("regular_pay", "Regular Pay"), ("overtime_pay", "Overtime Pay"),
               ("blended_rate_ot_adjustment", "Blended-Rate OT Adjustment"),
               ("shift_differential_pay", "Shift Differential Pay"), ("wage_parity_supplement", "Wage Parity Supplement"),
               ("retro_pay", "Retro Pay"), ("bonus_pay", "Bonus Pay"), ("pto_pay", "PTO Pay"), ("gross_pay", "Gross Pay"),
               ("pretax_deductions", "Pre-Tax Deductions"), ("employee_taxes", "Employee Taxes"),
               ("odp_repayment", "On-Demand Pay Repayment"), ("net_pay", "Net Pay"), ("employer_taxes", "Employer Taxes"),
               ("employer_benefit_cost", "Employer Benefit Cost"), ("total_employer_cost", "Total Employer Cost")],
        refs=[("employees", "employee_id", "employees.employee_id"),
              ("pay_periods", "pay_period_id", "pay_periods.pay_period_id")], dates=[(DATE, "check_date")]),
    "odp_transactions": dict(
        title="On-Demand Pay Transactions", desc="Earned wage access draws.", pk=("odp_transaction_id", "ODP Transaction"),
        attrs=[("transfer_type", "Transfer Type", S), ("transaction_status", "Transaction Status", S),
               ("decline_reason", "Decline Reason", S)],
        facts=[("amount", "ODP Amount"), ("fee", "ODP Fee")],
        refs=[("employees", "employee_id", "employees.employee_id"),
              ("pay_periods", "pay_period_id", "pay_periods.pay_period_id")], dates=[(DATE, "request_date")]),
    "benefit_enrollments": dict(
        title="Benefit Enrollments", desc="Benefit elections per employee, plan type and plan year.",
        pk=("enrollment_id", "Enrollment"),
        attrs=[("plan_year", "Plan Year", I), ("coverage_tier", "Coverage Tier", S),
               ("enrollment_event", "Enrollment Event", S), ("election_status", "Election Status", S),
               ("enrolled_via", "Enrolled Via", S)],
        facts=[("covered_lives", "Covered Lives"), ("contribution_pct", "401(k) Contribution %"),
               ("employee_monthly_cost", "Employee Monthly Cost"), ("employer_monthly_cost", "Employer Monthly Cost"),
               ("is_enrolled", "Is Enrolled")],
        refs=[("employees", "employee_id", "employees.employee_id"),
              ("benefit_plans", "benefit_plan_id", "benefit_plans.benefit_plan_id")], dates=[(DATE, "effective_date")]),
    "aca_monthly": dict(
        title="ACA Monthly", desc="ACA employer-mandate measurement per employee and month (Form 1095-C).",
        pk=("aca_record_id", "ACA Record"),
        attrs=[("aca_status", "ACA Status", S), ("measurement_method", "Measurement Method", S),
               ("offer_code_line14", "1095-C Line 14", S), ("safe_harbor_code_line16", "1095-C Line 16", S),
               ("form_1095c_status", "1095-C Filing Status", S)],
        facts=[("hours_of_service", "Hours of Service"), ("lowest_cost_ee_premium", "Lowest-Cost EE Premium"),
               ("affordability_threshold", "Affordability Threshold"), ("is_affordable", "Is Affordable"),
               ("is_aca_full_time", "Is ACA Full-Time"), ("is_offered_coverage", "Is Offered Coverage"),
               ("is_enrolled_medical", "Is Enrolled Medical"), ("penalty_risk", "Penalty Risk"),
               ("penalty_exposure_amount", "Penalty Exposure")],
        refs=[("employees", "employee_id", "employees.employee_id")], dates=[(DATE, "reporting_month")]),
    "course_assignments": dict(
        title="Course Assignments", desc="LMS course assignments and completions.", pk=("assignment_id", "Assignment"),
        attrs=[("assignment_reason", "Assignment Reason", S), ("assignment_status", "Assignment Status", S),
               ("completion_device", "Completion Device", S)],
        facts=[("score_pct", "Score %"), ("time_spent_minutes", "Time Spent (min)"), ("attempts", "Attempts"),
               ("ceu_credits_earned", "CEU Credits Earned"), ("is_completed", "Course Completed"),
               ("is_overdue", "Course Overdue"), ("completed_on_time", "Course Completed On Time")],
        refs=[("employees", "employee_id", "employees.employee_id"), ("courses", "course_id", "courses.course_id")],
        dates=[(DATE, "assigned_date")]),
    "exclusion_checks": dict(
        title="Exclusion Checks", desc="OIG / SAM / State Medicaid exclusion screening results.",
        pk=("check_id", "Exclusion Check"),
        attrs=[("exclusion_list", "Exclusion List", S), ("check_type", "Check Type", S),
               ("check_result", "Check Result", S), ("resolution", "Resolution", S)],
        facts=[("days_to_resolve", "Days to Resolve"), ("is_potential_match", "Is Potential Match"),
               ("is_confirmed_match", "Is Confirmed Match")],
        refs=[("employees", "employee_id", "employees.employee_id")], dates=[(DATE, "check_date")]),
    "hr_cases": dict(
        title="HR Cases", desc="HR questions and cases handled by Viventium HR experts or the client HR team.",
        pk=("case_id", "HR Case"),
        attrs=[("case_category", "Case Category", S), ("priority", "Case Priority", S), ("channel", "Case Channel", S),
               ("handled_by", "Handled By", S), ("case_status", "Case Status", S), ("escalated", "Escalated", S)],
        facts=[("first_response_hours", "First Response Hours"), ("resolution_days", "Resolution Days"),
               ("satisfaction_score", "Satisfaction Score"), ("is_rated", "Is Rated"), ("is_closed", "Is Closed")],
        refs=[("employees", "employee_id", "employees.employee_id")], dates=[(DATE, "opened_date")]),
    "workforce_monthly": dict(
        title="Workforce Monthly", desc="Monthly employee snapshot for headcount and turnover.",
        pk=("snapshot_id", "Snapshot"), attrs=[],
        facts=[("is_active_eom", "Active End of Month"), ("is_new_hire", "New Hire"), ("is_termination", "Termination"),
               ("is_voluntary_termination", "Voluntary Termination"), ("is_early_turnover", "Early Turnover (90 days)"),
               ("tenure_months", "Tenure (months)"), ("fte_eom", "FTE End of Month")],
        refs=[("employees", "employee_id", "employees.employee_id")], dates=[(DATE, "snapshot_month")]),
}


# Data products: each Viventium product owns its fact datasets, metrics, visualisations and dashboard.
# Everything else is a shared (conformed) dimension that every product may use.
DATASET_PRODUCT = {
    "requisitions": "Applicant Tracking", "job_postings": "Applicant Tracking", "applications": "Applicant Tracking",
    "onboarding_tasks": "Onboarding", "shifts": "Scheduling", "timecards": "Time & Attendance", "payroll": "Payroll",
    "odp_transactions": "On-Demand Pay", "benefit_enrollments": "Benefits", "benefit_plans": "Benefits",
    "aca_monthly": "ACA Compliance", "course_assignments": "LMS", "courses": "LMS",
    "exclusion_checks": "Exclusion Monitoring", "hr_cases": "HR", "workforce_monthly": "HR",
}
SHARED = "Shared Dimensions"


def product_of_dataset(ds):
    return DATASET_PRODUCT.get(ds, SHARED)


def slug(product):
    return "dp_" + "_".join(__import__("re").findall(r"[a-z0-9]+", product.lower()))


def build_datasets():
    out = {}
    for t, m in MODEL.items():
        tags = [product_of_dataset(t)]
        pk_col, pk_title = m["pk"]
        pk_id = f"{t}.{pk_col}"
        fields = {}
        pk = {"type": "attribute", "source_column": pk_col, "data_type": S, "title": pk_title,
              "description": f"{pk_title} ID", "tags": tags}
        if m.get("labels"):
            pk["labels"] = {}
            for col, title, vt in m["labels"]:
                pk["labels"][f"{pk_id}.{col}"] = {
                    "source_column": col, "data_type": gd_type(t, col), "title": title,
                    "description": title, "tags": tags, "value_type": vt}
        fields[pk_id] = pk
        for col, title, typ in m.get("attrs", []):
            fields[f"{t}.{col}"] = {"type": "attribute", "source_column": col, "data_type": gd_type(t, col), "title": title,
                                    "description": title, "tags": tags}
        for col, title in m.get("facts", []):
            fields[f"{t}.{col}"] = {"type": "fact", "source_column": col, "data_type": gd_type(t, col), "title": title,
                                    "description": title, "tags": tags}
        refs = [{"dataset": ds, "sources": [{"source_column": fk, "data_type": S, "target": tgt}]}
                for ds, fk, tgt in m.get("refs", [])]
        refs += [{"dataset": ds, "sources": [{"source_column": col, "data_type": D, "target": ds}]}
                 for ds, col in m.get("dates", [])]
        doc = {"type": "dataset", "id": t, "table_path": f"main/{t}", "title": m["title"],
               "description": m["desc"], "tags": tags, "primary_key": pk_id, "fields": fields}
        if refs:
            doc["references"] = refs
        if m.get("wdf", True):
            doc["workspace_data_filters"] = WDF
        out[t] = doc
    for d, (title, desc) in DATES.items():
        out[d] = {"type": "date", "id": d, "title": title, "description": desc, "tags": [SHARED],
                  "granularities": GRAN, "title_base": "", "title_pattern": "%titleBase - %granularityTitle"}
    return out


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
PCT, NUM, NUM1, USD, USD2, HRS = "#,##0.0%", "#,##0", "#,##0.0", "$#,##0", "$#,##0.00", "#,##0.0"
METRICS = []  # (id, title, maql, format, description, tag)


ZERO_IF_EMPTY = {"ats_open_reqs", "sch_agency_shifts", "sch_agency_cost", "sch_uncovered",
                 "sch_open_posted", "ta_pending", "pr_parity", "pr_retro", "pr_bonus", "odp_fees", "aca_risk_months",
                 "aca_exposure", "aca_newly_ft", "lms_overdue", "exc_potential", "exc_confirmed",
                 "hr_open_cases"}


def metric(mid, title, maql, fmt, desc, tag):
    # parenthesised sub-aggregations need their own SELECT in MAQL
    maql = __import__("re").sub(r"(^|[\s/*+-])\((COUNT|SUM|AVG)\(", r"\1(SELECT \2(", maql)
    if mid in ZERO_IF_EMPTY:  # show 0 instead of an empty KPI (e.g. no agency use in home care)
        maql = f"SELECT IFNULL(({maql}), 0)"
    METRICS.append((mid, title, maql, fmt, desc, tag))


def cnt(ds, pk):
    return f"COUNT({{attribute/{ds}.{pk}}})"


def L(x):
    return "{label/" + x + "}"


def F(x):
    return "{fact/" + x + "}"


def M(x):
    return "{metric/" + x + "}"


def build_metrics():
    t = "Applicant Tracking"
    metric("ats_applications", "Applications", f"SELECT {cnt('applications', 'application_id')}", NUM,
           "Number of applications received.", t)
    for k, f, d in [("screened", "is_screened", "Applications that passed screening."),
                    ("interviewed", "is_interviewed", "Applications that reached the interview stage."),
                    ("offered", "is_offered", "Applications that received an offer."),
                    ("hires", "is_hired", "Applications that resulted in a hire.")]:
        metric(f"ats_{k}", k.capitalize() if k != "hires" else "Hires", f"SELECT SUM({F('applications.' + f)})", NUM, d, t)
    metric("ats_apps_per_hire", "Applications per Hire", f"SELECT {M('ats_applications')} / {M('ats_hires')}", NUM1,
           "Applications needed for one hire.", t)
    metric("ats_screen_rate", "Screen Rate", f"SELECT {M('ats_screened')} / {M('ats_applications')}", PCT,
           "Share of applications that passed screening.", t)
    metric("ats_offer_accept_rate", "Offer Acceptance Rate", f"SELECT {M('ats_hires')} / {M('ats_offered')}", PCT,
           "Share of offers accepted.", t)
    metric("ats_hours_first_contact", "Avg Hours to First Contact",
           f"SELECT AVG({F('applications.hours_to_first_contact')})", NUM1,
           "Average hours from application to first recruiter contact.", t)
    metric("ats_days_to_hire", "Avg Days to Hire",
           f"SELECT AVG({F('applications.days_to_hire')}) WHERE {L('applications.application_status')} = \"Hired\"",
           NUM1, "Average days from application to start date for hired candidates.", t)
    metric("ats_reqs_opened", "Requisitions Opened", f"SELECT {cnt('requisitions', 'requisition_id')}", NUM,
           "Number of requisitions opened.", t)
    metric("ats_open_reqs", "Open Requisitions",
           f"SELECT {cnt('requisitions', 'requisition_id')} WHERE {L('requisitions.requisition_status')} = \"Open\"",
           NUM, "Requisitions currently open.", t)
    metric("ats_time_to_fill", "Avg Time to Fill (days)",
           f"SELECT AVG({F('requisitions.days_to_fill')}) WHERE {L('requisitions.requisition_status')} = \"Filled\"",
           NUM1, "Average days from requisition opened to filled.", t)
    metric("ats_days_open", "Avg Days Open",
           f"SELECT AVG({F('requisitions.days_open')}) WHERE {L('requisitions.requisition_status')} = \"Open\"",
           NUM1, "Average age of open requisitions.", t)
    metric("ats_spend", "Sponsored Job Spend", f"SELECT SUM({F('job_postings.sponsorship_spend')})", USD,
           "Spend on sponsored job postings.", t)
    metric("ats_board_applies", "Job Board Applies", f"SELECT SUM({F('job_postings.applies')})", NUM,
           "Applications that came from job boards.", t)
    metric("ats_clicks", "Job Board Clicks", f"SELECT SUM({F('job_postings.clicks')})", NUM, "Clicks on job postings.", t)
    metric("ats_cost_per_apply", "Cost per Apply", f"SELECT {M('ats_spend')} / {M('ats_board_applies')}", USD2,
           "Sponsored spend per job board application.", t)
    metric("ats_apply_rate", "Click-to-Apply Rate", f"SELECT {M('ats_board_applies')} / {M('ats_clicks')}", PCT,
           "Share of posting clicks that became applications.", t)

    t = "Onboarding"
    metric("ob_tasks", "Onboarding Tasks", f"SELECT {cnt('onboarding_tasks', 'onboarding_task_id')}", NUM,
           "Onboarding tasks assigned.", t)
    metric("ob_completed", "Tasks Completed", f"SELECT SUM({F('onboarding_tasks.is_completed')})", NUM,
           "Onboarding tasks completed.", t)
    metric("ob_completion_rate", "Task Completion Rate", f"SELECT {M('ob_completed')} / {M('ob_tasks')}", PCT,
           "Share of onboarding tasks completed.", t)
    metric("ob_on_time_rate", "On-Time Completion Rate",
           f"SELECT SUM({F('onboarding_tasks.completed_on_time')}) / {M('ob_completed')}", PCT,
           "Share of completed tasks finished by the due date.", t)
    metric("ob_avg_days", "Avg Days to Complete",
           f"SELECT AVG({F('onboarding_tasks.days_to_complete')}) WHERE {L('onboarding_tasks.task_status')} = \"Completed\"",
           NUM1, "Average days from task assignment (offer) to completion.", t)
    metric("ob_overdue", "Overdue Tasks",
           f"SELECT {cnt('onboarding_tasks', 'onboarding_task_id')} - (SELECT {cnt('onboarding_tasks', 'onboarding_task_id')} "
           f"WHERE {L('onboarding_tasks.task_status')} <> \"Overdue\")",
           NUM, "Tasks past due and still not completed.", t)
    metric("ob_new_hires", "New Hires Onboarded",
           "SELECT COUNT({attribute/employees.employee_id}, {dataset/onboarding_tasks})", NUM,
           "New hires with onboarding tasks.", t)
    metric("ob_mobile_share", "Completed on Mobile %",
           f"SELECT ({cnt('onboarding_tasks', 'onboarding_task_id')} WHERE {L('onboarding_tasks.completed_via')} = \"Mobile App\")"
           f" / ({cnt('onboarding_tasks', 'onboarding_task_id')} WHERE {L('onboarding_tasks.completed_via')} IN (\"Mobile App\", \"Desktop\"))",
           PCT, "Share of self-service tasks the new hire completed in the mobile app.", t)

    t = "Scheduling"
    sh = cnt("shifts", "shift_id")
    metric("sch_shifts", "Shifts", f"SELECT {sh}", NUM, "Scheduled shifts, visits and session blocks.", t)
    metric("sch_scheduled_hours", "Scheduled Hours", f"SELECT SUM({F('shifts.scheduled_hours')})", NUM,
           "Scheduled hours.", t)
    metric("sch_worked_hours", "Worked Shift Hours",
           f"SELECT SUM({F('shifts.scheduled_hours')}) WHERE {L('shifts.shift_status')} = \"Worked\"", NUM,
           "Scheduled hours of shifts that were worked.", t)
    metric("sch_original_shifts", "Assigned Shifts",
           f"SELECT {sh} WHERE {L('shifts.fill_method')} IN (\"Assigned\", \"Shift Swap\")", NUM,
           "Shifts on the original schedule.", t)
    metric("sch_calloffs", "Call-Offs & No-Shows",
           f"SELECT {sh} WHERE {L('shifts.shift_status')} IN (\"Called Off\", \"No Show\")", NUM,
           "Shifts called off or not shown.", t)
    metric("sch_calloff_rate", "Call-Off Rate", f"SELECT {M('sch_calloffs')} / {M('sch_original_shifts')}", PCT,
           "Share of scheduled shifts called off or no-show.", t)
    metric("sch_covered", "Covered Call-Offs",
           f"SELECT {sh} WHERE {L('shifts.coverage_outcome')} IN (\"Covered - Internal\", \"Covered - Agency\")", NUM,
           "Call-offs that were covered.", t)
    metric("sch_coverage_rate", "Coverage Rate",
           f"SELECT {M('sch_covered')} / ({sh} WHERE {L('shifts.coverage_outcome')} IN (\"Covered - Internal\", \"Covered - Agency\", \"Not Covered\"))",
           PCT, "Share of call-offs that were covered by staff or agency.", t)
    metric("sch_internal_pickups", "Internal Pickups",
           f"SELECT {sh} WHERE {L('shifts.fill_method')} IN (\"Picked Up via Mobile App\", \"Manager Assigned\")",
           NUM, "Open shifts covered by own staff.", t)
    metric("sch_app_pickup_share", "Picked Up via App %",
           f"SELECT ({sh} WHERE {L('shifts.fill_method')} = \"Picked Up via Mobile App\") / {M('sch_internal_pickups')}",
           PCT, "Share of internal pickups claimed in the mobile app.", t)
    metric("sch_agency_shifts", "Agency Shifts", f"SELECT {sh} WHERE {L('shifts.fill_method')} = \"Agency\"", NUM,
           "Shifts covered by staffing agencies.", t)
    metric("sch_agency_cost", "Agency Cost", f"SELECT SUM({F('shifts.agency_cost')})", USD, "Cost of agency shifts.", t)
    metric("sch_uncovered", "Uncovered Shifts / Missed Visits",
           f"SELECT {sh} WHERE {L('shifts.shift_status')} IN (\"Unfilled\", \"Missed Visit\")", NUM,
           "Call-offs nobody covered (missed visits in home-based care).", t)
    metric("sch_open_posted", "Open Shifts Posted", f"SELECT {sh} WHERE {L('shifts.shift_status')} = \"Open - Posted\"",
           NUM, "Open shifts posted to the mobile app for the next 14 days.", t)
    metric("sch_visits", "Visits & Sessions Delivered",
           f"SELECT SUM({F('shifts.visit_count')}) WHERE {L('shifts.shift_status')} = \"Worked\"", NUM,
           "Client visits / therapy sessions delivered.", t)
    metric("sch_publish_lead", "Avg Schedule Lead Time (days)",
           f"SELECT AVG({F('shifts.publish_lead_days')}) WHERE {L('shifts.fill_method')} = \"Assigned\"", NUM1,
           "How many days in advance shifts were published.", t)

    t = "Time & Attendance"
    tc = cnt("timecards", "timecard_id")
    metric("ta_timecards", "Timecards", f"SELECT {tc}", NUM, "Timecards (worked shifts).", t)
    metric("ta_worked_hours", "Worked Hours", f"SELECT SUM({F('timecards.worked_hours')})", NUM, "Hours worked.", t)
    metric("ta_ot_hours", "Overtime Hours", f"SELECT SUM({F('timecards.overtime_hours')})", NUM,
           "Hours above 40 per week.", t)
    metric("ta_ot_pct", "Overtime %", f"SELECT {M('ta_ot_hours')} / {M('ta_worked_hours')}", PCT,
           "Overtime share of worked hours.", t)
    metric("ta_late_rate", "Late Punch Rate", f"SELECT SUM({F('timecards.is_late')}) / {tc}", PCT,
           "Share of shifts clocked in more than 7 minutes late.", t)
    metric("ta_avg_late_min", "Avg Minutes Late",
           f"SELECT SUM({F('timecards.late_minutes')}) / SUM({F('timecards.is_late')})", NUM1,
           "Average minutes late for late punches.", t)
    metric("ta_missed_punch_rate", "Missed Punch Rate", f"SELECT SUM({F('timecards.is_missed_punch')}) / {tc}", PCT,
           "Share of timecards with a missed punch.", t)
    metric("ta_early_out_rate", "Early Out Rate", f"SELECT SUM({F('timecards.is_early_out')}) / {tc}", PCT,
           "Share of shifts clocked out early.", t)
    metric("ta_geofence_rate", "Geofence Compliance",
           f"SELECT ({tc} WHERE {L('timecards.within_geofence')} = \"Yes\") / ({tc} WHERE {L('timecards.within_geofence')} IN (\"Yes\", \"No\"))",
           PCT, "Share of mobile punches inside the geofence (EVV).", t)
    metric("ta_mobile_share", "Mobile Clock-In %",
           f"SELECT ({tc} WHERE {L('timecards.clock_method')} = \"Mobile App (GPS)\") / {tc}", PCT,
           "Share of punches made in the mobile app.", t)
    metric("ta_pending", "Timecards Pending Approval",
           f"SELECT {tc} WHERE {L('timecards.approval_status')} = \"Pending Approval\"", NUM,
           "Timecards waiting for manager approval.", t)
    metric("ta_edit_rate", "Manager Edit Rate",
           f"SELECT ({tc} WHERE {L('timecards.manager_edited')} = \"Yes\") / {tc}", PCT,
           "Share of timecards corrected by a manager.", t)

    t = "Payroll"
    for k, f, title, d in [
        ("gross", "gross_pay", "Gross Pay", "Total gross pay."), ("net", "net_pay", "Net Pay", "Total net pay."),
        ("regular", "regular_pay", "Regular Pay", "Regular pay."), ("ot", "overtime_pay", "Overtime Pay", "Overtime pay (1.5x)."),
        ("blended", "blended_rate_ot_adjustment", "Blended-Rate OT Adjustment",
         "FLSA regular-rate true-up of overtime for employees with differentials."),
        ("diff", "shift_differential_pay", "Shift Differential Pay", "Evening / night / weekend differentials."),
        ("parity", "wage_parity_supplement", "Wage Parity Supplement", "NY home care wage parity supplement."),
        ("retro", "retro_pay", "Retro Pay", "Retroactive pay for late raises."),
        ("bonus", "bonus_pay", "Bonus Pay", "Sign-on, referral and recognition bonuses."),
        ("pto", "pto_pay", "PTO Pay", "Paid time off."),
        ("er_taxes", "employer_taxes", "Employer Taxes", "Employer payroll taxes (FICA, FUTA/SUTA)."),
        ("ee_taxes", "employee_taxes", "Employee Taxes", "Withheld employee taxes."),
        ("pretax", "pretax_deductions", "Pre-Tax Deductions", "Benefit premiums and 401(k) deferrals."),
        ("odp", "odp_repayment", "On-Demand Pay Repaid", "On-Demand Pay advances repaid on the paycheck."),
        ("benefit_cost", "employer_benefit_cost", "Employer Benefit Cost", "Employer share of benefits per pay period."),
        ("total_cost", "total_employer_cost", "Total Employer Cost", "Gross pay + employer taxes + employer benefits."),
        ("ot_hours", "overtime_hours", "Paid OT Hours", "Overtime hours paid.")]:
        metric(f"pr_{k}", title, f"SELECT SUM({F('payroll.' + f)})", NUM if k == "ot_hours" else USD, d, t)
    metric("pr_paychecks", "Pay Statements", f"SELECT {cnt('payroll', 'payroll_id')}", NUM, "Pay statements issued.", t)
    metric("pr_employees_paid", "Employees Paid", "SELECT COUNT({attribute/employees.employee_id}, {dataset/payroll})",
           NUM, "Distinct employees paid.", t)
    metric("pr_avg_check", "Avg Gross per Paycheck", f"SELECT {M('pr_gross')} / {M('pr_paychecks')}", USD,
           "Average gross pay per pay statement.", t)
    metric("pr_ot_share", "OT Pay % of Gross", f"SELECT ({M('pr_ot')} + {M('pr_blended')}) / {M('pr_gross')}", PCT,
           "Overtime incl. blended-rate adjustment as share of gross pay.", t)

    t = "On-Demand Pay"
    ok = f"{L('odp_transactions.transaction_status')} = \"Completed\""
    metric("odp_amount", "Amount Advanced", f"SELECT SUM({F('odp_transactions.amount')}) WHERE {ok}", USD,
           "Earned wages advanced to employees.", t)
    metric("odp_draws", "Draws", f"SELECT {cnt('odp_transactions', 'odp_transaction_id')} WHERE {ok}", NUM,
           "Completed On-Demand Pay draws.", t)
    metric("odp_users", "Active ODP Users",
           f"SELECT COUNT({{attribute/employees.employee_id}}, {{dataset/odp_transactions}}) WHERE {ok}", NUM,
           "Employees who took at least one draw.", t)
    metric("odp_avg_draw", "Avg Draw", f"SELECT {M('odp_amount')} / {M('odp_draws')}", USD2, "Average draw amount.", t)
    metric("odp_draws_per_user", "Draws per User", f"SELECT {M('odp_draws')} / {M('odp_users')}", NUM1,
           "Average draws per active user.", t)
    metric("odp_fees", "ODP Fees", f"SELECT SUM({F('odp_transactions.fee')})", USD2, "Instant transfer fees paid by employees.", t)
    metric("odp_instant_share", "Instant Transfer %",
           f"SELECT ({cnt('odp_transactions', 'odp_transaction_id')} WHERE {ok} AND {L('odp_transactions.transfer_type')} = \"Instant (Debit Card)\") / {M('odp_draws')}",
           PCT, "Share of draws sent instantly to a debit card.", t)
    metric("odp_decline_rate", "Decline Rate",
           f"SELECT ({cnt('odp_transactions', 'odp_transaction_id')} WHERE {L('odp_transactions.transaction_status')} = \"Declined\") / {cnt('odp_transactions', 'odp_transaction_id')}",
           PCT, "Share of draw requests declined.", t)
    act = f"{L('employees.employment_status')} IN (\"Active\", \"On Leave\")"
    metric("odp_adoption", "ODP Adoption (active hourly)",
           f"SELECT ({cnt('employees', 'employee_id')} WHERE {L('employees.odp_enrolled')} = \"Yes\" AND {act}) / "
           f"({cnt('employees', 'employee_id')} WHERE {L('employees.pay_type')} = \"Hourly\" AND {act})",
           PCT, "Share of active hourly employees enrolled in On-Demand Pay.", t)

    t = "Benefits"
    emp_be = "COUNT({attribute/employees.employee_id}, {dataset/benefit_enrollments})"
    med = f"{L('benefit_plans.plan_type')} = \"Medical\""
    metric("ben_enrollments", "Active Enrollments", f"SELECT SUM({F('benefit_enrollments.is_enrolled')})", NUM,
           "Benefit enrollments (all plan types).", t)
    metric("ben_eligible", "Benefit-Eligible Employees", f"SELECT {emp_be}", NUM, "Employees with benefit elections.", t)
    metric("ben_med_participation", "Medical Participation",
           f"SELECT ({emp_be} WHERE {med} AND {L('benefit_enrollments.election_status')} IN (\"Enrolled\", \"Submitted\")) / "
           f"({emp_be} WHERE {med} AND {L('benefit_enrollments.election_status')} IN (\"Enrolled\", \"Submitted\", \"Waived\"))",
           PCT, "Share of eligible employees enrolled in a medical plan.", t)
    metric("ben_401k_participation", "401(k) Participation",
           f"SELECT ({emp_be} WHERE {L('benefit_plans.plan_type')} = \"Retirement\" AND {L('benefit_enrollments.election_status')} IN (\"Enrolled\", \"Submitted\")) / "
           f"({emp_be} WHERE {L('benefit_plans.plan_type')} = \"Retirement\" AND {L('benefit_enrollments.election_status')} IN (\"Enrolled\", \"Submitted\", \"Waived\"))",
           PCT, "Share of eligible employees contributing to the 401(k).", t)
    metric("ben_er_cost", "Employer Monthly Cost", f"SELECT SUM({F('benefit_enrollments.employer_monthly_cost')})", USD,
           "Employer monthly premium / match.", t)
    metric("ben_ee_cost", "Employee Monthly Cost", f"SELECT SUM({F('benefit_enrollments.employee_monthly_cost')})", USD,
           "Employee monthly premium / contribution.", t)
    metric("ben_er_share", "Employer Cost Share", f"SELECT {M('ben_er_cost')} / ({M('ben_er_cost')} + {M('ben_ee_cost')})",
           PCT, "Employer share of total benefit cost.", t)
    metric("ben_covered_lives", "Covered Lives", f"SELECT SUM({F('benefit_enrollments.covered_lives')}) WHERE {med}", NUM,
           "Members covered by medical plans (employees + dependents).", t)
    metric("ben_oe_employees", "Employees in Election", f"SELECT {emp_be}", NUM, "Employees with an election record.", t)

    t = "ACA Compliance"
    metric("aca_ft_months", "Full-Time Employee-Months", f"SELECT SUM({F('aca_monthly.is_aca_full_time')})", NUM,
           "Employee-months measured as ACA full-time (130+ hours or FT status).", t)
    metric("aca_avg_ft", "Avg Monthly FT Employees",
           f"SELECT {M('aca_ft_months')} / COUNT({{attribute/{DATE}.month}}, {{dataset/aca_monthly}})", NUM,
           "Average number of ACA full-time employees per month.", t)
    metric("aca_offer_rate", "Offer Rate (95% Test)",
           f"SELECT SUM({F('aca_monthly.is_offered_coverage')}) / (SELECT SUM({F('aca_monthly.is_aca_full_time')}) "
           f"WHERE {L('aca_monthly.safe_harbor_code_line16')} <> \"2D\")",
           PCT, "Share of full-time employee-months (outside waiting period) offered coverage. Must stay >= 95%.", t)
    metric("aca_risk_months", "At-Risk Employee-Months", f"SELECT SUM({F('aca_monthly.penalty_risk')})", NUM,
           "Employee-months that could trigger a 4980H penalty.", t)
    metric("aca_exposure", "Penalty Exposure", f"SELECT SUM({F('aca_monthly.penalty_exposure_amount')})", USD,
           "Estimated 4980H(a)/(b) penalty exposure.", t)
    metric("aca_affordability", "Affordability Rate",
           f"SELECT SUM({F('aca_monthly.is_affordable')}) / {cnt('aca_monthly', 'aca_record_id')}", PCT,
           "Share of employee-months where the lowest-cost plan is affordable (rate-of-pay safe harbor).", t)
    metric("aca_enroll_rate", "Medical Take-Up Rate",
           f"SELECT SUM({F('aca_monthly.is_enrolled_medical')}) / SUM({F('aca_monthly.is_offered_coverage')})", PCT,
           "Share of offered employee-months enrolled in medical coverage.", t)
    metric("aca_avg_hours", "Avg Monthly Hours of Service", f"SELECT AVG({F('aca_monthly.hours_of_service')})", NUM1,
           "Average monthly hours of service.", t)
    metric("aca_newly_ft", "Variable-Hour Became FT (months)",
           f"SELECT {cnt('aca_monthly', 'aca_record_id')} WHERE {L('aca_monthly.aca_status')} = \"Variable Hour - Became Full-Time\"",
           NUM, "Employee-months of variable-hour staff whose look-back average reached 130 hours.", t)
    metric("aca_records", "Employee-Months", f"SELECT {cnt('aca_monthly', 'aca_record_id')}", NUM,
           "Measured employee-months.", t)

    t = "LMS"
    ca = cnt("course_assignments", "assignment_id")
    metric("lms_assignments", "Course Assignments", f"SELECT {ca}", NUM, "Courses assigned.", t)
    metric("lms_completed", "Courses Completed", f"SELECT SUM({F('course_assignments.is_completed')})", NUM,
           "Courses completed.", t)
    metric("lms_completion_rate", "Completion Rate", f"SELECT {M('lms_completed')} / {M('lms_assignments')}", PCT,
           "Share of assigned courses completed.", t)
    metric("lms_on_time_rate", "On-Time Completion",
           f"SELECT SUM({F('course_assignments.completed_on_time')}) / {M('lms_completed')}", PCT,
           "Share of completions done by the due date.", t)
    metric("lms_overdue", "Overdue Courses",
           f"SELECT {ca} WHERE {L('course_assignments.assignment_status')} = \"Overdue\"", NUM,
           "Assigned courses past due and not completed.", t)
    metric("lms_ceu", "CEUs Earned", f"SELECT SUM({F('course_assignments.ceu_credits_earned')})", NUM1,
           "Continuing education credits earned.", t)
    metric("lms_avg_score", "Avg Score",
           f"SELECT AVG({F('course_assignments.score_pct')}) WHERE {L('course_assignments.assignment_status')} = \"Completed\"",
           NUM1, "Average quiz score of completed courses (%).", t)
    metric("lms_hours", "Training Hours", f"SELECT SUM({F('course_assignments.time_spent_minutes')}) / 60", NUM,
           "Hours spent in training.", t)
    metric("lms_mobile_share", "Completed on Mobile %",
           f"SELECT ({ca} WHERE {L('course_assignments.completion_device')} = \"Mobile App\") / {M('lms_completed')}",
           PCT, "Share of completions done in the mobile app.", t)

    t = "Exclusion Monitoring"
    ec = cnt("exclusion_checks", "check_id")
    metric("exc_checks", "Exclusion Checks", f"SELECT {ec}", NUM, "Screenings run against exclusion lists.", t)
    metric("exc_employees", "Employees Screened",
           "SELECT COUNT({attribute/employees.employee_id}, {dataset/exclusion_checks})", NUM,
           "Distinct employees screened.", t)
    metric("exc_potential", "Potential Matches", f"SELECT SUM({F('exclusion_checks.is_potential_match')})", NUM,
           "Checks flagged as a potential match.", t)
    metric("exc_confirmed", "Confirmed Matches", f"SELECT SUM({F('exclusion_checks.is_confirmed_match')})", NUM,
           "Confirmed excluded individuals.", t)
    metric("exc_match_rate", "Potential Match Rate", f"SELECT {M('exc_potential')} / {M('exc_checks')}", "#,##0.00%",
           "Share of checks flagged.", t)
    metric("exc_days_to_resolve", "Avg Days to Resolve",
           f"SELECT AVG({F('exclusion_checks.days_to_resolve')}) WHERE {L('exclusion_checks.check_result')} IN (\"Potential Match\", \"Confirmed Match\")",
           NUM1, "Average days to resolve a flagged check.", t)
    metric("exc_under_review", "Matches Under Review",   # difference form returns 0 (not empty) when none
           f"SELECT {ec} - (SELECT {ec} WHERE {L('exclusion_checks.resolution')} <> \"Under Review\")", NUM,
           "Flagged checks not yet resolved.", t)

    t = "HR"
    metric("hr_active_headcount", "Active Headcount",
           f"SELECT {cnt('employees', 'employee_id')} WHERE {act} AND {L('employees.is_placeholder')} = \"No\"", NUM,
           "Employees currently active or on leave.", t)
    metric("hr_headcount_eom", "Headcount (end of month)", f"SELECT SUM({F('workforce_monthly.is_active_eom')})", NUM,
           "Employees active at month end (sum over months when not sliced by month).", t)
    metric("hr_fte_eom", "FTE (end of month)", f"SELECT SUM({F('workforce_monthly.fte_eom')})", NUM1,
           "FTEs active at month end.", t)
    metric("hr_hires", "Hires", f"SELECT SUM({F('workforce_monthly.is_new_hire')})", NUM, "New hires.", t)
    metric("hr_terms", "Terminations", f"SELECT SUM({F('workforce_monthly.is_termination')})", NUM, "Terminations.", t)
    metric("hr_vol_terms", "Voluntary Terminations", f"SELECT SUM({F('workforce_monthly.is_voluntary_termination')})",
           NUM, "Voluntary terminations (resignations).", t)
    metric("hr_turnover", "Annualized Turnover", f"SELECT {M('hr_terms')} * 12 / {M('hr_headcount_eom')}", PCT,
           "Terminations / average headcount, annualized.", t)
    metric("hr_vol_turnover", "Annualized Voluntary Turnover",
           f"SELECT {M('hr_vol_terms')} * 12 / {M('hr_headcount_eom')}", PCT,
           "Voluntary terminations / average headcount, annualized.", t)
    metric("hr_early_turnover", "Early Turnover % (first 90 days)",
           f"SELECT SUM({F('workforce_monthly.is_early_turnover')}) / {M('hr_terms')}", PCT,
           "Share of terminations within 90 days of hire.", t)
    metric("hr_net_change", "Net Headcount Change", f"SELECT {M('hr_hires')} - {M('hr_terms')}", NUM,
           "Hires minus terminations.", t)
    hc = cnt("hr_cases", "case_id")
    metric("hr_cases", "HR Cases", f"SELECT {hc}", NUM, "HR cases opened.", t)
    metric("hr_open_cases", "Open HR Cases",
           f"SELECT {hc} WHERE {L('hr_cases.case_status')} IN (\"Open\", \"Escalated\")", NUM, "Cases still open.", t)
    metric("hr_first_response", "Avg First Response (hrs)", f"SELECT AVG({F('hr_cases.first_response_hours')})", NUM1,
           "Average hours to first response.", t)
    metric("hr_resolution", "Avg Resolution (days)",
           f"SELECT AVG({F('hr_cases.resolution_days')}) WHERE {L('hr_cases.case_status')} = \"Closed\"", NUM1,
           "Average days to close a case.", t)
    metric("hr_csat", "CSAT (1-5)",
           f"SELECT SUM({F('hr_cases.satisfaction_score')}) / SUM({F('hr_cases.is_rated')})", "#,##0.00",
           "Average satisfaction score of rated cases.", t)
    metric("hr_expert_share", "Handled by Viventium HR Experts %",
           f"SELECT ({hc} WHERE {L('hr_cases.handled_by')} = \"Viventium HR Expert\") / {hc}", PCT,
           "Share of cases handled by Viventium HR experts.", t)
    metric("hr_cases_per_100", "HR Cases per 100 Employees / yr",
           f"SELECT {M('hr_cases')} * 1200 / {M('hr_headcount_eom')}", NUM1, "Annualized HR case rate.", t)


# ---------------------------------------------------------------------------
# Visualisations & dashboards
# ---------------------------------------------------------------------------
VIS = {}
LOC = "label/locations.location_id.location_name"
ROLE = "label/job_roles.job_role_id.job_title"
FAMILY = "label/job_roles.job_family"
MONTH = f"label/{DATE}.month"
DOW = f"label/{DATE}.dayOfWeek"


def fid(ref):
    return ref.split("/", 1)[1].replace(".", "_")


def headline(vid, title, m, desc, compare=True):
    q = {"fields": {"primary": f"metric/{m}"}}
    v = {"type": "headline_chart", "id": vid, "title": title, "description": desc, "query": q}
    if compare:
        q["fields"]["secondary"] = {"title": "Previous period", "type": "PREVIOUS_PERIOD", "date_filter": DATE,
                                    "using": "primary"}
        q["filter_by"] = {f"{DATE}_year": {"type": "date_filter", "granularity": "YEAR", "from": 0, "to": 0,
                                           "using": DATE}}
        v["metrics"] = ["primary", "secondary"]
        v["config"] = {"comparison_type": "change", "indicator_arrow": True, "indicator_colors": True,
                       "label_default": "vs previous period", "label_conditional": True}
    else:
        v["metrics"] = ["primary"]
    VIS[vid] = v


def chart(vid, typ, title, desc, metrics, view=None, segment=None, sort=True, filters=None, config=None,
          axes=None, totals=False):
    fields = {}
    mkeys = []
    for m in metrics:
        k = m.replace("metric/", "")
        fields[k] = f"metric/{k}"
        mkeys.append(k)
    v = {"type": typ, "id": vid, "title": title, "description": desc, "query": {"fields": fields}}
    vk = [fid(x) for x in (view or [])]
    sk = [fid(x) for x in (segment or [])]
    for ref in (view or []) + (segment or []):
        fields[fid(ref)] = ref
    if filters:
        v["query"]["filter_by"] = filters
    if sort and view and typ in ("bar_chart", "table", "column_chart") and not view[0].startswith(f"label/{DATE}"):
        v["query"]["sort_by"] = [{"type": "metric_sort", "direction": "DESC", "metrics": [mkeys[0]]}]
    if axes:
        v["metrics"] = [{"field": k, "axis": a} for k, a in zip(mkeys, axes)]
    else:
        v["metrics"] = mkeys
    if vk:
        if totals:
            v["view_by"] = [{"field": vk[0], "totals": [{"title": "Total", "type": "SUM", "using": k}
                                                         for k in mkeys if totals is True or k in totals]}] + vk[1:]
        else:
            v["view_by"] = vk
    if sk:
        v["segment_by"] = sk
    if config:
        v["config"] = config
    VIS[vid] = v


def excl(label, *values):
    return {fid(label) + "_f": {"type": "attribute_filter", "using": label, "state": {"exclude": list(values)}}}


def incl(label, *values):
    return {fid(label) + "_f": {"type": "attribute_filter", "using": label, "state": {"include": list(values)}}}


BOTTOM = {"legend_position": "bottom"}
DASHBOARDS = []


PRODUCT_OF_DASHBOARD = {
    "p01_applicant_tracking": "Applicant Tracking", "p02_onboarding": "Onboarding", "p03_scheduling": "Scheduling",
    "p04_time_attendance": "Time & Attendance", "p05_payroll": "Payroll", "p06_on_demand_pay": "On-Demand Pay",
    "p07_benefits": "Benefits", "p08_aca": "ACA Compliance", "p09_lms": "LMS",
    "p10_exclusion_monitoring": "Exclusion Monitoring", "p11_hr": "HR",
}


def dashboard(did, title, desc, rows, extra_filters=None):
    product = PRODUCT_OF_DASHBOARD[did]
    """rows: list of (section title or None, [(vis id, columns, rows_height, use_date)])"""
    sections = []
    for stitle, widgets in rows:
        ws = []
        for vid, cols, h, use_date in widgets:
            w = {"id": f"w_{vid}", "visualization": vid, "title": VIS[vid]["title"], "columns": cols, "rows": h}
            if VIS[vid].get("tags") and VIS[vid]["tags"] != [product]:
                raise SystemExit(f"{vid} is used by two data products")
            VIS[vid]["tags"] = [product]
            if use_date:
                w["date"] = use_date if isinstance(use_date, str) else DATE
            ws.append(w)
        s = {"widgets": ws}
        if stitle:
            s["title"] = stitle
        sections.append(s)
    filters = {
        "date": {"type": "date_filter", "granularity": "MONTH", "from": -11, "to": 0},
        "client": {"type": "attribute_filter", "title": "Client", "using": "label/clients.client_id.client_name"},
        "location": {"type": "attribute_filter", "title": "Location", "using": LOC},
        "job_family": {"type": "attribute_filter", "title": "Job Family", "using": FAMILY},
    }
    filters.update(extra_filters or {})
    DASHBOARDS.append({"type": "dashboard", "id": did, "title": title, "description": desc,
                       "tags": [product], "sections": sections, "filters": filters})


def kpis(*items):
    return [(v, 2, 8, d) for v, d in items]


def build_visuals():
    # 1. Applicant Tracking --------------------------------------------------
    headline("ats_k_apps", "Applications", "ats_applications", "Applications received in the period.")
    headline("ats_k_hires", "Hires", "ats_hires", "Hires in the period.")
    headline("ats_k_dth", "Avg Days to Hire", "ats_days_to_hire", "Average days from application to start date.")
    headline("ats_k_contact", "Hours to First Contact", "ats_hours_first_contact", "Recruiter speed to first contact.")
    headline("ats_k_open", "Open Requisitions", "ats_open_reqs", "Requisitions open right now.", compare=False)
    headline("ats_k_spend", "Sponsored Job Spend", "ats_spend", "Spend on sponsored postings.")
    chart("ats_funnel", "funnel_chart", "Hiring Funnel", "Applications by furthest stage reached.",
          ["ats_applications", "ats_screened", "ats_interviewed", "ats_offered", "ats_hires"])
    chart("ats_trend", "combo_chart", "Applications & Hires by Month", "Monthly applications (columns) and hires (line).",
          ["ats_applications", "ats_hires"], view=[MONTH], axes=["primary", "secondary"], config=BOTTOM)
    chart("ats_by_source", "bar_chart", "Applications & Hires by Source", "Which channels bring applicants and hires.",
          ["ats_applications", "ats_hires"], view=["label/applications.application_source"], config=BOTTOM)
    chart("ats_ttf_by_role", "bar_chart", "Time to Fill by Job Role", "Average days to fill a requisition per role.",
          ["ats_time_to_fill"], view=[ROLE])
    chart("ats_ttf_trend", "line_chart", "Time to Fill Trend", "Average time to fill by month the requisition was filled.",
          ["ats_time_to_fill"], view=["label/req_filled_date.month"])
    chart("ats_boards", "table", "Job Board Performance", "Applies, clicks, spend and cost per apply per job board.",
          ["ats_board_applies", "ats_clicks", "ats_apply_rate", "ats_spend", "ats_cost_per_apply"],
          view=["label/job_postings.job_board"], totals=["ats_board_applies", "ats_clicks", "ats_spend"])
    chart("ats_open_table", "table", "Open Requisitions", "Open requisitions by location and role with average age.",
          ["ats_open_reqs", "ats_days_open"], view=[LOC, ROLE],
          filters=incl("label/requisitions.requisition_status", "Open"))
    chart("ats_status", "donut_chart", "Application Outcomes", "Final status of applications.",
          ["ats_applications"], view=["label/applications.application_status"], config={"legend_position": "right"})
    dashboard("p01_applicant_tracking", "1. Applicant Tracking",
              "Recruiting pipeline: applications, hiring funnel, time to fill, sources and sponsored job board ROI.",
              [(None, kpis(("ats_k_apps", 1), ("ats_k_hires", 1), ("ats_k_dth", 1), ("ats_k_contact", 1),
                           ("ats_k_open", None), ("ats_k_spend", 1))),
               ("Pipeline", [("ats_funnel", 4, 16, 1), ("ats_trend", 8, 16, 1)]),
               ("Sources & Job Boards", [("ats_by_source", 6, 16, 1), ("ats_boards", 6, 16, 1)]),
               ("Requisitions", [("ats_ttf_by_role", 6, 18, "req_opened_date"), ("ats_ttf_trend", 6, 18, "req_filled_date"),
                                 ("ats_open_table", 8, 16, None), ("ats_status", 4, 16, 1)])])

    # 2. Onboarding ---------------------------------------------------------
    headline("ob_k_hires", "New Hires Onboarded", "ob_new_hires", "New hires with onboarding packets.")
    headline("ob_k_rate", "Task Completion Rate", "ob_completion_rate", "Share of tasks completed.")
    headline("ob_k_ontime", "On-Time Completion", "ob_on_time_rate", "Completed by the due date (day before start).")
    headline("ob_k_days", "Avg Days to Complete", "ob_avg_days", "Days from offer to task completion.")
    headline("ob_k_overdue", "Overdue Tasks", "ob_overdue", "Tasks past due.", compare=False)
    headline("ob_k_mobile", "Completed on Mobile", "ob_mobile_share", "Self-service tasks done in the app.")
    chart("ob_days_trend", "line_chart", "Days to Complete by Month", "Average days to complete onboarding tasks.",
          ["ob_avg_days"], view=[MONTH])
    chart("ob_by_category", "bar_chart", "On-Time Rate by Task Category", "Which onboarding steps slow new hires down.",
          ["ob_on_time_rate"], view=["label/onboarding_tasks.task_category"])
    chart("ob_by_task", "bar_chart", "Avg Days by Task", "Average days to complete each task.", ["ob_avg_days"],
          view=["label/onboarding_tasks.task_name"])
    chart("ob_via", "column_chart", "Completion Channel by Month", "Mobile vs desktop vs in-person completions.",
          ["ob_completed"], view=[MONTH], segment=["label/onboarding_tasks.completed_via"],
          filters=excl("label/onboarding_tasks.completed_via", "N/A"),
          config={"legend_position": "bottom", "stack_measures_to_100": True})
    chart("ob_by_location", "table", "Onboarding by Location", "Onboarding KPIs per location.",
          ["ob_new_hires", "ob_completion_rate", "ob_on_time_rate", "ob_avg_days", "ob_overdue"], view=[LOC])
    dashboard("p02_onboarding", "2. Onboarding",
              "New-hire onboarding: completion, speed, overdue paperwork and credentials, mobile self-service.",
              [(None, kpis(("ob_k_hires", 1), ("ob_k_rate", 1), ("ob_k_ontime", 1), ("ob_k_days", 1),
                           ("ob_k_overdue", None), ("ob_k_mobile", 1))),
               ("Speed", [("ob_days_trend", 6, 16, 1), ("ob_by_category", 6, 16, 1)]),
               ("Tasks & Channels", [("ob_by_task", 6, 20, 1), ("ob_via", 6, 20, 1)]),
               ("Locations", [("ob_by_location", 12, 14, 1)])])

    # 3. Scheduling ---------------------------------------------------------
    headline("sch_k_hours", "Scheduled Hours", "sch_scheduled_hours", "Hours on the schedule.")
    headline("sch_k_calloff", "Call-Off Rate", "sch_calloff_rate", "Call-offs and no-shows / assigned shifts.")
    headline("sch_k_cover", "Coverage Rate", "sch_coverage_rate", "Call-offs covered by staff or agency.")
    headline("sch_k_agency", "Agency Cost", "sch_agency_cost", "Spend on agency staff.")
    headline("sch_k_uncovered", "Uncovered / Missed Visits", "sch_uncovered", "Call-offs nobody covered.")
    headline("sch_k_open", "Open Shifts (next 14 days)", "sch_open_posted", "Open shifts posted to the app.",
             compare=False)
    chart("sch_agency_trend", "combo_chart", "Internal Pickups vs Agency by Month",
          "How open shifts get filled: internal pickups and agency shifts (columns), agency cost (line).",
          ["sch_internal_pickups", "sch_agency_shifts", "sch_agency_cost"], view=[MONTH],
          axes=["primary", "primary", "secondary"], config=BOTTOM)
    chart("sch_coverage", "column_chart", "How Call-Offs Were Covered",
          "Call-offs by coverage outcome per month: internal pickup, agency or not covered.",
          ["sch_calloffs"], view=[MONTH], segment=["label/shifts.coverage_outcome"],
          filters=excl("label/shifts.coverage_outcome", "N/A", "Not Required"),
          config={"legend_position": "bottom", "stack_measures_to_100": True})
    chart("sch_calloff_dow", "column_chart", "Call-Off Rate by Weekday", "Which days are hardest to staff.",
          ["sch_calloff_rate"], view=[DOW])
    chart("sch_calloff_role", "bar_chart", "Call-Off Rate by Job Role", "Call-off rate per role.",
          ["sch_calloff_rate"], view=[ROLE])
    chart("sch_by_type", "donut_chart", "Hours by Shift Type", "Scheduled hours by shift type.",
          ["sch_scheduled_hours"], view=["label/shifts.shift_type"], config={"legend_position": "right"})
    chart("sch_by_location", "table", "Scheduling by Location", "Staffing KPIs per location.",
          ["sch_scheduled_hours", "sch_visits", "sch_calloff_rate", "sch_coverage_rate", "sch_app_pickup_share",
           "sch_agency_cost", "sch_uncovered"], view=[LOC])
    dashboard("p03_scheduling", "3. Scheduling",
              "Staffing coverage: call-offs, how they were covered (mobile pickups, agency, uncovered), agency spend "
              "and open shifts.",
              [(None, kpis(("sch_k_hours", 1), ("sch_k_calloff", 1), ("sch_k_cover", 1), ("sch_k_agency", 1),
                           ("sch_k_uncovered", 1), ("sch_k_open", None))),
               ("Agency & Coverage", [("sch_agency_trend", 6, 16, 1), ("sch_coverage", 6, 16, 1)]),
               ("Call-Offs", [("sch_calloff_dow", 4, 16, 1), ("sch_calloff_role", 4, 16, 1), ("sch_by_type", 4, 16, 1)]),
               ("Locations", [("sch_by_location", 12, 14, 1)])])

    # 4. Time & Attendance --------------------------------------------------
    headline("ta_k_hours", "Worked Hours", "ta_worked_hours", "Hours worked.")
    headline("ta_k_ot", "Overtime %", "ta_ot_pct", "Overtime share of worked hours.")
    headline("ta_k_late", "Late Punch Rate", "ta_late_rate", "Clock-ins more than 7 minutes late.")
    headline("ta_k_missed", "Missed Punch Rate", "ta_missed_punch_rate", "Timecards needing a manager fix.")
    headline("ta_k_geo", "Geofence Compliance", "ta_geofence_rate", "Mobile punches inside the geofence (EVV).")
    headline("ta_k_pending", "Pending Approval", "ta_pending", "Timecards waiting for approval.", compare=False)
    chart("ta_trend", "combo_chart", "Worked Hours & Overtime % by Month", "Worked hours (columns) and OT % (line).",
          ["ta_worked_hours", "ta_ot_pct"], view=[MONTH], axes=["primary", "secondary"], config=BOTTOM)
    chart("ta_ot_role", "bar_chart", "Overtime % by Job Role", "Where overtime is concentrated.", ["ta_ot_pct"],
          view=[ROLE])
    chart("ta_method", "column_chart", "Clock Method by Month", "Shift from kiosks and IVR to mobile GPS punches.",
          ["ta_timecards"], view=[MONTH], segment=["label/timecards.clock_method"],
          config={"legend_position": "bottom", "stack_measures_to_100": True})
    chart("ta_late_dow", "column_chart", "Late Punch Rate by Weekday", "Tardiness by day of week.", ["ta_late_rate"],
          view=[DOW])
    chart("ta_by_location", "table", "Attendance by Location", "Time & attendance KPIs per location.",
          ["ta_worked_hours", "ta_ot_hours", "ta_ot_pct", "ta_late_rate", "ta_missed_punch_rate", "ta_early_out_rate",
           "ta_mobile_share"], view=[LOC])
    dashboard("p04_time_attendance", "4. Time & Attendance",
              "Hours, overtime, punctuality, missed punches and mobile / geofenced clock-ins.",
              [(None, kpis(("ta_k_hours", 1), ("ta_k_ot", 1), ("ta_k_late", 1), ("ta_k_missed", 1), ("ta_k_geo", 1),
                           ("ta_k_pending", None))),
               ("Hours & Overtime", [("ta_trend", 7, 16, 1), ("ta_ot_role", 5, 16, 1)]),
               ("Punch Behaviour", [("ta_method", 6, 16, 1), ("ta_late_dow", 6, 16, 1)]),
               ("Locations", [("ta_by_location", 12, 14, 1)])])

    # 5. Payroll ------------------------------------------------------------
    headline("pr_k_gross", "Gross Pay", "pr_gross", "Total gross pay.")
    headline("pr_k_cost", "Total Employer Cost", "pr_total_cost", "Gross + employer taxes + benefits.")
    headline("pr_k_ot", "OT Pay % of Gross", "pr_ot_share", "Overtime incl. blended-rate true-up.")
    headline("pr_k_avg", "Avg Gross per Paycheck", "pr_avg_check", "Average paycheck.")
    headline("pr_k_emps", "Employees Paid", "pr_employees_paid", "Distinct employees paid.")
    headline("pr_k_taxes", "Employer Taxes", "pr_er_taxes", "Employer payroll taxes (FICA, FUTA/SUTA).")
    chart("pr_composition", "column_chart", "Gross Pay Composition by Month", "Earnings types per check month.",
          ["pr_regular", "pr_ot", "pr_blended", "pr_diff", "pr_parity", "pr_pto", "pr_retro", "pr_bonus"],
          view=[MONTH], config={"legend_position": "bottom", "stack_measures": True})
    chart("pr_gross_to_net", "bar_chart", "Gross to Net", "Where gross pay goes.",
          ["pr_net", "pr_ee_taxes", "pr_pretax", "pr_odp"], config=BOTTOM)
    chart("pr_ot_role", "bar_chart", "Overtime Pay by Job Role", "Overtime pay per role.", ["pr_ot"], view=[ROLE])
    chart("pr_method", "donut_chart", "Payment Method", "Direct deposit, pay card or paper check.", ["pr_paychecks"],
          view=["label/payroll.payment_method"], config={"legend_position": "right"})
    chart("pr_by_location", "table", "Cost of Labor by Location", "Payroll cost per location.",
          ["pr_employees_paid", "pr_gross", "pr_ot", "pr_ot_share", "pr_diff", "pr_er_taxes", "pr_benefit_cost",
           "pr_total_cost"], view=[LOC], totals=["pr_gross", "pr_ot", "pr_diff", "pr_er_taxes", "pr_benefit_cost",
                                                  "pr_total_cost"])
    dashboard("p05_payroll", "5. Payroll",
              "Cost of labor: gross-to-net, overtime incl. blended-rate true-up, differentials, wage parity, retro "
              "pay and employer cost.",
              [(None, kpis(("pr_k_gross", 1), ("pr_k_cost", 1), ("pr_k_ot", 1), ("pr_k_avg", 1), ("pr_k_emps", 1),
                           ("pr_k_taxes", 1))),
               ("Earnings", [("pr_composition", 8, 18, 1), ("pr_gross_to_net", 4, 18, 1)]),
               ("Overtime & Payments", [("pr_ot_role", 8, 16, 1), ("pr_method", 4, 16, 1)]),
               ("Locations", [("pr_by_location", 12, 14, 1)])])

    # 6. On-Demand Pay ------------------------------------------------------
    headline("odp_k_amount", "Amount Advanced", "odp_amount", "Earned wages advanced.")
    headline("odp_k_draws", "Draws", "odp_draws", "Completed draws.")
    headline("odp_k_users", "Active Users", "odp_users", "Employees who used On-Demand Pay.")
    headline("odp_k_avg", "Avg Draw", "odp_avg_draw", "Average draw amount.")
    headline("odp_k_adopt", "Adoption (active hourly)", "odp_adoption", "Enrolled share of active hourly staff.",
             compare=False)
    headline("odp_k_instant", "Instant Transfer %", "odp_instant_share", "Draws sent instantly.")
    chart("odp_trend", "combo_chart", "Amount Advanced & Active Users by Month", "Usage growth after launch.",
          ["odp_amount", "odp_users"], view=[MONTH], axes=["primary", "secondary"], config=BOTTOM)
    chart("odp_type", "donut_chart", "Transfer Type", "Instant vs next-day.", ["odp_draws"],
          view=["label/odp_transactions.transfer_type"], config={"legend_position": "right"})
    chart("odp_by_role", "bar_chart", "Amount Advanced by Job Role", "Who relies on earned wage access.",
          ["odp_amount"], view=[ROLE])
    chart("odp_dow", "column_chart", "Draws by Weekday", "When employees request their pay.", ["odp_draws"], view=[DOW])
    chart("odp_by_location", "table", "On-Demand Pay by Location", "Usage per location.",
          ["odp_users", "odp_draws", "odp_amount", "odp_avg_draw", "odp_draws_per_user", "odp_fees", "odp_decline_rate"],
          view=[LOC])
    dashboard("p06_on_demand_pay", "6. On-Demand Pay",
              "Earned wage access: adoption, draws, amounts, instant transfers and declines.",
              [(None, kpis(("odp_k_amount", 1), ("odp_k_draws", 1), ("odp_k_users", 1), ("odp_k_avg", 1),
                           ("odp_k_adopt", None), ("odp_k_instant", 1))),
               ("Usage", [("odp_trend", 8, 16, 1), ("odp_type", 4, 16, 1)]),
               ("Who & When", [("odp_by_role", 6, 16, 1), ("odp_dow", 6, 16, 1)]),
               ("Locations", [("odp_by_location", 12, 14, 1)])])

    # 7. Benefits -----------------------------------------------------------
    headline("ben_k_elig", "Benefit-Eligible Employees", "ben_eligible", "Employees with elections.")
    headline("ben_k_med", "Medical Participation", "ben_med_participation", "Enrolled in medical.")
    headline("ben_k_401k", "401(k) Participation", "ben_401k_participation", "Contributing to the 401(k).")
    headline("ben_k_er", "Employer Monthly Cost", "ben_er_cost", "Employer premiums and match per month.")
    headline("ben_k_share", "Employer Cost Share", "ben_er_share", "Employer share of total cost.")
    headline("ben_k_lives", "Covered Lives (Medical)", "ben_covered_lives", "Employees + dependents covered.")
    pt = "label/benefit_plans.plan_type"
    chart("ben_oe", "donut_chart", "2027 Open Enrollment Progress",
          "Medical elections for plan year 2027: submitted, waived or not yet elected.", ["ben_oe_employees"],
          view=["label/benefit_enrollments.election_status"],
          filters={**incl("label/benefit_enrollments.plan_year", "2027"), **incl(pt, "Medical")},
          config={"legend_position": "right"})
    chart("ben_by_plan", "bar_chart", "Enrollment by Plan", "Enrollments per plan.", ["ben_enrollments"],
          view=["label/benefit_plans.benefit_plan_id.plan_name"],
          filters=excl("label/benefit_enrollments.election_status", "Waived", "Not Yet Elected"))
    chart("ben_tier", "donut_chart", "Medical Coverage Tier", "Employee only vs family coverage.", ["ben_enrollments"],
          view=["label/benefit_enrollments.coverage_tier"], filters=incl(pt, "Medical"),
          config={"legend_position": "right"})
    chart("ben_cost_type", "bar_chart", "Employer vs Employee Cost by Plan Type", "Monthly cost split per plan type.",
          ["ben_er_cost", "ben_ee_cost"], view=[pt], config={"legend_position": "bottom", "stack_measures": True})
    chart("ben_via", "column_chart", "Elections by Channel and Plan Year", "Mobile self-service adoption at enrollment.",
          ["ben_eligible"], view=["label/benefit_enrollments.plan_year"], segment=["label/benefit_enrollments.enrolled_via"],
          filters=excl("label/benefit_enrollments.enrolled_via", "N/A"),
          config={"legend_position": "bottom", "stack_measures_to_100": True})
    chart("ben_by_location", "table", "Benefits by Location", "Participation and cost per location.",
          ["ben_eligible", "ben_med_participation", "ben_401k_participation", "ben_er_cost", "ben_ee_cost"],
          view=[LOC])
    dashboard("p07_benefits", "7. Benefits Administration",
              "Participation, plan mix, employer vs employee cost and 2027 open enrollment progress. "
              "The date filter applies to the coverage effective date (default: current plan year).",
              [(None, kpis(("ben_k_elig", 1), ("ben_k_med", 1), ("ben_k_401k", 1), ("ben_k_er", 1), ("ben_k_share", 1),
                           ("ben_k_lives", 1))),
               ("Open Enrollment 2027", [("ben_oe", 4, 16, None), ("ben_by_plan", 8, 16, 1)]),
               ("Cost & Coverage", [("ben_cost_type", 6, 16, 1), ("ben_tier", 3, 16, 1), ("ben_via", 3, 16, None)]),
               ("Locations", [("ben_by_location", 12, 14, 1)])],
              extra_filters={"plan_type": {"type": "attribute_filter", "title": "Plan Type", "using": pt}})

    # 8. ACA Compliance -----------------------------------------------------
    headline("aca_k_ft", "Avg Monthly FT Employees", "aca_avg_ft", "ACA full-time employees per month.")
    headline("aca_k_offer", "Offer Rate (95% Test)", "aca_offer_rate", "Must stay at or above 95%.")
    headline("aca_k_risk", "At-Risk Employee-Months", "aca_risk_months", "Months that could trigger 4980H.")
    headline("aca_k_exp", "Penalty Exposure", "aca_exposure", "Estimated 4980H exposure.")
    headline("aca_k_aff", "Affordability Rate", "aca_affordability", "Lowest-cost plan affordable.")
    headline("aca_k_take", "Medical Take-Up", "aca_enroll_rate", "Offered employee-months enrolled.")
    chart("aca_status_trend", "column_chart", "Workforce by ACA Status", "Employee-months by ACA status.",
          ["aca_records"], view=[MONTH], segment=["label/aca_monthly.aca_status"],
          config={"legend_position": "bottom", "stack_measures": True})
    chart("aca_offer_trend", "line_chart", "Offer Rate by Month", "Monthly offer rate vs the 95% requirement.",
          ["aca_offer_rate"], view=[MONTH])
    chart("aca_line14", "bar_chart", "1095-C Line 14 Codes", "Offer of coverage codes.", ["aca_records"],
          view=["label/aca_monthly.offer_code_line14"])
    chart("aca_line16", "bar_chart", "1095-C Line 16 Codes", "Safe harbor codes.", ["aca_records"],
          view=["label/aca_monthly.safe_harbor_code_line16"])
    chart("aca_risk_table", "table", "Employees at Penalty Risk", "Employee-months with 4980H exposure.",
          ["aca_risk_months", "aca_exposure", "aca_avg_hours"], view=[LOC, "label/employees.employee_id.full_name"],
          filters={**incl("label/aca_monthly.offer_code_line14", "1H"),
                   **incl("label/aca_monthly.aca_status", "Full-Time", "Variable Hour - Became Full-Time"),
                   **excl("label/aca_monthly.safe_harbor_code_line16", "2D", "2A")})
    chart("aca_by_location", "table", "ACA by Location", "ACA KPIs per location.",
          ["aca_avg_ft", "aca_offer_rate", "aca_affordability", "aca_enroll_rate", "aca_risk_months", "aca_exposure",
           "aca_newly_ft"], view=[LOC])
    dashboard("p08_aca", "8. ACA Compliance",
              "Employer mandate: full-time counts, 95% offer test, affordability, 1095-C codes and penalty exposure.",
              [(None, kpis(("aca_k_ft", 1), ("aca_k_offer", 1), ("aca_k_risk", 1), ("aca_k_exp", 1), ("aca_k_aff", 1),
                           ("aca_k_take", 1))),
               ("Measurement", [("aca_status_trend", 7, 16, 1), ("aca_offer_trend", 5, 16, 1)]),
               ("Form 1095-C", [("aca_line14", 4, 14, 1), ("aca_line16", 4, 14, 1), ("aca_risk_table", 4, 14, 1)]),
               ("Locations", [("aca_by_location", 12, 14, 1)])])

    # 9. LMS ----------------------------------------------------------------
    headline("lms_k_rate", "Completion Rate", "lms_completion_rate", "Assigned courses completed.")
    headline("lms_k_ontime", "On-Time Completion", "lms_on_time_rate", "Completed by the due date.")
    headline("lms_k_overdue", "Overdue Courses", "lms_overdue", "Past due, not completed.", compare=False)
    headline("lms_k_ceu", "CEUs Earned", "lms_ceu", "Continuing education credits.")
    headline("lms_k_score", "Avg Score", "lms_avg_score", "Average quiz score (%).")
    headline("lms_k_hours", "Training Hours", "lms_hours", "Time spent learning.")
    chart("lms_trend", "column_chart", "Completions by Month and Reason", "Orientation vs annual compliance vs development.",
          ["lms_completed"], view=[MONTH], segment=["label/course_assignments.assignment_reason"],
          config={"legend_position": "bottom", "stack_measures": True})
    chart("lms_by_category", "bar_chart", "Completion Rate by Course Category", "Compliance vs clinical vs culture.",
          ["lms_completion_rate"], view=["label/courses.course_category"])
    chart("lms_overdue_courses", "table", "Overdue Courses", "Which mandatory courses are overdue, by location.",
          ["lms_overdue"], view=["label/courses.course_id.course_title", LOC])
    chart("lms_device", "donut_chart", "Completion Device", "Mobile vs desktop learning.", ["lms_completed"],
          view=["label/course_assignments.completion_device"], filters=excl("label/course_assignments.completion_device", "N/A"),
          config={"legend_position": "right"})
    chart("lms_by_location", "table", "Training by Location", "LMS KPIs per location.",
          ["lms_assignments", "lms_completion_rate", "lms_on_time_rate", "lms_overdue", "lms_ceu", "lms_avg_score"],
          view=[LOC])
    dashboard("p09_lms", "9. Learning (LMS)",
              "Training compliance: completion and on-time rates, overdue mandatory courses, CEUs and mobile learning.",
              [(None, kpis(("lms_k_rate", 1), ("lms_k_ontime", 1), ("lms_k_overdue", None), ("lms_k_ceu", 1),
                           ("lms_k_score", 1), ("lms_k_hours", 1))),
               ("Completions", [("lms_trend", 8, 16, 1), ("lms_device", 4, 16, 1)]),
               ("Compliance Gaps", [("lms_by_category", 5, 18, 1), ("lms_overdue_courses", 7, 18, None)]),
               ("Locations", [("lms_by_location", 12, 14, 1)])])

    # 10. Exclusion Monitoring ----------------------------------------------
    headline("exc_k_checks", "Exclusion Checks", "exc_checks", "Screenings run.")
    headline("exc_k_emps", "Employees Screened", "exc_employees", "Distinct employees screened.")
    headline("exc_k_pot", "Potential Matches", "exc_potential", "Flags to review.")
    headline("exc_k_conf", "Confirmed Matches", "exc_confirmed", "Excluded individuals found.")
    headline("exc_k_days", "Avg Days to Resolve", "exc_days_to_resolve", "Speed of match review.")
    headline("exc_k_review", "Under Review", "exc_under_review", "Open flags.", compare=False)
    chart("exc_trend", "column_chart", "Checks by Month and List", "Monthly screening volume per exclusion list.",
          ["exc_checks"], view=[MONTH], segment=["label/exclusion_checks.exclusion_list"],
          config={"legend_position": "bottom", "stack_measures": True})
    chart("exc_matches", "bar_chart", "Potential Matches by List & Outcome",
          "Flagged checks per exclusion list: cleared false positives, under review, confirmed.", ["exc_checks"],
          view=["label/exclusion_checks.exclusion_list"], segment=["label/exclusion_checks.resolution"],
          filters=excl("label/exclusion_checks.resolution", "N/A"),
          config={"legend_position": "bottom", "stack_measures": True})
    chart("exc_confirmed_table", "table", "Confirmed Matches", "Excluded individuals and the list that flagged them.",
          ["exc_confirmed"], view=["label/employees.employee_id.full_name", LOC, "label/exclusion_checks.exclusion_list"],
          filters=incl("label/exclusion_checks.check_result", "Confirmed Match"))
    chart("exc_type", "donut_chart", "Checks by Type", "Pre-hire vs monthly rescreen.", ["exc_checks"],
          view=["label/exclusion_checks.check_type"], config={"legend_position": "right"})
    chart("exc_by_location", "table", "Screening by Location", "Exclusion monitoring per location.",
          ["exc_employees", "exc_checks", "exc_potential", "exc_confirmed", "exc_days_to_resolve"], view=[LOC])
    dashboard("p10_exclusion_monitoring", "10. Exclusion Monitoring",
              "OIG LEIE, SAM.gov and State Medicaid screening: volume, potential vs confirmed matches, resolution speed.",
              [(None, kpis(("exc_k_checks", 1), ("exc_k_emps", 1), ("exc_k_pot", 1), ("exc_k_conf", 1), ("exc_k_days", 1),
                           ("exc_k_review", None))),
               ("Screening", [("exc_trend", 8, 16, 1), ("exc_type", 4, 16, 1)]),
               ("Matches", [("exc_matches", 6, 16, 1), ("exc_confirmed_table", 6, 16, 1)]),
               ("Locations", [("exc_by_location", 12, 14, 1)])])

    # 11. HR ----------------------------------------------------------------
    headline("hr_k_hc", "Active Headcount", "hr_active_headcount", "Employees active today.", compare=False)
    headline("hr_k_hires", "Hires", "hr_hires", "New hires.")
    headline("hr_k_terms", "Terminations", "hr_terms", "Terminations.")
    headline("hr_k_turn", "Annualized Turnover", "hr_turnover", "Terminations / avg headcount, annualized.")
    headline("hr_k_early", "Early Turnover (90 days)", "hr_early_turnover", "Share of exits within 90 days.")
    headline("hr_k_cases", "HR Cases", "hr_cases", "Cases opened.")
    chart("hr_hc_trend", "line_chart", "Headcount by Month", "Month-end headcount by job family.", ["hr_headcount_eom"],
          view=[MONTH], segment=[FAMILY], config=BOTTOM)
    chart("hr_flow", "column_chart", "Hires vs Terminations", "Monthly hires and terminations.", ["hr_hires", "hr_terms"],
          view=[MONTH], config=BOTTOM)
    chart("hr_turn_role", "bar_chart", "Turnover by Job Role", "Annualized turnover per role.", ["hr_turnover"],
          view=[ROLE])
    chart("hr_reasons", "bar_chart", "Termination Reasons", "Why employees leave.", ["hr_terms"],
          view=["label/employees.termination_reason"], segment=["label/employees.termination_type"],
          config={"legend_position": "bottom", "stack_measures": True})
    chart("hr_case_cat", "bar_chart", "HR Cases by Category", "Case volume by category and who handled it.",
          ["hr_cases"], view=["label/hr_cases.case_category"], segment=["label/hr_cases.handled_by"],
          config={"legend_position": "bottom", "stack_measures": True})
    chart("hr_handler", "table", "Viventium HR Experts vs Client HR", "Speed and satisfaction by handler.",
          ["hr_cases", "hr_first_response", "hr_resolution", "hr_csat"], view=["label/hr_cases.handled_by"])
    chart("hr_by_location", "table", "Workforce by Location", "Headcount and turnover per location.",
          ["hr_hires", "hr_terms", "hr_net_change", "hr_turnover", "hr_vol_turnover", "hr_early_turnover",
           "hr_cases_per_100"], view=[LOC])
    dashboard("p11_hr", "11. HR & Workforce",
              "Headcount, hires, turnover (incl. first-90-day exits), termination reasons and HR expert case support.",
              [(None, kpis(("hr_k_hc", None), ("hr_k_hires", 1), ("hr_k_terms", 1), ("hr_k_turn", 1), ("hr_k_early", 1),
                           ("hr_k_cases", 1))),
               ("Workforce", [("hr_hc_trend", 6, 16, 1), ("hr_flow", 6, 16, 1)]),
               ("Turnover", [("hr_turn_role", 6, 18, 1), ("hr_reasons", 6, 18, 1)]),
               ("HR Support", [("hr_case_cat", 7, 16, 1), ("hr_handler", 5, 16, 1)]),
               ("Locations", [("hr_by_location", 12, 14, 1)])])


# ---------------------------------------------------------------------------
HEADERS = {
    "datasets": "# Generated by gooddata/build_analytics.py - edit the generator, not this file.\n",
}


def dump(folder, name, doc):
    path = os.path.join(OUT, folder, f"{name}.yaml")
    with open(path, "w") as f:
        f.write("# Generated by gooddata/build_analytics.py - edit the generator, not this file.\n\n")
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, width=120)


REF = __import__("re").compile(r"\{?(fact|label|attribute|dataset|metric)/([A-Za-z0-9_.]+)\}?")


def check_and_manifest():
    """Fail if any object of one data product depends on another product; write data_products.json."""
    ds_ids = set(MODEL) | set(DATES)
    metric_product = {m[0]: m[5] for m in METRICS}

    def ds_of(ident):
        head = ident.split(".")[0]
        return head if head in ds_ids else None

    def check(owner, product, text):
        for kind, ident in REF.findall(text):
            if kind == "metric":
                if metric_product[ident] != product:
                    raise SystemExit(f"{owner} ({product}) uses metric {ident} of {metric_product[ident]}")
                continue
            ds = ds_of(ident)
            if ds is None:
                raise SystemExit(f"{owner}: unknown reference {kind}/{ident}")
            if product_of_dataset(ds) not in (SHARED, product):
                raise SystemExit(f"{owner} ({product}) uses {kind}/{ident} of {product_of_dataset(ds)}")

    for mid, _, maql, _, _, tag in METRICS:
        check(f"metric {mid}", tag, maql)
    for vid, v in VIS.items():
        if "tags" not in v:
            raise SystemExit(f"visualisation {vid} is not on any dashboard")
        check(f"visualisation {vid}", v["tags"][0], yaml.safe_dump(v))
    for d in DASHBOARDS:
        check(f"dashboard {d['id']}", d["tags"][0], yaml.safe_dump(d))

    manifest = {}
    for product in PRODUCT_OF_DASHBOARD.values():
        dsets = [t for t in MODEL if DATASET_PRODUCT.get(t) == product]
        facts, attrs, labels = [], [], []
        for t in dsets:
            m = MODEL[t]
            pk_id = f"{t}.{m['pk'][0]}"
            attrs.append(pk_id)
            labels += [f"{pk_id}.{c}" for c, _, _ in m.get("labels", [])]
            attrs += [f"{t}.{c}" for c, _, _ in m.get("attrs", [])]
            facts += [f"{t}.{c}" for c, _ in m.get("facts", [])]
        # sensitive columns of shared dimensions that belong to a data product (column-level permissions)
        facts += {"Payroll": ["employees.hourly_rate", "employees.annual_salary"]}.get(product, [])
        manifest[product] = {
            "user_group": slug(product), "datasets": dsets, "facts": facts, "attributes": attrs, "labels": labels,
            "metrics": [m[0] for m in METRICS if m[5] == product],
            "visualizations": [v for v, d in VIS.items() if d["tags"] == [product]],
            "dashboards": [d["id"] for d in DASHBOARDS if d["tags"] == [product]],
        }
    with open(os.path.join(HERE, "data_products.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def main():
    for folder in ("datasets", "metrics", "visualisations", "dashboards"):
        p = os.path.join(OUT, folder)
        if os.path.isdir(p):
            shutil.rmtree(p)
        os.makedirs(p)
    for name, doc in build_datasets().items():
        dump("datasets", name, doc)
    build_metrics()
    for mid, title, maql, fmt, desc, tag in METRICS:
        dump("metrics", mid, {"type": "metric", "id": mid, "title": title, "description": desc, "tags": [tag],
                              "maql": maql, "format": fmt})
    build_visuals()
    manifest = check_and_manifest()
    for vid, doc in VIS.items():
        dump("visualisations", vid, doc)
    for d in DASHBOARDS:
        dump("dashboards", d["id"], d)
    for product, x in manifest.items():
        print(f"  {product:<22} {x['user_group']:<26} metrics {len(x['metrics']):>2}  vis {len(x['visualizations']):>2}")
    print(f"datasets {len(MODEL) + len(DATES)}, metrics {len(METRICS)}, visualisations {len(VIS)}, "
          f"dashboards {len(DASHBOARDS)}")


if __name__ == "__main__":
    main()
