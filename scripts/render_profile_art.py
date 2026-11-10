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
