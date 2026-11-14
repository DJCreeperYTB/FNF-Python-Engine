"""Succès façon Psych Engine. Ceux du moteur sont ici ; les mods ajoutent les leurs dans data/achievements/<id>.json."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Achievement:
    id: str
    name: str
    description: str
    icon: str = ""          # id d'icône de vie (images/icons/icon-<id>.png) ou chemin d'image dans le mod
    hidden: bool = False
    mod: str = ""
    name_fr: str = ""
    description_fr: str = ""


BUILTIN = [
    Achievement("first-song", "First Beat", "Finish a song.", "bf", name_fr="Premier son", description_fr="Termine une chanson."),
    Achievement("full-combo", "Full Combo", "Finish a song without a single miss.", "gf", name_fr="Full Combo", description_fr="Termine une chanson sans aucun raté."),
    Achievement("sick-only", "Sick Only", "Finish a song with nothing but SICK!! ratings.", "pico", name_fr="Que des SICK", description_fr="Termine une chanson avec uniquement des SICK!!."),
    Achievement("combo-200", "Combo Monster", "Reach a 200 combo.", "monster", name_fr="Monstre du combo", description_fr="Atteins un combo de 200."),
    Achievement("hard", "Hardcore", "Finish a song in Hard.", "dad", name_fr="Hardcore", description_fr="Termine une chanson en Hard."),
    Achievement("erect", "Remix Master", "Finish an Erect or Nightmare chart.", "mom", name_fr="Maître du remix", description_fr="Termine un chart Erect ou Nightmare."),
    Achievement("pixel", "8-Bit Funk", "Finish a pixel song.", "senpai", name_fr="Funk 8 bits", description_fr="Termine une chanson pixel."),
    Achievement("week", "Story Teller", "Finish a week in Story Mode.", "spooky", name_fr="Conteur", description_fr="Termine une semaine en Mode Histoire."),
    Achievement("week-fc", "Untouchable", "Finish a week in Story Mode without any miss.", "tankman", name_fr="Intouchable", description_fr="Termine une semaine en Mode Histoire sans aucun raté."),
    Achievement("death", "Blue Balled", "Lose a song.", "bf-old", name_fr="Boules bleues", description_fr="Perds une chanson."),
    Achievement("deaths-25", "Never Give Up", "Lose 25 times.", "face", name_fr="Ne lâche rien", description_fr="Perds 25 fois."),
    Achievement("friday-night", "Freaky Friday", "Play a song on a Friday night.", "parents", name_fr="Vendredi soir", description_fr="Joue une chanson un vendredi soir."),
    Achievement("modder", "Modder", "Create a mod from the Mods menu.", "darnell", name_fr="Moddeur", description_fr="Crée un mod depuis le menu Mods."),
    Achievement("charter", "Charter", "Save a chart in the Chart Editor.", "spirit", name_fr="Charteur", description_fr="Enregistre un chart dans l'éditeur."),
    Achievement("in-sync", "In Sync", "Calibrate your audio offset.", "bf-pixel", name_fr="Synchro", description_fr="Calibre ton délai audio."),
]


def load_all(roots: list[Path], mod_names: dict[Path, str]) -> list[Achievement]:
    """Succès du moteur puis ceux des mods actifs (un id déjà pris est ignoré)."""
    result = list(BUILTIN)
    taken = {item.id for item in result}
    for root in roots:
        for path in sorted((root / "data" / "achievements").glob("*.json")):
            if path.stem in taken:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                continue
            result.append(Achievement(
                id=path.stem, name=str(data.get("name", path.stem)), description=str(data.get("description", "")),
                icon=str(data.get("icon", "")), hidden=bool(data.get("hidden", False)), mod=mod_names.get(root, ""),
                name_fr=str(data.get("name_fr", "")), description_fr=str(data.get("description_fr", "")),
            ))
            taken.add(path.stem)
    return result
