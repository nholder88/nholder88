#!/usr/bin/env python3
"""Refresh the 'Currently building' section of the profile README.

Pulls the user's public, non-fork, non-archived repos from `gh repo list`,
ranks them by most recent push, takes the top N, and rewrites the section
of README.md between the CURRENTLY_BUILDING markers.

Env vars:
  PROFILE_USER  GitHub login (defaults to the GH_REPOSITORY owner in Actions)
  GH_TOKEN      auth for `gh` (provided automatically in Actions)

Run locally:
  PROFILE_USER=nholder88 python .github/scripts/refresh_profile.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

TOP_N = 6
README_PATH = Path("README.md")
START_MARKER = "<!-- CURRENTLY_BUILDING:START -->"
END_MARKER = "<!-- CURRENTLY_BUILDING:END -->"


def fetch_repos(user: str) -> list[dict]:
    """List public, non-fork, non-archived repos for `user`."""
    proc = subprocess.run(
        [
            "gh", "repo", "list", user,
            "--limit", "1000",
            "--no-archived",
            "--source",            # excludes forks
            "--visibility", "public",
            "--json", "name,description,url,pushedAt,isFork,isArchived",
        ],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


def render_section(repos: list[dict]) -> str:
    """Render the bullet list. Repos without descriptions render as bare links."""
    lines = []
    for r in repos:
        name = r["name"]
        url = r["url"]
        desc = (r.get("description") or "").strip()
        if desc:
            lines.append(f"- **[{name}]({url})** \u2014 {desc}")
        else:
            lines.append(f"- **[{name}]({url})**")
    return "\n".join(lines)


def rewrite_readme(content: str, new_section: str) -> str:
    """Replace content between markers. Errors loudly if markers are missing."""
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    if not pattern.search(content):
        raise SystemExit(
            f"ERROR: markers not found in {README_PATH}.\n"
            f"  Expected: {START_MARKER} ... {END_MARKER}\n"
            f"  Add them around your 'Currently building' list and re-run."
        )
    replacement = f"{START_MARKER}\n{new_section}\n{END_MARKER}"
    return pattern.sub(replacement, content)


def main() -> int:
    user = os.environ.get("PROFILE_USER")
    if not user:
        # Fall back to GITHUB_REPOSITORY owner when running in Actions.
        repo_full = os.environ.get("GITHUB_REPOSITORY", "")
        user = repo_full.split("/", 1)[0] if "/" in repo_full else ""
    if not user:
        raise SystemExit("ERROR: PROFILE_USER (or GITHUB_REPOSITORY) not set.")

    repos = fetch_repos(user)
    # Defensive re-filter (the gh flags should already exclude these).
    repos = [r for r in repos if not r.get("isFork") and not r.get("isArchived")]
    repos.sort(key=lambda r: r.get("pushedAt") or "", reverse=True)
    top = repos[:TOP_N]

    if not top:
        print("No qualifying repos found. Leaving README unchanged.")
        return 0

    new_section = render_section(top)
    content = README_PATH.read_text(encoding="utf-8")
    new_content = rewrite_readme(content, new_section)

    if new_content == content:
        print("No changes. 'Currently building' is already up to date.")
        return 0

    README_PATH.write_text(new_content, encoding="utf-8")
    print(f"Updated 'Currently building' with {len(top)} repos:")
    for r in top:
        print(f"  - {r['name']} (pushed {r.get('pushedAt')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
