from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pygame
from PIL import Image


class Assets:
    """Résolution et cache des ressources : dossiers des mods actifs d'abord, jeu de base ensuite."""

    def __init__(self, root: Path, mod_roots: list[Path] | tuple[Path, ...] = ()):
        self.root = root
        self.roots = [*mod_roots, root]
        self._images: dict[tuple[Path, bool], pygame.Surface] = {}
        self._sounds: dict[Path, pygame.mixer.Sound] = {}
        self._atlases: dict[Path, SparrowAtlas | AnimateAtlas] = {}

    def clear(self) -> None:
        self._images.clear()
        self._atlases.clear()

    def path(self, relative: str | Path) -> Path:
        """Premier fichier/dossier existant parmi les mods puis le jeu de base."""
        for root in self.roots:
            candidate = root / relative
            if candidate.exists():
                return candidate
        return self.root / relative

    def all_paths(self, relative: str | Path) -> list[Path]:
        """Toutes les copies existantes, mods d'abord (pour fusionner des dossiers)."""
        return [root / relative for root in self.roots if (root / relative).exists()]

    def find(self, relative: str | Path, extensions: tuple[str, ...] = ("",)) -> Path | None:
        relative = str(relative).replace("\\", "/").removeprefix("assets/")
        for extension in extensions:
            rel = relative if not extension or relative.lower().endswith(extension) else relative + extension
            for root in self.roots:
                for candidate in (root / rel, root / "images" / rel, root / "shared" / "images" / rel):
                    if candidate.is_file():
                        return candidate
        return None

    def resolve_image(self, asset_path: str, library: str | None = None) -> Path | None:
        """Chemin FNF "lib:dossier/nom" ou "dossier/nom" -> PNG ou dossier Animate existant."""
        if ":" in asset_path:
            library, asset_path = asset_path.split(":", 1)
        folders = [f"{library}/images"] if library else []
        folders += ["images", "shared/images"]
        for root in self.roots:
            for folder in folders:
                base = root / folder / asset_path
                if (base / "Animation.json").is_file():
                    return base
                if base.with_suffix(".png").is_file():
                    return base.with_suffix(".png")
        return None

    def libraries(self) -> list[str]:
        """Dossiers "bibliothèques" (shared, week6...) : ceux qui contiennent images/, music/ ou sounds/."""
        if not hasattr(self, "_libraries"):
            names = {""}
            for root in self.roots:
                if root.is_dir():
                    names.update(child.name for child in root.iterdir() if child.is_dir() and any((child / kind).is_dir() for kind in ("images", "music", "sounds")))
            self._libraries = sorted(names, key=lambda name: (name not in ("", "shared"), name))
        return self._libraries

    def search(self, kind: str, relative: str) -> Path | None:
        """Cherche kind/relative (kind = images, music, sounds...) dans toutes les bibliothèques."""
        for root in self.roots:
            for library in self.libraries():
                candidate = root / library / kind / relative
                if candidate.exists():
                    return candidate
        return None

    def resolve_any(self, asset_path: str) -> Path | None:
        """Comme resolve_image, mais essaie aussi chaque bibliothèque (week6:weeb/... sans préfixe)."""
        found = self.resolve_image(asset_path)
        if found or ":" in asset_path:
            return found
        for library in self.libraries():
            found = self.resolve_image(asset_path, library) if library else None
            if found:
                return found
        return None

    def atlas(self, asset_path: str, library: str | None = None) -> SparrowAtlas | AnimateAtlas | None:
        resolved = self.resolve_image(asset_path, library) or self.resolve_any(asset_path)
        if resolved is None:
            return None
        if resolved not in self._atlases:
            self._atlases[resolved] = AnimateAtlas(self, resolved) if resolved.is_dir() else SparrowAtlas(self, resolved)
        return self._atlases[resolved]

    def image(self, path: Path, alpha: bool = True) -> pygame.Surface:
        key = (path, alpha)
        if key not in self._images:
            loaded = pygame.image.load(path)
            self._images[key] = loaded.convert_alpha() if alpha else loaded.convert()
        return self._images[key]

    def sound(self, path: Path) -> pygame.mixer.Sound:
        if path not in self._sounds:
            self._sounds[path] = pygame.mixer.Sound(path)
        return self._sounds[path]

    @staticmethod
    def json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8-sig"))


