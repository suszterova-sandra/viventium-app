-- Viventium demo schema (GoodData Cloud). WDF column: wdf__client_id
-- Works for PostgreSQL and DuckDB / MotherDuck.
CREATE SCHEMA IF NOT EXISTS viventium;
SET search_path TO viventium;

DROP TABLE IF EXISTS job_roles;
CREATE TABLE job_roles (
  job_role_id VARCHAR(64) NOT NULL,
  job_title VARCHAR(128) NOT NULL,
  job_family VARCHAR(128) NOT NULL,
  department VARCHAR(128) NOT NULL,
  is_clinical VARCHAR(3) NOT NULL,
  license_required VARCHAR(128) NOT NULL,
  flsa_status VARCHAR(128) NOT NULL,
  pay_type VARCHAR(128) NOT NULL,
  work_setting VARCHAR(128) NOT NULL,
  PRIMARY KEY (job_role_id)
);

DROP TABLE IF EXISTS courses;
CREATE TABLE courses (
  course_id VARCHAR(64) NOT NULL,
  course_title VARCHAR(128) NOT NULL,
  course_category VARCHAR(128) NOT NULL,
  delivery_format VARCHAR(128) NOT NULL,
  duration_minutes INTEGER NOT NULL,
  ceu_credits NUMERIC(8,2) NOT NULL,
  is_state_mandated VARCHAR(3) NOT NULL,
  PRIMARY KEY (course_id)
);

DROP TABLE IF EXISTS pay_periods;
CREATE TABLE pay_periods (
  pay_period_id VARCHAR(64) NOT NULL,
  pay_period_label VARCHAR(128) NOT NULL,
  period_start_date DATE NOT NULL,
  period_end_date DATE NOT NULL,
  check_date DATE NOT NULL,
  pay_year INTEGER NOT NULL,
  period_number INTEGER NOT NULL,
  PRIMARY KEY (pay_period_id)
);

DROP TABLE IF EXISTS clients;
CREATE TABLE clients (
  client_id VARCHAR(64) NOT NULL,
  client_name VARCHAR(128) NOT NULL,
  industry VARCHAR(128) NOT NULL,
  industry_segment VARCHAR(128) NOT NULL,
  headquarters_city VARCHAR(128) NOT NULL,
  headquarters_state VARCHAR(2) NOT NULL,
  viventium_client_since DATE NOT NULL,
  plan_tier VARCHAR(128) NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (client_id)
);

DROP TABLE IF EXISTS locations;
CREATE TABLE locations (
  location_id VARCHAR(64) NOT NULL,
  location_name VARCHAR(128) NOT NULL,
  location_type VARCHAR(128) NOT NULL,
  city VARCHAR(128) NOT NULL,
  state VARCHAR(2) NOT NULL,
  state_name VARCHAR(128) NOT NULL,
  postal_code VARCHAR(10) NOT NULL,
  region VARCHAR(128) NOT NULL,
  latitude NUMERIC(9,6) NOT NULL,
  longitude NUMERIC(9,6) NOT NULL,
  licensed_capacity INTEGER NOT NULL,
  capacity_unit VARCHAR(128) NOT NULL,
  client_id VARCHAR(64) NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (location_id)
);

DROP TABLE IF EXISTS employees;
CREATE TABLE employees (
  employee_id VARCHAR(64) NOT NULL,
  employee_number VARCHAR(64) NOT NULL,
  first_name VARCHAR(128) NOT NULL,
  last_name VARCHAR(128) NOT NULL,
  full_name VARCHAR(128) NOT NULL,
  gender VARCHAR(10) NOT NULL,
  age_band VARCHAR(128) NOT NULL,
  location_id VARCHAR(64) NOT NULL,
  job_role_id VARCHAR(64) NOT NULL,
  employment_type VARCHAR(128) NOT NULL,
  fte NUMERIC(8,2) NOT NULL,
  pay_type VARCHAR(128) NOT NULL,
  hourly_rate NUMERIC(12,2) NOT NULL,
  annual_salary NUMERIC(12,2) NOT NULL,
  hire_date DATE NOT NULL,
  termination_date DATE NOT NULL,
  employment_status VARCHAR(128) NOT NULL,
  termination_type VARCHAR(128) NOT NULL,
  termination_reason VARCHAR(128) NOT NULL,
  rehire_eligible VARCHAR(128) NOT NULL,
  recruitment_source VARCHAR(128) NOT NULL,
  source_requisition_id VARCHAR(64) NOT NULL,
  preferred_shift VARCHAR(128) NOT NULL,
  uses_mobile_app VARCHAR(3) NOT NULL,
  odp_enrolled VARCHAR(3) NOT NULL,
  odp_enrollment_date DATE NOT NULL,
  is_placeholder VARCHAR(3) NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (employee_id)
);

