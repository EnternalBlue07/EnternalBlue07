#!/usr/bin/env python3
"""
Render EnternalBlue07's GitHub profile art as animated, font-embedded SVGs.

The visual system is adapted from the supplied reference renderer:
- Instrument Serif for editorial display type
- Geist for interface/body text
- Geist Mono for labels and metadata
- CSS keyframes + SVG SMIL for one-shot reveals, count-ups, bar growth and sheen
- Reduced-motion fallbacks for visitors who prefer less motion

All profile-specific copy and projects are authored for EnternalBlue07.
Contribution statistics are read only from data/contributions.json, fetched from
EnternalBlue07's own public GitHub contribution calendar.
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import json
import os
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "cards"
DATA = ROOT / "data"
FONTS_PATH = ROOT / "fonts"
CONTRIB_PATH = DATA / "contributions.json"
SIGNATURE_PATH = DATA / "signature-ascii.txt"
LOGIN = "EnternalBlue07"
W = 880

CARDS.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)

# Three subsets supplied with this project, embedded directly into the SVGs.
FONT_FILES = {
    "serif": ("Instrument Serif", "normal", 400, "serif-400.woff"),
    "serif-i": ("Instrument Serif", "italic", 400, "serif-italic.woff"),
    "sans": ("Geist", "normal", 400, "geist-400.woff"),
    "sans-b": ("Geist", "normal", 600, "geist-600.woff"),
    "mono": ("Geist Mono", "normal", 400, "geistmono-400.woff"),
}

PAPER = "#f3f3f1"
PAPER_DEEP = "#e2e2de"
INK = "#111111"
INK_SOFT = "#3a3a3c"
MUTED = "#6e6e73"
RULE = "#dcdcd7"
TECH = "#315bff"
TEAL = "#0f9f9a"
GOLD = "#ffc81a"
DARK = "#0d1117"
DARK_2 = "#111722"
SERIF = "'Instrument Serif', Georgia, serif"
SANS = "'Geist', system-ui, -apple-system, sans-serif"
MONO = "'Geist Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

BASE_CSS = """
@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes pop{0%{opacity:0;transform:scale(.3)}70%{opacity:1;transform:scale(1.14)}100%{opacity:1;transform:none}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
@keyframes nudge{0%,100%{transform:none}50%{transform:translateX(4px)}}
@keyframes nudgeup{0%,100%{transform:none}50%{transform:translate(3px,-3px)}}
@keyframes tilein{0%{opacity:0;transform:translateY(62px) scale(.82) rotate(-3deg)}58%{opacity:1;transform:translateY(-6px) scale(1.025) rotate(1deg)}82%{transform:translateY(2px) scale(.99)}100%{opacity:1;transform:none}}
@keyframes slidein{from{opacity:0;transform:translateX(-24px)}to{opacity:1;transform:none}}
@keyframes arrowin{0%{opacity:0;transform:translateX(-20px)}65%{opacity:1;transform:translateX(4px)}100%{opacity:1;transform:none}}
@keyframes roll{from{transform:translateY(52px)}to{transform:none}}
@keyframes sheen{0%{transform:translateX(-330px) skewX(-20deg)}24%,100%{transform:translateX(540px) skewX(-20deg)}}
@keyframes ring{0%{opacity:.7;transform:scale(.2)}100%{opacity:0;transform:scale(2.25)}}
@keyframes cursor{0%,48%{opacity:1}50%,100%{opacity:0}}
.r{opacity:0;animation:rise .78s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box}
.f{opacity:0;animation:fade .85s ease-out both}
.g{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:grow .78s cubic-bezier(.2,.7,.2,1) both}
.p{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .42s ease-out both}
.live{animation:pulse 1.8s ease-in-out infinite}
.n{transform-box:fill-box;animation:nudge 1.8s ease-in-out infinite}
.nu{transform-box:fill-box;animation:nudgeup 1.8s ease-in-out infinite}
.ti{opacity:0;transform-box:fill-box;transform-origin:50% 60%;animation:tilein 1.05s cubic-bezier(.2,.8,.2,1) both}
.sl{opacity:0;transform-box:fill-box;animation:slidein .62s cubic-bezier(.2,.7,.2,1) both}
.ai{opacity:0;transform-box:fill-box;animation:arrowin .7s cubic-bezier(.2,.7,.2,1) both}
.ro{transform-box:fill-box;animation:roll .76s cubic-bezier(.15,.8,.2,1) both}
.sh{animation:sheen 6.2s ease-in-out infinite}
.rg{opacity:0;transform-box:fill-box;transform-origin:center;animation:ring 1.05s ease-out both}
.cursor{animation:cursor 1s steps(1,end) infinite}
@media(prefers-reduced-motion:reduce){
 .r,.f,.g,.p,.live,.n,.nu,.ti,.sl,.ai,.ro,.rg,.cursor{animation:none!important;opacity:1!important;transform:none!important}
 .sh,.rg{display:none!important}
}
""".strip()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def font_face(keys: list[str]) -> str:
    rules = []
    for key in keys:
        family, style, weight, filename = FONT_FILES[key]
        encoded = base64.b64encode((FONTS_PATH / filename).read_bytes()).decode("ascii")
        rules.append(
            f"@font-face{{font-family:'{family}';font-style:{style};font-weight:{weight};"
            f"src:url(data:font/woff;base64,{encoded}) format('woff')}}"
        )
    return "".join(rules)


def svg(width: float, height: int, body: str, fonts: list[str], label: str,
        extra_css: str = "", background: str | None = None, bottom: int = 0) -> str:
    css = font_face(fonts) + BASE_CSS + extra_css
    if os.environ.get("STATIC"):
        css += ".r,.f,.g,.p,.live,.n,.nu,.ti,.sl,.ai,.ro,.rg,.cursor{animation:none!important;opacity:1!important;transform:none!important}.sh{display:none!important}"
    backdrop = f'<rect width="{width}" height="{height}" rx="14" fill="{background}"/>' if background else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}" height="{height}" '
        f'viewBox="0 0 {width:.3f} {height}" role="img" aria-label="{esc(label)}">'
        f'<title>{esc(label)}</title><style>{css}</style>{backdrop}{body}</svg>'
    )


def write(name: str, content: str) -> None:
    (CARDS / name).write_text(content, encoding="utf-8")
    print(f"wrote cards/{name} ({len(content)//1024} KB)")


def delay(seconds: float) -> str:
    return f'style="animation-delay:{seconds:.2f}s"'


def wrap(text: str, limit: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and len(candidate) > limit:
            lines.append(line)
            line = word
        else:
            line = candidate
    return lines + ([line] if line else [])


def text_lines(x: float, y: float, lines: list[str], leading: float, attrs: str) -> str:
: str) -> str:
    return "".join(
        f'<text x="{x}" y="{y + i*leading:.1f}" {attrs}>{esc(line)}</text>'
        for i, line in enumerate(lines)
    )


def count_up(value: int | float, x: float, y: float, attrs: str,
             begin: float, suffix: str = "", frames: int = 18, duration: float = 1.1) -> str:
    """Count values up with SVG SMIL <set> frames; works inside GitHub's <img> renderer."""
    if os.environ.get("STATIC"):
        shown = f"{value:,.1f}" if isinstance(value, float) and not value.is_integer() else f"{int(value):,}"
        return f'<text x="{x}" y="{y}" {attrs}>{shown}{suffix}</text>'
    out = []
    is_float = isinstance(value, float) and not float(value).is_integer()
    for i in range(frames + 1):
        progress = i / frames
        eased = 1 - (1 - progress) ** 3
        current = value if i == frames else value * eased
        text = f"{current:,.1f}" if is_float else f"{int(round(current)):,}"
        on = begin + duration * i / frames
        off = "" if i == frames else f'<set attributeName="opacity" to="0" begin="{begin + duration*(i+1)/frames:.3f}s"/>'
        out.append(
            f'<text x="{x}" y="{y}" {attrs} opacity="0">{text}{suffix}'
            f'<set attributeName="opacity" to="1" begin="{on:.3f}s"/>{off}</text>'
        )
    return "".join(out)


# ---- Profile signature hero ----------------------------------------------------
def hero() -> None:
    signature_rows = SIGNATURE_PATH.read_text(encoding="utf-8").splitlines()
    art_w = 390
    art_h_per_row = 6.05
    art_x, art_y = 470, 54
    signature = []
    row_count = len(signature_rows)
    row_duration = 5.8 / max(1, row_count)

    for index, row in enumerate(signature_rows):
        y = art_y + index * art_h_per_row
        start = 0.72 + index * row_duration
        safe = esc(row)
        text = (
            f'<text xml:space="preserve" x="0" y="{y:.1f}" fill="{INK}" '
            f'font-family="{MONO}" font-size="6.2" textLength="{art_w}" '
            f'lengthAdjust="spacingAndGlyphs">{safe}</text>'
        )
        if os.environ.get("STATIC"):
            signature.append(text)
        else:
            signature.append(
                f'<clipPath id="sig{index}"><rect x="0" y="{y-art_h_per_row+1:.1f}" '
                f'height="{art_h_per_row:.1f}" width="0">'
                f'<animate attributeName="width" from="0" to="{art_w}" begin="{start:.3f}s" '
                f'dur="{row_duration:.3f}s" fill="freeze"/></rect></clipPath>'
            )
            signature.append(f'<g clip-path="url(#sig{index})">{text}</g>')
            signature.append(
                f'<rect x="0" y="{y-art_h_per_row+1:.1f}" width="3.4" height="{art_h_per_row-1:.1f}" '
                f'fill="{INK}" opacity="0"><animate attributeName="x" from="0" to="{art_w}" '
                f'begin="{start:.3f}s" dur="{row_duration:.3f}s" fill="freeze"/>'
                f'<set attributeName="opacity" to=".9" begin="{start:.3f}s"/>'
                f'<set attributeName="opacity" to="0" begin="{start+row_duration:.3f}s"/></rect>'
            )

    body = f"""
<defs>
  <linearGradient id="nameShine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="520" y2="0">
    <stop offset="0" stop-color="{INK}"/><stop offset=".43" stop-color="{INK}"/>
    <stop offset=".5" stop-color="{TECH}"/><stop offset=".57" stop-color="{INK}"/>
    <stop offset="1" stop-color="{INK}"/>
    <animateTransform attributeName="gradientTransform" type="translate" values="-520 0;520 0;520 0"
      keyTimes="0;.5;1" dur="7.5s" begin="1.5s" repeatCount="indefinite"/>
  </linearGradient>
  <linearGradient id="signatureFade" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{INK}"/><stop offset="1" stop-color="#45484e"/>
  </linearGradient>
</defs>
<rect width="{W}" height="420" rx="14" fill="{PAPER}"/>
<g class="f" {delay(0.0)}>
  <rect class="live" x="48" y="47" width="8" height="8" rx="2" fill="{TECH}"/>
  <text x="66" y="56" font-family="{MONO}" font-size="11.5" letter-spacing="1.1" fill="{MUTED}">AI SYSTEMS BUILDER  ·  SOFTWARE ENGINEERING  ·  PRODUCT DESIGN</text>
</g>
<text class="r" {delay(0.12)} x="44" y="168" font-family="{SERIF}" font-size="94" letter-spacing="-2.6" fill="{INK}">Zumaan</text>
<text class="r" {delay(0.28)} x="44" y="263" font-family="{SERIF}" font-style="italic" font-size="94" letter-spacing="-2.8" fill="url(#nameShine)">Sayyed</text>
<g class="r" {delay(0.55)}>
  {text_lines(48, 320, ["I build AI systems, agentic products,", "and useful software for real-world problems."], 24, f'font-family="{SANS}" font-size="17" fill="{INK_SOFT}"')}
</g>
<g class="f" {delay(0.9)}>
  <text x="48" y="392" font-family="{MONO}" font-size="12.5" fill="{INK}">github.com/EnternalBlue07</text>
  <path class="nu" d="M248 390 L258 380 M250 380 H258 V388" fill="none" stroke="{TECH}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</g>
<g transform="translate({art_x} 0)" font-family="{MONO}">
  <text class="f" {delay(0.45)} x="0" y="34" font-family="{MONO}" font-size="10" letter-spacing="1.1" fill="{MUTED}">SIGNATURE / ORIGINAL MARK</text>
  <circle class="live" cx="350" cy="30" r="3.5" fill="{TECH}"/>
  {''.join(signature)}
</g>
"""
    write("hero.svg", svg(W, 420, body, ["serif", "serif-i", "sans", "mono"],
                          "Zumaan Sayyed — AI systems builder, software engineer and product designer."))


# ---- Contribution heatmap ------------------------------------------------------
BLUE = [PAPER_DEEP, "#cbd6ff", "#a5b9ff", "#7896ff", TECH, "#1b36cf"]


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


def heatmap(data: dict) -> None:
    days = data["days"]
    if not days:
        raise RuntimeError("Contribution data has no daily entries.")
    first = dt.date.fromisoformat(days[0]["date"])
    lead = (first.weekday() + 1) % 7  # Sunday starts the first column.
    cell, step, gx, gy = 11, 14, 42, 93
    ncols = (len(days) + lead + 6) // 7
    cells, months, seen = [], [], set()

    for index, day in enumerate(days):
        col, row = divmod(index + lead, 7)
        date = dt.date.fromisoformat(day["date"])
        if date.day <= 7 and row == 0 and (date.year, date.month) not in seen:
            seen.add((date.year, date.month))
            months.append((col, date.strftime("%b")))
        count = int(day["count"])
        lvl = level_for(count)
        delay_s = .85 + col * .026 + row * .022
        cells.append(
            f'<rect class="p" style="animation-delay:{delay_s:.3f}s" '
            f'x="{gx + col*step}" y="{gy + row*step}" width="{cell}" height="{cell}" rx="3" '
            f'fill="{BLUE[lvl]}"><title>{esc(day["date"])}: {count} contribution{"s" if count != 1 else ""}</title></rect>'
        )

    right = gx + ncols * step - 3
    labels = "".join(
        f'<text x="{gx + col*step}" y="{gy + 7*step + 17}" font-family="{MONO}" font-size="10.5" fill="{MUTED}">{label}</text>'
        for col, label in months if col < ncols - 8
    )
    legend_x = right - len(BLUE) * 14
    legend = "".join(
        f'<rect x="{legend_x + index*14}" y="{gy + 7*step + 5}" width="11" height="11" rx="2.5" fill="{colour}"/>'
        for index, colour in enumerate(BLUE)
    )
    h = gy + 7*step + 46
    body = f"""
<defs>
  <clipPath id="heatClip"><rect width="{W}" height="{h}" rx="14"/></clipPath>
  <linearGradient id="heatSheen" x1="0" x2="1">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
    <stop offset=".5" stop-color="#ffffff" stop-opacity=".43"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>
</defs>
<rect width="{W}" height="{h}" rx="14" fill="{PAPER}"/>
<text class="r" {delay(.25)} x="42" y="54" font-family="{SERIF}" font-size="36" fill="{INK}">Every day, <tspan font-style="italic" fill="{TECH}">in blue</tspan></text>
<text class="f" {delay(.35)} x="{W-42}" y="51" text-anchor="end" font-family="{MONO}" font-size="11.5" letter-spacing="1" fill="{MUTED}">REFRESHED DAILY</text>
{''.join(cells)}
<g class="f" {delay(2.5)}>
  {labels}
  <text x="{legend_x-8}" y="{gy + 7*step + 17}" text-anchor="end" font-family="{MONO}" font-size="10.5" fill="{MUTED}">less</text>
  {legend}
  <text x="{legend_x + len(BLUE)*14 + 2}" y="{gy + 7*step + 17}" font-family="{MONO}" font-size="10.5" fill="{MUTED}">more</text>
</g>
<g clip-path="url(#heatClip)"><rect class="sh" x="-330" y="76" width="150" height="{h-76}" fill="url(#heatSheen)" opacity=".45"/></g>
"""
    write("heatmap.svg", svg(W, h, body, ["serif", "serif-i", "mono"],
                              f'EnternalBlue07 contribution heatmap, {data["total_contributions"]:,} contributions in the last year.'))


# ---- Monthly activity -----------------------------------------------------------
def activity(data: dict) -> None:
    height = 340
    monthly = data["monthly"][-12:]
    if not monthly:
        raise RuntimeError("Contribution data has no monthly totals.")
    current_month = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
    best_pool = [m for m in monthly if m["month"] != current_month] or monthly
    best = max(best_pool, key=lambda item: item["total"])
    top = max(int(item["total"]) for item in monthly) or 1
    x0, x1, base, maxh, gap = 40, 600, 286, 138, 10
    bw = (x1 - x0 - gap * (len(monthly)-1)) / len(monthly)
    bars = []
    for index, month in enumerate(monthly):
        partial = month["month"] == current_month
        value = int(month["total"])
        bar_h = max(3, round(value / top * maxh))
        x = x0 + index * (bw + gap)
        fill = TECH if month is best else ("#c8c8c3" if partial else INK)
        label = dt.date.fromisoformat(month["month"] + "-01").strftime("%b")
        start = 2.0 + index * .075
        bars.append(
            f'<rect class="g" style="animation-delay:{start:.2f}s" x="{x:.1f}" y="{base-bar_h}" '
            f'width="{bw:.1f}" height="{bar_h}" rx="4" fill="{fill}">'
            f'<title>{label}: {value:,} contributions</title></rect>'
            f'<text class="f" style="animation-delay:{start:.2f}s" x="{x+bw/2:.1f}" y="{base+21}" '
            f'text-anchor="middle" font-family="{MONO}" font-size="10.5" fill="{MUTED}">{label}</text>'
        )
        if month is best:
            bars.append(
                f'<text class="p" style="animation-delay:3.0s" x="{x+bw/2:.1f}" y="{base-bar_h-10}" '
                f'text-anchor="middle" font-family="{MONO}" font-size="11" fill="{TECH}">{value:,}</text>'
            )

    current = int(data["current_streak"]["length"])
    longest = int(data["longest_streak"]["length"])
    active = int(data["active_days"])
    total_days = len(data["days"])
    best_day = data["best_day"]
    streak_note = "current streak" if current < longest else "current streak · longest"
    stats = [
        (f'{current} <tspan font-style="italic">days</tspan>', streak_note),
        (f'{active}<tspan fill="#94949a"> / {total_days}</tspan>', "days with a contribution"),
        (f'{int(best_day["count"])}', f'on {dt.date.fromisoformat(best_day["date"]).strftime("%b %-d")}'),
    ]
    side = []
    for index, (big, small) in enumerate(stats):
        y = 104 + index * 87
        side.append(
            f'<g class="r" {delay(2.6 + index*.16)}>'
            f'<text x="650" y="{y}" font-family="{SERIF}" font-size="39" fill="{INK}">{big}</text>'
            f'<text x="650" y="{y+23}" font-family="{SANS}" font-size="12.5" fill="{MUTED}">{esc(small)}</text></g>'
        )
        if index < 2:
            side.append(f'<rect class="f" {delay(2.65)} x="650" y="{y+43}" width="190" height="1" fill="{RULE}"/>')

    total = int(data["total_contributions"])
    body = f"""
<defs>
  <clipPath id="activityClip"><rect width="{W}" height="{height}" rx="14"/></clipPath>
  <linearGradient id="activitySheen" x1="0" x2="1">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
    <stop offset=".5" stop-color="#ffffff" stop-opacity=".48"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>
</defs>
<rect width="{W}" height="{height}" rx="14" fill="{PAPER}"/>
<text class="f" {delay(1.6)} x="40" y="51" font-family="{MONO}" font-size="11.5" letter-spacing="1.1" fill="{MUTED}">THE LAST 12 MONTHS ON GITHUB</text>
{count_up(total, 38, 111, f'font-family="{SERIF}" font-size="51" fill="{INK}"', 1.7, ' <tspan font-style="italic">contributions</tspan>', 20, 1.25)}
<text class="f" {delay(1.85)} x="40" y="140" font-family="{SANS}" font-size="12.5" fill="{MUTED}">A year of ideas, experiments, and shipped work.</text>
{''.join(bars)}
{''.join(side)}
<g clip-path="url(#activityClip)"><rect class="sh" x="-330" y="4" width="145" height="{height-8}" fill="url(#activitySheen)" opacity=".25"/></g>
"""
    write("activity.svg", svg(W, height, body, ["serif", "serif-i", "sans", "mono"],
                               f'{total:,} contributions in the last year, {current}-day current streak.'))
ount = int(day["count"])
        lvl = level_for(count)
        delay_s = .85 + col * .026 + row * .022
        cells.append(
            f'<rect class="p" style="animation-delay:{delay_s:.3f}s" '
            f'x="{gx + col*step}" y="{gy + row*step}" width="{cell}" height="{cell}" rx="3" '
            f'fill="{BLUE[lvl]}"><title>{esc(day["date"])}: {count} contribution{"s" if count != 1 else ""}</title></rect>'
        )

    right = gx + ncols * step - 3
    labels = "".join(
        f'<text x="{gx + col*step}" y="{gy + 7*step + 17}" font-family="{MONO}" font-size="10.5" fill="{MUTED}">{label}</text>'
        for col, label in months if col < ncols - 8
    )
    legend_x = right - len(BLUE) * 14
    legend = "".join(
        f'<rect x="{legend_x + index*14}" y="{gy + 7*step + 5}" width="11" height="11" rx="2.5" fill="{colour}"/>'
        for index, colour in enumerate(BLUE)
    )
    h = gy + 7*step + 46
    body = f"""
<defs>
  <clipPath id="heatClip"><rect width="{W}" height="{h}" rx="14"/></clipPath>
  <linearGradient id="heatSheen" x1="0" x2="1">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
    <stop offset=".5" stop-color="#ffffff" stop-opacity=".43"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>
</defs>
<rect width="{W}" height="{h}" rx="14" fill="{PAPER}"/>
<text class="r" {delay(.25)} x="42" y="54" font-family="{SERIF}" font-size="36" fill="{INK}">Every day, <tspan font-style="italic" fill="{TECH}">in blue</tspan></text>
<text class="f" {delay(.35)} x="{W-42}" y="51" text-anchor="end" font-family="{MONO}" font-size="11.5" letter-spacing="1" fill="{MUTED}">REFRESHED DAILY</text>
{''.join(cells)}
<g class="f" {delay(2.5)}>
  {labels}
  <text x="{legend_x-8}" y="{gy + 7*step + 17}" text-anchor="end" font-family="{MONO}" font-size="10.5" fill="{MUTED}">less</text>
  {legend}
  <text x="{legend_x + len(BLUE)*14 + 2}" y="{gy + 7*step + 17}" font-family="{MONO}" font-size="10.5" fill="{MUTED}">more</text>
</g>
<g clip-path="url(#heatClip)"><rect class="sh" x="-330" y="76" width="150" height="{h-76}" fill="url(#heatSheen)" opacity=".45"/></g>
"""
    write("heatmap.svg", svg(W, h, body, ["serif", "serif-i", "mono"],
                              f'EnternalBlue07 contribution heatmap, {data["total_contributions"]:,} contributions in the last year.'))


# ---- Monthly activity -----------------------------------------------------------
def activity(data: dict) -> None:
    height = 340
    monthly = data["monthly"][-12:]
    if not monthly:
        raise RuntimeError("Contribution data has no monthly totals.")
    current_month = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
    best_pool = [m for m in monthly if m["month"] != current_month] or monthly
    best = max(best_pool, key=lambda item: item["total"])
    top = max(int(item["total"]) for item in monthly) or 1
    x0, x1, base, maxh, gap = 40, 600, 286, 138, 10
    bw = (x1 - x0 - gap * (len(monthly)-1)) / len(monthly)
    bars = []
    for index, month in enumerate(monthly):
        partial = month["month"] == current_month
        value = int(month["total"])
        bar_h = max(3, round(value / top * maxh))
        x = x0 + index * (bw + gap)
        fill = TECH if month is best else ("#c8c8c3" if partial else INK)
        label = dt.date.fromisoformat(month["month"] + "-01").strftime("%b")
        start = 2.0 + index * .075
        bars.append(
            f'<rect class="g" style="animation-delay:{start:.2f}s" x="{x:.1f}" y="{base-bar_h}" '
            f'width="{bw:.1f}" height="{bar_h}" rx="4" fill="{fill}">'
            f'<title>{label}: {value:,} contributions</title></rect>'
            f'<text class="f" style="animation-delay:{start:.2f}s" x="{x+bw/2:.1f}" y="{base+21}" '
            f'text-anchor="middle" font-family="{MONO}" font-size="10.5" fill="{MUTED}">{label}</text>'
        )
        if month is best:
            bars.append(
                f'<text class="p" style="animation-delay:3.0s" x="{x+bw/2:.1f}" y="{base-bar_h-10}" '
                f'text-anchor="middle" font-family="{MONO}" font-size="11" fill="{TECH}">{value:,}</text>'
            )

    current = int(data["current_streak"]["length"])
    longest = int(data["longest_streak"]["length"])
    active = int(data["active_days"])
    total_days = len(data["days"])
    best_day = data["best_day"]
    streak_note = "current streak" if current < longest else "current streak · longest"
    stats = [
        (f'{current} <tspan font-style="italic">days</tspan>', streak_note),
        (f'{active}<tspan fill="#94949a"> / {total_days}</tspan>', "days with a contribution"),
        (f'{int(best_day["count"])}', f'on {dt.date.fromisoformat(best_day["date"]).strftime("%b %-d")}'),
    ]
    side = []
    for index, (big, small) in enumerate(stats):
        y = 104 + index * 87
        side.append(
            f'<g class="r" {delay(2.6 + index*.16)}>'
            f'<text x="650" y="{y}" font-family="{SERIF}" font-size="39" fill="{INK}">{big}</text>'
            f'<text x="650" y="{y+23}" font-family="{SANS}" font-size="12.5" fill="{MUTED}">{esc(small)}</text></g>'
        )
        if index < 2:
            side.append(f'<rect class="f" {delay(2.65)} x="650" y="{y+43}" width="190" height="1" fill="{RULE}"/>')

    total = int(data["total_contributions"])
    body = f"""
<defs>
  <clipPath id="activityClip"><rect width="{W}" height="{height}" rx="14"/></clipPath>
  <linearGradient id="activitySheen" x1="0" x2="1">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
    <stop offset=".5" stop-color="#ffffff" stop-opacity=".48"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>
</defs>
<rect width="{W}" height="{height}" rx="14" fill="{PAPER}"/>
<text class="f" {delay(1.6)} x="40" y="51" font-family="{MONO}" font-size="11.5" letter-spacing="1.1" fill="{MUTED}">THE LAST 12 MONTHS ON GITHUB</text>
{count_up(total, 38, 111, f'font-family="{SERIF}" font-size="51" fill="{INK}"', 1.7, ' <tspan font-style="italic">contributions</tspan>', 20, 1.25)}
<text class="f" {delay(1.85)} x="40" y="140" font-family="{SANS}" font-size="12.5" fill="{MUTED}">A year of ideas, experiments, and shipped work.</text>
{''.join(bars)}
{''.join(side)}
<g clip-path="url(#activityClip)"><rect class="sh" x="-330" y="4" width="145" height="{height-8}" fill="url(#activitySheen)" opacity=".25"/></g>
"""
    write("activity.svg", svg(W, height, body, ["serif", "serif-i", "sans", "mono"],
                               f'{total:,} contributions in the last year, {current}-day current streak.'))
              f'{total:,} contributions in the last year, {current}-day current streak.'))