class SparrowAtlas:
    """Lecteur des spritesheets Sparrow/Starling (PNG + XML) et "packer" (PNG + TXT) utilisés par FNF."""

    def __init__(self, assets: Assets, png_path: Path):
        self.assets = assets
        self.png_path = png_path
        xml_path = png_path.with_suffix(".xml")
        sliced = xml_path.is_file() or png_path.with_suffix(".txt").is_file()
        # Feuille découpée : on la charge sans la garder en cache, les frames sont des copies (mémoire).
        self.sheet = pygame.image.load(png_path).convert_alpha() if sliced and pygame.display.get_surface() else assets.image(png_path)
        self.frames: list[tuple[str, pygame.Surface]] = []
        self.origins: dict[int, tuple[int, int]] = {}  # id(frame) -> décalage du coin haut-gauche (frameX/Y positifs)
        if xml_path.is_file():
            # Lecture tolérante comme Flixel : certains XML de FNF contiennent des "<" non échappés (alphabet).
            text = xml_path.read_text(encoding="utf-8-sig", errors="replace")
            for tag in re.finditer(r"<SubTexture\s(.*?)/?>\s*(?=<|$)", text, re.S):
                attrib = dict(re.findall(r'(\w+)="([^"]*)"', tag.group(1)))
                node = type("Node", (), {"attrib": attrib})
                name = attrib.get("name", "")
                x, y = int(node.attrib["x"]), int(node.attrib["y"])
                width, height = int(node.attrib["width"]), int(node.attrib["height"])
                rect = pygame.Rect(x, y, width, height).clip(self.sheet.get_rect())
                crop = self.sheet.subsurface(rect).copy()
                if node.attrib.get("rotated") == "true":
                    crop = pygame.transform.rotate(crop, 90)
                frame_width = int(node.attrib.get("frameWidth", crop.get_width()))
                frame_height = int(node.attrib.get("frameHeight", crop.get_height()))
                dx, dy = -int(node.attrib.get("frameX", 0)), -int(node.attrib.get("frameY", 0))
                # frameX/frameY positifs (portraits de la Week 6) : l'image dépasse du cadre, on agrandit au lieu de couper.
                width = max(frame_width, dx + crop.get_width()) - min(0, dx)
                height = max(frame_height, dy + crop.get_height()) - min(0, dy)
                surface = pygame.Surface((max(1, width), max(1, height)), pygame.SRCALPHA)
                surface.blit(crop, (dx - min(0, dx), dy - min(0, dy)))
                if dx < 0 or dy < 0:
                    self.origins[id(surface)] = (min(0, dx), min(0, dy))
                self.frames.append((name, surface))
        elif png_path.with_suffix(".txt").is_file():
            # Format "packer" (Spirit) : une ligne "nom = x y largeur hauteur" par frame.
            for line in png_path.with_suffix(".txt").read_text(encoding="utf-8").splitlines():
                name, _, rect = line.partition("=")
                values = [int(value) for value in rect.split()]
                if len(values) == 4:
                    self.frames.append((name.strip(), self.sheet.subsurface(pygame.Rect(values).clip(self.sheet.get_rect())).copy()))
        if not self.frames:
            self.frames.append((png_path.stem, self.sheet))
        elif sliced:
            self.sheet = None

    def has(self, prefix: str) -> bool:
        wanted = prefix.lower()
        return any(name.lower().startswith(wanted) for name, _ in self.frames)

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


