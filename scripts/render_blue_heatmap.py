#!/usr/bin/env python3
"""
Render EnternalBlue07's contribution dashboard in the supplied editorial style:
an ivory blue-intensity heatmap above a monthly activity chart with a serif metric
stack. All figures come from this user's GitHub GraphQL contribution calendar.

Animation: one-shot diagonal heatmap-cell reveal and one-shot bar growth.
Fonts: Instrument Serif + Geist + Geist Mono, embedded as WOFF data URIs.
"""
from __future__ import annotations

import base64
import bisect
import datetime as dt
import html
import json
import os
import urllib.request
from pathlib import Path

LOGIN = "EnternalBlue07"
OUT_PATH = Path(__file__).resolve().parents[1] / "cards" / "heatmap.svg"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
RAW_FONT = "https://raw.githubusercontent.com/AVIVASHISHTA29/AVIVASHISHTA29/main/fonts/{}"

W, H = 1100, 765
OUTER = "#0d1117"
CARD = "#f3f3f1"
INK = "#111111"
MUTED = "#77787e"
MUTED_LIGHT = "#92939a"
RULE = "#deded9"
ROYAL = "#315bff"

PALETTE = [
    "#e3e4e2",  # no activity
    "#cbd5ff",
    "#a9baff",
    "#879fff",
    "#6483ff",
    "#315bff",  # strongest activity
]

CELL = 15
GAP = 3
STEP = CELL + GAP
COL_DELAY = 0.018
ROW_DELAY = 0.045
CELL_DURATION = 0.42

FONT_FILES = {
    "Instrument Serif": ("normal", 400, "serif-400.woff"),
    "Instrument Serif Italic": ("italic", 400, "serif-italic.woff"),
    "Geist": ("normal", 400, "geist-400.woff"),
    "Geist Mono": ("normal", 400, "geistmono-400.woff"),
}

SERIF = "'Instrument Serif', Georgia, serif"
SERIF_ITALIC = "'Instrument Serif Italic', Georgia, serif"
SANS = "'Geist', Arial, sans-serif"
MONO = "'Geist Mono', Consolas, monospace"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def fetch_font(filename: str) -> str:
    request = urllib.request.Request(
        RAW_FONT.format(filename),
        headers={"User-Agent": "EnternalBlue07-contribution-dashboard"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return base64.b64encode(response.read()).decode("ascii")


def embedded_fonts() -> str:
    declarations = []
    for family, (style, weight, filename) in FONT_FILES.items():
        encoded = fetch_font(filename)
        declarations.append(
            f"@font-face{{font-family:'{family}';font-style:{style};font-weight:{weight};"
            f"src:url(data:font/woff;base64,{encoded}) format('woff')}}"
        )
    return "".join(declarations)


def fetch_calendar() -> dict:
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
            "User-Agent": "EnternalBlue07-contribution-dashboard",
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
            {"date": item["date"], "count": int(item["contributionCount"])}
            for week in calendar["weeks"]
            for item in week["contributionDays"]
        ],
        key=lambda item: item["date"],
    )
    if not days:
        raise RuntimeError("GitHub returned an empty contribution calendar.")
    total = int(calendar["totalContributions"])
    if sum(item["count"] for item in days) != total:
        raise RuntimeError("Daily contribution cells do not sum to GitHub's calendar total.")

    current_days = list(days)
    today_text = today.isoformat()
    if current_days[-1]["date"] == today_text and current_days[-1]["count"] == 0:
        current_days.pop()

    current_streak = 0
    for item in reversed(current_days):
        if item["count"] <= 0:
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

    monthly = []
    for offset in range(11, -1, -1):
        month_index = today.year * 12 + today.month - 1 - offset
        year, month_zero = divmod(month_index, 12)
        first = dt.date(year, month_zero + 1, 1)
        next_month = (
            dt.date(year + 1, 1, 1)
            if month_zero == 11
            else dt.date(year, month_zero + 2, 1)
        )
        count = sum(
            item["count"] for item in days
            if first.isoformat() <= item["date"] < next_month.isoformat()
        )
        monthly.append({"month": first.isoformat()[:7], "total": count})

    best_day = max(days, key=lambda item: item["count"])
    return {
        "days": days,
        "total": total,
        "active_days": sum(1 for item in days if item["count"] > 0),
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "best_day": best_day,
        "monthly": monthly,
    }


