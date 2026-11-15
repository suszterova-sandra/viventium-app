#!/usr/bin/env python3
"""
Viventium demo data generator for GoodData Cloud (multitenant).

Viventium (https://viventium.com) sells an HCM / workforce platform for post-acute care:
skilled nursing, senior living / CCRC, home health, hospice, home care and ABA.
This script builds one relational data source that covers each Viventium product
as its own fact table (one product = one dashboard), with shared dimensions.

Multitenancy: every tenant-specific table carries `wdf__client_id` (= GoodData child
workspace client ID). Global reference tables (job_roles, courses, pay_periods) have none.

The simulation is internally consistent: employees come from requisitions (ATS), get
onboarding tasks, are scheduled (Scheduling), punch in/out (Time & Attendance), are
paid from their timecards (Payroll), take On-Demand Pay advances that are repaid in
payroll, enroll in benefits (deductions in payroll), are ACA-measured from their
worked hours, take LMS courses, are screened monthly (Exclusion Monitoring) and raise
HR cases.

Usage:  python3 generate.py      -> ./csv/*.csv and ./ddl/*.sql   (deterministic)
"""
import csv
import datetime as dt
import math
import os
import random
from collections import defaultdict

SEED = 20261115
START = dt.date(2024, 1, 1)
END = dt.date(2026, 11, 14)            # last day with actuals
SCHEDULE_UNTIL = END + dt.timedelta(days=14)   # published future schedule
P0 = dt.date(2023, 12, 30)             # first bi-weekly pay period start (Saturday)
NA_DATE = "1900-01-01"                 # "not applicable" date sentinel (no NULLs anywhere)
NA_TS = "1900-01-01 00:00:00"
NA = "N/A"
WDF = "wdf__client_id"

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(HERE, "csv")
OUT_DDL = os.path.join(HERE, "ddl")

rng = random.Random(SEED)
SPAN = (END - START).days


def progress(d):
    """0 at START .. 1 at END - drives improvement trends after Viventium adoption."""
    return min(1.0, max(0.0, (d - START).days / SPAN))


def poisson(lam):
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def wchoice(pairs):
    tot = sum(w for _, w in pairs)
    r = rng.random() * tot
    for v, w in pairs:
        r -= w
        if r <= 0:
            return v
    return pairs[-1][0]


def ds(d):
    return d.isoformat()


def ts(d, minutes):
    return (dt.datetime.combine(d, dt.time()) + dt.timedelta(minutes=int(minutes))).strftime("%Y-%m-%d %H:%M:%S")


def r2(x):
    return round(x + 0.0, 2)


def yn(b):
    return "Yes" if b else "No"


# ---------------------------------------------------------------------------
# Schema (column order = CSV order)
# ---------------------------------------------------------------------------
K = "VARCHAR(64)"
T = "VARCHAR(128)"
D = "DATE"
TS = "TIMESTAMP"
M = "NUMERIC(12,2)"
H = "NUMERIC(8,2)"
I = "INTEGER"
GEO = "NUMERIC(9,6)"

SCHEMA = {
    # ---- global reference (no WDF) ----
    "job_roles": [("job_role_id", K), ("job_title", T), ("job_family", T), ("department", T),
                  ("is_clinical", "VARCHAR(3)"), ("license_required", T), ("flsa_status", T), ("pay_type", T),
                  ("work_setting", T)],
    "courses": [("course_id", K), ("course_title", T), ("course_category", T), ("delivery_format", T),
                ("duration_minutes", I), ("ceu_credits", H), ("is_state_mandated", "VARCHAR(3)")],
    "pay_periods": [("pay_period_id", K), ("pay_period_label", T), ("period_start_date", D), ("period_end_date", D),
                    ("check_date", D), ("pay_year", I), ("period_number", I)],
    # ---- tenant dimensions ----
    "clients": [("client_id", K), ("client_name", T), ("industry", T), ("industry_segment", T),
                ("headquarters_city", T), ("headquarters_state", "VARCHAR(2)"), ("viventium_client_since", D),
                ("plan_tier", T), (WDF, K)],
    "locations": [("location_id", K), ("location_name", T), ("location_type", T), ("city", T),
                  ("state", "VARCHAR(2)"), ("state_name", T), ("postal_code", "VARCHAR(10)"), ("region", T),
                  ("latitude", GEO), ("longitude", GEO), ("licensed_capacity", I), ("capacity_unit", T),
                  ("client_id", K), (WDF, K)],
    "employees": [("employee_id", K), ("employee_number", K), ("first_name", T), ("last_name", T),
                  ("full_name", T), ("gender", "VARCHAR(10)"), ("age_band", T), ("location_id", K),
                  ("job_role_id", K), ("employment_type", T), ("fte", H), ("pay_type", T), ("hourly_rate", M),
                  ("annual_salary", M), ("hire_date", D), ("termination_date", D), ("employment_status", T),
                  ("termination_type", T), ("termination_reason", T), ("rehire_eligible", T),
                  ("recruitment_source", T), ("source_requisition_id", K), ("preferred_shift", T),
                  ("uses_mobile_app", "VARCHAR(3)"), ("odp_enrolled", "VARCHAR(3)"), ("odp_enrollment_date", D),
                  ("is_placeholder", "VARCHAR(3)"), (WDF, K)],
    "benefit_plans": [("benefit_plan_id", K), ("plan_name", T), ("plan_type", T), ("carrier", T),
                      ("network_type", T), (WDF, K)],
    # ---- Applicant Tracking + Job Sponsorships ----
    "requisitions": [("requisition_id", K), ("location_id", K), ("job_role_id", K), ("requisition_reason", T),
                     ("priority", T), ("opened_date", D), ("filled_date", D), ("closed_date", D),
                     ("requisition_status", T), ("openings", I), ("days_open", I), ("days_to_fill", I),
                     ("sign_on_bonus", M), (WDF, K)],
    "job_postings": [("posting_id", K), ("requisition_id", K), ("job_board", T), ("posted_date", D),
                     ("posting_end_date", D), ("is_sponsored", "VARCHAR(3)"), ("sponsorship_spend", M),
                     ("impressions", I), ("clicks", I), ("applies", I), (WDF, K)],
    "applications": [("application_id", K), ("requisition_id", K), ("candidate_id", K), ("candidate_name", T),
                     ("applied_date", D), ("application_source", T), ("apply_device", T),
                     ("highest_stage", T), ("stage_order", I), ("application_status", T),
                     ("screened_date", D), ("interview_date", D), ("offer_date", D), ("hire_date", D),
                     ("hours_to_first_contact", H), ("days_to_hire", I), ("is_screened", I),
                     ("is_interviewed", I), ("is_offered", I), ("is_hired", I), (WDF, K)],
    # ---- Onboarding ----
    "onboarding_tasks": [("onboarding_task_id", K), ("employee_id", K), ("task_name", T), ("task_category", T),
                         ("responsible_party", T), ("assigned_date", D), ("due_date", D), ("completed_date", D),
                         ("task_status", T), ("completed_via", T), ("days_to_complete", I),
                         ("is_completed", I), ("is_overdue", I), ("completed_on_time", I), (WDF, K)],
    # ---- Scheduling ----
    "shifts": [("shift_id", K), ("employee_id", K), ("shift_date", D), ("shift_type", T),
               ("scheduled_start", TS), ("scheduled_end", TS), ("scheduled_hours", H), ("visit_count", I),
               ("shift_status", T), ("fill_method", T), ("coverage_outcome", T), ("covers_shift_id", K),
               ("is_weekend", "VARCHAR(3)"), ("publish_lead_days", I), ("agency_cost", M), (WDF, K)],
    # ---- Time & Attendance ----
    "timecards": [("timecard_id", K), ("shift_id", K), ("employee_id", K), ("work_date", D),
                  ("clock_in", TS), ("clock_out", TS), ("scheduled_hours", H), ("worked_hours", H),
                  ("regular_hours", H), ("overtime_hours", H), ("break_minutes", I), ("late_minutes", I),
                  ("is_late", I), ("is_early_out", I), ("is_missed_punch", I), ("clock_method", T),
                  ("within_geofence", T), ("manager_edited", "VARCHAR(3)"), ("approval_status", T), (WDF, K)],
    # ---- Payroll ----
    "payroll": [("payroll_id", K), ("pay_period_id", K), ("employee_id", K), ("check_date", D),
                ("payment_method", T), ("regular_hours", H), ("overtime_hours", H), ("pto_hours", H),
                ("regular_pay", M), ("overtime_pay", M), ("blended_rate_ot_adjustment", M),
                ("shift_differential_pay", M), ("wage_parity_supplement", M), ("retro_pay", M),
                ("bonus_pay", M), ("pto_pay", M), ("gross_pay", M), ("pretax_deductions", M),
                ("employee_taxes", M), ("odp_repayment", M), ("net_pay", M), ("employer_taxes", M),
                ("employer_benefit_cost", M), ("total_employer_cost", M), (WDF, K)],
    # ---- On-Demand Pay ----
    "odp_transactions": [("odp_transaction_id", K), ("employee_id", K), ("pay_period_id", K),
                         ("request_date", D), ("request_timestamp", TS), ("amount", M), ("fee", M),
                         ("transfer_type", T), ("transaction_status", T), ("decline_reason", T), (WDF, K)],
    # ---- Benefits Administration ----
    "benefit_enrollments": [("enrollment_id", K), ("employee_id", K), ("benefit_plan_id", K), ("plan_year", I),
                            ("coverage_tier", T), ("enrollment_event", T), ("election_date", D),
                            ("effective_date", D), ("coverage_end_date", D), ("election_status", T),
                            ("enrolled_via", T), ("covered_lives", I), ("contribution_pct", H),
                            ("employee_monthly_cost", M), ("employer_monthly_cost", M), ("is_enrolled", I),
                            (WDF, K)],
    # ---- ACA Compliance ----
    "aca_monthly": [("aca_record_id", K), ("employee_id", K), ("reporting_month", D), ("reporting_year", I),
                    ("hours_of_service", H), ("aca_status", T), ("measurement_method", T),
                    ("offer_code_line14", "VARCHAR(4)"), ("safe_harbor_code_line16", "VARCHAR(4)"),
                    ("lowest_cost_ee_premium", M), ("affordability_threshold", M), ("is_affordable", I),
                    ("is_aca_full_time", I), ("is_offered_coverage", I), ("is_enrolled_medical", I),
                    ("penalty_risk", I), ("penalty_exposure_amount", M), ("form_1095c_status", T), (WDF, K)],
    # ---- LMS ----
    "course_assignments": [("assignment_id", K), ("employee_id", K), ("course_id", K), ("assignment_reason", T),
                           ("assigned_date", D), ("due_date", D), ("completed_date", D), ("assignment_status", T),
                           ("score_pct", H), ("time_spent_minutes", I), ("attempts", I),
                           ("completion_device", T), ("ceu_credits_earned", H), ("is_completed", I),
                           ("is_overdue", I), ("completed_on_time", I), (WDF, K)],
    # ---- Exclusion Monitoring ----
    "exclusion_checks": [("check_id", K), ("employee_id", K), ("check_date", D), ("exclusion_list", T),
                         ("check_type", T), ("check_result", T), ("resolution", T), ("resolved_date", D),
                         ("days_to_resolve", I), ("is_potential_match", I), ("is_confirmed_match", I), (WDF, K)],
    # ---- HR (HR expert support + workforce) ----
    "hr_cases": [("case_id", K), ("employee_id", K), ("opened_date", D), ("closed_date", D), ("case_category", T),
                 ("priority", T), ("channel", T), ("handled_by", T), ("case_status", T),
                 ("first_response_hours", H), ("resolution_days", I), ("satisfaction_score", I),
                 ("is_rated", I), ("is_closed", I), ("escalated", "VARCHAR(3)"), (WDF, K)],
    "workforce_monthly": [("snapshot_id", K), ("employee_id", K), ("snapshot_month", D),
                          ("is_active_eom", I), ("is_new_hire", I), ("is_termination", I),
                          ("is_voluntary_termination", I), ("is_early_turnover", I), ("tenure_months", I),
                          ("fte_eom", H), (WDF, K)],
}

PRIMARY_KEYS = {
    "job_roles": ["job_role_id"], "courses": ["course_id"], "pay_periods": ["pay_period_id"],
    "clients": ["client_id"], "locations": ["location_id"], "employees": ["employee_id"],
    "benefit_plans": ["benefit_plan_id"], "requisitions": ["requisition_id"], "job_postings": ["posting_id"],
    "applications": ["application_id"], "onboarding_tasks": ["onboarding_task_id"], "shifts": ["shift_id"],
    "timecards": ["timecard_id"], "payroll": ["payroll_id"], "odp_transactions": ["odp_transaction_id"],
    "benefit_enrollments": ["enrollment_id"], "aca_monthly": ["aca_record_id"],
    "course_assignments": ["assignment_id"], "exclusion_checks": ["check_id"], "hr_cases": ["case_id"],
    "workforce_monthly": ["snapshot_id"],
}

