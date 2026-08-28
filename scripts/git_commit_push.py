"""Stage, commit, and push portfolio updates using dulwich (no git CLI required)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dulwich import porcelain
from dulwich.repo import Repo

REPO = Path(__file__).resolve().parents[1]
FILES = [
    "index.html",
    "assets/nfl-demo.gif",
    "assets/wmgoldmine-demo.gif",
    "assets/wmmods-demo.gif",
    "assets/wmnavigation-demo.gif",
    "assets/wmnav-1.png",
    "assets/wmnav-2.png",
    "assets/wmnav-3.png",
    "assets/wmnav-4.png",
    "assets/wmnav-5.png",
    "assets/profile.jpg",
    "scripts/capture_demos.py",
    "scripts/git_commit_push.py",
]

MESSAGE = """Refresh WMNavigation demo with real in-app UI screenshots.

Rebuild wmnavigation-demo.gif from five live WMNavigation captures, add a screenshot gallery to the featured project block, and update capture_demos.py to reuse the assets."""


def main() -> None:
    token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    os.environ["GIT_AUTHOR_NAME"] = "Michael Schartner"
    os.environ["GIT_AUTHOR_EMAIL"] = "mike.j.schartner@gmail.com"
    os.environ["GIT_COMMITTER_NAME"] = os.environ["GIT_AUTHOR_NAME"]
    os.environ["GIT_COMMITTER_EMAIL"] = os.environ["GIT_AUTHOR_EMAIL"]

    repo = Repo(str(REPO))
    for rel in FILES:
        path = REPO / rel
        if path.exists():
            porcelain.add(repo, rel.encode())

    commit_id = porcelain.commit(
        repo,
        message=MESSAGE.encode(),
        author=os.environ["GIT_AUTHOR_NAME"].encode() + b" <" + os.environ["GIT_AUTHOR_EMAIL"].encode() + b">",
        committer=os.environ["GIT_COMMITTER_NAME"].encode() + b" <" + os.environ["GIT_COMMITTER_EMAIL"].encode() + b">",
    )
    print(f"Committed {commit_id.decode()[:12]}")

    remote_url = f"https://x-access-token:{token}@github.com/mikejschartner/Mike-Schartner-Portfolio.git"
    porcelain.push(repo, remote_url, refspecs=[b"refs/heads/main"])
    print("Pushed to origin/main")


if __name__ == "__main__":
    main()
