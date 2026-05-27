from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--example", choices=["toy_python", "toy_r"], default=None)
    parser.add_argument("--paper", default=None)
    parser.add_argument("--repo", default=None)
    parser.add_argument("--tutorial", action="append", default=[])
    parser.add_argument("--skill-name", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    command = [sys.executable, "-m", "paper2skill.cli", "build"]
    if args.example:
        command.extend(["--example", args.example])
    if args.paper:
        command.extend(["--paper", args.paper])
    if args.repo:
        command.extend(["--repo", args.repo])
    for tutorial in args.tutorial:
        command.extend(["--tutorial", tutorial])
    if args.skill_name:
        command.extend(["--skill-name", args.skill_name])
    if args.out:
        command.extend(["--out", args.out])
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
