from __future__ import annotations

import sys
from pathlib import Path


def resource_root() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    packaged = base / "fnf_assets"
    if packaged.is_dir():
        return packaged
    local = Path(__file__).resolve().parent / "fnf_assets"
    if local.is_dir():
        return local
    raise FileNotFoundError("Le dossier fnf_assets est introuvable. Réexécute extract-assets.ps1.")


def write_crash_log() -> Path:
    """Erreur fatale -> %APPDATA%/FNF Python/crash.log (à envoyer pour corriger le bug)."""
    import os
    import traceback
    from datetime import datetime
    folder = Path(os.environ.get("APPDATA") or Path.home()) / "FNF Python"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "crash.log"
    with path.open("a", encoding="utf-8") as log:
        log.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} =====\n{traceback.format_exc()}")
    return path


if __name__ == "__main__":
    from pyfnf.game import FunkinApp

    try:
        FunkinApp(resource_root()).run()
    except Exception:
        print("Crash enregistré dans", write_crash_log())
        raise