def intensity_levels(days: list[dict]) -> list[int]:
    """Use contribution-volume quantiles so the blue ramp remains useful per user."""
    positives = sorted(item["count"] for item in days if item["count"] > 0)
    if not positives:
        return [0]
    # 30th/55th/75th/90th percentiles among active days; top 10% gets royal blue.
    thresholds = []
    for fraction in (0.30, 0.55, 0.75, 0.90):
        idx = min(len(positives) - 1, int((len(positives) - 1) * fraction))
        thresholds.append(positives[idx])
    # Collapse duplicate thresholds while keeping monotonic level assignment.
    return thresholds


def level_for(count: int, thresholds: list[int]) -> int:
    if count <= 0:
        return 0
    return min(5, 1 + bisect.bisect_right(thresholds, count))


def build_grid(days: list[dict]):
    first = dt.date.fromisoformat(days[0]["date"])
    lead = (first.weekday() + 1) % 7
    grid = []
    column = [None] * lead
    for item in days:
        date = dt.date.fromisoformat(item["date"])
        weekday = (date.weekday() + 1) % 7
        while len(column) < weekday:
            column.append(None)
        column.append((item["date"], item["count"]))
        if len(column) == 7:
            grid.append(column)
            column = []
    if column:
        while len(column) < 7:
            column.append(None)
        grid.append(column)
    return grid


def reveal_css() -> str:
    return """
@keyframes cell-reveal {
  0% { opacity:0; transform:translateY(-6px); }
  100% { opacity:1; transform:translateY(0); }
}
@keyframes bar-grow {
  0% { opacity:.35; transform:scaleY(0); }
  100% { opacity:1; transform:scaleY(1); }
}
@keyframes fade-up {
  0% { opacity:0; transform:translateY(9px); }
  100% { opacity:1; transform:translateY(0); }
}
@keyframes number-in {
  0% { opacity:0; transform:translateY(13px); }
  100% { opacity:1; transform:translateY(0); }
}
.cell {
  opacity:0;
  transform-box:fill-box;
  animation:cell-reveal .42s cubic-bezier(.2,.8,.2,1) both;
}
.bar {
  transform-box:fill-box;
  transform-origin:bottom;
  animation:bar-grow .72s cubic-bezier(.2,.8,.2,1) both;
}
.fade { opacity:0; animation:fade-up .7s ease-out both; }
.metric { opacity:0; animation:number-in .78s cubic-bezier(.2,.7,.2,1) both; }
@media(prefers-reduced-motion:reduce) {
  .cell,.bar,.fade,.metric { opacity:1!important; transform:none!important; animation:none!important; }
}
""".strip()