DROP TABLE IF EXISTS benefit_plans;
CREATE TABLE benefit_plans (
  benefit_plan_id VARCHAR(64) NOT NULL,
  plan_name VARCHAR(128) NOT NULL,
  plan_type VARCHAR(128) NOT NULL,
  carrier VARCHAR(128) NOT NULL,
  network_type VARCHAR(128) NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (benefit_plan_id)
);

DROP TABLE IF EXISTS requisitions;
CREATE TABLE requisitions (
  requisition_id VARCHAR(64) NOT NULL,
  location_id VARCHAR(64) NOT NULL,
  job_role_id VARCHAR(64) NOT NULL,
  requisition_reason VARCHAR(128) NOT NULL,
  priority VARCHAR(128) NOT NULL,
  opened_date DATE NOT NULL,
  filled_date DATE NOT NULL,
  closed_date DATE NOT NULL,
  requisition_status VARCHAR(128) NOT NULL,
  openings INTEGER NOT NULL,
  days_open INTEGER NOT NULL,
  days_to_fill INTEGER NOT NULL,
  sign_on_bonus NUMERIC(12,2) NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (requisition_id)
);

DROP TABLE IF EXISTS job_postings;
CREATE TABLE job_postings (
  posting_id VARCHAR(64) NOT NULL,
  requisition_id VARCHAR(64) NOT NULL,
  job_board VARCHAR(128) NOT NULL,
  posted_date DATE NOT NULL,
  posting_end_date DATE NOT NULL,
  is_sponsored VARCHAR(3) NOT NULL,
  sponsorship_spend NUMERIC(12,2) NOT NULL,
  impressions INTEGER NOT NULL,
  clicks INTEGER NOT NULL,
  applies INTEGER NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (posting_id)
);

DROP TABLE IF EXISTS applications;
CREATE TABLE applications (
  application_id VARCHAR(64) NOT NULL,
  requisition_id VARCHAR(64) NOT NULL,
  candidate_id VARCHAR(64) NOT NULL,
  candidate_name VARCHAR(128) NOT NULL,
  applied_date DATE NOT NULL,
  application_source VARCHAR(128) NOT NULL,
  apply_device VARCHAR(128) NOT NULL,
  highest_stage VARCHAR(128) NOT NULL,
  stage_order INTEGER NOT NULL,
  application_status VARCHAR(128) NOT NULL,
  screened_date DATE NOT NULL,
  interview_date DATE NOT NULL,
  offer_date DATE NOT NULL,
  hire_date DATE NOT NULL,
  hours_to_first_contact NUMERIC(8,2) NOT NULL,
  days_to_hire INTEGER NOT NULL,
  is_screened INTEGER NOT NULL,
  is_interviewed INTEGER NOT NULL,
  is_offered INTEGER NOT NULL,
  is_hired INTEGER NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (application_id)
);

DROP TABLE IF EXISTS onboarding_tasks;
CREATE TABLE onboarding_tasks (
  onboarding_task_id VARCHAR(64) NOT NULL,
  employee_id VARCHAR(64) NOT NULL,
  task_name VARCHAR(128) NOT NULL,
  task_category VARCHAR(128) NOT NULL,
  responsible_party VARCHAR(128) NOT NULL,
  assigned_date DATE NOT NULL,
  due_date DATE NOT NULL,
  completed_date DATE NOT NULL,
  task_status VARCHAR(128) NOT NULL,
  completed_via VARCHAR(128) NOT NULL,
  days_to_complete INTEGER NOT NULL,
  is_completed INTEGER NOT NULL,
  is_overdue INTEGER NOT NULL,
  completed_on_time INTEGER NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (onboarding_task_id)
);