# ---- Feature cards (three worlds) ----------------------------------------------
TILE_W, TILE_H = W/3 - 8, 210
FEATURES = [
    (
        "build", "BUILD", TECH, "#ffffff", "AI products",
        "Agent platforms and data products built around real operational needs.",
        "TALLY NEXUS  ·  DATAFORGE AI",
    ),
    (
        "engineer", "ENGINEER", TEAL, "#ffffff", "Robotics",
        "CAREMATE connects Flutter software to ESP32 hardware over BLE.",
        "CAREMATE  ·  EMBEDDED + MOBILE",
    ),
    (
        "learn", "TEACH", GOLD, INK, "AI education",
        "Prompt engineering, AI tools, and useful workflows taught hands-on.",
        "AI TOOLS  ·  PROMPT ENGINEERING",
    ),
]


def feature_tile(name: str, label: str, colour: str, on: str, title: str,
                 blurb: str, meta: str, index: int) -> None:
    delay_s = 3.05 + index * .18
    title_lines = wrap(title, 18)
    blurb_lines = wrap(blurb, 38)[:2]
    title_markup = text_lines(23, 105, title_lines, 30,
                              f'font-family="{SERIF}" font-size="28" fill="{on}"')
    blurb_markup = text_lines(23, 151, blurb_lines, 17,
                              f'font-family="{SANS}" font-size="11.5" fill="{on}" opacity=".95"')
    body = f"""
<defs>
  <clipPath id="tileClip"><rect width="{TILE_W:.3f}" height="{TILE_H}" rx="14"/></clipPath>
  <linearGradient id="tileSheen" x1="0" x2="1">
    <stop offset="0" stop-color="#fff" stop-opacity="0"/>
    <stop offset=".5" stop-color="#fff" stop-opacity=".34"/>
    <stop offset="1" stop-color="#fff" stop-opacity="0"/>
  </linearGradient>
</defs>
<g class="ti" {delay(delay_s)}>
  <g clip-path="url(#tileClip)">
    <rect width="{TILE_W:.3f}" height="{TILE_H}" fill="{colour}"/>
    <circle class="rg" {delay(delay_s+.45)} cx="{TILE_W-36:.1f}" cy="{TILE_H-30}" r="56" fill="none" stroke="{on}" stroke-opacity=".5" stroke-width="2"/>
    <rect class="sh" style="animation-delay:{delay_s+1.2:.2f}s" x="-120" y="-20" width="88" height="{TILE_H+40}" fill="url(#tileSheen)" transform="translate(-260 0)"/>
  </g>
  <text class="sl" {delay(delay_s+.2)} x="23" y="34" font-family="{MONO}" font-size="10.5" letter-spacing="1.3" fill="{on}">{esc(label)}</text>
  <g class="ai" {delay(delay_s+.36)}><path class="n" style="animation-delay:{delay_s+1.1:.2f}s" d="M{TILE_W-42:.1f} 28 H{TILE_W-24:.1f} M{TILE_W-31:.1f} 20 L{TILE_W-23:.1f} 28 L{TILE_W-31:.1f} 36" fill="none" stroke="{on}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></g>
  <g class="ro" {delay(delay_s+.3)}>{title_markup}</g>
  <g class="r" {delay(delay_s+.72)}>{blurb_markup}</g>
  <text class="f" {delay(delay_s+1.0)} x="23" y="198" font-family="{MONO}" font-size="9.3" letter-spacing=".2" fill="{on}" opacity=".82">{esc(meta)}</text>
</g>
"""
    write(f"{name}.svg", svg(TILE_W, TILE_H, body, ["serif", "sans", "mono"],
                              f"{label}: {title}. {blurb}", bottom=0))


