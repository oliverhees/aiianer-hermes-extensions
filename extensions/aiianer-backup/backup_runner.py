#!/usr/bin/env python3
"""Local-only AIIANER backup runner. No shell interpolation, no uploads."""
from __future__ import annotations
import argparse, datetime as dt, json, os, shutil, subprocess, sys, tempfile, time, zipfile
from pathlib import Path

MAX_RETENTION = 100
PREFIX = "aiianer-backup-"

def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home()/".hermes"))).expanduser()

def state_path(home: Path) -> Path: return home / "aiianer" / "backup-state.json"

def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, sort_keys=True); f.write("\n"); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        try: os.unlink(name)
        except FileNotFoundError: pass

def load_state(home: Path) -> dict:
    try:
        value = json.loads(state_path(home).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError): return {}

def validate_target(raw: str, home: Path, create: bool = True) -> Path:
    if not isinstance(raw, str) or not raw.strip(): raise ValueError("TARGET_REQUIRED")
    p = Path(raw).expanduser()
    if not p.is_absolute(): raise ValueError("TARGET_ABSOLUTE_REQUIRED")
    if any(part == ".." for part in p.parts): raise ValueError("TARGET_TRAVERSAL")
    if create: p.mkdir(parents=True, exist_ok=True)
    target = p.resolve(strict=True)
    h = home.expanduser().resolve(strict=False)
    try: target.relative_to(h)
    except ValueError: pass
    else: raise ValueError("TARGET_INSIDE_HERMES_HOME")
    if not target.is_dir(): raise ValueError("TARGET_NOT_DIRECTORY")
    if not os.access(target, os.W_OK): raise ValueError("TARGET_NOT_WRITABLE")
    # V1 deliberately rejects obvious network/UNC paths.
    if os.name == "nt" and (str(target).startswith("\\\\") or target.drive.startswith("//")):
        raise ValueError("TARGET_NETWORK_OR_UNSUPPORTED")
    return target

def acquire_lock(path: Path):
    try: path.mkdir()
    except FileExistsError: raise RuntimeError("BACKUP_IN_PROGRESS")
    return path

def release_lock(path: Path):
    try: path.rmdir()
    except OSError: pass

def verify_archive(path: Path) -> tuple[int, int]:
    if not path.is_file() or path.stat().st_size < 22: raise ValueError("ARCHIVE_MISSING_OR_INVALID")
    try:
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            if not names or not any(Path(n).name in {"config.yaml", ".env", "state.db"} for n in names):
                raise ValueError("ARCHIVE_MISSING_OR_INVALID")
            bad = z.testzip()
            if bad: raise ValueError("ARCHIVE_MISSING_OR_INVALID")
            return len(names), path.stat().st_size
    except (OSError, zipfile.BadZipFile): raise ValueError("ARCHIVE_MISSING_OR_INVALID")

def apply_retention(target: Path, keep: int) -> list[str]:
    removed=[]
    candidates=sorted((p for p in target.iterdir() if p.is_file() and p.name.startswith(PREFIX) and p.name.endswith(".zip")), key=lambda p:p.stat().st_mtime, reverse=True)
    for p in candidates[max(1, keep):]:
        try: p.unlink(); removed.append(p.name)
        except OSError: pass
    return removed

def run(home: Path, config: dict) -> dict:
    target=validate_target(config.get("target_dir", ""), home)
    lock=home/".aiianer-backup.lock"; acquire_lock(lock)
    partial=None
    try:
        stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        final=target/f"{PREFIX}{stamp}.zip"
        # ``hermes backup`` appends .zip when its output lacks that suffix. Keep the
        # hidden staging path zip-suffixed so the CLI writes exactly where we verify it.
        partial=target/(f".{final.stem}.{os.getpid()}.partial.zip")
        cmd=[shutil.which("hermes") or "hermes", "backup", "--output", str(partial), "--keep", "0"]
        try:
            proc=subprocess.run(cmd, cwd=str(home), capture_output=True, text=True, timeout=3600, shell=False)
        except FileNotFoundError as exc: raise RuntimeError("HERMES_COMMAND_NOT_FOUND") from exc
        if proc.returncode != 0: raise RuntimeError("HERMES_COMMAND_FAILED")
        count,size=verify_archive(partial)
        os.replace(partial, final)
        removed=apply_retention(target, int(config.get("retention",{}).get("keep",5))) if config.get("retention",{}).get("enabled") else []
        result={"state":"success", "lastRun":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "lastArchive":{"name":final.name,"bytes":size,"fileCount":count}, "lastErrorCode":None, "retentionDeleted":removed}
        atomic_json(state_path(home), {**load_state(home), **result})
        return result
    finally:
        if partial:
            try: partial.unlink()
            except OSError: pass
        release_lock(lock)

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--home", default=None); args=ap.parse_args()
    home=Path(args.home).expanduser() if args.home else hermes_home(); state=load_state(home)
    try: result=run(home,state); print(json.dumps(result)); return 0
    except (ValueError,RuntimeError) as exc:
        code=str(exc); atomic_json(state_path(home), {**state,"state":"failed","lastErrorCode":code}); print(json.dumps({"state":"failed","lastErrorCode":code})); return 2
if __name__ == "__main__": raise SystemExit(main())
