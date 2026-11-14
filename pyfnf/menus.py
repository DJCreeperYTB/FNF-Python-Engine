"""Écrans de menus : titre, menu principal, story mode, freeplay, mods, succès, options."""
from __future__ import annotations

import math
import os
import statistics
import textwrap
import time
from datetime import datetime
from pathlib import Path

import pygame

from .assets import SparrowAtlas
from .data import difficulty_sort_key
from .mods import create_template, discover, mods_dir
from .settings import FPS_CHOICES, step_scroll
from . import gamepad, news
from .stage import Actor
from .ui import (BLACK, CYAN, HEIGHT, LANE_COLORS, LANE_NAMES, PINK, RED, SCREEN_CAM, TRACK_PINK, UI_BORDER, UI_MUTED,
                 UI_TEXT, WHITE, WIDTH, YELLOW, BaseState, ease_out, fit, lerp, make_actor, parse_color, rows, scale_by,
                 shade, tint, window, key_hints, rich_text)


def sparrow(app, relative: str) -> SparrowAtlas | None:
    """Spritesheet Sparrow mise en cache dans l'app (les menus en recréent souvent)."""
    key = ("sparrow", relative)
    if key not in app.cache:
        path = app.assets.path(relative)
        app.cache[key] = SparrowAtlas(app.assets, path) if path.is_file() else None
    return app.cache[key]


def frames(app, relative: str, prefix: str) -> list[pygame.Surface]:
    atlas = sparrow(app, relative)
    return atlas.animation(prefix) if atlas and atlas.has(prefix) else []


def image(app, relative: str) -> pygame.Surface | None:
    path = app.assets.path(relative)
    return app.assets.image(path) if path.is_file() else None


def frame_at(sequence: list[pygame.Surface], seconds: float, fps: float = 24, loop: bool = True) -> pygame.Surface | None:
    if not sequence:
        return None
    index = int(seconds * fps)
    return sequence[index % len(sequence)] if loop else sequence[min(index, len(sequence) - 1)]


def whiten(surface: pygame.Surface) -> pygame.Surface:
    """Texte sombre des capsules passé en blanc pour rester lisible."""
    surface = surface.copy()
    surface.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
    return surface


def bitmap_text(app, text: str, height: int, color: tuple[int, int, int]) -> pygame.Surface:
    """Texte dans la police dessinée de FNF (images/fonts/default), recolorée : liste TRACKS du mode histoire."""
    import unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    key = ("bitmap-text", text, height, color)
    if key not in app.cache:
        atlas = sparrow(app, "images/fonts/default.png")
        glyphs, width = [], 0
        names = {"-": "-dash-", ".": "-period-", ",": "-comma-", "!": "-exclamation point-", "?": "-question mark-",
                 "'": "-apostraphie-", "/": "-forward slash-"}
        for char in text:
            char = names.get(char, char)
            frame = atlas.animation(char)[0] if atlas and char != " " and atlas.has(char) else None
            if frame is None:
                glyphs.append((None, 0, 22, char)); width += 22
                continue
            bounds = frame.get_bounding_rect()
            glyphs.append((frame, bounds.x, bounds.width, char)); width += bounds.width + 3
        size = max((frame.get_height() for frame, _, _, _ in glyphs if frame), default=50)
        canvas = pygame.Surface((max(1, width), size), pygame.SRCALPHA)
        x = 0
        for frame, left, advance, char in glyphs:
            if frame:
                # Petits signes rognés : tiret au milieu, point et virgule en bas (sinon collés en haut).
                y = (size - frame.get_height()) // 2 if char == "-dash-" else size - frame.get_height() if char in ("-period-", "-comma-") else 0
                canvas.blit(frame, (x - left, y)); x += advance + 3
            else:
                x += advance
        canvas.fill(color, special_flags=pygame.BLEND_RGB_MAX)  # lettres noires -> couleur demandée
        app.cache[key] = scale_by(canvas, height / size)
    return app.cache[key]


def grade_letter(accuracy: float) -> str:
    """Même barème que l'écran de résultats."""
    return "S" if accuracy >= 95 else "A" if accuracy >= 88 else "B" if accuracy >= 78 else "C" if accuracy >= 65 else "D"


