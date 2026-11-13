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


if __name__ == "__main__":
    from pyfnf.game import FunkinApp

    FunkinApp(resource_root()).run()
