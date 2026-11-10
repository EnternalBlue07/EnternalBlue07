#!/usr/bin/env python3
"""Generate the Engineering / With Intent cards and live GitHub activity panel."""
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

def esc(value: object) -> str:
    return html.escape(str(value), quote=True)

def github_graphql(query: str, variables: dict) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "EnternalBlue07-profile-visuals",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"]))
    return result["data"]

today = dt.datetime.now(dt.timezone.utc).date()
start = today - dt.timedelta(days=364)
query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
"""
data = github_graphql(query, {
    "login": LOGIN,
    "from": dt.datetime.combine(start, dt.time.min, tzinfo=dt.timezone.utc).isoformat(),
    "to": dt.datetime.combine(today, dt.time.max, tzinfo=dt.timezone.utc).isoformat(),
})
calendar = data["user"]["contributionsCollection"]["contributionCalendar"]
days = sorted(
    [day for week in calendar["weeks"] for day in week["contributionDays"]],
    key=lambda item: item["date"],
)
total = int(calendar["totalContributions"])
active_days = sum(1 for day in days if day["contributionCount"] > 0)
busiest = max(days, key=lambda item: item["contributionCount"], default={"contributionCount": 0, "date": "—"})

# Match GitHub's today-grace convention for the current streak.
streak_days = days[:]
if streak_days and streak_days[-1]["date"] == today.isoformat() and streak_days[-1]["contributionCount"] == 0:
    streak_days = streak_days[:-1]
streak = 0
for day in reversed(streak_days):
    if day["contributionCount"] <= 0:
        break
    streak += 1

months = []
for offset in range(11, -1, -1):
    month_index = today.year * 12 + today.month - 1 - offset
    year, month_zero = divmod(month_index, 12)
    month_start = dt.date(year, month_zero + 1, 1)
    next_month = dt.date(year + 1, 1, 1) if month_zero == 11 else dt.date(year, month_zero + 2, 1)
    month_total = sum(
        item["contributionCount"]
        for item in days
        if month_start.isoformat() <= item["date"] < next_month.isoformat()
    )
    months.append((month_start.strftime("%b"), month_total))

# Engineering / with intent — four responsive-looking, fixed-viewBox cards.
engineering = [
    '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="354" viewBox="0 0 1080 354" role="img" aria-label="Engineering with intent: software, design, intelligence and cloud">',
    '<defs>',
    '<linearGradient id="build" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#315BFF"/><stop offset="1" stop-color="#2445D6"/></linearGradient>',
    '<linearGradient id="shape" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F04438"/><stop offset="1" stop-color="#D92E35"/></linearGradient>',
    '<linearGradient id="explore" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFD43B"/><stop offset="1" stop-color="#F4B61D"/></linearGradient>',
    '<linearGradient id="ship" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#14B8A6"/><stop offset="1" stop-color="#0F827C"/></linearGradient>',
    '<style>.serif{font-family:"Bodoni 72","Didot","Times New Roman",serif}.sans{font-family:Inter,"Segoe UI",Arial,sans-serif}.mono{font-family:Consolas,"Liberation Mono",monospace}</style>',
    '</defs>',
    '<rect width="1080" height="354" rx="20" fill="#0D1117"/>',
    '<text x="36" y="64" class="serif" font-size="48" fill="#F0F4F8">Engineering <tspan font-style="italic" fill="#67E8F9">/ with intent</tspan></text>',
    '<line x1="36" y1="88" x2="1044" y2="88" stroke="#263445" stroke-width="1"/>',
]
cards = [
    (36, "01 / BUILD", "Software", ["Applications", "Systems", "Architecture"], "url(#build)", "#FFFFFF"),
    (294, "02 / SHAPE", "Design", ["UI / UX", "Visual systems", "Experiences"], "url(#shape)", "#FFFFFF"),
    (552, "03 / EXPLORE", "Intelligence", ["AI", "Agents", "Automation"], "url(#explore)", "#171717"),
    (810, "04 / SHIP", "Cloud", ["APIs", "Infrastructure", "Deployment"], "url(#ship)", "#FFFFFF"),
]
for x, eyebrow, title, lines, fill, foreground in cards:
    engineering.append(f'<rect x="{x}" y="112" width="234" height="210" rx="18" fill="{fill}"/>')
    engineering.append(f'<text x="{x+22}" y="144" class="mono" font-size="11.5" letter-spacing="1.1" fill="{foreground}" opacity=".88">{eyebrow}</text>')
    engineering.append(f'<text x="{x+22}" y="197" class="serif" font-size="34" fill="{foreground}">{title}</text>')
    for index, line in enumerate(lines):
        engineering.append(f'<text x="{x+22}" y="{239+index*23}" class="sans" font-size="15" fill="{foreground}" opacity=".95">{esc(line)}</text>')
    engineering.append(f'<text x="{x+208}" y="145" text-anchor="end" class="sans" font-size="17" fill="{foreground}">↗</text>')
engineering.append('</svg>')
(OUT / "engineering-intent.svg").write_text("".join(engineering), encoding="utf-8")

# A clean, editorial activity card inspired by the supplied monthly summary reference.
activity = [
    '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="404" viewBox="0 0 1080 404" role="img" aria-label="GitHub contributions in the last twelve months">',
    '<defs><style>.serif{font-family:"Bodoni 72","Didot","Times New Roman",serif}.sans{font-family:Inter,"Segoe UI",Arial,sans-serif}.mono{font-family:Consolas,"Liberation Mono",monospace}</style>',
    '<linearGradient id="accent" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#315BFF"/><stop offset="1" stop-color="#22D3EE"/></linearGradient>',
    '</defs>',
    '<rect width="1080" height="404" rx="22" fill="#F3F3F0"/>',
    '<text x="54" y="50" class="mono" font-size="12" letter-spacing="1.6" fill="#747984">THE LAST 12 MONTHS ON GITHUB</text>',
    f'<text x="54" y="112" class="serif" font-size="53" fill="#15171C">{total:,} <tspan font-style="italic">contributions</tspan></text>',
    '<text x="54" y="146" class="sans" font-size="14" fill="#777D87">A year of ideas, experiments, and shipped work.</text>',
]
max_month = max((value for _, value in months), default=1) or 1
base_y = 328
bar_width = 38
bar_gap = 17
chart_left = 56
for index, (label, value) in enumerate(months):
    x = chart_left + index * (bar_width + bar_gap)
    bar_height = max(3, int(156 * value / max_month))
    y = base_y - bar_height
    fill = "#315BFF" if value == max_month and value > 0 else "#22252D"
    activity.append(
        f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" rx="6" fill="{fill}">'
        f'<title>{label}: {value} contributions</title></rect>'
    )
    activity.append(f'<text x="{x+bar_width/2}" y="356" text-anchor="middle" class="mono" font-size="11.5" fill="#737985">{label}</text>')
    if value == max_month and value > 0:
        activity.append(f'<text x="{x+bar_width/2}" y="{y-9}" text-anchor="middle" class="mono" font-size="11.5" fill="#315BFF">{value:,}</text>')

# Compact metric stack on the right; every value is computed from GitHub's calendar.
activity.extend([
    '<rect x="790" y="42" width="238" height="84" rx="14" fill="#E3EAFE"/>',
    '<text x="812" y="67" class="mono" font-size="10.5" letter-spacing="1.1" fill="#315BFF">CURRENT STREAK</text>',
    f'<text x="812" y="108" class="serif" font-size="37" fill="#171A22">{streak} <tspan font-style="italic" font-size="26">days</tspan></text>',
    '<rect x="790" y="140" width="238" height="84" rx="14" fill="#FCE4E1"/>',
    '<text x="812" y="165" class="mono" font-size="10.5" letter-spacing="1.1" fill="#D94841">ACTIVE DAYS</text>',
    f'<text x="812" y="206" class="serif" font-size="37" fill="#171A22">{active_days} <tspan font-style="italic" font-size="26">/ 365</tspan></text>',
    '<rect x="790" y="238" width="238" height="102" rx="14" fill="#FCEFC7"/>',
    '<text x="812" y="263" class="mono" font-size="10.5" letter-spacing="1.1" fill="#9A6B00">BUSIEST DAY</text>',
    f'<text x="812" y="305" class="serif" font-size="37" fill="#171A22">{int(busiest["contributionCount"]):,}</text>',
    f'<text x="812" y="326" class="sans" font-size="12.5" fill="#6A5B37">{esc(busiest["date"])}</text>',
    '<text x="54" y="386" class="sans" font-size="11.5" fill="#7B8088">Contribution totals and streak are calculated from your public GitHub contribution calendar.</text>',
    '</svg>',
])
(OUT / "contribution-activity.svg").write_text("".join(activity), encoding="utf-8")

print(f"Rendered cards using {total} contributions from {start.isoformat()} through {today.isoformat()}.")
