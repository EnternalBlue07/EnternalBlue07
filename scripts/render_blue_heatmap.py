#!/usr/bin/env python3
"""
Render EnternalBlue07's GitHub contribution calendar as an animated royal-blue
heatmap. Uses a single diagonal slide-down reveal: left-to-right by week and
top-to-bottom by weekday. Each square animates once, then remains still.

The layout and reveal timing follow the supplied render_heatmap_svg.py reference,
with a deep royal-blue palette and a live GitHub GraphQL data fetch.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import urllib.request
from pathlib import Path

LOGIN = "EnternalBlue07"
OUT_PATH = Path(__file__).resolve().parents[1] / "cards" / "heatmap.svg"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

# Empty -> strongest royal blue. No pale periwinkle or green levels.
PALETTE = [
    "#111827",  # no activity: deep slate
    "#102653",  # low
    "#15377E",
    "#1C49AD",
    "#2457D7",
    "#315BFF",  # strongest: royal blue
]

CELL = 12
GAP = 3
STEP = CELL + GAP
PAD = 22
LEFT_LABEL_W = 30
TOP_LABEL_H = 20
TITLEBAR_H = 30

BG = "#070B14"
BG2 = "#0C1425"
FRAME = "#315BFF"
MUTED = "#8390AA"
TEXT = "#E8EEFF"
ACCENT = "#5278FF"
ROYAL = "#4169FF"

# One-shot diagonal cascade, matching the supplied reference renderer.
COL_T = 0.018
ROW_T = 0.045
CELL_DUR = 0.42


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def level_for(count: int) -> int:
    if count <= 0:
        return 0
    if count <= 5:
        return 1
    if count <= 15:
        return 2
    if count <= 30:
        return 3
    if count <= 50:
        return 4
    return 5


def fetch_contributions() -> dict:
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
    payload = {
        "query": query,
        "variables": {
            "login": LOGIN,
            "from": dt.datetime.combine(start, dt.time.min, tzinfo=dt.timezone.utc).isoformat(),
            "to": dt.datetime.combine(today, dt.time.max, tzinfo=dt.timezone.utc).isoformat(),
        },
    }
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "EnternalBlue07-royal-blue-heatmap",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if result.get("errors"):
        raise RuntimeError("GitHub GraphQL error: " + json.dumps(result["errors"]))

    user = result.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user {LOGIN} was not returned.")

    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = sorted(
        [
            {
                "date": item["date"],
                "count": int(item["contributionCount"]),
            }
            for week in calendar["weeks"]
            for item in week["contributionDays"]
        ],
        key=lambda item: item["date"],
    )
    if not days:
        raise RuntimeError("GitHub returned an empty contribution calendar.")

    total = int(calendar["totalContributions"])
    best = max(days, key=lambda item: item["count"])
    current_days = list(days)
    today_text = today.isoformat()
    # GitHub's current streak convention allows today to be empty until the day ends.
    if current_days[-1]["date"] == today_text and current_days[-1]["count"] == 0:
        current_days.pop()

    current_streak = 0
    for item in reversed(current_days):
        if item["count"] == 0:
            break
        current_streak += 1

    longest_streak = 0
    running = 0
    for item in days:
        if item["count"] > 0:
            running += 1
            longest_streak = max(longest_streak, running)
        else:
            running = 0

    return {
        "days": days,
        "total_contributions": total,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "best_day": best,
        "range": {
            "start": days[0]["date"],
            "end": days[-1]["date"],
        },
    }


def build_grid(days: list[dict]) -> list[list[tuple[str, int, int] | None]]:
    first = dt.date.fromisoformat(days[0]["date"])
    lead_pad = (first.weekday() + 1) % 7  # Sunday = 0.
    grid: list[list[tuple[str, int, int] | None]] = []
    column: list[tuple[str, int, int] | None] = [None] * lead_pad

    for item in days:
        date = dt.date.fromisoformat(item["date"])
        weekday = (date.weekday() + 1) % 7
        while len(column) < weekday:
            column.append(None)
        count = int(item["count"])
        column.append((item["date"], count, level_for(count)))
        if len(column) == 7:
            grid.append(column)
            column = []

    if column:
        while len(column) < 7:
            column.append(None)
        grid.append(column)

    return grid


def render(data: dict) -> str:
    days = data["days"]
    grid = build_grid(days)
    n_cols = len(grid)
    art_w = n_cols * STEP
    art_h = 7 * STEP

    month_labels = []
    seen_months = set()
    for col_index, column in enumerate(grid):
        for cell in column:
            if cell is None:
                continue
            date = dt.date.fromisoformat(cell[0])
            key = (date.year, date.month)
            if key not in seen_months and date.day <= 7:
                seen_months.add(key)
                month_labels.append((col_index, date.strftime("%b")))
            break

    canvas_w = PAD + LEFT_LABEL_W + art_w + PAD
    stats_h = 88
    canvas_h = TITLEBAR_H + TOP_LABEL_H + art_h + stats_h + PAD

    css = f"""
