from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

import pygame


class Assets:
    """Résolution et cache des ressources extraites du build FNF."""

    def __init__(self, root: Path):
        self.root = root
        self._images: dict[Path, pygame.Surface] = {}
        self._sounds: dict[Path, pygame.mixer.Sound] = {}

    def find(self, relative: str | Path, extensions: tuple[str, ...] = ("",)) -> Path | None:
        relative = str(relative).replace("\\", "/").removeprefix("assets/")
        candidates: list[Path] = []
        for extension in extensions:
            rel = relative if not extension or relative.lower().endswith(extension) else relative + extension
            candidates.extend((
                self.root / rel,
                self.root / "images" / rel,
                self.root / "shared" / "images" / rel,
            ))
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def resolve_image(self, asset_path: str, library: str | None = None) -> Path | None:
        if ":" in asset_path:
            prefix, asset_path = asset_path.split(":", 1)
            if prefix == "shared":
                candidate = self.root / "shared" / "images" / f"{asset_path}.png"
                return candidate if candidate.is_file() else None
        paths = []
        if library:
            paths.append(self.root / library / "images" / f"{asset_path}.png")
        paths.extend((
            self.root / "images" / f"{asset_path}.png",
            self.root / "shared" / "images" / f"{asset_path}.png",
        ))
        for path in paths:
            if path.is_file():
                return path
        return None

    def image(self, path: Path, alpha: bool = True) -> pygame.Surface:
        if path not in self._images:
            loaded = pygame.image.load(path)
            self._images[path] = loaded.convert_alpha() if alpha else loaded.convert()
        return self._images[path]

    def sound(self, path: Path) -> pygame.mixer.Sound:
        if path not in self._sounds:
            self._sounds[path] = pygame.mixer.Sound(path)
        return self._sounds[path]

    @staticmethod
    def json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8-sig"))


class SparrowAtlas:
    """Lecteur des spritesheets Sparrow/Starling utilisés par FNF."""

    def __init__(self, assets: Assets, png_path: Path):
        self.assets = assets
        self.png_path = png_path
        self.sheet = assets.image(png_path)
        xml_path = png_path.with_suffix(".xml")
        self.frames: list[tuple[str, pygame.Surface]] = []
        if xml_path.is_file():
            root = ET.parse(xml_path).getroot()
            for node in root.findall("SubTexture"):
                name = node.attrib.get("name", "")
                x, y = int(node.attrib["x"]), int(node.attrib["y"])
                width, height = int(node.attrib["width"]), int(node.attrib["height"])
                crop = self.sheet.subsurface((x, y, width, height)).copy()
                frame_width = int(node.attrib.get("frameWidth", width))
                frame_height = int(node.attrib.get("frameHeight", height))
                frame_x = int(node.attrib.get("frameX", 0))
                frame_y = int(node.attrib.get("frameY", 0))
                surface = pygame.Surface((frame_width, frame_height), pygame.SRCALPHA)
                surface.blit(crop, (-frame_x, -frame_y))
                self.frames.append((name, surface))
        else:
            self.frames.append((png_path.stem, self.sheet))

    def animation(self, prefix: str) -> list[pygame.Surface]:
        exact = [(name, frame) for name, frame in self.frames if name.lower().startswith(prefix.lower())]
        if not exact:
            return [self.frames[0][1]]
        return [frame for _, frame in sorted(exact, key=lambda pair: _natural_frame_key(pair[0]))]


def _natural_frame_key(name: str) -> tuple[str, int]:
    digits = ""
    for char in reversed(name):
        if char.isdigit():
            digits = char + digits
        elif digits:
            break
    return name[: -len(digits)] if digits else name, int(digits or 0)


def _matrix_multiply(parent: tuple[float, ...], child: list[float]) -> tuple[float, ...]:
    pa, pb, pc, pd, ptx, pty = parent
    a, b, c, d, tx, ty = child
    return (
        pa * a + pc * b,
        pb * a + pd * b,
        pa * c + pc * d,
        pb * c + pd * d,
        pa * tx + pc * ty + ptx,
        pb * tx + pd * ty + pty,
    )