# ---------------------------------------------------------------- titre ----
class TitleState(BaseState):
    def __init__(self, app, restart_music: bool = True):
        super().__init__(app)
        self.logo = frames(app, "images/logoBumpin.png", "logo bumpin")
        self.gf = frames(app, "images/gfDanceTitle.png", "gfDance")
        self.title_text = make_actor(app.assets, "title-screen-text", [{"name": "idle", "prefix": "Idle", "looped": True}, {"name": "confirm", "prefix": "Confirm"}])
        self.leaving_at = 0
        if restart_music or not pygame.mixer.music.get_busy():
            app.play_menu_music()

    def event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE) and not self.leaving_at:
            self.app.confirm_sound()
            self.leaving_at = pygame.time.get_ticks()

    def update(self, dt: float) -> None:
        if self.leaving_at and pygame.time.get_ticks() - self.leaving_at > 700:
            self.app.change(MainMenuState(self.app))

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        beat = self.app.menu_beat()
        screen.fill(BLACK)
        if self.gf:
            # GF danse sur la musique : 30 frames = 2 temps.
            gf = self.gf[int((beat % 2) / 2 * len(self.gf)) % len(self.gf)]
            screen.blit(gf, (WIDTH - gf.get_width() + 40, HEIGHT - gf.get_height() + 10))
        if self.logo:
            logo = self.logo[min(len(self.logo) - 1, int((beat % 1) * len(self.logo) * 1.6))]
            screen.blit(logo, (-40, -30))
        flash = 255 - min(255, (now - self.leaving_at) * 255 // 700) if self.leaving_at else 0
        if self.title_text.anims:
            if self.leaving_at and self.title_text.current != "confirm":
                self.title_text.play("confirm", now, force=True)
            actor = self.title_text
            surface, _, _ = actor._frame(actor.current, actor.frame_number(now), 1.0)
            surface = fit(surface, 1100, 140)
            screen.blit(surface, surface.get_rect(center=(WIDTH // 2, 640)))
        else:
            pulse = 180 + round(math.sin(now / 180) * 75)
            self.app.text(screen, "PRESS ENTER TO BEGIN", (WIDTH // 2, 635), 42, color=(255, pulse, 225), bold=True, center=True, outline=True)
        if flash:
            screen.blit(shade(flash, (255, 255, 255)), (0, 0))
        self.app.draw_version(screen)


# ------------------------------------------------------- menu principal ----
def menu_icon(app, kind: str, focused: bool) -> pygame.Surface:
    """Bouton rond du menu principal (trophée ou parchemin), dessiné dans le style des boutons FNF : contour noir épais."""
    key = ("menu-icon", kind, focused)
    if key in app.cache:
        return app.cache[key]
    size = 96
    icon = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    pygame.draw.circle(icon, BLACK, (c + 4, c + 4), 40)
    pygame.draw.circle(icon, (255, 222, 70) if focused else WHITE, (c, c), 40)
    pygame.draw.circle(icon, BLACK, (c, c), 40, 5)
    if kind == "trophies":
        gold, dark = (255, 196, 40), (190, 120, 10)
        for side in (-1, 1):  # anses
            pygame.draw.circle(icon, BLACK, (c + side * 17, c - 9), 9, 4)
        cup = [(c - 17, c - 22), (c + 17, c - 22), (c + 11, c + 4), (c - 11, c + 4)]
        pygame.draw.polygon(icon, gold, cup)
        pygame.draw.polygon(icon, dark, [(c + 4, c - 22), (c + 17, c - 22), (c + 11, c + 4), (c + 2, c + 4)])
        pygame.draw.polygon(icon, BLACK, cup, 4)
        pygame.draw.rect(icon, gold, (c - 4, c + 4, 8, 8)); pygame.draw.rect(icon, BLACK, (c - 4, c + 4, 8, 8), 3)
        pygame.draw.rect(icon, gold, (c - 14, c + 12, 28, 9)); pygame.draw.rect(icon, BLACK, (c - 14, c + 12, 28, 9), 4)
    else:  # parchemin des annonces
        paper, roll = (252, 238, 205), (226, 196, 140)
        sheet = pygame.Rect(c - 17, c - 19, 34, 40)
        pygame.draw.rect(icon, paper, sheet); pygame.draw.rect(icon, BLACK, sheet, 4)
        for y in (c - 24, c + 18):
            rod = pygame.Rect(c - 22, y, 44, 10)
            pygame.draw.rect(icon, roll, rod, border_radius=5); pygame.draw.rect(icon, BLACK, rod, 4, border_radius=5)
        for row in range(3):
            pygame.draw.line(icon, BLACK, (c - 10, c - 8 + row * 9), (c + 10 - (8 if row == 2 else 0), c - 8 + row * 9), 3)
    app.cache[key] = icon
    return icon


class MainMenuState(BaseState):
    ITEMS = ("storymode", "freeplay", "mods", "online", "tools", "donate", "options")
    LOCKED = {"online"}  # multijoueur en ligne : arrive dans une prochaine mise à jour
    ICONS = ("trophies", "news")
    DONATE_URL = "https://paypal.me/djcreeperytb"
    SPACING = 150

    def __init__(self, app, selected: int | str = 0):
        super().__init__(app)
        # Retour d'un écran : on revient sur son bouton (nom) ; les icônes trophée / annonces gardent le focus.
        self.icon = self.ICONS.index(selected) if selected in self.ICONS else None
        if isinstance(selected, str):
            selected = self.ITEMS.index(selected) if selected in self.ITEMS else 0
        self.selected = selected % len(self.ITEMS)
        self.cam_y = float(self.selected * self.SPACING)
        self.confirmed_at = 0
        self.locked_at = 0
        bg = image(app, "images/menuBG.png")
        magenta = image(app, "images/menuBGMagenta.png") or bg
        size = (round(WIDTH * 1.18), round(HEIGHT * 1.18))
        self.bg = pygame.transform.smoothscale(bg, size) if bg else None
        self.magenta = pygame.transform.smoothscale(magenta, size) if magenta else None
        self.item_frames = {name: (frames(app, f"images/mainmenu/{name}.png", f"{name} idle"),
                                   frames(app, f"images/mainmenu/{name}.png", f"{name} selected")) for name in self.ITEMS}

    def _icon_rects(self) -> list[pygame.Rect]:
        return [pygame.Rect(WIDTH - 214 + index * 104, 22, 96, 96) for index in range(len(self.ICONS))]

    def _open_icon(self, index: int) -> None:
        self.app.confirm_sound()
        self.app.change(AchievementsState(self.app) if self.ICONS[index] == "trophies" else NewsState(self.app))

    def event(self, event: pygame.event.Event) -> None:
        if self.confirmed_at:
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, rect in enumerate(self._icon_rects()):
                if rect.collidepoint(event.pos):
                    self._open_icon(index)
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_RIGHT, pygame.K_d):  # vers les icônes en haut à droite
            self.icon = 0 if self.icon is None else min(len(self.ICONS) - 1, self.icon + 1); self.app.scroll_sound()
        elif event.key in (pygame.K_LEFT, pygame.K_a) and self.icon is not None:
            self.icon = None if self.icon == 0 else self.icon - 1; self.app.scroll_sound()
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.icon = None
            self.selected = (self.selected - 1) % len(self.ITEMS); self.app.scroll_sound()
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.icon = None
            self.selected = (self.selected + 1) % len(self.ITEMS); self.app.scroll_sound()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            target = self.ITEMS[self.selected]
            if self.icon is not None:
                self._open_icon(self.icon)
            elif target in self.LOCKED:
                self.locked_at = pygame.time.get_ticks()
                self.app.play_sound("sounds/CS_locked.ogg")
            elif target == "donate":
                import webbrowser
                self.app.confirm_sound()
                webbrowser.open(self.DONATE_URL)
            else:
                self.app.confirm_sound()
                self.confirmed_at = pygame.time.get_ticks()
        elif event.key == pygame.K_ESCAPE:
            self.app.cancel_sound()
            self.app.change(TitleState(self.app, restart_music=False))

    def update(self, dt: float) -> None:
        self.cam_y = lerp(self.cam_y, self.selected * self.SPACING, dt, 9)
        if self.confirmed_at and pygame.time.get_ticks() - self.confirmed_at > 1000:
            target = self.ITEMS[self.selected]
            if target == "storymode":
                self.app.change(StoryMenuState(self.app))
            elif target == "freeplay":
                self.app.change(FreeplayState(self.app))
            elif target == "mods":
                self.app.change(ModsState(self.app))
            elif target == "tools":
                from .editors import ToolsState
                self.app.change(ToolsState(self.app))
            else:
                self.app.change(OptionsState(self.app))

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        flicker = self.confirmed_at and ((now - self.confirmed_at) // 110) % 2 == 0 and self.app.settings.flashing_lights
        background = self.magenta if flicker else self.bg
        if background:
            span = (len(self.ITEMS) - 1) * self.SPACING
            progress = self.cam_y / span if span else 0
            screen.blit(background, ((WIDTH - background.get_width()) // 2, round(-(background.get_height() - HEIGHT) * progress)))
        else:
            screen.fill((250, 205, 80))
        since = now - self.confirmed_at if self.confirmed_at else 0
        for index, name in enumerate(self.ITEMS):
            selected = index == self.selected
            idle, chosen = self.item_frames[name]
            sequence = chosen if selected else idle
            frame = frame_at(sequence, now / 1000, 24) if sequence else self.app.alphabet(name.upper(), 90)
            if frame is None:
                continue
            frame = fit(frame, 760, 170)
            y = HEIGHT / 2 + index * self.SPACING - self.cam_y
            shake = 0
            if name in self.LOCKED:
                frame = tint(frame, (150, 150, 160))  # bouton verrouillé : grisé, cadenas à côté
                if selected and now - self.locked_at < 350:
                    shake = round(math.sin(now / 22) * 10)
            if self.confirmed_at and not selected:
                fade = max(0, 255 - since * 255 // 400)
                if not fade:
                    continue
                frame = frame.copy(); frame.set_alpha(fade)
            elif self.confirmed_at and selected and (since // 70) % 2:
                continue  # le bouton choisi clignote
            elif not selected:
                frame = frame.copy(); frame.set_alpha(150)
            left = WIDTH // 2 - frame.get_width() // 2 + shake
            screen.blit(frame, (left, round(y - frame.get_height() / 2)))
            if name in self.LOCKED:
                lock = image(self.app, "images/storymenu/ui/lock.png")
                if lock:
                    lock = fit(lock, 80, 80)
                    screen.blit(lock, lock.get_rect(midleft=(left + frame.get_width() + 14, round(y))))
        # Icônes trophée / annonces, avec un point rouge s'il y a du nouveau.
        settings = self.app.settings
        unread = {"trophies": len(settings.achievements) > settings.trophies_seen,
                  "news": any(item["id"] not in settings.news_seen for item in news.all_news(self.app))}
        for index, (kind, rect) in enumerate(zip(self.ICONS, self._icon_rects())):
            icon = menu_icon(self.app, kind, self.icon == index)
            if self.icon == index:
                icon = scale_by(icon, 1.12)
            screen.blit(icon, icon.get_rect(center=rect.center))
            if unread[kind]:
                dot = (rect.right - 14, rect.y + 16)
                pygame.draw.circle(screen, WHITE, dot, 13)
                pygame.draw.circle(screen, (230, 30, 45), dot, 10)
        self.app.draw_version(screen)


# ------------------------------------------------------------ story mode ----
class StoryMenuState(BaseState):
    BAND_Y, BAND_H = 56, 400

    def __init__(self, app, selected: int = 0, difficulty: str | None = None):
        super().__init__(app)
        self.weeks = app.data.weeks
        self.selected = selected % max(1, len(self.weeks))
        self.scroll = float(self.selected)
        self.difficulty_index = 0
        self.diff_changed_at = 0
        self.arrow_pressed = {"left": 0, "right": 0}
        self.confirmed_at = 0
        self.shown_score = 0.0
        self.props_cache: dict[int, list[Actor]] = {}
        self.last_beat = -1
        self._sync_difficulties()
        if difficulty in self.difficulties:
            self.difficulty_index = self.difficulties.index(difficulty)
        self.arrows = {name: frames(app, "images/storymenu/ui/arrows.png", name) for name in ("leftIdle", "leftConfirm", "rightIdle", "rightConfirm")}

    def _sync_difficulties(self) -> None:
        if not self.weeks:
            self.difficulties = ["normal"]
            return
        week = self.weeks[self.selected]
        previous = self.difficulties[self.difficulty_index] if getattr(self, "difficulties", None) else None
        base = [key for key in self.app.data.common_difficulties(week.songs) if ":" not in key]
        self.difficulties = base or [key for key in sorted(self.app.data.songs[week.songs[0]].charts, key=difficulty_sort_key) if ":" not in key] \
            or sorted(self.app.data.songs[week.songs[0]].charts, key=difficulty_sort_key)
        self.difficulty_index = self.difficulties.index(previous) if previous in self.difficulties else min(1, len(self.difficulties) - 1)

    def props(self) -> list[Actor]:
        if self.selected not in self.props_cache:
            actors = []
            data = self.weeks[self.selected].props if self.weeks else []
            for index, prop in enumerate(data):
                try:
                    actor = make_actor(self.app.assets, str(prop.get("assetPath", "")), prop.get("animations") or [],
                                       float(prop.get("scale", 1)), bool(prop.get("flipX", False)), bool(prop.get("isPixel", False)))
                except (OSError, ValueError, KeyError, pygame.error):
                    continue
                if not actor.anims:
                    continue
                offsets = (prop.get("offsets") or [0, 0])[:2]
                actor.x = WIDTH * .25 * index + float(offsets[0])
                actor.y = self.BAND_Y + float(offsets[1])
                actor.dance_every = 1
                actors.append(actor)
            self.props_cache[self.selected] = actors
        return self.props_cache[self.selected]

    def change_difficulty(self, step: int) -> None:
        self.difficulty_index = (self.difficulty_index + step) % len(self.difficulties)
        self.diff_changed_at = pygame.time.get_ticks()
        self.arrow_pressed["left" if step < 0 else "right"] = self.diff_changed_at
        self.app.scroll_sound()

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN or self.confirmed_at:
            return
        if event.key == pygame.K_ESCAPE:
            self.app.change(MainMenuState(self.app, "storymode")); self.app.cancel_sound()
        elif not self.weeks:
            return
        elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
            step = -1 if event.key in (pygame.K_UP, pygame.K_w) else 1
            self.selected = (self.selected + step) % len(self.weeks); self._sync_difficulties(); self.app.scroll_sound()
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            self.change_difficulty(-1)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.change_difficulty(1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.app.confirm_sound()
            self.confirmed_at = pygame.time.get_ticks()
            for actor in self.props():
                actor.play("confirm", self.confirmed_at, force=True)

    def update(self, dt: float) -> None:
        now = pygame.time.get_ticks()
        self.scroll = lerp(self.scroll, self.selected, dt, 10)
        beat = int(self.app.menu_beat())
        if beat != self.last_beat:
            self.last_beat = beat
            for actor in self.props():
                if actor.current != "confirm":
                    actor.beat(beat, now)
        if self.weeks:
            key = self.difficulties[self.difficulty_index]
            target = sum(self.app.settings.scores.get(f"{song}|{key}", 0) for song in self.weeks[self.selected].songs)
            self.shown_score = lerp(self.shown_score, target, dt, 14)
        if self.confirmed_at and now - self.confirmed_at > 1100:
            week = self.weeks[self.selected]
            self.app.start_playlist(week.songs, self.difficulties[self.difficulty_index], story_week=self.selected)

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        screen.fill(BLACK)
        if not self.weeks:
            self.app.text(screen, "NO WEEK AVAILABLE", (WIDTH // 2, HEIGHT // 2), 40, center=True, bold=True)
            return
        week = self.weeks[self.selected]
        # Liste des semaines sous la bande, centrée, qui défile en douceur.
        screen.set_clip(pygame.Rect(0, self.BAND_Y + self.BAND_H, WIDTH, HEIGHT))
        for index, item in enumerate(self.weeks):
            offset = index - self.scroll
            if abs(offset) > 3:
                continue
            y = self.BAND_Y + self.BAND_H + 70 + offset * 120
            title = self._title(item)
            if index == self.selected and self.confirmed_at and ((now - self.confirmed_at) // 80) % 2:
                title = tint(title, (51, 255, 255))
            elif index != self.selected:
                title = title.copy(); title.set_alpha(150)
            screen.blit(title, title.get_rect(center=(WIDTH // 2, round(y))))
        screen.set_clip(None)
        # Bande de couleur avec les personnages de la semaine.
        pygame.draw.rect(screen, parse_color(week.background), (0, self.BAND_Y, WIDTH, self.BAND_H))
        screen.set_clip(pygame.Rect(0, self.BAND_Y, WIDTH, self.BAND_H))
        for actor in self.props():
            actor.draw(screen, SCREEN_CAM, 1.0, now)
        screen.set_clip(None)
        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, self.BAND_Y))
        self.app.text(screen, f"{self.app.tr('WEEK SCORE')}: {round(self.shown_score)}", (12, 12), 32, bold=True)
        self.app.text(screen, week.name.upper(), (WIDTH - 12, 12), 32, color=(178, 178, 178), right=True, bold=True, raw=True)
        # Pistes.
        tracks = bitmap_text(self.app, "TRACKS", 40, TRACK_PINK)
        screen.blit(tracks, tracks.get_rect(center=(190, self.BAND_Y + self.BAND_H + 62)))
        for row, song_id in enumerate(week.songs[:5]):
            name = fit(bitmap_text(self.app, self.app.data.songs[song_id].name.upper(), 32, TRACK_PINK), 340, 40)
            screen.blit(name, name.get_rect(center=(190, self.BAND_Y + self.BAND_H + 112 + row * 40)))
        # Difficulté avec flèches animées.
        center_x, center_y = 1065, self.BAND_Y + self.BAND_H + 95
        difficulty = self.difficulties[self.difficulty_index].split(":", 1)[0]
        sprite = image(self.app, f"images/storymenu/difficulties/{difficulty}.png")
        if sprite is None:
            animated = frames(self.app, f"images/storymenu/difficulties/{difficulty}.png", "")
            sprite = frame_at(animated, now / 1000) if animated else None
        drop = ease_out((now - self.diff_changed_at) / 220) if self.diff_changed_at else 1
        if sprite:
            sprite = fit(sprite, 250, 100).copy()
            sprite.set_alpha(round(255 * drop))
            screen.blit(sprite, sprite.get_rect(center=(center_x, round(center_y - 18 * (1 - drop)))))
        else:
            self.app.text(screen, difficulty.upper(), (center_x, center_y - 25), 44, color=YELLOW, bold=True, center=True, outline=True, raw=True)
        half = (sprite.get_width() // 2 if sprite else 110) + 45
        for side, x in (("left", center_x - half), ("right", center_x + half)):
            pressed = now - self.arrow_pressed[side] < 150
            sequence = self.arrows[f"{side}{'Confirm' if pressed else 'Idle'}"]
            arrow = frame_at(sequence, now / 1000)
            if arrow:
                screen.blit(arrow, arrow.get_rect(center=(x, center_y)))

    def _title(self, week) -> pygame.Surface:
        key = ("week-title", week.week_id, week.title_asset)
        if key not in self.app.cache:
            path = self.app.assets.resolve_image(week.title_asset)
            surface = self.app.assets.image(path) if path and path.is_file() else self.app.alphabet(week.name or week.week_id, 70)
            # Taille réelle comme le jeu officiel (le titre Weekend 1, avec sa tache de peinture, n'est plus rétréci).
            self.app.cache[key] = fit(surface, 440, 220)  # place entre TRACKS et la difficulté
        return self.app.cache[key]


# -------------------------------------------------------------- freeplay ----
class FreeplayState(BaseState):
    CARD_W = 470
    PANEL_W = 470
    # Menu Ctrl : (clé dans app.modifiers, libellé, description).
    MODIFIERS = [
        ("scroll", "SCROLL SPEED", "Speed of the notes for this song (AUTO = the speed of the chart)."),
        ("rate", "SONG SPEED", "Plays the song faster or slower (the pitch follows)."),
        ("opponent", "PLAY AS OPPONENT", "You sing the opponent's notes, Boyfriend plays by himself."),
        ("judgment", "JUDGMENT", "NORMAL: a GOOD counts 75 %. EASY: GOOD counts 100 %."),
        ("practice", "PRACTICE MODE", "You can't lose. Scores are not saved."),
        ("botplay", "BOTPLAY", "The game plays the song for you. Scores are not saved."),
        ("locked", "GAMEPLAY MODIFIERS", "Coming in a future update!"),
    ]
    CHARACTERS = {
        "bf": {"dj": "freeplay/freeplay-boyfriend", "bg": "images/freeplay/freeplayBGweek1-bf.png", "tint": (255, 210, 120),
               "rows": (("BOYFRIEND", 70, (255, 160, 60), -.06), ("HOT BLOODED IN MORE WAYS THAN ONE", 26, (255, 255, 255), .04),
                        ("BOYFRIEND", 70, (255, 160, 60), .05), ("PROTECT YO NUTS", 26, (255, 255, 255), -.05))},
        "pico": {"dj": "freeplay/freeplay-pico", "bg": "images/freeplay/freeplayBGweek1-pico.png", "tint": (150, 190, 255),
                 "rows": (("PICO", 70, (90, 170, 255), -.06), ("PICO MIX", 26, (255, 255, 255), .04),
                          ("PICO", 70, (90, 170, 255), .05), ("PICO MIX", 26, (255, 255, 255), -.05))},
    }

    def __init__(self, app, song_id: str | None = None, chart: str | None = None):
        super().__init__(app)
        self.character = getattr(app, "freeplay_character", "bf")
        self.query = ""
        self.typing = False
        self.panel_open = False
        self.panel_row = 0
        self.panel_slide = 0.0
        self.locked_at = 0
        self.difficulty = chart.split(":")[0] if chart else "normal"
        self.chart_index = 0
        self.song_ids: list[str] = []
        self.selected = 0
        self._build_list(song_id, chart)
        self.scroll = float(self.selected)
        self.opened_at = pygame.time.get_ticks()
        self.confirmed_at = 0
        self.moved_at = self.opened_at
        self.preview_song = ""
        self.diff_changed_at = 0
        self.shown_score = 0.0
        self.last_beat = -1
        self._load_character()
        self.capsule_on = frames(app, "images/freeplay/freeplayCapsule/capsule/freeplayCapsule.png", "mp3 capsule w backing0")
        self.capsule_off = frames(app, "images/freeplay/freeplayCapsule/capsule/freeplayCapsule.png", "mp3 capsule w backing NOT SELECTED")
        self.selector = frames(app, "images/freeplay/freeplaySelector.png", "arrow pointer loop")
        self.highscore = frames(app, "images/freeplay/highscore.png", "highscore small")
        self.digits = {name: frames(app, "images/digital_numbers.png", f"{name} DIGITAL") for name in
                       ("ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE")}

    @property
    def text_input(self) -> bool:
        return self.typing  # les touches + - 0 du volume ne s'appliquent pas pendant la recherche

    def _load_character(self) -> None:
        """DJ, fond et carte du personnage choisi (Boyfriend ou Pico, Tab pour changer)."""
        style = self.CHARACTERS[self.character]
        self.dj = make_actor(self.app.assets, style["dj"], [
            {"name": "intro", "prefix": "Intro"}, {"name": "idle", "prefix": "Idle"},
            {"name": "confirm", "prefix": "Confirm"}], .76)
        if self.dj.anims:
            raw, (ox, oy) = self.dj.anims["intro" if "intro" in self.dj.anims else next(iter(self.dj.anims))].raw(0)
            self.dj_left = 30 - ox * .76
            self.dj.y = HEIGHT - 20 - (oy + raw.get_height()) * .76
        else:
            self.dj_left = 0.0
        self.dj.play("intro", pygame.time.get_ticks(), force=True)
        bg = image(self.app, style["bg"])
        self.bg = pygame.transform.smoothscale(bg, (round(bg.get_width() * HEIGHT / bg.get_height()), HEIGHT)) if bg else None
        card = image(self.app, "images/freeplay/pinkBack.png")
        self.card = tint(pygame.transform.smoothscale(card, (self.CARD_W + 40, HEIGHT)), style["tint"]) if card else None

    # ----- données
    def song(self):
        return self.app.data.songs[self.song_ids[self.selected]]

    def _charts_of(self, song) -> list[str]:
        """Difficultés proposées pour le personnage choisi, comme le freeplay officiel :
        côté BF les chansons de BF et les BF Mix (variation « bf »), côté Pico les chansons de Pico et les Pico Mix."""
        keys = sorted(song.charts, key=difficulty_sort_key)
        variation = lambda key: key.partition(":")[2]
        pico_song = "pico" in song.player  # Weekend 1 : Pico est le chanteur de la version de base
        if self.character == "pico":
            return [key for key in keys if variation(key) != "bf"] if pico_song else [key for key in keys if variation(key) == "pico"]
        return [key for key in keys if variation(key) == "bf"] if pico_song else [key for key in keys if variation(key) not in ("pico", "bf")]

    def charts(self) -> list[str]:
        return self._charts_of(self.song()) if self.song_ids else []

    def _order(self) -> list[str]:
        """Ordre d'apparition dans les semaines, puis les chansons hors semaine ; les chansons de mods tout en bas."""
        songs, ordered = self.app.data.songs, []
        for from_mod in (False, True):
            for week in self.app.data.weeks:
                ordered += [song for song in week.songs if song not in ordered and bool(songs[song].mod) == from_mod]
            ordered += sorted((song for song in songs if song not in ordered and bool(songs[song].mod) == from_mod),
                              key=lambda song: songs[song].name.lower())
        return ordered

    def _build_list(self, keep: str | None = None, chart: str | None = None) -> None:
        query = self.query.casefold().strip()
        songs = self.app.data.songs
        self.song_ids = [song for song in self._order() if self._charts_of(songs[song])
                         and (not query or query in songs[song].name.casefold() or query in song)]
        if keep in self.song_ids:
            self.selected = self.song_ids.index(keep)
        else:
            self.selected = min(self.selected, max(0, len(self.song_ids) - 1))
        self._pick_chart(chart)

    def _pick_chart(self, preferred: str | None = None) -> None:
        charts = self.charts()
        if not charts:
            return
        if preferred in charts:
            self.chart_index = charts.index(preferred)
        else:
            same = [index for index, key in enumerate(charts) if key.split(":")[0] == self.difficulty]
            self.chart_index = same[0] if same else min(1, len(charts) - 1)
        self.difficulty = charts[self.chart_index].split(":")[0]

    # ----- entrées
    def _current(self) -> str | None:
        return self.song_ids[self.selected] if self.song_ids else None

    def _search_event(self, event: pygame.event.Event) -> bool:
        """Saisie de la recherche ; renvoie False pour laisser passer les flèches."""
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.typing = False
        elif event.key == pygame.K_ESCAPE:
            self.typing = False; self.query = ""; self._build_list(self._current())
        elif event.key == pygame.K_BACKSPACE:
            self.query = self.query[:-1]; self._build_list(self._current()); self.moved_at = pygame.time.get_ticks()
        elif event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
            return False
        elif event.unicode and event.unicode.isprintable() and len(self.query) < 24:
            self.query += event.unicode; self._build_list(self._current()); self.moved_at = pygame.time.get_ticks()
        return True

    def _modifier_value(self, key: str) -> str:
        modifiers, settings, tr = self.app.modifiers, self.app.settings, self.app.tr
        if key == "scroll":
            value = modifiers.get("scroll", settings.scroll_speed)
            return tr("AUTO") if value <= 0 else f"{value:.1f}"
        if key == "rate":
            return f"x{modifiers.get('rate', 1.0):.2f}"
        if key == "judgment":
            return tr("EASY" if modifiers.get("judgment", settings.judgment) == "easy" else "NORMAL")
        if key == "locked":
            return ""
        return tr("ON" if modifiers.get(key) else "OFF")

    def _adjust_modifier(self, key: str, step: int) -> None:
        modifiers, settings = self.app.modifiers, self.app.settings
        if key == "scroll":
            modifiers["scroll"] = step_scroll(modifiers.get("scroll", settings.scroll_speed), step * .1)
        elif key == "rate":
            modifiers["rate"] = round(min(4.0, max(.5, modifiers.get("rate", 1.0) + step * .05)), 2)
        elif key == "judgment":
            modifiers["judgment"] = "easy" if modifiers.get("judgment", settings.judgment) == "normal" else "normal"
        elif key == "locked":
            self.locked_at = pygame.time.get_ticks()
            self.app.play_sound("sounds/CS_locked.ogg")
            return
        else:
            modifiers[key] = not modifiers.get(key, False)
        self.app.scroll_sound()

    def _active_modifiers(self) -> int:
        defaults = {"scroll": self.app.settings.scroll_speed, "rate": 1.0, "judgment": self.app.settings.judgment}
        return sum(1 for key, value in self.app.modifiers.items() if value != defaults.get(key, False))

    def _panel_event(self, event: pygame.event.Event) -> None:
        key = self.MODIFIERS[self.panel_row][0]
        if event.key in (pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_ESCAPE):
            self.panel_open = False; self.app.cancel_sound()
        elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
            self.panel_row = (self.panel_row + (-1 if event.key in (pygame.K_UP, pygame.K_w) else 1)) % len(self.MODIFIERS)
            self.app.scroll_sound()
        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            self._adjust_modifier(key, -1 if event.key in (pygame.K_LEFT, pygame.K_a) else 1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._adjust_modifier(key, 1)
        elif event.key == pygame.K_r:
            self.app.modifiers = {}; self.app.cancel_sound()

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN or self.confirmed_at:
            return
        if self.typing and self._search_event(event):
            return
        if self.panel_open:
            self._panel_event(event)
            return
        if event.key in (pygame.K_LCTRL, pygame.K_RCTRL):
            self.panel_open = True; self.app.confirm_sound()
        elif event.key == pygame.K_TAB:
            self.character = self.app.freeplay_character = "pico" if self.character == "bf" else "bf"
            current = self._current()
            self._build_list(current)
            self.scroll = float(self.selected)
            self._load_character()
            self.preview_song = ""; self.moved_at = pygame.time.get_ticks(); self.app.confirm_sound()
        elif event.key == pygame.K_f:
            self.typing = True; self.app.scroll_sound()
        elif event.key == pygame.K_ESCAPE:
            if self.query:
                self.query = ""; self._build_list(self._current()); return
            self.app.cancel_sound(); self.app.play_menu_music()
            self.app.change(MainMenuState(self.app, "freeplay"))
        elif not self.song_ids:
            return
        elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
            step = -1 if event.key in (pygame.K_UP, pygame.K_w) else 1
            self.selected = (self.selected + step) % len(self.song_ids)
            self._pick_chart(); self.moved_at = pygame.time.get_ticks(); self.app.scroll_sound()
        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            step = -1 if event.key in (pygame.K_LEFT, pygame.K_a) else 1
            self.chart_index = (self.chart_index + step) % len(self.charts())
            self.difficulty = self.charts()[self.chart_index].split(":")[0]
            self.diff_changed_at = pygame.time.get_ticks(); self.moved_at = self.diff_changed_at; self.app.scroll_sound()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.app.confirm_sound()
            self.confirmed_at = pygame.time.get_ticks()
            self.dj.play("confirm", self.confirmed_at, force=True)

    def update(self, dt: float) -> None:
        now = pygame.time.get_ticks()
        self.scroll = lerp(self.scroll, self.selected, dt, 12)
        self.panel_slide = lerp(self.panel_slide, 1.0 if self.panel_open else 0.0, dt, 14)
        if self.dj.current == "intro" and self.dj.finished(now):
            self.dj.play("idle", now, force=True)
        beat = int(self.app.menu_beat())
        if beat != self.last_beat:
            self.last_beat = beat
            if self.dj.current == "idle" and beat % 2 == 0:
                self.dj.play("idle", now, force=True)
        if self.song_ids:
            target = self.app.settings.scores.get(f"{self.song_ids[self.selected]}|{self.charts()[self.chart_index]}", 0)
            self.shown_score = lerp(self.shown_score, target, dt, 16)
            # Aperçu : l'instru de la chanson choisie démarre après un court arrêt sur la capsule.
            key = f"{self.song_ids[self.selected]}|{self.charts()[self.chart_index].partition(':')[2]}"
            if key != self.preview_song and now - self.moved_at > 500 and not self.confirmed_at:
                self.preview_song = key
                self._preview()
        if self.confirmed_at and now - self.confirmed_at > 1200:
            pygame.mixer.music.stop()
            self.app.start_playlist([self.song_ids[self.selected]], self.charts()[self.chart_index])

    def _preview(self) -> None:
        song = self.song()
        variation = self.charts()[self.chart_index].partition(":")[2]
        folder = self.app.assets.path(f"songs/{song.song_id}")
        path = folder / f"Inst-{variation}.ogg" if variation else folder / "Inst.ogg"
        if not path.is_file():
            path = folder / "Inst.ogg"
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.app.volume * .7)
            pygame.mixer.music.play(-1, start=song.preview_start / 1000, fade_ms=900)
        except pygame.error:
            pass

    # ----- dessin
    def _capsule_icon(self, song) -> pygame.Surface | None:
        key = ("fp-icon", song.song_id)
        if key not in self.app.cache:
            icon = None
            opponent = song.opponent
            for name in (opponent, opponent.split("-")[0], opponent.replace("-christmas", "s-christmas")):
                found = frames(self.app, f"images/freeplay/icons/{name}pixel.png", "idle")
                if found:
                    icon = scale_by(found[0], 1.8, pixel=True)
                    break
            if icon is None:
                health = self.app.icon_frames(opponent)
                icon = pygame.transform.smoothscale(health[0], (80, 80)) if health else None
            self.app.cache[key] = icon
        return self.app.cache[key]

    def _chart_for(self, song) -> str:
        """La difficulté affichée sur une capsule : celle choisie si la chanson l'a, sinon la première (côté BF ou Pico)."""
        charts = self._charts_of(song) or sorted(song.charts, key=difficulty_sort_key)
        same = [key for key in charts if key.split(":")[0] == self.difficulty]
        return same[0] if same else charts[0]

    def _numbers(self, sprite: str, value: int, scale: float) -> list[pygame.Surface]:
        names = ("ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE")
        result = []
        for char in str(max(0, value)):
            found = frames(self.app, f"images/freeplay/freeplayCapsule/{sprite}.png", names[int(char)])
            if found:
                result.append(whiten(scale_by(found[0], scale)))
        return result

    def _draw_capsule_details(self, screen: pygame.Surface, song, x: int, y: int, s: float, selected: bool, now: int) -> None:
        """Icône, titre dans la fente sombre, BPM, difficulté et lettre de notation (mêmes repères que la capsule officielle)."""
        chart = self._chart_for(song)
        profile = song.profiles.get(chart, {})
        icon = self._capsule_icon(song)
        if icon:
            screen.blit(icon, icon.get_rect(center=(x + round(54 * s), y + round(58 * s))))
        color = WHITE if selected else (190, 190, 205)
        if selected and self.confirmed_at and ((now - self.confirmed_at) // 90) % 2:
            color = (130, 255, 255)
        slot = pygame.Rect(x + round(112 * s), y + round(30 * s), round(380 * s), round(56 * s))
        label = fit(self._label(song.name, 30, color), slot.width, slot.height)
        screen.blit(label, label.get_rect(midleft=(slot.x + 4, slot.centery)))
        # Bande du bas : BPM à gauche, difficulté à droite.
        strip_y = y + round(108 * s)
        bpm_label = image(self.app, "images/freeplay/freeplayCapsule/bpmtext.png")
        cursor = x + round(118 * s)
        if bpm_label:
            bpm_label = whiten(scale_by(bpm_label, s))
            screen.blit(bpm_label, bpm_label.get_rect(midleft=(cursor, strip_y)))
            cursor += bpm_label.get_width() + 4
        bpm = round(profile.get("bpm_changes", [(0, song.bpm)])[0][1])
        for digit in self._numbers("smallnumbers", bpm, s):
            screen.blit(digit, digit.get_rect(midleft=(cursor, strip_y)))
            cursor += digit.get_width() - 2
        rating = int(profile.get("rating", 0))
        diff_label = image(self.app, "images/freeplay/freeplayCapsule/difficultytext.png")
        cursor = x + round(318 * s)
        if diff_label:
            diff_label = whiten(scale_by(diff_label, s))
            screen.blit(diff_label, diff_label.get_rect(midleft=(cursor, strip_y)))
            cursor += diff_label.get_width() + 6
        for digit in self._numbers("bignumbers", rating, s * .55):
            screen.blit(digit, digit.get_rect(midleft=(cursor, strip_y - 2)))
            cursor += digit.get_width() - 2
        # Lettre de notation d'après la meilleure précision (rien tant que la chanson n'est pas finie).
        accuracy = self.app.settings.accuracies.get(f"{song.song_id}|{chart}")
        if accuracy is not None:
            grade = grade_letter(accuracy)
            letter = self.app.alphabet(grade, round(70 * s))
            screen.blit(letter, letter.get_rect(center=(x + round(548 * s), y + round(72 * s))))

    def _label(self, text: str, size: int, color) -> pygame.Surface:
        key = ("fp-label", text, size, color)
        if key not in self.app.cache:
            font = self.app.font(size, bold=True)
            face = font.render(text, True, color)
            outline = font.render(text, True, BLACK)
            surface = pygame.Surface((face.get_width() + 6, face.get_height() + 6), pygame.SRCALPHA)
            for ox, oy in ((0, 3), (6, 3), (3, 0), (3, 6), (1, 1), (5, 5), (1, 5), (5, 1)):
                surface.blit(outline, (ox, oy))
            surface.blit(face, (3, 3))
            self.app.cache[key] = surface
        return self.app.cache[key]

    def _digits(self, screen: pygame.Surface, value: int, right: int, y: int) -> int:
        """Score en chiffres digitaux, aligné à droite sur `right`. Renvoie le x de gauche."""
        names = ("ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE")
        now = pygame.time.get_ticks()
        digits = [frame_at(self.digits[names[int(char)]], now / 1000) for char in f"{value:07d}"]
        digits = [scale_by(digit, .28) for digit in digits if digit is not None]
        x = right - sum(digit.get_width() - 4 for digit in digits)
        left = x
        for digit in digits:
            screen.blit(digit, (x, y)); x += digit.get_width() - 4
        return left

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        intro = ease_out((now - self.opened_at) / 450)
        screen.fill((30, 26, 40))
        if self.bg:
            screen.blit(self.bg, (WIDTH - self.bg.get_width(), 0))
            screen.blit(shade(70), (0, 0))
        # Capsules des chansons, en arc, qui glissent depuis la droite à l'ouverture.
        on_frame = frame_at(self.capsule_on, now / 1000) if self.capsule_on else None
        off_frame = frame_at(self.capsule_off, now / 1000) if self.capsule_off else None
        for index in range(len(self.song_ids)):
            offset = index - self.scroll
            if offset < -4 or offset > 5:
                continue
            selected = index == self.selected
            capsule = on_frame if selected else off_frame
            x = 505 + abs(offset) ** 1.3 * 20 + (1 - intro) * 700
            y = 318 + offset * 104
            if y < 70 or y > HEIGHT - 52 - 96:
                continue  # rien sous les barres noires du haut et du bas
            capsule_width = 470
            if capsule:
                capsule = scale_by(capsule, .72)
                capsule_width = capsule.get_width()
                if not selected:
                    capsule.set_alpha(190)
                screen.blit(capsule, (round(x), round(y)))
            song = self.app.data.songs[self.song_ids[index]]
            self._draw_capsule_details(screen, song, round(x), round(y), .72, selected, now)
        # Carte du DJ à gauche.
        card_x = round(-self.CARD_W * (1 - intro))
        if self.card:
            screen.blit(self.card, (card_x - 20, 0))
        self._scrolling_text(screen, card_x, now)
        self.dj.x = card_x + self.dj_left
        self.dj.draw(screen, SCREEN_CAM, 1.0, now)
        if self.song_ids:
            self._draw_album(screen, now)
        self._draw_panel(screen, now)
        # Barre du haut : titre, recherche, record. Barre du bas : touches.
        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, 64))
        self.app.text(screen, "FREEPLAY", (16, 10), 38, bold=True)
        self._draw_search(screen, now)
        pygame.draw.rect(screen, BLACK, (0, HEIGHT - 52, WIDTH, 52))
        hint = ("ENTER OK     ESC CLEAR" if self.typing else
                "↑↓ CHOOSE     ←→ CHANGE     R RESET     CTRL CLOSE" if self.panel_open else
                f"↑↓ SONG     ←→ DIFFICULTY     TAB {'BOYFRIEND' if self.character == 'pico' else 'PICO MIX'}     F SEARCH     CTRL MODIFIERS     ENTER PLAY     ESC BACK")
        key_hints(self.app, screen, hint, HEIGHT - 26, bar=False, size=14)
        if not self.song_ids:
            self.app.text(screen, "NO SONG FOUND" if self.query else "NO SONG AVAILABLE", (WIDTH // 2 + 200, HEIGHT // 2), 40, center=True, bold=True, outline=True)
            return
        # Difficulté + flèches du sélecteur.
        center = (card_x + 255, 118)
        relative = f"images/freeplay/freeplay{self.difficulty}.png"
        if self.app.assets.path(relative[:-4] + ".xml").is_file():
            animated = frames(self.app, relative, "idle") or frames(self.app, relative, "")
            sprite = frame_at(animated, now / 1000) if animated else None
        else:
            sprite = image(self.app, relative)
        drop = ease_out((now - self.diff_changed_at) / 220) if self.diff_changed_at else 1
        half = 110
        if sprite:
            sprite = fit(sprite, 300, 90).copy(); sprite.set_alpha(round(255 * drop))
            half = sprite.get_width() // 2 + 40
            screen.blit(sprite, sprite.get_rect(center=(center[0], round(center[1] - 14 * (1 - drop)))))
        else:
            self.app.text(screen, self.difficulty.upper(), (center[0], center[1] - 24), 40, color=YELLOW, bold=True, center=True, outline=True, raw=True)
        arrow = frame_at(self.selector, now / 1000)
        if arrow:
            arrow = scale_by(arrow, .8)
            screen.blit(arrow, arrow.get_rect(center=(center[0] - half, center[1])))
            screen.blit(pygame.transform.flip(arrow, True, False), arrow.get_rect(center=(center[0] + half, center[1])))
        # Record perso en chiffres digitaux.
        left = self._digits(screen, round(self.shown_score), WIDTH - 14, 13)
        badge = frame_at(self.highscore, now / 1000)
        if badge:
            badge = scale_by(badge, .34)
            screen.blit(badge, badge.get_rect(midright=(left - 10, 32)))

    def _draw_search(self, screen: pygame.Surface, now: int) -> None:
        box = pygame.Rect(250, 13, 330, 38)
        pygame.draw.rect(screen, (34, 34, 42) if not self.typing else (20, 44, 54), box, border_radius=19)
        pygame.draw.rect(screen, CYAN if self.typing else (90, 90, 104), box, 2, border_radius=19)
        # Loupe dessinée.
        pygame.draw.circle(screen, WHITE, (box.x + 22, box.centery - 2), 8, 2)
        pygame.draw.line(screen, WHITE, (box.x + 28, box.centery + 4), (box.x + 34, box.centery + 10), 3)
        if self.query or self.typing:
            caret = "|" if self.typing and (now // 400) % 2 else ""
            self.app.text(screen, self.query + caret, (box.x + 46, box.y + 8), 19, bold=True, raw=True)
        else:
            self.app.text(screen, "F  SEARCH...", (box.x + 46, box.y + 9), 18, color=(150, 150, 165), bold=True)
        count = f"{self.selected + 1 if self.song_ids else 0} / {len(self.song_ids)}"
        self.app.text(screen, count, (box.right + 16, box.y + 8), 20, bold=True, raw=True)
        active = self._active_modifiers()
        if active:
            label = f"{active} {self.app.tr('MODIFIER' if active == 1 else 'MODIFIERS')}"
            self.app.text(screen, label, (box.right + 100, box.y + 9), 17, color=YELLOW, bold=True, raw=True)

    def _draw_album(self, screen: pygame.Surface, now: int) -> None:
        """Pochette de l'album de la chanson (OST Volume 1, 2...) à droite, comme dans le freeplay officiel."""
        charts = self.charts()
        chart = charts[self.chart_index] if charts else ""
        album_id = self.song().profiles.get(chart, {}).get("album") or self.song().album
        if not album_id or self.panel_slide > .95:
            return
        key = ("fp-album", album_id)
        if key not in self.app.cache:
            art = image(self.app, f"images/freeplay/albumRoll/{album_id}.png")
            title = frames(self.app, f"images/freeplay/albumRoll/{album_id}-text.png", "idle")
            art = pygame.transform.rotozoom(art, -8, 1.0) if art else None
            self.app.cache[key] = (art, scale_by(title[0], .9) if title else None)
        art, title = self.app.cache[key]
        moved = ease_out((now - self.moved_at) / 300)
        if art:
            art = art.copy(); art.set_alpha(round(255 * moved))
            screen.blit(art, art.get_rect(center=(1085, round(330 + 18 * (1 - moved)))))
        if title:
            screen.blit(title, title.get_rect(center=(1060, 500)))

    def _draw_panel(self, screen: pygame.Surface, now: int) -> None:
        """Menu Ctrl des modificateurs, qui glisse depuis la droite."""
        if self.panel_slide < .01:
            return
        tr = self.app.tr
        left = round(WIDTH - self.PANEL_W * ease_out(self.panel_slide))
        top, bottom = 64, HEIGHT - 52
        panel = pygame.Surface((self.PANEL_W + 40, bottom - top), pygame.SRCALPHA)
        pygame.draw.polygon(panel, (8, 8, 14, 235), [(40, 0), (self.PANEL_W + 40, 0), (self.PANEL_W + 40, bottom - top), (0, bottom - top)])
        pygame.draw.line(panel, CYAN, (40, 0), (0, bottom - top), 4)
        screen.blit(panel, (left - 40, top))
        title = fit(self.app.alphabet(tr("MODIFIERS"), 46), self.PANEL_W - 50, 60)
        screen.blit(title, (left + 30, top + 18))
        lock = image(self.app, "images/storymenu/ui/lock.png")
        for row, (key, label, _) in enumerate(self.MODIFIERS):
            y = top + 100 + row * 56
            selected = row == self.panel_row and self.panel_open
            shake = round(math.sin(now / 25) * 6) if key == "locked" and now - self.locked_at < 300 else 0
            if selected:
                bar = pygame.Surface((self.PANEL_W - 30, 46), pygame.SRCALPHA)
                bar.fill((0, 220, 255, 45))
                screen.blit(bar, (left + 16, y - 6))
                pygame.draw.rect(screen, CYAN, (left + 16, y - 6, 5, 46))
            color = (120, 120, 132) if key == "locked" else WHITE if selected else (200, 200, 212)
            x = left + 34 + shake
            if key == "locked" and lock:
                icon = fit(lock, 30, 30)
                screen.blit(icon, icon.get_rect(midleft=(x, y + 17)))
                x += 40
            self.app.text(screen, label, (x, y + 4), 21, color=color, bold=True)
            value = self._modifier_value(key)
            if key in ("opponent", "practice", "botplay"):
                on = bool(self.app.modifiers.get(key))
                pill = pygame.Rect(0, 0, 58, 28); pill.midright = (left + self.PANEL_W - 30, y + 17)
                pygame.draw.rect(screen, (60, 200, 90) if on else (70, 70, 82), pill, border_radius=14)
                pygame.draw.circle(screen, WHITE, (pill.right - 14 if on else pill.x + 14, pill.centery), 11)
            elif value:
                text_color = CYAN if selected else WHITE
                self.app.text(screen, value, (left + self.PANEL_W - 30, y + 4), 21, color=text_color, bold=True, right=True, raw=True)
                if selected:
                    width = self.app.font(21, True).size(value)[0]
                    for direction, ax in ((-1, left + self.PANEL_W - 44 - width), (1, left + self.PANEL_W - 18)):
                        pygame.draw.polygon(screen, CYAN, [(ax + direction * 8, y + 17), (ax, y + 9), (ax, y + 25)])
        description = self.MODIFIERS[self.panel_row][2]
        lines = textwrap.wrap(tr(description), 40)
        for index, line in enumerate(lines[:3]):
            self.app.text(screen, line, (left + 34, bottom - 92 + index * 24), 18, color=(190, 190, 205), raw=True)

    def _scrolling_text(self, screen: pygame.Surface, card_x: int, now: int) -> None:
        if not self.card:
            return
        layer = pygame.Surface(self.card.get_size(), pygame.SRCALPHA)
        rows = self.CHARACTERS[self.character]["rows"]
        for row, (text, size, color, speed) in enumerate(rows):
            image_text = self.app.cache.get(("fp-row", text, size))
            if image_text is None:
                font = self.app.font(size, bold=True)
                image_text = font.render(text + "   ", True, color)
                image_text.set_alpha(120 if size > 40 else 170)
                self.app.cache[("fp-row", text, size)] = image_text
            y = 175 + row * 120
            x = (now * speed) % image_text.get_width() - image_text.get_width()
            while x < layer.get_width():
                layer.blit(image_text, (x, y)); x += image_text.get_width()
        if "fp-card-mask" not in self.app.cache:
            mask = self.card.copy()
            mask.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
            self.app.cache["fp-card-mask"] = mask
        layer.blit(self.app.cache["fp-card-mask"], (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        screen.blit(layer, (card_x - 20, 0))


# ------------------------------------------------------------ listes ----
class ListMenu(BaseState):
    """Base des menus en liste (options, mods, succès, outils) : fond teinté + police alphabet de FNF."""

    TINT = (234, 113, 253)
    TITLE = ""

    def __init__(self, app):
        super().__init__(app)
        self.selected = 0
        self.scroll = 0.0
        self.message = ""
        self.message_at = 0

    def entries(self) -> list:
        return []

    def notify(self, text: str) -> None:
        self.message, self.message_at = text, pygame.time.get_ticks()

    def background(self, screen: pygame.Surface) -> None:
        screen.fill(BLACK)  # l'image de fond a de la transparence : sans ça l'écran précédent transparaît
        screen.blit(self.app.menu_bg(self.TINT), (0, 0))

    def move(self, step: int) -> None:
        count = len(self.entries())
        if count:
            self.selected = (self.selected + step) % count
            self.app.scroll_sound()

    def update(self, dt: float) -> None:
        self.scroll = lerp(self.scroll, self.selected, dt, 12)

    def draw_rows(self, screen: pygame.Surface, labels: list[str], x: int = 120, height: int = 62,
                  spacing: int = 96, center_y: int = 330, icons: list | None = None, dim: list[bool] | None = None,
                  max_width: int = 1100) -> None:
        for index, label in enumerate(labels):
            offset = index - self.scroll
            y = center_y + offset * spacing
            if y < -80 or y > HEIGHT + 80:
                continue
            selected = index == self.selected
            text = fit(self.app.alphabet(label, height), max_width, height + 20)
            if dim and dim[index]:
                text = tint(text, (150, 150, 150))
            text = text.copy()
            text.set_alpha(255 if selected else 140)
            row_x = x + (30 if selected else 0) + round(abs(offset) * 12)
            if icons and icons[index] is not None:
                icon = icons[index]
                screen.blit(icon, icon.get_rect(midleft=(row_x, round(y))))
                row_x += icon.get_width() + 16
            screen.blit(text, text.get_rect(midleft=(row_x, round(y))))

    def draw_footer(self, screen: pygame.Surface, hint: str, description: str = "") -> None:
        bar = pygame.Surface((WIDTH, 92), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 170))
        screen.blit(bar, (0, HEIGHT - 92))
        if description:
            self.app.text(screen, description, (WIDTH // 2, HEIGHT - 84), 22, center=True, raw=True)
        key_hints(self.app, screen, hint, HEIGHT - 30, bar=False)
        if self.message and pygame.time.get_ticks() - self.message_at < 3500:
            self.app.text(screen, self.message, (WIDTH // 2, HEIGHT - 130), 26, center=True, color=YELLOW, bold=True, outline=True, raw=True)

    def title(self, screen: pygame.Surface, text: str) -> None:
        title = self.app.alphabet(self.app.tr(text), 74)
        screen.blit(title, (40, 24))


# ------------------------------------------------------------ options ----
class OptionsState(ListMenu):
    TINT = (234, 113, 253)

    def __init__(self, app):
        super().__init__(app)
        s = app.settings
        # (libellé, type, description) ; les valeurs sont lues/écrites dans les réglages.
        self.items = [
            ("LANGUAGE", "language", ""),
            ("VOLUME", "volume", ""),
            ("SCROLL SPEED", "scroll", "AUTO: speed chosen by each song. Otherwise every chart uses exactly this speed."),
            ("JUDGMENT", "judgment", "NORMAL: a GOOD counts 75 %. EASY: GOOD counts 100 %."),
            ("NOTE OFFSET", "offset", "Delay between the music and the notes (+ = notes later)."),
            ("AUDIO CALIBRATION", "calibration", "Measure the delay of your audio by tapping along with BF's voice."),
            ("CONTROLS", "controls", "Change the 4 note keys."),
            ("DOWNSCROLL", "downscroll", "Notes come from the top and the receptors are at the bottom."),
            ("GHOST TAPPING", "ghost_tapping", "Pressing a key with no note doesn't count as a miss."),
            ("HITSOUNDS", "hitsounds", "A click plays each time you hit a note."),
            ("HITSOUND VOLUME", "hitsound_volume", "Volume of the hitsounds."),
            ("FLASHING LIGHTS", "flashing_lights", "Mods may use flashes; turn off if they bother you."),
            ("CAMERA ZOOMS", "camera_zooms", "The camera and the interface bump to the beat, like the original game."),
            ("SUBTITLES", "subtitles", "Subtitles on cutscenes, in the language of the game."),
            ("CHILD MODE", "child_mode", "Censors violent or crude lines in dialogues and cutscenes."),
            ("FPS LIMIT", "fps", "Maximum frames per second."),
            ("DISPLAY QUALITY", "quality", "HIGH: smooth image when the window is enlarged. PIXELS: sharp pixels."),
            ("FULLSCREEN", "fullscreen", "Play in fullscreen (also F11)."),
            ("SHOW FPS", "show_fps", ""),
            ("CLEAR DATA", "clear_data", "Erases every score and rank of every song and week (asks first)."),
        ]
        self.settings = s
        self.check_unselected = frames(app, "images/checkboxThingie.png", "Check Box unselected")
        self.check_anim = frames(app, "images/checkboxThingie.png", "Check Box selecting animation")
        self.toggled_at: dict[str, int] = {}

    def entries(self) -> list:
        return self.items

    def value(self, kind: str) -> str:
        s = self.settings
        if kind == "language":
            return "FRANÇAIS" if s.language == "fr" else "ENGLISH"
        if kind == "volume":
            return f"{round(self.app.volume * 100)}%"
        if kind == "scroll":
            return self.app.tr("AUTO") if s.scroll_speed <= 0 else f"{s.scroll_speed:.1f}"
        if kind == "judgment":
            return self.app.tr("EASY" if s.judgment == "easy" else "NORMAL")
        if kind == "hitsound_volume":
            return f"{round(s.hitsound_volume * 100)}%"
        if kind == "fps":
            return self.app.tr("UNLIMITED") if s.fps_limit == 0 else str(s.fps_limit)
        if kind == "quality":
            return self.app.tr("HIGH" if s.quality == "high" else "PIXELS")
        if kind == "offset":
            return f"{s.offset_ms:+d} ms"
        return ""

    def adjust(self, kind: str, step: int, big: bool) -> None:
        s = self.settings
        if kind == "language":
            s.language = "fr" if s.language == "en" else "en"
        elif kind == "volume":
            self.app.volume = round(min(1, max(0, self.app.volume + step * .05)), 2)
            s.volume = self.app.volume
            pygame.mixer.music.set_volume(self.app.volume)
        elif kind == "scroll":
            s.scroll_speed = step_scroll(s.scroll_speed, step * (.5 if big else .1))
        elif kind == "judgment":
            s.judgment = "easy" if s.judgment == "normal" else "normal"
        elif kind == "quality":
            s.quality = "pixel" if s.quality == "high" else "high"
            self.app.apply_display_quality(reopen=True)
        elif kind == "hitsound_volume":
            s.hitsound_volume = round(min(1, max(0, s.hitsound_volume + step * .1)), 2)
            self.app.play_sound("sounds/hitsound.mp3", s.hitsound_volume)
        elif kind == "fps":
            index = FPS_CHOICES.index(s.fps_limit) if s.fps_limit in FPS_CHOICES else 1
            s.fps_limit = FPS_CHOICES[(index + step) % len(FPS_CHOICES)]
        elif kind == "offset":
            s.offset_ms = max(-500, min(500, s.offset_ms + step * (10 if big else 1)))
        else:
            return
        s.save()
        self.app.scroll_sound()

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        kind = self.items[self.selected][1]
        if getattr(self, "confirm_clear", False):  # « Êtes-vous sûr ? » : Entrée efface, Échap annule
            self.confirm_clear = False
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                s = self.settings
                s.scores.clear(); s.accuracies.clear(); s.save()
                self.app.confirm_sound(); self.notify(self.app.tr("ALL SCORES ERASED"))
            else:
                self.app.cancel_sound()
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.move(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.move(1)
        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            self.adjust(kind, -1 if event.key in (pygame.K_LEFT, pygame.K_a) else 1, bool(event.mod & pygame.KMOD_SHIFT))
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if kind == "clear_data":
                self.confirm_clear = True; self.app.scroll_sound()
            elif kind == "calibration":
                self.app.change(CalibrationState(self.app))
            elif kind == "controls":
                self.app.change(ControlsState(self.app))
            elif kind in ("language", "judgment", "quality"):
                self.adjust(kind, 1, False)
            elif kind == "fullscreen":
                self.app.set_fullscreen(not self.app.is_fullscreen)
                self.toggled_at[kind] = pygame.time.get_ticks()
                self.settings.save(); self.app.confirm_sound()
            elif isinstance(getattr(self.settings, kind, None), bool):
                setattr(self.settings, kind, not getattr(self.settings, kind))
                self.toggled_at[kind] = pygame.time.get_ticks()
                self.settings.save(); self.app.confirm_sound()
        elif event.key == pygame.K_ESCAPE:
            self.settings.save(); self.app.cancel_sound(); self.app.change(MainMenuState(self.app, "options"))

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        self.background(screen)
        labels = [self.app.tr(label) for label, _, _ in self.items]
        icons = []
        for _, kind, _ in self.items:
            if isinstance(getattr(self.settings, kind, None), bool):
                checked = getattr(self.settings, kind)
                if checked:
                    sequence = self.check_anim
                    frame = frame_at(sequence, (now - self.toggled_at.get(kind, 0)) / 1000, 24, loop=False) if kind in self.toggled_at else (sequence[-1] if sequence else None)
                else:
                    frame = self.check_unselected[0] if self.check_unselected else None
                icons.append(scale_by(frame, .42) if frame else None)
            else:
                icons.append(None)
        self.draw_rows(screen, labels, x=90, height=46, spacing=72, center_y=330, icons=icons)
        for index, (_, kind, _) in enumerate(self.items):
            value = self.value(kind)
            if value and abs(index - self.scroll) < 5:
                y = 330 + (index - self.scroll) * 72
                selected = index == self.selected
                text = self.app.alphabet(value, 40)
                text = text.copy(); text.set_alpha(255 if selected else 140)
                screen.blit(text, text.get_rect(midright=(WIDTH - 60, round(y))))
                if selected and kind not in ("language", "judgment", "quality"):
                    self.app.text(screen, "<", (WIDTH - 80 - text.get_width() - 20, round(y) - 18), 30, bold=True, color=YELLOW, outline=True)
        self.title(screen, "OPTIONS")
        self.draw_footer(screen, "↑↓ SELECT     ←→ CHANGE     ENTER OPEN     ESC BACK", self.app.tr(self.items[self.selected][2]))
        if getattr(self, "confirm_clear", False):
            screen.blit(shade(200), (0, 0))
            question = fit(self.app.alphabet(self.app.tr("ARE YOU SURE?"), 80), WIDTH - 120, 100)
            screen.blit(question, question.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 70)))
            self.app.text(screen, "Every score and rank will be erased. This cannot be undone.", (WIDTH // 2, HEIGHT // 2 + 10), 24,
                          center=True, bold=True, outline=True)
            key_hints(self.app, screen, "ENTER YES, ERASE     ESC NO", HEIGHT // 2 + 90, bar=False, size=20)


class ControlsState(BaseState):
    """Options > Touches, façon FNF : une ligne par flèche, colonne CLAVIER et colonne MANETTE."""
    RESERVED = (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_r, pygame.K_7, pygame.K_LSHIFT, pygame.K_RSHIFT,
                pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_LALT, pygame.K_RALT)
    COLUMNS = (660, 1010)

    def __init__(self, app):
        super().__init__(app)
        self.selected = 0  # flèche
        self.column = 0  # 0 = clavier, 1 = manette
        self.listening = False
        self.listen_at = 0
        strums = sparrow(app, "shared/images/noteStrumline.png")
        self.arrows = [fit(strums.animation(f"static{d.title()}0")[0], 92, 92) if strums else None for d in ("left", "down", "up", "right")]
        self.confirm = [fit(strums.animation(f"confirm{d.title()}0")[0], 118, 118) if strums else None for d in ("left", "down", "up", "right")]

    @property
    def pad_listening(self) -> bool:
        return self.listening and self.column == 1

    def pad_button(self, button: int) -> None:
        """Appelé par Gamepads quand on attend un bouton de manette."""
        self.listening = False
        if button in gamepad.RESERVED:  # Start / Select / Home restent la pause
            self.app.cancel_sound()
            return
        self.app.settings.bind_pad(self.selected, button); self.app.confirm_sound()

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if self.listening:
            if event.key == pygame.K_ESCAPE:
                self.listening = False; self.app.cancel_sound()
            elif self.column == 0 and event.key not in self.RESERVED:
                # Échap/Entrée/R/7 pilotent la pause, le restart et l'éditeur : pas sur une note.
                self.app.settings.bind(self.selected, event.key)
                self.listening = False; self.app.confirm_sound()
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - 1) % 4; self.app.scroll_sound()
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 1) % 4; self.app.scroll_sound()
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
            self.column = 1 - self.column; self.app.scroll_sound()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.listening = True; self.listen_at = pygame.time.get_ticks(); self.app.confirm_sound()
        elif event.key == pygame.K_r:
            self.app.settings.reset_binds(); self.app.confirm_sound()
        elif event.key == pygame.K_ESCAPE:
            self.app.change(OptionsState(self.app)); self.app.cancel_sound()

    def label(self, value: str, height: int) -> pygame.Surface:
        """Nom de touche en lettres FNF ; police normale si un caractère n'existe pas dans l'alphabet (; [ ...)."""
        value = value.upper()
        if all(char.isascii() and (char.isalnum() or char in " -.+/") for char in value):
            return self.app.alphabet(value, height)
        font = self.app.font(round(height * .8), True)
        image = font.render(value, True, WHITE)
        canvas = pygame.Surface((image.get_width() + 6, image.get_height() + 6), pygame.SRCALPHA)
        shadow = font.render(value, True, BLACK)
        for ox, oy in ((0, 3), (6, 3), (3, 0), (3, 6)):
            canvas.blit(shadow, (ox, oy))
        canvas.blit(image, (3, 3))
        return canvas

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        screen.fill(BLACK)
        screen.blit(self.app.menu_bg((120, 140, 255)), (0, 0))
        screen.blit(self.app.alphabet(self.app.tr("CONTROLS"), 74), (40, 24))
        for column, name in enumerate(("KEYBOARD", "CONTROLLER")):
            head = fit(self.app.alphabet(self.app.tr(name), 44), 330, 50).copy()
            head.set_alpha(255 if column == self.column else 110)
            screen.blit(head, head.get_rect(center=(self.COLUMNS[column], 165)))
        for lane in range(4):
            y = 255 + lane * 95
            row = lane == self.selected
            arrow = (self.confirm if row else self.arrows)[lane]
            if arrow:
                screen.blit(arrow, arrow.get_rect(center=(110, y)))
            name = fit(self.app.alphabet(self.app.tr(LANE_NAMES[lane]), 50), 280, 56).copy()
            name.set_alpha(255 if row else 110)
            screen.blit(name, name.get_rect(midleft=(180, y)))
            values = (pygame.key.name(self.app.settings.keybinds[lane]), gamepad.button_name(self.app.settings.pad_binds[lane]))
            for column, value in enumerate(values):
                cell = row and column == self.column
                if cell and self.listening:
                    if (now - self.listen_at) // 300 % 2:
                        continue  # « ? » qui clignote en attendant la touche
                    value = "?"
                image = fit(self.label(value, 80 if value == "?" else 50), 300, 80 if value == "?" else 56).copy()
                image.set_alpha(255 if cell else 150 if row else 80)
                rect = image.get_rect(center=(self.COLUMNS[column], y))
                screen.blit(image, rect)
                if cell and not self.listening:
                    for side, x in (("<", rect.left - 34), (">", rect.right + 34)):
                        mark = self.app.alphabet(side, 40)
                        screen.blit(mark, mark.get_rect(center=(x + round(math.sin(now / 160) * 5) * (1 if side == ">" else -1), y)))
        if self.listening:
            prompt = "PRESS A CONTROLLER BUTTON..." if self.column else "PRESS A KEY..."
            self.app.text(screen, prompt, (WIDTH // 2, 608), 26, center=True, bold=True, color=YELLOW, outline=True)
        else:
            self.app.text(screen, "D-pad and left stick always work too. Start = pause.", (WIDTH // 2, 612), 20, center=True, bold=True, outline=True)
        key_hints(self.app, screen, "↑↓←→ SELECT     ENTER CHANGE     R RESET     ESC BACK", HEIGHT - 30)


class CalibrationState(BaseState):
    BEAT_MS = 500
    VOICE_ATTACK_MS = 6  # mesuré sur bfBeep.ogg

    def __init__(self, app):
        super().__init__(app)
        pygame.mixer.music.stop()
        now = pygame.time.get_ticks()
        self.first_beat = now + 1400
        # La voix de BF (week7/sounds/bfBeep.ogg) sur chaque temps au lieu du bip du métronome.
        voice = app.assets.path("week7/sounds/bfBeep.ogg")
        path = voice if voice.is_file() else app.assets.path("sounds/chartingSounds/metronome1.ogg")
        self.tick = app.assets.sound(path) if path.is_file() else None
        self.tick_lead = self.VOICE_ATTACK_MS if voice.is_file() else 0  # la voix part un peu avant le temps : son attaque tombe dessus
        self.next_tick = self.first_beat - self.tick_lead
        self.next_beat = self.first_beat
        self.last_beat = self.first_beat - self.BEAT_MS
        self.samples: list[int] = []
        self.applied_flash = 0
        arrow, receptor = image(app, "shared/images/latencyArrow.png"), image(app, "shared/images/latencyReceptor.png")
        self.arrow = fit(arrow, 118, 118) if arrow else None
        self.receptor = fit(receptor, 118, 118) if receptor else None
        self.small = fit(arrow, 40, 40) if arrow else None
        self.small_off = tint(self.small, (70, 70, 90)) if self.small else None
        self.taps: list[tuple[int, int]] = []  # (heure, écart en ms) : chiffres qui s'envolent au-dessus du récepteur

    @property
    def suggestion(self) -> int:
        if not self.samples:
            return self.app.settings.offset_ms
        return max(-500, min(500, round(statistics.median(self.samples[-12:]))))

    def apply(self, now: int) -> None:
        self.app.settings.offset_ms = self.suggestion
        self.app.settings.save()
        self.applied_flash = now
        self.app.unlock("in-sync")

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        now = pygame.time.get_ticks()
        tap_keys = {pygame.K_SPACE, *self.app.settings.keybinds}
        if event.key in tap_keys and now >= self.first_beat - 250:
            nearest = self.first_beat + round((now - self.first_beat) / self.BEAT_MS) * self.BEAT_MS
            error = now - nearest
            if abs(error) <= 250:
                self.samples.append(error)
                self.taps = self.taps[-5:] + [(now, error)]
                if len(self.samples) >= 8:
                    self.apply(now)
            return
        if event.key == pygame.K_RETURN and len(self.samples) >= 4:
            self.apply(now)
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            step = 10 if event.mod & pygame.KMOD_SHIFT else 1
            self.app.settings.offset_ms = max(-500, min(500, self.app.settings.offset_ms + (-step if event.key == pygame.K_LEFT else step)))
            self.app.settings.save()
        elif event.key == pygame.K_c:
            self.samples.clear()
        elif event.key == pygame.K_ESCAPE:
            self.app.settings.save(); self.app.play_menu_music(); self.app.change(OptionsState(self.app))

    def update(self, dt: float) -> None:
        now = pygame.time.get_ticks()
        while now >= self.next_tick:
            if self.tick:
                self.tick.set_volume(self.app.volume); self.tick.play()
            self.next_tick += self.BEAT_MS
        while now >= self.next_beat:
            self.last_beat = self.next_beat
            self.next_beat += self.BEAT_MS

    RECEPTOR_X, LANE_Y, SPEED = 300, 300, .6  # vitesse des flèches en pixels par ms

    def value(self, label: str, value: str, center: tuple[int, int], color: tuple[int, int, int] | None) -> None:
        """Libellé en petites lettres FNF, valeur en grosses lettres FNF (teintée)."""
        head = self.app.alphabet(self.app.tr(label), 34).copy()
        head.set_alpha(170)
        screen = self.app.screen
        screen.blit(head, head.get_rect(midbottom=(center[0], center[1] - 6)))
        big = bitmap_text(self.app, value, 58, color or WHITE)
        screen.blit(big, big.get_rect(midtop=(center[0], center[1] + 4)))

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        screen.fill(BLACK)
        screen.blit(self.app.menu_bg((90, 80, 160)), (0, 0))
        screen.blit(self.app.alphabet(self.app.tr("AUDIO CALIBRATION"), 64), (40, 24))
        lane = pygame.Surface((WIDTH, 150), pygame.SRCALPHA)
        lane.fill((0, 0, 0, 110))
        screen.blit(lane, (0, self.LANE_Y - 75))
        # Récepteur officiel qui grossit sur chaque clic ; flèches qui arrivent dessus pile sur le temps.
        pulse = max(0.0, 1 - abs(now - self.last_beat) / 140)
        if self.receptor:
            size = round(118 * (1 + .12 * pulse))
            receptor = pygame.transform.smoothscale(self.receptor, (size, size))
            screen.blit(receptor, receptor.get_rect(center=(self.RECEPTOR_X, self.LANE_Y)))
        if self.arrow and now >= self.first_beat - 2000:
            beat = max(self.first_beat, self.last_beat)
            while True:
                x = self.RECEPTOR_X + (beat - now) * self.SPEED
                if x > WIDTH + 80:
                    break
                if x > self.RECEPTOR_X - 60:
                    arrow = self.arrow.copy()
                    arrow.set_alpha(255 if x >= self.RECEPTOR_X else max(0, round(255 * (x - self.RECEPTOR_X + 60) / 60)))
                    screen.blit(arrow, arrow.get_rect(center=(round(x), self.LANE_Y)))
                beat += self.BEAT_MS
        # Chaque frappe : son écart en ms qui monte et disparaît (vert = dans le temps, jaune = un peu à côté).
        for at, error in self.taps:
            age = now - at
            if age > 900:
                continue
            color = (120, 255, 120) if abs(error) <= 30 else (255, 220, 60) if abs(error) <= 80 else (255, 110, 110)
            label = bitmap_text(self.app, f"{error:+d} ms", 38, color).copy()
            label.set_alpha(round(255 * (1 - age / 900)))
            screen.blit(label, label.get_rect(center=(self.RECEPTOR_X, self.LANE_Y - 100 - age // 12)))
        self.app.text(screen, "TAP SPACE OR YOUR NOTE KEYS WHEN THE ARROW HITS THE RECEPTOR", (WIDTH // 2, self.LANE_Y + 90), 20,
                      center=True, bold=True, outline=True)
        # 8 petites flèches = 8 frappes pour le calibrage automatique.
        if self.small:
            count = min(8, len(self.samples))
            for index in range(8):
                icon = self.small if index < count else self.small_off
                screen.blit(icon, icon.get_rect(center=(WIDTH // 2 - 175 + index * 50, 455)))
        measured = f"{self.suggestion:+d} ms" if self.samples else "-- ms"
        self.value("MEASURED OFFSET", measured, (WIDTH // 2 - 280, 540), (120, 230, 255))
        self.value("CURRENT OFFSET", f"{self.app.settings.offset_ms:+d} ms", (WIDTH // 2 + 280, 540), (255, 220, 60))
        if now - self.applied_flash < 900:
            self.app.text(screen, "AUTO CALIBRATION APPLIED", (WIDTH // 2, 628), 22, center=True, bold=True, color=(120, 255, 120), outline=True)
        key_hints(self.app, screen, "SPACE TAP     ←→ ADJUST (SHIFT = 10 ms)     ENTER APPLY     C CLEAR     ESC BACK", HEIGHT - 30)


# ---------------------------------------------------------------- mods ----
class ModsState(ListMenu):
    TINT = (110, 150, 255)

    def __init__(self, app):
        super().__init__(app)
        self.changed = False
        self.icons: dict[Path, pygame.Surface | None] = {}

    def entries(self) -> list:
        return self.app.mods

    def icon(self, path: Path | None, size: int = 64) -> pygame.Surface | None:
        if path is None:
            return None
        key = (path, size)
        if key not in self.icons:
            try:
                self.icons[key] = pygame.transform.smoothscale(pygame.image.load(path).convert_alpha(), (size, size))
            except (pygame.error, OSError):
                self.icons[key] = None
        return self.icons[key]

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        mods = self.app.mods
        if event.key == pygame.K_ESCAPE:
            self.app.cancel_sound()
            if self.changed:
                self.app.loading_screen("RELOADING MODS...")
                self.app.reload_mods()
            self.app.change(MainMenuState(self.app, "mods"))
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.move(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.move(1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and mods:
            mod = mods[self.selected]
            if mod.error:
                self.notify(self.app.tr("CAN'T ENABLE") + f": {mod.error}"); self.app.cancel_sound(); return
            mod.enabled = not mod.enabled
            disabled = set(self.app.settings.disabled_mods)
            (disabled.discard if mod.enabled else disabled.add)(mod.folder)
            self.app.settings.disabled_mods = sorted(disabled)
            self.app.settings.save()
            self.changed = True
            self.app.confirm_sound()
        elif event.key == pygame.K_n:
            target = create_template()
            self.app.mods = discover(self.app.settings.disabled_mods)
            self.selected = next((index for index, mod in enumerate(self.app.mods) if mod.folder == target.name), 0)
            self.changed = True
            self.app.unlock("modder")
            self.notify(f"{self.app.tr('CREATED')} mods/{target.name} - {self.app.tr('SEE THE PDF GUIDE')}")
            self.app.confirm_sound()
        elif event.key == pygame.K_o:
            try:
                os.startfile(mods_dir())
            except (OSError, AttributeError):
                self.notify(str(mods_dir()))
        elif event.key == pygame.K_h:
            from .help import open_help
            open_help(self.app, self)
        elif event.key == pygame.K_F5:
            self.app.loading_screen("RELOADING MODS...")
            self.app.reload_mods(); self.changed = False
            self.selected = min(self.selected, max(0, len(self.app.mods) - 1))
            self.notify(self.app.tr("MODS RELOADED"))

    def draw(self, screen: pygame.Surface) -> None:
        self.background(screen)
        mods = self.app.mods
        if mods:
            labels = [mod.name for mod in mods]
            icons = [self.icon(mod.icon) for mod in mods]
            self.draw_rows(screen, labels, x=50, height=46, spacing=86, center_y=320, icons=icons,
                           dim=[not mod.enabled for mod in mods], max_width=560)
            mod = mods[self.selected]
            panel = pygame.Rect(760, 104, 480, 480)
            top = window(self.app, screen, panel, "Mod info")
            big = self.icon(mod.icon, 112)
            if big:
                frame = pygame.Rect(panel.x + 16, top + 4, 120, 120)
                pygame.draw.rect(screen, WHITE, frame)
                pygame.draw.rect(screen, UI_BORDER, frame, 1)
                screen.blit(big, big.get_rect(center=frame.center))
            text_x = panel.x + (152 if big else 16)
            self.app.text(screen, mod.name[:24], (text_x, top + 10), 22, bold=True, color=UI_TEXT, raw=True)
            by = f"v{mod.version}" + (f"  •  {self.app.tr('by')} {mod.author}" if mod.author else "")
            self.app.text(screen, by, (text_x, top + 44), 16, color=UI_MUTED, raw=True)
            state = "ERROR" if mod.error else "ON" if mod.enabled else "OFF"
            badge_color = (200, 40, 60) if mod.error else (46, 160, 90) if mod.enabled else (130, 130, 140)
            badge = pygame.Rect(text_x, top + 76, 120, 30)
            pygame.draw.rect(screen, badge_color, badge)
            self.app.text(screen, state, (badge.centerx, badge.y + 5), 16, bold=True, color=WHITE, center=True)
            body = top + 140
            pygame.draw.line(screen, UI_BORDER, (panel.x + 12, body - 10), (panel.right - 12, body - 10))
            lines = []
            for paragraph in (mod.description or self.app.tr("No description.")).splitlines():
                lines += textwrap.wrap(paragraph, 48) or [""]
            problems = self.app.data.warnings.get(mod.root, []) if mod.enabled else []
            rows(self.app, screen, panel.x + 16, body, lines[:9 if not problems else 3], size=17, gap=25)
            if problems:  # pourquoi une semaine ou une chanson du mod est ignorée
                y = body + 3 * 25 + 6
                fr = self.app.settings.language == "fr"
                for problem in problems[:4]:
                    for line in textwrap.wrap(problem[0] if fr else problem[1], 58)[:3]:
                        if y < panel.bottom - 72:
                            self.app.text(screen, line, (panel.x + 16, y), 14, color=(200, 40, 60), raw=True); y += 19
                    y += 4
            if mod.error:
                self.app.text(screen, mod.error[:52], (panel.x + 16, panel.bottom - 64), 15, color=(200, 40, 60), raw=True)
            self.app.text(screen, f"mods/{mod.folder}", (panel.x + 16, panel.bottom - 32), 15, color=UI_MUTED, raw=True)
        else:
            self.app.text(screen, "NO MOD FOUND", (WIDTH // 2, 290), 44, center=True, bold=True, outline=True)
            self.app.text(screen, "Put a mod folder or .zip in the mods folder, or press N to create one.", (WIDTH // 2, 360), 24, center=True, outline=True)
        self.title(screen, "MODS")
        self.draw_footer(screen, "ENTER ON/OFF     N NEW MOD     O OPEN FOLDER     F5 RELOAD     H HELP     ESC BACK")


# -------------------------------------------------------------- succès ----
class AchievementsState(ListMenu):
    TINT = (255, 196, 92)

    def __init__(self, app):
        super().__init__(app)
        app.settings.trophies_seen = len(app.settings.achievements)  # le point rouge du trophee s'efface
        app.settings.save()

    def entries(self) -> list:
        return self.app.achievements

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.move(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.move(1)
        elif event.key == pygame.K_ESCAPE:
            self.app.cancel_sound(); self.app.change(MainMenuState(self.app, "trophies"))

    def draw(self, screen: pygame.Surface) -> None:
        self.background(screen)
        unlocked = set(self.app.settings.achievements)
        labels, icons, dim = [], [], []
        for item in self.app.achievements:
            got = item.id in unlocked
            labels.append(self.app.achievement_name(item) if got or not item.hidden else "???")
            icon = self.app.achievement_icon(item, 84)
            if icon is not None and not got:
                icon = tint(icon, (40, 40, 50))
            icons.append(icon)
            dim.append(not got)
        self.draw_rows(screen, labels, x=70, height=52, spacing=104, center_y=320, icons=icons, dim=dim)
        self.title(screen, "TROPHIES")
        count = sum(item.id in unlocked for item in self.app.achievements)
        self.app.text(screen, f"{count} / {len(self.app.achievements)}", (WIDTH - 40, 40), 40, right=True, bold=True, outline=True, raw=True)
        if self.app.achievements:
            item = self.app.achievements[self.selected]
            description = self.app.achievement_description(item) if item.id in unlocked or not item.hidden else "???"
            if item.mod:
                description += f"   [{item.mod}]"
            self.draw_footer(screen, "↑↓ SELECT     ESC BACK", description)


def news_blocks(app, item: dict, width: int, size: int, pic_height: int) -> list[tuple[pygame.Surface, int]]:
    """Annonce mise en page : liste de (surface, décalage x). Image d'en-tête, titres « # », puces « - », images « @img »."""
    key = ("news-blocks", item["id"], app.settings.language, width, size, pic_height)
    if key in app.cache:
        return app.cache[key]
    blocks: list[tuple[pygame.Surface, int]] = []

    def picture(relative: str) -> None:
        source = image(app, relative)
        if source:
            pic = fit(source, width, pic_height).copy()
            pygame.draw.rect(pic, UI_TEXT, pic.get_rect(), 2)
            if blocks:
                blocks.append((pygame.Surface((1, 8), pygame.SRCALPHA), 0))
            blocks.append((pic, (width - pic.get_width()) // 2))
            blocks.append((pygame.Surface((1, 12), pygame.SRCALPHA), 0))

    def wrap(text: str, text_size: int, bold: bool, indent: int) -> None:
        font, line = app.font(text_size, bold), ""
        for word in text.split():
            candidate = f"{line} {word}".strip()
            if line and font.size(candidate)[0] > width - indent:
                blocks.append((rich_text(app, line, text_size, UI_TEXT, bold), indent)); line = word
            else:
                line = candidate
        blocks.append((rich_text(app, line, text_size, UI_TEXT, bold), indent))

    if item.get("image"):
        picture(item["image"])
    for raw in item["fr" if app.settings.language == "fr" else "en"].splitlines():
        line = raw.strip()
        if line.startswith("@img "):
            picture(line[5:].strip())
        elif line.startswith("# "):
            blocks.append((pygame.Surface((1, 8), pygame.SRCALPHA), 0))
            wrap(line[2:], size + 5, True, 0)
            blocks.append((pygame.Surface((1, 4), pygame.SRCALPHA), 0))
        elif line.startswith("- "):
            start = len(blocks)
            wrap(line[2:], size, False, 22)
            dot = rich_text(app, "•", size, UI_TEXT, True)
            first, indent = blocks[start]
            row = pygame.Surface((first.get_width() + indent, first.get_height()), pygame.SRCALPHA)
            row.blit(dot, (4, 0)); row.blit(first, (indent, 0))
            blocks[start] = (row, 0)
            blocks.append((pygame.Surface((1, 5), pygame.SRCALPHA), 0))
        elif not line:
            blocks.append((pygame.Surface((1, size // 2 + 4), pygame.SRCALPHA), 0))
        else:
            wrap(line, size, False, 0)
    app.cache[key] = blocks
    return blocks


class NewsState(ListMenu):
    """Annonces (bouton parchemin du menu principal) : nouveautés, sortie de VS DJCreeper, mise à jour disponible."""
    TINT = (120, 200, 160)

    def __init__(self, app, selected: int = 0):
        super().__init__(app)
        self.items = news.all_news(app)
        self.selected = self.scroll = min(selected, len(self.items) - 1)
        settings = app.settings
        settings.news_seen = sorted(set(settings.news_seen) | {item["id"] for item in self.items})
        settings.save()

    def entries(self) -> list:
        return self.items

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.move(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.move(1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.app.confirm_sound(); self.app.change(NewsArticleState(self.app, self.selected))
        elif event.key == pygame.K_ESCAPE:
            self.app.cancel_sound(); self.app.change(MainMenuState(self.app, "news"))

    def draw(self, screen: pygame.Surface) -> None:
        self.background(screen)
        # Liste fixe et centrée : peu d'annonces, elle n'a pas besoin de défiler (et ne touche pas le titre).
        middle = 330 + (self.scroll - (len(self.items) - 1) / 2) * 86
        self.draw_rows(screen, [item["title"] for item in self.items], x=50, height=46, spacing=86, center_y=middle, max_width=560)
        item = self.items[self.selected]
        panel = pygame.Rect(650, 90, 600, 530)
        top = window(self.app, screen, panel, self.app.tr("News"))
        self.app.text(screen, item["title"], (panel.x + 16, top + 8), 22, bold=True, color=UI_TEXT, raw=True)
        y, bottom = top + 44, panel.bottom - 44
        for block, dx in news_blocks(self.app, item, panel.width - 32, 17, 200):
            if y + block.get_height() > bottom:
                break
            screen.blit(block, (panel.x + 16 + dx, y)); y += block.get_height()
        self.app.text(screen, "ENTER: READ IT ALL", (panel.right - 16, panel.bottom - 34), 17, bold=True, color=UI_MUTED, right=True)
        self.title(screen, "NEWS")
        self.draw_footer(screen, "↑↓ SELECT     ENTER READ     ESC BACK")


class NewsArticleState(BaseState):
    """Une annonce en entier, qui défile (↑↓, molette, Page préc./suiv.) ; Entrée ouvre son lien."""
    TINT = (120, 200, 160)
    VIEW = pygame.Rect(140, 116, 1000, 520)

    def __init__(self, app, index: int):
        super().__init__(app)
        self.index = index
        self.item = news.all_news(app)[index]
        self.blocks = news_blocks(app, self.item, self.VIEW.width - 84, 20, 315)
        self.total = sum(block.get_height() for block, _ in self.blocks)
        self.offset = self.target = 0.0
        self.held: set[int] = set()

    @property
    def limit(self) -> float:
        return max(0.0, self.total - (self.VIEW.height - 70))

    def event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            self.target -= event.y * 80
        elif event.type == pygame.KEYUP:
            self.held.discard(event.key)
        elif event.type == pygame.KEYDOWN:
            self.held.add(event.key)
            steps = {pygame.K_UP: -60, pygame.K_w: -60, pygame.K_DOWN: 60, pygame.K_s: 60,
                     pygame.K_PAGEUP: -400, pygame.K_PAGEDOWN: 400, pygame.K_HOME: -10 ** 6, pygame.K_END: 10 ** 6}
            if event.key in steps:
                self.target += steps[event.key]
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and self.item.get("link"):
                import webbrowser
                self.app.confirm_sound(); webbrowser.open(self.item["link"])
            elif event.key == pygame.K_ESCAPE:
                self.app.cancel_sound(); self.app.change(NewsState(self.app, self.index))
        self.target = min(self.limit, max(0.0, self.target))

    def update(self, dt: float) -> None:
        # Flèche maintenue : défilement continu (aussi avec la croix de la manette).
        if self.held & {pygame.K_UP, pygame.K_w}:
            self.target -= 700 * dt
        if self.held & {pygame.K_DOWN, pygame.K_s}:
            self.target += 700 * dt
        self.target = min(self.limit, max(0.0, self.target))
        self.offset += (self.target - self.offset) * min(1.0, dt * 14)

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(BLACK)
        screen.blit(self.app.menu_bg(self.TINT), (0, 0))
        title = fit(self.app.alphabet(self.item["title"], 64), WIDTH - 80, 74)
        screen.blit(title, title.get_rect(midtop=(WIDTH // 2, 18)))
        top = window(self.app, screen, self.VIEW, self.app.tr("News"))
        area = pygame.Rect(self.VIEW.x + 2, top, self.VIEW.width - 4, self.VIEW.bottom - top - 2)
        screen.set_clip(area)
        y = top + 16 - round(self.offset)
        for block, dx in self.blocks:
            if y + block.get_height() >= area.top and y <= area.bottom:
                screen.blit(block, (self.VIEW.x + 32 + dx, y))
            y += block.get_height()
        screen.set_clip(None)
        if self.limit:
            track = pygame.Rect(self.VIEW.right - 14, area.top + 8, 6, area.height - 16)
            pygame.draw.rect(screen, (200, 200, 210), track, border_radius=3)
            size = max(30, round(track.height * area.height / (self.total + 32)))
            bar = pygame.Rect(track.x, track.y + round((track.height - size) * self.offset / self.limit), 6, size)
            pygame.draw.rect(screen, UI_MUTED, bar, border_radius=3)
        hint = "↑↓ SCROLL     ENTER OPEN LINK     ESC BACK" if self.item.get("link") else "↑↓ SCROLL     ESC BACK"
        key_hints(self.app, screen, hint, HEIGHT - 30)

