#!/usr/bin/env python3
"""
Replay every dashboard widget the way the dashboard runs it and report data quality per workspace.

    set -a; . ../.env; set +a
    python3 gooddata/check_dashboards.py                 # parent + all client workspaces
    python3 gooddata/check_dashboards.py hearthside      # selected workspaces

For each widget: visualization buckets + its filters + the dashboard default date filter (last 12 months)
on the widget's date dataset (replacing the visualization's own filter on that dataset).
Flags: ERROR (execution failed), EMPTY (no rows / all values null), GAPS (>30 % null cells),
SHORT (monthly trend with fewer than 12 months), THIN (ranking chart / table with < 2 rows).
"""
import concurrent.futures as cf
import json
import os
import sys
import urllib.error
import urllib.request

HOST = os.environ.get("GD_HOST", "https://sandrasuszterova.demo.cloud.gooddata.com")
PARENT = "a60f79ad0a99473fafe4d043228d5bd7"
CLIENTS = ["riverstone", "hearthside", "shard_base_01"]  # see tenancy/tenant_mapping.csv
DASH_DATE = {"granularity": "MONTH", "from": -11, "to": 0}


def call(method, path, body=None):
    req = urllib.request.Request(HOST + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {os.environ['GOODDATA_API_TOKEN']}",
                                          "Content-Type": "application/json"})
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()[:400]
        except Exception as e:  # noqa: BLE001 - retry transient network errors
            err = str(e)
    return 599, err


def afm_measure(m):
    d = m["definition"]
    if "measureDefinition" in d:
        md = d["measureDefinition"]
        return {"localIdentifier": m["localIdentifier"],
                "definition": {"measure": {"item": md["item"], "filters": [afm_filter(f) for f in md.get("filters", [])]}}}
    if "previousPeriodMeasure" in d:
        p = d["previousPeriodMeasure"]
        return {"localIdentifier": m["localIdentifier"],
                "definition": {"previousPeriodMeasure": {
                    "measureIdentifier": {"localIdentifier": p["measureIdentifier"]},
                    "dateDatasets": [{"dataset": {"identifier": x["dataSet"]["identifier"]},
                                      "periodsAgo": x["periodsAgo"]} for x in p["dateDataSets"]]}}}
    raise ValueError(f"unsupported measure {d.keys()}")


def afm_filter(f):
    if "relativeDateFilter" in f:
        r = f["relativeDateFilter"]
        return {"relativeDateFilter": {"dataset": {"identifier": r["dataSet"]["identifier"]},
                                       "granularity": r["granularity"].replace("GDC.time.", "").upper(),
                                       "from": r["from"], "to": r["to"]}}
    for kind, key in (("negativeAttributeFilter", "notIn"), ("positiveAttributeFilter", "in")):
        if kind in f:
            a = f[kind]
            return {kind: {"label": {"identifier": a["displayForm"]["identifier"]}, key: {"values": a[key]["values"]}}}
    raise ValueError(f"unsupported filter {f}")


def widgets(layout):
    for s in layout.get("sections", []):
        for it in s.get("items", []):
            w = it.get("widget", {})
            if w.get("type") == "insight":
                yield w
            elif w.get("type") == "IDashboardLayout":
                yield from widgets(w)
            elif w.get("type") == "visualizationSwitcher":
                yield from w.get("visualizations", [])


