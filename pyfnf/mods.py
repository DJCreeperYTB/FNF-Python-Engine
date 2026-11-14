"""Mods de Python Engine : dossiers ou .zip dans mods/, superposés aux assets du jeu de base."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import time
import traceback
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Mod:
    folder: str          # nom du dossier ou du .zip dans mods/
    root: Path           # dossier qui contient mod.json (extrait pour un .zip)
    name: str
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    icon: Path | None = None
    enabled: bool = True
    error: str = ""
    priority: int = 0


def mods_dir() -> Path:
    """mods/ à côté de l'exe (build PyInstaller) ou à côté de main.py."""
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    return base / "mods"


def cache_dir() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "FNF Python" / "mod_cache"


def _extract(zip_path: Path, cache: Path) -> Path:
    """Extrait le .zip une fois (ré-extrait s'il a changé) et renvoie le dossier contenant mod.json."""
    target = cache / zip_path.stem
    stat = zip_path.stat()
    stamp = f"{stat.st_size}:{stat.st_mtime_ns}"
    stamp_file = target / ".stamp"
    if not (stamp_file.is_file() and stamp_file.read_text() == stamp):
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(target)  # extractall neutralise les chemins absolus et les "..".
        stamp_file.write_text(stamp)
    if (target / "mod.json").is_file():
        return target
    # Zip créé en compressant le dossier lui-même : mod.json est un niveau plus bas.
    return next((child for child in target.iterdir() if (child / "mod.json").is_file()), target)


def discover(disabled: list[str]) -> list[Mod]:
    directory = mods_dir()
    directory.mkdir(parents=True, exist_ok=True)
    mods: list[Mod] = []
    for entry in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
        if entry.name.startswith((".", "_")) or not (entry.is_dir() or entry.suffix.lower() == ".zip"):
            continue
        if entry.name == EDITOR_SAVES:  # shortcut: ancien dossier resté là si Editor Saves/ existait déjà ; à fusionner à la main
            continue
        mod = Mod(folder=entry.name, root=entry, name=entry.stem, enabled=entry.name not in disabled)
        try:
            if entry.is_file():
                mod.root = _extract(entry, cache_dir())
            meta_path = mod.root / "mod.json"
            if not meta_path.is_file():
                mod.error = "mod.json manquant"
                mod.enabled = False
            else:
                meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
                mod.name = str(meta.get("name", mod.name))
                mod.description = str(meta.get("description", ""))
                mod.author = str(meta.get("author", ""))
                mod.version = str(meta.get("version", mod.version))
                mod.priority = int(meta.get("priority", 0) or 0)
                icon = mod.root / str(meta.get("icon", "icon.png"))
                mod.icon = icon if icon.is_file() else None
        except (OSError, ValueError, zipfile.BadZipFile) as error:
            mod.error = f"{type(error).__name__}: {error}"
            mod.enabled = False
        mods.append(mod)
    # Priorité haute d'abord (ses fichiers gagnent), puis ordre alphabétique.
    return sorted(mods, key=lambda item: -item.priority)


TEMPLATE_SCRIPT = '''"""Script de mod : chaque fonction est optionnelle. `game` = la partie en cours."""


def on_create(game):
    pass


def on_beat(game, beat):
    pass


def on_note_hit(game, note, rating):
    pass
'''


EDITOR_SAVES = "Editor Saves"


def editor_saves_dir() -> Path:
    """Ce que les éditeurs enregistrent depuis le jeu de base ou un .zip : « Editor Saves/ » à côté de mods/.
    Ce n'est pas un mod : le jeu le charge toujours, avant tous les mods, et l'écran MODS ne le montre pas."""
    target = mods_dir().parent / EDITOR_SAVES
    old = mods_dir() / EDITOR_SAVES  # versions d'avant : c'était un mod dans mods/
    if old.is_dir() and not target.exists():
        shutil.move(str(old), str(target))
        (target / "mod.json").unlink(missing_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    return target


def create_template(name: str = "MyMod") -> Path:
    """Crée un mod vide prêt à remplir dans mods/ et renvoie son dossier."""
    directory = mods_dir()
    target = directory / name
    index = 2
    while target.exists():
        target = directory / f"{name}{index}"
        index += 1
    for sub in ("data/songs", "data/levels", "data/characters", "data/stages", "songs", "images/characters", "scripts"):
        (target / sub).mkdir(parents=True)
    (target / "mod.json").write_text(json.dumps({
        "name": target.name, "description": "Describe your mod here.", "author": "", "version": "1.0.0",
    }, indent=2), encoding="utf-8")
    (target / "scripts" / "script.py").write_text(TEMPLATE_SCRIPT, encoding="utf-8")
    return target


class ScriptHost:
    """Charge les scripts .py des mods et appelle leurs fonctions on_xxx sans jamais faire planter le jeu."""

    def __init__(self, paths: list[Path], log_path: Path | None = None):
        self.modules = []
        self.errors: list[tuple[float, str]] = []
        self.log_path = log_path
        for index, path in enumerate(paths):
            try:
                spec = importlib.util.spec_from_file_location(f"fnf_mod_script_{index}_{path.stem}", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.modules.append(module)
            except Exception:
                self._report(path.name, "load")

    def call(self, hook: str, *args) -> list:
        results = []
        for module in self.modules:
            function = getattr(module, hook, None)
            if not callable(function):
                continue
            try:
                results.append(function(*args))
            except Exception:
                # Un hook qui plante est désactivé pour ce module : pas de spam à 60 fps.
                setattr(module, hook, None)
                self._report(Path(module.__file__).name, hook)
        return results

    def _report(self, script: str, hook: str) -> None:
        details = traceback.format_exc()
        last_line = details.strip().splitlines()[-1]
        self.errors.append((time.monotonic(), f"{script} / {hook}: {last_line}"))
        print(details, file=sys.stderr)
        if self.log_path:
            try:
                with self.log_path.open("a", encoding="utf-8") as log:
                    log.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {script} / {hook}\n{details}\n")
            except OSError:
                pass