# ---- Project cards --------------------------------------------------------------
PROJECTS = [
    {
        "repo": "Tally-Nexus",
        "file": "repo-tally-nexus.svg",
        "name": "TALLY NEXUS",
        "desc": "A deterministic clearinghouse for AI-agent micro-IOUs: task evidence, SLA verdicts, signed obligations, netting, and PayPal settlement.",
        "stack": "TypeScript  ·  Node.js  ·  SQLite  ·  PayPal",
        "color": TECH,
    },
    {
        "repo": "CAREMATE",
        "file": "repo-caremate.svg",
        "name": "CAREMATE",
        "desc": "A home-care companion connecting a Flutter app to an ESP32 medication robot, with BLE state transitions and sensor-confirmed tablet drops.",
        "stack": "Flutter  ·  Dart  ·  ESP32  ·  BLE",
        "color": TEAL,
    },
    {
        "repo": "SentinelAI",
        "file": "repo-sentinelai.svg",
        "name": "SENTINEL AI",
        "desc": "Fraud and anomaly intelligence combining XGBoost, Isolation Forest, TreeSHAP explanations, and human-review case dossiers.",
        "stack": "Python  ·  FastAPI  ·  Next.js  ·  XGBoost",
        "color": GOLD,
    },
]


def repo_meta(repo_name: str, fallback_stack: str) -> tuple[str, int]:
    try:
        response = requests.get(
            f"https://api.github.com/repos/{LOGIN}/{repo_name}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-art"},
            timeout=15,
        )
        response.raise_for_status()
        item = response.json()
        language = item.get("language") or fallback_stack.split("·")[0].strip()
        stars = int(item.get("stargazers_count", 0))
        return language, stars
    except Exception as exc:
        print(f"Repo metadata unavailable for {repo_name}: {exc}")
        return fallback_stack.split("·")[0].strip(), 0


