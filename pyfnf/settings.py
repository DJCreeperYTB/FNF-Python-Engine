from __future__ import annotations

import json
import shutil
import os
from dataclasses import dataclass, field
from pathlib import Path

import pygame


DEFAULT_BINDS = [pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k]
DEFAULT_PAD_BINDS = [pygame.CONTROLLER_BUTTON_X, pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_Y, pygame.CONTROLLER_BUTTON_B]
FPS_CHOICES = (30, 60, 75, 120, 144, 165, 240, 0)  # 0 = illimité
SCROLL_MIN, SCROLL_MAX = 1.0, 5.0  # vitesse fixe ; en dessous de 1.0 = AUTO


def step_scroll(value: float, step: float) -> float:
    """AUTO (0) <-> 1.0 ... 5.0 : la vitesse choisie remplace celle du chart, elle ne la multiplie pas."""
    if value <= 0:
        return SCROLL_MIN if step > 0 else 0.0
    value = round(value + step, 1)
    return 0.0 if value < SCROLL_MIN else min(SCROLL_MAX, value)


def default_settings_path() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home())
    return base / "FNF Python" / "settings.json"


@dataclass
class Settings:
    volume: float = .75
    offset_ms: int = 0
    keybinds: list[int] = field(default_factory=lambda: DEFAULT_BINDS.copy())
    pad_binds: list[int] = field(default_factory=lambda: DEFAULT_PAD_BINDS.copy())  # boutons de manette des 4 flèches
    language: str = "en"
    scroll_speed: float = 0.0  # 0 = AUTO (vitesse du chart) ; sinon vitesse fixe, la même pour tous les charts
    fps_limit: int = 60  # 0 = illimité
    hitsound_volume: float = .8
    judgment: str = "normal"  # "easy" : les GOOD comptent pour 100 %
    subtitles: bool = True
    camera_zooms: bool = True  # la caméra et l'interface battent la mesure (bop), comme le jeu officiel
    quality: str = "high"  # "high" : image lissée ; "pixel" : pixels nets
    fullscreen: bool = False  # F11 ou Options > PLEIN ÉCRAN
    child_mode: bool = False  # versions censurées des dialogues et cinématiques (comme le jeu de base)
    news_seen: list[str] = field(default_factory=list)  # annonces déjà lues (point rouge du parchemin)
    trophies_seen: int = 0  # succès déjà vus dans l'écran des trophées (point rouge du trophée)
    downscroll: bool = False
    ghost_tapping: bool = True
    hitsounds: bool = False
    flashing_lights: bool = True
    show_fps: bool = False
    disabled_mods: list[str] = field(default_factory=list)
    scores: dict[str, int] = field(default_factory=dict)
    achievements: list[str] = field(default_factory=list)
    accuracies: dict[str, float] = field(default_factory=dict)
    stats: dict[str, int] = field(default_factory=dict)
    path: Path = field(default_factory=default_settings_path, repr=False)

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        target = path or default_settings_path()
        settings = cls(path=target)
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return settings
        except (OSError, ValueError):
            # Fichier abîmé : on le met de côté au lieu de l'écraser à la prochaine sauvegarde (scores, trophées...).
            try:
                shutil.copy2(target, target.with_name("settings.broken.json"))
            except OSError:
                pass
            return settings
        if not isinstance(data, dict):
            return settings
        try:  # la progression d'abord : un réglage illisible ne doit jamais faire perdre les scores
            settings.scores = {str(key): int(value) for key, value in data.get("scores", {}).items()}
            settings.achievements = [str(name) for name in data.get("achievements", [])]
            settings.accuracies = {str(key): float(value) for key, value in data.get("accuracies", {}).items()}
            settings.stats = {str(key): int(value) for key, value in data.get("stats", {}).items()}
            settings.news_seen = [str(name) for name in data.get("news_seen", [])]
            settings.trophies_seen = int(data.get("trophies_seen", 0))
        except (ValueError, TypeError, AttributeError):
            pass
        try:
            settings.volume = min(1.0, max(0.0, float(data.get("volume", settings.volume))))
            settings.offset_ms = min(500, max(-500, int(data.get("offset_ms", 0))))
            settings.language = "fr" if data.get("language") == "fr" else "en"
            # Vitesse fixe (clé "scroll_fixed") ; les anciennes clés (multiplicateur) sont ignorées : AUTO par défaut.
            fixed = float(data.get("scroll_fixed", 0) or 0)
            settings.scroll_speed = 0.0 if fixed <= 0 else round(min(SCROLL_MAX, max(SCROLL_MIN, fixed)), 1)
            settings.fps_limit = int(data.get("fps_limit", 60)) if int(data.get("fps_limit", 60)) in FPS_CHOICES else 60
            settings.hitsound_volume = min(1.0, max(0.0, float(data.get("hitsound_volume", .8))))
            settings.judgment = "easy" if data.get("judgment") == "easy" else "normal"
            settings.quality = "pixel" if data.get("quality") == "pixel" else "high"
            for name in ("downscroll", "ghost_tapping", "hitsounds", "flashing_lights", "show_fps", "subtitles", "child_mode", "fullscreen", "camera_zooms"):
                if isinstance(data.get(name), bool):
                    setattr(settings, name, data[name])
            settings.disabled_mods = [str(name) for name in data.get("disabled_mods", [])]
            names = data.get("keybinds", [])
            if isinstance(names, list) and len(names) == 4:
                converted = [pygame.key.key_code(str(name)) for name in names]
                if len(set(converted)) == 4:
                    settings.keybinds = converted
            buttons = data.get("pad_binds", [])
            if isinstance(buttons, list) and len(buttons) == 4 and len(set(buttons)) == 4                     and all(isinstance(button, int) and 0 <= button < pygame.CONTROLLER_BUTTON_MAX for button in buttons):
                settings.pad_binds = buttons
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return settings

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "save_version": 2,  # les versions suivantes lisent ce format (scores, vitesse de défilement...) sans rien perdre
            "volume": round(self.volume, 2),
            "offset_ms": int(self.offset_ms),
            "keybinds": [pygame.key.name(key) for key in self.keybinds],
            "pad_binds": self.pad_binds,
            "language": self.language,
            "scroll_fixed": round(self.scroll_speed, 1),
            "fps_limit": self.fps_limit,
            "hitsound_volume": round(self.hitsound_volume, 2),
            "judgment": self.judgment,
            "quality": self.quality,
            "downscroll": self.downscroll,
            "ghost_tapping": self.ghost_tapping,
            "hitsounds": self.hitsounds,
            "flashing_lights": self.flashing_lights,
            "show_fps": self.show_fps,
            "subtitles": self.subtitles,
            "camera_zooms": self.camera_zooms,
            "child_mode": self.child_mode,
            "fullscreen": self.fullscreen,
            "disabled_mods": self.disabled_mods,
            "scores": self.scores,
            "achievements": self.achievements,
            "accuracies": self.accuracies,
            "stats": self.stats,
            "news_seen": self.news_seen,
            "trophies_seen": self.trophies_seen,
        }
        # Écriture atomique : un plantage ou une coupure pendant l'écriture ne laisse jamais un fichier à moitié écrit.
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self.path)

    @staticmethod
    def _swap(binds: list[int], lane: int, value: int) -> None:
        """Une touche déjà prise sur une autre flèche échange sa place avec l'ancienne."""
        if value in binds:
            binds[binds.index(value)] = binds[lane]
        binds[lane] = value

    def bind(self, lane: int, key: int) -> None:
        self._swap(self.keybinds, lane, key)
        self.save()

    def bind_pad(self, lane: int, button: int) -> None:
        self._swap(self.pad_binds, lane, button)
        self.save()

    def save_accuracy(self, key: str, accuracy: float) -> None:
        if accuracy > self.accuracies.get(key, -1):
            self.accuracies[key] = round(accuracy, 2)
            self.save()

    def save_score(self, key: str, score: int) -> bool:
        if score <= self.scores.get(key, 0):
            return False
        self.scores[key] = score
        self.save()
        return True

    def reset_binds(self) -> None:
        self.keybinds = DEFAULT_BINDS.copy()
        self.pad_binds = DEFAULT_PAD_BINDS.copy()
        self.save()
