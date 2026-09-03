"""AIIANER Marktplatz - Backend.

Liest den Katalog, vergleicht ihn mit dem lokal Installierten und installiert
oder aktualisiert Komponenten. Alles landet unter ~/.hermes/, nie im
Hermes-Checkout, mit einer Ausnahme: die Sprachdatei, weil Hermes keine
Laufzeit-Registrierung fuer Sprachen anbietet. Die uebernimmt der Waechter.

Routen liegen unter /api/plugins/aiianer-hub/ und damit hinter dem Auth-Gate
des Dashboards.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

REPO = "oliverhees/aiianer-hermes-extensions"
TARBALL = f"https://github.com/{REPO}/archive/refs/heads/main.tar.gz"
CATALOG_URL = (
    f"https://raw.githubusercontent.com/{REPO}/main/"
    "extensions/aiianer-hub/catalog.json"
)

def hermes_home() -> Path:
    """Wo Hermes seine Daten haelt, plattformuebergreifend.

    Reihenfolge wie in Hermes' eigenem scripts/install.ps1:
      1. HERMES_HOME, wenn gesetzt (gilt ueberall, auch fuer Profile)
      2. natives Windows: %LOCALAPPDATA%\\hermes
      3. sonst (Linux, macOS, WSL): ~/.hermes
    """
    env = os.environ.get("HERMES_HOME", "").strip()
    if env:
        return Path(env)
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "").strip()
        if local:
            return Path(local) / "hermes"
        return Path.home() / "AppData" / "Local" / "hermes"
    return Path.home() / ".hermes"


HERMES_HOME = hermes_home()
PLUGINS = HERMES_HOME / "plugins"
STATE_DIR = HERMES_HOME / "aiianer"
STATE_FILE = STATE_DIR / "installed.json"
LOCAL_CATALOG = Path(__file__).resolve().parent.parent / "catalog.json"


# ---------------------------------------------------------------- Zustand

def _read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def _write_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _load_catalog() -> dict:
    """Katalog aus dem Netz, mit der mitgelieferten Fassung als Rueckfall."""
    try:
        with urllib.request.urlopen(CATALOG_URL, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return json.loads(LOCAL_CATALOG.read_text())


# ---------------------------------------------------------------- Routen

@router.get("/catalog")
async def catalog() -> dict:
    """Katalog plus lokaler Zustand pro Komponente."""
    cat = _load_catalog()
    state = _read_state()
    items = []
    for c in cat.get("components", []):
        local = state.get(c["id"], {})
        installed = local.get("version")
        items.append(
            {
                **c,
                "installed": installed,
                "installedAt": local.get("at"),
                "status": (
                    "missing"
                    if not installed
                    else "outdated"
                    if installed != c["version"]
                    else "current"
                ),
            }
        )
    return {"catalogVersion": cat.get("catalogVersion"), "components": items}


def _guard():
    """guard_check liegt unter ~/.hermes/aiianer/, dieselbe Datei, die auch
    der Waechter-Hook benutzt. Ein Ort, eine Wahrheit."""
    if str(STATE_DIR) not in sys.path:
        sys.path.insert(0, str(STATE_DIR))
    import guard_check  # type: ignore

    return guard_check


@router.get("/health")
async def health() -> dict:
    """Sitzt alles noch? Der Waechter nutzt dieselbe Pruefung."""
    return _guard().check_all()


@router.post("/install")
async def install(body: dict) -> dict:
    comp_id = (body or {}).get("id", "")
    cat = _load_catalog()
    entry = next((c for c in cat.get("components", []) if c["id"] == comp_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unbekannte Komponente: {comp_id}")

    with tempfile.TemporaryDirectory() as tmp:
        root = _download(tmp)
        src = root / "extensions" / comp_id
        if not src.is_dir():
            raise HTTPException(
                status_code=500, detail=f"{comp_id} fehlt im heruntergeladenen Repo"
            )
        installer = src / "install.sh"
        if not installer.is_file():
            raise HTTPException(status_code=500, detail=f"{comp_id} hat kein install.sh")
        os.chmod(installer, 0o755)
        proc = subprocess.run(
            ["bash", str(installer)],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(src),
        )
        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=(proc.stderr or proc.stdout or "Installation fehlgeschlagen")[-800:],
            )

        # Sprachdatei zusaetzlich als Quelle sichern, damit der Waechter sie
        # nach einem Hermes-Update erneut einspielen kann.
        if comp_id == "german-language":
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            for name in ("de.ts", "apply-de.py"):
                if (src / name).is_file():
                    shutil.copy2(src / name, STATE_DIR / name)

    state = _read_state()
    state[comp_id] = {"version": entry["version"], "at": _now()}
    _write_state(state)
    return {"ok": True, "id": comp_id, "version": entry["version"]}


@router.post("/repair")
async def repair() -> dict:
    """Erzwingt, was der Waechter beim Start automatisch tut."""
    return _guard().repair_all()


# ---------------------------------------------------------------- Helfer

def _download(tmp: str) -> Path:
    archive = Path(tmp) / "repo.tar.gz"
    urllib.request.urlretrieve(TARBALL, archive)
    with tarfile.open(archive) as tf:
        tf.extractall(tmp)
    roots = [p for p in Path(tmp).iterdir() if p.is_dir() and p.name != "__MACOSX"]
    if not roots:
        raise HTTPException(status_code=500, detail="Archiv war leer")
    return roots[0]


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")