class AnimateAtlas:
    """Rendu des exports Adobe Animate Texture Atlas de FNF.

    Les symboles et matrices sont composés récursivement. Les frames calculées
    sont mises en cache, ce qui maintient le gameplay fluide après le premier
    passage d'une animation.
    """

    def __init__(self, assets: Assets, directory: Path):
        self.assets = assets
        self.directory = directory
        self.data = assets.json(directory / "Animation.json")
        self.animation = self.data["AN"]
        self.fps = float(self.data.get("MD", {}).get("FRT", 24))
        self.symbols = {symbol["SN"]: symbol for symbol in self.data.get("SD", {}).get("S", [])}
        self.atlas_surfaces: dict[str, pygame.Surface] = {}
        self.sprite_meta: dict[str, dict] = {}
        for json_path in sorted(directory.glob("spritemap*.json")):
            atlas_data = assets.json(json_path)["ATLAS"]
            sheet_name = atlas_data.get("meta", {}).get("image", json_path.with_suffix(".png").name)
            sheet = assets.image(directory / sheet_name)
            for item in atlas_data.get("SPRITES", []):
                sprite = item["SPRITE"]
                rect = pygame.Rect(int(sprite["x"]), int(sprite["y"]), int(sprite["w"]), int(sprite["h"]))
                surface = sheet.subsurface(rect).copy()
                if sprite.get("rotated"):
                    surface = pygame.transform.rotate(surface, 90)
                name = str(sprite["name"])
                self.atlas_surfaces[name] = surface
                self.sprite_meta[name] = sprite
        self.labels = self._read_labels()
        self._cache: dict[tuple[str, int], pygame.Surface] = {}

    def _read_labels(self) -> dict[str, tuple[int, int]]:
        labels: dict[str, tuple[int, int]] = {}
        for layer in self.animation.get("TL", {}).get("L", []):
            for frame in layer.get("FR", []):
                if "N" in frame:
                    labels[str(frame["N"]).lower()] = (int(frame.get("I", 0)), max(1, int(frame.get("DU", 1))))
        return labels

    def find_label(self, prefix: str) -> tuple[str, int, int]:
        wanted = prefix.lower()
        for label, (start, duration) in self.labels.items():
            if label.startswith(wanted):
                return label, start, duration
        if self.labels:
            label = next(iter(self.labels))
            start, duration = self.labels[label]
            return label, start, duration
        return "default", 0, 1

    def frame(self, prefix: str, index: int) -> pygame.Surface:
        label, start, duration = self.find_label(prefix)
        local_index = index % duration
        key = (label, local_index)
        if key not in self._cache:
            commands: list[tuple[pygame.Surface, tuple[float, ...]]] = []
            self._render_timeline(self.animation.get("TL", {}), start + local_index, (1, 0, 0, 1, 0, 0), commands)
            self._cache[key] = self._compose(commands)
        return self._cache[key]

    def _timeline_length(self, timeline: dict) -> int:
        return max((int(frame.get("I", 0)) + int(frame.get("DU", 1))
                    for layer in timeline.get("L", []) for frame in layer.get("FR", [])), default=1)

    def _active_frame(self, frames: list[dict], frame_number: int) -> dict | None:
        for frame in frames:
            start, duration = int(frame.get("I", 0)), int(frame.get("DU", 1))
            if start <= frame_number < start + duration:
                return frame
        return frames[-1] if frames and frame_number >= int(frames[-1].get("I", 0)) else None

    def _render_timeline(self, timeline: dict, frame_number: int, matrix: tuple[float, ...], commands: list) -> None:
        for layer in reversed(timeline.get("L", [])):
            active = self._active_frame(layer.get("FR", []), frame_number)
            if not active:
                continue
            delta = frame_number - int(active.get("I", 0))
            for element in active.get("E", []):
                if "ASI" in element:
                    instance = element["ASI"]
                    surface = self.atlas_surfaces.get(str(instance.get("N")))
                    if surface:
                        commands.append((surface, _matrix_multiply(matrix, instance.get("MX", [1, 0, 0, 1, 0, 0]))))
                elif "SI" in element:
                    instance = element["SI"]
                    symbol = self.symbols.get(instance.get("SN"))
                    if not symbol:
                        continue
                    child_matrix = _matrix_multiply(matrix, instance.get("MX", [1, 0, 0, 1, 0, 0]))
                    child_timeline = symbol.get("TL", {})
                    length = self._timeline_length(child_timeline)
                    child_frame = int(instance.get("FF", 0)) + delta
                    if instance.get("LP", "LP") == "LP":
                        child_frame %= max(1, length)
                    else:
                        child_frame = min(child_frame, max(0, length - 1))
                    self._render_timeline(child_timeline, child_frame, child_matrix, commands)

    def _compose(self, commands: list[tuple[pygame.Surface, tuple[float, ...]]]) -> pygame.Surface:
        rendered: list[tuple[pygame.Surface, tuple[int, int]]] = []
        bounds: list[pygame.Rect] = []
        for surface, matrix in commands:
            a, b, c, d, tx, ty = matrix
            scale_x, scale_y = max(.01, math.hypot(a, b)), max(.01, math.hypot(c, d))
            width = max(1, round(surface.get_width() * scale_x))
            height = max(1, round(surface.get_height() * scale_y))
            transformed = pygame.transform.smoothscale(surface, (width, height))
            if a * d - b * c < 0:
                transformed = pygame.transform.flip(transformed, True, False)
            angle = math.degrees(math.atan2(b, a))
            if abs(angle) > .01:
                transformed = pygame.transform.rotate(transformed, -angle)
            corners = [
                (tx, ty), (a * surface.get_width() + tx, b * surface.get_width() + ty),
                (c * surface.get_height() + tx, d * surface.get_height() + ty),
                (a * surface.get_width() + c * surface.get_height() + tx,
                 b * surface.get_width() + d * surface.get_height() + ty),
            ]
            x = round(min(point[0] for point in corners))
            y = round(min(point[1] for point in corners))
            rect = pygame.Rect(x, y, transformed.get_width(), transformed.get_height())
            rendered.append((transformed, (x, y)))
            bounds.append(rect)
        if not bounds:
            return pygame.Surface((2, 2), pygame.SRCALPHA)
        union = bounds[0].unionall(bounds[1:])
        canvas = pygame.Surface((max(1, union.width), max(1, union.height)), pygame.SRCALPHA)
        for surface, position in rendered:
            canvas.blit(surface, (position[0] - union.x, position[1] - union.y))
        return canvas


class AnimatedSprite:
    def __init__(self, source: SparrowAtlas | AnimateAtlas, animations: dict[str, str], fps: float = 24):
        self.source = source
        self.animations = animations
        self.fps = fps
        self.current = "idle" if "idle" in animations else next(iter(animations), "default")
        self.started = 0
        self.loop = True

    def play(self, name: str, now_ms: int, force: bool = False, loop: bool | None = None) -> None:
        if name not in self.animations:
            return
        if force or name != self.current:
            self.current = name
            self.started = now_ms
        if loop is not None:
            self.loop = loop

    def frame(self, now_ms: int) -> pygame.Surface:
        prefix = self.animations.get(self.current, next(iter(self.animations.values()), ""))
        index = max(0, int((now_ms - self.started) * self.fps / 1000))
        if isinstance(self.source, SparrowAtlas):
            frames = self.source.animation(prefix)
            index = index % len(frames) if self.loop else min(index, len(frames) - 1)
            return frames[index]
        return self.source.frame(prefix, index)