def build_svg(data: dict, fonts: str) -> str:
    days = data["days"]
    grid = build_grid(days)
    thresholds = intensity_levels(days)
    # Main background and panel dimensions mirror the supplied 2-card screenshot.
    top_x, top_y, top_w, top_h = 25, 9, 1058, 295
    bottom_x, bottom_y, bottom_w, bottom_h = 25, 324, 1058, 409
    grid_x, grid_y = 77, 124
    cell = 15
    step = 18

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{LOGIN} GitHub contributions over the last 12 months">',
        f'<title>{LOGIN} — Every day, in blue: contribution calendar and monthly activity</title>',
        f'<style>{fonts}{reveal_css()}</style>',
        f'<rect width="{W}" height="{H}" fill="{OUTER}"/>',
        f'<rect x="{top_x}" y="{top_y}" width="{top_w}" height="{top_h}" rx="17" fill="{CARD}"/>',
        f'<rect x="{bottom_x}" y="{bottom_y}" width="{bottom_w}" height="{bottom_h}" rx="17" fill="{CARD}"/>',
    ]

    # ---- Heatmap panel: title, refresh label, contribution grid, month labels.
    parts.append(
        f'<text class="fade" style="animation-delay:.2s" x="76" y="84" '
        f'font-family="{SERIF}" font-size="40" fill="{INK}">'
        f'Every day, <tspan font-family="{SERIF_ITALIC}" font-style="italic" fill="{ROYAL}">in blue</tspan></text>'
    )
    parts.append(
        f'<text class="fade" style="animation-delay:.3s" x="1028" y="81" text-anchor="end" '
        f'font-family="{MONO}" font-size="12" letter-spacing="1.2" fill="{MUTED}">REFRESHED DAILY</text>'
    )

    month_labels = []
    seen = set()
    for col_index, column in enumerate(grid):
        for item in column:
            if item is None:
                continue
            date = dt.date.fromisoformat(item[0])
            key = (date.year, date.month)
            if key not in seen and date.day <= 7:
                seen.add(key)
                if col_index < len(grid) - 8:
                    month_labels.append((col_index, date.strftime("%b")))
            break

    for col_index, column in enumerate(grid):
        x = grid_x + col_index * step
        for row_index, item in enumerate(column):
            if item is None:
                continue
            date_text, count = item
            y = grid_y + row_index * step
            delay = .62 + col_index * .018 + row_index * .045
            lvl = level_for(count, thresholds)
            parts.append(
                f'<rect class="cell" style="animation-delay:{delay:.3f}s" '
                f'x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" fill="{PALETTE[lvl]}">'
                f'<title>{date_text}: {count} contribution{"s" if count != 1 else ""}</title></rect>'
            )

    for col_index, label in month_labels:
        x = grid_x + col_index * step
        parts.append(
            f'<text class="fade" style="animation-delay:2.0s" x="{x}" y="270" '
            f'font-family="{MONO}" font-size="12" fill="{MUTED}">{label}</text>'
        )

    # Six-step legend sits on the lower right of the heatmap card.
    legend_x, legend_y = 930, 258
    parts.append(
        f'<text class="fade" style="animation-delay:2.05s" x="{legend_x-9}" y="270" '
        f'text-anchor="end" font-family="{MONO}" font-size="12" fill="{MUTED}">less</text>'
    )
    for index, colour in enumerate(PALETTE):
        parts.append(
            f'<rect class="fade" style="animation-delay:{2.05+index*.05:.2f}s" '
            f'x="{legend_x+index*17}" y="{legend_y}" width="14" height="14" rx="3" fill="{colour}"/>'
        )
    parts.append(
        f'<text class="fade" style="animation-delay:2.35s" x="{legend_x+len(PALETTE)*17+3}" y="270" '
        f'font-family="{MONO}" font-size="12" fill="{MUTED}">more</text>'
    )

    # ---- Monthly activity panel.
    total = int(data["total"])
    active = int(data["active_days"])
    day_count = len(days)
    current_streak = int(data["current_streak"])
    longest_streak = int(data["longest_streak"])
    best_day = data["best_day"]

    parts.append(
        f'<text class="fade" style="animation-delay:2.1s" x="72" y="384" '
        f'font-family="{MONO}" font-size="12" letter-spacing="1.2" fill="{MUTED}">'
        f'THE LAST 12 MONTHS ON GITHUB</text>'
    )
    parts.append(
        f'<text class="metric" style="animation-delay:2.2s" x="72" y="460" '
        f'font-family="{SERIF}" font-size="62" fill="{INK}">{total:,}'
        f'<tspan font-family="{SERIF_ITALIC}" font-style="italic"> contributions</tspan></text>'
    )

    # Bar chart uses the same 12-month bucket boundaries as the real calendar.
    months = data["monthly"][-12:]
    max_month = max((item["total"] for item in months), default=1) or 1
    base_y = 676
    bar_x = 73
    bar_w = 44
    bar_gap = 11
    current_month = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
    max_month_key = max(months, key=lambda item: item["total"])["month"]
    for index, item in enumerate(months):
        month_key = item["month"]
        month_label = dt.date.fromisoformat(month_key + "-01").strftime("%b")
        amount = int(item["total"])
        height = max(3, int(168 * amount / max_month))
        x = bar_x + index * (bar_w + bar_gap)
        y = base_y - height
        if month_key == current_month:
            colour = "#c9c9c5"
        elif month_key == max_month_key and amount > 0:
            colour = ROYAL
        else:
            colour = "#111111"
        delay = 2.5 + index * .075
        parts.append(
            f'<rect class="bar" style="animation-delay:{delay:.3f}s" '
            f'x="{x}" y="{y}" width="{bar_w}" height="{height}" rx="5" fill="{colour}">'
            f'<title>{month_label}: {amount:,} contributions</title></rect>'
        )
        parts.append(
            f'<text class="fade" style="animation-delay:{delay+.5:.3f}s" x="{x+bar_w/2}" y="703" '
            f'text-anchor="middle" font-family="{MONO}" font-size="12" fill="{MUTED}">{month_label}</text>'
        )
        if month_key == max_month_key and amount > 0:
            parts.append(
                f'<text class="fade" style="animation-delay:{delay+.55:.3f}s" x="{x+bar_w/2}" '
                f'y="{y-11}" text-anchor="middle" font-family="{MONO}" font-size="12" fill="{ROYAL}">'
                f'{amount:,}</text>'
            )

    # Right metrics, with the sample's hierarchy and divider placement.
    metric_x = 805
    parts.append(
        f'<text class="metric" style="animation-delay:3.25s" x="{metric_x}" y="449" '
        f'font-family="{SERIF}" font-size="48" fill="{INK}">{current_streak}'
        f'<tspan font-family="{SERIF_ITALIC}" font-style="italic"> days</tspan></text>'
    )
    streak_caption = (
        f"current streak, and the longest"
        if current_streak == longest_streak
        else f"current streak · longest {longest_streak} days"
    )
    parts.append(
        f'<text class="fade" style="animation-delay:3.4s" x="{metric_x}" y="478" '
        f'font-family="{SANS}" font-size="13.5" fill="{MUTED}">{esc(streak_caption)}</text>'
    )
    parts.append(f'<line x1="{metric_x}" y1="503" x2="1034" y2="503" stroke="{RULE}"/>')

    parts.append(
        f'<text class="metric" style="animation-delay:3.55s" x="{metric_x}" y="558" '
        f'font-family="{SERIF}" font-size="43" fill="{INK}">{active}'
        f'<tspan fill="{MUTED_LIGHT}"> / {day_count}</tspan></text>'
    )
    parts.append(
        f'<text class="fade" style="animation-delay:3.7s" x="{metric_x}" y="586" '
        f'font-family="{SANS}" font-size="13.5" fill="{MUTED}">days with a commit</text>'
    )
    parts.append(f'<line x1="{metric_x}" y1="614" x2="1034" y2="614" stroke="{RULE}"/>')

    parts.append(
        f'<text class="metric" style="animation-delay:3.85s" x="{metric_x}" y="671" '
        f'font-family="{SERIF}" font-size="47" fill="{INK}">{int(best_day["count"]):,}</text>'
    )
    parts.append(
        f'<text class="fade" style="animation-delay:4.0s" x="{metric_x}" y="700" '
        f'font-family="{SANS}" font-size="13.5" fill="{MUTED}">on the busiest day</text>'
    )

    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    if not TOKEN:
        raise SystemExit("GH_TOKEN or GITHUB_TOKEN is required.")
    data = fetch_calendar()
    font_data = embedded_fonts()
    rendered = build_svg(data, font_data)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(rendered, encoding="utf-8")
    print(
        f"Rendered two-panel dashboard for {LOGIN}: "
        f"{data['total']:,} contributions, {data['active_days']}/{len(data['days'])} active days, "
        f"{data['current_streak']}-day streak, busiest day {data['best_day']['count']}."
    )


if __name__ == "__main__":
    main()
