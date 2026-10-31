#!/usr/bin/env python3
"""Generate assets/stats.svg — a self-hosted GitHub stats card.

Self-hosted on purpose: the image is served from this repo (raw.githubusercontent.com),
so it never depends on github-readme-stats / vercel being reachable.

Usage:
    python tools/gen_stats.py --user moriruruka --out assets/stats.svg
    GITHUB_TOKEN=... python tools/gen_stats.py ...   # avoids the 60 req/h limit

If the API is unreachable the script leaves the existing SVG untouched and exits 0,
so a flaky network never breaks the profile page.
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.github.com"

LANGS = [
    ("Python", "#22d3ee"),
    ("MATLAB", "#fb923c"),
    ("PowerShell", "#60a5fa"),
    ("Shell", "#a78bfa"),
    ("Dockerfile", "#34d399"),
    ("Batchfile", "#94a3b8"),
    ("C++", "#f472b6"),
    ("C", "#facc15"),
]
OTHER = ("其他", "#334155")

FONT = "'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif"
MONO = "'Cascadia Code','JetBrains Mono',Consolas,'Courier New',monospace"

W, H = 1200, 300


def get(url, token=None):
    req = urllib.request.Request(url, headers={
        "User-Agent": "moriruruka-profile-stats",
        "Accept": "application/vnd.github+json",
    })
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def f(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def collect(user, token):
    u = get(f"{API}/users/{user}", token)
    repos = get(f"{API}/users/{user}/repos?per_page=100&type=owner", token)

    stars = 0
    words = {}
    for r in repos:
        if r.get("fork"):
            continue
        stars += r.get("stargazers_count", 0)
        try:
            for k, v in get(r["languages_url"], token).items():
                words[k] = words.get(k, 0) + v
        except Exception:
            pass

    total = sum(words.values()) or 1
    ranked = sorted(words.items(), key=lambda kv: -kv[1])
    top = ranked[:4]
    rest = sum(v for _, v in ranked[4:])
    langs = [(k, v / total) for k, v in top]
    if rest:
        langs.append((OTHER[0], rest / total))

    return dict(login=u["login"], repos=u["public_repos"], stars=stars,
                followers=u["followers"], year=u["created_at"][:4], langs=langs)


def build(d):
    colors = dict(LANGS)
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

    # ---- stat blocks ----
    stats = [
        ("公开仓库", str(d["repos"]), "#22d3ee"),
        ("Star 总数", str(d["stars"]), "#a78bfa"),
        ("关注者", str(d["followers"]), "#60a5fa"),
        ("始于", d["year"], "#fbbf24"),
    ]
    blocks = []
    for i, (label, value, color) in enumerate(stats):
        x = 44 + i * 300
        blocks.append(
            f'<rect x="{x}" y="86" width="26" height="3" rx="1.5" fill="{color}" opacity="0.85"/>'
            f'<text x="{x}" y="136" font-family="{FONT}" font-size="47" font-weight="700" '
            f'fill="#e6edf3" letter-spacing="-0.6">{value}</text>'
            f'<text x="{x}" y="164" font-family="{FONT}" font-size="14.5" fill="#6b7c96">{label}</text>'
        )

    # ---- language bar ----
    x0, x1, bar_y, bar_h = 44, 1156, 216, 10
    span = x1 - x0
    cursor = x0
    segs, legend = [], []
    for i, (name, pct) in enumerate(d["langs"]):
        w = span * pct
        color = colors.get(name, OTHER[1])
        segs.append(f'<rect x="{f(cursor)}" y="{bar_y}" width="{f(w)}" height="{bar_h}" '
                    f'fill="{color}" opacity="0.92"/>')
        cursor += w

        lx = 44 + i * 158
        legend.append(
            f'<circle cx="{lx + 4}" cy="256" r="4" fill="{color}" opacity="0.92"/>'
            f'<text x="{lx + 16}" y="260" font-family="{FONT}" font-size="14" fill="#93a4bd">'
            f'{name}</text>'
            f'<text x="{lx + 16}" y="279" font-family="{MONO}" font-size="12" fill="#5b6b85">'
            f'{pct * 100:.1f}%</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub stats for {d["login"]}">
  <title>GitHub stats — {d["login"]}</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#060911"/>
      <stop offset="50%" stop-color="#0c1526"/>
      <stop offset="100%" stop-color="#080c17"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#22d3ee" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="#22d3ee" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="edge" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#22d3ee" stop-opacity="0"/>
      <stop offset="30%" stop-color="#22d3ee" stop-opacity="0.9"/>
      <stop offset="70%" stop-color="#a78bfa" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#a78bfa" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="round"><rect x="0" y="0" width="{W}" height="{H}" rx="18" ry="18"/></clipPath>
    <clipPath id="bar"><rect x="44" y="216" width="1112" height="10" rx="5"/></clipPath>
  </defs>

  <g clip-path="url(#round)">
    <rect width="{W}" height="{H}" fill="url(#bg)"/>
    <ellipse cx="1080" cy="40" rx="320" ry="200" fill="url(#glow)"/>
    <g opacity="0.045" stroke="#7dd3fc" stroke-width="1">
      <path d="M0 74 H1200 M0 148 H1200 M0 222 H1200"/>
      <path d="M142 0 V300 M284 0 V300 M426 0 V300 M568 0 V300 M710 0 V300 M852 0 V300 M994 0 V300 M1136 0 V300"/>
    </g>
    <rect x="44" y="34" width="2.5" height="52" rx="1.25" fill="url(#edge)"/>

    <text x="72" y="52" font-family="{MONO}" font-size="11.5" letter-spacing="3.6" fill="#5b6b85">GITHUB STATS</text>
    <text x="1156" y="52" text-anchor="end" font-family="{MONO}" font-size="11.5" fill="#41506a">updated {stamp}</text>

    {"".join(blocks)}

    <text x="44" y="201" font-family="{FONT}" font-size="12.5" letter-spacing="1.5" fill="#4c5a72">语言分布</text>
    <rect x="128" y="196" width="{W - 172}" height="1" fill="#1b2740"/>
    <g clip-path="url(#bar)">
      {"".join(segs)}
    </g>
    {"".join(legend)}
  </g>

  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="18" ry="18" fill="none" stroke="#1e2d45" stroke-width="1"/>
</svg>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="moriruruka")
    ap.add_argument("--out", default="assets/stats.svg")
    a = ap.parse_args()

    try:
        data = collect(a.user, os.environ.get("GITHUB_TOKEN"))
    except Exception as e:  # noqa: BLE001 - never break the profile page
        print(f"stats: fetch failed ({e}); keeping existing {a.out}", file=sys.stderr)
        return 0

    svg = build(data)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)
    print(f"stats: wrote {a.out} ({len(svg)} bytes) "
          f"repos={data['repos']} stars={data['stars']} followers={data['followers']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