def repo_card(project: dict, index: int) -> None:
    width, height = TILE_W, 178
    language, stars = repo_meta(project["repo"], project["stack"])
    meta = f"{project['stack']}  ·  ★ {stars}" if stars else project["stack"]
    lines = wrap(project["desc"], 37)[:3]
    delay_s = 4.35 + index * .15
    body = f"""
<defs>
  <clipPath id="repoClip"><rect width="{width:.3f}" height="{height}" rx="14"/></clipPath>
  <linearGradient id="repoSheen" x1="0" x2="1">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
    <stop offset=".5" stop-color="#ffffff" stop-opacity=".82"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>
</defs>
<g clip-path="url(#repoClip)">
  <rect width="{width:.3f}" height="{height}" rx="14" fill="{PAPER}"/>
  <rect class="sh" style="animation-delay:{delay_s+1.0:.2f}s" x="-120" y="-10" width="82" height="{height+20}" fill="url(#repoSheen)"/>
</g>
<g class="r" {delay(delay_s)}>
  <rect x="23" y="29" width="8" height="8" rx="2" fill="{project['color']}"/>
  <text x="39" y="39" font-family="{SANS}" font-weight="600" font-size="17.5" fill="{INK}">{esc(project["name"])}</text>
  {text_lines(23, 70, lines, 19, f'font-family="{SANS}" font-size="12.5" fill="{INK_SOFT}"')}
  <text x="23" y="{height-19}" font-family="{MONO}" font-size="9.2" fill="{MUTED}">{esc(meta)}</text>
  <path class="n" style="animation-delay:{delay_s+1.3:.2f}s" d="M{width-34:.1f} 38 L{width-22:.1f} 26 M{width-31:.1f} 26 H{width-22:.1f} V35" fill="none" stroke="{project['color']}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
</g>
"""
    write(project["file"], svg(width
, height, body, ["sans", "sans-b", "mono"],
                                f'{project["name"]}: {project["desc"]}', bottom=0))


