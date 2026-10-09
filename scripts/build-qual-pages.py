#!/usr/bin/env python3
"""Build the New Jersey qualification course pages for brassops.com.

Reads data/nj-courses.json (exported from the BrassOps product) and writes:
  qualifications/nj/<slug>.html   one page per course
  qualifications/nj.html          the index
and appends any missing <url> entries for those pages to sitemap.xml.

Re-runnable: every generated file is rewritten from the data; the sitemap
only gains entries it does not already have. Python 3 stdlib only.

    python3 scripts/build-qual-pages.py
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "nj-courses.json")
OUT_DIR = os.path.join(ROOT, "qualifications", "nj")
INDEX_FILE = os.path.join(ROOT, "qualifications", "nj.html")
SITEMAP = os.path.join(ROOT, "sitemap.xml")

SITE = "https://brassops.com"
INDEX_PATH = "/qualifications/nj"
TODAY = date.today().isoformat()
GTAG_ID = "G-KJM9SJ714M"

# The Attorney General's Guidelines page at the Division of Criminal Justice
# (the "Semi-Annual Firearms Qualification and Requalification Standards for
# New Jersey Law Enforcement", issued December 1989, last revised June 2003).
AG_PAGE_URL = "https://www.nj.gov/oag/dcj/agguide/firearms.htm"
AG_PDF_URL = "https://www.nj.gov/oag/dcj/agguide/AGs%20Firearms%20Qualification%20Standards_2003.pdf"

WEAPON_LABEL = {
    "handgun": "Handgun",
    "rifle": "Patrol rifle",
    "shotgun": "Shotgun",
    "subgun": "Subgun",
    "taser": "TASER",
    "less_lethal": "Less lethal",
}
WEAPON_ORDER = ["handgun", "rifle", "shotgun", "subgun", "taser", "less_lethal"]
WEAPON_GROUP_HEADING = {
    "handgun": "Handgun courses",
    "rifle": "Patrol rifle courses",
    "shotgun": "Shotgun courses",
    "subgun": "Subgun courses",
    "taser": "TASER courses",
    "less_lethal": "Less lethal courses",
}


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def condition(course: dict) -> str:
    """Day, Night, or Day or night (lighting-neutral courses like TASER)."""
    p = course["payload"]
    ctx = (p.get("qual_context") or "").lower()
    name = (p.get("name") or "").lower()
    if "night" in ctx or re.search(r"\bnight\b", name):
        return "Night"
    if "day" in ctx or re.search(r"\bday\b", name):
        return "Day"
    return "Day or night"


def is_night(course: dict) -> bool:
    return condition(course) == "Night"


def pass_label(course: dict) -> str:
    p = course["payload"]
    if p.get("scored_by") == "pct" and p.get("pass_pct") is not None:
        return f"{p['pass_pct']}%"
    if p.get("pass_time") is not None:
        return f"{p['pass_time']} s"
    return "Pass / fail"


def total_rounds(course: dict) -> int:
    return sum(int(s.get("rounds") or 0) for s in course["payload"]["stages"])


def distance_span(course: dict) -> str:
    ds = [s.get("distance") for s in course["payload"]["stages"] if s.get("distance") is not None]
    if not ds:
        return ""
    lo, hi = min(ds), max(ds)
    if lo == hi:
        return f"{lo} yards"
    return f"{lo} to {hi} yards"


def course_url(course: dict) -> str:
    return f"{INDEX_PATH}/{course['slug']}"


def weapon(course: dict) -> str:
    return WEAPON_LABEL.get(course["payload"].get("category"), "Firearm")


def course_code(course: dict) -> str | None:
    """A short description like 'HQC-1' or 'ARQC' is a course code."""
    d = (course["payload"].get("description") or "").strip()
    if d and len(d) <= 12 and " " not in d:
        return d
    return None


def long_description(course: dict) -> str | None:
    d = (course["payload"].get("description") or "").strip()
    if d and course_code(course) is None:
        return d
    return None


# ---------------------------------------------------------------- page shell

HEAD_CSS = """
  :root { --red: #ef4444; --red-dim: rgba(239,68,68,0.08); --navy: #111111; --text: #1a1a1a; --text-light: #444444; --accent: #ef4444; --border: #e4e4e7; --bg: #ffffff; --green: #16a34a; --brass: #ef4444; --brass-light: #fecaca; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Barlow', sans-serif; color: var(--text); background: var(--bg); line-height: 1.8; font-size: 17px; }
  .breadcrumb { font-family: 'Rajdhani', sans-serif; font-size: 13px; color: #666; max-width: 780px; margin: 0 auto; padding: 76px 24px 0; }
  .breadcrumb a { color: var(--accent); text-decoration: none; } .breadcrumb span { margin: 0 6px; }
  .hero { max-width: 780px; margin: 0 auto; padding: 24px 24px 40px; border-bottom: 3px solid var(--accent); }
  .hero-badge { display: inline-block; font-family: 'Rajdhani', sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; background: var(--accent); color: #fff; padding: 5px 14px; border-radius: 4px; margin-bottom: 20px; }
  .hero h1 { font-family: 'Rajdhani', sans-serif; font-size: clamp(28px, 4.5vw, 40px); font-weight: 700; line-height: 1.18; color: var(--navy); margin-bottom: 16px; }
  .hero-subtitle { font-size: 18px; color: #333; line-height: 1.6; }
  .hero-meta { margin-top: 22px; display: flex; flex-wrap: wrap; gap: 20px; font-family: 'Rajdhani', sans-serif; font-size: 14px; color: #666; align-items: center; }
  .hero-meta strong { color: var(--text); } .hero-meta .divider { width: 1px; height: 16px; background: var(--border); }
  article { max-width: 780px; margin: 0 auto; padding: 48px 24px 32px; }
  article h2 { font-family: 'Rajdhani', sans-serif; font-size: 26px; font-weight: 700; color: var(--navy); margin: 48px 0 16px; padding-top: 8px; border-top: 1px solid var(--border); }
  article h2:first-of-type { border-top: none; margin-top: 0; }
  article h3 { font-family: 'Rajdhani', sans-serif; font-size: 19px; font-weight: 700; color: #333; margin: 32px 0 10px; }
  article p { margin-bottom: 20px; }
  article a { color: var(--accent); text-decoration: underline; text-decoration-color: rgba(239,68,68,0.3); text-underline-offset: 3px; }
  article a:hover { text-decoration-color: var(--accent); }
  article ul, article ol { margin: 0 0 20px 24px; } article li { margin-bottom: 8px; }
  .callout { border-left: 4px solid var(--accent); background: var(--red-dim); padding: 18px 22px; margin: 24px 0; border-radius: 0 8px 8px 0; }
  .callout p { margin-bottom: 0; font-size: 16px; } .callout strong { color: var(--navy); }
  .standards { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; margin: 0 0 8px; }
  .standards .stat { background: #f9fafb; border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }
  .standards .stat .k { font-family: 'Rajdhani', sans-serif; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--accent); margin-bottom: 4px; }
  .standards .stat .v { font-family: 'Rajdhani', sans-serif; font-size: 24px; font-weight: 700; color: var(--navy); line-height: 1.1; }
  .standards .stat .v small { font-size: 13px; font-weight: 600; color: #666; margin-left: 4px; }
  .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 20px 0; }
  table { width: 100%; border-collapse: collapse; margin: 0; font-size: 15px; }
  th { background: #f3f4f6; font-family: 'Rajdhani', sans-serif; font-weight: 700; text-align: left; padding: 10px 14px; border-bottom: 2px solid var(--border); white-space: nowrap; }
  td { padding: 10px 14px; border-bottom: 1px solid var(--border); vertical-align: top; }
  td.num, th.num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
  tfoot td { font-weight: 700; background: #f9fafb; }
  .table-note { font-size: 14px; color: #666; line-height: 1.6; margin: 12px 0 0; }
  .cta-block { background: linear-gradient(135deg, #dc2626, #ef4444); padding: 36px 32px; border-radius: 12px; margin: 44px 0; text-align: center; }
  .cta-block h3 { font-family: 'Rajdhani', sans-serif; font-size: 22px; color: #fff; margin: 0 0 10px; }
  .cta-block p { color: rgba(255,255,255,0.85); font-size: 15px; margin-bottom: 22px; max-width: 500px; margin-left: auto; margin-right: auto; }
  .cta-btn { display: inline-block; font-family: 'Rajdhani', sans-serif; font-size: 15px; font-weight: 700; color: #dc2626; background: #fff; padding: 13px 34px; border-radius: 8px; text-decoration: none; letter-spacing: 0.5px; text-transform: uppercase; }
  .cta-btn:hover { background: #f5f5f5; }
  .cta-secondary { display: block; margin-top: 14px; font-family: 'Rajdhani', sans-serif; font-size: 14px; font-weight: 600; color: #fff !important; text-decoration: underline; text-decoration-color: rgba(255,255,255,0.5) !important; }
  .related-section { max-width: 780px; margin: 0 auto; padding: 40px 24px 20px; border-top: 2px solid var(--accent); }
  .related-label { font-family: 'Rajdhani', sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--accent); margin-bottom: 18px; }
  .related-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; }
  .related-card { border: 1px solid var(--border); border-radius: 8px; padding: 18px; }
  .related-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.06); }
  .related-card .card-type { font-family: 'Rajdhani', sans-serif; font-size: 10px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--accent); margin-bottom: 6px; }
  .related-card h4 { font-family: 'Rajdhani', sans-serif; font-size: 16px; font-weight: 600; line-height: 1.35; margin-bottom: 6px; }
  .related-card h4 a { color: var(--navy); text-decoration: none; } .related-card h4 a:hover { color: var(--accent); }
  .related-card p { font-size: 13px; color: #666; line-height: 1.5; margin-bottom: 0; }
  .course-list a.course-link { color: var(--navy); font-weight: 600; text-decoration: none; }
  .course-list a.course-link:hover { color: var(--accent); }
  /* Nav */
  .site-nav { position: fixed; top: 0; left: 0; right: 0; z-index: 100; display: flex; align-items: center; justify-content: space-between; padding: 0 clamp(1rem,4vw,3rem); height: 56px; background: rgba(10,10,10,0.95); backdrop-filter: blur(20px); border-bottom: 1px solid rgba(255,255,255,0.06); }
  .site-nav .nb { font-family: 'Rajdhani', sans-serif; font-weight: 700; font-size: 1.1rem; color: #ededed; text-decoration: none; letter-spacing: 0.04em; }
  .site-nav .nb .bo { color: #ef4444; }
  .site-nav .nl { display: flex; gap: 1.5rem; align-items: center; }
  .site-nav .nl a { font-family: 'Barlow', sans-serif; font-size: 0.85rem; font-weight: 500; color: #71717a; text-decoration: none; }
  .site-nav .nl a:hover { color: #ededed; }
  .site-nav .nl .la { background: linear-gradient(135deg,#ef4444,#dc2626); color: #fff !important; padding: 0.35rem 1rem; border-radius: 8px; font-weight: 600; font-size: 0.8rem; }
  .hb { display: none; background: none; border: none; cursor: pointer; padding: 0.4rem; z-index: 110; }
  .hb svg { width: 22px; height: 22px; stroke: #ededed; stroke-width: 2; fill: none; }
  @media(max-width:768px) { .hb { display: block; } .site-nav .nl { display: none; flex-direction: column; align-items: stretch; gap: 0; position: fixed; top: 56px; left: 0; right: 0; background: rgba(10,10,10,0.95); backdrop-filter: blur(24px); border-bottom: 1px solid rgba(255,255,255,0.08); padding: 0.5rem 0; max-height: 0; overflow: hidden; transition: max-height 0.35s; } .site-nav .nl.open { display: flex; max-height: 400px; padding: 0.75rem 0; } .site-nav .nl a { padding: 0.75rem clamp(1rem,4vw,3rem); font-size: 0.95rem; border-bottom: 1px solid rgba(255,255,255,0.04); } .site-nav .nl .la { margin: 0.5rem clamp(1rem,4vw,3rem) 0.25rem; text-align: center; padding: 0.65rem 1rem; border-radius: 10px; } }
  /* Footer */
  .site-footer { background: #0a0a0a; color: #71717a; padding: 3rem 1.5rem 2.5rem; text-align: center; }
  .site-footer .fb { font-family: 'Rajdhani', sans-serif; font-size: 1.1rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #71717a; margin-bottom: 0.5rem; }
  .site-footer .fb .bo { color: #ef4444; }
  .site-footer .tl { font-size: 0.8rem; color: #52525b; margin-bottom: 0.75rem; font-style: italic; }
  .site-footer .fl { display: flex; flex-wrap: wrap; justify-content: center; gap: 1.5rem; margin-bottom: 0.75rem; }
  .site-footer .fl a { font-size: 0.75rem; color: #52525b; text-decoration: underline; }
  .site-footer .fl a:hover { color: #a1a1aa; }
  .site-footer .cp { font-size: 0.7rem; color: #52525b; }
  @media (max-width: 600px) { .hero h1 { font-size: 26px; } .hero { padding: 20px 16px 32px; } article { padding: 32px 16px 24px; } }
"""

NAV = f"""<nav class="site-nav">
  <a href="{SITE}" class="nb">Brass<span class="bo">Ops</span></a>
  <button class="hb" aria-label="Toggle menu" aria-expanded="false"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg></button>
  <div class="nl">
    <a href="{SITE}/why-brassops">Why Brass<span style="color:#ef4444">Ops</span></a>
    <a href="{SITE}/briefing">Briefing</a>
    <a href="{SITE}/faq">FAQ</a>
    <a href="{SITE}/contact">Contact</a>
    <a href="https://app.brassops.com" class="la" target="_blank" rel="noopener">Launch App</a>
  </div>
</nav>"""

FOOTER = f"""<footer class="site-footer">
  <p class="fb">Brass<span class="bo">Ops</span></p>
  <p class="tl">Built for those who train to protect.</p>
  <div class="fl"><a href="{SITE}/privacy">Privacy Policy</a><a href="{SITE}/terms">Terms of Service</a><a href="{SITE}{INDEX_PATH}">NJ Qualification Courses</a><a href="{SITE}/resources">Resources</a></div>
  <p class="cp">&copy; 2026 BrassOps. All rights reserved.</p>
</footer>
<script>
document.addEventListener('DOMContentLoaded',()=>{{
  const h=document.querySelector('.hb'),n=document.querySelector('.nl');
  if(h&&n)h.addEventListener('click',()=>{{const o=n.classList.toggle('open');h.setAttribute('aria-expanded',o);h.innerHTML=o?'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>':'<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>';}});
}});
</script>"""


def head(title: str, description: str, path: str, jsonld: list[dict], og_type: str) -> str:
    url = f"{SITE}{path}"
    ld = "\n".join(
        '<script type="application/ld+json">\n' + json.dumps(d, indent=2, ensure_ascii=False) + "\n</script>"
        for d in jsonld
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GTAG_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GTAG_ID}');
</script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="BrassOps">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
{ld}

<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700;800&family=Rajdhani:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{HEAD_CSS}</style>
</head>
<body>
{NAV}
"""


def breadcrumb_ld(items: list[tuple[str, str | None]]) -> dict:
    out = []
    for i, (name, url) in enumerate(items, 1):
        item = {"@type": "ListItem", "position": i, "name": name}
        if url:
            item["item"] = url
        out.append(item)
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": out}


# ---------------------------------------------------------------- course page

def defensible_record_section(course: dict) -> str:
    p = course["payload"]
    name = esc(p["name"])
    pct = pass_label(course)
    night = is_night(course)
    items = [
        "<li><strong>The officer.</strong> Name and badge or ID number, so the record cannot be confused with another officer of the same surname.</li>",
        f"<li><strong>The weapon, by serial number.</strong> Make, model, caliber and serial of the {esc(weapon(course)).lower()} the officer actually fired, not the one on the assignment sheet. If the officer qualified on a loaner, the record says so.</li>",
        "<li><strong>The date and the instructor.</strong> When the course was fired and which instructor ran the line and signed the score, with that instructor's certification current on that date.</li>",
        f"<li><strong>The score against the standard in force that day.</strong> Hits, rounds fired and the resulting percentage, judged against the pass standard that applied when the course was fired ({esc(pct)} here as modelled). If the agency later raises or lowers the standard, the old record keeps the standard it was judged by; it is never re-scored.</li>",
        "<li><strong>Pass or fail, and what followed a fail.</strong> A failed attempt is a record too. It stays in the file alongside the remedial training that followed it and the date of the successful re-fire, so the chain from failure to remediation to qualification is visible on its own page.</li>",
    ]
    if night:
        items.append(
            "<li><strong>The lighting condition.</strong> This is a night course, so the record states that it was fired under low light conditions, whether natural or simulated, and the handheld or weapon-mounted light the officer used. A night qualification logged without a lighting condition is indistinguishable from a day course.</li>"
        )
    else:
        items.append(
            "<li><strong>The lighting condition.</strong> Even on a day course, record the condition the course was fired under. It separates this attempt from the officer's night qualification on the same weapon and keeps the two records from being confused.</li>"
        )
    return f"""
<h2 id="record">What a defensible record of this course contains</h2>
<p>A qualification score on its own proves very little. When a {name} record is pulled for an internal inquiry, a discovery request or a civil suit, the questions are about what the number is attached to. A record that survives that scrutiny contains:</p>
<ul>
{chr(10).join(items)}
</ul>
<p>Every field above is something an instructor already knows on the day. The failure mode is not ignorance; it is a paper scorecard or a spreadsheet that never asked for the serial number, the lighting condition or the standard in force, and cannot produce them two years later.</p>
"""


def course_table(course: dict) -> str:
    p = course["payload"]
    rows = []
    for i, s in enumerate(p["stages"], 1):
        dist = s.get("distance")
        dist_txt = f"{dist} yd" if dist is not None else ""
        rows.append(
            "    <tr>"
            f"<td class=\"num\">{i}</td>"
            f"<td>{esc(s.get('name'))}</td>"
            f"<td class=\"num\">{esc(dist_txt)}</td>"
            f"<td class=\"num\">{esc(s.get('rounds'))}</td>"
            f"<td>{esc(s.get('description'))}</td>"
            "</tr>"
        )
    return f"""<div class="table-wrap">
<table>
  <thead>
    <tr><th class="num">Stage</th><th>Position / name</th><th class="num">Distance</th><th class="num">Rounds</th><th>Description</th></tr>
  </thead>
  <tbody>
{chr(10).join(rows)}
  </tbody>
  <tfoot>
    <tr><td colspan="3">Total</td><td class="num">{total_rounds(course)}</td><td>{len(p['stages'])} stages, pass standard {esc(pass_label(course))}</td></tr>
  </tfoot>
</table>
</div>
<p class="table-note">Course of fire as modelled in BrassOps. Confirm stage details against the current <a href="{AG_PAGE_URL}" rel="noopener">Attorney General firearms qualification standards</a> before use.</p>
"""


def siblings_section(course: dict, courses: list[dict]) -> str:
    cards = []
    for c in courses:
        if c["slug"] == course["slug"]:
            continue
        cards.append(
            f"""    <div class="related-card">
      <div class="card-type">{esc(weapon(c))} &middot; {esc(condition(c))}</div>
      <h4><a href="{course_url(c)}">{esc(c['payload']['name'])}</a></h4>
      <p>{len(c['payload']['stages'])} stages, {total_rounds(c)} rounds, pass {esc(pass_label(c))}.</p>
    </div>"""
        )
    return f"""<section class="related-section">
  <div class="related-label">Other New Jersey courses</div>
  <div class="related-grid">
{chr(10).join(cards)}
  </div>
  <p style="margin-top:18px;font-size:14px;"><a href="{INDEX_PATH}" style="color:var(--accent);">All New Jersey qualification courses</a></p>
</section>
"""


def course_page(course: dict, courses: list[dict]) -> str:
    p = course["payload"]
    name = p["name"]
    w = weapon(course)
    cond = condition(course)
    n_stages = len(p["stages"])
    rounds = total_rounds(course)
    pct = pass_label(course)
    span = distance_span(course)
    code = course_code(course)
    longdesc = long_description(course)
    path = course_url(course)
    url = f"{SITE}{path}"

    title = f"{name}: New Jersey police firearms qualification course of fire | BrassOps"
    cond_phrase = {"Day": "day", "Night": "night", "Day or night": "day or night"}[cond]
    description = (
        f"{name}: the New Jersey {w.lower()} {cond_phrase} qualification course of fire, stage by stage. "
        f"{n_stages} stages, {rounds} rounds, {pct} to pass. What a defensible record of it contains."
    )
    if len(description) > 160:
        description = f"{name}: New Jersey {w.lower()} {cond_phrase} qualification course of fire. {n_stages} stages, {rounds} rounds, {pct} to pass."

    jsonld = [
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": f"{name}: New Jersey police firearms qualification course of fire",
            "description": description,
            "author": {"@type": "Organization", "name": "BrassOps", "url": SITE},
            "publisher": {"@type": "Organization", "name": "BrassOps", "url": SITE},
            "datePublished": "2026-10-09",
            "dateModified": TODAY,
            "mainEntityOfPage": url,
        },
        breadcrumb_ld([("Home", f"{SITE}/"), ("NJ Qualification Courses", f"{SITE}{INDEX_PATH}"), (name, None)]),
    ]

    intro_bits = [f"<strong>{esc(name)}</strong> is the New Jersey {esc(w).lower()} {cond_phrase} qualification course as modelled in BrassOps"]
    if code:
        intro_bits[0] += f", course code {esc(code)}"
    intro_bits[0] += f": {n_stages} stages and {rounds} rounds"
    if span:
        intro_bits[0] += f", fired from {esc(span)}"
    intro_bits[0] += f", with a pass standard of {esc(pct)}."
    if longdesc:
        intro_bits.append(esc(longdesc) + ("" if longdesc.endswith(".") else "."))
    intro = " ".join(intro_bits)

    night_note = ""
    if cond == "Night":
        night_note = (
            "<div class=\"callout\"><p><strong>Night course.</strong> The Attorney General's standards define night firing as low light conditions, "
            "either natural subdued lighting or simulated subdued lighting, and require a handheld or weapon-mounted light on the handgun night course. "
            "Record the condition and the light with every score.</p></div>\n"
        )

    body = f"""<nav class="breadcrumb"><a href="{SITE}/">Home</a> <span>&rsaquo;</span> <a href="{INDEX_PATH}">NJ Qualification Courses</a> <span>&rsaquo;</span> <strong>{esc(name)}</strong></nav>

<header class="hero">
  <div class="hero-badge">New Jersey &middot; {esc(w)} &middot; {esc(cond)}</div>
  <h1>{esc(name)}: New Jersey police firearms qualification course of fire</h1>
  <p class="hero-subtitle">{intro}</p>
  <div class="hero-meta">
    <span>Weapon <strong>{esc(w)}</strong></span> <div class="divider"></div>
    <span>Condition <strong>{esc(cond)}</strong></span> <div class="divider"></div>
    <span>Updated <strong>{TODAY}</strong></span>
  </div>
</header>

<article>
<h2 id="standards">Standards at a glance</h2>
<div class="standards">
  <div class="stat"><div class="k">Pass standard</div><div class="v">{esc(pct)}</div></div>
  <div class="stat"><div class="k">Total rounds</div><div class="v">{rounds}</div></div>
  <div class="stat"><div class="k">Stages</div><div class="v">{n_stages}</div></div>
  <div class="stat"><div class="k">Weapon type</div><div class="v" style="font-size:20px;">{esc(w)}</div></div>
  <div class="stat"><div class="k">Condition</div><div class="v" style="font-size:20px;">{esc(cond)}</div></div>
</div>

<h2 id="course-of-fire">Course of fire</h2>
{night_note}{course_table(course)}
{defensible_record_section(course)}
<div class="callout">
  <p><strong>The documentation checklist.</strong> What the Attorney General's Standards require in the file for every course on this page, as a tick list with the section cited for each item: courses and scores, the Firearms Record fields, what to keep when an officer fails, instructor records, the annual report. <a href="/resources/nj-qualification-checklist">Get the NJ qualification checklist (PDF)</a>.</p>
</div>
<div class="cta-block">
  <h3>Track this course in BrassOps</h3>
  <p>{esc(name)} is already in the BrassOps library. Log every officer against it, with the serial number, the instructor, the lighting condition and the standard in force, and pull the record in seconds when someone asks.</p>
  <a href="/demo" class="cta-btn">Book a demo</a>
  <a href="/assessment" class="cta-secondary">Or take the two-minute records assessment</a>
</div>
</article>

{siblings_section(course, courses)}
{FOOTER}
</body>
</html>
"""
    return head(title, description, path, jsonld, "article") + body


# ---------------------------------------------------------------- index page

def index_page(courses: list[dict]) -> str:
    title = "New Jersey police firearms qualification courses: HQC-1, HNQC, ARQC and more | BrassOps"
    description = (
        "Every New Jersey law enforcement firearms qualification course of fire as modelled in BrassOps: "
        "handgun, patrol rifle, shotgun, subgun, TASER and less lethal, day and night, with rounds, stages and pass standards."
    )
    path = INDEX_PATH
    url = f"{SITE}{path}"
    jsonld = [
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "New Jersey police firearms qualification courses",
            "description": description,
            "url": url,
            "publisher": {"@type": "Organization", "name": "BrassOps", "url": SITE},
            "dateModified": TODAY,
        },
        breadcrumb_ld([("Home", f"{SITE}/"), ("NJ Qualification Courses", None)]),
    ]

    groups: dict[str, list[dict]] = {}
    for c in courses:
        groups.setdefault(c["payload"].get("category") or "other", []).append(c)
    order = [k for k in WEAPON_ORDER if k in groups] + [k for k in groups if k not in WEAPON_ORDER]

    sections = []
    for key in order:
        items = sorted(groups[key], key=lambda c: (condition(c) != "Day", c["payload"]["name"]))
        rows = []
        for c in items:
            rows.append(
                "    <tr>"
                f"<td><a class=\"course-link\" href=\"{course_url(c)}\">{esc(c['payload']['name'])}</a></td>"
                f"<td>{esc(weapon(c))}</td>"
                f"<td>{esc(condition(c))}</td>"
                f"<td class=\"num\">{len(c['payload']['stages'])}</td>"
                f"<td class=\"num\">{total_rounds(c)}</td>"
                f"<td class=\"num\">{esc(pass_label(c))}</td>"
                "</tr>"
            )
        heading = WEAPON_GROUP_HEADING.get(key, key.replace("_", " ").title() + " courses")
        sections.append(
            f"""<h2 id="{esc(key)}">{esc(heading)}</h2>
<div class="table-wrap course-list">
<table>
  <thead><tr><th>Course</th><th>Weapon</th><th>Condition</th><th class="num">Stages</th><th class="num">Rounds</th><th class="num">Pass</th></tr></thead>
  <tbody>
{chr(10).join(rows)}
  </tbody>
</table>
</div>"""
        )

    body = f"""<nav class="breadcrumb"><a href="{SITE}/">Home</a> <span>&rsaquo;</span> <strong>NJ Qualification Courses</strong></nav>

<header class="hero">
  <div class="hero-badge">New Jersey &middot; Qualification courses</div>
  <h1>New Jersey police firearms qualification courses of fire</h1>
  <p class="hero-subtitle">The {len(courses)} New Jersey law enforcement qualification courses as modelled in BrassOps, grouped by weapon: stages, rounds, pass standard and whether the course is fired by day or at night. Each course has its own page with the full stage table.</p>
  <div class="hero-meta">
    <span><strong>{len(courses)}</strong> courses</span> <div class="divider"></div>
    <span>Updated <strong>{TODAY}</strong></span>
  </div>
</header>

<article>
<h2 id="about">Semi-annual qualification in New Jersey</h2>
<p>New Jersey law enforcement firearms qualification runs under the Attorney General's <a href="{AG_PAGE_URL}" rel="noopener">Semi-Annual Firearms Qualification and Requalification Standards for New Jersey Law Enforcement</a>, issued in December 1989 and revised through June 2003, which every agency in the state is directed to adopt as its own policy. The standards define a semi-annual program as two prescribed qualification sessions within a 12-month period with at least three months between them. Handgun qualification includes a day course and a Handgun Night Qualification Course (HNQC), fired under low light conditions, natural or simulated, with a handheld or weapon-mounted light and a passing score of 80% or higher; shotgun qualification likewise has day and subdued light courses. The twice-yearly requirement was adjusted to a single round for 2020 and again for 2021 by Attorney General directives. The courses below are the versions modelled in BrassOps; confirm each against the <a href="{AG_PDF_URL}" rel="noopener">current standards document</a> before use.</p>

{chr(10).join(sections)}

<p class="table-note">Courses of fire as modelled in BrassOps. Confirm stage details against the current <a href="{AG_PAGE_URL}" rel="noopener">Attorney General firearms qualification standards</a> before use.</p>

<div class="callout">
  <p><strong>The documentation checklist.</strong> What the Attorney General's Standards require in the file for every course on this page, as a tick list with the section cited for each item: courses and scores, the Firearms Record fields, what to keep when an officer fails, instructor records, the annual report. <a href="/resources/nj-qualification-checklist">Get the NJ qualification checklist (PDF)</a>.</p>
</div>
<div class="cta-block">
  <h3>Track every course in BrassOps</h3>
  <p>All {len(courses)} New Jersey courses ship in the BrassOps library. Log officers against them by serial number, instructor, lighting condition and the standard in force, and the record is ready when someone asks for it.</p>
  <a href="/demo" class="cta-btn">Book a demo</a>
  <a href="/assessment" class="cta-secondary">Or take the two-minute records assessment</a>
</div>
</article>

{FOOTER}
</body>
</html>
"""
    return head(title, description, path, jsonld, "website") + body


# ---------------------------------------------------------------- sitemap

def update_sitemap(paths: list[str]) -> int:
    with open(SITEMAP, encoding="utf-8") as f:
        xml = f.read()
    added = 0
    entries = []
    for p in paths:
        loc = f"{SITE}{p}"
        if f"<loc>{loc}</loc>" in xml:
            continue
        entries.append(
            "  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{TODAY}</lastmod>\n"
            "    <changefreq>monthly</changefreq>\n"
            "    <priority>0.7</priority>\n"
            "  </url>\n"
        )
        added += 1
    if entries:
        idx = xml.rindex("</urlset>")
        xml = xml[:idx] + "".join(entries) + xml[idx:]
        with open(SITEMAP, "w", encoding="utf-8") as f:
            f.write(xml)
    return added


# ---------------------------------------------------------------- main

def main() -> int:
    with open(DATA, encoding="utf-8") as f:
        courses = json.load(f)
    courses = sorted(courses, key=lambda c: (WEAPON_ORDER.index(c["payload"].get("category")) if c["payload"].get("category") in WEAPON_ORDER else 99, condition(c) != "Day", c["payload"]["name"]))

    os.makedirs(OUT_DIR, exist_ok=True)
    written = []
    for c in courses:
        out = os.path.join(OUT_DIR, f"{c['slug']}.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(course_page(c, courses))
        written.append(out)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(index_page(courses))
    written.append(INDEX_FILE)

    added = update_sitemap([INDEX_PATH] + [course_url(c) for c in courses])

    for w in written:
        print("wrote", os.path.relpath(w, ROOT))
    print(f"sitemap: {added} entries added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