_LONG_KEYS = {
    "ANIMATION": "AN", "SYMBOL_DICTIONARY": "SD", "Symbols": "S", "SYMBOL_name": "SN", "TIMELINE": "TL",
    "LAYERS": "L", "Frames": "FR", "index": "I", "duration": "DU", "elements": "E", "ATLAS_SPRITE_instance": "ASI",
    "SYMBOL_Instance": "SI", "name": "N", "firstFrame": "FF", "loop": "LP", "metadata": "MD", "framerate": "FRT",
    "color": "C", "mode": "M", "alphaMultiplier": "AM", "RedMultiplier": "RM", "redMultiplier": "RM",
    "greenMultiplier": "GM", "blueMultiplier": "BM", "redOffset": "RO", "greenOffset": "GO", "blueOffset": "BO",
    "AlphaOffset": "AO", "alphaOffset": "AO", "tintColor": "TC", "tintMultiplier": "TM", "brightness": "BRT",
}
_LOOP_MODES = {"loop": "LP", "playonce": "PO", "singleframe": "SF"}
_IDENTITY_COLOR = (1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0)


def _short_keys(node):
    """Les exports Animate "non optimisés" utilisent des clés longues : on les ramène au format court."""
    if isinstance(node, list):
        return [_short_keys(item) for item in node]
    if not isinstance(node, dict):
        return node
    result = {}
    for key, value in node.items():
        if key == "Matrix3D" and isinstance(value, dict):
            result["MX"] = [value.get("m00", 1), value.get("m01", 0), value.get("m10", 0), value.get("m11", 1), value.get("m30", 0), value.get("m31", 0)]
        elif key in ("M3D", "Matrix3D") and isinstance(value, list) and len(value) >= 14:
            # Matrice 4x4 (colonnes) des exports récents : on garde la partie 2D (a, b, c, d, tx, ty).
            result["MX"] = [value[0], value[1], value[4], value[5], value[12], value[13]]
        elif key == "loop" and isinstance(value, str):
            result["LP"] = _LOOP_MODES.get(value.lower(), "LP")
        else:
            result[_LONG_KEYS.get(key, key)] = _short_keys(value)
    return result


def _color_effect(instance: dict) -> tuple[float, ...] | None:
    """Effet de couleur Animate -> (multiplicateurs RGBA, décalages RGBA)."""
    effect = instance.get("C")
    if not isinstance(effect, dict):
        return None
    mode = str(effect.get("M", ""))

    def get(key: str, default: float) -> float:
        return float(effect.get(key, default))

    if mode in ("CA", "Alpha"):
        return (1, 1, 1, get("AM", 1), 0, 0, 0, 0)
    if mode in ("AD", "Advanced"):
        return (get("RM", 1), get("GM", 1), get("BM", 1), get("AM", 1), get("RO", 0), get("GO", 0), get("BO", 0), get("AO", 0))
    if mode in ("T", "Tint"):
        amount = get("TM", 0)
        color = pygame.Color(str(effect.get("TC", "#000000")))
        return (1 - amount, 1 - amount, 1 - amount, 1, color.r * amount, color.g * amount, color.b * amount, 0)
    if mode in ("CBRT", "Brightness"):
        bright = get("BRT", 0)
        if bright < 0:
            return (1 + bright, 1 + bright, 1 + bright, 1, 0, 0, 0, 0)
        return (1 - bright, 1 - bright, 1 - bright, 1, 255 * bright, 255 * bright, 255 * bright, 0)
    return None


def _combine_color(parent: tuple[float, ...], child: tuple[float, ...] | None) -> tuple[float, ...]:
    if child is None:
        return parent
    return tuple(child[i] * parent[i] for i in range(4)) + tuple(child[i + 4] * parent[i] + parent[i + 4] for i in range(4))