DROP TABLE IF EXISTS shifts;
CREATE TABLE shifts (
  shift_id VARCHAR(64) NOT NULL,
  employee_id VARCHAR(64) NOT NULL,
  shift_date DATE NOT NULL,
  shift_type VARCHAR(128) NOT NULL,
  scheduled_start TIMESTAMP NOT NULL,
  scheduled_end TIMESTAMP NOT NULL,
  scheduled_hours NUMERIC(8,2) NOT NULL,
  visit_count INTEGER NOT NULL,
  shift_status VARCHAR(128) NOT NULL,
  fill_method VARCHAR(128) NOT NULL,
  coverage_outcome VARCHAR(128) NOT NULL,
  covers_shift_id VARCHAR(64) NOT NULL,
  is_weekend VARCHAR(3) NOT NULL,
  publish_lead_days INTEGER NOT NULL,
  agency_cost NUMERIC(12,2) NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (shift_id)
);

DROP TABLE IF EXISTS timecards;
CREATE TABLE timecards (
  timecard_id VARCHAR(64) NOT NULL,
  shift_id VARCHAR(64) NOT NULL,
  employee_id VARCHAR(64) NOT NULL,
  work_date DATE NOT NULL,
  clock_in TIMESTAMP NOT NULL,
  clock_out TIMESTAMP NOT NULL,
  scheduled_hours NUMERIC(8,2) NOT NULL,
  worked_hours NUMERIC(8,2) NOT NULL,
  regular_hours NUMERIC(8,2) NOT NULL,
  overtime_hours NUMERIC(8,2) NOT NULL,
  break_minutes INTEGER NOT NULL,
  late_minutes INTEGER NOT NULL,
  is_late INTEGER NOT NULL,
  is_early_out INTEGER NOT NULL,
  is_missed_punch INTEGER NOT NULL,
  clock_method VARCHAR(128) NOT NULL,
  within_geofence VARCHAR(128) NOT NULL,
  manager_edited VARCHAR(3) NOT NULL,
  approval_status VARCHAR(128) NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (timecard_id)
);

DROP TABLE IF EXISTS payroll;
CREATE TABLE payroll (
  payroll_id VARCHAR(64) NOT NULL,
  pay_period_id VARCHAR(64) NOT NULL,
  employee_id VARCHAR(64) NOT NULL,
  check_date DATE NOT NULL,
  payment_method VARCHAR(128) NOT NULL,
  regular_hours NUMERIC(8,2) NOT NULL,
  overtime_hours NUMERIC(8,2) NOT NULL,
  pto_hours NUMERIC(8,2) NOT NULL,
  regular_pay NUMERIC(12,2) NOT NULL,
  overtime_pay NUMERIC(12,2) NOT NULL,
  blended_rate_ot_adjustment NUMERIC(12,2) NOT NULL,
  shift_differential_pay NUMERIC(12,2) NOT NULL,
  wage_parity_supplement NUMERIC(12,2) NOT NULL,
  retro_pay NUMERIC(12,2) NOT NULL,
  bonus_pay NUMERIC(12,2) NOT NULL,
  pto_pay NUMERIC(12,2) NOT NULL,
  gross_pay NUMERIC(12,2) NOT NULL,
  pretax_deductions NUMERIC(12,2) NOT NULL,
  employee_taxes NUMERIC(12,2) NOT NULL,
  odp_repayment NUMERIC(12,2) NOT NULL,
  net_pay NUMERIC(12,2) NOT NULL,
  employer_taxes NUMERIC(12,2) NOT NULL,
  employer_benefit_cost NUMERIC(12,2) NOT NULL,
  total_employer_cost NUMERIC(12,2) NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (payroll_id)
);