def section_title(text: str, italic: str, theme: str) -> None:
    foreground = "#e6edf3" if theme == "dark" else INK
    body = (
        f'<text class="r" {delay(4.1)} x="2" y="47" font-family="{SERIF}" font-size="35" fill="{foreground}">'
        f'{esc(text)} <tspan font-style="italic">{esc(italic)}</tspan></text>'
    )
    write(f"title-coding-{theme}.svg", svg(W, 62, body, ["serif", "serif-i"],
                                          f"{text} {italic}", bottom=0))


# ---- Engineering / with intent -------------------------------------------------
def engineering_intent() -> None:
    card_w, card_h = 188, 205
    x_positions = [34, 242, 450, 658]
    cards = [
        ("01 / BUILD", "SOFTWARE", ["Applications", "Systems", "Architecture"], TECH, "#ffffff"),
        ("02 / SHAPE", "DESIGN", ["UI / UX", "Visual systems", "Experiences"], TEAL, "#ffffff"),
        ("03 / EXPLORE", "INTELLIGENCE", ["AI", "Agents", "Automation"], GOLD, INK),
        ("04 / SHIP", "CLOUD", ["APIs", "Infrastructure", "Deployment"], "#34465f", "#ffffff"),
    ]
    blocks = []
    for index, (label, title, items, colour, foreground) in enumerate(cards):
        x = x_positions[index]
        delay_s = .45 + index * .16
        lines = text_lines(x+22, 230, items, 22, f'font-family="{SANS}" font-size="13.5" fill="{foreground}"')
        blocks.append(f"""
<g class="ti" {delay(delay_s)}>
  <g clip-path="url(#eng{index})">
    <rect x="{x}" y="116" width="{card_w}" height="{card_h}" rx="14" fill="{colour}"/>
    <circle class="rg" {delay(delay_s+.38)} cx="{x+card_w-28}" cy="292" r="46" fill="none" stroke="{foreground}" stroke-opacity=".5" stroke-width="2"/>
    <rect class="sh" style="animation-delay:{delay_s+1.2:.2f}s" x="{x-100}" y="104" width="75" height="{card_h+24}" fill="url(#engSheen)"/>
  </g>
  <text class="sl" {delay(delay_s+.2)} x="{x+22}" y="145" font-family="{MONO}" font-size="10" letter-spacing=".8" fill="{foreground}">{label}</text>
  <text class="ro" {delay(delay_s+.32)} x="{x+22}" y="194" font-family="{SERIF}" font-size="21" fill="{foreground}">{title}</text>
  {lines}
</g>
""")
    defs = "".join(
        f'<clipPath id="eng{index}"><rect x="{x_positions[index]}" y="116" width="{card_w}" height="{card_h}" rx="14"/></clipPath>'
        for index in range(4)
    )
    body = f"""
<defs>
  {defs}
  <linearGradient id="engSheen" x1="0" x2="1">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
    <stop offset=".5" stop-color="#ffffff" stop-opacity=".34"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="engRule" x1="0" x2="1">
    <stop offset="0" stop-color="#22d3ee" stop-opacity="0"/>
    <stop offset=".5" stop-color="#22d3ee"/>
    <stop offset="1" stop-color="#22d3ee" stop-opacity="0"/>
  </linearGradient>
</defs>
<rect width="{W}" height="354" rx="14" fill="{DARK}"/>
<text class="r" {delay(.1)} x="36" y="65" font-family="{SERIF}" font-size="45" fill="#e6edf3">Engineering <tspan font-style="italic" fill="#67e8f9">/ with intent</tspan></text>
<line x1="36" y1="88" x2="844" y2="88" stroke="#30363d"/>
{''.join(blocks)}
<rect class="live" x="36" y="338" width="808" height="2.5" rx="1.2" fill="url(#engRule)"/>
"""
    write("engineering-intent.svg", svg(W, 354, body, ["serif", "serif-i", "sans", "mono"],
                                        "Engineering with intent: software, design, intelligence, and cloud."))


