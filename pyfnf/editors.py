"""Outils de moddeur : éditeur de chart, éditeur de scène et caméra, éditeur de personnage.

Tout ce qui est enregistré depuis le jeu de base ou un mod en .zip part dans Editor Saves/ (à côté de mods/, chargé par défaut)
(un mod prioritaire, donc les changements s'appliquent tout de suite sans toucher aux originaux).
Un fichier qui vient d'un mod en dossier est modifié sur place.
"""
from __future__ import annotations

import copy
import json
import math
import random
import shutil
from pathlib import Path

import numpy as np
import pygame

from .assets import SparrowAtlas
from .data import difficulty_sort_key
from .help import open_help
from .menus import ListMenu, MainMenuState, frames
from .mods import cache_dir, editor_saves_dir, mods_dir
from .stage import Character, Stage, StaticProp, to_screen
from .ui import (BLACK, CHECKER, CYAN, HEIGHT, LANE_COLORS, PINK, RED, UI_ACCENT, UI_BG, UI_BORDER, UI_MUTED, UI_TEXT,
                 UI_TITLE, WHITE, WIDTH, YELLOW, BaseState, fit, rows, scale_by, shade, toast, toolbar, window)

SNAPS = (4, 8, 12, 16, 24, 32, 48, 64)

# ------------------------------------------------------------ utilitaires ----
def save_target(app, source: Path | None, relative: str) -> Path:
    """Où enregistrer : sur place si le fichier vient d'un mod en dossier, sinon dans Editor Saves/ (jeu par défaut)."""
    if source is not None:
        resolved = source.resolve()
        in_base = app.base_root.resolve() in resolved.parents
        in_cache = cache_dir().resolve() in resolved.parents
        if not in_base and not in_cache and mods_dir().resolve() in resolved.parents:
            return source
    target = editor_saves_dir() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def all_ids(app, folder: str) -> list[str]:
    ids = set()
    for root in app.assets.roots:
        ids.update(path.stem for path in (root / folder).glob("*.json"))
    return sorted(ids, key=str.lower)


