#!/usr/bin/env python3
"""
Provision the Viventium multitenant setup in GoodData Cloud. Safe to re-run (existing objects are kept).

    set -a; . ../.env; set +a
    python3 provision.py                     # WDF + all client workspaces
    python3 provision.py --client riverstone # one client only (live provisioning demo)

Only the dedicated client workspaces live here. The full tenancy (dedicated workspaces + the shared Base
shard, client groups, user data filters, personas) is reconciled from tenancy/tenant_mapping.csv by
tenancy/reconcile.py, which is the source of truth.

Run `gd deploy` (from viventium/) between creating the WDF and creating the clients the first time,
because the datasets reference the `client_id` filter.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HOST = os.environ.get("GD_HOST", "https://sandrasuszterova.demo.cloud.gooddata.com")
PARENT = os.environ.get("GD_PARENT", "a60f79ad0a99473fafe4d043228d5bd7")
JSONAPI = "application/vnd.gooddata.api+json"
CLIENTS = {
    "riverstone": "Riverstone Health Partners",
    "hearthside": "HearthSide Home Care",
}


def call(method, path, body=None, ctype=JSONAPI):
    req = urllib.request.Request(HOST + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {os.environ['GOODDATA_API_TOKEN']}",
                                          "Content-Type": ctype, "Accept": "application/json, " + JSONAPI})
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:600]


def create(path, body, label):
    status, resp = call("POST", path, body)
    if status in (200, 201):
        print(f"  created  {label}")
    elif status == 409:
        print(f"  exists   {label}")
    else:
        sys.exit(f"  FAILED   {label}: {status} {resp}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", choices=sorted(CLIENTS))
    args = ap.parse_args()
    if not args.client:
        print("Workspace data filter")
        create(f"/api/v1/entities/workspaces/{PARENT}/workspaceDataFilters",
               {"data": {"id": "client_id", "type": "workspaceDataFilter",
                         "attributes": {"title": "Client ID", "description": "Tenant isolation by Viventium client",
                                        "columnName": "wdf__client_id"}}}, "client_id")
    for cid in ([args.client] if args.client else CLIENTS):
        print(f"Client {cid}")
        create("/api/v1/entities/workspaces",
               {"data": {"id": cid, "type": "workspace", "attributes": {"name": CLIENTS[cid]},
                         "relationships": {"parent": {"data": {"id": PARENT, "type": "workspace"}}}}},
               f"workspace {cid}")
        create(f"/api/v1/entities/workspaces/{cid}/workspaceDataFilterSettings",
               {"data": {"id": cid, "type": "workspaceDataFilterSetting",
                         "attributes": {"title": CLIENTS[cid], "filterValues": [cid]},
                         "relationships": {"workspaceDataFilter": {"data": {"id": "client_id",
                                                                             "type": "workspaceDataFilter"}}}}},
               f"filter value {cid}")


if __name__ == "__main__":
    main()
