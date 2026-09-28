#!/usr/bin/env python3
"""Upload / download MicroPython project files to an ESP32 board.

Syncs a local project directory to the board flash filesystem using mpremote.
Supports dry-run, selective upload, and directory creation.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


@dataclass
class FileAction:
    action: str  # upload / download / mkdir / skip
    local: str
    remote: str
    size: int = 0


def run_mpremote(port: str, *args: str, timeout: int = 30) -> tuple[int, str, str]:
    cmd = [sys.executable, "-m", "mpremote", "connect", port, *args]
    try:
        completed = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout
        )
        return completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "mpremote timed out"


def collect_files(root: Path, include_lib: bool = True) -> list[Path]:
    """Collect .py files to upload, preserving relative paths."""
    files = []
    patterns = ["*.py"]
    if include_lib:
        files.extend(sorted(root.rglob("*.py")))
    else:
        files.extend(sorted(root.glob("*.py")))
    # Skip hidden and cache
    files = [f for f in files if not any(p.startswith(".") or p == "__pycache__" for p in f.parts)]
    return files


def plan_upload(root: Path, port: str, dry_run: bool = False) -> list[FileAction]:
    """Plan file uploads."""
    actions = []
    files = collect_files(root)

    for f in files:
        rel = f.relative_to(root)
        remote_path = str(rel).replace("\\", "/")
        size = f.stat().st_size

        # Check if remote directory needs creating
        remote_dir = str(rel.parent).replace("\\", "/")
        if remote_dir and remote_dir != ".":
            actions.append(FileAction(action="mkdir", local="", remote=remote_dir))

        actions.append(FileAction(action="upload", local=str(f), remote=remote_path, size=size))

    return actions


def execute_actions(port: str, actions: list[FileAction], dry_run: bool = False) -> tuple[int, int]:
    """Execute planned file actions. Returns (success_count, fail_count)."""
    success = 0
    fail = 0

    for act in actions:
        if act.action == "mkdir":
            if dry_run:
                print(f"[DRY] mkdir :{act.remote}")
            else:
                rc, out, err = run_mpremote(port, "fs", "mkdir", act.remote, timeout=10)
                if rc == 0 or "exists" in err.lower() or "EEXIST" in err:
                    print(f"[OK]  mkdir :{act.remote}")
                    success += 1
                else:
                    print(f"[ERR] mkdir :{act.remote} — {err.strip()[:80]}")
                    fail += 1

        elif act.action == "upload":
            if dry_run:
                print(f"[DRY] upload {act.local} -> :{act.remote} ({act.size} bytes)")
                success += 1
            else:
                rc, out, err = run_mpremote(port, "fs", "cp", act.local, f":{act.remote}", timeout=30)
                if rc == 0:
                    print(f"[OK]  upload {act.local} -> :{act.remote} ({act.size} bytes)")
                    success += 1
                else:
                    print(f"[ERR] upload {act.local} — {err.strip()[:80]}")
                    fail += 1

    return success, fail


def list_remote_files(port: str):
    """List all files on the board recursively."""
    rc, out, err = run_mpremote(port, "fs", "ls", timeout=15)
    if rc == 0:
        print(out)
    else:
        print(f"Error listing files: {err}", file=sys.stderr)


def reset_board(port: str, soft: bool = True):
    """Reset the board."""
    if soft:
        code = "import machine; machine.soft_reset()"
    else:
        code = "import machine; machine.reset()"
    rc, out, err = run_mpremote(port, "exec", code, timeout=10)
    if rc == 0:
        print("Board reset.")
    else:
        print(f"Reset failed: {err}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Manage MicroPython files on ESP32 board")
    sub = parser.add_subparsers(dest="command", required=True)

    # upload
    up = sub.add_parser("upload", help="Upload project files to board")
    up.add_argument("project_dir", help="Local project directory")
    up.add_argument("--port", "-p", required=True, help="Serial port (e.g. COM3)")
    up.add_argument("--dry-run", action="store_true", help="Show actions without executing")
    up.add_argument("--reset", action="store_true", help="Soft-reset after upload")

    # list
    ls = sub.add_parser("list", help="List files on board")
    ls.add_argument("--port", "-p", required=True, help="Serial port")

    # reset
    rs = sub.add_parser("reset", help="Reset the board")
    rs.add_argument("--port", "-p", required=True, help="Serial port")
    rs.add_argument("--hard", action="store_true", help="Hard reset instead of soft")

    # download
    dl = sub.add_parser("download", help="Download a file from board")
    dl.add_argument("--port", "-p", required=True, help="Serial port")
    dl.add_argument("remote", help="Remote file path (e.g. main.py)")
    dl.add_argument("local", nargs="?", help="Local destination path")

    args = parser.parse_args()

    if args.command == "upload":
        root = Path(args.project_dir).resolve()
        if not root.exists():
            print(f"Error: directory not found: {root}", file=sys.stderr)
            sys.exit(1)

        actions = plan_upload(root, args.port, args.dry_run)
        print(f"Planned {len(actions)} action(s) for {root}")
        print("-" * 60)
        success, fail = execute_actions(args.port, actions, args.dry_run)
        print("-" * 60)
        print(f"Done: {success} ok, {fail} failed")

        if args.reset and not args.dry_run:
            reset_board(args.port, soft=True)

    elif args.command == "list":
        list_remote_files(args.port)

    elif args.command == "reset":
        reset_board(args.port, soft=not args.hard)

    elif args.command == "download":
        dest = args.local or args.remote
        rc, out, err = run_mpremote(args.port, "fs", "cp", f":{args.remote}", dest, timeout=30)
        if rc == 0:
            print(f"Downloaded :{args.remote} -> {dest}")
        else:
            print(f"Download failed: {err}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