DROP TABLE IF EXISTS odp_transactions;
CREATE TABLE odp_transactions (
  odp_transaction_id VARCHAR(64) NOT NULL,
  employee_id VARCHAR(64) NOT NULL,
  pay_period_id VARCHAR(64) NOT NULL,
  request_date DATE NOT NULL,
  request_timestamp TIMESTAMP NOT NULL,
  amount NUMERIC(12,2) NOT NULL,
  fee NUMERIC(12,2) NOT NULL,
  transfer_type VARCHAR(128) NOT NULL,
  transaction_status VARCHAR(128) NOT NULL,
  decline_reason VARCHAR(128) NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (odp_transaction_id)
);

DROP TABLE IF EXISTS benefit_enrollments;
CREATE TABLE benefit_enrollments (
  enrollment_id VARCHAR(64) NOT NULL,
  employee_id VARCHAR(64) NOT NULL,
  benefit_plan_id VARCHAR(64) NOT NULL,
  plan_year INTEGER NOT NULL,
  coverage_tier VARCHAR(128) NOT NULL,
  enrollment_event VARCHAR(128) NOT NULL,
  election_date DATE NOT NULL,
  effective_date DATE NOT NULL,
  coverage_end_date DATE NOT NULL,
  election_status VARCHAR(128) NOT NULL,
  enrolled_via VARCHAR(128) NOT NULL,
  covered_lives INTEGER NOT NULL,
  contribution_pct NUMERIC(8,2) NOT NULL,
  employee_monthly_cost NUMERIC(12,2) NOT NULL,
  employer_monthly_cost NUMERIC(12,2) NOT NULL,
  is_enrolled INTEGER NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (enrollment_id)
);

DROP TABLE IF EXISTS aca_monthly;
CREATE TABLE aca_monthly (
  aca_record_id VARCHAR(64) NOT NULL,
  employee_id VARCHAR(64) NOT NULL,
  reporting_month DATE NOT NULL,
  reporting_year INTEGER NOT NULL,
  hours_of_service NUMERIC(8,2) NOT NULL,
  aca_status VARCHAR(128) NOT NULL,
  measurement_method VARCHAR(128) NOT NULL,
  offer_code_line14 VARCHAR(4) NOT NULL,
  safe_harbor_code_line16 VARCHAR(4) NOT NULL,
  lowest_cost_ee_premium NUMERIC(12,2) NOT NULL,
  affordability_threshold NUMERIC(12,2) NOT NULL,
  is_affordable INTEGER NOT NULL,
  is_aca_full_time INTEGER NOT NULL,
  is_offered_coverage INTEGER NOT NULL,
  is_enrolled_medical INTEGER NOT NULL,
  penalty_risk INTEGER NOT NULL,
  penalty_exposure_amount NUMERIC(12,2) NOT NULL,
  form_1095c_status VARCHAR(128) NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (aca_record_id)
);

DROP TABLE IF EXISTS course_assignments;
CREATE TABLE course_assignments (
  assignment_id VARCHAR(64) NOT NULL,
  employee_id VARCHAR(64) NOT NULL,
  course_id VARCHAR(64) NOT NULL,
  assignment_reason VARCHAR(128) NOT NULL,
  assigned_date DATE NOT NULL,
  due_date DATE NOT NULL,
  completed_date DATE NOT NULL,
  assignment_status VARCHAR(128) NOT NULL,
  score_pct NUMERIC(8,2) NOT NULL,
  time_spent_minutes INTEGER NOT NULL,
  attempts INTEGER NOT NULL,
  completion_device VARCHAR(128) NOT NULL,
  ceu_credits_earned NUMERIC(8,2) NOT NULL,
  is_completed INTEGER NOT NULL,
  is_overdue INTEGER NOT NULL,
  completed_on_time INTEGER NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (assignment_id)
);

DROP TABLE IF EXISTS exclusion_checks;
CREATE TABLE exclusion_checks (
  check_id VARCHAR(64) NOT NULL,
  employee_id VARCHAR(64) NOT NULL,
  check_date DATE NOT NULL,
  exclusion_list VARCHAR(128) NOT NULL,
  check_type VARCHAR(128) NOT NULL,
  check_result VARCHAR(128) NOT NULL,
  resolution VARCHAR(128) NOT NULL,
  resolved_date DATE NOT NULL,
  days_to_resolve INTEGER NOT NULL,
  is_potential_match INTEGER NOT NULL,
  is_confirmed_match INTEGER NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (check_id)
);