# ---- Team evaluation snapshot --------------------------------------------------
def repo_totals() -> tuple[int | None, int | None]:
    try:
        response = requests.get(
            f"https://api.github.com/users/{LOGIN}/repos?per_page=100&type=owner&sort=updated",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-art"},
            timeout=20,
        )
        response.raise_for_status()
        repos = [item for item in response.json() if not item.get("private", False)]
        return len(repos), sum(int(item.get("stargazers_count", 0)) for item in repos)
    except Exception as exc:
        print(f"Public repository summary unavailable: {exc}")
        return None, None


def team_evaluation(data: dict) -> None:
    repo_count, stars = repo_totals()
    public_value = f"{repo_count} repositories · {stars} stars" if repo_count is not None else "Explore public work"
    public_detail = "Featured builds linked below" if repo_count is not None else "Live repository data unavailable"
    contributions = int(data["total_contributions"])
    active = int(data["active_days"])
    card_w, card_h = 258, 128
    positions = [34, 311, 588]
    definitions = [
        {
            "title": "Role fit", "small": "SOFTWARE · AI · PRODUCT",
            "value": "Builder mindset",
            "detail": "Software engineering · AI systems · Product design",
            "fill": TECH, "ink": "#ffffff",
        },
        {
            "title": "Public proof", "small": "OPEN-SOURCE WORK",
            "value": public_value,
            "detail": public_detail,
            "fill": TEAL, "ink": "#ffffff",
        },
        {
            "title": "Momentum", "small": "LAST 12 MONTHS",
            "value": f"{contributions:,} contributions",
            "detail": f"{active} active days",
            "fill": GOLD, "ink": INK,
        },
    ]
    items = []
    for index, card in enumerate(definitions):
        x = positions[index]
        dly = .5 + index*.18
        value_size = 21 if len(card["value"]) <= 18 else (18 if len(card["value"]) <= 25 else 15.5)
        detail_lines = wrap(card["detail"], 31)[:2]
        detail_markup = text_lines(x+20, 181, detail_lines, 13, f'font-family="{SANS}" font-size="9.4" fill="{card["ink"]}" opacity=".92"')
        items.append(f"""
<g class="ti" {delay(dly)}>
  <rect x="{x}" y="74" width="{card_w}" height="{card_h}" rx="14" fill="{card["fill"]}"/>
  <circle class="rg" {delay(dly+.3)} cx="{x+card_w-28}" cy="175" r="34" fill="none" stroke="{card["ink"]}" stroke-opacity=".48" stroke-width="2"/>
  <rect class="sh" style="animation-delay:{dly+1.2:.2f}s" x="{x-100}" y="64" width="72" height="{card_h+20}" fill="url(#proofSheen)"/>
  <text class="sl" {delay(dly+.18)} x="{x+20}" y="101" font-family="{SANS}" font-size="18" font-weight="600" fill="{card["ink"]}">{esc(card["title"])}</text>
  <text class="f" {delay(dly+.38)} x="{x+20}" y="124" font-family="{MONO}" font-size="8.8" letter-spacing=".65" fill="{card["ink"]}" opacity=".82">{esc(card["small"])}</text>
  <text class="ro" {delay(dly+.42)} x="{x+20}" y="157" font-family="{SERIF}" font-size="{value_size}" fill="{card["ink"]}">{esc(card["value"])}</text>
  {detail_markup}
</g>
""")
    body = f"""
<defs><linearGradient id="proofSheen" x1="0" x2="1">
  <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
  <stop offset=".5" stop-color="#ffffff" stop-opacity=".34"/>
  <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
</linearGradient></defs>
<rect width="{W}" height="248" rx="14" fill="{DARK}"/>
<text class="r" {delay(.12)} x="{W/2}" y="42" text-anchor="middle" font-family="{SANS}" font-size="22" font-weight="600" fill="#e6edf3">What teams can evaluate quickly</text>
<line x1="28" y1="55" x2="852" y2="55" stroke="#30363d"/>
{''.join(items)}
<text class="f" {delay(1.2)} x="{W/2}" y="231" text-anchor="middle" font-family="{MONO}" font-size="10.2" fill="#9aa4b2">TECH EXPLORER · AI &amp; PROMPT ENGINEERING · LEARNING BY BUILDING</text>
"""
    write("team-evaluation.svg", svg(W, 248, body, ["serif", "sans", "sans-b", "mono"],
                                        f"Role fit, {repo_count} public repositories, {stars} public stars, {contributions:,} contributions and {active} active days."))


