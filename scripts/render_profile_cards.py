#!/usr/bin/env python3
"""Render responsive SVG cards for the EnternalBlue07 profile README."""
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

def api(url: str, payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url, data=data, method="POST" if payload else "GET",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "EnternalBlue07-profile-card-renderer",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())

def esc(value):
    return html.escape(str(value), quote=True)

today = dt.datetime.now(dt.timezone.utc).date()
start = today - dt.timedelta(days=364)
query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes { name description url stargazerCount primaryLanguage { name } isPrivate }
    }
  }
}
"""
data = api("https://api.github.com/graphql", {
    "query": query,
    "variables": {
        "login": LOGIN,
        "from": dt.datetime.combine(start, dt.time.min, tzinfo=dt.timezone.utc).isoformat(),
        "to": dt.datetime.combine(today, dt.time.max, tzinfo=dt.timezone.utc).isoformat(),
    },
})
if data.get("errors"):
    raise SystemExit("GitHub GraphQL error: " + json.dumps(data["errors"]))
user = data["data"]["user"]
calendar = user["contributionsCollection"]["contributionCalendar"]
days = [day for week in calendar["weeks"] for day in week["contributionDays"]]
repos = {r["name"].lower(): r for r in user["repositories"]["nodes"] if not r["isPrivate"]}

# Contribution heatmap: week columns, weekday rows.
cell, gap, left, top = 16, 3, 52, 92
palette = ["#E7ECF4", "#C7D3FF", "#91A8FF", "#5F80FF", "#315BFF"]
peak_count = max((d["contributionCount"] for d in days), default=1) or 1

def level(count):
    if count == 0:
        return 0
    ratio = count / peak_count
    return 1 if ratio <= .2 else 2 if ratio <= .4 else 3 if ratio <= .7 else 4

heat = [
    '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="302" viewBox="0 0 1080 302" role="img" aria-label="Daily GitHub contributions, refreshed daily">',
    '<rect width="1080" height="302" rx="22" fill="#F4F5F7"/>',
    '<text x="54" y="52" font-family="Georgia,serif" font-size="36" fill="#111827">Every day, <tspan fill="#315BFF" font-style="italic">in blue</tspan></text>',
    '<text x="1025" y="44" text-anchor="end" font-family="Consolas,monospace" font-size="13" letter-spacing="1.5" fill="#667085">REFRESHED DAILY</text>',
]
for wi, week in enumerate(calendar["weeks"]):
    for di, day in enumerate(week["contributionDays"]):
        x, y = left + wi * (cell + gap), top + di * (cell + gap)
        count = day["contributionCount"]
        heat.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" fill="{palette[level(count)]}">'
            f'<title>{esc(day["date"])}: {count} contributions</title></rect>'
        )

# Month labels align with the first day of each month in this calendar window.
for month_index in range(13):
    date = start + dt.timedelta(days=month_index * 30)
    if date > today:
        break
    x = left + ((date - start).days / 7) * (cell + gap)
    heat.append(f'<text x="{x:.1f}" y="284" font-family="Consolas,monospace" font-size="12" fill="#667085">{date.strftime("%b")}</text>')
heat.append('<text x="850" y="284" font-family="Consolas,monospace" font-size="12" fill="#667085">LESS</text>')
for i, color in enumerate(palette):
    heat.append(f'<rect x="{886 + i*18}" y="270" width="14" height="14" rx="3" fill="{color}"/>')
heat.append('<text x="985" y="284" font-family="Consolas,monospace" font-size="12" fill="#667085">MORE</text></svg>')
(OUT / "heatmap.svg").write_text("".join(heat), encoding="utf-8")

# Accurate calendar-month totals for the trailing 12 months.
months = []
for offset in range(11, -1, -1):
    index = today.year * 12 + today.month - 1 - offset
    year, month_zero = divmod(index, 12)
    month_start = dt.date(year, month_zero + 1, 1)
    next_month = dt.date(year + 1, 1, 1) if month_zero == 11 else dt.date(year, month_zero + 2, 1)
    total = sum(d["contributionCount"] for d in days if month_start.isoformat() <= d["date"] < next_month.isoformat())
    months.append((month_start.strftime("%b"), total))

peak_day = max((d["contributionCount"] for d in days), default=0)
busy_day = next((d["date"] for d in reversed(days) if d["contributionCount"] == peak_day), "—")
streak = 0
for day in reversed(days):
    if day["contributionCount"] > 0:
        streak += 1
    elif day["date"] != today.isoformat():
        break

chart = [
    '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="390" viewBox="0 0 1080 390" role="img" aria-label="Monthly GitHub activity for the last 12 months">',
    '<rect width="1080" height="390" rx="22" fill="#F4F5F7"/>',
    '<text x="54" y="54" font-family="Consolas,monospace" font-size="13" letter-spacing="1.5" fill="#667085">THE LAST 12 MONTHS ON GITHUB</text>',
    f'<text x="54" y="116" font-family="Georgia,serif" font-size="52" fill="#111827">{calendar["totalContributions"]:,} <tspan font-style="italic">contributions</tspan></text>',
]
max_month = max((value for _, value in months), default=1) or 1
for i, (label, value) in enumerate(months):
    x = 56 + i * 62
    height = max(2, int(176 * value / max_month))
    y = 330 - height
    fill = "#315BFF" if value == max_month else "#171A21"
    chart.append(f'<rect x="{x}" y="{y}" width="42" height="{height}" rx="6" fill="{fill}"><title>{label}: {value} contributions</title></rect>')
    chart.append(f'<text x="{x+21}" y="356" text-anchor="middle" font-family="Consolas,monospace" font-size="12" fill="#667085">{label}</text>')
    if fill == "#315BFF":
        chart.append(f'<text x="{x+21}" y="{y-10}" text-anchor="middle" font-family="Consolas,monospace" font-size="12" fill="#315BFF">{value:,}</text>')
chart.extend([
    '<line x1="800" y1="150" x2="1020" y2="150" stroke="#D7DCE5"/>',
    f'<text x="800" y="112" font-family="Georgia,serif" font-size="44" fill="#111827">{streak} days</text>',
    '<text x="800" y="136" font-family="Arial,sans-serif" font-size="14" fill="#667085">current streak*</text>',
    '<line x1="800" y1="235" x2="1020" y2="235" stroke="#D7DCE5"/>',
    f'<text x="800" y="207" font-family="Georgia,serif" font-size="40" fill="#111827">{peak_day}</text>',
    '<text x="800" y="226" font-family="Arial,sans-serif" font-size="14" fill="#667085">contributions on busiest day</text>',
    '<line x1="800" y1="320" x2="1020" y2="320" stroke="#D7DCE5"/>',
    f'<text x="800" y="291" font-family="Georgia,serif" font-size="26" fill="#111827">{esc(busy_day)}</text>',
    '<text x="800" y="312" font-family="Arial,sans-serif" font-size="14" fill="#667085">busiest contribution date</text>',
    '<text x="800" y="362" font-family="Arial,sans-serif" font-size="11" fill="#667085">*From the displayed 12-month calendar.</text>',
    '</svg>',
])
(OUT / "activity.svg").write_text("".join(chart), encoding="utf-8")

def wrapped_svg_lines(text: str, max_chars: int = 39, limit: int = 3):
    result, current = [], ""
    for word in text.split():
        candidate = (current + " " + word).strip()
        if len(candidate) > max_chars and current:
            result.append(current)
            current = word
        else:
            current = candidate
    if current:
        result.append(current)
    return result[:limit]

tiles = [
    ("build.svg", "BUILD", "Systems that work", "Agent infrastructure, healthcare robotics, and data products.", "#315BFF", "#FFFFFF"),
    ("explore.svg", "EXPLORE", "Intelligence with guardrails", "AI agents, machine learning, and trustworthy workflows.", "#EAF0FF", "#101827"),
    ("teach.svg", "TEACH", "Make AI practical", "Helping learners turn modern AI tools into useful workflows.", "#101827", "#FFFFFF"),
]
for filename, tag, title, body, background, foreground in tiles:
    lines = wrapped_svg_lines(body)
    text_lines = "".join(
        f'<text x="28" y="{145+i*19}" font-family="Arial,sans-serif" font-size="13" fill="{foreground}">{esc(line)}</text>'
        for i, line in enumerate(lines)
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="340" height="214" viewBox="0 0 340 214" role="img" aria-label="{esc(tag)}: {esc(title)}">'
        f'<rect width="340" height="214" rx="18" fill="{background}"/>'
        f'<text x="28" y="40" font-family="Arial,sans-serif" font-size="13" font-weight="700" letter-spacing="1.4" fill="{foreground}">{tag}</text>'
        f'<text x="312" y="40" text-anchor="end" font-family="Arial,sans-serif" font-size="18" fill="{foreground}">↗</text>'
        f'<text x="28" y="112" font-family="Georgia,serif" font-size="27" letter-spacing="-1" fill="{foreground}">{esc(title)}</text>'
        f'{text_lines}</svg>'
    )
    (OUT / filename).write_text(svg, encoding="utf-8")

# Featured repository tiles: metadata is read live from the GitHub account.
featured = [
    ("Tally-Nexus", "tally-nexus.svg", "#315BFF"),
    ("CAREMATE", "caremate.svg", "#EF4444"),
    ("DATAFORGE-AI", "dataforge.svg", "#FBBF24"),
]
for name, filename, accent in featured:
    repo = repos.get(name.lower())
    if not repo:
        continue
    title = name.replace("-", " ")
    description = repo.get("description") or "A project from the EnternalBlue07 workspace."
    language = (repo.get("primaryLanguage") or {}).get("name") or "Multi-stack"
    stars = repo.get("stargazerCount", 0)
    lines = wrapped_svg_lines(description, max_chars=39, limit=3)
    text_lines = "".join(
        f'<text x="28" y="{90+i*18}" font-family="Arial,sans-serif" font-size="13" fill="#434A56">{esc(line)}</text>'
        for i, line in enumerate(lines)
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="340" height="176" viewBox="0 0 340 176" role="img" aria-label="{esc(title)} repository card">'
        f'<rect width="340" height="176" rx="18" fill="#F1F3F6"/>'
        f'<rect x="28" y="31" width="10" height="10" rx="3" fill="{accent}"/>'
        f'<text x="54" y="42" font-family="Arial,sans-serif" font-size="20" font-weight="700" fill="#171A21">{esc(title)}</text>'
        f'{text_lines}'
        f'<text x="28" y="151" font-family="Consolas,monospace" font-size="12" fill="#697180">{esc(language)}  ·  ★ {stars}</text>'
        f'</svg>'
    )
    (OUT / filename).write_text(svg, encoding="utf-8")

print(f"Rendered cards for {LOGIN}: {calendar['totalContributions']} contributions through {today.isoformat()}.")
