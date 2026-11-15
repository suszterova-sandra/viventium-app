#!/usr/bin/env python3
"""
Build the Viventium themes and chart palettes, and optionally deploy + activate them.

    python3 theme/build_themes.py               # write JSON files only
    python3 theme/build_themes.py --deploy      # also create/update in the org and activate per workspace
    python3 theme/build_themes.py viventium_hearthside --deploy   # one theme only

Themes (one per workspace; a theme can't be assigned to a single dashboard):
- viventium               -> parent "Viventium" (purple #591490 / #8C21E7, gold #FFB630, Noto Sans, real logo)
- viventium_<client_id>   -> each client's own (fictional) brand. Activated on the dedicated workspaces
                             (riverstone, hearthside); clients in the shared Base shard see the Viventium
                             theme, their brand theme is kept ready for an upgrade to a dedicated workspace.

Structure comes from _template_theme.json (the conference dark-lime template) and is recoloured by role,
exactly like conference_env/theme/build_themes.py, so every theme stays structurally identical.

Data products: every theme carries the same image ids for the publisher reports
  {theme.assets.images.dp_<product>}  product visual (Viventium product imagery)
  {theme.assets.images.cover_bg} / section_bg / accent_bar / logo / spacer
so each per-product report renders in the brand of whichever workspace opens it.
GoodData limits a theme to 15,000 characters.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOST = os.environ.get("GD_HOST", "https://sandrasuszterova.demo.cloud.gooddata.com")
PARENT_WS = "a60f79ad0a99473fafe4d043228d5bd7"
FONT = "https://fonts.gstatic.com/s/notosans/v42/o-0bIpQlx3QUlC5A4PNB6Ryti20_6n1iPHjc5a7du3mhPy0.woff2"
VIV = "https://viventium.com/hs-fs/hubfs/"

# product visuals per data product (same ids in every theme)
PRODUCT_IMAGES = {
    "dp_applicant_tracking": VIV + "applicant-tracking-product-image.webp",
    "dp_onboarding": VIV + "onboarding-product-suite.webp",
    "dp_scheduling": VIV + "scheduling-time-product-suite-image.webp",
    "dp_time_attendance": VIV + "2026%20Marketing/Images/Website/T%26A%20Product%20Suite.png?width=1200",
    "dp_payroll": VIV + "payroll-product-suite-image.webp",
    "dp_on_demand_pay": VIV + "Business-intelligence-product-suite-image.webp",
    "dp_benefits": VIV + "benefits-aca-product-image.webp",
    "dp_aca_compliance": VIV + "ACA-compliance-product-suite-image.webp",
    "dp_lms": VIV + "lms-product-image.webp",
    "dp_exclusion_monitoring": VIV + "HR%20manager%20at%20desk_1%20(1).jpg?width=1200",
    "dp_hr": VIV + "hr-product-image.webp",
}

TEMPLATE_HEX = {  # role -> colour used in the template
    "page": "#0B0D10", "card": "#14171C", "panel": "#1B1F25", "line": "#252A31", "line2": "#343A43",
    "g5": "#4E5560", "g6": "#747C88", "muted": "#9BA3AE", "g8": "#C9CED6", "text": "#F2F4F7",
    "subtle": "#5B636E", "accent": "#D4F24A", "accent_hover": "#C3E635", "accent_dim": "#2A3312",
}


def solid(hex_):
    h = hex_.lstrip("#")
    return f"https://placehold.co/1920x1080/{h}/{h}/png"


def wordmark(name, fg, bg="FFFFFF"):
    return f"https://placehold.co/600x140/{bg}/{fg.lstrip('#')}/png?text={name.replace(' ', '+')}&font=montserrat"


def light(primary, deep, accent, ink, tint, line, viz, header, logo, header_logo=None, bg=None, kpi=None):
    """Light brand theme config: primary (buttons), deep (nav, KPI tiles), accent (highlights)."""
    return {
        "header": header, "primary": primary, "logo": logo, "header_logo": header_logo or logo,
        "bg": bg or solid(deep), "rule": accent.lstrip("#"), "viz": viz,
        "hex": {"page": "#FFFFFF", "card": tint, "panel": tint, "line": line, "line2": line,
                "g5": "#9A98A8", "g6": "#6E6C80", "muted": "#4F4D63", "g8": deep, "text": ink,
                "subtle": "#7E7C90", "accent": primary, "accent_hover": deep, "accent_dim": accent},
        "nav": {"bg": deep, "border": deep, "item": "#E4DDF0" if deep == "#591490" else "#E6E9EE",
                "selected": deep, "selected_bg": accent},
        "kpi_tile": kpi or {"bg": deep, "border": deep, "title": "#E9E3F3", "value": "#FFFFFF",
                            "secondary": "#E9E3F3", "good": "#8FE3C0", "bad": "#FFB3BF"},
        "doc": {"page": tint, "card": "#FFFFFF", "panel": tint},
    }


THEMES = {
    "viventium": dict(name="Viventium", ws=PARENT_WS, brand="Viventium", **light(
        primary="#8C21E7", deep="#591490", accent="#FFB630", ink="#140B42", tint="#FBF8FE", line="#E7DDF5",
        viz=["#591490", "#8C21E7", "#FFB630", "#F42A77", "#A967FF", "#FF7418", "#C62EC2", "#3A394E", "#2F9E7A",
             "#D2C2EE"],
        header=("#FFFFFF", "#3A394E", "#8C21E7"),
        logo=VIV + "viventium-logo.png?width=496&height=96&name=viventium-logo.png",
        bg="https://viventium.com/hubfs/2025%20Marketing/Images/Brand%20Images/manager-in-conversation.jpg",
        kpi={"bg": "#591490", "border": "#591490", "title": "#E4D2FA", "value": "#FFFFFF", "secondary": "#E4D2FA",
             "good": "#8FE3C0", "bad": "#FFB3BF"})),
    "viventium_riverstone": dict(name="Riverstone Health Partners", ws="riverstone", brand="Riverstone Health Partners", **light(
        primary="#1B6F8C", deep="#12355B", accent="#E0A526", ink="#0D2238", tint="#F3F7FA", line="#DCE5EC",
        viz=["#12355B", "#1B8A8C", "#E0A526", "#5B8DB8", "#9FC5C9", "#D9674E", "#6C7A89", "#2F9E7A", "#F2CF7A",
             "#B9C6D3"],
        header=("#12355B", "#FFFFFF", "#E0A526"), logo=wordmark("Riverstone Health", "#12355B"),
        header_logo=wordmark("Riverstone Health", "#FFFFFF", "12355B"))),
    "viventium_maplehollow": dict(name="Maple Hollow Senior Living", ws=None, brand="Maple Hollow Senior Living", **light(
        primary="#A23B2A", deep="#6E1F2A", accent="#E8913A", ink="#2B1215", tint="#FBF6F2", line="#EDE0D8",
        viz=["#6E1F2A", "#D9692B", "#E8B04A", "#8C6A4F", "#C9A27E", "#4F7C6A", "#B5524A", "#3E3A4F", "#F0CFA0",
             "#A38C8C"],
        header=("#FFFFFF", "#6E1F2A", "#D9692B"), logo=wordmark("Maple Hollow", "#6E1F2A"))),
    "viventium_hearthside": dict(name="HearthSide Home Care", ws="hearthside", brand="HearthSide Home Care", **light(
        primary="#C0532F", deep="#2E3A4F", accent="#F2B544", ink="#1E2533", tint="#FBF6F3", line="#EADFD8",
        viz=["#C0532F", "#2E3A4F", "#F2B544", "#7A9CC6", "#E39A7B", "#5E8C6A", "#9A4A3C", "#B9C3D3", "#F7D58C",
             "#6E6A78"],
        header=("#2E3A4F", "#FFFFFF", "#F2B544"), logo=wordmark("HearthSide Home Care", "#C0532F"),
        header_logo=wordmark("HearthSide Home Care", "#FFFFFF", "2E3A4F"))),
    "viventium_willowbend": dict(name="Willowbend Home Health & Hospice", ws=None, brand="Willowbend", **light(
        primary="#3E7A63", deep="#24493D", accent="#B9A3D6", ink="#14261F", tint="#F4F8F5", line="#DCE7E0",
        viz=["#24493D", "#7FA36B", "#B9A3D6", "#3E7A63", "#D8B45C", "#6F8FA8", "#A5C49A", "#7D5E8C", "#C9D6CC",
             "#4F4D63"],
        header=("#24493D", "#FFFFFF", "#B9A3D6"), logo=wordmark("Willowbend", "#24493D"),
        header_logo=wordmark("Willowbend", "#FFFFFF", "24493D"))),
    "viventium_littleoak": dict(name="Little Oak Behavioral Health", ws=None, brand="Little Oak", **light(
        primary="#2E7D4F", deep="#1F5537", accent="#F6C343", ink="#13261A", tint="#F5FAF6", line="#DCEBDF",
        viz=["#2E7D4F", "#F6C343", "#4BA3D9", "#F28B5B", "#8CC084", "#1F5537", "#A98BD6", "#F7DE8F", "#6C7A89",
             "#B6DCC2"],
        header=("#FFFFFF", "#1F5537", "#2E7D4F"), logo=wordmark("Little Oak ABA", "#2E7D4F"))),
}


def doc_colors(h):
    return {"backgrounds": [{"id": "page", "color": h["page"]}, {"id": "card", "color": h["card"]},
                            {"id": "panel", "color": h["panel"]}, {"id": "accent", "color": h["accent"]}],
            "texts": [{"id": "default", "color": h["text"]}, {"id": "muted", "color": h["muted"]},
                      {"id": "subtle", "color": h["subtle"]}, {"id": "accent", "color": h["accent"]},
                      {"id": "inverse", "color": "#FFFFFF"}]}


def recolor(obj, mapping):
    s = json.dumps(obj)
    for old, new in mapping.items():
        s = s.replace(old, new).replace(old.lower(), new)
    return json.loads(s)


def build_theme(cfg):
    base = json.load(open(HERE / "_template_theme.json"))
    hexes, nav = cfg["hex"], cfg["nav"]
    t = recolor({k: v for k, v in base.items() if k not in ("assets", "images")},
                {TEMPLATE_HEX[k]: hexes[k] for k in TEMPLATE_HEX})
    t = json.loads(json.dumps(t).replace('"Inter"', '"Noto Sans"').replace("Inter,", "Noto Sans,"))
    t["typography"] = {"font": FONT, "fontBold": FONT}
    good, bad = "#2F9E7A", "#D1435B"
    t["palette"]["primary"] = {"base": cfg["primary"], "contrast": "#FFFFFF"}
    t["palette"]["error"]["base"], t["palette"]["success"]["base"] = bad, good
    t["kpi"]["value"] = {"positiveColor": good, "negativeColor": bad}
    t["modal"]["outsideBackgroundColor"] = "rgba(0, 0, 0, 0.45)"
    t["dashboards"]["navigation"] = {"title": {"color": "#FFFFFF"}, "backgroundColor": nav["bg"],
                                     "borderColor": nav["border"],
                                     "item": {"color": nav["item"], "hoverColor": "#FFFFFF",
                                              "selectedColor": nav["selected"],
                                              "selectedBackgroundColor": nav["selected_bg"]}}
    for w in ("widget", "kpiWidget"):
        t["dashboards"]["content"][w].update(backgroundColor="#FFFFFF", borderColor=hexes["line"])
    t["dashboards"]["content"]["backgroundColor"] = hexes["card"]
    t["dashboards"]["filterBar"]["backgroundColor"] = "#FFFFFF"
    t["chart"]["backgroundColor"] = "#FFFFFF"
    t["tooltip"] = {"color": "#FFFFFF", "backgroundColor": hexes["text"]}
    t["chart"].update(tooltipBackgroundColor=hexes["text"], tooltipBorderColor=hexes["text"],
                      tooltipLabelColor=hexes["line2"], tooltipValueColor="#FFFFFF")
    k = cfg["kpi_tile"]
    tile = t["dashboards"]["content"]["kpiWidget"]
    tile.update(backgroundColor=k["bg"], borderColor=k["border"])
    tile["title"]["color"] = k["title"]
    tile["kpi"] = {"primaryMeasureColor": k["value"], "secondaryInfoColor": k["secondary"],
                   "value": {"positiveColor": k["good"], "negativeColor": k["bad"]}}
    doc_hex = {**hexes, **cfg["doc"]}
    t["documents"]["colors"] = doc_colors(doc_hex)
    t["documents"]["page"] = {"backgroundColor": doc_hex["page"]}
    t["documents"]["visualizationPalette"] = cfg["viz"]
    img = lambda i, u, ti: {"id": i, "url": u, "title": ti, "altText": ti}
    logo = img("logo", cfg["logo"], f"{cfg['brand']} logo")
    bgs = [img("cover_bg", cfg["bg"], "Cover background"), img("section_bg", cfg["bg"], "Section background")]
    rule = img("accent_bar", f"https://placehold.co/1600x12/{cfg['rule']}/{cfg['rule']}/png", "Accent rule")
    spacer = next(a for a in base["assets"]["images"] if a["id"] == "spacer")  # inline transparent 1x1 PNG
    products = [img(pid, url, pid.replace("dp_", "").replace("_", " ").title()) for pid, url in PRODUCT_IMAGES.items()]
    t["assets"] = {"logos": [logo], "backgrounds": bgs, "images": bgs + [rule, logo, spacer] + products}
    t["images"] = {"logo": f"url({cfg['header_logo']})"}
    h = cfg["header"]
    t["header"] = {"backgroundColor": h[0], "color": h[1], "activeColor": h[2]}
    return t


def palette(viz):
    h = lambda x: {"r": int(x[1:3], 16), "g": int(x[3:5], 16), "b": int(x[5:7], 16)}
    return {"colorPalette": [{"guid": f"{i + 1:02d}", "fill": h(c)} for i, c in enumerate(viz)]}


def api(method, path, body=None):
    req = urllib.request.Request(HOST + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {os.environ['GOODDATA_API_TOKEN']}",
                                          "Content-Type": "application/vnd.gooddata.api+json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def upsert(kind, oid, name, content):
    body = {"data": {"id": oid, "type": kind[:-1], "attributes": {"name": name, "content": content}}}
    code, resp = api("PUT", f"/api/v1/entities/{kind}/{oid}", body)
    if code == 404:
        code, resp = api("POST", f"/api/v1/entities/{kind}", body)
    if code not in (200, 201):
        sys.exit(f"{kind}/{oid}: {code} {resp}")
    return code


def activate(ws, setting_type, ref):
    code, res = api("GET", f"/api/v1/entities/workspaces/{ws}/workspaceSettings?origin=NATIVE")
    existing = next((s for s in res["data"] if s["attributes"]["type"] == setting_type), None) if code == 200 else None
    sid = existing["id"] if existing else f"{setting_type.lower()}_viventium"
    body = {"data": {"id": sid, "type": "workspaceSetting", "attributes": {"type": setting_type, "content": ref}}}
    if existing:
        return api("PUT", f"/api/v1/entities/workspaces/{ws}/workspaceSettings/{sid}", body)[0]
    return api("POST", f"/api/v1/entities/workspaces/{ws}/workspaceSettings", body)[0]


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    for tid, cfg in THEMES.items():
        if only and tid not in only:
            continue
        theme = build_theme(cfg)
        size = len(json.dumps(theme))
        assert size < 15000, f"{tid} is {size} chars (limit 15000)"
        (HERE / f"{tid}_theme.json").write_text(json.dumps(theme, indent=2) + "\n")
        (HERE / f"{tid}_palette.json").write_text(json.dumps(palette(cfg["viz"]), indent=2) + "\n")
        print(f"wrote {tid}_theme.json ({size} chars)")
        if "--deploy" in sys.argv and not cfg["ws"]:
            # client is in the shared Base shard (Viventium theme); the brand theme is kept for an upgrade
            print("  theme", upsert("themes", tid, f"Viventium – {cfg['name']}", theme), "(no workspace: client is in the Base shard)")
        elif "--deploy" in sys.argv:
            print("  theme", upsert("themes", tid, f"Viventium – {cfg['name']}", theme),
                  "| palette", upsert("colorPalettes", tid, f"Viventium – {cfg['name']}", palette(cfg["viz"])),
                  "| ACTIVE_THEME", activate(cfg["ws"], "ACTIVE_THEME", {"id": tid, "type": "theme"}),
                  "| ACTIVE_COLOR_PALETTE", activate(cfg["ws"], "ACTIVE_COLOR_PALETTE",
                                                     {"id": tid, "type": "colorPalette"}),
                  f"-> {cfg['ws']}")


if __name__ == "__main__":
    main()