def run_widget(ws, vis, w):
    c = vis["content"]
    measures, attrs = [], []
    for b in c["buckets"]:
        for it in b["items"]:
            if "measure" in it:
                measures.append(afm_measure(it["measure"]))
            elif "attribute" in it:
                attrs.append({"localIdentifier": it["attribute"]["localIdentifier"],
                              "label": {"identifier": it["attribute"]["displayForm"]["identifier"]}})
    date_ds = (w.get("dateDataSet") or {}).get("identifier", {}).get("id")
    filters = []
    for f in c.get("filters", []):
        af = afm_filter(f)
        if date_ds and "relativeDateFilter" in af and af["relativeDateFilter"]["dataset"]["identifier"]["id"] == date_ds:
            continue
        filters.append(af)
    if date_ds:
        filters.append({"relativeDateFilter": {"dataset": {"identifier": {"id": date_ds, "type": "dataset"}}, **DASH_DATE}})
    dims = ([{"localIdentifier": "d0", "itemIdentifiers": [a["localIdentifier"] for a in attrs]}] if attrs else []) + \
           [{"localIdentifier": "d1", "itemIdentifiers": ["measureGroup"]}]
    body = {"execution": {"attributes": attrs, "filters": filters, "measures": measures}, "resultSpec": {"dimensions": dims}}
    s, r = call("POST", f"/api/v1/actions/workspaces/{ws}/execution/afm/execute", body)
    if s != 200:
        return "ERROR", f"{s} {str(r)[:200]}", 0
    rid = r["executionResponse"]["links"]["executionResult"]
    s, res = call("GET", f"/api/v1/actions/workspaces/{ws}/execution/afm/execute/result/{rid}")
    if s != 200:
        return "ERROR", f"result {s} {str(res)[:200]}", 0
    data = res["data"]
    rows = data if attrs else [data]
    cells = [v for row in rows for v in (row if isinstance(row, list) else [row])]
    nrows = len(rows)
    nulls = sum(1 for v in cells if v is None)
    month_view = any(a["label"]["identifier"]["id"].endswith(".month") for a in attrs)
    months = len({h["attributeHeader"]["labelValue"] for h in res["dimensionHeaders"][0]["headerGroups"][0]["headers"]}) \
        if month_view and attrs[0]["label"]["identifier"]["id"].endswith(".month") else None
    if not cells or nulls == len(cells) or all((v or 0) == 0 for v in cells):
        return "EMPTY", "no data", nrows
    if nulls / len(cells) > 0.3:
        return "GAPS", f"{nulls}/{len(cells)} null cells", nrows
    if months is not None and months < 12:
        return "SHORT", f"{months} months", nrows
    if attrs and not month_view and nrows < 2 and vis["content"]["visualizationUrl"] not in ("local:donut",):
        return "THIN", f"{nrows} row", nrows
    return "OK", (cells[0] if not attrs else ""), nrows


def main():
    s, am = call("GET", f"/api/v1/layout/workspaces/{PARENT}/analyticsModel")
    am = am["analytics"]
    vis = {v["id"]: v for v in am["visualizationObjects"]}
    targets = sys.argv[1:] or [PARENT] + CLIENTS
    jobs = []
    for d in sorted(am["analyticalDashboards"], key=lambda x: x["id"]):
        for w in widgets(d["content"]["layout"]):
            vid = w["insight"]["identifier"]["id"]
            for ws in targets:
                jobs.append((d["title"], vid, ws, w))
    with cf.ThreadPoolExecutor(10) as ex:
        results = list(ex.map(lambda j: (j[0], j[1], j[2], *run_widget(j[2], vis[j[1]], j[3])), jobs))
    summary = {}
    for dash, vid, ws, status, note, n in results:
        summary.setdefault(dash, {}).setdefault(ws, []).append((status, vid, note, n))
    names = {PARENT: "parent"}
    print(f"{'dashboard':<28}" + "".join(f"{names.get(w, w):>13}" for w in targets))
    for dash, per_ws in summary.items():
        print(f"{dash:<28}" + "".join(
            f"{(sum(1 for x in per_ws[w] if x[0] == 'OK'))}/{len(per_ws[w])}".rjust(13) for w in targets))
    print("\nIssues:")
    for dash, vid, ws, status, note, n in sorted(results):
        if status != "OK":
            print(f"  {status:<6} {names.get(ws, ws):<12} {dash:<28} {vid:<24} {note}")
    json.dump(results, open(os.environ.get("CHECK_OUT", "/dev/null"), "w"), default=str)


if __name__ == "__main__":
    main()