class AnimateAtlas:
    """Rendu des exports Adobe Animate Texture Atlas de FNF.

    Les symboles sont composés récursivement avec leur matrice affine complète
    (échelle, rotation, miroir et cisaillement) et leurs effets de couleur.
    Chaque frame est renvoyée avec la position de son coin haut-gauche dans le
    repère de la timeline, pour que le personnage reste ancré d'une frame à l'autre.
    """

    def __init__(self, assets: Assets, directory: Path):
        self.assets = assets
        self.directory = directory
        self.data = _short_keys(assets.json(directory / "Animation.json"))
        self.animation = self.data["AN"]
        self.fps = float(self.data.get("MD", {}).get("FRT", 24))
        self.symbols = {symbol["SN"]: symbol for symbol in self.data.get("SD", {}).get("S", [])}
        self.sprites: dict[str, Image.Image] = {}
        for json_path in sorted(directory.glob("spritemap*.json")):
            atlas_data = assets.json(json_path)["ATLAS"]
            sheet_name = atlas_data.get("meta", {}).get("image", json_path.with_suffix(".png").name)
            with Image.open(directory / sheet_name) as opened:
                sheet = opened.convert("RGBA")
            for item in atlas_data.get("SPRITES", []):
                sprite = item["SPRITE"]
                x, y, w, h = int(sprite["x"]), int(sprite["y"]), int(sprite["w"]), int(sprite["h"])
                piece = sheet.crop((x, y, x + w, y + h))
                if sprite.get("rotated"):
                    piece = piece.rotate(90, expand=True)
                self.sprites[str(sprite["name"])] = piece
        self.labels = self._read_labels()

    def _read_labels(self) -> dict[str, tuple[int, int]]:
        labels: dict[str, tuple[int, int]] = {}
        for layer in self.animation.get("TL", {}).get("L", []):
            for frame in layer.get("FR", []):
                if "N" in frame:
                    labels[str(frame["N"]).lower()] = (int(frame.get("I", 0)), max(1, int(frame.get("DU", 1))))
        if not labels:
            labels["default"] = (0, max(1, self._timeline_length(self.animation.get("TL", {}))))
        return labels

    def has(self, prefix: str) -> bool:
        wanted = prefix.lower()
        return any(label.startswith(wanted) for label in self.labels) or self._symbol(prefix) is not None

    def _symbol(self, prefix: str) -> dict | None:
        """Animation « animType: symbol » : la timeline d'un symbole (ex. BOPPERS_EXPORT, le public de la Week 5 Erect)."""
        wanted = prefix.lower()
        if any(label.startswith(wanted) for label in self.labels):
            return None
        if prefix == self.animation.get("SN"):  # le symbole exporté est la timeline principale elle-même
            return self.animation
        return self.symbols.get(prefix)

    def find_label(self, prefix: str) -> tuple[str, int, int]:
        symbol = self._symbol(prefix)
        if symbol is not None:
            return prefix, 0, max(1, self._timeline_length(symbol.get("TL", {})))
        wanted = prefix.lower()
        # Le nom exact gagne : "Left" ne doit pas tomber sur "Left Miss".
        match = wanted if wanted in self.labels else next((label for label in self.labels if label.startswith(wanted)), None)
        label = match or next(iter(self.labels))
        start, duration = self.labels[label]
        return label, start, duration

    def frame(self, prefix: str, index: int, hidden: tuple[str, ...] = ()) -> tuple[pygame.Surface, tuple[int, int]]:
        """Frame composée + position de son coin haut-gauche dans la timeline.
        hidden : préfixes de noms de calques à ne pas dessiner (ex. "HAT" : le bonnet de Monster hors Noël)."""
        _, start, duration = self.find_label(prefix)
        symbol = self._symbol(prefix)
        timeline = symbol.get("TL", {}) if symbol is not None else self.animation.get("TL", {})
        commands: list[tuple[str, tuple[float, ...], tuple[float, ...]]] = []
        self._render_timeline(timeline, start + index % duration, (1, 0, 0, 1, 0, 0), _IDENTITY_COLOR, commands, hidden)
        return self._compose(commands)

    def whole_bounds(self) -> tuple[float, float, float, float]:
        """Cadre (x, y, l, h) qui englobe TOUTES les images de la timeline principale.
        flixel-animate (le jeu officiel) place un atlas par ce cadre : position = son coin, taille = la sienne."""
        if getattr(self, "_whole", None) is None:
            timeline = self.animation.get("TL", {})
            x0 = y0 = float("inf"); x1 = y1 = float("-inf")
            for frame in range(self._timeline_length(timeline)):
                commands: list = []
                self._render_timeline(timeline, frame, (1, 0, 0, 1, 0, 0), _IDENTITY_COLOR, commands)
                for name, (a, b, c, d, tx, ty), color in commands:
                    if color[3] <= 0 and color[7] <= 0:
                        continue
                    w, h = self.sprites[name].size
                    xs = (tx, a * w + tx, c * h + tx, a * w + c * h + tx)
                    ys = (ty, b * w + ty, d * h + ty, b * w + d * h + ty)
                    x0, y0, x1, y1 = min(x0, *xs), min(y0, *ys), max(x1, *xs), max(y1, *ys)
            self._whole = (x0, y0, x1 - x0, y1 - y0) if x1 > x0 else (0.0, 0.0, 1.0, 1.0)
        return self._whole

    def frame_at(self, frame_number: int) -> tuple[pygame.Surface, tuple[int, int]]:
        """Frame n de la timeline principale, sans passer par les étiquettes."""
        commands: list[tuple[str, tuple[float, ...], tuple[float, ...]]] = []
        self._render_timeline(self.animation.get("TL", {}), frame_number, (1, 0, 0, 1, 0, 0), _IDENTITY_COLOR, commands)
        return self._compose(commands)

    def _timeline_length(self, timeline: dict) -> int:
        return max((int(frame.get("I", 0)) + int(frame.get("DU", 1))
                    for layer in timeline.get("L", []) for frame in layer.get("FR", [])), default=1)

    def _active_frame(self, frames: list[dict], frame_number: int) -> dict | None:
        for frame in frames:
            start, duration = int(frame.get("I", 0)), int(frame.get("DU", 1))
            if start <= frame_number < start + duration:
                return frame
        return frames[-1] if frames and frame_number >= int(frames[-1].get("I", 0)) else None

    def _render_timeline(self, timeline: dict, frame_number: int, matrix: tuple[float, ...],
                         color: tuple[float, ...], commands: list, hidden: tuple[str, ...] = ()) -> None:
        for layer in reversed(timeline.get("L", [])):
            if hidden and str(layer.get("LN", "")).startswith(hidden):
                continue
            active = self._active_frame(layer.get("FR", []), frame_number)
            if not active:
                continue
            delta = frame_number - int(active.get("I", 0))
            for element in active.get("E", []):
                if "ASI" in element:
                    instance = element["ASI"]
                    name = str(instance.get("N"))
                    if name in self.sprites:
                        commands.append((name, _matrix_multiply(matrix, instance.get("MX", [1, 0, 0, 1, 0, 0])), color))
                elif "SI" in element:
                    instance = element["SI"]
                    symbol = self.symbols.get(instance.get("SN"))
                    if not symbol:
                        continue
                    child_color = _combine_color(color, _color_effect(instance))
                    if child_color[3] <= 0 and child_color[7] <= 0:
                        continue  # symbole invisible (alpha 0) : reflets, yeux cachés...
                    child_matrix = _matrix_multiply(matrix, instance.get("MX", [1, 0, 0, 1, 0, 0]))
                    child_timeline = symbol.get("TL", {})
                    length = self._timeline_length(child_timeline)
                    loop_mode = instance.get("LP", "LP")
                    child_frame = int(instance.get("FF", 0)) + (0 if loop_mode == "SF" else delta)
                    if loop_mode == "LP":
                        child_frame %= max(1, length)
                    else:
                        child_frame = min(child_frame, max(0, length - 1))
                    self._render_timeline(child_timeline, child_frame, child_matrix, child_color, commands, hidden)

    def _piece_surface(self, name: str, color: tuple[float, ...]) -> pygame.Surface:
        """Pièce convertie en surface pygame, effet de couleur appliqué, gardée en cache (réutilisée d'une image à l'autre)."""
        key = (name, tuple(round(value, 3) for value in color))
        cache = self.__dict__.setdefault("_pieces", {})
        bases = self.__dict__.setdefault("_piece_bases", {})
        if key not in cache:
            if len(cache) > 256:
                cache.clear()
            if name not in bases:  # conversion PIL -> pygame une seule fois par pièce
                source = self.sprites[name]
                base = pygame.image.frombytes(source.tobytes(), source.size, "RGBA")
                bases[name] = base.convert_alpha() if pygame.display.get_surface() is not None else base
            surface = bases[name].copy() if color != _IDENTITY_COLOR else bases[name]
            if color != _IDENTITY_COLOR:
                multiply = tuple(max(0, min(255, round(value * 255))) for value in color[:4])
                surface.fill(multiply, special_flags=pygame.BLEND_RGBA_MULT)
                add = tuple(max(0, min(255, round(value))) for value in color[4:8])
                sub = tuple(max(0, min(255, round(-value))) for value in color[4:8])
                if any(add):
                    surface.fill(add, special_flags=pygame.BLEND_RGBA_ADD)
                if any(sub):
                    surface.fill(sub, special_flags=pygame.BLEND_RGBA_SUB)
            cache[key] = surface
        return cache[key]

    def _compose(self, commands: list) -> tuple[pygame.Surface, tuple[int, int]]:
        # Chemin rapide : pièces seulement déplacées (ni rotation ni échelle), assemblées par blit pygame.
        # Le décor de la Week 2 (2534 x 1835) passe de ~300 ms à quelques dizaines de ms par image (éclairs).
        if commands and all(abs(a - 1) < 1e-6 and abs(d - 1) < 1e-6 and abs(b) < 1e-6 and abs(c) < 1e-6
                            for _, (a, b, c, d, _tx, _ty), _ in commands):
            placed = []
            for name, (_a, _b, _c, _d, tx, ty), color in commands:
                if color[3] <= 0 and color[7] <= 0:
                    continue
                placed.append((self._piece_surface(name, color), round(tx), round(ty)))
            if not placed:
                return pygame.Surface((2, 2), pygame.SRCALPHA), (0, 0)
            left = min(x for _, x, _ in placed)
            top = min(y for _, _, y in placed)
            right = max(x + surface.get_width() for surface, x, _ in placed)
            bottom = max(y + surface.get_height() for surface, _, y in placed)
            canvas = pygame.Surface((right - left, bottom - top), pygame.SRCALPHA)
            for surface, x, y in placed:
                canvas.blit(surface, (x - left, y - top))
            return canvas, (left, top)
        pieces: list[tuple[Image.Image, int, int]] = []
        for name, (a, b, c, d, tx, ty), color in commands:
            det = a * d - b * c
            if abs(det) < 1e-9:
                continue
            source = self.sprites[name]
            w, h = source.size
            xs = (tx, a * w + tx, c * h + tx, a * w + c * h + tx)
            ys = (ty, b * w + ty, d * h + ty, b * w + d * h + ty)
            x0, y0 = math.floor(min(xs)), math.floor(min(ys))
            size = (max(1, math.ceil(max(xs)) - x0), max(1, math.ceil(max(ys)) - y0))
            # Matrice inverse : pour chaque pixel de sortie, PIL va chercher le pixel source.
            inverse = (d / det, -c / det, (d * (x0 - tx) - c * (y0 - ty)) / det,
                       -b / det, a / det, (-b * (x0 - tx) + a * (y0 - ty)) / det)
            piece = source.transform(size, Image.AFFINE, inverse, resample=Image.BILINEAR)
            if color != _IDENTITY_COLOR:
                bands = piece.split()
                piece = Image.merge("RGBA", [band.point(lambda v, m=color[i], o=color[i + 4]: v * m + o) for i, band in enumerate(bands)])
            pieces.append((piece, x0, y0))
        if not pieces:
            return pygame.Surface((2, 2), pygame.SRCALPHA), (0, 0)
        left = min(x for _, x, _ in pieces)
        top = min(y for _, _, y in pieces)
        right = max(x + piece.width for piece, x, _ in pieces)
        bottom = max(y + piece.height for piece, _, y in pieces)
        canvas = Image.new("RGBA", (right - left, bottom - top))
        for piece, x, y in pieces:
            canvas.alpha_composite(piece, (x - left, y - top))
        surface = pygame.image.frombytes(canvas.tobytes(), canvas.size, "RGBA")
        if pygame.display.get_surface() is not None:
            surface = surface.convert_alpha()
        return surface, (left, top)