DROP TABLE IF EXISTS hr_cases;
CREATE TABLE hr_cases (
  case_id VARCHAR(64) NOT NULL,
  employee_id VARCHAR(64) NOT NULL,
  opened_date DATE NOT NULL,
  closed_date DATE NOT NULL,
  case_category VARCHAR(128) NOT NULL,
  priority VARCHAR(128) NOT NULL,
  channel VARCHAR(128) NOT NULL,
  handled_by VARCHAR(128) NOT NULL,
  case_status VARCHAR(128) NOT NULL,
  first_response_hours NUMERIC(8,2) NOT NULL,
  resolution_days INTEGER NOT NULL,
  satisfaction_score INTEGER NOT NULL,
  is_rated INTEGER NOT NULL,
  is_closed INTEGER NOT NULL,
  escalated VARCHAR(3) NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (case_id)
);

DROP TABLE IF EXISTS workforce_monthly;
CREATE TABLE workforce_monthly (
  snapshot_id VARCHAR(64) NOT NULL,
  employee_id VARCHAR(64) NOT NULL,
  snapshot_month DATE NOT NULL,
  is_active_eom INTEGER NOT NULL,
  is_new_hire INTEGER NOT NULL,
  is_termination INTEGER NOT NULL,
  is_voluntary_termination INTEGER NOT NULL,
  is_early_turnover INTEGER NOT NULL,
  tenure_months INTEGER NOT NULL,
  fte_eom NUMERIC(8,2) NOT NULL,
  wdf__client_id VARCHAR(64) NOT NULL,
  PRIMARY KEY (snapshot_id)
);

-- load (psql, run from demo_data/):
\copy job_roles FROM 'csv/job_roles.csv' WITH (FORMAT csv, HEADER true)
\copy courses FROM 'csv/courses.csv' WITH (FORMAT csv, HEADER true)
\copy pay_periods FROM 'csv/pay_periods.csv' WITH (FORMAT csv, HEADER true)
\copy clients FROM 'csv/clients.csv' WITH (FORMAT csv, HEADER true)
\copy locations FROM 'csv/locations.csv' WITH (FORMAT csv, HEADER true)
\copy employees FROM 'csv/employees.csv' WITH (FORMAT csv, HEADER true)
\copy benefit_plans FROM 'csv/benefit_plans.csv' WITH (FORMAT csv, HEADER true)
\copy requisitions FROM 'csv/requisitions.csv' WITH (FORMAT csv, HEADER true)
\copy job_postings FROM 'csv/job_postings.csv' WITH (FORMAT csv, HEADER true)
\copy applications FROM 'csv/applications.csv' WITH (FORMAT csv, HEADER true)
\copy onboarding_tasks FROM 'csv/onboarding_tasks.csv' WITH (FORMAT csv, HEADER true)
\copy shifts FROM 'csv/shifts.csv' WITH (FORMAT csv, HEADER true)
\copy timecards FROM 'csv/timecards.csv' WITH (FORMAT csv, HEADER true)
\copy payroll FROM 'csv/payroll.csv' WITH (FORMAT csv, HEADER true)
\copy odp_transactions FROM 'csv/odp_transactions.csv' WITH (FORMAT csv, HEADER true)
\copy benefit_enrollments FROM 'csv/benefit_enrollments.csv' WITH (FORMAT csv, HEADER true)
\copy aca_monthly FROM 'csv/aca_monthly.csv' WITH (FORMAT csv, HEADER true)
\copy course_assignments FROM 'csv/course_assignments.csv' WITH (FORMAT csv, HEADER true)
\copy exclusion_checks FROM 'csv/exclusion_checks.csv' WITH (FORMAT csv, HEADER true)
\copy hr_cases FROM 'csv/hr_cases.csv' WITH (FORMAT csv, HEADER true)
\copy workforce_monthly FROM 'csv/workforce_monthly.csv' WITH (FORMAT csv, HEADER true)