# ---------------------------------------------------------------------------
# Tenants & locations (fictional operators, real US cities/coordinates)
# ---------------------------------------------------------------------------
STATES = {  # name, region, wage multiplier, state income tax rate
    "NY": ("New York", "Northeast", 1.24, 0.055), "NJ": ("New Jersey", "Northeast", 1.16, 0.045),
    "CT": ("Connecticut", "Northeast", 1.15, 0.050), "PA": ("Pennsylvania", "Northeast", 1.00, 0.0307),
    "OH": ("Ohio", "Midwest", 0.95, 0.030), "FL": ("Florida", "Southeast", 0.97, 0.0),
    "NC": ("North Carolina", "Southeast", 0.94, 0.045), "TN": ("Tennessee", "Southeast", 0.91, 0.0),
    "GA": ("Georgia", "Southeast", 0.94, 0.053), "AL": ("Alabama", "Southeast", 0.88, 0.045),
    "TX": ("Texas", "Southwest", 0.96, 0.0), "AZ": ("Arizona", "Southwest", 1.00, 0.025),
    "CA": ("California", "West", 1.22, 0.050),
}

TENANTS = [
    dict(client_id="riverstone", name="Riverstone Health Partners", industry="Skilled Nursing",
         segment="Facilities", hq=("Brooklyn", "NY"), since="2022-03-01", tier="Enterprise", growth=0.03,
         prefix="RSH", locations=[
             dict(id="RSH-BKN", name="Riverstone Rehabilitation & Nursing - Brooklyn", type="Skilled Nursing Facility",
                  mix="snf", city="Brooklyn", state="NY", zip="11220", lat=40.641300, lon=-74.017000, cap=180,
                  unit="Licensed Beds", hc=120),
             dict(id="RSH-YON", name="Riverstone Rehabilitation & Nursing - Yonkers", type="Skilled Nursing Facility",
                  mix="snf", city="Yonkers", state="NY", zip="10701", lat=40.931200, lon=-73.898800, cap=140,
                  unit="Licensed Beds", hc=95),
             dict(id="RSH-PAR", name="Riverstone Care Center - Paramus", type="Skilled Nursing Facility",
                  mix="snf", city="Paramus", state="NJ", zip="07652", lat=40.944500, lon=-74.075400, cap=150,
                  unit="Licensed Beds", hc=100),
             dict(id="RSH-TMS", name="Riverstone Care Center - Toms River", type="Skilled Nursing Facility",
                  mix="snf", city="Toms River", state="NJ", zip="08753", lat=39.953700, lon=-74.197900, cap=120,
                  unit="Licensed Beds", hc=80),
         ]),
    dict(client_id="maplehollow", name="Maple Hollow Senior Living", industry="Senior Living & CCRC",
         segment="Facilities", hq=("Lancaster", "PA"), since="2023-06-01", tier="Professional", growth=0.06,
         prefix="MHL", locations=[
             dict(id="MHL-LAN", name="Maple Hollow at Lancaster", type="CCRC", mix="ccrc", city="Lancaster",
                  state="PA", zip="17601", lat=40.037900, lon=-76.305500, cap=210, unit="Residential Units", hc=80),
             dict(id="MHL-DUB", name="Maple Hollow Assisted Living & Memory Care - Dublin",
                  type="Assisted Living & Memory Care", mix="senior", city="Dublin", state="OH", zip="43017",
                  lat=40.099200, lon=-83.114100, cap=96, unit="Residential Units", hc=60),
             dict(id="MHL-SRQ", name="Maple Hollow at Sarasota Bay", type="CCRC", mix="ccrc", city="Sarasota",
                  state="FL", zip="34232", lat=27.336400, lon=-82.530700, cap=190, unit="Residential Units", hc=70),
             dict(id="MHL-AVL", name="Maple Hollow Assisted Living - Asheville", type="Assisted Living",
                  mix="senior", city="Asheville", state="NC", zip="28803", lat=35.595100, lon=-82.551500, cap=72,
                  unit="Residential Units", hc=45),
         ]),
    dict(client_id="hearthside", name="HearthSide Home Care", industry="Home Care",
         segment="Home Care & ABA", hq=("Flushing", "NY"), since="2021-09-01", tier="Enterprise", growth=0.12,
         prefix="HSC", locations=[
             dict(id="HSC-QNS", name="HearthSide Home Care - Queens", type="Home Care Agency", mix="homecare",
                  city="Flushing", state="NY", zip="11354", lat=40.767500, lon=-73.833100, cap=420,
                  unit="Active Clients", hc=110),
             dict(id="HSC-HEM", name="HearthSide Home Care - Long Island", type="Home Care Agency", mix="homecare",
                  city="Hempstead", state="NY", zip="11550", lat=40.706200, lon=-73.618700, cap=300,
                  unit="Active Clients", hc=80),
             dict(id="HSC-STM", name="HearthSide Home Care - Stamford", type="Home Care Agency", mix="homecare",
                  city="Stamford", state="CT", zip="06901", lat=41.053400, lon=-73.538700, cap=160,
                  unit="Active Clients", hc=45),
             dict(id="HSC-HOU", name="HearthSide Home Care - Houston", type="Home Care Agency", mix="homecare",
                  city="Houston", state="TX", zip="77027", lat=29.740000, lon=-95.444000, cap=220,
                  unit="Active Clients", hc=60),
         ]),
    dict(client_id="willowbend", name="Willowbend Home Health & Hospice", industry="Home Health & Hospice",
         segment="Home Health & Hospice", hq=("Nashville", "TN"), since="2023-01-01", tier="Professional",
         growth=0.09, prefix="WBH", locations=[
             dict(id="WBH-NSH", name="Willowbend Home Health - Nashville", type="Home Health Agency",
                  mix="homehealth", city="Nashville", state="TN", zip="37203", lat=36.162700, lon=-86.781600,
                  cap=350, unit="Average Daily Census", hc=55),
             dict(id="WBH-KNX", name="Willowbend Hospice - Knoxville", type="Hospice", mix="hospice",
                  city="Knoxville", state="TN", zip="37919", lat=35.960600, lon=-83.920700, cap=110,
                  unit="Average Daily Census", hc=35),
             dict(id="WBH-ATL", name="Willowbend Home Health & Hospice - Marietta", type="Home Health & Hospice",
                  mix="hhh", city="Marietta", state="GA", zip="30060", lat=33.952600, lon=-84.549900, cap=260,
                  unit="Average Daily Census", hc=45),
             dict(id="WBH-BHM", name="Willowbend Hospice - Birmingham", type="Hospice", mix="hospice",
                  city="Birmingham", state="AL", zip="35209", lat=33.465000, lon=-86.809400, cap=90,
                  unit="Average Daily Census", hc=30),
         ]),
    dict(client_id="littleoak", name="Little Oak Behavioral Health", industry="ABA Therapy",
         segment="Home Care & ABA", hq=("San Diego", "CA"), since="2024-01-01", tier="Growth", growth=0.18,
         prefix="LOB", locations=[
             dict(id="LOB-SAN", name="Little Oak ABA Center - San Diego", type="ABA Clinic", mix="aba",
                  city="San Diego", state="CA", zip="92123", lat=32.808500, lon=-117.134600, cap=95,
                  unit="Active Learners", hc=45),
             dict(id="LOB-PHX", name="Little Oak ABA Center - Phoenix", type="ABA Clinic", mix="aba",
                  city="Phoenix", state="AZ", zip="85016", lat=33.509100, lon=-112.027000, cap=80,
                  unit="Active Learners", hc=40),
             dict(id="LOB-AUS", name="Little Oak ABA Center - Austin", type="ABA Clinic", mix="aba",
                  city="Austin", state="TX", zip="78758", lat=30.376500, lon=-97.709000, cap=70,
                  unit="Active Learners", hc=35),
         ]),
]

# ---------------------------------------------------------------------------
# Job roles: title, family, department, pay type, base rate (hourly USD or annual salary),
# work pattern, FT share, annual turnover, mean days-to-fill, applicants per req,
# license, clinical, coverage kind for call-offs
# ---------------------------------------------------------------------------
ROLES = {
    "CNA": ("Certified Nursing Assistant", "Direct Care", "Nursing", "Hourly", 18.5, "fac8_24", .70, .55, 26, 30, "CNA", True, "agency"),
    "LPN": ("Licensed Practical Nurse", "Nursing", "Nursing", "Hourly", 28.5, "fac8_24", .75, .38, 36, 14, "LPN", True, "agency"),
    "RN": ("Registered Nurse", "Nursing", "Nursing", "Hourly", 41.0, "fac12", .75, .30, 44, 10, "RN", True, "agency"),
    "RNUM": ("RN Unit Manager", "Nursing", "Nursing", "Salary", 96000, "salary", 1, .20, 50, 8, "RN", True, None),
    "DON": ("Director of Nursing", "Leadership", "Nursing", "Salary", 128000, "salary", 1, .15, 70, 6, "RN", True, None),
    "NHA": ("Nursing Home Administrator", "Leadership", "Administration", "Salary", 142000, "salary", 1, .12, 80, 5, "NHA", False, None),
    "PT": ("Physical Therapist", "Therapy", "Rehabilitation", "Hourly", 50.0, "day8wk", .80, .22, 55, 7, "PT", True, None),
    "OT": ("Occupational Therapist", "Therapy", "Rehabilitation", "Hourly", 47.5, "day8wk", .80, .22, 55, 7, "OT", True, None),
    "SLP": ("Speech-Language Pathologist", "Therapy", "Rehabilitation", "Hourly", 48.5, "day8wk", .70, .22, 60, 6, "SLP", True, None),
    "PTA": ("Physical Therapist Assistant", "Therapy", "Rehabilitation", "Hourly", 32.0, "day8wk", .80, .28, 40, 9, "PTA", True, None),
    "COTA": ("Certified Occupational Therapy Assistant", "Therapy", "Rehabilitation", "Hourly", 31.0, "day8wk", .80, .28, 40, 9, "COTA", True, None),
    "DIET": ("Dietary Aide", "Support Services", "Dietary & Culinary", "Hourly", 16.0, "fac8_2", .55, .58, 18, 28, NA, False, "internal"),
    "COOK": ("Cook", "Support Services", "Dietary & Culinary", "Hourly", 19.0, "fac8_2", .75, .45, 22, 20, NA, False, "internal"),
    "HSK": ("Housekeeper", "Support Services", "Environmental Services", "Hourly", 16.0, "day8", .70, .55, 18, 26, NA, False, "internal"),
    "LAUND": ("Laundry Aide", "Support Services", "Environmental Services", "Hourly", 15.5, "day8", .60, .55, 18, 24, NA, False, "internal"),
    "ACT": ("Activities Assistant", "Life Enrichment", "Life Enrichment", "Hourly", 18.0, "day8", .60, .40, 25, 18, NA, False, None),
    "SW": ("Social Services Director", "Social Services", "Social Services", "Salary", 64000, "salary", 1, .22, 45, 9, "LMSW", False, None),
    "MAINT": ("Maintenance Technician", "Support Services", "Maintenance", "Hourly", 23.0, "day8wk", .95, .30, 30, 15, NA, False, None),
    "BOM": ("Business Office Coordinator", "Administration", "Administration", "Hourly", 22.0, "office", .90, .28, 28, 22, NA, False, None),
    "SCHED": ("Staffing Coordinator", "Administration", "Scheduling & Intake", "Hourly", 22.0, "office", .95, .32, 30, 20, NA, False, None),
    "CG": ("Resident Care Associate", "Direct Care", "Resident Care", "Hourly", 17.0, "fac8_24", .65, .60, 22, 32, NA, True, "agency"),
    "MT": ("Medication Technician", "Direct Care", "Resident Care", "Hourly", 19.5, "fac8_2", .70, .50, 28, 18, "Med Tech", True, "agency"),
    "ED": ("Executive Director", "Leadership", "Administration", "Salary", 118000, "salary", 1, .15, 75, 8, NA, False, None),
    "WD": ("Wellness Director", "Leadership", "Resident Care", "Salary", 98000, "salary", 1, .18, 60, 7, "RN", True, None),
    "CR": ("Community Relations Director", "Sales & Marketing", "Administration", "Salary", 72000, "salary", 1, .25, 45, 14, NA, False, None),
    "CONC": ("Concierge", "Administration", "Administration", "Hourly", 16.5, "day8", .60, .45, 20, 25, NA, False, None),
    "HHA": ("Home Health Aide", "Direct Care", "Home Care Services", "Hourly", 17.5, "visit", .55, .65, 18, 34, "HHA", True, "visit"),
    "PCA": ("Personal Care Aide", "Direct Care", "Home Care Services", "Hourly", 16.5, "visit", .50, .70, 16, 36, "PCA", True, "visit"),
    "CC": ("Care Coordinator", "Administration", "Scheduling & Intake", "Hourly", 23.0, "office", .95, .30, 30, 18, NA, False, None),
    "RNS": ("RN Field Supervisor", "Nursing", "Clinical Services", "Hourly", 43.0, "field", .90, .28, 45, 9, "RN", True, "field"),
    "BM": ("Branch Manager", "Leadership", "Administration", "Salary", 86000, "salary", 1, .18, 60, 10, NA, False, None),
    "REC": ("Talent Acquisition Specialist", "Administration", "Administration", "Hourly", 24.0, "office", .95, .30, 30, 18, NA, False, None),
    "RNCM": ("RN Case Manager", "Nursing", "Clinical Services", "Hourly", 43.0, "field", .85, .28, 48, 9, "RN", True, "field"),
    "MSW": ("Medical Social Worker", "Social Services", "Social Services", "Salary", 66000, "salary", 1, .22, 45, 8, "LMSW", True, None),
    "INT": ("Intake Coordinator", "Administration", "Scheduling & Intake", "Hourly", 22.5, "office", .95, .30, 28, 20, NA, False, None),
    "CM": ("Clinical Manager", "Leadership", "Clinical Services", "Salary", 105000, "salary", 1, .18, 65, 7, "RN", True, None),
    "BD": ("Branch Director", "Leadership", "Administration", "Salary", 112000, "salary", 1, .15, 75, 7, NA, False, None),
    "CHAP": ("Chaplain", "Spiritual Care", "Hospice Services", "Salary", 58000, "salary", 1, .18, 50, 8, NA, False, None),
    "BER": ("Bereavement Coordinator", "Spiritual Care", "Hospice Services", "Salary", 54000, "salary", 1, .20, 45, 9, NA, False, None),
    "VOL": ("Volunteer Coordinator", "Administration", "Hospice Services", "Hourly", 21.0, "office", .90, .28, 30, 15, NA, False, None),
    "RBT": ("Registered Behavior Technician", "Behavioral Health", "Behavioral Services", "Hourly", 21.0, "session", .55, .70, 28, 30, "RBT", True, "session"),
    "BCBA": ("Board Certified Behavior Analyst", "Behavioral Health", "Behavioral Services", "Salary", 84000, "salary", 1, .18, 75, 6, "BCBA", True, None),
    "BCABA": ("Assistant Behavior Analyst (BCaBA)", "Behavioral Health", "Behavioral Services", "Hourly", 33.0, "session", .85, .30, 50, 8, "BCaBA", True, "session"),
    "CD": ("Clinic Director", "Leadership", "Administration", "Salary", 108000, "salary", 1, .15, 70, 6, "BCBA", True, None),
}
(R_TITLE, R_FAMILY, R_DEPT, R_PAY, R_BASE, R_PATTERN, R_FT, R_TURN, R_TTF, R_APPS, R_LIC, R_CLIN, R_COVER) = range(13)

