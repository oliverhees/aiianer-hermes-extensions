"""AIIANER Marktplatz agent-plugin entry point.

The Git-installable repository root is a hybrid plugin: Hermes discovers the
Dashboard and Desktop halves from this same directory. The gateway guard is
installed into Hermes' user hook directory on plugin load so the Git install
has the same update-repair behavior as the legacy installer.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _hermes_home() -> Path:
    configured = os.environ.get("HERMES_HOME", "").strip()
    if configured:
        return Path(configured)
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "").strip()
        return Path(local) / "hermes" if local else Path.home() / "AppData" / "Local" / "hermes"
    return Path.home() / ".hermes"


def _install_guard_files() -> None:
    """Keep the gateway guard available after a direct Git installation."""
    source_dir = Path(__file__).resolve().parent
    hermes_home = _hermes_home()
    state_dir = hermes_home / "aiianer"
    hook_dir = hermes_home / "hooks" / "aiianer-guard"

    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        hook_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_dir / "guard_check.py", state_dir / "guard_check.py")
        shutil.copy2(source_dir / "guard" / "HOOK.yaml", hook_dir / "HOOK.yaml")
        shutil.copy2(source_dir / "guard" / "handler.py", hook_dir / "handler.py")
    except OSError:
        # A broken optional guard must never prevent Hermes from loading the
        # marketplace itself. The health route still reports the issue.
        return


def register(ctx):
    """Load the plugin and provision its update guard."""
    del ctx
    _install_guard_files()
