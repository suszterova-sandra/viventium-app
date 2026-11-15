#!/usr/bin/env python3
"""
Reconcile the Viventium tenancy setup in GoodData from two mapping files (PoC of the "tenant mapping table ->
pipeline" design: the mapping is the source of truth, this script makes GoodData match it).

    set -a; . ../.env; set +a
    python3 tenancy/reconcile.py              # apply
    python3 tenancy/reconcile.py --tokens     # also (re)create API tokens for the personas -> ../demo_app/.tokens.json

tenant_mapping.csv  client_id, tier (AI | Analytics | Base), product_bundle, workspace_id, locations
                    - AI / Analytics -> dedicated child workspace (workspace data filter = that client)
                    - Base           -> shared shard; the shard's workspace data filter lists all its clients
                                        (backstop), each client is a user group with a client user data filter
personas.csv        demo users: client, role, workspace permissions (tier), data products (role -> dashboards),
                    locations (row-level facility security via user data filter)

Layers (see the design brief):
  tenant   -> workspace data filter (dedicated) / user group + user data filter (shard)
  location -> user data filter per user
  product  -> object-level permissions of the data-product groups dp_<product> (gooddata/apply_permissions.py)
  role     -> data products + column security (pay rates belong to Payroll)
  tier     -> workspace permissions (VIEW / ANALYZE / EXPORT / CREATE_AUTOMATION / USE_AI_ASSISTANT)
Idempotent: existing objects are updated, nothing outside the mapping is deleted. HTTP 429 is retried.
"""
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOST = os.environ.get("GD_HOST", "https://sandrasuszterova.demo.cloud.gooddata.com")
PARENT = "a60f79ad0a99473fafe4d043228d5bd7"
JSONAPI = "application/vnd.gooddata.api+json"
TOKEN_ID = "viventium-demo-app"
DP = json.load(open(HERE.parent / "gooddata" / "data_products.json"))


def call(method, path, body=None, ctype=JSONAPI):
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(6):
        req = urllib.request.Request(HOST + path, method=method, data=data,
                                     headers={"Authorization": f"Bearer {os.environ['GOODDATA_API_TOKEN']}",
                                              "Content-Type": ctype, "Accept": "application/json, " + JSONAPI})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt)
                continue
            return e.code, e.read().decode()[:500]
    return 429, "rate limited"


def upsert(collection, oid, body, label):
    s, r = call("POST", collection, body)
    if s in (200, 201):
        print(f"  created  {label}")
        return
    if s == 409:
        s, r = call("PUT", f"{collection}/{oid}", body)
        if s in (200, 201, 204):
            print(f"  updated  {label}")
            return
    sys.exit(f"  FAILED   {label}: {s} {r}")


def ok(s, r, label):
    if s not in (200, 201, 204):
        sys.exit(f"  FAILED   {label}: {s} {r}")