MIXES = {
    "snf": dict(CNA=.36, LPN=.13, RN=.09, RNUM=.02, DON=.01, NHA=.01, PT=.025, OT=.02, SLP=.01, PTA=.025,
                COTA=.015, DIET=.07, COOK=.03, HSK=.07, LAUND=.02, ACT=.025, SW=.015, MAINT=.02, BOM=.03, SCHED=.015),
    "senior": dict(CG=.34, MT=.11, LPN=.05, RN=.02, ED=.015, WD=.015, CR=.02, DIET=.09, COOK=.06, HSK=.08,
                   ACT=.05, MAINT=.04, CONC=.04, BOM=.03, SCHED=.015),
    "ccrc": dict(CG=.24, CNA=.10, MT=.08, LPN=.07, RN=.04, ED=.01, WD=.01, CR=.02, DIET=.09, COOK=.05, HSK=.08,
                 ACT=.05, MAINT=.04, CONC=.03, BOM=.03, SCHED=.015, PT=.015, OT=.01),
    "homecare": dict(HHA=.48, PCA=.32, CC=.06, SCHED=.04, RNS=.04, BM=.015, REC=.02, BOM=.03),
    "homehealth": dict(RNCM=.30, LPN=.10, HHA=.15, PT=.12, PTA=.05, OT=.06, SLP=.03, MSW=.04, INT=.05, BOM=.04,
                       CM=.025, BD=.02, SCHED=.02),
    "hospice": dict(RNCM=.30, HHA=.20, LPN=.06, MSW=.08, CHAP=.05, BER=.03, VOL=.03, INT=.05, BOM=.05, CM=.025,
                    BD=.025, SCHED=.02),
    "aba": dict(RBT=.62, BCBA=.15, BCABA=.05, INT=.04, SCHED=.03, BOM=.04, CD=.025),
}
MIXES["hhh"] = {r: (MIXES["homehealth"].get(r, 0) + MIXES["hospice"].get(r, 0)) / 2
                for r in set(MIXES["homehealth"]) | set(MIXES["hospice"])}
HOME_BASED = {"homehealth", "hospice", "hhh"}

SHIFTS_PER_WEEK = dict(fac8_24=5, fac8_2=5, fac12=3, day8=5, day8wk=5, office=5, field=5, visit=5, session=5)  # work days
WEEKDAY_ONLY = {"day8wk", "office", "field", "session"}
MULTI_PER_DAY = {"visit", "session"}
PAY_DIFF = {"Evening": 1.50, "Night": 2.50}
WEEKEND_DIFF = 1.00

FIRST_F = ["Maria", "Jennifer", "Patricia", "Linda", "Elizabeth", "Ashley", "Jessica", "Sarah", "Karen", "Nancy",
           "Lisa", "Michelle", "Angela", "Stephanie", "Nicole", "Keisha", "Tamika", "Rosa", "Guadalupe", "Ana",
           "Fatima", "Grace", "Esther", "Mercy", "Joy", "Priya", "Mei", "Ngozi", "Abena", "Yolanda", "Latoya",
           "Brittany", "Danielle", "Monique", "Carmen", "Sofia", "Isabella", "Emily", "Hannah", "Olivia",
           "Chloe", "Destiny", "Shanice", "Gloria", "Beatriz", "Marisol", "Tiffany", "Crystal", "Rachel", "Megan"]
FIRST_M = ["James", "Michael", "Robert", "David", "John", "Joseph", "Daniel", "Anthony", "Marcus", "Andre",
           "Kevin", "Brian", "Jose", "Luis", "Carlos", "Miguel", "Samuel", "Emmanuel", "Kwame", "Tunde",
           "Wei", "Raj", "Omar", "Ahmed", "Terrence", "Darnell", "Jamal", "Tyler", "Brandon", "Jordan",
           "Christopher", "Matthew", "Eric", "Victor", "Angel"]
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
        "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
        "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
        "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts", "Okafor",
        "Mensah", "Adeyemi", "Patel", "Shah", "Chen", "Wang", "Kim", "Joseph", "Pierre", "Jean-Baptiste",
        "Reyes", "Cruz", "Morales", "Ortiz", "Gutierrez", "Washington", "Brooks", "Bennett", "Coleman"]


def person():
    female = rng.random() < 0.78  # post-acute workforce is ~80% female
    first = rng.choice(FIRST_F if female else FIRST_M)
    return first, rng.choice(LAST), ("Female" if female else "Male")


# ---------------------------------------------------------------------------
# CSV writer that refuses NULL/empty values
# ---------------------------------------------------------------------------
class Writer:
    def __init__(self):
        os.makedirs(OUT_CSV, exist_ok=True)
        self.files, self.writers, self.counts = {}, {}, defaultdict(int)
        for t, cols in SCHEMA.items():
            f = open(os.path.join(OUT_CSV, f"{t}.csv"), "w", newline="")
            w = csv.writer(f)
            w.writerow([c for c, _ in cols])
            self.files[t], self.writers[t] = f, w

    def row(self, table, values):
        if len(values) != len(SCHEMA[table]):
            raise ValueError(f"{table}: expected {len(SCHEMA[table])} cols, got {len(values)}: {values}")
        for v in values:
            if v is None or v == "":
                raise ValueError(f"NULL/empty value in {table}: {values}")
        self.writers[table].writerow(values)
        self.counts[table] += 1

    def close(self):
        for f in self.files.values():
            f.close()


W = Writer()

# ---------------------------------------------------------------------------
# Global reference tables
# ---------------------------------------------------------------------------
SETTING = dict(fac8_24="Facility", fac8_2="Facility", fac12="Facility", day8="Facility", day8wk="Facility / Field",
               office="Office", field="Field (Patient Home)", visit="Field (Client Home)", session="Clinic / Home",
               salary="Office / Leadership")
for rid, r in ROLES.items():
    W.row("job_roles", [rid, r[R_TITLE], r[R_FAMILY], r[R_DEPT], yn(r[R_CLIN]), r[R_LIC],
                        "Exempt" if r[R_PAY] == "Salary" else "Non-Exempt", r[R_PAY], SETTING[r[R_PATTERN]]])

COURSES = [  # id, title, category, format, minutes, ceu, state mandated
    ("HIPAA", "HIPAA Privacy & Security", "Compliance", "Interactive", 45, 0.75, True),
    ("INFX", "Infection Control & Hand Hygiene", "Clinical Skills", "Video", 40, 0.75, True),
    ("ABUSE", "Abuse, Neglect & Exploitation Prevention", "Compliance", "Interactive", 50, 1.0, True),
    ("OSHA", "Workplace Safety & OSHA Essentials", "Safety", "Microlearning", 30, 0.5, False),
    ("EMERG", "Emergency Preparedness", "Safety", "Video", 35, 0.5, True),
    ("CODE", "Corporate Compliance & Code of Conduct", "Compliance", "Interactive", 30, 0.5, False),
    ("HARASS", "Harassment Prevention", "Compliance", "Interactive", 60, 1.0, True),
    ("FIRE", "Fire Safety & Evacuation", "Safety", "Video", 25, 0.0, True),
    ("DEMEN", "Dementia Care Fundamentals", "Clinical Skills", "Interactive", 90, 1.5, True),
    ("BBP", "Bloodborne Pathogens", "Clinical Skills", "Video", 30, 0.5, True),
    ("RIGHTS", "Resident & Patient Rights", "Compliance", "Microlearning", 25, 0.5, True),
    ("HANDLE", "Safe Patient Handling & Transfers", "Clinical Skills", "Instructor-Led", 120, 2.0, False),
    ("FALLS", "Fall Prevention Strategies", "Clinical Skills", "Microlearning", 30, 0.5, False),
    ("EOL", "Hospice Philosophy & End-of-Life Care", "Clinical Skills", "Interactive", 75, 1.25, False),
    ("OASIS", "OASIS-E Documentation Accuracy", "Clinical Skills", "Interactive", 90, 1.5, False),
    ("EVV", "Electronic Visit Verification (EVV)", "Compliance", "Microlearning", 20, 0.0, True),
    ("ABAETH", "BACB Ethics Code for Behavior Analysts", "Compliance", "Interactive", 60, 1.0, False),
    ("RBTSUP", "RBT Supervision & Session Documentation", "Clinical Skills", "Video", 45, 0.75, False),
    ("CULT", "Cultural Competency in Care", "Culture & Development", "Video", 40, 0.5, False),
    ("LEAD", "Leading Frontline Teams", "Culture & Development", "Instructor-Led", 180, 3.0, False),
    ("CUST", "Service Excellence & Family Communication", "Culture & Development", "Microlearning", 25, 0.0, False),
]
COURSE = {c[0]: c for c in COURSES}
for c in COURSES:
    W.row("courses", [c[0], c[1], c[2], c[3], c[4], c[5], yn(c[6])])

PERIODS = []  # (id, start, end, check)
p = 0
while True:
    s = P0 + dt.timedelta(days=14 * p)
    e = s + dt.timedelta(days=13)
    chk = e + dt.timedelta(days=6)
    if s > END:
        break
    num = sum(1 for x in PERIODS if x[3].year == chk.year) + 1
    pid = f"PP-{chk.year}-{num:02d}"
    PERIODS.append((pid, s, e, chk))
    W.row("pay_periods", [pid, f"{chk.year} #{num:02d} ({s:%b %d} - {e:%b %d})", ds(s), ds(e), ds(chk),
                          chk.year, num])
    p += 1


def period_index(d):
    return (d - P0).days // 14