# ---- About section title and three cards ----------------------------------------
def about_title() -> None:
    body = (
        f'<text class="r" {delay(.12)} x="2" y="45" font-family="{SERIF}" font-size="35" fill="#e6edf3">'
        f'What I&#39;m <tspan font-style="italic">about</tspan></text>'
    )
    write("about-title.svg", svg(W, 56, body, ["serif", "serif-i"], "What I'm about", bottom=0))
"{x+20}" y="124" font-family="{MONO}" font-size="8.8" letter-spacing=".65" fill="{card["ink"]}" opacity=".82">{esc(card["small"])}</text>
  <text class="ro" {delay(dly+.42)} x="{x+20}" y="157" font-family="{SERIF}" font-size="{value_size}" fill="{card["ink"]}">{esc(card["value"])}</text>
  {detail_markup}
</g>
""")
    body = f"""
<defs><linearGradient id="proofSheen" x1="0" x2="1">
  <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
  <stop offset=".5" stop-color="#ffffff" stop-opacity=".34"/>
  <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
</linearGradient></defs>
<rect width="{W}" height="248" rx="14" fill="{DARK}"/>
<text class="r" {delay(.12)} x="{W/2}" y="42" text-anchor="middle" font-family="{SANS}" font-size="22" font-weight="600" fill="#e6edf3">What teams can evaluate quickly</text>
<line x1="28" y1="55" x2="852" y2="55" stroke="#30363d"/>
{''.join(items)}
<text class="f" {delay(1.2)} x="{W/2}" y="231" text-anchor="middle" font-family="{MONO}" font-size="10.2" fill="#9aa4b2">TECH EXPLORER · AI &amp; PROMPT ENGINEERING · LEARNING BY BUILDING</text>
"""
    write("team-evaluation.svg", svg(W, 248, body, ["serif", "sans", "sans-b", "mono"],
                                        f"Role fit, {repo_count} public repositories, {stars} public stars, {contributions:,} contributions and {active} active days."))


# ---- About section title and three cards ----------------------------------------
def about_title() -> None:
    body = (
        f'<text class="r" {delay(.12)} x="2" y="45" font-family="{SERIF}" font-size="35" fill="#e6edf3">'
        f'What I&#39;m <tspan font-style="italic">about</tspan></text>'
    )
    write("about-title.svg", svg(W, 56, body, ["serif", "serif-i"], "What I'm about", bottom=0))


def about_card(filename: str, label: str, colour: str, title: str,
               description: str, footer: str, index: int) -> None:
    width, height = TILE_W, 206
    dly = .25 + index*.16
    lines = wrap(description, 34)[:3]
    desc = text_lines(22, 112, lines, 20,
                      f'font-family="{SANS}" font-size="12.5" fill="{INK_SOFT}"')
    body = f"""
