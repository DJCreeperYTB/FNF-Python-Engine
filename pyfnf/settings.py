from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import pygame


DEFAULT_BINDS = [pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k]


def default_settings_path() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home())
    return base / "FNF Python" / "settings.json"


@dataclass
class Settings:
    volume: float = .75
    offset_ms: int = 0
    keybinds: list[int] = field(default_factory=lambda: DEFAULT_BINDS.copy())
    path: Path = field(default_factory=default_settings_path, repr=False)

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        target = path or default_settings_path()
        settings = cls(path=target)
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            settings.volume = min(1.0, max(0.0, float(data.get("volume", settings.volume))))
            settings.offset_ms = min(500, max(-500, int(data.get("offset_ms", 0))))
            names = data.get("keybinds", [])
            if isinstance(names, list) and len(names) == 4:
                converted = [pygame.key.key_code(str(name)) for name in names]
                if len(set(converted)) == 4:
                    settings.keybinds = converted
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        return settings

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "volume": round(self.volume, 2),
            "offset_ms": int(self.offset_ms),
            "keybinds": [pygame.key.name(key) for key in self.keybinds],
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def bind(self, lane: int, key: int) -> None:
        if key in self.keybinds:
            other_lane = self.keybinds.index(key)
            self.keybinds[other_lane], self.keybinds[lane] = self.keybinds[lane], self.keybinds[other_lane]
        else:
            self.keybinds[lane] = key
        self.save()

    def reset_binds(self) -> None:
        self.keybinds = DEFAULT_BINDS.copy()
        self.save()
