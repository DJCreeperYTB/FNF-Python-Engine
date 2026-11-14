"""Fabrique les boutons MODS / TOOLS / TROPHIES du menu principal dans le style exact des sprites FNF.

On récupère seulement le REMPLISSAGE blanc de chaque lettre dans les vrais sprites (storymode, freeplay,
options, merch), on les aligne sur une ligne de base, puis on redessine un contour noir continu autour
du mot entier (avec l'épaisseur décalée vers le bas-droite comme les originaux). Pas de contour découpé.

python tools/build_menu_items.py  ->  fnf_assets/images/mainmenu/<item>.png + .xml (format Sparrow)
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
MENU = ROOT / "fnf_assets" / "images" / "mainmenu"

SOURCES = {"storymode": "STORYMODE", "freeplay": "FREEPLAY", "options": "OPTIONS", "merch": "MERCH"}
# Lettre -> (sprite source, position dans le mot). Minuscules = les petites lettres stylisées de FNF (StoRY MoDE).
PICKS = {
    "M": ("storymode", 5), "o": ("storymode", 6), "O": ("options", 0), "D": ("storymode", 7), "S": ("options", 6),
    "T": ("options", 2), "L": ("freeplay", 5), "R": ("storymode", 3), "P": ("options", 1),
    "H": ("merch", 4), "i": ("options", 3), "E": ("storymode", 8),
    "Y": ("storymode", 4), "F": ("freeplay", 0), "A": ("freeplay", 6), "N": ("options", 5),
}
# Tous les boutons du menu sont faits pareil, pour qu'ils aient exactement le même style.
ITEMS = {"storymode": "STORY MODE", "freeplay": "FREEPLAY", "mods": "MODS", "trophies": "TROPHiES", "tools": "TOOLS", "options": "OPTiONS",
         "donate": "DONATE", "online": "ONLiNE"}


def load_frames(name: str) -> list[Image.Image]:
    # Les sprites officiels sont gardés dans mainmenu/original/ (les boutons du menu sont regénérés).
    sheet = Image.open(MENU / "original" / f"{name}.png").convert("RGBA")
    text = (MENU / "original" / f"{name}.xml").read_text(encoding="utf-8")
    frames = []
    for tag in re.finditer(r"<SubTexture\s(.*?)/?>", text, re.S):
        a = dict(re.findall(r'(\w+)="([^"]*)"', tag.group(1)))
        if "selected" not in a["name"]:
            continue
        x, y, w, h = (int(a[k]) for k in ("x", "y", "width", "height"))
        frame = Image.new("RGBA", (int(a.get("frameWidth", w)), int(a.get("frameHeight", h))))
        frame.paste(sheet.crop((x, y, x + w, y + h)), (-int(a.get("frameX", 0)), -int(a.get("frameY", 0))))
        frames.append((a["name"], frame))
    return [frame for _, frame in sorted(frames, key=lambda item: item[0])]


def letter_fills(frame: Image.Image, count: int) -> list[tuple[np.ndarray, int]]:
    """Remplissage (couverture 0..1) de chaque lettre + décalage de sa base par rapport à la base du mot."""
    rgba = np.asarray(frame).astype(np.float32)
    luma = rgba[..., :3].mean(axis=2)
    coverage = np.clip((luma - 70) / 150, 0, 1) * (rgba[..., 3] / 255)
    hard = coverage > .5
    labels, _ = ndimage.label(hard)
    objects = ndimage.find_objects(labels)
    keep = [i + 1 for i, box in enumerate(objects) if box is not None and (labels[box] == i + 1).sum() > 60]
    groups: list[list[int]] = []
    for label in sorted(keep, key=lambda item: objects[item - 1][1].start):
        x0, x1 = objects[label - 1][1].start, objects[label - 1][1].stop
        for group in groups:
            gx0 = min(objects[i - 1][1].start for i in group)
            gx1 = max(objects[i - 1][1].stop for i in group)
            if min(x1, gx1) - max(x0, gx0) > .5 * min(x1 - x0, gx1 - gx0):
                group.append(label)
                break
        else:
            groups.append([label])
    while len(groups) > count:
        gaps = [min(objects[b - 1][1].start for b in groups[i + 1]) - max(objects[a - 1][1].stop for a in groups[i]) for i in range(len(groups) - 1)]
        i = int(np.argmin(gaps))
        groups[i] += groups.pop(i + 1)
    if len(groups) != count:
        raise ValueError(f"{len(groups)} lettres au lieu de {count}")
    grown = ndimage.grey_dilation(labels, size=(5, 5))  # récupère l'anti-aliasing autour du remplissage
    result, bottoms = [], []
    for group in groups:
        mask = np.isin(grown, group) & (coverage > 0)
        ys, xs = np.nonzero(mask)
        crop = np.where(mask, coverage, 0)[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        result.append((crop, ys.max()))
        bottoms.append(ys.max())
    base = float(np.median(bottoms))
    return [(crop, int(bottom - base)) for crop, bottom in result]


def render(fill: np.ndarray, radius: float, shadow: tuple[int, int], fill_rgb, line_rgb) -> Image.Image:
    distance = ndimage.distance_transform_edt(~(fill > .5))
    outline = np.clip(radius + .5 - distance, 0, 1)
    if shadow != (0, 0):
        outline = np.maximum(outline, ndimage.shift(outline, (shadow[1], shadow[0]), order=1))
    alpha = np.maximum(outline, fill)
    rgb = np.empty(fill.shape + (3,), np.float32)
    for c in range(3):
        rgb[..., c] = fill_rgb[c] * fill + line_rgb[c] * (1 - fill)
    out = np.dstack([rgb, alpha * 255]).clip(0, 255).astype(np.uint8)
    ys, xs = np.nonzero(alpha > .02)
    return Image.fromarray(out[ys.min():ys.max() + 1, xs.min():xs.max() + 1])


def compose(letters: list[tuple[np.ndarray, int]], gap: int) -> np.ndarray:
    pad = 40
    glyphs = [(crop, delta) for crop, delta in letters if crop is not None]
    above = max(crop.shape[0] - delta for crop, delta in glyphs)
    below = max(max(delta, 0) for _, delta in glyphs)
    width = sum(crop.shape[1] if crop is not None else 38 for crop, _ in letters) + gap * (len(letters) - 1) + 2 * pad
    canvas = np.zeros((above + below + 2 * pad, width), np.float32)
    base, x = pad + above, pad
    for crop, delta in letters:
        if crop is None:  # espace
            x += 38
            continue
        top = base + delta - crop.shape[0]
        region = canvas[top:top + crop.shape[0], x:x + crop.shape[1]]
        np.maximum(region, crop, out=region)
        x += crop.shape[1] + gap
    return canvas


def build(item: str, word: str, frames: dict, cache: dict) -> list[tuple[str, Image.Image]]:
    out, selected = [], []
    for k in range(3):
        letters = []
        for char in word:
            if char == " ":
                letters.append((None, 0))
                continue
            source, position = PICKS[char]
            key = (source, k)
            if key not in cache:
                try:
                    cache[key] = letter_fills(frames[source][k % len(frames[source])], len(SOURCES[source]))
                except ValueError:  # lettres collées sur cette frame : on reprend la frame 0
                    cache[key] = cache.get((source, 0)) or letter_fills(frames[source][0], len(SOURCES[source]))
            letters.append(cache[key][position])
        fill = compose(letters, gap=7)
        selected.append(render(fill, 11, (4, 6), (255, 255, 255), (0, 0, 0)))
        if k == 0:
            # Les "idle" de FNF : lettres noires, contour blanc plus fin, sprite plus petit.
            idle = render(fill, 8, (0, 0), (0, 0, 0), (255, 255, 255))
            out.append((f"{item} idle0000", idle.resize((round(idle.width * .74), round(idle.height * .74)), Image.LANCZOS)))
    return out + [(f"{item} selected{k:04d}", frame) for k, frame in enumerate(selected)]


def save(item: str, frames_out: list[tuple[str, Image.Image]]) -> None:
    frame_w = max(frame.width for _, frame in frames_out)
    frame_h = max(frame.height for _, frame in frames_out)
    sheet = Image.new("RGBA", (frame_w, sum(frame.height + 2 for _, frame in frames_out)))
    xml = ['<?xml version="1.0" encoding="utf-8"?>', f'<TextureAtlas imagePath="{item}.png">']
    y = 0
    for name, frame in frames_out:
        sheet.paste(frame, (0, y))
        fx, fy = -(frame_w - frame.width) // 2, -(frame_h - frame.height) // 2
        xml.append(f'\t<SubTexture name="{name}" x="0" y="{y}" width="{frame.width}" height="{frame.height}" '
                   f'frameX="{fx}" frameY="{fy}" frameWidth="{frame_w}" frameHeight="{frame_h}"/>')
        y += frame.height + 2
    xml.append("</TextureAtlas>")
    sheet.save(MENU / f"{item}.png")
    (MENU / f"{item}.xml").write_text("\n".join(xml), encoding="utf-8")


if __name__ == "__main__":
    frames = {name: load_frames(name) for name in SOURCES}
    cache: dict = {}
    for item, word in ITEMS.items():
        save(item, build(item, word, frames, cache))
        print("ok", item)