@keyframes cell {{
  0%   {{ opacity: 0; transform: translateY(-6px); }}
  100% {{ opacity: 1; transform: translateY(0); }}
}}
.c {{
  opacity: 0;
  animation: cell {CELL_DUR:.2f}s cubic-bezier(.2,.8,.2,1) both;
}}
@media (prefers-reduced-motion: reduce) {{
  .c {{ opacity: 1 !important; animation: none !important; }}
}}
""".strip()

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        f'<title>{LOGIN} — Royal-blue GitHub contribution trail</title>',
        f'<style>{css}</style>',
        '<defs>',
        f'<linearGradient id="hbg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/></linearGradient>',
        '</defs>',
        f'<rect width="{canvas_w}" height="{canvas_h}" rx="12" fill="url(#hbg)"/>',
        f'<rect x="0.5" y="0.5" width="{canvas_w-1}" height="{canvas_h-1}" rx="12" '
        f'fill="none" stroke="{FRAME}" stroke-width="1" stroke-opacity="0.62"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{canvas_w}" y2="{TITLEBAR_H}" '
        f'stroke="{FRAME}" stroke-opacity="0.42"/>',
    ]

    # Terminal controls.
    for index, colour in enumerate(["#FF5F56", "#FFBD2E", "#27C93F"]):
        parts.append(
            f'<circle cx="{PAD + index*16}" cy="{TITLEBAR_H/2}" r="5" fill="{colour}"/>'
        )

    parts.append(
        f'<text x="{canvas_w/2}" y="{TITLEBAR_H/2 + 4}" fill="{MUTED}" font-size="12" '
        f'text-anchor="middle">zumaan@github: ~/contributions --graph</text>'
    )

    grid_top = TITLEBAR_H + TOP_LABEL_H
    grid_left = PAD + LEFT_LABEL_W

    for col_index, label in month_labels:
        x = grid_left + col_index * STEP
        parts.append(
            f'<text x="{x}" y="{TITLEBAR_H + 14}" fill="{MUTED}" font-size="10">{label}</text>'
        )

    for row_index, weekday in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = grid_top + row_index * STEP + CELL * 0.78
        parts.append(
            f'<text x="{PAD}" y="{y:.1f}" fill="{MUTED}" font-size="9">{weekday}</text>'
        )

    # Rounded boxes, revealed diagonally once. No continuous glow or pulsing.
    for col_index, column in enumerate(grid):
        gx = grid_left + col_index * STEP
        for row_index, cell in enumerate(column):
            if cell is None:
                continue
            date_text, count, palette_level = cell
            gy = grid_top + row_index * STEP
            delay = col_index * COL_T + row_index * ROW_T
            plural = "s" if count != 1 else ""
            parts.append(
                f'<rect class="c" x="{gx}" y="{gy}" width="{CELL}" height="{CELL}" rx="2.5" '
                f'fill="{PALETTE[palette_level]}" style="animation-delay:{delay:.3f}s">'
                f'<title>{date_text}: {count} contribution{plural}</title></rect>'
            )

    # Less -> More legend.
    legend_y = grid_top + art_h + 6
    legend_x = canvas_w - PAD - (len(PALETTE) * (CELL - 1) + 70)
    parts.append(
        f'<text x="{legend_x}" y="{legend_y + CELL*0.8:.1f}" fill="{MUTED}" '
        f'font-size="10" text-anchor="end">Less</text>'
    )
    x = legend_x + 8
    for colour in PALETTE:
        parts.append(
            f'<rect x="{x}" y="{legend_y}" width="{CELL-1}" height="{CELL-1}" '
            f'rx="2.2" fill="{colour}"/>'
        )
        x += CELL
    parts.append(
        f'<text x="{x+4}" y="{legend_y + CELL*0.8:.1f}" fill="{MUTED}" font-size="10">More</text>'
    )

    separator_y = legend_y + CELL + 14
    parts.append(
        f'<line x1="0" y1="{separator_y}" x2="{canvas_w}" y2="{separator_y}" '
        f'stroke="{FRAME}" stroke-opacity="0.3"/>'
    )

    total = int(data["total_contributions"])
    current = int(data["current_streak"])
    longest = int(data["longest_streak"])
    best = data["best_day"]
    date_range = data["range"]
    line_y = separator_y + 24

    parts.append(
        f'<text x="{PAD}" y="{line_y}" font-size="13" fill="{ROYAL}">'
        f'<tspan font-weight="700">{total:,}</tspan>'
        f'<tspan fill="{TEXT}"> contributions in the last year</tspan></text>'
    )
    parts.append(
        f'<text x="{canvas_w-PAD}" y="{line_y}" font-size="11" fill="{MUTED}" text-anchor="end">'
        f'{esc(date_range["start"])} &#8594; {esc(date_range["end"])}</text>'
    )

    line_y += 24
    parts.append(
        f'<text x="{PAD}" y="{line_y}" font-size="12" fill="{MUTED}">current streak '
        f'<tspan fill="{ROYAL}" font-weight="700">{current} days</tspan>'
        f'<tspan fill="{MUTED}">   &#183;   longest </tspan>'
        f'<tspan fill="{ROYAL}" font-weight="700">{longest} days</tspan></text>'
    )
    parts.append(
        f'<text x="{canvas_w-PAD}" y="{line_y}" font-size="11" fill="{MUTED}" text-anchor="end">'
        f'best day <tspan fill="{ACCENT}" font-weight="700">{int(best["count"])}</tspan>'
        f' on {esc(best["date"])}</text>'
    )

    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("GH_TOKEN or GITHUB_TOKEN is required.")
    result = fetch_contributions()
    content = render(result)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(content, encoding="utf-8")
    print(
        f"Rendered {OUT_PATH}: {result['total_contributions']:,} contributions, "
        f"{result['current_streak']}-day current streak, {result['longest_streak']}-day longest streak."
    )
