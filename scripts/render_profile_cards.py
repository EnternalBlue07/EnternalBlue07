#!/usr/bin/env python3
"""Render responsive, theme-aware SVG cards for the EnternalBlue07 profile README."""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import urllib.request
from pathlib import Path

LOGIN = "EnternalBlue07"
OUT = Path("cards")
OUT.mkdir(exist_ok=True)
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    raise SystemExit("GH_TOKEN or GITHUB_TOKEN is required")

def request_json(url: str, method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "EnternalBlue07-profile-card-renderer",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())

today = dt.datetime.now(dt.timezone.utc).date()
start = today - dt.timedelta(days=364)
query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { contributionCount date }
        }
        weeks { firstDay }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes { name description url stargazerCount primaryLanguage { name } updatedAt isPrivate }
    }
  }
}
"""
payload = {"query": query, "variables": {
    "login": LOGIN,
    "from": dt.datetime.combine(start, dt.time.min, tzinfo=dt.timezone.utc).isoformat(),
    "to": dt.datetime.combine(today, dt.time.max, tzinfo=dt.timezone.utc).isoformat(),
}}
gql = request_json("https://api.github.com/graphql", "POST", payload)
if gql.get("errors"):
    raise SystemExit("GitHub GraphQL error: " + json.dumps(gql["errors"]))
user = gql["data"]["user"]
calendar = user["contributionsCollection"]["contributionCalendar"]
days = [day for week in calendar["weeks"] for day in week["contributionDays"]]
repo_nodes = [repo for repo in user["repositories"]["nodes"] if not repo["isPrivate"]]
repo_by_name = {repo["name"].lower(): repo for repo in repo_nodes}

def esc(value):
    return html.escape(str(value), quote=True)

def write(name: str, svg: str):
    (OUT / name).write_text(svg, encoding="utf-8")

def card_start(width=1080, height=300, label=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(label)}">
<defs>
 <linearGradient id="surface" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F8FAFC"/><stop offset="1" stop-color="#EEF2F7"/></linearGradient>
 <linearGradient id="darkSurface" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#101827"/><stop offset="1" stop-color="#0B1220"/></linearGradient>
 <style>
   .bg{{fill:url(#surface)}} .ink{{fill:#101827}} .muted{{fill:#667085}} .blue{{fill:#315BFF}}
   .dark .bg{{fill:url(#darkSurface)}} .dark .ink{{fill:#F8FAFC}} .dark .muted{{fill:#94A3B8}}
   .serif{{font-family:Georgia,'Times New Roman',serif;letter-spacing:-1.8px}}
   .sans{{font-family:Inter,ui-sans-serif,Arial,sans-serif}}
   .mono{{font-family:'SFMono-Regular',Consolas,monospace;letter-spacing:1px}}
 </style>
</defs>
<g class="light"><rect class="bg" x="0" y="0" width="{width}" height="{height}" rx="22"/></g>
<g class="dark" style="display:none"><rect class="bg" x="0" y="0" width="{width}" height="{height}" rx="22"/></g>
'''
# GitHub SVG embeds don't reliably honor prefers-color-scheme CSS; use clean light cards
# with a restrained blue palette that remains legible in both profile themes.

# Contribution heatmap, 53 columns x 7 rows.
weeks = calendar["weeks"]
cell = 16
gap = 3
left, top = 54, 94
palette = ["#E7ECF4", "#C7D3FF", "#91A8FF", "#5F80FF", "#315BFF"]
max_count = max((d["contributionCount"] for d in days), default=1)
def level(count):
    if count <= 0: return 0
    ratio = count / max_count
    return 1 if ratio <= .2 else 2 if ratio <= .4 else 3 if ratio <= .7 else 4

heat = [card_start(1080, 302, "Daily GitHub contributions over the last 12 months")]
heat += [
 '<text x="54" y="52" class="ink serif" font-size="36">Every day, <tspan fill="#315BFF" font-style="italic">in blue</tspan></text>',
 '<text x="1026" y="44" text-anchor="end" class="muted mono" font-size="13">REFRESHED DAILY</text>',
]
for wi, week in enumerate(weeks):
    for di, day in enumerate(week["contributionDays"]):
        x = left + wi * (cell + gap)
        y = top + di * (cell + gap)
        count = day["contributionCount"]
        heat.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" fill="{palette[level(count)]}"><title>{esc(day["date"])}: {count} contributions</title></rect>')
for month in range(12):
    date = start + dt.timedelta(days=month * 30)
    x = left + (date - start).days / 7 * (cell + gap)
    heat.append(f'<text x="{x:.1f}" y="284" class="muted mono" font-size="12">{date.strftime("%b")}</text>')
heat.append('<text x="1026" y="284" text-anchor="end" class="muted mono" font-size="12">LESS</text>')
for i, color in enumerate(palette):
    heat.append(f'<rect x="{1034+i*18}" y="270" width="14" height="14" rx="3" fill="{color}"/>')
heat.append('<text x="1068" y="284" class="muted mono" font-size="12">MORE</text></svg>')
write("heatmap.svg", "".join(heat))

# Monthly contribution bars plus current streak and busiest day.
months = []
for offset in range(11, -1, -1):
    month_start = (today.replace(day=1) - dt.timedelta(days=offset * 30)).replace(day=1)
    if month_start.month == 12:
        next_month = dt.date(month_start.year + 1, 1, 1)
    else:
        next_month = dt.date(month_start.year, month_start.month + 1, 1)
    val = sum(d["contributionCount"] for d in days if month_start.isoformat() <= d["date"] < next_month.isoformat())
    months.append((month_start.strftime("%b"), val))
peak = max((d["contributionCount"] for d in days), default=0)
busy = next((d["date"] for d in reversed(days) if d["contributionCount"] == peak), "—")
current_streak = 0
for day in reversed(days):
    if day["contributionCount"] > 0:
        current_streak += 1
    elif day["date"] != today.isoformat():
        break
monthly = [card_start(1080, 390, "Monthly GitHub contribution activity")]
monthly += [
 '<text x="54" y="54" class="muted mono" font-size="13">THE LAST 12 MONTHS ON GITHUB</text>',
 f'<text x="54" y="115" class="ink serif" font-size="52">{calendar["totalContributions"]:,} <tspan font-style="italic">contributions</tspan></text>',
]
chart_x, base_y, bar_w, bar_gap = 56, 330, 42, 20
max_month = max((v for _, v in months), default=1) or 1
for i, (label, value) in enumerate(months):
    h = max(2, int(176 * value / max_month))
    x = chart_x + i * (bar_w + bar_gap)
    y = base_y - h
    color = "#315BFF" if i == max(range(len(months)), key=lambda j: months[j][1]) else "#151922"
    monthly.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" rx="6" fill="{color}"><title>{label}: {value} contributions</title></rect>')
    monthly.append(f'<text x="{x+bar_w/2}" y="356" text-anchor="middle" class="muted mono" font-size="12">{label}</text>')
    if color == "#315BFF":
        monthly.append(f'<text x="{x+bar_w/2}" y="{y-10}" text-anchor="middle" fill="#315BFF" class="mono" font-size="12">{value:,}</text>')
monthly += [
 '<line x1="800" y1="150" x2="1020" y2="150" stroke="#D7DCE5"/>',
 f'<text x="800" y="112" class="ink serif" font-size="44">{current_streak} days</text>',
 '<text x="800" y="136" class="muted sans" font-size="14">current contribution streak*</text>',
 '<line x1="800" y1="235" x2="1020" y2="235" stroke="#D7DCE5"/>',
 f'<text x="800" y="207" class="ink serif" font-size="40">{peak}</text>',
 '<text x="800" y="226" class="muted sans" font-size="14">contributions on busiest day</text>',
 '<line x1="800" y1="320" x2="1020" y2="320" stroke="#D7DCE5"/>',
 f'<text x="800" y="291" class="ink serif" font-size="26">{esc(busy)}</text>',
 '<text x="800" y="312" class="muted sans" font-size="14">busiest contribution date</text>',
 '<text x="800" y="362" class="muted sans" font-size="11">*Based on the fetched 12-month calendar.</text>',
 '</svg>'
]
write("activity.svg", "".join(monthly))

# Three feature tiles. These describe real focus areas, not invented reach metrics.
tiles = [
 ("build.svg", "BUILD", "Systems that work", "Agent infrastructure, healthcare robotics, data products.", "#315BFF", "#FFFFFF"),
 ("explore.svg", "EXPLORE", "Intelligence with guardrails", "AI agents, ML evaluation, automation, and trustworthy workflows.", "#EAF0FF", "#101827"),
 ("teach.svg", "TEACH", "Make AI practical", "Helping learners turn modern AI tools into useful workflows.", "#101827", "#FFFFFF"),
]
for filename, tag, title, body, bg, fg in tiles:
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="340" height="214" viewBox="0 0 340 214" role="img" aria-label="{esc(tag)}: {esc(title)}">
<rect width="340" height="214" rx="18" fill="{bg}"/>
<text x="28" y="40" font-family="Arial,sans-serif" font-size="13" font-weight="700" letter-spacing="1.4" fill="{fg}">{tag}</text>
<text x="312" y="40" text-anchor="end" font-family="Arial,sans-serif" font-size="18" fill="{fg}">↗</text>
<text x="28" y="112" font-family="Georgia,serif" font-size="30" letter-spacing="-1" fill="{fg}">{esc(title)}</text>
<foreignObject x="28" y="132" width="284" height="64"><div xmlns="http://www.w3.org/1999/xhtml" style="font:14px Arial,sans-serif;line-height:1.45;color:{fg};">{esc(body)}</div></foreignObject>
</svg>'''
    write(filename, svg)

# Project cards include live repo metadata but only for the featured public projects.
featured = [
 ("Tally-Nexus", "tally-nexus.svg", "#315BFF"),
 ("CAREMATE", "caremate.svg", "#EF4444"),
 ("DATAFORGE-AI", "dataforge.svg", "#FBBF24"),
]
for name, filename, accent in featured:
    repo = repo_by_name.get(name.lower())
    if not repo:
        continue
    title = name.replace("-", " ")
    description = repo.get("description") or "A software project from the EnternalBlue07 workspace."
    language = (repo.get("primaryLanguage") or {}).get("name") or "Multi-stack"
    stars = repo.get("stargazerCount", 0)
    url = repo.get("url", f"https://github.com/{LOGIN}/{name}")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="340" height="176" viewBox="0 0 340 176" role="img" aria-label="{esc(title)} repository card">
<rect width="340" height="176" rx="18" fill="#F1F3F6"/>
<rect x="28" y="31" width="10" height="10" rx="3" fill="{accent}"/>
<text x="54" y="42" font-family="Arial,sans-serif" font-size="20" font-weight="700" fill="#171A21">{esc(title)}</text>
<foreignObject x="28" y="62" width="284" height="64"><div xmlns="http://www.w3.org/1999/xhtml" style="font:14px Arial,sans-serif;line-height:1.45;color:#434A56;">{esc(description[:125])}</div></foreignObject>
<text x="28" y="151" font-family="Consolas,monospace" font-size="12" fill="#697180">{esc(language)}  ·  ★ {stars}</text>
</svg>'''
    write(filename, svg)

print(f"Rendered profile cards for {LOGIN} through {today.isoformat()} ({calendar['totalContributions']} contributions).")
