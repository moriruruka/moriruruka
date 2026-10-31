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
import re
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

W, H = 760, 500
PAD = 44


def _open(url, token=None):
    req = urllib.request.Request(url, headers={
        "User-Agent": "moriruruka-profile-stats",
        "Accept": "application/vnd.github+json",
    })
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r), r.headers


def get(url, token=None):
    return _open(url, token)[0]


def commit_count(repo, token):
    """Default-branch commit count, read off the Link header's last page."""
    try:
        _, headers = _open(
            f'{API}/repos/{repo["owner"]["login"]}/{repo["name"]}/commits'
            f'?per_page=1&sha={repo["default_branch"]}', token)
    except Exception:
        return 0
    m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', headers.get("Link") or "")
    return int(m.group(1)) if m else 1


def search_count(q, token):
    try:
        return get(f"{API}/search/issues?q={q}&per_page=1", token).get("total_count", 0)
    except Exception:
        return 0


def f(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def collect(user, token):
    u = get(f"{API}/users/{user}", token)
    repos = get(f"{API}/users/{user}/repos?per_page=100&type=owner", token)

    stars = forks = commits = 0
    words = {}
    ranked_repos = []
    for r in repos:
        if r.get("fork"):
            continue
        s = r.get("stargazers_count", 0)
        stars += s
        forks += r.get("forks_count", 0)
        ranked_repos.append((r["name"], s))
        commits += commit_count(r, token)
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

    ranked_repos.sort(key=lambda kv: (-kv[1], kv[0]))

    return dict(login=u["login"], repos=u["public_repos"], stars=stars, forks=forks,
                followers=u["followers"], following=u["following"], year=u["created_at"][:4],
                commits=commits, langs=langs,
                prs=search_count(f"author:{user}+type:pr", token),
                issues=search_count(f"author:{user}+type:issue", token),
                top=ranked_repos[:4], maxstars=max([s for _, s in ranked_repos] or [1]))


def build(d):
    colors = dict(LANGS)
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

    # ---- headline numbers ------------------------------------------------
    stats = [
        ("公开仓库", str(d["repos"]), "#22d3ee"),
        ("Star 总数", str(d["stars"]), "#a78bfa"),
        ("提交总数", str(d["commits"]), "#60a5fa"),
        ("关注者", str(d["followers"]), "#fbbf24"),
    ]
    blocks = []
    for i, (label, value, color) in enumerate(stats):
        x = PAD + i * 168
        blocks.append(
            f'<rect x="{x}" y="86" width="22" height="3" rx="1.5" fill="{color}" opacity="0.85"/>'
            f'<text x="{x}" y="128" font-family="{FONT}" font-size="36" font-weight="700" '
            f'fill="#e6edf3" letter-spacing="-0.6">{value}</text>'
            f'<text x="{x}" y="150" font-family="{FONT}" font-size="13.5" fill="#6b7c96">{label}</text>'
        )

    # ---- secondary numbers ----------------------------------------------
    minor = [("PR", str(d["prs"])), ("Issue", str(d["issues"])),
             ("Fork", str(d["forks"])), ("关注中", str(d["following"]))]
    chips = []
    for i, (label, value) in enumerate(minor):
        x = PAD + i * 168
        chips.append(
            f'<rect x="{x}" y="172" width="96" height="26" rx="13" fill="#101a2c" stroke="#1e2d45"/>'
            f'<text x="{x + 13}" y="189.5" font-family="{FONT}" font-size="11.5" fill="#5b6b85">{label}</text>'
            f'<text x="{x + 83}" y="190" text-anchor="end" font-family="{MONO}" font-size="13" '
            f'font-weight="700" fill="#cbd8ea">{value}</text>'
        )

    # ---- stacked language bar -------------------------------------------
    x0, x1, bar_y, bar_h = PAD, W - PAD, 240, 8
    span = x1 - x0
    cursor = x0
    segs = []
    for name, pct in d["langs"]:
        color = colors.get(name, OTHER[1])
        w = span * pct
        segs.append(f'<rect x="{f(cursor)}" y="{bar_y}" width="{f(w)}" height="{bar_h}" '
                    f'fill="{color}" opacity="0.92"/>')
        cursor += w

    # ---- language legend, one compact flowing line -----------------------
    legend = []
    lx = x0
    for name, pct in d["langs"]:
        color = colors.get(name, OTHER[1])
        label = f"{name}"
        value = f"{pct * 100:.1f}%"
        w_label = sum(12.0 if ord(ch) > 0x2E80 else 7.0 for ch in label)
        w_value = len(value) * 6.6
        legend.append(
            f'<circle cx="{f(lx + 4)}" cy="274" r="3.6" fill="{color}"/>'
            f'<text x="{f(lx + 13)}" y="278" font-family="{FONT}" font-size="12" fill="#93a4bd">{label}</text>'
            f'<text x="{f(lx + 13 + w_label + 7)}" y="278" font-family="{MONO}" '
            f'font-size="11.5" fill="#5b6b85">{value}</text>'
        )
        lx += 13 + w_label + 7 + w_value + 20

    # ---- top repositories by stars ---------------------------------------
    track_x, track_w = 292, 330
    rows = []
    for i, (name, s) in enumerate(d["top"]):
        y = 338 + i * 32
        bar_w = track_w * (s / d["maxstars"]) if d["maxstars"] else 0
        nm = name if len(name) <= 30 else name[:29] + "…"
        rows.append(
            f'<text x="{PAD}" y="{y}" font-family="{FONT}" font-size="12.5" fill="#93a4bd">{nm}</text>'
            f'<rect x="{track_x}" y="{y - 9}" width="{track_w}" height="6" rx="3" fill="#16233a"/>'
            f'<rect x="{track_x}" y="{y - 9}" width="{f(bar_w)}" height="6" rx="3" '
            f'fill="#22d3ee" opacity="0.75"/>'
            f'<text x="{W - PAD}" y="{y}" text-anchor="end" font-family="{MONO}" font-size="11.5" '
            f'fill="#5b6b85">{s}</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub stats for {d["login"]}: {d["repos"]} repos, {d["stars"]} stars, {d["commits"]} commits, {d["followers"]} followers">
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
    <clipPath id="bar"><rect x="{x0}" y="{bar_y}" width="{span}" height="{bar_h}" rx="4"/></clipPath>
  </defs>

  <g clip-path="url(#round)">
    <rect width="{W}" height="{H}" fill="url(#bg)"/>
    <ellipse cx="700" cy="30" rx="240" ry="180" fill="url(#glow)"/>
    <g opacity="0.045" stroke="#7dd3fc" stroke-width="1">
      <path d="M0 78 H760 M0 182 H760 M0 286 H760 M0 390 H760"/>
      <path d="M142 0 V500 M284 0 V500 M426 0 V500 M568 0 V500 M710 0 V500"/>
    </g>
    <rect x="{PAD}" y="34" width="2.5" height="46" rx="1.25" fill="url(#edge)"/>

    <text x="{PAD + 28}" y="50" font-family="{MONO}" font-size="11.5" letter-spacing="3.6" fill="#5b6b85">GITHUB STATS</text>
    <text x="{W - PAD}" y="50" text-anchor="end" font-family="{MONO}" font-size="11.5" fill="#41506a">updated {stamp}</text>
    <rect x="{PAD}" y="64" width="{W - 2 * PAD}" height="1" fill="#1b2740"/>

    {"".join(blocks)}
    {"".join(chips)}

    <text x="{PAD}" y="222" font-family="{FONT}" font-size="12" letter-spacing="1.5" fill="#4c5a72">语言分布</text>
    <rect x="128" y="217" width="{W - PAD - 128}" height="1" fill="#1b2740"/>
    <g clip-path="url(#bar)">{"".join(segs)}</g>
    {"".join(legend)}

    <text x="{PAD}" y="312" font-family="{FONT}" font-size="12" letter-spacing="1.5" fill="#4c5a72">热门仓库</text>
    <rect x="128" y="307" width="{W - PAD - 128}" height="1" fill="#1b2740"/>
    {"".join(rows)}

    <rect x="{PAD}" y="464" width="{W - 2 * PAD}" height="1" fill="#1b2740"/>
    <text x="{PAD}" y="484" font-family="{FONT}" font-size="11.5" fill="#41506a">数据来自 GitHub API</text>
    <text x="{W - PAD}" y="484" text-anchor="end" font-family="{FONT}" font-size="11.5" fill="#41506a">每月 1 / 15 日自动刷新</text>
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
    print(f"stats: wrote {a.out} ({len(svg)} bytes) repos={data['repos']} stars={data['stars']} "
          f"commits={data['commits']} followers={data['followers']} prs={data['prs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
