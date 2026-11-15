"""Create or update the three Viventium agents in AI Hub (idempotent).

    python3 demo_app/setup_agents.py

AI is the AI tier's differentiator: Summary and Next Steps go to the AI-tier client (client_riverstone) and
admins; the Compliance agent (ACA, exclusion screening, overtime exposure) to admins and the ACA Compliance
data product group. Analytics-tier and Base-shard users have no USE_AI_ASSISTANT and never see them.
"""
import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l)
TOKEN = ENV["GOODDATA_API_TOKEN"].strip().strip('"')
HOST = "https://sandrasuszterova.demo.cloud.gooddata.com"


def req(method, path, body=None):
    r = urllib.request.Request(HOST + path, method=method, data=json.dumps(body).encode() if body else None,
                               headers={"Authorization": "Bearer " + TOKEN,
                                        "Content-Type": "application/vnd.gooddata.api+json"})
    try:
        with urllib.request.urlopen(r) as x:
            return x.status, x.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def ins(title, content):
    assert len(content) <= 255, (title, len(content))
    return {"title": title, "strategy": "ALWAYS", "content": content}


AGENTS = [
    dict(id="viventium-summary-agent", name="Workforce Summary Agent",
         description="Summarizes payroll, scheduling, recruiting and HR dashboards in 5 bullets: what moved, by how much, at which facility and role.",
         personality="You are a crisp workforce briefer for a post-acute care operator (skilled nursing, home care, hospice). Lead with the headline number, then context. Plain language, no filler.",
         skills=["dashboard_summary", "visualization_summary", "visualization", "key_driver_analysis", "anomaly_detection"],
         instructions=[ins("Format", "Start with a one-line headline containing the key number. Then at most 5 bullets: metric, change vs previous period, and the main driver (facility/location, job role such as CNA, LPN, RN, or shift type)."),
                       ins("Scope", "Only use governed metrics from this workspace. Always state the period and filters. Flag overtime, call-off or turnover spikes and anything else unusual with the word 'Anomaly'.")],
         groups=["client_riverstone", "adminGroup"]),
    dict(id="viventium-next-steps-agent", name="Next Steps Agent",
         description="Turns the numbers into a short staffing and payroll action plan: who does what this week, plus alerts and scheduled exports to keep watching.",
         personality="You are a pragmatic post-acute care operations lead (DON, administrator, payroll and HR). You speak in actions with owners and deadlines, not in analysis.",
         skills=["visualization", "forecasting", "alert", "schedule_export", "visualization_summary", "dashboard_summary"],
         instructions=[ins("Format", "Return 3 numbered next steps. Each: action, owner role (Administrator, DON, Scheduler, Payroll, HR/Recruiting), due date within 2 weeks, and the metric that proves it worked."),
                       ins("Follow-up", "After the steps, offer an alert on the metric to watch (e.g. overtime %, call-off rate, agency cost) or a weekly export of the related dashboard. Ask before creating anything.")],
         groups=["client_riverstone", "adminGroup"]),
    dict(id="viventium-compliance-agent", name="Compliance Agent",
         description="Checks HR compliance risk: ACA offer rate and penalty exposure, exclusion screening matches, overtime and wage-and-hour exposure, with forecasts.",
         personality="You are a careful HR compliance analyst for post-acute care employers. Be precise, cite the metric and period, and separate facts from risk estimates. Never give legal advice.",
         skills=["key_driver_analysis", "anomaly_detection", "forecasting", "what_if_analysis", "visualization", "metric"],
         instructions=[ins("Format", "List at most 3 risks, ranked by exposure. Each: the rule (ACA 95% offer test, OIG/state exclusion, overtime), the evidence with numbers, the facility or role, and 'Exposure: <amount or range>'."),
                       ins("Honesty", "If exposure cannot be estimated from the data, write 'exposure not estimated' instead of guessing. Recommend review by counsel or the compliance officer for any confirmed match.")],
         groups=["adminGroup", "dp_aca_compliance"]),
]

if __name__ == "__main__":
    for a in AGENTS:
        body = {"data": {"id": a["id"], "type": "agent",
                         "attributes": {"enabled": True, "name": a["name"], "description": a["description"],
                                        "personality": a["personality"], "skillsMode": "custom",
                                        "customSkills": a["skills"], "aiKnowledge": True, "availableToAll": False,
                                        "instructions": a["instructions"]},
                         "relationships": {"userGroups": {"data": [{"id": g, "type": "userGroup"} for g in a["groups"]]}}}}
        s, t = req("POST", "/api/v1/entities/agents", body)
        if s == 409:
            s, t = req("PUT", "/api/v1/entities/agents/" + a["id"], body)
        print(a["id"], s, t[:300] if s >= 300 else "ok")
