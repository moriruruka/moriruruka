#!/usr/bin/env python3
r"""Regenerate assets/stats.svg and commit it with the owner's identity.

Why a local script: scheduled GitHub Actions runs are recorded as github-actions[bot],
and this repository must not carry bot attribution anywhere. Running the refresh from
the owner's machine keeps every commit, run and record under the owner's account.

Usage:
    python tools/update_stats.py              # regenerate, commit if changed
    python tools/update_stats.py --push       # regenerate, commit, push
    python tools/update_stats.py --dry-run    # regenerate only, no git operations

Optional: set GITHUB_TOKEN to avoid the 60 requests/hour unauthenticated API limit.

Windows Task Scheduler (twice a month, 1st and 15th at 08:00):

    schtasks /Create /TN "moriruruka-stats" /SC MONTHLY /D 1,15 /ST 08:00 /TR ^
      "python F:\AriaLuna\DSH\WS2\moriruruka\tools\update_stats.py --push"

    schtasks /Query  /TN "moriruruka-stats"
    schtasks /Delete /TN "moriruruka-stats" /F
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "assets" / "stats.svg"

AUTHOR_NAME = "Aria_Luna"
AUTHOR_EMAIL = "80839392+moriruruka@users.noreply.github.com"
COMMIT_MESSAGE = "chore: refresh stats card"


def git(*args: str, env: dict[str, str] | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def regenerate() -> int:
    print("regenerating assets/stats.svg ...")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_stats.py"), "--user", "moriruruka", "--out", str(CARD)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode


CANDIDATE_IPS = ("20.27.177.113", "140.82.113.3", "140.82.114.3", "4.237.22.34")


def push_with_fallback(env: dict[str, str]) -> tuple[int, str]:
    """推送；直连失败时按候选 IP 重试（仅固定 github.com 的解析结果，保留证书校验）。"""

    code, out = git("push", "origin", "HEAD", env=env)
    if code == 0:
        return code, out
    for ip in CANDIDATE_IPS:
        code, out = git("-c", f"http.curloptResolve=github.com:443:{ip}", "push", "origin", "HEAD", env=env)
        if code == 0:
            return code, out
    return code, out


def commit_and_push(push: bool) -> int:
    code, diff = git("status", "--porcelain", "--", "assets/stats.svg")
    if code != 0:
        print(diff)
        return 1
    if not diff:
        print("stats unchanged, nothing to commit")
        return 0

    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME=AUTHOR_NAME,
        GIT_AUTHOR_EMAIL=AUTHOR_EMAIL,
        GIT_COMMITTER_NAME=AUTHOR_NAME,
        GIT_COMMITTER_EMAIL=AUTHOR_EMAIL,
    )
    code, out = git("add", "--", "assets/stats.svg", env=env)
    if code != 0:
        print(out)
        return 1
    code, out = git("commit", "-m", COMMIT_MESSAGE, env=env)
    print(out)
    if code != 0:
        return 1
    if push:
        code, out = push_with_fallback(env)
        print(out)
        if code != 0:
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="refresh the profile stats card")
    parser.add_argument("--push", action="store_true", help="push after committing")
    parser.add_argument("--dry-run", action="store_true", help="regenerate only, no git")
    args = parser.parse_args(argv)

    if regenerate() != 0:
        return 1
    if args.dry_run:
        return 0
    return commit_and_push(args.push)


if __name__ == "__main__":
    raise SystemExit(main())