# ---------------------------------------------------------------------------
# Employees (slot simulation) + ATS
# ---------------------------------------------------------------------------
class Emp:
    __slots__ = ("idx", "id", "num", "first", "last", "gender", "age_band", "loc", "tenant", "role", "etype",
                 "fte", "start_rate", "hire", "term", "term_type", "term_reason", "req_id", "source", "pref",
                 "mobile", "odp_date", "placeholder", "offer_date")


EMPS = []
REQS = []          # dicts
BY_LOCROLE = defaultdict(list)
emp_seq = defaultdict(int)


def market_rate(role, state, d):
    r = ROLES[role]
    return r[R_BASE] * STATES[state][2] * (1.035 ** ((d - START).days / 365.0))


def rate_at(e, d):
    years = max(0, (d - e.hire).days // 365)
    return e.start_rate * (1.03 ** years)


def new_emp(tenant, loc, role, hire, req_id, source):
    e = Emp()
    e.idx = len(EMPS)
    emp_seq[tenant["client_id"]] += 1
    n = emp_seq[tenant["client_id"]]
    e.id = f"{tenant['prefix']}-E{n:05d}"
    e.num = f"{tenant['prefix']}{100000 + n}"
    e.first, e.last, e.gender = person()
    e.age_band = wchoice([("18-24", .17), ("25-34", .30), ("35-44", .22), ("45-54", .17), ("55-64", .11), ("65+", .03)])
    e.loc, e.tenant, e.role = loc, tenant, role
    r = ROLES[role]
    if r[R_PAY] == "Salary":
        e.etype, e.fte = "Full-Time", 1.0
    else:
        x = rng.random()
        e.etype, e.fte = ("Full-Time", 1.0) if x < r[R_FT] else (("Part-Time", 0.6) if x < r[R_FT] + (1 - r[R_FT]) * 0.7 else ("PRN / Per Diem", 0.2))
    e.start_rate = market_rate(role, loc["state"], hire) * rng.uniform(0.92, 1.12)
    e.hire, e.term, e.term_type, e.term_reason = hire, None, NA, NA
    e.req_id, e.source = req_id, source
    pat = pattern_for(role, loc)
    if pat == "fac8_24":
        e.pref = wchoice([("Day", .45), ("Evening", .33), ("Night", .22)])
    elif pat == "fac8_2":
        e.pref = wchoice([("Day", .6), ("Evening", .4)])
    elif pat == "fac12":
        e.pref = wchoice([("Day", .6), ("Night", .4)])
    elif pat in ("visit", "field"):
        e.pref = "Field Day"
    elif pat == "session":
        e.pref = "Session Block"
    elif pat == "salary":
        e.pref = "Exempt (No Schedule)"
    else:
        e.pref = "Day"
    base_mobile = 0.55 if hire < START else 0.75 + 0.2 * progress(hire)
    e.mobile = rng.random() < base_mobile
    e.odp_date = None
    e.placeholder = False
    e.offer_date = None
    EMPS.append(e)
    BY_LOCROLE[(loc["id"], role)].append(e)
    return e


def pattern_for(role, loc):
    pat = ROLES[role][R_PATTERN]
    if loc["mix"] in HOME_BASED and pat in ("day8wk", "fac8_24", "fac12"):
        return "field"
    return pat


VOL_REASONS = [("Better Pay Elsewhere", .26), ("Schedule / Work-Life Balance", .22), ("Personal / Family Reasons", .15),
               ("Relocation", .09), ("Career Advancement", .12), ("Returned to School", .06),
               ("Burnout / Workload", .10)]
INV_REASONS = [("Attendance Policy Violation", .34), ("Job Abandonment", .24), ("Performance", .20),
               ("Policy Violation", .14), ("Lapsed License / Certification", .08)]


def sample_tenure_days(role, start_d, is_new_hire):
    turn = ROLES[role][R_TURN] * (1 - 0.12 * progress(start_d))
    if is_new_hire and turn > 0.35 and rng.random() < 0.22 * (1 - 0.35 * progress(start_d)):
        return rng.randint(5, 90)  # early turnover (first 90 days)
    return int(rng.expovariate(turn / 365.0)) + 1


def finish_employment(e, start_d, is_new_hire):
    term = start_d + dt.timedelta(days=sample_tenure_days(e.role, start_d, is_new_hire))
    if term > END:
        return None
    e.term = term
    if rng.random() < 0.78:
        e.term_type, e.term_reason = "Voluntary", wchoice(VOL_REASONS)
    else:
        e.term_type, e.term_reason = "Involuntary", wchoice(INV_REASONS)
    return term


req_seq = defaultdict(int)


def open_requisition(tenant, loc, role, opened, reason):
    req_seq[tenant["client_id"]] += 1
    rid = f"{tenant['prefix']}-REQ{req_seq[tenant['client_id']]:05d}"
    r = ROLES[role]
    ttf = r[R_TTF] * (1 - 0.22 * progress(opened)) * math.exp(rng.gauss(0, 0.35))
    ttf = max(5, int(ttf))
    urgent = r[R_COVER] in ("agency", "visit") or r[R_FAMILY] == "Leadership"
    req = dict(id=rid, tenant=tenant, loc=loc, role=role, opened=opened, reason=reason,
               priority="Urgent" if urgent and rng.random() < 0.6 else "Standard",
               fill=opened + dt.timedelta(days=ttf), status=None, emp=None,
               bonus=0.0)
    if role in ("CNA", "RN", "LPN", "HHA", "RBT", "RNCM", "CG"):
        if rng.random() < 0.45 - 0.2 * progress(opened):
            req["bonus"] = float(rng.choice([500, 750, 1000, 1500, 2000] if role in ("RN", "RNCM", "LPN") else [250, 500, 750, 1000]))
    REQS.append(req)
    return req


for tenant in TENANTS:
    W.row("clients", [tenant["client_id"], tenant["name"], tenant["industry"], tenant["segment"], tenant["hq"][0],
                      tenant["hq"][1], tenant["since"], tenant["tier"], tenant["client_id"]])
    for loc in tenant["locations"]:
        sn, region = STATES[loc["state"]][0], STATES[loc["state"]][1]
        W.row("locations", [loc["id"], loc["name"], loc["type"], loc["city"], loc["state"], sn, loc["zip"], region,
                            f"{loc['lat']:.6f}", f"{loc['lon']:.6f}", loc["cap"], loc["unit"], tenant["client_id"],
                            tenant["client_id"]])
        mix = MIXES[loc["mix"]]
        slots = []
        for role, share in mix.items():
            slots += [role] * max(1, round(loc["hc"] * share))
        # growth positions opened during the period
        growth_roles = [r for r, s in mix.items() if s >= 0.03]
        weights = [(r, mix[r]) for r in growth_roles]
        n_growth = round(loc["hc"] * tenant["growth"] * SPAN / 365.0)
        growth = [(wchoice(weights), START + dt.timedelta(days=rng.randint(0, SPAN))) for _ in range(n_growth)]

        def run_slot(role, first_emp_start, req):
            """Follow one position through time: employee -> vacancy (requisition) -> hire -> ..."""
            while True:
                if req is not None:
                    if req["fill"] > END:
                        req["status"] = "Open"
                        return
                    req["status"] = "Filled"
                    e = new_emp(tenant, loc, role, req["fill"], req["id"], NA)
                    req["emp"] = e
                    start_d, newhire = e.hire, True
                else:
                    tenure = min(int(rng.expovariate(ROLES[role][R_TURN] / 365.0)), 365 * 18)
                    e = new_emp(tenant, loc, role, first_emp_start - dt.timedelta(days=tenure + 1), NA, "Legacy (Pre-2024 Hire)")
                    start_d, newhire = START, False
                term = finish_employment(e, start_d, newhire)
                if term is None:
                    return
                opened = term - dt.timedelta(days=rng.randint(0, 12) if e.term_type == "Voluntary" else 0)
                opened = max(opened, START)
                req = open_requisition(tenant, loc, role, opened, "Replacement")

        for role in slots:
            run_slot(role, START, None)
        for role, opened in growth:
            req = open_requisition(tenant, loc, role, opened, "New Position (Growth)")
            if rng.random() < 0.06:
                req["status"] = "Cancelled"
                req["cancel"] = opened + dt.timedelta(days=rng.randint(10, 60))
                if req["cancel"] > END:
                    req["status"] = "Open"
                continue
            run_slot(role, None, req)

# Seed a few confirmed exclusion matches -> involuntary terminations
_inv = [e for e in EMPS if e.term_type == "Involuntary" and e.term and e.term > dt.date(2024, 3, 1)
        and ROLES[e.role][R_CLIN]]
EXCLUDED = set()
for _t in TENANTS:
    _ti = [e for e in _inv if e.tenant is _t]
    _old = [e for e in _ti if e.term < END - dt.timedelta(days=330)]
    _new = [e for e in _ti if END - dt.timedelta(days=330) <= e.term <= END - dt.timedelta(days=10)]
    for e in rng.sample(_old, min(1, len(_old))) + rng.sample(_new, min(2, len(_new))):
        e.term_reason = "Excluded Provider - OIG/State Match"
        EXCLUDED.add(e.idx)

# On-Demand Pay enrollment (launched 2024-04-01; adoption ramps up)
ODP_LAUNCH = dt.date(2024, 4, 1)
for e in EMPS:
    if ROLES[e.role][R_PAY] != "Hourly":
        continue
    if rng.random() < 0.46:
        earliest = max(e.hire + dt.timedelta(days=14), ODP_LAUNCH)
        d = earliest + dt.timedelta(days=int(rng.expovariate(1 / 120.0)))
        if d <= END and (e.term is None or d < e.term):
            e.odp_date = d

# Placeholder employees for open / agency shifts (one per location x role with coverage)
PLACE_OPEN, PLACE_AGENCY = {}, {}
for tenant in TENANTS:
    for loc in tenant["locations"]:
        for role in MIXES[loc["mix"]]:
            cov = ROLES[role][R_COVER]
            if not cov:
                continue
            for kind, store, label in (("OPEN", PLACE_OPEN, "Open Shift"), ("AGENCY", PLACE_AGENCY, "Agency Staff")):
                if kind == "AGENCY" and cov != "agency":
                    continue
                e = Emp()
                e.idx = len(EMPS)
                e.id = f"{loc['id']}-{kind}-{role}"
                e.num = NA
                e.first, e.last, e.gender = label, f"({ROLES[role][R_TITLE]})", NA
                e.age_band, e.loc, e.tenant, e.role = NA, loc, tenant, role
                e.etype, e.fte, e.start_rate = "System Placeholder", 0.0, 0.0
                e.hire, e.term, e.term_type, e.term_reason = None, None, NA, NA
                e.req_id, e.source, e.pref, e.mobile, e.odp_date = NA, NA, NA, False, None
                e.placeholder, e.offer_date = True, None
                EMPS.append(e)
                store[(loc["id"], role)] = e

REAL = [e for e in EMPS if not e.placeholder]

# ---- ATS: postings + applications ----
BOARDS = [("Indeed", .40), ("ZipRecruiter", .18), ("Facebook Jobs", .12), ("Glassdoor", .08),
          ("Google for Jobs", .10), ("LinkedIn", .06), ("Craigslist", .06)]
ORGANIC = [("Career Site", .40), ("Employee Referral", .30), ("Job Fair", .10), ("Walk-In", .08), ("Text-to-Apply", .12)]
cand_seq = 0
app_seq = 0
post_seq = 0
STAGES = ["Applied", "Screened", "Interviewed", "Offered", "Hired"]


def clip(d, lo, hi):
    return max(lo, min(hi, d))


for req in REQS:
    tenant, role = req["tenant"], req["role"]
    r = ROLES[role]
    opened = req["opened"]
    status = req["status"]
    e = req["emp"]
    if status == "Filled":
        end_d = e.hire
    elif status == "Cancelled":
        end_d = req["cancel"]
    else:
        end_d = END
    # postings
    boards = ["Indeed"] + [b for b in (wchoice(BOARDS[1:]) for _ in range(rng.randint(1, 3)))]
    boards = list(dict.fromkeys(boards))
    if r[R_LIC] in ("RN", "BCBA", "PT", "OT", "SLP", "NHA") and "LinkedIn" not in boards:
        boards.append("LinkedIn")
    spons = {}
    for b in boards:
        p_sp = (0.55 if b in ("Indeed", "ZipRecruiter") else 0.18) * (1.3 if req["priority"] == "Urgent" else 1.0)
        spons[b] = rng.random() < p_sp
    any_sp = any(spons.values())
    n_apps = max(2, int(r[R_APPS] * math.exp(rng.gauss(0, 0.35)) * (1.25 if any_sp else 1.0)
                        * min(1.0, ((end_d - opened).days + 3) / max(10, r[R_TTF]))))
    app_counts = defaultdict(int)
    hired_slot = rng.randrange(n_apps) if status == "Filled" else -1
    for i in range(n_apps):
        app_seq += 1
        cand_seq += 1
        aid = f"APP{app_seq:07d}"
        cid = f"CAND{cand_seq:07d}"
        if i == hired_slot:
            fn, ln = e.first, e.last
        else:
            fn, ln, _ = person()
        if rng.random() < 0.74:
            src = wchoice([(b, (2.2 if spons[b] else 1.0) * dict(BOARDS)[b]) for b in boards])
            app_counts[src] += 1
        else:
            src = wchoice(ORGANIC)
        device = "Mobile" if rng.random() < 0.68 + 0.1 * progress(opened) else "Desktop"
        contact_h = max(0.2, rng.expovariate(1 / (30 * (1 - 0.6 * progress(opened)))))
        scr = intv = off = hire = NA_DATE
        flags = [0, 0, 0, 0]
        dth = 0
        if i == hired_slot:
            hire_d = e.hire
            off_d = hire_d - dt.timedelta(days=rng.randint(5, 14))
            int_d = off_d - dt.timedelta(days=rng.randint(1, 5))
            scr_d = int_d - dt.timedelta(days=rng.randint(1, 4))
            app_d = scr_d - dt.timedelta(days=rng.randint(0, 3))
            app_d = clip(app_d, opened, hire_d)
            scr_d, int_d, off_d = clip(scr_d, app_d, hire_d), clip(int_d, app_d, hire_d), clip(off_d, app_d, hire_d)
            e.offer_date = off_d
            e.source = src
            scr, intv, off, hire = ds(scr_d), ds(int_d), ds(off_d), ds(hire_d)
            flags = [1, 1, 1, 1]
            stage, st = "Hired", "Hired"
            dth = (hire_d - app_d).days
        else:
            span = max(1, (end_d - opened).days)
            app_d = opened + dt.timedelta(days=min(span, int(rng.random() ** 1.3 * span)))
            stage_n = 0
            if rng.random() < 0.55:
                stage_n = 1
                if rng.random() < 0.45:
                    stage_n = 2
                    if rng.random() < 0.22:
                        stage_n = 3
            d = app_d
            dates = []
            for _ in range(stage_n):
                d = d + dt.timedelta(days=rng.randint(1, 5))
                dates.append(d)
            if dates and dates[-1] > END:
                stage_n = sum(1 for x in dates if x <= END)
                dates = dates[:stage_n]
            stage = STAGES[stage_n]
            if stage_n >= 1:
                scr, flags[0] = ds(dates[0]), 1
            if stage_n >= 2:
                intv, flags[1] = ds(dates[1]), 1
            if stage_n >= 3:
                off, flags[2] = ds(dates[2]), 1
            if status == "Open" and (END - (dates[-1] if dates else app_d)).days < 21:
                st = "In Review"
            elif stage_n == 0:
                st = wchoice([("Rejected - Not Qualified", .40), ("No Response from Candidate", .42),
                              ("Withdrawn", .08), ("Not Selected - Position Filled", .10)])
                if status == "Cancelled":
                    st = "Requisition Cancelled"
            elif stage_n == 1:
                st = wchoice([("No-Show to Interview", .35), ("Rejected After Screen", .35), ("Withdrawn", .30)])
            elif stage_n == 2:
                st = wchoice([("Not Selected", .75), ("Withdrawn", .25)])
            else:
                st = wchoice([("Offer Declined", .80), ("Failed Background Check", .20)])
        W.row("applications", [aid, req["id"], cid, f"{fn} {ln}", ds(app_d), src, device, stage,
                               STAGES.index(stage) + 1, st, scr, intv, off, hire, r2(contact_h), dth,
                               flags[0], flags[1], flags[2], flags[3], tenant["client_id"]])
    for b in boards:
        post_seq += 1
        p_end = end_d if status != "Open" else END
        days_active = max(1, (p_end - opened).days)
        applies = app_counts[b]
        sp = spons[b]
        spend = r2(days_active * rng.uniform(6, 22)) if sp else 0.0
        impressions = int(max(applies, 1) * rng.uniform(60, 140) * (2.2 if sp else 1.0))
        clicks = int(max(applies, 1) * rng.uniform(4, 9))
        W.row("job_postings", [f"{tenant['prefix']}-POST{post_seq:06d}", req["id"], b, ds(opened), ds(p_end),
                               yn(sp), spend, impressions, clicks, applies, tenant["client_id"]])
    filled = ds(e.hire) if status == "Filled" else NA_DATE
    closed = ds(e.hire) if status == "Filled" else (ds(req["cancel"]) if status == "Cancelled" else NA_DATE)
    days_open = ((e.hire if status == "Filled" else req.get("cancel", END)) - opened).days
    W.row("requisitions", [req["id"], req["loc"]["id"], role, req["reason"], req["priority"], ds(opened), filled,
                           closed, status, 1, days_open, days_open if status == "Filled" else 0,
                           req["bonus"], tenant["client_id"]])

# ---- employees CSV ----
for e in EMPS:
    if e.placeholder:
        W.row("employees", [e.id, e.num, e.first, e.last, f"{e.first} {e.last}", e.gender, e.age_band, e.loc["id"],
                            e.role, e.etype, 0.0, NA, 0.0, 0.0, NA_DATE, NA_DATE, "System Placeholder", NA, NA, NA,
                            NA, NA, NA, "No", "No", NA_DATE, "Yes", e.tenant["client_id"]])
        continue
    r = ROLES[e.role]
    ref = e.term or END
    if r[R_PAY] == "Salary":
        hourly, salary = r2(rate_at(e, ref) / 2080), r2(rate_at(e, ref))
    else:
        hourly, salary = r2(rate_at(e, ref)), r2(rate_at(e, ref) * 2080 * e.fte)
    status = "Terminated" if e.term else ("On Leave" if rng.random() < 0.025 else "Active")
    rehire = NA if not e.term else yn(rng.random() < (0.85 if e.term_type == "Voluntary" else 0.15))
    W.row("employees", [e.id, e.num, e.first, e.last, f"{e.first} {e.last}", e.gender, e.age_band, e.loc["id"],
                        e.role, e.etype, e.fte, r[R_PAY], hourly, salary, ds(e.hire),
                        ds(e.term) if e.term else NA_DATE, status, e.term_type, e.term_reason, rehire, e.source,
                        e.req_id, e.pref, yn(e.mobile), yn(e.odp_date is not None),
                        ds(e.odp_date) if e.odp_date else NA_DATE, "No", e.tenant["client_id"]])


def employed(e, d):
    return e.hire <= d and (e.term is None or d <= e.term)


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------
ob_seq = 0
for e in REAL:
    if e.hire < START or e.offer_date is None:
        continue
    r = ROLES[e.role]
    pat = pattern_for(e.role, e.loc)
    tasks = [("Personal Information & Emergency Contacts", "Personal Info", "New Hire", 0),
             ("Federal W-4", "Tax & Payroll Forms", "New Hire", 0),
             ("Form I-9 Section 1", "Employment Eligibility", "New Hire", 0),
             ("Form I-9 Section 2 Verification", "Employment Eligibility", "HR Admin", 3),
             ("Direct Deposit / Pay Card Setup", "Tax & Payroll Forms", "New Hire", 0),
             ("Employee Handbook Acknowledgment", "Policies", "New Hire", 0),
             ("Criminal Background Check", "Screening", "Background Vendor", 0),
             ("Viventium Mobile App Activation", "Systems Access", "New Hire", 0)]
    if STATES[e.loc["state"]][3] > 0:
        tasks.append(("State Tax Withholding", "Tax & Payroll Forms", "New Hire", 0))
    if e.etype == "Full-Time":
        tasks.append(("Benefits Enrollment", "Benefits", "New Hire", 30))
    if r[R_LIC] != NA:
        tasks.append(("License / Certification Verification", "Credentials", "HR Admin", 0))
    if r[R_CLIN]:
        tasks += [("TB Test / Health Screening", "Health Screening", "New Hire", 0),
                  ("Drug Screen", "Screening", "Background Vendor", 0),
                  ("Hepatitis B Vaccination Record", "Health Screening", "New Hire", 0),
                  ("Fingerprinting", "Screening", "Background Vendor", 0)]
    if r[R_FAMILY] in ("Nursing", "Direct Care"):
        tasks.append(("CPR / BLS Certification Upload", "Credentials", "New Hire", 0))
    if pat in ("visit", "field"):
        tasks += [("Driver's License & Auto Insurance", "Credentials", "New Hire", 0),
                  ("EVV Mobile Check-In Training", "Systems Access", "New Hire", 7)]
    if r[R_COVER] in ("agency", "visit", "session"):
        tasks.append(("Skills Competency Evaluation", "Training", "Clinical Supervisor", 7))
    assigned = e.offer_date
    pr = progress(assigned)
    for name, cat, party, due_after in tasks:
        ob_seq += 1
        due = e.hire + dt.timedelta(days=due_after) if due_after else e.hire - dt.timedelta(days=1)
        if due < assigned:
            due = assigned
        if party == "Background Vendor":
            lag = rng.randint(1, 8) if name != "Fingerprinting" else rng.randint(2, 12)
        else:
            lag = int(rng.expovariate(1 / (3.5 * (1 - 0.45 * pr))))
        if rng.random() < 0.07 * (1 - 0.5 * pr):
            lag += rng.randint(3, 25)
        comp = assigned + dt.timedelta(days=lag)
        if e.term and comp > e.term:
            comp = None
        if comp is not None and comp > END:
            comp = None
        if comp:
            status = "Completed"
            via = NA if party in ("Background Vendor", "HR Admin", "Clinical Supervisor") else \
                ("Mobile App" if rng.random() < 0.55 + 0.3 * pr else "Desktop")
            if party in ("HR Admin", "Clinical Supervisor"):
                via = "In Person"
            elif party == "Background Vendor":
                via = "Vendor Integration"
        else:
            status = "Overdue" if due < END and not e.term else ("Cancelled - Terminated" if e.term else "Pending")
            via = NA
        W.row("onboarding_tasks", [f"OBT{ob_seq:07d}", e.id, name, cat, party, ds(assigned), ds(due),
                                   ds(comp) if comp else NA_DATE, status, via, (comp - assigned).days if comp else 0,
                                   int(comp is not None), int(status == "Overdue" or (comp is not None and comp > due)),
                                   int(comp is not None and comp <= due), e.tenant["client_id"]])

# ---------------------------------------------------------------------------
# Scheduling + Time & Attendance
# ---------------------------------------------------------------------------
shift_seq = 0
WORKED = defaultdict(list)   # emp idx -> [(date, shift_id, start_min, sched_hours, shift_type)]


def new_shift_id():
    global shift_seq
    shift_seq += 1
    return f"SH{shift_seq:08d}"


def shift_times(pat, pref, d, slot_start=None):
    """-> (shift_type, start_minute, scheduled_hours, visit_count)"""
    if pat == "fac8_24" or pat == "fac8_2":
        opts = ["Day", "Evening", "Night"] if pat == "fac8_24" else ["Day", "Evening"]
        st = pref if rng.random() < 0.85 else rng.choice(opts)
        return st, {"Day": 7 * 60, "Evening": 15 * 60, "Night": 23 * 60}[st], 8.0, 0
    if pat == "fac12":
        st = pref if rng.random() < 0.9 else rng.choice(["Day", "Night"])
        return st, 7 * 60 if st == "Day" else 19 * 60, 12.0, 0
    if pat == "day8":
        return "Day", 7 * 60, 8.0, 0
    if pat == "day8wk":
        return "Day", 8 * 60, 8.0, 0
    if pat == "office":
        return "Day", 8 * 60 + 30, 8.0, 0
    if pat == "field":
        return "Field Day", 8 * 60, 8.0, rng.choice([4, 4, 5, 5, 5, 6])
    if pat == "visit":
        return "Client Visit", slot_start[0], slot_start[1], 1
    if pat == "session":
        return "Therapy Session Block", slot_start[0], slot_start[1], 2 if slot_start[1] >= 4 else 1
    raise ValueError(pat)


def calloff_prob(d, role):
    p = 0.032
    if d.month in (1, 2):
        p *= 1.45
    elif d.month == 12:
        p *= 1.25
    if d.weekday() >= 4:
        p *= 1.3
    if ROLES[role][R_FAMILY] == "Direct Care":
        p *= 1.25
    return p * (1 - 0.18 * progress(d))


def find_coworker(e, d):
    pool = BY_LOCROLE[(e.loc["id"], e.role)]
    for _ in range(8):
        c = rng.choice(pool)
        if c is not e and employed(c, d) and c.etype != "System Placeholder":
            return c
    return None


def write_shift(sid, e, d, stype, start_min, hours, visits, status, fill, outcome, covers, lead, agency_cost):
    W.row("shifts", [sid, e.id, ds(d), stype, ts(d, start_min), ts(d, start_min + hours * 60), hours, visits,
                     status, fill, outcome, covers, yn(d.weekday() >= 5), lead, r2(agency_cost),
                     e.tenant["client_id"]])
    if status == "Worked" and not e.placeholder:
        WORKED[e.idx].append((d, sid, start_min, hours, stype))


for e in REAL:
    r = ROLES[e.role]
    pat = pattern_for(e.role, e.loc)
    if pat == "salary":
        continue
    first = max(e.hire, START)
    last = min(e.term or SCHEDULE_UNTIL, SCHEDULE_UNTIL)
    if first > last:
        continue
    per_week = SHIFTS_PER_WEEK[pat]
    wk = P0 + dt.timedelta(days=7 * ((first - P0).days // 7))
    while wk <= last:
        days = [wk + dt.timedelta(days=i) for i in range(7)]
        days = [d for d in days if first <= d <= last and (pat not in WEEKDAY_ONLY or d.weekday() < 5)]
        if not days:
            wk += dt.timedelta(days=7)
            continue
        if e.etype == "Full-Time":
            n = per_week
        elif e.etype == "Part-Time":
            n = int(per_week * 0.55 + rng.random())
        else:
            n = poisson(per_week * 0.22)
        if rng.random() < 0.035 and e.etype == "Full-Time":   # PTO week
            n = max(0, n - rng.randint(2, n))
        n = int(round(n * len(days) / (5 if pat in WEEKDAY_ONLY else 7)))
        # extra (overtime) shifts for full-timers in short-staffed roles - trending down after go-live
        if e.etype == "Full-Time" and r[R_COVER] in ("agency", "visit", "internal", "session"):
            p_extra = (0.38 if r[R_COVER] in ("agency", "visit") else 0.15) * (1 - 0.4 * progress(wk))
            if rng.random() < p_extra:
                n += 1
        workdays = sorted(rng.sample(days, min(n, len(days))))
        chosen = []
        for d in workdays:
            if pat == "visit":   # a care day = one or more client visits (live-in / hourly / split)
                plan = rng.choice([(4.0, 4.0), (3.0, 5.0), (2.0, 3.0, 3.0), (8.0,), (8.0,), (4.0, 4.0, 2.0),
                                   (12.0,), (5.0, 3.0), (6.0, 2.0)])
                cur = rng.choice([7, 8, 8, 9]) * 60
            elif pat == "session":
                plan = rng.choice([(3.5, 4.0), (4.0, 4.0), (3.0, 3.5), (4.5, 3.5), (4.0,), (3.0, 3.0, 2.0)])
                cur = 8 * 60 + 30
            else:
                chosen.append((d, None))
                continue
            for hrs in plan:
                chosen.append((d, (cur, hrs)))
                cur += int(hrs * 60) + rng.choice([30, 45, 60])
        for d, slot in chosen:
            stype, smin, hrs, visits = shift_times(pat, e.pref, d, slot)
            sid = new_shift_id()
            lead = max(1, int(rng.gauss(10 + 8 * progress(d), 3)))
            if d > END:
                write_shift(sid, e, d, stype, smin, hrs, visits, "Scheduled", "Assigned", NA, NA, lead, 0)
                continue
            x = rng.random()
            p_co = calloff_prob(d, e.role)
            if x < p_co or x < p_co + 0.006 * (1 - 0.4 * progress(d)):
                status = "Called Off" if x < p_co else "No Show"
                cov = r[R_COVER]
                pr = progress(d)
                if cov is None:
                    write_shift(sid, e, d, stype, smin, hrs, visits, status, "Assigned", "Not Required", NA, lead, 0)
                    continue
                if cov == "agency":
                    outcome = wchoice([("Covered - Internal", 0.42 + 0.22 * pr), ("Covered - Agency", 0.40 - 0.24 * pr),
                                       ("Not Covered", 0.18 + 0.02 * pr)])
                elif cov == "internal":
                    outcome = wchoice([("Covered - Internal", 0.55 + 0.1 * pr), ("Not Covered", 0.45 - 0.1 * pr)])
                elif cov == "visit":
                    outcome = wchoice([("Covered - Internal", 0.70 + 0.14 * pr), ("Not Covered", 0.30 - 0.14 * pr)])
                elif cov == "field":
                    outcome = wchoice([("Covered - Internal", 0.50 + 0.1 * pr), ("Not Covered", 0.50 - 0.1 * pr)])
                else:
                    outcome = wchoice([("Covered - Internal", 0.35 + 0.15 * pr), ("Not Covered", 0.65 - 0.15 * pr)])
                cw = find_coworker(e, d) if outcome == "Covered - Internal" else None
                if outcome == "Covered - Internal" and cw is None:
                    outcome = "Not Covered"
                write_shift(sid, e, d, stype, smin, hrs, visits, status, "Assigned", outcome, NA, lead, 0)
                csid = new_shift_id()
                if outcome == "Covered - Internal":
                    fill = "Picked Up via Mobile App" if rng.random() < 0.45 + 0.4 * pr else "Manager Assigned"
                    write_shift(csid, cw, d, stype, smin, hrs, visits, "Worked", fill, NA, sid, 0, 0)
                elif outcome == "Covered - Agency":
                    ag = PLACE_AGENCY[(e.loc["id"], e.role)]
                    cost = hrs * rate_at(e, d) * rng.uniform(1.7, 2.1)
                    write_shift(csid, ag, d, stype, smin, hrs, visits, "Worked", "Agency", NA, sid, 0, cost)
                else:
                    op = PLACE_OPEN[(e.loc["id"], e.role)]
                    write_shift(csid, op, d, stype, smin, hrs, visits,
                                "Missed Visit" if cov in ("visit", "field", "session") else "Unfilled",
                                "Open - Not Filled", NA, sid, 0, 0)
            else:
                fill = "Assigned" if rng.random() > 0.03 else "Shift Swap"
                write_shift(sid, e, d, stype, smin, hrs, visits, "Worked", fill, NA, NA, lead, 0)
        wk += dt.timedelta(days=7)

# Future open shifts posted to the mobile app
for tenant in TENANTS:
    for loc in tenant["locations"]:
        keys = [k for k in PLACE_OPEN if k[0] == loc["id"]]
        for i in range(1, 15):
            d = END + dt.timedelta(days=i)
            for _ in range(poisson(loc["hc"] * 0.012)):
                op = PLACE_OPEN[rng.choice(keys)]
                pat = pattern_for(op.role, loc)
                pref = {"fac8_24": rng.choice(["Day", "Evening", "Night"]), "fac8_2": rng.choice(["Day", "Evening"]),
                        "fac12": rng.choice(["Day", "Night"])}.get(pat, "Day")
                stype, smin, hrs, visits = shift_times(pat, pref, d, (rng.choice([8, 9, 13]) * 60, rng.choice([3.0, 4.0, 8.0])))
                write_shift(new_shift_id(), op, d, stype, smin, hrs, visits, "Open - Posted", "Posted to Mobile App",
                            NA, NA, i, 0)

# Timecards (+ accumulators for payroll and ACA)
PAY_ACC = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])   # (emp, period) -> reg h, ot h, diff pay, field hours
ACA_HOURS = defaultdict(float)                        # (emp, (y, m)) -> hours
tc_seq = 0
for e in REAL:
    rows = WORKED.get(e.idx)
    if not rows:
        continue
    rows.sort(key=lambda x: (x[0], x[2]))
    pat = pattern_for(e.role, e.loc)
    week_hours = defaultdict(float)
    for d, sid, smin, hrs, stype in rows:
        pr = progress(d)
        late = 0
        if rng.random() < 0.085 * (1 - 0.3 * pr):
            late = rng.randint(8, 45)
            in_off = late
        else:
            in_off = int(rng.gauss(-6, 4))
        early = rng.random() < 0.03
        out_off = -rng.randint(20, 120) if early else int(rng.gauss(4, 6))
        missed = rng.random() < 0.035 * (1 - 0.5 * pr)
        if pat in ("visit", "field", "session"):
            method = wchoice([("Mobile App (GPS)", 0.80 + 0.12 * pr), ("Telephony (IVR)", 0.20 - 0.12 * pr)]) \
                if pat != "session" else wchoice([("Mobile App (GPS)", .9), ("Web Clock", .1)])
        elif pat == "office":
            method = wchoice([("Web Clock", .6), ("Mobile App (GPS)", .25 + .15 * pr), ("Kiosk / Biometric", .15)])
        else:
            method = wchoice([("Kiosk / Biometric", 0.62 - 0.25 * pr), ("Mobile App (GPS)", 0.30 + 0.25 * pr),
                              ("Web Clock", 0.08)])
        geo = NA if not method.startswith("Mobile") else ("Yes" if rng.random() < 0.965 else "No")
        cin = smin + in_off
        cout = smin + hrs * 60 + out_off
        brk = 30 if hrs >= 6 else 0
        worked = max(0.5, (cout - cin - brk) / 60.0)
        if missed:  # manager fixes to schedule
            cout = smin + hrs * 60
            worked = max(0.5, (cout - cin - brk) / 60.0)
        widx = (d - P0).days // 7
        before = week_hours[widx]
        week_hours[widx] += worked
        ot = max(0.0, week_hours[widx] - max(40.0, before))
        reg = worked - ot
        approval = "Approved" if d <= END - dt.timedelta(days=7) else ("Pending Approval" if rng.random() < .7 else "Approved")
        tc_seq += 1
        W.row("timecards", [f"TC{tc_seq:08d}", sid, e.id, ds(d), ts(d, cin), ts(d, cout), hrs, r2(worked), r2(reg),
                            r2(ot), brk, late, int(late > 0), int(early), int(missed), method, geo,
                            yn(missed or rng.random() < 0.02), approval, e.tenant["client_id"]])
        acc = PAY_ACC[(e.idx, period_index(d))]
        acc[0] += reg
        acc[1] += ot
        diff = PAY_DIFF.get(stype, 0.0) + (WEEKEND_DIFF if d.weekday() >= 5 else 0.0)
        acc[2] += diff * worked
        acc[3] += worked
        ACA_HOURS[(e.idx, (d.year, d.month))] += worked

# ---------------------------------------------------------------------------
# Benefits Administration
# ---------------------------------------------------------------------------
PLAN_DEFS = [  # key, name, type, carrier, network, total monthly EE-only (2024), employee share
    ("MED-HMO", "Medical HMO", "Medical", "Summit Health Plan", "HMO", 640.0, 0.22),
    ("MED-PPO", "Medical PPO", "Medical", "Summit Health Plan", "PPO", 790.0, 0.30),
    ("MED-HDHP", "Medical HDHP + HSA", "Medical", "Summit Health Plan", "HDHP", 515.0, 0.12),
    ("DEN", "Dental PPO", "Dental", "BrightSmile Dental", "PPO", 46.0, 0.50),
    ("VIS", "Vision", "Vision", "ClearView Vision", "Network", 12.0, 1.00),
    ("LIFE", "Basic Life & AD&D (1x Salary)", "Life & AD&D", "Guardian Mutual", "N/A", 9.0, 0.0),
    ("401K", "401(k) Retirement Plan", "Retirement", "Horizon Retirement Services", "N/A", 0.0, 0.0),
]
TIERS = [("Employee Only", 1.0, 1, .52), ("Employee + Spouse", 2.1, 2, .14), ("Employee + Child(ren)", 1.85, 3, .19),
         ("Family", 2.9, 4, .15)]
PLAN_TYPES = ["Medical", "Dental", "Vision", "Life & AD&D", "Retirement"]
for tenant in TENANTS:
    for key, name, ptype, carrier, net, _, _ in PLAN_DEFS:
        W.row("benefit_plans", [f"{tenant['prefix']}-{key}", name, ptype, carrier, net, tenant["client_id"]])
    for ptype in PLAN_TYPES:
        W.row("benefit_plans", [f"{tenant['prefix']}-WAIVED-{ptype[:3].upper()}", f"Waived - {ptype}", ptype,
                                NA, NA, tenant["client_id"]])
        W.row("benefit_plans", [f"{tenant['prefix']}-PENDING-{ptype[:3].upper()}", f"Election Pending - {ptype}",
                                ptype, NA, NA, tenant["client_id"]])

BEN = defaultdict(list)          # emp idx -> [(eff, end, ee_monthly, er_monthly, ptype, enrolled, pct)]
MED_ENROLLED = defaultdict(list)  # emp idx -> [(eff, end)]
enr_seq = 0


def month_end(d):
    nxt = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return nxt - dt.timedelta(days=1)


def eligibility_date(e):
    x = e.hire + dt.timedelta(days=60)
    return dt.date(x.year + (x.month == 12), x.month % 12 + 1, 1)


OE_2027_CUTOFF = END
for e in REAL:
    if e.etype != "Full-Time":
        continue
    elig = eligibility_date(e)
    prefs = dict(med=rng.random() < 0.72, plan=wchoice([("MED-HMO", .45), ("MED-PPO", .30), ("MED-HDHP", .25)]),
                 tier=wchoice([(t, t[3]) for t in TIERS]), den=rng.random() < 0.66, vis=rng.random() < 0.55,
                 k401=rng.random() < 0.58, pct=rng.choice([3, 4, 5, 6, 6, 8, 10]),
                 via=rng.random())
    for year in (2024, 2025, 2026, 2027):
        ys, ye = dt.date(year, 1, 1), dt.date(year, 12, 31)
        if elig > ye or (e.term and e.term < ys) or (year == 2027 and e.term):
            continue
        if elig <= ys:
            event, eff = "Open Enrollment", ys
            elect = dt.date(year - 1, 11, 1) + dt.timedelta(days=rng.randint(0, 28))
        else:
            event, eff = "New Hire", elig
            elect = elig - dt.timedelta(days=rng.randint(5, 30))
        end = min(ye, month_end(e.term)) if e.term else ye
        pending = False
        if year == 2027:
            elect = dt.date(2026, 11, 1) + dt.timedelta(days=rng.randint(0, 29))
            if elect > OE_2027_CUTOFF:
                pending = True
        if rng.random() < 0.15 and year > 2024:   # re-shop at open enrollment
            prefs["plan"] = wchoice([("MED-HMO", .45), ("MED-PPO", .30), ("MED-HDHP", .25)])
        infl = 1.07 ** (year - 2024)
        pr = progress(min(elect, END))
        via = "Mobile App" if prefs["via"] < 0.35 + 0.35 * pr else ("Desktop" if prefs["via"] < 0.9 else "HR Assisted")
        annual = rate_at(e, eff) * (1 if ROLES[e.role][R_PAY] == "Salary" else 2080)
        for ptype in PLAN_TYPES:
            enr_seq += 1
            tier, mult, lives = prefs["tier"][0], prefs["tier"][1], prefs["tier"][2]
            pct = 0.0
            if pending:
                plan, status, enrolled, ee, er, tier, lives = f"{e.tenant['prefix']}-PENDING-{ptype[:3].upper()}", \
                    "Not Yet Elected", 0, 0.0, 0.0, NA, 0
                elect_s = NA_DATE
            else:
                elect_s = ds(elect)
                take = {"Medical": prefs["med"], "Dental": prefs["den"], "Vision": prefs["vis"],
                        "Life & AD&D": True, "Retirement": prefs["k401"]}[ptype]
                if not take:
                    plan, status, enrolled, ee, er, tier, lives = f"{e.tenant['prefix']}-WAIVED-{ptype[:3].upper()}", \
                        "Waived", 0, 0.0, 0.0, NA, 0
                else:
                    key = {"Medical": prefs["plan"], "Dental": "DEN", "Vision": "VIS", "Life & AD&D": "LIFE",
                           "Retirement": "401K"}[ptype]
                    pdef = next(p for p in PLAN_DEFS if p[0] == key)
                    plan = f"{e.tenant['prefix']}-{key}"
                    status = "Submitted" if year == 2027 else "Enrolled"
                    enrolled = 1
                    if ptype == "Retirement":
                        pct = float(prefs["pct"])
                        ee = annual / 12 * pct / 100
                        er = annual / 12 * min(pct, 6) / 100 * 0.5
                        tier, lives = "Employee Only", 1
                    elif ptype == "Life & AD&D":
                        ee, er, tier, lives = 0.0, pdef[5] * infl * max(1, annual / 50000), "Employee Only", 1
                    else:
                        total = pdef[5] * mult * infl
                        ee, er = total * pdef[6], total * (1 - pdef[6])
            W.row("benefit_enrollments", [f"ENR{enr_seq:07d}", e.id, plan, year, tier, event, elect_s, ds(eff),
                                          ds(end), status, via if not pending else NA, lives, pct, r2(ee), r2(er),
                                          enrolled, e.tenant["client_id"]])
            if enrolled and year <= 2026:
                BEN[e.idx].append((eff, end, ee, er))
                if ptype == "Medical":
                    MED_ENROLLED[e.idx].append((eff, end))

# ---------------------------------------------------------------------------
# Payroll + On-Demand Pay
# ---------------------------------------------------------------------------
pay_seq = 0
odp_seq = 0
ODP_BY_PERIOD = {}
REQ_BONUS = {q["id"]: q["bonus"] for q in REQS if q["bonus"]}
WAGE_PARITY = {2024: 4.50, 2025: 4.70, 2026: 4.90}
for e in REAL:
    r = ROLES[e.role]
    salaried = r[R_PAY] == "Salary"
    state = e.loc["state"]
    parity = e.tenant["client_id"] == "hearthside" and state == "NY" and e.role in ("HHA", "PCA")
    method = wchoice([("Direct Deposit", .86), ("Pay Card", .10), ("Paper Check", .04)])
    for pi, (pid, ps, pe, chk) in enumerate(PERIODS):
        if pe < e.hire or (e.term and ps > e.term) or pe < START:
            continue
        rate = rate_at(e, pe)
        reg_h = ot_h = diff = 0.0
        pto_h = 0.0
        if salaried:
            days = (min(pe, e.term or pe) - max(ps, e.hire, START)).days + 1
            frac = days / 14.0
            reg_pay = rate / 26 * frac
            reg_h = 80 * frac
            ot_pay = blended = diff_pay = parity_pay = 0.0
        else:
            reg_h, ot_h, diff_pay, _ = PAY_ACC.get((e.idx, period_index(ps)), (0.0, 0.0, 0.0, 0.0))
            if reg_h + ot_h == 0 and (e.term is None or e.term >= pe):
                if e.etype == "PRN / Per Diem":
                    continue
            if e.etype == "Full-Time" and rng.random() < 0.22:
                pto_h = float(rng.choice([8, 8, 16, 24]))
            reg_pay = reg_h * rate
            ot_pay = ot_h * rate * 1.5
            tot_h = reg_h + ot_h
            blended = 0.5 * (diff_pay / tot_h) * ot_h if tot_h and ot_h else 0.0   # FLSA regular-rate true-up
            parity_pay = (reg_h + ot_h) * WAGE_PARITY[chk.year] if parity else 0.0
        pto_pay = pto_h * rate if not salaried else 0.0
        retro = 0.0
        anniv = dt.date(ps.year, e.hire.month, min(e.hire.day, 28))
        if e.hire.year < ps.year and ps <= anniv <= pe and rng.random() < 0.25:
            retro = (reg_h + ot_h) * rate * 0.03 * rng.choice([1, 2])
        bonus = 0.0
        sob = REQ_BONUS.get(e.req_id, 0.0)
        if sob and ps <= e.hire + dt.timedelta(days=90) <= pe:
            bonus += sob                                       # sign-on bonus paid after 90 days
        if rng.random() < 0.012:
            bonus += float(rng.choice([100, 150, 250, 500]))   # referral / recognition bonus
        gross = reg_pay + ot_pay + blended + diff_pay + parity_pay + retro + bonus + pto_pay
        if gross <= 0:
            continue
        # benefits / 401k deductions active on check date
        ee_m = er_m = 0.0
        for eff, end, ee, er in BEN.get(e.idx, ()):
            if eff <= chk <= end:
                ee_m += ee
                er_m += er
        pretax = min(ee_m * 12 / 26, gross * 0.4)   # remainder taken in arrears
        taxable = max(0.0, gross - pretax)
        fed = 0.055 + min(0.11, taxable / 25000)
        ee_tax = taxable * (0.0765 + fed + STATES[state][3])
        er_tax = gross * 0.0765 + (gross * 0.027 if period_index(ps) % 26 < 6 else 0.0)
        # On-Demand Pay draws during this period
        odp_total = 0.0
        if e.odp_date and e.odp_date <= pe and not salaried:
            avail = 0.5 * max(0.0, gross - pretax - ee_tax)
            for _ in range(poisson(1.15 + 0.4 * progress(ps))):
                if avail < 20:
                    break
                req_d = ps + dt.timedelta(days=rng.randint(3, 13))
                if req_d < e.odp_date or req_d > END:
                    continue
                amt = r2(min(avail, rng.choice([40, 60, 75, 100, 120, 150, 200, 250, 300]) * rng.uniform(.8, 1.2)))
                instant = rng.random() < 0.62
                odp_seq += 1
                declined = rng.random() < 0.03
                W.row("odp_transactions", [f"ODP{odp_seq:07d}", e.id, pid, ds(req_d),
                                           ts(req_d, rng.randint(6 * 60, 23 * 60)), amt,
                                           2.99 if instant and not declined else 0.0,
                                           "Instant (Debit Card)" if instant else "Next-Day (ACH)",
                                           "Declined" if declined else "Completed",
                                           "Exceeds Available Earned Balance" if declined else NA,
                                           e.tenant["client_id"]])
                if not declined:
                    odp_total += amt
                    avail -= amt
        if chk > END:      # open pay period: draws already happened, the paycheck is not processed yet
            continue
        net = gross - pretax - ee_tax - odp_total
        pay_seq += 1
        W.row("payroll", [f"PAY{pay_seq:08d}", pid, e.id, ds(chk), method, r2(reg_h), r2(ot_h), r2(pto_h),
                          r2(reg_pay), r2(ot_pay), r2(blended), r2(diff_pay), r2(parity_pay), r2(retro), r2(bonus),
                          r2(pto_pay), r2(gross), r2(pretax), r2(ee_tax), r2(odp_total), r2(net), r2(er_tax),
                          r2(er_m * 12 / 26), r2(gross + er_tax + er_m * 12 / 26), e.tenant["client_id"]])

# ---------------------------------------------------------------------------
# ACA Compliance (monthly, 2024-01 .. last full month)
# ---------------------------------------------------------------------------
AFFORD = {2024: 0.0839, 2025: 0.0902, 2026: 0.0996}
PEN_A, PEN_B = {2024: 241.67, 2025: 241.67, 2026: 280.00}, {2024: 362.50, 2025: 362.50, 2026: 420.00}
months = []
m = START
while month_end(m) <= END:
    months.append(m)
    m = month_end(m) + dt.timedelta(days=1)
aca_seq = 0
for e in REAL:
    salaried = ROLES[e.role][R_PAY] == "Salary"
    elig = eligibility_date(e)
    hist = []
    offer_glitch = rng.random() < 0.04   # missed offers (payroll/benefits setup errors), shrinking over time
    var_offered = rng.random() < 0.85    # variable-hour staff who became ACA full-time and got an offer
    for m in months:
        me = month_end(m)
        if e.hire > me or (e.term and e.term < m):
            continue
        y = m.year
        hrs = 173.33 if salaried else ACA_HOURS.get((e.idx, (y, m.month)), 0.0)
        if salaried and (e.hire > m or (e.term and e.term < me)):
            hrs = hrs * 0.5
        hist.append(hrs)
        full_month = e.hire <= m and (e.term is None or e.term >= me)
        lookback = sum(hist[-12:]) / len(hist[-12:])
        if e.etype == "Full-Time":
            status, method, ft = "Full-Time", "Monthly Measurement", 1
        elif len(hist) >= 6 and lookback >= 130:
            status, method, ft = "Variable Hour - Became Full-Time", "Look-Back Measurement", 1
        else:
            status, method, ft = ("Variable Hour" if e.etype == "PRN / Per Diem" else "Part-Time"), \
                "Look-Back Measurement", 0
        med = any(eff <= m <= end for eff, end in MED_ENROLLED.get(e.idx, ()))
        in_wait = m < elig
        offered = ft == 1 and not in_wait and (e.etype == "Full-Time" or var_offered)
        if offered and offer_glitch and rng.random() < {2024: 0.6, 2025: 0.35, 2026: 0.2}[y]:
            offered = False
        lowest = 515.0 * 1.07 ** (y - 2024) * 0.12
        threshold = (rate_at(e, m) / (2080 if salaried else 1)) * 130 * AFFORD[y]
        affordable = int(lowest <= threshold)
        risk, exposure = 0, 0.0
        if ft and not in_wait and not offered:
            risk, exposure = 1, PEN_A[y]
        elif offered and not affordable and not med:
            risk, exposure = 1, PEN_B[y]
        line14 = "1E" if offered else "1H"
        if in_wait:                       # limited non-assessment (waiting) period incl. the hire month
            line16 = "2D"
        elif not full_month:
            line16 = "2A"
        elif med:
            line16 = "2C"
        elif ft == 0:
            line16 = "2B"
        elif offered:
            line16 = "2H"
        else:
            line16 = NA
        aca_seq += 1
        W.row("aca_monthly", [f"ACA{aca_seq:08d}", e.id, ds(m), y, r2(hrs), status, method, line14, line16,
                              r2(lowest), r2(threshold), affordable, ft, int(offered), int(med), risk, r2(exposure),
                              "Filed with IRS" if y < 2026 else "Not Yet Due", e.tenant["client_id"]])

# ---------------------------------------------------------------------------
# LMS
# ---------------------------------------------------------------------------
asg_seq = 0


def courses_for(e, annual):
    mix = e.loc["mix"]
    r = ROLES[e.role]
    c = ["HIPAA", "ABUSE", "HARASS", "EMERG"] + ([] if annual else ["CODE", "OSHA", "CULT"])
    if r[R_CLIN]:
        c += ["INFX", "BBP"]
    if mix in ("snf", "senior", "ccrc"):
        c += ["FIRE", "RIGHTS"] + (["DEMEN"] if r[R_CLIN] else [])
        if r[R_FAMILY] in ("Direct Care", "Nursing") and not annual:
            c += ["HANDLE", "FALLS"]
    if mix == "homecare":
        c += ["RIGHTS"] + ([] if annual else ["EVV", "CUST"]) + (["DEMEN"] if r[R_CLIN] else [])
    if mix in ("homehealth", "hhh") and r[R_CLIN]:
        c += ["OASIS"] if annual or r[R_FAMILY] == "Nursing" else []
    if mix in ("hospice", "hhh"):
        c += ["EOL"] if not annual else []
    if mix == "aba" and r[R_FAMILY] == "Behavioral Health":
        c += ["ABAETH"] + (["RBTSUP"] if not annual else [])
    if r[R_FAMILY] == "Leadership" and not annual:
        c += ["LEAD"]
    return list(dict.fromkeys(c))


def emit_assignment(e, cid, reason, assigned, due_days):
    global asg_seq
    pr = progress(assigned)
    due = assigned + dt.timedelta(days=due_days)
    lag = int(rng.expovariate(1 / (due_days * (0.45 - 0.15 * pr))))
    if rng.random() < 0.05:
        lag = 10 ** 4  # never completed
    comp = assigned + dt.timedelta(days=lag)
    if comp > END or (e.term and comp > e.term):
        comp = None
    c = COURSE[cid]
    if comp:
        status = "Completed"
    elif e.term and e.term < min(due, END):
        status = "Incomplete - Terminated"
    elif due < END:
        status = "Overdue"
    else:
        status = "In Progress" if rng.random() < 0.4 else "Not Started"
    score = r2(min(100, max(70, rng.gauss(89, 7)))) if comp else 0.0
    spent = int(c[4] * rng.uniform(0.75, 1.5)) if comp else (int(c[4] * rng.uniform(0.1, 0.6)) if status == "In Progress" else 0)
    attempts = (1 if rng.random() < 0.88 else 2) if comp else (1 if status == "In Progress" else 0)
    device = (("Mobile App" if rng.random() < 0.45 + 0.3 * pr else "Desktop") if c[3] != "Instructor-Led" else "In Person") if comp else NA
    asg_seq += 1
    W.row("course_assignments", [f"LMS{asg_seq:08d}", e.id, cid, reason, ds(assigned), ds(due),
                                 ds(comp) if comp else NA_DATE, status, score, spent, attempts, device,
                                 c[5] if comp else 0.0, int(comp is not None), int(status == "Overdue"),
                                 int(comp is not None and comp <= due), e.tenant["client_id"]])


for e in REAL:
    if e.hire >= START - dt.timedelta(days=10):
        for cid in courses_for(e, annual=False):
            emit_assignment(e, cid, "New Hire Orientation", max(e.hire - dt.timedelta(days=2), START), 21)
    for year in (2024, 2025, 2026):
        a = dt.date(year, e.hire.month, min(e.hire.day, 28)) - dt.timedelta(days=30)
        if a < START or a > END or a < e.hire + dt.timedelta(days=300) or (e.term and a > e.term):
            continue
        for cid in courses_for(e, annual=True):
            emit_assignment(e, cid, "Annual Compliance", a, 45)
        if rng.random() < 0.18:
            emit_assignment(e, rng.choice(["CULT", "CUST", "FALLS", "DEMEN", "LEAD"]), "Career Development",
                            a + dt.timedelta(days=rng.randint(5, 60)), 60)
    # remediation after attendance / policy issues
    if e.term_type == "Involuntary" and e.term and e.term > START + dt.timedelta(days=60) and rng.random() < 0.4:
        emit_assignment(e, rng.choice(["CODE", "ABUSE", "INFX"]), "Remediation",
                        e.term - dt.timedelta(days=rng.randint(20, 50)), 14)

# ---------------------------------------------------------------------------
# Exclusion Monitoring
# ---------------------------------------------------------------------------
LISTS = ["OIG LEIE", "SAM.gov", "State Medicaid Exclusion List"]
ex_seq = 0


def emit_check(e, d, lst, ctype, confirmed=False):
    global ex_seq
    ex_seq += 1
    potential = confirmed or rng.random() < 0.0022
    if confirmed:
        res, resol, rd = "Confirmed Match", "Confirmed - Employment Terminated", e.term
    elif potential:
        days = rng.randint(1, 6) if rng.random() < 0.7 else rng.randint(7, 24)
        rd = d + dt.timedelta(days=days)
        if rd > END:
            res, resol, rd = "Potential Match", "Under Review", None
        else:
            res, resol = "Potential Match", "Cleared - False Positive"
    else:
        res, resol, rd = "Clear", NA, None
    W.row("exclusion_checks", [f"EXC{ex_seq:08d}", e.id, ds(d), lst, ctype, res, resol, ds(rd) if rd else NA_DATE,
                               (rd - d).days if rd else 0, int(potential), int(confirmed), e.tenant["client_id"]])


for e in REAL:
    if e.hire >= START:
        pre = (e.offer_date or e.hire) + dt.timedelta(days=1)
        for lst in LISTS:
            emit_check(e, min(pre, e.hire), lst, "Pre-Hire Screening")
    m = dt.date(START.year, START.month, 5)
    while m <= END:
        if employed(e, m) and m > e.hire + dt.timedelta(days=15):
            for lst in LISTS:
                conf = (e.idx in EXCLUDED and lst == "OIG LEIE" and e.term and 0 <= (e.term - m).days < 31)
                emit_check(e, m, lst, "Monthly Rescreen", confirmed=conf)
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 5)