<defs>
  <clipPath id="aboutClip"><rect width="{width:.3f}" height="{height}" rx="14"/></clipPath>
  <linearGradient id="aboutSheen" x1="0" x2="1">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
    <stop offset=".5" stop-color="#ffffff" stop-opacity=".8"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>
</defs>
<g class="ti" {delay(dly)}>
  <g clip-path="url(#aboutClip)">
    <rect width="{width:.3f}" height="{height}" rx="14" fill="{PAPER}"/>
    <rect class="sh" style="animation-delay:{dly+1.0:.2f}s" x="-120" y="-10" width="82" height="{height+20}" fill="url(#aboutSheen)"/>
  </g>
  <rect class="live" x="22" y="31" width="9" height="9" rx="3" fill="{colour}"/>
  <text class="sl" {delay(dly+.15)} x="43" y="41" font-family="{SANS}" font-size="16.5" font-weight="600" fill="{INK}">{esc(title)}</text>
  {desc}
  <text class="f" {delay(dly+.6)} x="22" y="180" font-family="{MONO}" font-size="10.2" fill="{MUTED}">{esc(footer)}</text>
</g>
"""
    write(filename, svg(width, height, body, ["sans", "sans-b", "mono"], f"{label}: {description}", bottom=0))


# ---- Run all renderers ----------------------------------------------------------
def main() -> None:
    if not CONTRIB_PATH.exists():
        raise SystemExit(f"Missing {CONTRIB_PATH}; run scripts/fetch_profile_contributions.py first.")
    data = json.loads(CONTRIB_PATH.read_text(encoding="utf-8"))
    if data.get("username", "").lower() != LOGIN.lower():
        raise SystemExit("Contribution data username does not match this profile; refusing to render foreign stats.")

    hero()
    heatmap(data)
    activity(data)

    feature_tile(*FEATURES[0], 0)
    feature_tile(*FEATURES[1], 1)
    feature_tile(*FEATURES[2], 2)

    section_title("What I'm", "coding", "dark")
    section_title("What I'm", "coding", "light")
    for index, project in enumerate(PROJECTS):
        repo_card(project, index)

    engineering_intent()
    team_evaluation(data)
    about_title()
    about_card("about-curious.svg", "Curious Builder", TECH, "Curious Builder",
               "I learn by building real projects, experimenting with ideas, and solving problems through technology.",
               "BUILD  ·  EXPERIMENT  ·  LEARN", 0)
    about_card("about-creative.svg", "AI & Systems Enthusiast", TEAL, "AI & Systems Enthusiast",
               "I'm passionate about AI, automation, and building intelligent systems that solve real-world problems.",
               "AI  ·  AGENTS  ·  AUTOMATION", 1)
    about_card("about-technical.svg", "Design & Technology", GOLD, "Design & Technology",
               "I enjoy turning complex ideas into clean, useful, and thoughtful digital experiences.",
               "PRODUCT  ·  UI/UX  ·  ENGINEERING", 2)

    print(
        f"Rendered profile art for {LOGIN}: {int(data['total_contributions']):,} contributions, "
        f"{int(data['active_days'])} active days, {int(data['current_streak']['length'])}-day streak."
    )


if __name__ == "__main__":
    main()