def main():
    tenants = list(csv.DictReader(open(HERE / "tenant_mapping.csv")))
    personas = list(csv.DictReader(open(HERE / "personas.csv")))

    # 1. workspaces + workspace data filter values
    print("Workspaces")
    by_ws = {}
    for t in tenants:
        by_ws.setdefault(t["workspace_id"], {"name": t["workspace_name"], "clients": []})["clients"].append(t)
    for ws, w in by_ws.items():
        body = {"data": {"id": ws, "type": "workspace", "attributes": {"name": w["name"]},
                         "relationships": {"parent": {"data": {"id": PARENT, "type": "workspace"}}}}}
        upsert("/api/v1/entities/workspaces", ws, body, f"workspace {ws} ({w['name']})")
        values = [c["client_id"] for c in w["clients"]]
        body = {"data": {"id": ws, "type": "workspaceDataFilterSetting",
                         "attributes": {"title": ", ".join(c["client_name"] for c in w["clients"]),
                                        "filterValues": values},
                         "relationships": {"workspaceDataFilter": {"data": {"id": "client_id",
                                                                             "type": "workspaceDataFilter"}}}}}
        upsert(f"/api/v1/entities/workspaces/{ws}/workspaceDataFilterSettings", ws, body,
               f"  WDF client_id = {values}")

    # 2. client groups + client user data filters in shared shards
    print("Client groups (shards)")
    shards = {ws for ws, w in by_ws.items() if len(w["clients"]) > 1}
    for t in tenants:
        gid = f"client_{t['client_id']}"
        upsert("/api/v1/entities/userGroups", gid,
               {"data": {"id": gid, "type": "userGroup", "attributes": {"name": f"Client: {t['client_name']}"}}},
               f"group {gid}")
        if t["workspace_id"] in shards:
            fid = f"udf_{gid}"
            body = {"data": {"id": fid, "type": "userDataFilter",
                             "attributes": {"title": f"Client {t['client_name']}",
                                            "maql": f'{{label/clients.client_id}} = "{t["client_id"]}"'},
                             "relationships": {"userGroup": {"data": {"id": gid, "type": "userGroup"}}}}}
            upsert(f"/api/v1/entities/workspaces/{t['workspace_id']}/userDataFilters", fid, body,
                   f"  UDF {fid} in {t['workspace_id']}")

    # 3. personas: user, groups, location filter, workspace permissions
    print("Personas")
    for p in personas:
        uid = p["user_id"]
        groups = [f"client_{p['client_id']}"] + [DP[d]["user_group"] for d in p["data_products"].split("|")]
        body = {"data": {"id": uid, "type": "user",
                         "attributes": {"firstname": p["first_name"], "lastname": p["last_name"],
                                        "email": f"{uid}@example.com"},
                         "relationships": {"userGroups": {"data": [{"id": g, "type": "userGroup"} for g in groups]}}}}
        upsert("/api/v1/entities/users", uid, body, f"user {uid} ({p['role']}) groups={groups}")
        ws = p["workspace_id"]
        fid = f"udf_loc_{uid.replace('.', '_')}"
        if p["locations"] != "ALL":
            locs = ", ".join(f'"{x}"' for x in p["locations"].split("|"))
            body = {"data": {"id": fid, "type": "userDataFilter",
                             "attributes": {"title": f"Locations of {p['first_name']} {p['last_name']}",
                                            "maql": f"{{label/locations.location_id}} IN ({locs})"},
                             "relationships": {"user": {"data": {"id": uid, "type": "user"}}}}}
            upsert(f"/api/v1/entities/workspaces/{ws}/userDataFilters", fid, body, f"  UDF locations {locs}")
        else:
            call("DELETE", f"/api/v1/entities/workspaces/{ws}/userDataFilters/{fid}")
        perms = p["workspace_permissions"].split("|")
        s, r = call("POST", f"/api/v1/actions/workspaces/{ws}/managePermissions",
                    [{"assigneeIdentifier": {"id": uid, "type": "user"}, "permissions": perms,
                      "hierarchyPermissions": []}], "application/json")
        ok(s, r, f"permissions {uid}")
        print(f"  {ws}: {perms}")

    if "--tokens" in sys.argv:
        out = HERE.parent / "demo_app" / ".tokens.json"
        out.parent.mkdir(exist_ok=True)
        store = json.loads(out.read_text()) if out.exists() else {}
        for p in personas:
            uid = p["user_id"]
            call("DELETE", f"/api/v1/entities/users/{uid}/apiTokens/{TOKEN_ID}")
            s, r = call("POST", f"/api/v1/entities/users/{uid}/apiTokens",
                        {"data": {"id": TOKEN_ID, "type": "apiToken", "attributes": {}}})
            ok(s, r, f"token {uid}")
            store[uid] = r["data"]["attributes"]["bearerToken"]
        out.write_text(json.dumps(store, indent=2))
        out.chmod(0o600)
        print(f"tokens -> {out}")


if __name__ == "__main__":
    main()