# ---------------------------------------------------------------------------
# HR cases (Viventium HR experts vs client HR team)
# ---------------------------------------------------------------------------
CASE_CATS = [("Policy & Handbook Question", .18, 2), ("Leave & FMLA", .16, 9), ("Wage & Hour / Overtime", .13, 5),
             ("Employee Relations", .14, 8), ("Discipline & Termination", .12, 6),
             ("Workplace Injury / Workers' Comp", .07, 14), ("State Regulation & Licensing", .08, 6),
             ("Benefits & ACA Question", .07, 3), ("Harassment & Discrimination", .03, 21),
             ("Immigration / I-9", .02, 7)]
case_seq = 0
for tenant in TENANTS:
    expert_share = {"Enterprise": .45, "Professional": .6, "Growth": .8}[tenant["tier"]]
    locs = {l["id"] for l in tenant["locations"]}
    temps = [e for e in REAL if e.loc["id"] in locs]
    d = START
    while d <= END:
        active = [e for e in temps if employed(e, d)] if d.day == 1 else active
        lam = len(active) * 0.024 / 30.0
        for _ in range(poisson(lam)):
            e = rng.choice(active)
            cat, _, mean_days = wchoice([((c, w, m), w) for c, w, m in CASE_CATS])
            handler = "Viventium HR Expert" if rng.random() < expert_share else "Client HR Team"
            prio = "Urgent" if cat.startswith("Harassment") or (cat.startswith("Workplace") and rng.random() < .4) \
                else wchoice([("High", .2), ("Medium", .5), ("Low", .3)])
            frh = max(0.1, rng.expovariate(1 / (2.5 if handler == "Viventium HR Expert" else 9.0)))
            days = max(0, int(rng.expovariate(1 / (mean_days * (0.8 if handler == "Viventium HR Expert" else 1.15)))))
            closed = d + dt.timedelta(days=days)
            escalated = rng.random() < 0.06
            if closed > END:
                status, closed_s, is_closed = ("Escalated" if escalated else "Open"), NA_DATE, 0
                days = (END - d).days
            else:
                status, closed_s, is_closed = "Closed", ds(closed), 1
            rated = is_closed and rng.random() < 0.55
            sat = (rng.choice([4, 5, 5, 5, 4, 3]) if handler == "Viventium HR Expert" else rng.choice([3, 4, 4, 5, 2]))\
                if rated else 0
            channel = wchoice([("HR Expert Hotline", .35), ("Email", .25), ("Client Portal", .2), ("Mobile App", .2)]) \
                if handler == "Viventium HR Expert" else wchoice([("Email", .4), ("In Person", .4), ("Mobile App", .2)])
            case_seq += 1
            W.row("hr_cases", [f"{tenant['prefix']}-CASE{case_seq:06d}", e.id, ds(d), closed_s, cat, prio, channel,
                               handler, status, r2(frh), days, sat, int(rated), is_closed, yn(escalated),
                               tenant["client_id"]])
        d += dt.timedelta(days=1)