class TextPrompt:
    """Petite zone de saisie au clavier (Entrée valide, Échap annule)."""

    def __init__(self, label: str, value: str, on_done, hint: str = ""):
        self.label, self.value, self.on_done, self.hint = label, value, on_done, hint

    def event(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_RETURN:
            self.on_done(self.value)
            return True
        if event.key == pygame.K_ESCAPE:
            return True
        if event.key == pygame.K_BACKSPACE:
            self.value = self.value[:-1]
        elif event.unicode and event.unicode.isprintable():
            self.value += event.unicode
        return False

    def draw(self, app, screen: pygame.Surface) -> None:
        screen.blit(app.shade(110), (0, 0))
        box = pygame.Rect(0, 0, 760, 176 if self.hint else 150); box.center = (WIDTH // 2, HEIGHT // 2)
        top = window(app, screen, box, app.tr(self.label))
        field = pygame.Rect(box.x + 16, top + 8, box.width - 32, 38)
        pygame.draw.rect(screen, WHITE, field)
        pygame.draw.rect(screen, UI_ACCENT, field, 2)
        cursor = "|" if (pygame.time.get_ticks() // 400) % 2 else ""
        app.text(screen, self.value + cursor, (field.x + 10, field.y + 8), 20, color=UI_TEXT, raw=True)
        if self.hint:
            app.text(screen, self.hint, (box.centerx, field.bottom + 8), 14, center=True, color=UI_MUTED, raw=True)
        app.text(screen, "ENTER OK     ESC CANCEL", (box.centerx, box.bottom - 30), 15, center=True, color=UI_MUTED)


# ------------------------------------------------------- événements du chart ----
def _field(key, kind, default, label, choices=None, step=1.0):
    return {"key": key, "type": kind, "default": default, "label": label, "choices": choices, "step": step}


_EASES = ["linear", "sine", "quad", "cube", "quart", "quint", "expo", "circ", "back", "elastic", "bounce", "smoothStep", "INSTANT"]
# Événements natifs du moteur (clés JSON au format V-Slice) ; les mods en ajoutent via data/events/*.json.
NATIVE_EVENTS = {
    "FocusCamera": {"description": "Moves the camera to a character or a point.", "fields": [
        _field("char", "choice", 0, "Character", [(0, "Player (BF)"), (1, "Opponent"), (2, "Girlfriend (GF)")]),
        _field("x", "number", 0, "X offset", step=10), _field("y", "number", 0, "Y offset", step=10),
        _field("ease", "choice", "CLASSIC", "Movement", ["CLASSIC", "INSTANT"])]},
    "PlayAnimation": {"description": "Plays an animation on a character or a stage element.", "fields": [
        _field("target", "text", "bf", "Target (bf, dad, gf, prop)"), _field("anim", "text", "hey", "Animation"),
        _field("force", "bool", True, "Restart if playing")]},
    "ZoomCamera": {"description": "Zooms the camera smoothly (1 = normal stage zoom).", "fields": [
        _field("zoom", "number", 1.0, "Zoom", step=.05), _field("duration", "number", 4, "Duration (1/16 steps)"),
        _field("mode", "choice", "stage", "Zoom mode", ["stage", "direct"]), _field("ease", "choice", "expo", "Easing", _EASES),
        _field("easeDir", "choice", "Out", "Direction", ["In", "Out", "InOut"])]},
    "SetCameraBop": {"description": "Sets the camera bounce on the beat (rate 0 = never).", "fields": [
        _field("rate", "int", 4, "Every N beats"), _field("intensity", "number", 1.0, "Intensity", step=.1)]},
    "ScrollSpeed": {"description": "Changes the speed of the arrows.", "fields": [
        _field("scroll", "number", 1.0, "Speed", step=.1), _field("absolute", "bool", False, "Absolute value")]},
    "SetHealthIcon": {"description": "Changes the icon of a health bar side.", "fields": [
        _field("char", "choice", 0, "Side", [(0, "Player"), (1, "Opponent")]), _field("id", "text", "", "Icon id")]},
    "FlashScreen": {"description": "Flashes the screen with a color.", "fields": [
        _field("color", "color", [255, 255, 255], "Color"), _field("duration", "int", 400, "Duration (ms)", step=50)]},
    "Subtitle": {"description": "Shows a subtitle in the language of the game (French or English text).", "fields": [
        _field("fr", "text", "", "French text"), _field("en", "text", "", "English text"),
        _field("duration", "int", 3000, "Duration (ms)", step=250), _field("size", "int", 28, "Text size", step=2),
        _field("color", "color", [255, 255, 255], "Text color"), _field("opacity", "int", 100, "Text opacity (%)", step=10),
        _field("background", "color", [0, 0, 0], "Background color"),
        _field("background_opacity", "int", 63, "Background opacity (%)", step=10),
        _field("outline", "bool", False, "Black outline"), _field("bold", "bool", True, "Bold"),
        _field("position", "choice", "bottom", "Position", [("bottom", "Bottom"), ("middle", "Middle"), ("top", "Top")]),
        _field("font", "text", "", "Font (name or .ttf)")]},
    "ChangeStage": {"description": "Changes the stage during the song (the characters go to the places of the new stage).", "fields": [
        _field("stage", "text", "mainStage", "Stage id (data/stages/<id>.json)")]},
    "ShakeCamera": {"description": "Shakes the camera.", "fields": [
        _field("intensity", "number", 10, "Intensity (px)"), _field("duration", "int", 400, "Duration (ms)", step=50)]},
}
PALETTE = [[255, 255, 255], [255, 60, 60], [255, 170, 40], [250, 230, 70], [80, 210, 100], [70, 210, 230], [70, 110, 240], [170, 90, 240], [0, 0, 0]]
FIELD_TYPES = ("number", "int", "text", "bool", "choice", "color")


def event_definitions(app) -> dict:
    """Événements natifs puis ceux des mods et du jeu de base (data/events/*.json, le premier nom trouvé gagne)."""
    defs = copy.deepcopy(NATIVE_EVENTS)
    for root in app.assets.roots:
        for path in sorted((Path(root) / "data/events").glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                name = str(raw["name"])
                if name in defs:
                    continue
                fields = []
                for item in raw.get("fields", []):
                    kind = item.get("type", "text")
                    kind = kind if kind in FIELD_TYPES else "text"
                    choices = [tuple(c) if isinstance(c, list) and len(c) == 2 else c for c in item.get("choices", [])]
                    if kind == "choice" and not choices:
                        kind = "text"
                    fallback = {"bool": False, "color": [255, 255, 255], "number": 0, "int": 0}.get(kind, "")
                    if kind == "choice":
                        fallback = choices[0][0] if isinstance(choices[0], tuple) else choices[0]
                    key = str(item["key"])
                    fields.append(_field(key, kind, item.get("default", fallback), str(item.get("label", key)), choices or None, float(item.get("step", 1.0))))
                defs[name] = {"description": str(raw.get("description", "")), "fields": fields}
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue
    return defs


class EventPanel:
    """Panneau visuel pour créer / modifier un événement : liste à gauche, champs à droite, onglet « Texte » pour les experts."""

    BOX = pygame.Rect(150, 70, 980, 560)
    ROWS = 14  # noms visibles dans la liste

    def __init__(self, app, defs: dict, event: dict | None, on_done, on_text):
        self.app, self.defs, self.on_done, self.on_text = app, defs, on_done, on_text
        self.names = list(defs)
        self.text_mode, self.text, self.focus, self.scroll = False, "", 0, 0
        name = event.get("e") if event else "FocusCamera"
        if name in defs:
            self._load(name, event.get("v") if event else None)
        else:  # nom inconnu : saisie texte
            self._load("FocusCamera")
            self.text_mode, self.text = True, f"{name}|{json.dumps(event.get('v', {}))}"

    # ----- données
    def _load(self, name: str, value=None) -> None:
        self.name, fields = name, self.defs[name]["fields"]
        if value is not None and not isinstance(value, dict):
            value = {fields[0]["key"]: value} if fields else {}
        value = value or {}
        self.vals = {}
        for f in fields:
            v = value.get(f["key"], f["default"])
            numeric = f["type"] in ("number", "int") and isinstance(v, (int, float)) and not isinstance(v, bool)
            self.vals[f["key"]] = f"{v:g}" if numeric else v  # nombres et textes sont édités sous forme de texte
        self.extra = {k: v for k, v in value.items() if k not in self.vals}  # champs inconnus : conservés tels quels
        self.focus = 0
        self.scroll = max(0, min(self.names.index(name) - 6, len(self.names) - self.ROWS))

    def value(self) -> dict:
        out = dict(self.extra)
        for f in self.defs[self.name]["fields"]:
            v = self.vals[f["key"]]
            if f["type"] in ("number", "int"):
                try:
                    number = float(str(v).replace(",", "."))
                except ValueError:
                    number = float(f["default"] or 0)
                v = int(round(number)) if f["type"] == "int" or number == int(number) else round(number, 4)
            out[f["key"]] = v
        return out

    @staticmethod
    def _options(f, v) -> list:
        if f["type"] == "color":
            return PALETTE + ([v] if v not in PALETTE else [])
        return [c[0] if isinstance(c, tuple) else c for c in f["choices"]]

    def _step(self, index: int, direction: int) -> None:
        f = self.defs[self.name]["fields"][index]
        v = self.vals[f["key"]]
        if f["type"] in ("number", "int"):
            try:
                number = float(str(v).replace(",", "."))
            except ValueError:
                number = 0.0
            step = 1.0 if f["type"] == "int" else f["step"]
            self.vals[f["key"]] = f"{round(number + direction * step, 4):g}"
        elif f["type"] == "bool":
            self.vals[f["key"]] = not v
        elif f["type"] in ("choice", "color"):
            options = self._options(f, v)
            at = options.index(v) if v in options else -1
            self.vals[f["key"]] = options[(at + direction) % len(options)]

    # ----- géométrie (partagée par le dessin et la souris)
    def _controls(self) -> list:
        box = self.BOX
        px, top = box.x + 260, box.y + 96
        found = []
        fields = self.defs[self.name]["fields"]
        step = max(30, min(40, (box.bottom - 66 - top) // max(1, len(fields))))  # beaucoup de champs : lignes resserrées
        for i, f in enumerate(fields):
            y, cx = top + i * step, px + 230
            found.append(("row", pygame.Rect(px - 6, y - (step - 28) // 2, 690, step), i, None))
            if f["type"] in ("number", "int", "choice"):
                width = 120 if f["type"] != "choice" else 210
                found += [("dec", pygame.Rect(cx, y, 30, 28), i, None), ("val", pygame.Rect(cx + 34, y, width, 28), i, None),
                          ("inc", pygame.Rect(cx + 38 + width, y, 30, 28), i, None)]
            elif f["type"] == "text":
                found.append(("val", pygame.Rect(cx, y, 300, 28), i, None))
            elif f["type"] == "bool":
                found.append(("toggle", pygame.Rect(cx, y, 28, 28), i, None))
            else:
                for k, color in enumerate(self._options(f, self.vals[f["key"]])):
                    found.append(("swatch", pygame.Rect(cx + k * 30, y, 26, 28), i, color))
        by = box.bottom - 56
        found += [("text", pygame.Rect(px, by, 130, 32), -1, None), ("cancel", pygame.Rect(box.right - 290, by, 130, 32), -1, None),
                  ("ok", pygame.Rect(box.right - 150, by, 130, 32), -1, None)]
        for k, name in enumerate(self.names[self.scroll:self.scroll + self.ROWS]):
            found.append(("name", pygame.Rect(box.x + 12, box.y + 40 + k * 30, 226, 28), -1, name))
        return found

    # ----- entrées
    def _apply(self) -> bool:
        if self.text_mode:
            self.on_text(self.text)
        else:
            self.on_done(self.name, self.value())
        return True

    def _toggle_text(self) -> None:
        if not self.text_mode:
            self.text, self.text_mode = f"{self.name}|{json.dumps(self.value())}", True
            return
        name, _, raw = self.text.partition("|")
        if name.strip() in self.defs:  # retour au visuel seulement si le nom est connu
            try:
                value = json.loads(raw) if raw.strip() else {}
            except ValueError:
                value = {}
            self._load(name.strip(), value)
            self.text_mode = False

    def event(self, event: pygame.event.Event) -> bool:
        """Renvoie True quand le panneau se ferme (validé ou annulé)."""
        fields = self.defs[self.name]["fields"]
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(max(0, len(self.names) - self.ROWS), self.scroll - event.y))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for kind, rect, i, extra in reversed(self._controls()):
                if not rect.collidepoint(event.pos) or (self.text_mode and kind not in ("text", "cancel", "ok")):
                    continue
                if kind == "ok":
                    return self._apply()
                if kind == "cancel":
                    return True
                if kind == "text":
                    self._toggle_text()
                elif kind == "name":
                    self._load(extra, self.value() if extra == self.name else None)
                else:
                    self.focus = i
                    if kind in ("dec", "inc"):
                        self._step(i, 1 if kind == "inc" else -1)
                    elif kind in ("val", "toggle") and fields[i]["type"] in ("choice", "bool"):
                        self._step(i, 1)
                    elif kind == "swatch":
                        self.vals[fields[i]["key"]] = extra
                return False
        elif event.type == pygame.KEYDOWN:
            key = event.key
            if key == pygame.K_ESCAPE:
                return True
            if key == pygame.K_RETURN:
                return self._apply()
            if key == pygame.K_TAB:
                self._toggle_text()
            elif self.text_mode:
                if key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]
                elif event.unicode and event.unicode.isprintable():
                    self.text += event.unicode
            elif key in (pygame.K_UP, pygame.K_DOWN) and fields:
                self.focus = (self.focus + (1 if key == pygame.K_DOWN else -1)) % len(fields)
            elif key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
                self._load(self.names[(self.names.index(self.name) + (1 if key == pygame.K_PAGEDOWN else -1)) % len(self.names)])
            elif key in (pygame.K_LEFT, pygame.K_RIGHT) and fields:
                self._step(self.focus, 1 if key == pygame.K_RIGHT else -1)
            elif fields and fields[self.focus]["type"] in ("number", "int", "text"):
                f = fields[self.focus]
                v = str(self.vals[f["key"]])
                if key == pygame.K_BACKSPACE:
                    self.vals[f["key"]] = v[:-1]
                elif event.unicode and event.unicode.isprintable() and (f["type"] == "text" or event.unicode in "0123456789.,-"):
                    self.vals[f["key"]] = v + event.unicode
            elif fields and fields[self.focus]["type"] == "bool" and key == pygame.K_SPACE:
                self._step(self.focus, 1)
        return False

    # ----- dessin
    def draw(self, app, screen: pygame.Surface) -> None:
        tr, box = app.tr, self.BOX
        screen.blit(app.shade(110), (0, 0))
        window(app, screen, box, tr("Event"))
        px = box.x + 260
        pygame.draw.line(screen, UI_BORDER, (box.x + 250, box.y + 36), (box.x + 250, box.bottom - 12))
        fields = self.defs[self.name]["fields"]
        mouse = pygame.mouse.get_pos()
        font, line, y = app.font(15), "", box.y + 40  # phrase d'aide, coupée à la main
        for word in ([] if self.text_mode else tr(self.defs[self.name]["description"]).split()):
            if font.size(line + " " + word)[0] > 690:
                app.text(screen, line, (px, y), 15, color=UI_MUTED, raw=True)
                line, y = word, y + 20
            else:
                line = (line + " " + word).strip()
        app.text(screen, line, (px, y), 15, color=UI_MUTED, raw=True)
        if self.text_mode:
            app.text(screen, "name|value (JSON)", (px, box.y + 110), 15, color=UI_MUTED, raw=True)
            field = pygame.Rect(px, box.y + 134, 690, 36)
            pygame.draw.rect(screen, WHITE, field)
            pygame.draw.rect(screen, UI_ACCENT, field, 2)
            cursor = "|" if (pygame.time.get_ticks() // 400) % 2 else ""
            app.text(screen, (self.text + cursor)[-68:], (field.x + 8, field.y + 8), 17, color=UI_TEXT, raw=True)
        for kind, rect, i, extra in self._controls():
            hover = rect.collidepoint(mouse)
            if kind == "name":
                if extra == self.name and not self.text_mode:
                    pygame.draw.rect(screen, UI_ACCENT, rect)
                elif hover:
                    pygame.draw.rect(screen, UI_TITLE, rect)
                app.text(screen, extra, (rect.x + 8, rect.y + 5), 16, color=WHITE if extra == self.name and not self.text_mode else UI_TEXT, raw=True)
            elif self.text_mode and kind not in ("text", "cancel", "ok"):
                continue
            elif kind == "row":
                if i == self.focus:
                    pygame.draw.rect(screen, (222, 216, 238), rect)
                app.text(screen, tr(fields[i]["label"]), (rect.x + 6, rect.y + 7), 16, color=UI_TEXT, raw=True)
            elif kind in ("dec", "inc"):
                pygame.draw.rect(screen, UI_TITLE if hover else WHITE, rect)
                pygame.draw.rect(screen, UI_BORDER, rect, 1)
                signs = ("-", "+") if fields[i]["type"] in ("number", "int") else ("<", ">")
                app.text(screen, signs[kind == "inc"], (rect.centerx, rect.y + 4), 18, center=True, color=UI_TEXT, raw=True)
            elif kind == "val":
                f, v = fields[i], self.vals[fields[i]["key"]]
                if f["type"] == "choice":
                    v = next((tr(c[1]) for c in f["choices"] if isinstance(c, tuple) and c[0] == v), v)
                pygame.draw.rect(screen, WHITE, rect)
                pygame.draw.rect(screen, UI_ACCENT if i == self.focus else UI_BORDER, rect, 2 if i == self.focus else 1)
                cursor = "|" if i == self.focus and f["type"] != "choice" and (pygame.time.get_ticks() // 400) % 2 else ""
                app.text(screen, (str(v) + cursor)[-26:], (rect.x + 8, rect.y + 5), 16, color=UI_TEXT, raw=True)
            elif kind == "toggle":
                on = self.vals[fields[i]["key"]]
                pygame.draw.rect(screen, WHITE, rect)
                pygame.draw.rect(screen, UI_ACCENT if i == self.focus else UI_BORDER, rect, 2 if i == self.focus else 1)
                if on:
                    pygame.draw.lines(screen, UI_TEXT, False, [(rect.x + 6, rect.centery), (rect.x + 12, rect.bottom - 8), (rect.right - 6, rect.y + 7)], 3)
                app.text(screen, tr("on") if on else tr("off"), (rect.right + 10, rect.y + 5), 16, color=UI_MUTED, raw=True)
            elif kind == "swatch":
                chosen = self.vals[fields[i]["key"]] == extra
                pygame.draw.rect(screen, tuple(extra), rect)
                pygame.draw.rect(screen, UI_ACCENT if chosen else UI_BORDER, rect, 3 if chosen else 1)
            else:  # boutons
                label = {"text": "Visual" if self.text_mode else "Text", "cancel": "Cancel (Esc)", "ok": "Confirm (Enter)"}[kind]
                pygame.draw.rect(screen, UI_ACCENT if kind == "ok" else UI_TITLE if hover else WHITE, rect)
                pygame.draw.rect(screen, UI_BORDER, rect, 1)
                app.text(screen, tr(label), (rect.centerx, rect.y + 8), 15, center=True, color=WHITE if kind == "ok" else UI_TEXT, raw=True)
        app.text(screen, tr("Up/Down: field    Left/Right: change    PgUp/PgDn: event    Tab: text"), (box.x + 262, box.bottom - 20), 13, color=UI_MUTED, raw=True)


# ------------------------------------------------------------ menu outils ----
class ToolsState(ListMenu):
    TINT = (120, 230, 170)
    ITEMS = (("CHART EDITOR", "Place notes, sustains and events, then test the song."),
             ("STAGE & CAMERA EDITOR", "Move characters and props, set the camera of each character."),
             ("CHARACTER EDITOR", "Fix the offsets of each animation and the camera point."),
             ("HELP", "Pick your problem: the guide opens at the right page."))

    def entries(self) -> list:
        return list(self.ITEMS)

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.move(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.move(1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.app.confirm_sound()
            if self.selected == 0:
                self.app.change(SongPicker(self.app))
            elif self.selected == 1:
                self.app.change(Picker(self.app, "CHOOSE A STAGE", all_ids(self.app, "data/stages"), lambda value: StageEditorState(self.app, value), (150, 190, 255)))
            elif self.selected == 3:
                open_help(self.app, lambda: ToolsState(self.app))
            else:
                self.app.change(Picker(self.app, "CHOOSE A CHARACTER", all_ids(self.app, "data/characters"), lambda value: CharacterEditorState(self.app, value), (255, 170, 200)))
        elif event.key == pygame.K_ESCAPE:
            self.app.cancel_sound(); self.app.change(MainMenuState(self.app, "tools"))

    def draw(self, screen: pygame.Surface) -> None:
        self.background(screen)
        self.draw_rows(screen, [self.app.tr(label) for label, _ in self.ITEMS], x=90, height=58, spacing=110, center_y=330)
        self.title(screen, "TOOLS")
        self.draw_footer(screen, "↑↓ SELECT     ENTER OPEN     ESC BACK", self.app.tr(self.ITEMS[self.selected][1]))


class Picker(ListMenu):
    """Liste de choix simple (scènes, personnages)."""

    def __init__(self, app, title: str, values: list[str], factory, tint=(150, 190, 255)):
        super().__init__(app)
        self.heading, self.values, self.factory, self.TINT = title, values, factory, tint

    def entries(self) -> list:
        return self.values

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.move(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.move(1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and self.values:
            self.app.confirm_sound()
            self.app.loading_screen()
            self.app.change(self.factory(self.values[self.selected]))
        elif event.key == pygame.K_ESCAPE:
            self.app.cancel_sound(); self.app.change(ToolsState(self.app))

    def draw(self, screen: pygame.Surface) -> None:
        self.background(screen)
        self.draw_rows(screen, self.values, x=90, height=46, spacing=70, center_y=330)
        self.title(screen, self.heading)
        self.draw_footer(screen, "↑↓ SELECT     ENTER OPEN     ESC BACK")


class SongPicker(ListMenu):
    TINT = (255, 150, 120)

    def __init__(self, app):
        super().__init__(app)
        self.song_ids = sorted(app.data.songs, key=lambda key: app.data.songs[key].name.lower())
        self.chart_index = 0
        self.prompt: TextPrompt | None = None
        self.new_song: dict = {}

    def entries(self) -> list:
        return ["+"] + self.song_ids

    def charts(self) -> list[str]:
        if self.selected == 0:
            return []
        return sorted(self.app.data.songs[self.song_ids[self.selected - 1]].charts, key=difficulty_sort_key)

    def event(self, event: pygame.event.Event) -> None:
        if self.prompt:
            current = self.prompt
            # Un callback peut ouvrir la question suivante : on ne ferme que si c'est toujours la même.
            if current.event(event) and self.prompt is current:
                self.prompt = None
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.move(-1); self.chart_index = 0
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.move(1); self.chart_index = 0
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT) and self.charts():
            self.chart_index = (self.chart_index + (1 if event.key == pygame.K_RIGHT else -1)) % len(self.charts())
            self.app.scroll_sound()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.selected == 0:
                self.ask_new_song()
            else:
                self.app.loading_screen()
                self.app.change(ChartEditorState(self.app, self.song_ids[self.selected - 1], self.charts()[self.chart_index]))
        elif event.key == pygame.K_ESCAPE:
            self.app.cancel_sound(); self.app.change(ToolsState(self.app))

    # Nouvelle chanson : dossier du mod, id, nom, BPM -> métadonnées + chart vide, puis l'éditeur s'ouvre.
    def ask_new_song(self) -> None:
        folders = [mod for mod in self.app.mods if mod.root.parent == mods_dir() and mod.root.is_dir()]
        default = folders[0].folder if folders else "MyMod"
        self.new_song = {}

        def step_mod(value: str):
            self.new_song.update(mod=value.strip() or default)
            self.prompt = TextPrompt("Song id (lowercase, no space)", "my-song", step_id)

        def step_id(value: str):
            self.new_song.update(id=value.strip().lower().replace(" ", "-") or "my-song")
            self.prompt = TextPrompt("Song name", self.new_song["id"].replace("-", " ").title(), step_name)

        def step_name(value: str):
            self.new_song.update(name=value.strip() or self.new_song["id"])
            self.prompt = TextPrompt("BPM", "120", step_bpm)

        def step_bpm(value: str):
            try:
                bpm = max(20.0, min(400.0, float(value.replace(",", "."))))
            except ValueError:
                bpm = 120.0
            self.prompt = None
            self.create_song(self.new_song["mod"], self.new_song["id"], self.new_song["name"], bpm)

        self.prompt = TextPrompt("Mod folder (in mods/)", default, step_mod)

    def create_song(self, mod_folder: str, song_id: str, name: str, bpm: float) -> None:
        root = mods_dir() / mod_folder
        if not (root / "mod.json").is_file():
            root.mkdir(parents=True, exist_ok=True)
            write_json(root / "mod.json", {"name": mod_folder, "description": "", "author": "", "version": "1.0.0"})
        song_dir = root / "data" / "songs" / song_id
        audio_dir = root / "songs" / song_id
        audio_dir.mkdir(parents=True, exist_ok=True)
        write_json(song_dir / f"{song_id}-metadata.json", {
            "version": "2.2.4", "songName": name, "artist": "", "charter": "",
            "playData": {"difficulties": ["easy", "normal", "hard"], "characters": {
                "player": "bf", "girlfriend": "gf", "opponent": "dad", "playerVocals": ["bf"], "opponentVocals": ["dad"]},
                "stage": "mainStage", "noteStyle": "funkin"},
            "timeChanges": [{"t": 0, "b": 0, "bpm": bpm, "bt": [4, 4, 4, 4]}],
        })
        chart_path = song_dir / f"{song_id}-chart.json"
        if not chart_path.is_file():
            write_json(chart_path, {"version": "2.0.0", "scrollSpeed": {"easy": 1.6, "normal": 1.9, "hard": 2.2},
                                    "events": [], "notes": {"easy": [], "normal": [], "hard": []}})
        if not any(audio_dir.glob("Inst*.ogg")):
            tr = self.app.tr
            self.notify(f"{tr('Put Inst.ogg (and Voices-bf.ogg / Voices-dad.ogg) in')} mods/{mod_folder}/songs/{song_id}/ {tr('then F5')}")
            try:
                import os
                os.startfile(audio_dir)
            except (OSError, AttributeError):
                pass
            return
        self.app.reload_mods()
        song = self.app.data.songs.get(song_id)
        if song:
            self.app.change(ChartEditorState(self.app, song_id, sorted(song.charts, key=difficulty_sort_key)[0]))

    def draw(self, screen: pygame.Surface) -> None:
        self.background(screen)
        labels = [self.app.tr("+ NEW SONG")] + [self.app.data.songs[song].name for song in self.song_ids]
        self.draw_rows(screen, labels, x=90, height=46, spacing=70, center_y=330)
        if self.charts():
            chart = self.charts()[self.chart_index].replace(":", " / ").upper()
            self.app.text(screen, f"< {chart} >", (WIDTH - 40, 330 - 18), 30, right=True, bold=True, color=YELLOW, outline=True, raw=True)
        self.title(screen, "CHOOSE A SONG")
        self.draw_footer(screen, "↑↓ SONG     ←→ DIFFICULTY     ENTER OPEN     ESC BACK")
        if self.prompt:
            self.prompt.draw(self.app, screen)


# ------------------------------------------------------- éditeur de chart ----
def tr_live(app, mode: int, long: bool = True) -> str:
    """Nom du mode de saisie en direct de l'éditeur de chart."""
    name = app.tr(("off", "keys 1-8", "WASD + arrows")[mode])
    return f"{app.tr('Live input')} : {name}" if long else name


class ChartEditorState(BaseState):
    CELL = 46
    GRID_X = 455
    LINE_Y = 250
    GRID_TOP, GRID_BOTTOM = 76, 682
    COLUMNS = 9  # 0 = événements, 1-4 adversaire, 5-8 joueur

    def __init__(self, app, song_id: str, chart_key: str, cursor_ms: float = 0.0):
        super().__init__(app)
        from .game import audio_paths
        self.song = app.data.songs[song_id]
        self.chart_key = chart_key
        self.chart_path, self.difficulty = self.song.charts[chart_key]
        self.chart = app.assets.json(self.chart_path)
        self.variation = self.chart_path.stem.removeprefix(f"{song_id}-chart").removeprefix("-")
        meta_name = f"{song_id}-metadata{'-' + self.variation if self.variation else ''}.json"
        self.meta_path = self.chart_path.with_name(meta_name)
        if not self.meta_path.is_file():
            self.meta_path = self.chart_path.with_name(f"{song_id}-metadata.json")
        self.meta = app.assets.json(self.meta_path) if self.meta_path.is_file() else {"timeChanges": [{"t": 0, "bpm": self.song.bpm}]}
        self.chart.setdefault("notes", {}).setdefault(self.difficulty, [])
        self.chart.setdefault("events", [])
        self.cursor = max(0.0, cursor_ms)
        self.snap_index = SNAPS.index(16)
        self.zoom = 1.0
        self.selected: dict | None = None
        self.dragging = False
        self.undo: list = []
        self.redo: list = []
        self.stretched = False  # note longue étirée pendant le glisser (son « snap » au relâchement)
        self.live = 0  # saisie en direct (L) : 0 aucune, 1 touches 1-8, 2 WASD + flèches (pendant la lecture)
        self.live_held: dict[int, dict] = {}  # touche enfoncée -> note posée (devient longue si on la tient)
        self.prompt_shown = False
        self.selection: list[dict] = []  # sélection multiple (Ctrl+clic, Ctrl+glisser, Ctrl+A)
        self.box = None  # rectangle de sélection en cours
        self.clipboard = {"notes": [], "events": [], "bar": False}
        self.dirty = False
        self.message, self.message_at = "", 0
        self.prompt: TextPrompt | None = None
        self.playing = False
        self.play_start = 0.0
        self.play_started_at = 0
        self.channels: list[pygame.mixer.Channel] = []
        self.metronome = False
        self.hitsounds = True
        self.escape_at = 0
        profile = self.song.profiles.get(chart_key, {})
        inst, voices = audio_paths(app.assets, song_id, self.variation, profile)
        self.sounds = []
        vocals = []  # (fichier, son) de chaque voix chargée
        for path in [inst, *voices[:6]]:
            try:
                self.sounds.append(pygame.mixer.Sound(path))
                if path is not inst:
                    vocals.append((path, self.sounds[-1]))
            except (pygame.error, FileNotFoundError):
                pass
        self.waves = self._waveforms(vocals, profile)
        self.show_wave = True
        self.bar_drag = False  # glisser le rond de la barre de lecture
        self.last_click = (0, None)  # (ms, événement) pour le double-clic
        self.cycled = False
        self._wave_layer: pygame.Surface | None = None
        self.length = max((sound.get_length() * 1000 for sound in self.sounds), default=60000)
        notes = SparrowAtlas(app.assets, app.assets.path("shared/images/notes.png"))
        size = self.CELL - 6
        self.arrows = [fit(notes.animation(f"note{d.title()}")[0], size, size) for d in ("left", "down", "up", "right")]
        self.icon_dad = app.icon_frames(profile.get("opponent", self.song.opponent))
        self.icon_bf = app.icon_frames(profile.get("player", self.song.player))
        pygame.mixer.music.stop()

    WAVE_SLICE = 10  # ms par tranche d'enveloppe

    def _waveforms(self, vocals, profile) -> dict[str, np.ndarray]:
        """Enveloppe (crête par tranche, 0..1) de la voix de chaque côté, calculée une seule fois.

        Un fichier est joueur / adversaire d'après son nom (Voices-bf.ogg) ; sans nom (Voices.ogg) il sert aux deux côtés."""
        rate = (pygame.mixer.get_init() or (44100,))[0]
        step = max(1, rate * self.WAVE_SLICE // 1000)
        sides: dict[str, list[np.ndarray]] = {"player": [], "opponent": []}
        for path, sound in vocals:
            data = np.abs(pygame.sndarray.array(sound).astype(np.int32))
            if data.ndim > 1:
                data = data.mean(axis=1)  # le mixer peut avoir 4 canaux
            count = len(data) // step
            env = data[:count * step].reshape(count, step).max(axis=1).astype(np.float32)
            token = path.stem.removeprefix("Voices").removeprefix("-")
            token = token.removesuffix(f"-{self.variation}") if self.variation else token
            ids = {key: [str(v) for v in profile.get(f"{key}_vocals", [])] for key in sides}
            for key in sides:
                if not token or any(v == token or v.startswith(token) for v in ids[key]):
                    sides[key].append(env)
        waves = {}
        for key, items in sides.items():
            if items:
                env = np.zeros(max(map(len, items)), np.float32)
                for item in items:
                    env[:len(item)] = np.maximum(env[:len(item)], item)
                waves[key] = env / max(float(np.percentile(env, 99.5)), 1e-6)
        return waves

    def _draw_waves(self, screen: pygame.Surface, left: int) -> None:
        """Forme d'onde des voix derrière les colonnes (une ligne par rangée de pixels)."""
        top, height = self.GRID_TOP, self.GRID_BOTTOM - self.GRID_TOP
        width = self.CELL * 4
        if self._wave_layer is None:
            self._wave_layer = pygame.Surface((width, height), pygame.SRCALPHA)
        layer = self._wave_layer
        times = self.time_at(np.arange(top, top + height)) / self.WAVE_SLICE
        for key, column, color in (("opponent", 1, (110, 70, 150, 120)), ("player", 5, (40, 110, 140, 120))):
            env = self.waves.get(key)
            if env is None:
                continue
            layer.fill((0, 0, 0, 0))
            amp = np.clip(np.interp(times, np.arange(len(env)) + .5, env, left=0, right=0), 0, 1) * (width / 2 - 3)
            for row in np.nonzero(amp >= 1)[0].tolist():
                half = int(amp[row])
                pygame.draw.line(layer, color, (width // 2 - half, row), (width // 2 + half, row))
            screen.blit(layer, (left + column * self.CELL, top))

    # ----- temps
    @property
    def bpm(self) -> float:
        changes = self.meta.get("timeChanges") or [{}]
        return float(changes[0].get("bpm", self.song.bpm) or 120)

    @property
    def beat_ms(self) -> float:
        return 60000 / self.bpm

    @property
    def snap_ms(self) -> float:
        return self.beat_ms * 4 / SNAPS[self.snap_index]

    @property
    def px_per_ms(self) -> float:
        return self.CELL * self.zoom / (self.beat_ms / 4)

    def notes(self) -> list[dict]:
        return self.chart["notes"].setdefault(self.difficulty, [])

    def time_at(self, y: float) -> float:
        return self.cursor + (y - self.LINE_Y) / self.px_per_ms

    def y_at(self, time_ms: float) -> float:
        return self.LINE_Y + (time_ms - self.cursor) * self.px_per_ms

    def snapped(self, time_ms: float) -> float:
        return max(0.0, round(time_ms / self.snap_ms) * self.snap_ms)

    def cell_at(self, y: float) -> float:
        """Temps de la case sous la souris : une note occupe la case qui commence à son temps (comme FNF)."""
        return max(0.0, math.floor(self.time_at(y) / self.snap_ms + 1e-6) * self.snap_ms)

    @property
    def half_cell(self) -> float:
        return self.CELL * self.zoom / 2

    def column_at(self, x: int) -> int | None:
        column = (x - self.GRID_X) // self.CELL
        return column if 0 <= column < self.COLUMNS else None

    @staticmethod
    def column_of(note: dict) -> int:
        direction = int(note.get("d", 0)) % 8
        return 1 + (direction - 4) if direction >= 4 else 5 + direction

    @staticmethod
    def direction_of(column: int) -> int:
        return 4 + (column - 1) if column <= 4 else column - 5

    # ----- édition
    def remember(self) -> None:
        self.undo.append(self._snapshot())
        self.undo = self.undo[-80:]
        self.redo = []
        self.dirty = True

    def notify(self, text: str) -> None:
        self.message, self.message_at = text, pygame.time.get_ticks()

    def item_at(self, column: int, time_ms: float) -> dict | None:
        tolerance = max(4.0, self.snap_ms / 3)
        if column == 0:
            return next((event for event in self.chart["events"] if abs(float(event.get("t", 0)) - time_ms) < tolerance), None)
        direction = self.direction_of(column)
        return next((note for note in self.notes() if int(note.get("d", 0)) % 8 == direction and abs(float(note.get("t", 0)) - time_ms) < tolerance), None)

    def save(self) -> Path:
        relative_dir = f"data/songs/{self.song.song_id}"
        target = save_target(self.app, self.chart_path, f"{relative_dir}/{self.chart_path.name}")
        if target != self.chart_path:
            # Copie des autres fichiers de la chanson (métadonnées, autres variations) dans le mod de sauvegarde.
            for source in self.chart_path.parent.glob("*.json"):
                copy_to = target.parent / source.name
                if not copy_to.exists():
                    shutil.copy2(source, copy_to)
        self.notes().sort(key=lambda note: float(note.get("t", 0)))
        self.chart["events"].sort(key=lambda event: float(event.get("t", 0)))
        write_json(target, self.chart)
        meta_target = target.parent / self.meta_path.name
        write_json(meta_target, self.meta)
        self.chart_path, self.meta_path = target, meta_target
        self.dirty = False
        self.app.reload_mods()
        self.app.unlock("charter")
        self.notify(f"{self.app.tr('SAVED')} : {target}")
        return target

    def test(self) -> None:
        from .game import PlayState
        self.stop()
        self.save()
        self.app.editor_return = self
        self.app.loading_screen()
        if self.song.song_id in self.app.data.songs:
            self.app.change(PlayState(self.app, self.song.song_id, self.chart_key, start_ms=self.cursor, intro=False))

    # ----- audio
    def play(self) -> None:
        from .game import slice_sound
        self.channels = []
        for index, sound in enumerate(self.sounds):
            channel = pygame.mixer.Channel(index)
            channel.set_volume(self.app.volume)
            channel.play(slice_sound(sound, self.cursor))
            self.channels.append(channel)
        self.play_start, self.play_started_at, self.playing = self.cursor, pygame.time.get_ticks(), True

    def stop(self) -> None:
        for channel in self.channels:
            channel.stop()
        self.channels, self.playing = [], False
        self.cursor = self.snapped(self.cursor) if not self.playing else self.cursor

    # ----- entrées
    def event(self, event: pygame.event.Event) -> None:
        # Petits sons d'interface comme l'éditeur V-Slice (clics, frappe au clavier).
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and event.button in (1, 3):
            self.app.play_sound(f"sounds/chartingSounds/Click{'Down' if event.type == pygame.MOUSEBUTTONDOWN else 'Up'}.ogg", .4)
        if self.prompt:
            if event.type == pygame.KEYDOWN and event.unicode and event.unicode.isprintable():
                self.app.play_sound(f"sounds/chartingSounds/keyboard{random.randint(1, 3)}.ogg", .4)
            current = self.prompt
            if current.event(event) and self.prompt is current:
                self.prompt = None
            return
        ctrl = pygame.key.get_mods() & pygame.KMOD_CTRL
        shift = pygame.key.get_mods() & pygame.KMOD_SHIFT
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and event.pos[1] >= 686:
            bar = self._bar_rect()
            if bar.x - 12 <= event.pos[0] <= bar.right + 12:
                self.stop()
                self.bar_drag = True
                self._seek(event.pos[0])
            return
        if event.type == pygame.MOUSEMOTION and self.bar_drag:
            self._seek(event.pos[0])
            return
        if event.type == pygame.MOUSEBUTTONUP and self.bar_drag:
            self.bar_drag = False
            return
        if event.type == pygame.MOUSEWHEEL:
            if ctrl:
                self.zoom = max(.25, min(4.0, self.zoom * (1.15 if event.y > 0 else 1 / 1.15)))
            else:
                self.stop()
                self.cursor = max(0.0, self.snapped(self.cursor) - event.y * self.snap_ms * (4 if shift else 1))
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            column = self.column_at(event.pos[0])
            if column is None:
                return
            time_ms = self.cell_at(event.pos[1])
            found = self.item_at(column, time_ms)
            if event.button == 1 and ctrl:  # Ctrl+clic : ajouter / retirer ; Ctrl+glisser : rectangle de sélection
                if found:
                    self._toggle(found)
                else:
                    self.box = [event.pos, event.pos]
                return
            if event.button == 3:
                if found:
                    self.remember()
                    (self.chart["events"] if column == 0 else self.notes()).remove(found)
                    self.app.play_sound("sounds/chartingSounds/noteErase.ogg", .6)
                    if found is self.selected:
                        self.selected = None
                    self.selection = [item for item in self.selection if item is not found]
                return
            if found:
                now = pygame.time.get_ticks()
                if column == 0 and event.button == 1 and found is self.last_click[1] and now - self.last_click[0] < 400:
                    self.last_click = (0, None)
                    if self.undo and self.cycled:  # le premier clic avait changé BF/OP/GF : on l'annule
                        self._restore(self.undo.pop())
                        found = self.item_at(0, time_ms) or found
                    self.selected, self.selection = found, [found]
                    self._open_event_panel()
                    return
                self.cycled = False
                if column == 0:
                    self.last_click = (now, found)
                if column == 0 and found.get("e") == "FocusCamera" and found is self.selected:
                    self.cycled = True
                    self.remember()
                    value = found.get("v") if isinstance(found.get("v"), dict) else {"char": found.get("v", 0)}
                    value["char"] = (int(float(value.get("char", 0))) + 1) % 3
                    found["v"] = value
                self.selected, self.dragging = found, column != 0
                self.selection = [found]
                return
            self.remember()
            if column == 0:
                item = {"t": round(time_ms, 3), "e": "FocusCamera", "v": {"char": 1}}
                self.chart["events"].append(item)
            else:
                item = {"t": round(time_ms, 3), "d": self.direction_of(column), "l": 0}
                self.notes().append(item)
                self.dragging = True
            self.selected, self.selection = item, [item]
            self.app.play_sound("sounds/chartingSounds/noteLay.ogg", .6)
            return
        if event.type == pygame.MOUSEBUTTONUP:
            if self.dragging and self.stretched:
                self.app.play_sound("sounds/chartingSounds/stretchSNAP_UI.ogg", .5)
            self.dragging = self.stretched = False
            if self.box:
                self._box_select()
                self.box = None
            return
        if event.type == pygame.MOUSEMOTION and self.box:
            self.box[1] = event.pos
            return
        if event.type == pygame.MOUSEMOTION and self.dragging and self.selected and "d" in self.selected:
            end = self.cell_at(event.pos[1])  # la note longue va jusqu'au bout de la case sous la souris (comme Psych)
            length = max(0.0, end - float(self.selected["t"]))
            length = round(length, 3) if length >= self.snap_ms else 0
            if length != self.selected.get("l", 0):  # un cran de plus ou de moins : petit son d'étirement
                self.stretched = True
                self.app.play_sound(f"sounds/chartingSounds/stretch{1 + (length > float(self.selected.get('l', 0) or 0))}_UI.ogg", .5)
            self.selected["l"] = length
            self.dirty = True
            return
        if event.type == pygame.KEYUP and event.key in self.live_held:
            note = self.live_held.pop(event.key)
            length = self.snapped(self.cursor) - float(note["t"])
            if self.playing and length >= self.snap_ms * 2:  # touche tenue : note longue
                note["l"] = round(length, 3)
            return
        if event.type != pygame.KEYDOWN:
            return
        key = event.key
        column = self._live_column(key) if not ctrl else None
        if column:
            time_ms = round(self.snapped(self.cursor), 3)
            note = self.item_at(column, time_ms)
            if note is None:
                self.remember()
                note = {"t": time_ms, "d": self.direction_of(column), "l": 0}
                self.notes().append(note)
                self.app.play_sound("sounds/chartingSounds/noteLay.ogg", .6)
            self.live_held[key] = note
            return
        if key == pygame.K_F1:
            self.stop()
            open_help(self.app, self)
        elif key == pygame.K_l:
            self.live = (self.live + 1) % 3
            self.notify(f"{tr_live(self.app, self.live)}")
        elif key == pygame.K_SPACE:
            self.stop() if self.playing else self.play()
        elif key in (pygame.K_UP, pygame.K_DOWN) and ctrl:
            self._move(time_ms=self.snap_ms * (4 if shift else 1) * (1 if key == pygame.K_DOWN else -1))
        elif key in (pygame.K_LEFT, pygame.K_RIGHT) and ctrl:
            self._move(lanes=1 if key == pygame.K_RIGHT else -1)
        elif key == pygame.K_f and ctrl:
            self._move(mirror=True)
        elif key == pygame.K_a and ctrl:
            self.selection = self.notes() + self.chart["events"]
            self.selected = self.selection[0] if self.selection else None
        elif key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s) and not (key == pygame.K_s and ctrl):  # Ctrl+S = enregistrer
            self.stop()
            step = self.snap_ms * (4 if shift else 1)
            self.cursor = max(0.0, self.snapped(self.cursor) + (step if key in (pygame.K_DOWN, pygame.K_s) else -step))
        elif key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.stop()
            self.cursor = max(0.0, self.snapped(self.cursor) + self.beat_ms * 4 * (1 if key == pygame.K_PAGEDOWN else -1))
        elif key == pygame.K_HOME:
            self.stop(); self.cursor = 0.0
        elif key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.snap_index = max(0, min(len(SNAPS) - 1, self.snap_index + (1 if key == pygame.K_RIGHT else -1)))
        elif key in (pygame.K_q, pygame.K_e) and self.selected and "d" in self.selected:
            self.remember()
            self.selected["l"] = max(0.0, round(float(self.selected.get("l", 0)) + self.snap_ms * (1 if key == pygame.K_e else -1), 3))
        elif key in (pygame.K_DELETE, pygame.K_BACKSPACE) and (self.selection or self.selected):
            self._delete(self.selection or [self.selected])
        elif key == pygame.K_k and self.selected and "d" in self.selected:
            self.prompt = TextPrompt("Note kind (empty = normal)", str(self.selected.get("k", "")), self._set_kind)
        elif key in (pygame.K_c, pygame.K_x, pygame.K_v, pygame.K_d) and ctrl:
            self._clip_key(key, shift)
        elif key == pygame.K_v:
            self._open_event_panel()
        elif key == pygame.K_b:
            self.prompt = TextPrompt("BPM", f"{self.bpm:g}", self._set_bpm)
        elif key == pygame.K_n:
            speeds = self.chart.setdefault("scrollSpeed", {})
            self.prompt = TextPrompt(f"{self.app.tr('Scroll speed')} ({self.difficulty})", str(speeds.get(self.difficulty, 1.8)), self._set_speed)
        elif key == pygame.K_TAB:
            keys = sorted({*self.chart["notes"].keys(), "easy", "normal", "hard"}, key=lambda name: difficulty_sort_key(name))
            self.difficulty = keys[(keys.index(self.difficulty) + 1) % len(keys)] if self.difficulty in keys else keys[0]
            self.chart_key = f"{self.difficulty}:{self.variation}" if self.variation else self.difficulty
            self.selected, self.selection = None, []
        elif key == pygame.K_m:
            self.metronome = not self.metronome
        elif key == pygame.K_h:
            self.hitsounds = not self.hitsounds
        elif key == pygame.K_o:
            self.show_wave = not self.show_wave
        elif key == pygame.K_z and ctrl and self.undo:
            self.redo.append(self._snapshot())
            self._restore(self.undo.pop())
            self.app.play_sound("sounds/chartingSounds/undo.ogg", .6)
        elif key == pygame.K_y and ctrl and self.redo:
            self.undo.append(self._snapshot())
            self._restore(self.redo.pop())
            self.app.play_sound("sounds/chartingSounds/undo.ogg", .6)
        elif key == pygame.K_s and ctrl:
            self.save()
        elif key == pygame.K_RETURN:
            self.test()
        elif key == pygame.K_ESCAPE and len(self.selection) > 1:  # d'abord vider la sélection multiple
            self.selection, self.selected = [], None
        elif key == pygame.K_ESCAPE:
            now = pygame.time.get_ticks()
            if self.dirty and now - self.escape_at > 2000:
                self.escape_at = now
                self.notify(self.app.tr("UNSAVED CHANGES - ESC AGAIN TO QUIT"))
                return
            self.stop()
            self.app.play_menu_music()
            self.app.change(SongPicker(self.app))

    def _live_column(self, key: int) -> int | None:
        """Saisie en direct comme V-Slice : touches 1-8 = colonnes de gauche à droite (1-4 adversaire, 5-8 joueur) ;
        WASD = adversaire et flèches = joueur, seulement pendant la lecture (sinon W/S et flèches gardent leur rôle)."""
        if self.live == 1 and pygame.K_1 <= key <= pygame.K_8:
            return key - pygame.K_1 + 1
        if self.live == 2 and self.playing:
            return {pygame.K_a: 1, pygame.K_s: 2, pygame.K_w: 3, pygame.K_d: 4,
                    pygame.K_LEFT: 5, pygame.K_DOWN: 6, pygame.K_UP: 7, pygame.K_RIGHT: 8}.get(key)
        return None

    def _snapshot(self):
        return copy.deepcopy((self.chart["notes"].get(self.difficulty, []), self.chart["events"]))

    def _restore(self, state) -> None:
        self.chart["notes"][self.difficulty], self.chart["events"] = state
        self.selected, self.selection, self.dirty = None, [], True

    def _toggle(self, item: dict) -> None:
        if any(item is other for other in self.selection):
            self.selection = [other for other in self.selection if other is not item]
        else:
            self.selection.append(item)
        self.selected = self.selection[-1] if self.selection else None

    def _box_select(self) -> None:
        (x1, y1), (x2, y2) = self.box
        rect = pygame.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1) + 1, abs(y2 - y1) + 1)
        centre = lambda item, column: (self.GRID_X + column * self.CELL + self.CELL // 2, self.y_at(float(item.get("t", 0))) + self.half_cell)
        self.selection = [note for note in self.notes() if rect.collidepoint(centre(note, self.column_of(note)))]
        self.selection += [event for event in self.chart["events"] if rect.collidepoint(centre(event, 0))]
        self.selected = self.selection[0] if self.selection else None

    def _delete(self, items: list) -> None:
        self.remember()
        gone = {id(item) for item in items}
        self.chart["notes"][self.difficulty] = [note for note in self.notes() if id(note) not in gone]
        self.chart["events"] = [event for event in self.chart["events"] if id(event) not in gone]
        self.selection, self.selected = [], None
        self.app.play_sound("sounds/chartingSounds/noteErase.ogg", .6)

    def _move(self, time_ms: float = 0.0, lanes: int = 0, mirror: bool = False) -> None:
        """Ctrl+flèches : décaler la sélection d'un cran (haut/bas) ou d'une colonne (gauche/droite) ; Ctrl+F : miroir."""
        if not self.selection:
            return
        self.remember()
        for item in self.selection:
            item["t"] = round(max(0.0, float(item.get("t", 0)) + time_ms), 3)
            if "d" in item and (lanes or mirror):
                direction = int(item.get("d", 0))
                lane = direction % 4
                item["d"] = direction - lane + (3 - lane if mirror else (lane + lanes) % 4)

    def _clip_key(self, key: int, shift: int) -> None:
        """Ctrl+C / X / V : copier / couper / coller la sélection (rien de sélectionné : la mesure de la ligne rouge) ;
        Ctrl+D : la sélection (ou les notes de l'adversaire de la mesure) recopiée de l'autre côté, Maj : du joueur vers
        l'adversaire. On ajoute sans doublons ; Ctrl+Z annule."""
        tr, bar = self.app.tr, self.beat_ms * 4
        start = math.floor(self.cursor / bar + 1e-6) * bar
        inside = lambda item: start - 1e-3 <= float(item.get("t", 0)) < start + bar - 1e-3
        if key in (pygame.K_c, pygame.K_x):
            items = list(self.selection) or [item for item in self.notes() + self.chart["events"] if inside(item)]
            anchor = min((float(item.get("t", 0)) for item in items), default=0.0) if self.selection else start
            self.clipboard = {"bar": not self.selection, **{name: [dict(copy.deepcopy(item), t=float(item.get("t", 0)) - anchor)
                              for item in items if field in item] for name, field in (("notes", "d"), ("events", "e"))}}
            label = ("Cut" if key == pygame.K_x else "Copied") + ("" if self.selection or key == pygame.K_x else " (bar)")
            if key == pygame.K_x and items:
                self._delete(items)
            self.notify(f"{tr(label)} : {len(items)}")
            return
        if key == pygame.K_v:
            if not (self.clipboard["notes"] or self.clipboard["events"]):
                self.notify(tr("Nothing to paste")); return
            anchor = start if self.clipboard["bar"] else self.snapped(self.cursor)
            notes, events = self.clipboard["notes"], self.clipboard["events"]
        else:
            source = [item for item in self.selection if "d" in item] or [
                note for note in self.notes() if inside(note) and (int(note.get("d", 0)) % 8 >= 4) == (not shift)]
            anchor, events = 0.0, []
            notes = [dict(copy.deepcopy(note), d=(int(note.get("d", 0)) % 8) ^ 4, t=float(note.get("t", 0))) for note in source]
        self.remember()
        added = []
        for target, items, ident in ((self.notes(), notes, lambda n: (int(n.get("d", 0)) % 8, round(float(n["t"])))),
                                     (self.chart["events"], events, lambda e: (e.get("e"), round(float(e["t"])), json.dumps(e.get("v"))))):
            have = {ident(item) for item in target}
            for item in items:
                new = dict(copy.deepcopy(item), t=round(item["t"] + anchor, 3))
                if ident(new) not in have:
                    target.append(new); have.add(ident(new)); added.append(new)
        self.selection, self.selected = added, (added[0] if added else None)
        message = "Pasted" if key == pygame.K_v else "Copied to the other side"
        self.notify(f"{tr(message)} : +{len(added)}")
        self.app.play_sound("sounds/chartingSounds/noteLay.ogg", .6)

    def _set_kind(self, value: str) -> None:
        self.remember()
        if value.strip():
            self.selected["k"] = value.strip()
        else:
            self.selected.pop("k", None)

    def _open_event_panel(self) -> None:
        """V ou double-clic : crée un événement à la ligne rouge, ou modifie l'événement sélectionné."""
        current = self.selected if self.selected and "e" in self.selected else None
        self.prompt = EventPanel(self.app, event_definitions(self.app), current, self._apply_event, self._set_event)

    def _set_event(self, text: str) -> None:
        """Onglet texte du panneau : « nom|valeur JSON »."""
        name, _, raw_value = text.partition("|")
        try:
            value = json.loads(raw_value) if raw_value.strip() else {}
        except ValueError:
            value = raw_value.strip()
        self._apply_event(name.strip(), value)

    def _apply_event(self, name: str, value) -> None:
        self.remember()
        if self.selected and "e" in self.selected:
            self.selected.update(e=name, v=value)
        else:
            item = {"t": round(self.snapped(self.cursor), 3), "e": name, "v": value}
            self.chart["events"].append(item)
            self.selected, self.selection = item, [item]

    def _bar_rect(self) -> pygame.Rect:
        left = 150 if self.app.settings.language != "fr" else 205  # le libellé français est plus long
        return pygame.Rect(left, 699, 1100 - left, 8)

    def _seek(self, x: int) -> None:
        bar = self._bar_rect()
        self.cursor = max(0.0, min(1.0, (x - bar.x) / bar.width)) * self.length

    def _set_bpm(self, value: str) -> None:
        try:
            bpm = max(20.0, min(400.0, float(value.replace(",", "."))))
        except ValueError:
            return
        changes = self.meta.setdefault("timeChanges", [{"t": 0, "b": 0, "bt": [4, 4, 4, 4]}])
        changes[0]["bpm"] = bpm
        self.dirty = True

    def _set_speed(self, value: str) -> None:
        try:
            self.chart.setdefault("scrollSpeed", {})[self.difficulty] = round(max(.5, min(6.0, float(value.replace(",", ".")))), 2)
            self.dirty = True
        except ValueError:
            pass

    # ----- boucle
    def update(self, dt: float) -> None:
        if (self.prompt is not None) != self.prompt_shown:  # fenêtre ouverte / fermée
            self.prompt_shown = self.prompt is not None
            self.app.play_sound(f"sounds/chartingSounds/{'openWindow' if self.prompt_shown else 'exitWindow'}.ogg", .5)
        if not self.playing:
            return
        previous = self.cursor
        self.cursor = self.play_start + pygame.time.get_ticks() - self.play_started_at
        if self.cursor >= self.length:
            self.stop(); return
        if self.hitsounds:
            for note in self.notes():
                if previous < float(note.get("t", 0)) <= self.cursor:
                    player = int(note.get("d", 0)) % 8 < 4
                    self.app.play_sound(f"sounds/chartingSounds/hitNote{'Player' if player else 'Opponent'}.ogg", 1.0)  # à .5 la musique les couvrait
        beat = math.floor(self.cursor / self.beat_ms)
        if self.metronome and math.floor(previous / self.beat_ms) != beat:  # son grave en début de mesure
            self.app.play_sound(f"sounds/chartingSounds/metronome{1 if beat % 4 == 0 else 2}.ogg", .5)

    def draw(self, screen: pygame.Surface) -> None:
        screen.blit(self.app.menu_bg((92, 84, 110)), (0, 0))
        left = self.GRID_X
        width = self.CELL * self.COLUMNS
        grid = pygame.Rect(left, self.GRID_TOP, width, self.GRID_BOTTOM - self.GRID_TOP)
        screen.set_clip(grid)
        step = self.beat_ms / 4
        first = max(0, math.floor(self.time_at(self.GRID_TOP) / step))
        index = first
        # Damier façon chart editor de FNF : une ligne par double-croche, temps et mesures soulignés.
        while index * step <= self.time_at(self.GRID_BOTTOM):
            y = self.y_at(index * step)
            height = step * self.px_per_ms + 1
            for column in range(self.COLUMNS):
                color = CHECKER[(index + column) % 2]
                if column == 0:
                    color = tuple(max(0, c - 22) for c in color)
                pygame.draw.rect(screen, color, (left + column * self.CELL, y, self.CELL, height))
            if index % 4 == 0:
                pygame.draw.line(screen, (60, 60, 66) if index % 16 == 0 else (150, 146, 150), (left, y), (left + width, y), 2 if index % 16 == 0 else 1)
            index += 1
        song_end = self.y_at(self.length)
        if song_end < self.GRID_BOTTOM:
            pygame.draw.rect(screen, (70, 66, 76), (left, song_end, width, self.GRID_BOTTOM - song_end))
        for column in (1, 5):
            x = left + column * self.CELL
            pygame.draw.line(screen, (50, 50, 56), (x, self.GRID_TOP), (x, self.GRID_BOTTOM), 3)
        if self.show_wave and self.waves:
            self._draw_waves(screen, left)
        picked = {id(item) for item in self.selection} | ({id(self.selected)} if self.selected else set())
        # Événements : petite pastille sombre avec la cible de la caméra.
        for event in self.chart["events"]:
            y = self.y_at(float(event.get("t", 0)))
            if self.GRID_TOP - 20 < y < self.GRID_BOTTOM + 20:
                box = pygame.Rect(0, 0, 32, 32); box.center = (left + self.CELL // 2, round(y + self.half_cell))
                pygame.draw.rect(screen, (52, 52, 60), box, border_radius=6)
                chosen = id(event) in picked
                pygame.draw.rect(screen, UI_ACCENT if chosen else (20, 20, 24), box, 3 if chosen else 1, border_radius=6)
                value = event.get("v")
                if event.get("e") == "FocusCamera":
                    char = value.get("char", 0) if isinstance(value, dict) else value
                    label = {0: "BF", 1: "OP", 2: "GF"}.get(int(float(char or 0)), "?")
                else:
                    label = "EV"
                self.app.text(screen, label, (box.centerx, box.y + 8), 13, center=True, bold=True, color=WHITE, raw=True)
        # Notes et notes longues.
        for note in self.notes():
            start = float(note.get("t", 0))
            length = float(note.get("l", 0) or 0)
            y = self.y_at(start)
            if y > self.GRID_BOTTOM + 30 or self.y_at(start + length) < self.GRID_TOP - 30:
                continue
            lane = int(note.get("d", 0)) % 4
            cx = left + self.column_of(note) * self.CELL + self.CELL // 2
            y += self.half_cell  # centre de la case de la note
            if length > 0:
                tail = pygame.Rect(cx - 7, round(y), 14, round(length * self.px_per_ms + self.half_cell))  # finit au bout d'une case
                pygame.draw.rect(screen, LANE_COLORS[lane], tail)
                pygame.draw.rect(screen, (30, 30, 36), tail, 2)
            arrow = self.arrows[lane]
            rect = arrow.get_rect(center=(cx, round(y)))
            screen.blit(arrow, rect)
            if note.get("k"):
                pygame.draw.circle(screen, (255, 210, 60), (rect.right - 4, rect.y + 4), 6)
                pygame.draw.circle(screen, (30, 30, 36), (rect.right - 4, rect.y + 4), 6, 1)
            if id(note) in picked:
                pygame.draw.rect(screen, UI_ACCENT, rect.inflate(6, 6), 3)
        if self.box:
            (x1, y1), (x2, y2) = self.box
            area = pygame.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
            layer = pygame.Surface(area.size, pygame.SRCALPHA); layer.fill((146, 90, 230, 60))
            screen.blit(layer, area); pygame.draw.rect(screen, UI_ACCENT, area, 2)
        mouse = pygame.mouse.get_pos()
        column = self.column_at(mouse[0])
        if column is not None and not self.prompt and grid.collidepoint(mouse):
            y = self.y_at(self.cell_at(mouse[1]))
            hover = pygame.Surface((self.CELL, max(4, round(self.snap_ms * self.px_per_ms))), pygame.SRCALPHA); hover.fill((146, 90, 230, 70))
            screen.blit(hover, (left + column * self.CELL, round(y)))
        screen.set_clip(None)
        pygame.draw.rect(screen, (50, 50, 56), grid, 2)
        # Tête de lecture.
        pygame.draw.line(screen, (230, 60, 90), (left - 18, self.LINE_Y), (left + width + 18, self.LINE_Y), 3)
        pygame.draw.polygon(screen, (230, 60, 90), [(left - 18, self.LINE_Y - 8), (left - 4, self.LINE_Y), (left - 18, self.LINE_Y + 8)])
        # En-tête des colonnes : événements, adversaire, joueur.
        header = pygame.Rect(left, 36, width, 38)
        pygame.draw.rect(screen, UI_TITLE, header)
        pygame.draw.rect(screen, UI_BORDER, header, 1)
        self.app.text(screen, "EV", (left + self.CELL // 2, 46), 14, center=True, bold=True, color=UI_TEXT, raw=True)
        for frames_list, x in ((self.icon_dad, left + self.CELL * 3), (self.icon_bf, left + self.CELL * 7)):
            if frames_list:
                icon = pygame.transform.smoothscale(frames_list[0], (40, 40))
                screen.blit(icon, icon.get_rect(center=(x, 55)))
        for column in range(self.COLUMNS + 1):
            x = left + column * self.CELL
            if column in (1, 5):
                pygame.draw.line(screen, (50, 50, 56), (x, 36), (x, 74), 3)
        self._draw_panel(screen)
        if self.prompt:
            self.prompt.draw(self.app, screen)

    def _draw_panel(self, screen: pygame.Surface) -> None:
        tr = self.app.tr
        toolbar(self.app, screen, f"{tr('Chart Editor')}  —  {self.song.name}", tr("F1 help    Ctrl+S save    Enter test    Esc quit"))
        speed = self.chart.get("scrollSpeed", {}).get(self.difficulty, "?")
        y = window(self.app, screen, pygame.Rect(16, 44, 416, 190), tr("Song"))
        rows(self.app, screen, 30, y, [
            (tr("Song"), self.song.name), (tr("Difficulty"), self.difficulty + (f"  ({self.variation})" if self.variation else "")),
            ("BPM", f"{self.bpm:g}   (B)"), (tr("Scroll speed"), f"{speed}   (N)"),
            (tr("Notes"), len(self.notes())), (tr("Events"), len(self.chart["events"])),
        ])
        y = window(self.app, screen, pygame.Rect(16, 248, 416, 194), tr("Editing"))
        rows(self.app, screen, 30, y, [
            (tr("Snap"), f"1/{SNAPS[self.snap_index]}   ({tr('Left/Right')})"), (tr("Zoom"), f"{self.zoom:.2f}x   ({tr('Ctrl+wheel')})"),
            (tr("Metronome"), f"{tr('on') if self.metronome else tr('off')} (M)"), (tr("Hitsounds"), f"{tr('on') if self.hitsounds else tr('off')} (H)"),
            (tr("Waveform"), f"{tr('on') if self.show_wave else tr('off')} (O)"), (tr("Live input"), f"{tr_live(self.app, self.live, False)} (L)"),
            (tr("File"), tr("unsaved changes") if self.dirty else tr("saved")),
        ])
        y = window(self.app, screen, pygame.Rect(16, 456, 416, 126), tr("Selection"))
        if len(self.selection) > 1:
            rows(self.app, screen, 30, y, [(tr("Selected"), len(self.selection)), tr("Ctrl+arrows: move    Ctrl+F: mirror"),
                                           tr("Ctrl+C / X / V    Del: delete")])
        elif self.selected:
            if "e" in self.selected:
                lines = [(tr("Event"), self.selected.get("e")), (tr("Time"), f"{float(self.selected.get('t', 0)):.1f} ms"),
                         (tr("Value"), json.dumps(self.selected.get("v"))[:30])]
            else:
                side = tr("player") if int(self.selected.get("d", 0)) % 8 < 4 else tr("opponent")
                lines = [(tr("Note"), f"{tr(('left', 'down', 'up', 'right')[int(self.selected.get('d', 0)) % 4])} ({side})"),
                         (tr("Time"), f"{float(self.selected.get('t', 0)):.1f} ms"),
                         (tr("Sustain"), f"{float(self.selected.get('l', 0) or 0):.0f} ms"), (tr("Kind"), self.selected.get("k", "-") + "   (K)")]
            rows(self.app, screen, 30, y, lines)
        else:
            rows(self.app, screen, 30, y, [tr("Click a note or an event to select it.")])
        y = window(self.app, screen, pygame.Rect(906, 44, 358, 518), tr("Controls"))
        rows(self.app, screen, 920, y, [tr(line) for line in (
            "Left click: place / select", "Drag down: sustain    Q / E: -/+", "Right click: delete", "Event column: FocusCamera",
            "   click again: BF / OP / GF", "V / double-click: event editor", "Wheel or W / S: move", "PgUp / PgDn: one bar",
            "Space: play / pause", "Tab: next difficulty", "Ctrl+Z / Ctrl+Y: undo / redo", "Ctrl+click / Ctrl+drag: select",
            "Ctrl+A: select all    Del: delete", "Ctrl+C / X / V: copy / cut / paste", "   nothing selected: the whole bar",
            "Ctrl+D: opponent -> player (Shift: reverse)", "Ctrl+arrows: move    Ctrl+F: mirror", "O: show / hide the voice waveform",
            "L: live input (keys 1-8 / WASD + arrows)")], size=15, gap=24)
        # Barre de lecture.
        pygame.draw.rect(screen, (44, 44, 50), (0, 686, WIDTH, 34))
        bar = self._bar_rect()
        left_bar = bar.x
        pygame.draw.rect(screen, (90, 90, 100), bar)
        progress = min(1.0, self.cursor / max(1.0, self.length))
        pygame.draw.rect(screen, UI_ACCENT, (bar.x, bar.y, round(bar.width * progress), bar.height))
        mouse = pygame.mouse.get_pos()
        near = self.bar_drag or (686 <= mouse[1] and bar.x - 12 <= mouse[0] <= bar.right + 12)
        pygame.draw.circle(screen, WHITE, (bar.x + round(bar.width * progress), bar.centery), 11 if near else 8)
        state = "PAUSE" if self.playing else "PLAY"
        self.app.text(screen, f"{self.app.tr(state)}  ({self.app.tr('Space')})", (16, 693), 16, color=WHITE, bold=True, raw=True)
        total = self.length / 1000
        now = self.cursor / 1000
        self.app.text(screen, f"{int(now // 60)}:{now % 60:06.3f} / {int(total // 60)}:{total % 60:06.3f}", (WIDTH - 16, 694), 16, right=True, color=WHITE, raw=True)
        toast(self.app, screen, self.message, self.message_at, 655)


# ------------------------------------------------- éditeur scène / caméra ----
class StageEditorState(BaseState):
    """Déplace persos et éléments de décor à la souris, règle la caméra de chaque perso, aperçu en jeu."""

    ZOOMS = (.25, .35, .5, .65, .8, 1.0, 1.25)

    def __init__(self, app, stage_id: str):
        super().__init__(app)
        self.stage_id = stage_id
        self.source = app.assets.path(f"data/stages/{stage_id}.json")
        self.data = app.assets.json(self.source) if self.source.is_file() else {"props": [], "characters": {}, "cameraZoom": 1.0}
        self.data.setdefault("characters", {})
        self.view_zoom_index = 3
        self.preview = False
        self.camera_mode = False
        self.selection = "bf"
        self.drag_from: tuple[int, int] | None = None
        self.pan_from: tuple[int, int] | None = None
        self.message, self.message_at = "", 0
        self.characters = {"bf": Character(app.assets, "bf", True), "dad": Character(app.assets, "dad"), "gf": Character(app.assets, "gf")}
        self.build()
        self.cam = list(self._focus("gf"))

    def build(self) -> None:
        zoom = self.data.get("cameraZoom", 1.0) if self.preview else self.ZOOMS[self.view_zoom_index]
        self.app.loading_screen()
        self.stage = Stage(self.app.assets, self.stage_id, zoom=float(zoom))
        for key, character in self.characters.items():
            info = self.data["characters"].setdefault(key, dict(Stage.DEFAULT_CHARACTERS[key]))
            self.stage.characters[key] = info
            self.stage.add_character(key, character)

    def _focus(self, key: str) -> tuple[float, float]:
        return self.characters[key].focus()

    def selections(self) -> list[str]:
        return ["bf", "dad", "gf"] + [f"prop:{index}" for index in range(len(self.data.get("props", [])))]

    def selected_object(self):
        if self.selection.startswith("prop:"):
            index = int(self.selection.split(":")[1])
            return next((item for _, _, item in self.stage.items if getattr(item, "prop_index", None) == index), None)
        return self.characters[self.selection]

    def notify(self, text: str) -> None:
        self.message, self.message_at = text, pygame.time.get_ticks()

    def move_selected(self, dx: float, dy: float) -> None:
        if self.selection.startswith("prop:"):
            index = int(self.selection.split(":")[1])
            prop = self.data["props"][index]
            x, y = prop.get("position", [0, 0])
            prop["position"] = [round(x + dx, 2), round(y + dy, 2)]
            item = self.selected_object()
            if item is not None:
                item.x += dx; item.y += dy
            return
        info = self.data["characters"][self.selection]
        if self.camera_mode:
            ox, oy = info.get("cameraOffsets", [0, 0])
            info["cameraOffsets"] = [round(ox + dx, 2), round(oy + dy, 2)]
            self.characters[self.selection].stage_camera_offsets = tuple(info["cameraOffsets"])
        else:
            x, y = info.get("position", [0, 0])
            info["position"] = [round(x + dx, 2), round(y + dy, 2)]
            self.characters[self.selection].place(*info["position"])

    def zoom(self) -> float:
        return self.stage.zoom

    def event(self, event: pygame.event.Event) -> None:
        shift = pygame.key.get_mods() & pygame.KMOD_SHIFT
        if event.type == pygame.MOUSEWHEEL and not self.preview:
            self.view_zoom_index = max(0, min(len(self.ZOOMS) - 1, self.view_zoom_index + (1 if event.y > 0 else -1)))
            self.build()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.drag_from = event.pos
            elif event.button in (2, 3):
                self.pan_from = event.pos
        elif event.type == pygame.MOUSEBUTTONUP:
            self.drag_from = self.pan_from = None
        elif event.type == pygame.MOUSEMOTION:
            if self.drag_from:
                dx, dy = event.pos[0] - self.drag_from[0], event.pos[1] - self.drag_from[1]
                self.move_selected(dx / self.zoom(), dy / self.zoom())
                self.drag_from = event.pos
            elif self.pan_from and not self.preview:
                self.cam[0] -= (event.pos[0] - self.pan_from[0]) / self.zoom()
                self.cam[1] -= (event.pos[1] - self.pan_from[1]) / self.zoom()
                self.pan_from = event.pos
        elif event.type == pygame.KEYDOWN:
            step = 10 if shift else 1
            key = event.key
            if key == pygame.K_LEFT: self.move_selected(-step, 0)
            elif key == pygame.K_RIGHT: self.move_selected(step, 0)
            elif key == pygame.K_UP: self.move_selected(0, -step)
            elif key == pygame.K_DOWN: self.move_selected(0, step)
            elif key == pygame.K_TAB:
                options = self.selections()
                self.selection = options[(options.index(self.selection) + (-1 if shift else 1)) % len(options)]
            elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
                self.selection = ("bf", "dad", "gf")[key - pygame.K_1]
            elif key == pygame.K_c:
                self.camera_mode = not self.camera_mode
            elif key in (pygame.K_z, pygame.K_x):
                self.data["cameraZoom"] = round(max(.2, min(3.0, float(self.data.get("cameraZoom", 1)) + (.05 if key == pygame.K_x else -.05))), 2)
                if self.preview:
                    self.build()
            elif key == pygame.K_p:
                self.preview = not self.preview
                self.build()
            elif key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL or key == pygame.K_F2:
                target = save_target(self.app, self.source if self.source.is_file() else None, f"data/stages/{self.stage_id}.json")
                write_json(target, self.data)
                self.source = target
                self.app.reload_mods()
                self.notify(f"{self.app.tr('SAVED')} : {target}")
            elif key == pygame.K_ESCAPE:
                self.app.change(ToolsState(self.app))

    def update(self, dt: float) -> None:
        now = pygame.time.get_ticks()
        beat = int(now / 600)
        if beat != getattr(self, "_beat", -1):
            self._beat = beat
            self.stage.beat(beat, now, 150)
        if self.preview and not self.selection.startswith("prop:"):
            target = self._focus(self.selection)
            follow = 1 - (1 - .08) ** (dt * 60)
            self.cam[0] += (target[0] - self.cam[0]) * follow
            self.cam[1] += (target[1] - self.cam[1]) * follow

    def _screen_rect(self, item) -> pygame.Rect | None:
        now = pygame.time.get_ticks()
        if isinstance(item, StaticProp):
            x, y = to_screen(item.x, item.y, tuple(self.cam), self.zoom(), item.scroll)
            return pygame.Rect(round(x), round(y), item.surface.get_width(), item.surface.get_height())
        if item is None or item.current not in item.anims:
            return None
        surface, left, top = item._frame(item.current, item.frame_number(now), self.zoom())
        off = item.anims[item.current].offsets
        x, y = to_screen(item.x + left * item.scale[0] - off[0] * item.scale[0], item.y + top * item.scale[1] - off[1] * item.scale[1],
                         tuple(self.cam), self.zoom(), item.scroll)
        return pygame.Rect(round(x), round(y), surface.get_width(), surface.get_height())

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        screen.fill((40, 40, 46))
        self.stage.draw(screen, tuple(self.cam), now)
        if not self.preview:
            rect = self._screen_rect(self.selected_object())
            if rect:
                pygame.draw.rect(screen, UI_ACCENT, rect, 3)
            for key, character in self.characters.items():
                fx, fy = to_screen(*character.focus(), tuple(self.cam), self.zoom())
                selected = key == self.selection
                color = (230, 60, 90) if selected else WHITE
                pygame.draw.circle(screen, color, (round(fx), round(fy)), 9, 3)
                pygame.draw.line(screen, color, (fx - 16, fy), (fx + 16, fy), 2)
                pygame.draw.line(screen, color, (fx, fy - 16), (fx, fy + 16), 2)
                if selected:
                    # Ce que la caméra du jeu voit quand elle suit ce perso.
                    game_zoom = float(self.data.get("cameraZoom", 1))
                    half_w, half_h = WIDTH / 2 / game_zoom, HEIGHT / 2 / game_zoom
                    x0, y0 = to_screen(character.focus()[0] - half_w, character.focus()[1] - half_h, tuple(self.cam), self.zoom())
                    x1, y1 = to_screen(character.focus()[0] + half_w, character.focus()[1] + half_h, tuple(self.cam), self.zoom())
                    pygame.draw.rect(screen, WHITE, (round(x0), round(y0), round(x1 - x0), round(y1 - y0)), 2)
                    self.app.text(screen, "game camera", (round(x0) + 6, round(y0) + 4), 14, color=WHITE)
        tr = self.app.tr
        mode = tr("PREVIEW") if self.preview else tr("camera offsets") if self.camera_mode else tr("position")
        toolbar(self.app, screen, f"{tr('Stage Editor')}  —  {self.stage_id}", tr("Ctrl+S save    P preview    Esc quit"))
        name = self.selection
        if name.startswith("prop:"):
            prop = self.data["props"][int(name.split(":")[1])]
            selected = [(tr("Selected"), f"{tr('prop')} '{prop.get('name', '')}'"), (tr("Position"), prop.get("position")),
                        (tr("Scroll"), prop.get("scroll", [1, 1])), ("Z index", prop.get("zIndex", 0))]
        else:
            data = self.data["characters"][name]
            selected = [(tr("Selected"), name), (tr("Position"), data.get("position")), (tr("Camera offs."), data.get("cameraOffsets", [0, 0])),
                        ("Z index", data.get("zIndex", 0))]
        y = window(self.app, screen, pygame.Rect(WIDTH - 372, 44, 356, 196), tr("Stage"))
        rows(self.app, screen, WIDTH - 358, y, [(tr("Stage"), self.stage_id), (tr("Game zoom"), f"{self.data.get('cameraZoom', 1)}   (Z / X)"),
                                                (tr("Mode"), f"{mode}   (C)"), *selected])
        y = window(self.app, screen, pygame.Rect(WIDTH - 372, 254, 356, 170), tr("Controls"))
        rows(self.app, screen, WIDTH - 358, y, [tr(line) for line in (
            "Drag / arrows: move (Shift x10)", "Tab or 1 2 3: select", "C: position / camera offsets",
            "Right drag: pan   Wheel: zoom", "P: see it like in game")], size=15, gap=24)
        toast(self.app, screen, self.message, self.message_at, HEIGHT - 30)


# ---------------------------------------------------- éditeur de personnage ----
class CharacterEditorState(BaseState):
    """Corrige les offsets de chaque animation (onion skin de la pose de repos) et le point de caméra."""

    def __init__(self, app, character_id: str):
        super().__init__(app)
        self.character_id = character_id
        self.source = app.assets.path(f"data/characters/{character_id}.json")
        self.player_view = False
        self.load()
        self.camera_mode = False
        self.ghost = True
        self.message, self.message_at = "", 0

    def load(self) -> None:
        self.character = Character(self.app.assets, self.character_id, self.player_view)
        self.character.place(0, 0)
        self.config = self.character.config
        self.names = [item.get("name") for item in self.config.get("animations", []) if item.get("name") in self.character.anims]
        self.index = 0
        if self.names:
            self.character.play(self.names[0], pygame.time.get_ticks(), force=True)
        self.zoom = min(1.0, 560 / max(1, self.character.anchor[1] * self.character.scale[1])) if self.character.loaded else 1.0
        self.cam = (self.character.center[0] * self.character.scale[0] + self.character.x, self.character.y + self.character.anchor[1] * self.character.scale[1] / 2 + 40)

    def entry(self, name: str) -> dict:
        return next(item for item in self.config["animations"] if item.get("name") == name)

    def nudge(self, dx: int, dy: int) -> None:
        if self.camera_mode:
            ox, oy = self.config.get("cameraOffsets", [0, 0])
            self.config["cameraOffsets"] = [ox + dx, oy + dy]
            self.character.camera_offsets = tuple(self.config["cameraOffsets"])
            return
        if not self.names:
            return
        name = self.names[self.index]
        entry = self.entry(name)
        ox, oy = (entry.get("offsets") or [0, 0])[:2]
        # Comme FNF : augmenter l'offset décale le sprite vers la gauche / le haut.
        entry["offsets"] = [ox - dx, oy - dy]
        self.character.anims[name].offsets = (float(entry["offsets"][0]), float(entry["offsets"][1]))

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        shift = pygame.key.get_mods() & pygame.KMOD_SHIFT
        step = 10 if shift else 1
        key = event.key
        now = pygame.time.get_ticks()
        if key in (pygame.K_w, pygame.K_s) and self.names and not pygame.key.get_mods() & pygame.KMOD_CTRL:  # Ctrl+S = enregistrer
            self.index = (self.index + (1 if key == pygame.K_s else -1)) % len(self.names)
            self.character.play(self.names[self.index], now, force=True)
        elif key == pygame.K_SPACE and self.names:
            self.character.play(self.names[self.index], now, force=True)
        elif key == pygame.K_LEFT: self.nudge(-step, 0)
        elif key == pygame.K_RIGHT: self.nudge(step, 0)
        elif key == pygame.K_UP: self.nudge(0, -step)
        elif key == pygame.K_DOWN: self.nudge(0, step)
        elif key == pygame.K_c:
            self.camera_mode = not self.camera_mode
        elif key == pygame.K_g:
            self.ghost = not self.ghost
        elif key == pygame.K_f:
            self.player_view = not self.player_view
            index = self.index
            config = self.config
            self.load()
            self.config = config
            self.index = min(index, max(0, len(self.names) - 1))
            for name in self.names:
                self.character.anims[name].offsets = tuple(float(v) for v in (self.entry(name).get("offsets") or [0, 0])[:2])
        elif (key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL) or key == pygame.K_F2:
            target = save_target(self.app, self.source if self.source.is_file() else None, f"data/characters/{self.character_id}.json")
            write_json(target, self.config)
            self.source = target
            self.app.reload_mods()
            self.message, self.message_at = f"{self.app.tr('SAVED')} : {target}", now
        elif key == pygame.K_ESCAPE:
            self.app.change(ToolsState(self.app))

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        # Fond en damier gris comme l'Animation Debug de FNF.
        for x in range(0, WIDTH, 40):
            for y in range(0, HEIGHT, 40):
                pygame.draw.rect(screen, (196, 196, 200) if (x // 40 + y // 40) % 2 else (182, 182, 188), (x, y, 40, 40))
        floor = to_screen(0, 0, self.cam, self.zoom)[1]
        pygame.draw.line(screen, (90, 90, 100), (0, floor), (WIDTH, floor), 2)
        if self.ghost and self.names and self.character.loaded:
            reference = next((name for name in ("idle", "danceRight", "danceLeft") if name in self.character.anims), self.names[0])
            surface, left, top = self.character._frame(reference, 0, self.zoom)
            off = self.character.anims[reference].offsets
            sx, sy = self.character.scale
            x, y = to_screen(self.character.x + left * sx - off[0] * sx, self.character.y + top * sy - off[1] * sy, self.cam, self.zoom)
            ghost = surface.copy(); ghost.set_alpha(80)
            screen.blit(ghost, (round(x), round(y)))
        self.character.draw(screen, self.cam, self.zoom, now)
        fx, fy = to_screen(*self.character.focus(), self.cam, self.zoom)
        color = (230, 60, 90) if self.camera_mode else (40, 40, 48)
        pygame.draw.circle(screen, color, (round(fx), round(fy)), 9, 3)
        pygame.draw.line(screen, color, (fx - 18, fy), (fx + 18, fy), 2)
        pygame.draw.line(screen, color, (fx, fy - 18), (fx, fy + 18), 2)
        tr = self.app.tr
        toolbar(self.app, screen, f"{tr('Character Editor')}  —  {self.character_id}", tr("Ctrl+S save    Esc quit"))
        box = pygame.Rect(16, 44, 330, min(470, 50 + max(1, len(self.names)) * 24))
        y = window(self.app, screen, box, tr("Animations   (W / S)"))
        if not self.character.loaded:
            self.app.text(screen, "No animation found", (30, y), 16, color=(200, 40, 60))
        for row, name in enumerate(self.names[:18]):
            offsets = self.entry(name).get("offsets") or [0, 0]
            line = pygame.Rect(box.x + 4, y + row * 24 - 2, box.width - 8, 22)
            selected = row == self.index
            if selected:
                pygame.draw.rect(screen, UI_ACCENT, line)
            self.app.text(screen, name, (line.x + 8, line.y + 2), 15, color=WHITE if selected else UI_TEXT, raw=True)
            self.app.text(screen, f"[{offsets[0]}, {offsets[1]}]", (line.right - 8, line.y + 2), 15, right=True, color=WHITE if selected else UI_MUTED, raw=True)
        y = window(self.app, screen, pygame.Rect(16, HEIGHT - 196, 330, 180), tr("Controls"))
        rows(self.app, screen, 30, y, [*(tr(line) for line in ("Arrows: offsets (Shift x10)", "Space: replay animation", "C: camera point mode",
                                                               "G: ghost   F: player view (flip)")),
                                       f"{tr('Camera offsets')}: {self.config.get('cameraOffsets', [0, 0])}"], size=15, gap=24)
        toast(self.app, screen, self.message, self.message_at, HEIGHT - 30)
