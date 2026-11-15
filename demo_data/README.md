# Viventium – GoodData demo data source

Demo data for [Viventium](https://viventium.com), an HCM / workforce platform for post-acute care
(skilled nursing, senior living / CCRC, home health, hospice, home care and ABA). It's built for a
multitenant GoodData Cloud setup where **each Viventium product gets its own fact table, so you can build one dashboard per product**.

```
python3 generate.py          # deterministic (fixed seed), ~40 s → csv/*.csv (~2.5 M rows, ~370 MB) + ddl/*.sql
python3 load_motherduck.py   # optional: load into MotherDuck database `viventium` (duckdb==1.5.6)
```

Data covers **2024-01-01 → 2026-11-14**. Published schedules run 14 days into the future, and
2027 Open Enrollment is in progress.

## One product = one dashboard

| Dashboard (Viventium product) | Fact table(s) | Key metrics it supports |
|---|---|---|
| **Applicant Tracking** (+ Job Sponsorships) | `requisitions`, `applications`, `job_postings` | open reqs, time-to-fill, funnel conversion (Applied→Screened→Interviewed→Offered→Hired), source of hire, hours to first contact, sponsored spend, cost per apply / per hire |
| **Onboarding** | `onboarding_tasks` | completion rate, on-time %, days to complete, overdue tasks by category, mobile vs desktop |
| **Scheduling** | `shifts` | scheduled vs worked hours, call-off / no-show rate, coverage outcome (internal pickup / agency / not covered), agency cost, missed visits, open shifts posted to the mobile app, schedule publish lead time |
| **Time & Attendance** | `timecards` | worked / OT hours, late %, missed punches, early outs, clock method (Mobile GPS / Kiosk / IVR / Web), geofence compliance, pending approvals |
| **Payroll** | `payroll` (+ `pay_periods`) | gross / net pay, OT pay, blended-rate OT true-up, shift differentials, **NY wage parity**, retro pay, bonuses, employer taxes, total cost of labor |
| **On-Demand Pay** | `odp_transactions` | adoption, draws per employee, amount, fees, instant vs next-day, declines |
| **Benefits Administration** | `benefit_enrollments`, `benefit_plans` | participation by plan type, waive rate, tier mix, employer vs employee cost, 2027 Open Enrollment progress |
| **ACA Compliance** | `aca_monthly` | FT count, offer rate (Line 14), safe-harbor codes (Line 16), affordability, 4980H penalty exposure, variable-hour employees crossing 130 hours |
| **LMS** | `course_assignments`, `courses` | completion %, overdue compliance training, CEUs earned, scores, time spent |
| **Exclusion Monitoring** | `exclusion_checks` | checks run (OIG LEIE / SAM.gov / State Medicaid), potential vs confirmed matches, days to resolve |
| **HR** (HR experts + workforce) | `hr_cases`, `workforce_monthly`, `employees` | headcount, hires, terminations, annual turnover, early (≤ 90 day) turnover, HR cases by category, Viventium HR Expert vs client HR response and resolution times, CSAT |

The shared dimensions are `employees`, `locations`, `clients`, `job_roles`, `pay_periods`, `courses` and `benefit_plans`.

## Multitenancy (WDF)

Every tenant table has **`wdf__client_id`** = the GoodData child workspace client ID. The global tables (`job_roles`,
`courses`, `pay_periods`) don't have it. All tenants are fictional. Each one represents one of Viventium's industry segments:

| Client ID | Tenant | Segment / industry | Locations |
|---|---|---|---|
| `riverstone` | Riverstone Health Partners | Facilities · Skilled Nursing | Brooklyn NY, Yonkers NY, Paramus NJ, Toms River NJ |
| `maplehollow` | Maple Hollow Senior Living | Facilities · Senior Living & CCRC | Lancaster PA (CCRC), Dublin OH (AL & Memory Care), Sarasota FL (CCRC), Asheville NC (AL) |
| `hearthside` | HearthSide Home Care | Home Care & ABA · Home Care | Flushing NY, Hempstead NY, Stamford CT, Houston TX |
| `willowbend` | Willowbend Home Health & Hospice | Home Health & Hospice | Nashville TN (HH), Knoxville TN (Hospice), Marietta GA (HH&H), Birmingham AL (Hospice) |
| `littleoak` | Little Oak Behavioral Health | Home Care & ABA · ABA | San Diego CA, Phoenix AZ, Austin TX |

`locations` includes real city latitude / longitude (for geo pushpin charts), the state, the US region, and licensed capacity (beds / units / census / learners).

## LDM guidance (single join path)

To avoid ambiguous paths in GoodData, each fact table references **`employees` only**. Location, job role and client
are reached through `employees → locations → clients` and `employees → job_roles`:

- `shifts`, `timecards`, `payroll`, `odp_transactions`, `benefit_enrollments`, `aca_monthly`, `course_assignments`,
  `exclusion_checks`, `hr_cases`, `onboarding_tasks`, `workforce_monthly` → `employees`
- `payroll`, `odp_transactions` → `pay_periods`. `benefit_enrollments` → `benefit_plans`. `course_assignments` → `courses`
- `requisitions` → `locations`, `job_roles`. `applications` and `job_postings` → `requisitions`
- `locations` → `clients`

Open shifts and agency shifts are assigned to **placeholder employees**: one per location × role, with `is_placeholder = Yes`
and IDs like `RSH-BKN-AGENCY-CNA`. Filter them out of headcount metrics.

## Consistency rules (useful when you validate dashboards)

- An employee comes from a filled requisition. Their hired application has the same name and `hire_date`.
  Employees hired before 2024 have `recruitment_source = Legacy (Pre-2024 Hire)`.
- Every `timecards` row belongs to a `Worked` shift of a real employee. Overtime is weekly (> 40 h).
- `payroll` is calculated from timecards per pay period:
  - regular / OT hours and pay match the timecards
  - shift differentials: Evening +$1.50, Night +$2.50, Weekend +$1.00 per hour
  - the FLSA blended-rate OT adjustment is included
  - benefit deductions come from `benefit_enrollments`
  - `odp_repayment` = the sum of completed `odp_transactions` in the period
- `aca_monthly.hours_of_service` = timecard hours in the month (salaried = 173.33). `is_enrolled_medical` matches `benefit_enrollments`.
- A call-off or no-show creates a coverage shift that has `covers_shift_id` = the original shift. The coverage shift is one of:
  - a coworker's pickup, with `fill_method` `Picked Up via Mobile App` or `Manager Assigned`
  - an agency shift with `agency_cost`
  - an unfilled shift, shown as `Unfilled` in facilities or `Missed Visit` in home-based care
- 5 seeded OIG confirmed matches line up with involuntary terminations (`Excluded Provider - OIG/State Match`).

## Built-in demo stories (trends after Viventium go-live)

- Agency shifts and spend fall about 55 % from 2024 to 2026, while internal pickups through the mobile app rise.
- Time-to-fill, early turnover, hours to first candidate contact and onboarding days-to-complete all improve.
- Overtime is highest in NY home care, which also pays wage parity. Facilities run at about 4–6 % OT.
- Mobile adoption grows: clock-ins, onboarding, benefits elections and LMS completions.
- Headcount grows by tenant (ABA +18 %/yr, home care +12 %/yr, SNF +3 %/yr).

## No NULLs

No CSV contains an empty cell. Wherever a value doesn't apply, the data uses one of these instead:

| Type | Placeholder |
|---|---|
| Date | `1900-01-01` |
| Text | `N/A` |
| Number | `0` |

The generator stops with an error if it ever tries to write an empty value.