# ---------------------------------------------------------------------------
# Workforce monthly snapshot (headcount / turnover)
# ---------------------------------------------------------------------------
snap_seq = 0
all_months = list(months)
if month_end(all_months[-1]) < END:
    all_months.append(month_end(all_months[-1]) + dt.timedelta(days=1))
for e in REAL:
    for m in all_months:
        me = min(month_end(m), END)
        if e.hire > me or (e.term and e.term < m):
            continue
        active = int(e.term is None or e.term > me)
        hire = int(m <= e.hire <= me)
        term = int(e.term is not None and m <= e.term <= me)
        snap_seq += 1
        W.row("workforce_monthly", [f"WF{snap_seq:08d}", e.id, ds(m), active, hire, term,
                                    int(term and e.term_type == "Voluntary"),
                                    int(term and (e.term - e.hire).days <= 90),
                                    max(0, (me - e.hire).days // 30), e.fte if active else 0.0,
                                    e.tenant["client_id"]])

W.close()


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------
def write_ddl():
    os.makedirs(OUT_DDL, exist_ok=True)
    with open(os.path.join(OUT_DDL, "postgresql.sql"), "w") as f:
        f.write("-- Viventium demo schema (GoodData Cloud). WDF column: wdf__client_id\n"
                "-- Works for PostgreSQL and DuckDB / MotherDuck.\n")
        f.write("CREATE SCHEMA IF NOT EXISTS viventium;\nSET search_path TO viventium;\n\n")
        for t, cols in SCHEMA.items():
            body = ",\n".join(f"  {c} {typ} NOT NULL" for c, typ in cols)
            body += f",\n  PRIMARY KEY ({', '.join(PRIMARY_KEYS[t])})"
            f.write(f"DROP TABLE IF EXISTS {t};\nCREATE TABLE {t} (\n{body}\n);\n\n")
        f.write("-- load (psql, run from demo_data/):\n")
        for t in SCHEMA:
            f.write(f"\\copy {t} FROM 'csv/{t}.csv' WITH (FORMAT csv, HEADER true)\n")
    with open(os.path.join(OUT_DDL, "snowflake.sql"), "w") as f:
        f.write("-- Viventium demo schema (GoodData Cloud). WDF column: WDF__CLIENT_ID\n")
        f.write("CREATE SCHEMA IF NOT EXISTS VIVENTIUM;\nUSE SCHEMA VIVENTIUM;\n"
                "CREATE OR REPLACE FILE FORMAT VIV_CSV TYPE = CSV SKIP_HEADER = 1 "
                "FIELD_OPTIONALLY_ENCLOSED_BY = '\"';\n"
                "CREATE OR REPLACE STAGE VIV_STAGE FILE_FORMAT = VIV_CSV;\n\n")
        for t, cols in SCHEMA.items():
            body = ",\n".join(f"  {c.upper()} {typ} NOT NULL" for c, typ in cols)
            f.write(f"CREATE OR REPLACE TABLE {t.upper()} (\n{body}\n);\n\n")
        f.write("-- PUT file://<path>/demo_data/csv/*.csv @VIV_STAGE;  then:\n")
        for t in SCHEMA:
            f.write(f"COPY INTO {t.upper()} FROM @VIV_STAGE/{t}.csv.gz;\n")


write_ddl()
print("Row counts:")
for t in SCHEMA:
    print(f"  {t:<22}{W.counts[t]:>10,}")
print(f"  {'TOTAL':<22}{sum(W.counts.values()):>10,}")
