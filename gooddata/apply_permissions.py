#!/usr/bin/env python3
"""
Object-level permissions per data product (Viventium product).

For every product in data_products.json (written by build_analytics.py):
  * user group  dp_<product>  is created (if missing)
  * the group gets VIEW on the product's facts, attributes, secondary labels, metrics,
    visualizations and dashboard
  * the "all workspace users" grant is removed from those objects (unless --open)
Shared dimensions (dates, clients, locations, job roles, employees, pay periods) stay open to everybody.
Child workspaces inherit these permissions from the parent.

    set -a; . ../.env; set +a
    python3 apply_permissions.py            # restrict each product to its group
    python3 apply_permissions.py --open     # grant groups but keep everything visible to all users
    python3 apply_permissions.py --add-user <user_id> --products Payroll,HR   # put a user in product groups

Re-run after every `gd deploy`.
"""
import argparse
import concurrent.futures as cf
import json
import os
import sys
import urllib.error
import urllib.request

HOST = os.environ.get("GD_HOST", "https://sandrasuszterova.demo.cloud.gooddata.com")
PARENT = os.environ.get("GD_PARENT", "a60f79ad0a99473fafe4d043228d5bd7")
HERE = os.path.dirname(os.path.abspath(__file__))
JSONAPI = "application/vnd.gooddata.api+json"


def call(method, path, body=None, ctype="application/json"):
    req = urllib.request.Request(HOST + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {os.environ['GOODDATA_API_TOKEN']}",
                                          "Content-Type": ctype, "Accept": "application/json, " + JSONAPI})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


def ensure_group(gid, product):
    status, resp = call("POST", "/api/v1/entities/userGroups",
                        {"data": {"id": gid, "type": "userGroup", "attributes": {"name": f"Data Product: {product}"}}},
                        JSONAPI)
    if status not in (200, 201, 409):
        sys.exit(f"group {gid}: {status} {resp}")
    return "created" if status in (200, 201) else "exists"


def set_perms(kind, oid, gid, restrict):
    body = [{"assigneeIdentifier": {"id": gid, "type": "userGroup"}, "permissions": ["VIEW"]}]
    if restrict:
        body.append({"assigneeRule": {"type": "allWorkspaceUsers"}, "permissions": []})
    else:
        body.append({"assigneeRule": {"type": "allWorkspaceUsers"}, "permissions": ["VIEW"]})
    status, resp = call("POST", f"/api/v1/actions/workspaces/{PARENT}/{kind}/{oid}/managePermissions", body)
    return kind, oid, status, resp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true", help="keep objects visible to all workspace users")
    ap.add_argument("--add-user")
    ap.add_argument("--products", help="comma-separated product names for --add-user (default: all)")
    args = ap.parse_args()
    products = json.load(open(os.path.join(HERE, "data_products.json")))

    if args.add_user:
        wanted = args.products.split(",") if args.products else list(products)
        for p in wanted:
            gid = products[p]["user_group"]
            s, r = call("GET", f"/api/v1/entities/users/{args.add_user}?include=userGroups", None, JSONAPI)
            if s != 200:
                sys.exit(f"user {args.add_user}: {s} {r}")
            groups = r["data"].get("relationships", {}).get("userGroups", {}).get("data", [])
            if not any(g["id"] == gid for g in groups):
                groups.append({"id": gid, "type": "userGroup"})
                s, r = call("PATCH", f"/api/v1/entities/users/{args.add_user}",
                            {"data": {"id": args.add_user, "type": "user",
                                      "relationships": {"userGroups": {"data": groups}}}}, JSONAPI)
                if s not in (200, 204):
                    sys.exit(f"add {args.add_user} to {gid}: {s} {r}")
            print(f"  {args.add_user} -> {gid}")
        return

    jobs = []
    for product, x in products.items():
        gid = x["user_group"]
        print(f"{product:<22} group {gid:<26} {ensure_group(gid, product)}")
        for kind, key in (("facts", "facts"), ("attributes", "attributes"), ("labels", "labels"),
                          ("metrics", "metrics"), ("visualizationObjects", "visualizations"),
                          ("analyticalDashboards", "dashboards")):
            jobs += [(kind, oid, gid) for oid in x[key]]
    with cf.ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda j: set_perms(*j, restrict=not args.open), jobs))
    bad = [r for r in results if r[2] not in (200, 204)]
    print(f"\n{len(results) - len(bad)} objects updated ({'open to all' if args.open else 'restricted to product group'}),"
          f" {len(bad)} failed")
    for kind, oid, status, resp in bad[:20]:
        print(f"  {kind}/{oid}: {status} {resp}")


if __name__ == "__main__":
    main()
