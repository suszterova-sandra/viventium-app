#!/usr/bin/env python3
"""
Verify the tenancy design by acting as each persona (their own API token from ../demo_app/.tokens.json).

    set -a; . ../.env; set +a
    python3 tenancy/verify_personas.py

Per persona: visible workspaces + permissions, visible dashboards, and probes that must hold:
  - clients visible     (tenant isolation: WDF in dedicated workspaces, client UDF in the shard)
  - locations visible   (location UDF)
  - a metric of a product outside the persona's role is refused (object-level permissions)
"""
import csv
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOST = os.environ.get("GD_HOST", "https://sandrasuszterova.demo.cloud.gooddata.com")
TOKENS = json.loads((HERE.parent / "demo_app" / ".tokens.json").read_text())
DP = json.load(open(HERE.parent / "gooddata" / "data_products.json"))
# one probe metric per data product
PROBE = {"Applicant Tracking": "ats_applications", "Onboarding": "ob_tasks", "Scheduling": "sch_shifts",
         "Time & Attendance": "ta_worked_hours", "Payroll": "pr_gross", "On-Demand Pay": "odp_amount",
         "Benefits": "ben_enrollments", "ACA Compliance": "aca_records", "LMS": "lms_assignments",
         "Exclusion Monitoring": "exc_checks", "HR": "hr_hires"}


def call(token, method, path, body=None):
    req = urllib.request.Request(HOST + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def execute(token, ws, metric, label=None):
    attrs = [{"localIdentifier": "a", "label": {"identifier": {"id": label, "type": "label"}}}] if label else []
    body = {"execution": {"attributes": attrs, "filters": [],
                          "measures": [{"localIdentifier": "m", "definition": {"measure": {"item": {"identifier": {
                              "id": metric, "type": "metric"}}}}}]},
            "resultSpec": {"dimensions": ([{"localIdentifier": "d0", "itemIdentifiers": ["a"]}] if label else [])
                           + [{"localIdentifier": "d1", "itemIdentifiers": ["measureGroup"]}]}}
    s, r = call(token, "POST", f"/api/v1/actions/workspaces/{ws}/execution/afm/execute", body)
    if s != 200:
        return None, s
    s, res = call(token, "GET", f"/api/v1/actions/workspaces/{ws}/execution/afm/execute/result/"
                                f"{r['executionResponse']['links']['executionResult']}")
    if s != 200:
        return None, s
    if not label:
        return res["data"], 200
    return [h["attributeHeader"]["labelValue"] for h in res["dimensionHeaders"][0]["headerGroups"][0]["headers"]], 200


def main():
    personas = list(csv.DictReader(open(HERE / "personas.csv")))
    all_ok = True
    for p in personas:
        tok, ws = TOKENS[p["user_id"]], p["workspace_id"]
        print(f"\n=== {p['first_name']} {p['last_name']} · {p['role']} ({p['user_id']})")
        s, r = call(tok, "GET", "/api/v1/entities/workspaces?metaInclude=permissions&size=100")
        wss = {w["id"]: w.get("meta", {}).get("permissions", []) for w in r["data"]}
        print(f"  workspaces: {wss}")
        s, r = call(tok, "GET", f"/api/v1/entities/workspaces/{ws}/analyticalDashboards?size=100")
        dashes = sorted(d["attributes"]["title"] for d in r["data"]) if s == 200 else f"HTTP {s}"
        print(f"  dashboards: {dashes}")
        own = p["data_products"].split("|")
        m = PROBE[own[0]]
        clients, _ = execute(tok, ws, m, "clients.client_id")
        locs, _ = execute(tok, ws, m, "locations.location_id")
        print(f"  clients visible: {clients}   locations visible: {locs}")
        checks = [("only own client", clients == [p["client_id"]]),
                  ("only own locations", p["locations"] == "ALL" or sorted(locs or []) == sorted(p["locations"].split("|"))),
                  ("own dashboards only", isinstance(dashes, list) and len(dashes) == len(own))]
        refused = []
        for prod, metric in PROBE.items():
            v, s = execute(tok, ws, metric)
            if prod in own and s != 200:
                checks.append((f"{prod} usable", False))
            if prod not in own:
                refused.append(s != 200)
        checks.append((f"{len(refused)} other products refused", all(refused)))
        s, _ = call(tok, "GET", f"/api/v1/entities/workspaces/{ws}/facts/employees.hourly_rate")
        pay_visible = s == 200
        checks.append(("pay rates hidden" if "Payroll" not in own else "pay rates visible",
                       pay_visible == ("Payroll" in own)))
        for name, passed in checks:
            all_ok &= passed
            print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    print("\nALL CHECKS PASSED" if all_ok else "\nSOME CHECKS FAILED")


if __name__ == "__main__":
    main()
