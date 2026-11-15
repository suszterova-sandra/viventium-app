# Viventium – GoodData setup

The whole workspace is defined as code: the data model, metrics, visualizations and dashboards are generated from `build_analytics.py` and deployed with the `gd` CLI.

| Setting | Value |
|---|---|
| Org | sandrasuszterova.demo.cloud.gooddata.com |
| Parent workspace | `a60f79ad0a99473fafe4d043228d5bd7` (Viventium) |
| Data source | `60decaca-4985-4d83-84f1-a2232c38cf3b` (MotherDuck `viventium`, schema `main`) |

```bash
cd viventium
set -a; . ./.env; set +a                         # GOODDATA_API_TOKEN
export PATH=~/.nvm/versions/node/v22.14.0/bin:$PATH  # gd CLI

python3 gooddata/build_analytics.py   # writes analytics/*.yaml and gooddata/data_products.json
gd validate && gd deploy              # parent workspace
python3 gooddata/provision.py         # WDF client_id + 5 child workspaces (or --client <id>)
python3 gooddata/apply_permissions.py # object-level permissions per data product (re-run after every deploy)
python3 theme/build_themes.py --deploy        # Viventium theme on the parent + a brand theme per client workspace
python3 publisher/build_reports.py --deploy   # one publisher report per data product (documents dp_<product>_report)
python3 gooddata/check_dashboards.py          # replay every dashboard widget (last 12 months) in parent + all clients
```

After reloading MotherDuck, clear the GoodData cache, because the data source caches results indefinitely:
`curl -X POST -H "Authorization: Bearer $GOODDATA_API_TOKEN" $HOST/api/v1/actions/dataSources/60decaca-4985-4d83-84f1-a2232c38cf3b/uploadNotification`

`check_dashboards.py` flags a widget as EMPTY when every value is 0. Some of those zeros are correct:

| Widget | Clients | Why 0 is right |
|---|---|---|
| Agency Cost | HearthSide (home care), Little Oak (ABA) | They don't use staffing agencies. |
| Matches Under Review | Any | There are no open exclusion reviews right now. |

ACA trends show 11 of the last 12 months, because the current month isn't closed yet.

## Themes and reports

**Themes (`theme/`)** are per workspace: GoodData can't give a single dashboard its own theme.
- **Parent** (`viventium`): Viventium purple, Noto Sans font, the real Viventium logo.
- **Clients** (`viventium_<client_id>`): each child workspace has its own fictional brand colours and a text logo.
- **Report images:** every theme carries the same image ids, including one product image per data product (`dp_<product>`). Reports therefore render in whichever brand is active.

**Reports (`publisher/`)**: there is one report per data product, 4 pages each.
- **Pages:** a cover with the product image, an "At a Glance" page with KPIs and the main chart, and two analysis pages.
- **Content:** a report uses only its own product's visualizations; the builder stops with an error otherwise.
  Documents have no permissions of their own, but the restricted visualizations block report content for users outside that product's group.
- **Period and summaries:** the period is the last 6 complete months, and AI takeaways are on.

## Multitenancy

The workspace data filter `client_id` uses the column `wdf__client_id`, and it's set on every tenant table.
`job_roles`, `courses` and `pay_periods` are global tables without the filter.

The child workspaces inherit everything from the parent. Each one is filtered to a single client:

| Workspace ID | Client |
|---|---|
| `riverstone` | Riverstone Health Partners |
| `maplehollow` | Maple Hollow Senior Living |
| `hearthside` | HearthSide Home Care |
| `willowbend` | Willowbend Home Health & Hospice |
| `littleoak` | Little Oak Behavioral Health |

## Data products and object-level permissions

Each Viventium product is a **data product**: its own fact datasets, metrics, visualizations and one dashboard.
- **Isolation:** a data product may use only its own objects plus the shared dimensions (Date, Clients, Locations, Job Roles, Employees, Pay Periods).
  `build_analytics.py` stops with an error if any metric, visualization or dashboard references another product, so restricting one product never breaks another.
- **Tags:** each object is tagged with its product name. Shared dimensions are tagged "Shared Dimensions".
- **Permissions:** `apply_permissions.py` creates one user group per product (`dp_applicant_tracking`, `dp_onboarding`, `dp_scheduling`, `dp_time_attendance`, `dp_payroll`, `dp_on_demand_pay`, `dp_benefits`, `dp_aca_compliance`, `dp_lms`, `dp_exclusion_monitoring`, `dp_hr`).
  - Each group gets VIEW on its product's facts, attributes, labels, metrics, visualizations and dashboard.
  - The "all workspace users" grant is removed from those objects.
  - Employee pay columns (`hourly_rate`, `annual_salary`) belong to the Payroll product.
  - Child workspaces inherit the grants.
- **Users:** give a user a data product with `python3 gooddata/apply_permissions.py --add-user <user_id> --products "Payroll,HR"`.
  Users also need normal workspace access (VIEW or ANALYZE on the client workspace). Org admins see everything.
- **Undo:** `apply_permissions.py --open` keeps the groups' grants and makes everything visible to all users again.

| # | Dashboard (data product) | Fact datasets |
|---|---|---|
| 1 | Applicant Tracking | requisitions, job_postings, applications |
| 2 | Onboarding | onboarding_tasks |
| 3 | Scheduling | shifts |
| 4 | Time & Attendance | timecards |
| 5 | Payroll | payroll (+ employee pay columns) |
| 6 | On-Demand Pay | odp_transactions |
| 7 | Benefits Administration | benefit_enrollments, benefit_plans |
| 8 | ACA Compliance | aca_monthly |
| 9 | Learning (LMS) | course_assignments, courses |
| 10 | Exclusion Monitoring | exclusion_checks |
| 11 | HR & Workforce | hr_cases, workforce_monthly |

Every dashboard has the same filters:

| Filter | Default |
|---|---|
| Date | Last 12 months |
| Client | All |
| Location | All |
| Job Family | All |

Benefits also has a Plan Type filter.
