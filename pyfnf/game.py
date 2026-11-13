from __future__ import annotations

import json
import math
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

import pygame

from .assets import AnimateAtlas, AnimatedSprite, Assets, SparrowAtlas
from .data import FunkinData, SongInfo, WeekInfo
from .settings import Settings


WIDTH, HEIGHT = 1280, 720
FPS = 60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
PINK = (255, 0, 110)
CYAN = (0, 220, 255)
LANE_COLORS = ((194, 75, 255), (0, 220, 255), (43, 255, 93), (255, 55, 70))
LANE_NAMES = ("LEFT", "DOWN", "UP", "RIGHT")


def fit(surface: pygame.Surface, max_width: int, max_height: int) -> pygame.Surface:
    factor = min(max_width / surface.get_width(), max_height / surface.get_height())
    if factor >= 1:
        return surface
    return pygame.transform.smoothscale(surface, (max(1, round(surface.get_width() * factor)), max(1, round(surface.get_height() * factor))))


def tint(surface: pygame.Surface, color: tuple[int, int, int]) -> pygame.Surface:
    copy = surface.copy()
    copy.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return copy


def parse_color(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    try:
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
    except (ValueError, TypeError):
        return (249, 207, 81)


class Character:
    def __init__(self, assets: Assets, character_id: str):
        self.assets = assets
        self.id = character_id
        self.sprite: AnimatedSprite | None = None
        self.scale = .65
        self.flip = False
        self.last_sing = 0
        path = assets.root / "data" / "characters" / f"{character_id}.json"
        if not path.is_file():
            return
        config = assets.json(path)
        asset_path = config.get("assetPath", f"shared:characters/{character_id}")
        animations = {item.get("name", "idle"): item.get("prefix", "Idle") for item in config.get("animations", []) if not item.get("assetPath")}
        if not animations:
            animations = {"idle": "idle"}
        self.scale *= float(config.get("scale", 1))
        self.flip = bool(config.get("flipX", False))
        if ":" in asset_path:
            library, relative = asset_path.split(":", 1)
            directory = assets.root / library / "images" / relative
        else:
            candidates = [
                assets.root / "shared" / "images" / asset_path,
                assets.root / "images" / asset_path,
            ]
            directory = next((candidate for candidate in candidates if candidate.exists() or candidate.with_suffix(".png").exists()), candidates[0])
        try:
            if directory.is_dir() and (directory / "Animation.json").is_file():
                source = AnimateAtlas(assets, directory)
            else:
                png = directory.with_suffix(".png") if not directory.suffix else directory
                source = SparrowAtlas(assets, png)
            self.sprite = AnimatedSprite(source, animations)
        except (OSError, KeyError, ValueError, pygame.error):
            self.sprite = None

    def sing(self, lane: int, now: int, miss: bool = False) -> None:
        if not self.sprite:
            return
        name = f"sing{LANE_NAMES[lane]}{'miss' if miss else ''}"
        self.sprite.play(name, now, force=True, loop=False)
        self.last_sing = now

    def draw(self, screen: pygame.Surface, position: tuple[int, int], now: int, max_height: int = 500) -> None:
        if not self.sprite:
            pygame.draw.circle(screen, PINK if self.id != "bf" else CYAN, position, 70)
            return
        if self.sprite.current != "idle" and now - self.last_sing > 420:
            self.sprite.play("idle", now, force=True, loop=True)
        frame = self.sprite.frame(now)
        target_height = min(max_height, max(80, round(frame.get_height() * self.scale)))
        target_width = max(1, round(frame.get_width() * target_height / frame.get_height()))
        frame = pygame.transform.smoothscale(frame, (target_width, target_height))
        if self.flip:
            frame = pygame.transform.flip(frame, True, False)
        screen.blit(frame, (position[0] - frame.get_width() // 2, position[1] - frame.get_height()))


class Stage:
    def __init__(self, assets: Assets, stage_id: str):
        self.assets = assets
        self.id = stage_id
        self.props: list[tuple[int, pygame.Surface, tuple[int, int]]] = []
        self.characters = {"dad": (430, 625), "gf": (640, 580), "bf": (850, 625)}
        self.character_z = {"gf": 100, "dad": 200, "bf": 300}
        self.character_scale = 1.0
        path = assets.root / "data" / "stages" / f"{stage_id}.json"
        if not path.is_file():
            self._fallback()
            return
        data = assets.json(path)
        library = data.get("directory", "shared")
        character_data = data.get("characters", {})
        zoom = float(data.get("cameraZoom", 1.0))
        world_scale = max(.30, min(.62, .55 * zoom / 1.1))
        self.character_scale = world_scale / .55
        dad_position = character_data.get("dad", {}).get("position", [335, 885])
        bf_position = character_data.get("bf", {}).get("position", [990, 885])
        gf_position = character_data.get("gf", {}).get("position", [752, 787])
        midpoint_x = (float(dad_position[0]) + float(bf_position[0])) / 2
        baseline_y = statistics.median((float(dad_position[1]), float(bf_position[1]), float(gf_position[1])))
        offset_x = WIDTH / 2 - midpoint_x * world_scale
        offset_y = 615 - baseline_y * world_scale
        if stage_id == "phillyBlazin":
            # Cette scène de duel utilise des coordonnées caméra spéciales dans
            # les scripts Haxe ; on reproduit son cadrage plein écran ici.
            world_scale = .45
            self.character_scale = .82
            offset_x, offset_y = 270, 80
        for prop in sorted(data.get("props", []), key=lambda item: item.get("zIndex", 0)):
            try:
                image = self._prop_surface(prop, library)
                if image is None:
                    continue
                scale_data = prop.get("scale", [1, 1])
                if isinstance(scale_data, (int, float)):
                    scale_data = [scale_data, scale_data]
                sx, sy = world_scale * float(scale_data[0]), world_scale * float(scale_data[1])
                image = pygame.transform.smoothscale(image, (max(1, round(image.get_width() * sx)), max(1, round(image.get_height() * sy))))
                x, y = prop.get("position", [0, 0])
                self.props.append((int(prop.get("zIndex", 0)), image, (round(x * world_scale + offset_x), round(y * world_scale + offset_y))))
            except (pygame.error, OSError, ValueError):
                continue
        for key, fallback in self.characters.items():
            if key in character_data:
                x, y = character_data[key].get("position", [0, 0])
                self.characters[key] = (round(x * world_scale + offset_x), round(y * world_scale + offset_y))
                self.character_z[key] = int(character_data[key].get("zIndex", self.character_z[key]))
        if stage_id == "phillyBlazin":
            self.characters.update({"dad": (420, 650), "gf": (640, 1200), "bf": (860, 650)})
        if not self.props:
            self._fallback()

    def _fallback(self) -> None:
        image = self.assets.root / "shared" / "images" / "stageback.png"
        if image.is_file():
            surface = pygame.transform.smoothscale(self.assets.image(image), (WIDTH, HEIGHT))
            self.props = [(0, surface, (0, 0))]

    def _prop_surface(self, prop: dict, default_library: str) -> pygame.Surface | None:
        asset_path = str(prop.get("assetPath", ""))
        library = default_library
        if ":" in asset_path:
            library, asset_path = asset_path.split(":", 1)
        roots = [self.assets.root / library / "images", self.assets.root / "images", self.assets.root / "shared" / "images"]
        animations = prop.get("animations", [])
        prefix = animations[0].get("prefix", animations[0].get("name", "")) if animations else ""
        for root in roots:
            directory = root / asset_path
            if directory.is_dir() and (directory / "Animation.json").is_file():
                atlas = AnimateAtlas(self.assets, directory)
                if not prefix and atlas.labels:
                    prefix = next(iter(atlas.labels))
                return atlas.frame(prefix, 0)
            png_path = directory.with_suffix(".png")
            if png_path.is_file():
                if png_path.with_suffix(".xml").is_file() and prefix:
                    return SparrowAtlas(self.assets, png_path).animation(prefix)[0]
                return self.assets.image(png_path)
        return None

    def draw_range(self, screen: pygame.Surface, lower: float, upper: float) -> None:
        for z_index, surface, position in self.props:
            if lower <= z_index < upper:
                screen.blit(surface, position)


class BaseState:
    def __init__(self, app: "FunkinApp"):
        self.app = app

    def event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        pass


class TitleState(BaseState):
    def __init__(self, app: "FunkinApp"):
        super().__init__(app)
        self.started = pygame.time.get_ticks()
        self.logo = SparrowAtlas(app.assets, app.assets.root / "images" / "logoBumpin.png")
        self.gf = SparrowAtlas(app.assets, app.assets.root / "images" / "gfDanceTitle.png")
        app.play_menu_music()

    def event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.app.confirm_sound()
            self.app.change(MainMenuState(self.app))

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        screen.fill(BLACK)
        gf_frames = self.gf.animation("gfDance")
        gf = gf_frames[(now // 55) % len(gf_frames)]
        gf = fit(gf, 690, 690)
        screen.blit(gf, (WIDTH - gf.get_width() - 40, HEIGHT - gf.get_height()))
        logo_frames = self.logo.animation("logo bumpin")
        logo = logo_frames[(now // 45) % len(logo_frames)]
        logo = fit(logo, 650, 470)
        screen.blit(logo, (35, -30))
        pulse = 180 + round(math.sin(now / 180) * 75)
        text = self.app.font(42, bold=True).render("PRESS ENTER TO BEGIN", True, (255, pulse, 225))
        shadow = self.app.font(42, bold=True).render("PRESS ENTER TO BEGIN", True, BLACK)
        x = WIDTH // 2 - text.get_width() // 2
        screen.blit(shadow, (x + 4, 635 + 4)); screen.blit(text, (x, 635))
        self.app.draw_version(screen)


class MainMenuState(BaseState):
    ITEMS = (("STORY MODE", "storymode"), ("FREEPLAY", "freeplay"), ("OPTIONS", "options"))

    def __init__(self, app: "FunkinApp"):
        super().__init__(app)
        self.selected = 0
        self.atlases = {asset: SparrowAtlas(app.assets, app.assets.root / "images" / "mainmenu" / f"{asset}.png") for _, asset in self.ITEMS}

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - 1) % len(self.ITEMS); self.app.scroll_sound()
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 1) % len(self.ITEMS); self.app.scroll_sound()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.app.confirm_sound()
            if self.selected == 0:
                self.app.change(StoryMenuState(self.app))
            elif self.selected == 1:
                self.app.change(FreeplayState(self.app))
            else:
                self.app.change(OptionsState(self.app))
        elif event.key == pygame.K_ESCAPE:
            self.app.change(TitleState(self.app))

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        screen.blit(self.app.menu_background, (0, 0))
        for index, (_, asset_name) in enumerate(self.ITEMS):
            selected = index == self.selected
            atlas = self.atlases[asset_name]
            frames = atlas.animation(f"{asset_name} {'selected' if selected else 'idle'}")
            frame = frames[(now // 70) % len(frames)]
            frame = fit(frame, 600 if selected else 490, 150 if selected else 105)
            frame.set_alpha(255 if selected else 150)
            x = WIDTH // 2 - frame.get_width() // 2
            y = 150 + index * 165 - (frame.get_height() - 105) // 2
            screen.blit(frame, (x, y))
        self.app.draw_version(screen)


class StoryMenuState(BaseState):
    def __init__(self, app: "FunkinApp"):
        super().__init__(app)
        self.selected = 0
        self.difficulty_index = 0
        self._sync_difficulties()

    def _sync_difficulties(self) -> None:
        week = self.app.data.weeks[self.selected]
        self.difficulties = self.app.data.common_difficulties(week.songs) or list(self.app.data.songs[week.songs[0]].charts)
        self.difficulty_index %= len(self.difficulties)

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - 1) % len(self.app.data.weeks); self._sync_difficulties(); self.app.scroll_sound()
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 1) % len(self.app.data.weeks); self._sync_difficulties(); self.app.scroll_sound()
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            self.difficulty_index = (self.difficulty_index - 1) % len(self.difficulties); self.app.scroll_sound()
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.difficulty_index = (self.difficulty_index + 1) % len(self.difficulties); self.app.scroll_sound()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            week = self.app.data.weeks[self.selected]
            self.app.confirm_sound()
            self.app.start_playlist(week.songs, self.difficulties[self.difficulty_index])
        elif event.key == pygame.K_ESCAPE:
            self.app.change(MainMenuState(self.app)); self.app.cancel_sound()

    def draw(self, screen: pygame.Surface) -> None:
        week = self.app.data.weeks[self.selected]
        screen.fill(parse_color(week.background))
        pygame.draw.rect(screen, (42, 40, 48), (0, 90, WIDTH, 500))
        for offset in range(-2, 3):
            index = (self.selected + offset) % len(self.app.data.weeks)
            item = self.app.data.weeks[index]
            alpha = 255 if offset == 0 else 85
            title_path = self.app.assets.resolve_image(item.title_asset)
            if title_path:
                title = fit(self.app.assets.image(title_path), 440 if offset == 0 else 300, 130)
                title.set_alpha(alpha)
                screen.blit(title, (80, 310 + offset * 145 - title.get_height() // 2))
        pygame.draw.rect(screen, (20, 20, 20), (630, 90, 650, 500))
        self.app.text(screen, "WEEK SCORE: 0", (20, 20), 28, color=WHITE)
        self.app.text(screen, week.name, (690, 145), 54, color=PINK, bold=True)
        for index, song_id in enumerate(week.songs):
            song = self.app.data.songs[song_id]
            self.app.text(screen, song.name.upper(), (710, 245 + index * 62), 38, color=WHITE, bold=True)
        difficulty = self.difficulties[self.difficulty_index].split(":", 1)[0]
        diff_path = self.app.assets.root / "images" / "storymenu" / "difficulties" / f"{difficulty}.png"
        if diff_path.is_file():
            image = fit(self.app.assets.image(diff_path), 300, 80)
            screen.blit(image, (940 - image.get_width() // 2, 510))
        else:
            self.app.text(screen, f"< {difficulty.upper()} >", (820, 520), 40, color=(255, 220, 0), bold=True)
        self.app.text(screen, "↑↓ WEEK     ←→ DIFFICULTY     ENTER PLAY", (WIDTH // 2, 680), 22, center=True)


class FreeplayState(BaseState):
    def __init__(self, app: "FunkinApp"):
        super().__init__(app)
        self.song_ids = sorted(app.data.songs, key=lambda key: app.data.songs[key].name)
        self.selected = 0
        self.chart_index = 0

    def charts(self) -> list[str]:
        return list(self.app.data.songs[self.song_ids[self.selected]].charts)

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - 1) % len(self.song_ids); self.chart_index = 0; self.app.scroll_sound()
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 1) % len(self.song_ids); self.chart_index = 0; self.app.scroll_sound()
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            self.chart_index = (self.chart_index - 1) % len(self.charts()); self.app.scroll_sound()
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.chart_index = (self.chart_index + 1) % len(self.charts()); self.app.scroll_sound()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.app.confirm_sound(); self.app.start_playlist([self.song_ids[self.selected]], self.charts()[self.chart_index])
        elif event.key == pygame.K_ESCAPE:
            self.app.change(MainMenuState(self.app)); self.app.cancel_sound()

    def draw(self, screen: pygame.Surface) -> None:
        screen.blit(self.app.menu_background, (0, 0))
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); overlay.fill((0, 0, 0, 105)); screen.blit(overlay, (0, 0))
        self.app.text(screen, "FREEPLAY", (45, 28), 64, color=PINK, bold=True)
        for offset in range(-5, 6):
            index = self.selected + offset
            if not 0 <= index < len(self.song_ids):
                continue
            song = self.app.data.songs[self.song_ids[index]]
            y = 150 + offset * 52
            selected = offset == 0
            if selected:
                pygame.draw.polygon(screen, (20, 20, 20), [(0, y - 10), (930, y - 22), (970, y + 30), (0, y + 42)])
            self.app.text(screen, song.name.upper(), (60 if selected else 85, y), 40 if selected else 30,
                          color=(255, 255, 255) if selected else (155, 155, 165), bold=True)
            if selected:
                self.app.text(screen, song.artist, (710, y + 5), 20, color=(200, 200, 210))
        chart = self.charts()[self.chart_index]
        label = chart.replace(":", " / ").upper()
        self.app.text(screen, f"< {label} >", (WIDTH - 250, 95), 28, center=True, color=(255, 230, 40), bold=True)
        self.app.text(screen, f"{self.selected + 1} / {len(self.song_ids)}", (WIDTH - 115, 665), 20)


class OptionsState(BaseState):
    ITEMS = ("VOLUME", "AUDIO CALIBRATION", "CONTROLS")

    def __init__(self, app: "FunkinApp"):
        super().__init__(app)
        self.selected = 0

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - 1) % len(self.ITEMS); self.app.scroll_sound()
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 1) % len(self.ITEMS); self.app.scroll_sound()
        elif self.selected == 0 and event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            direction = -1 if event.key in (pygame.K_LEFT, pygame.K_a) else 1
            self.app.volume = min(1, max(0, self.app.volume + direction * .05))
            self.app.settings.volume = self.app.volume; self.app.settings.save()
            pygame.mixer.music.set_volume(self.app.volume); self.app.scroll_sound()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.selected == 1: self.app.change(CalibrationState(self.app))
            elif self.selected == 2: self.app.change(ControlsState(self.app))
        elif event.key == pygame.K_ESCAPE:
            self.app.settings.save(); self.app.change(MainMenuState(self.app))

    def draw(self, screen: pygame.Surface) -> None:
        screen.blit(self.app.menu_background, (0, 0))
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); shade.fill((0, 0, 0, 90)); screen.blit(shade, (0, 0))
        self.app.text(screen, "OPTIONS", (WIDTH // 2, 110), 72, center=True, color=PINK, bold=True)
        values = (f"{round(self.app.volume * 100)}%", f"{self.app.settings.offset_ms:+d} ms", "  ".join(pygame.key.name(key).upper() for key in self.app.settings.keybinds))
        for index, label in enumerate(self.ITEMS):
            y = 245 + index * 112
            selected = index == self.selected
            color = PINK if selected else (235, 235, 240)
            if selected: pygame.draw.polygon(screen, (25, 25, 35), [(190, y - 20), (1080, y - 30), (1100, y + 60), (170, y + 55)])
            self.app.text(screen, label, (260, y), 38, color=color, bold=True)
            self.app.text(screen, values[index], (1010, y + 5), 28, color=CYAN if selected else WHITE, center=True, bold=True)
        self.app.text(screen, "↑↓ SELECT     ←→ VOLUME     ENTER OPEN     ESC BACK", (WIDTH // 2, 650), 22, center=True)


class ControlsState(BaseState):
    def __init__(self, app: "FunkinApp"):
        super().__init__(app)
        self.selected = 0
        self.listening = False

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if self.listening:
            if event.key == pygame.K_ESCAPE:
                self.listening = False
            elif event.key not in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_LALT, pygame.K_RALT):
                self.app.settings.bind(self.selected, event.key)
                self.listening = False; self.app.confirm_sound()
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - 1) % 4; self.app.scroll_sound()
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 1) % 4; self.app.scroll_sound()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.listening = True
        elif event.key == pygame.K_r:
            self.app.settings.reset_binds(); self.app.confirm_sound()
        elif event.key == pygame.K_ESCAPE:
            self.app.change(OptionsState(self.app)); self.app.cancel_sound()

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((18, 16, 29))
        self.app.text(screen, "CONTROLS", (WIDTH // 2, 70), 68, center=True, color=PINK, bold=True)
        arrows = ("←", "↓", "↑", "→")
        for lane, name in enumerate(LANE_NAMES):
            y = 195 + lane * 92
            selected = lane == self.selected
            pygame.draw.rect(screen, (38, 36, 50) if not selected else (67, 33, 65), (300, y - 15, 680, 70), border_radius=12)
            self.app.text(screen, arrows[lane], (340, y - 3), 45, color=LANE_COLORS[lane], bold=True)
            self.app.text(screen, name, (420, y + 5), 30, bold=True)
            key_name = "PRESS A KEY..." if selected and self.listening else pygame.key.name(self.app.settings.keybinds[lane]).upper()
            self.app.text(screen, key_name, (835, y + 4), 28, center=True, color=CYAN if selected else WHITE, bold=True)
        self.app.text(screen, "ENTER REBIND     R RESET TO D F J K     ESC BACK", (WIDTH // 2, 630), 23, center=True)


class CalibrationState(BaseState):
    BEAT_MS = 500

    def __init__(self, app: "FunkinApp"):
        super().__init__(app)
        pygame.mixer.music.stop()
        now = pygame.time.get_ticks()
        self.first_beat = now + 1400
        self.next_beat = self.first_beat
        self.last_beat = self.first_beat - self.BEAT_MS
        self.samples: list[int] = []
        self.applied_flash = 0
        path = app.assets.root / "sounds" / "chartingSounds" / "metronome1.ogg"
        self.tick = app.assets.sound(path) if path.is_file() else None

    @property
    def suggestion(self) -> int:
        if not self.samples:
            return self.app.settings.offset_ms
        recent = self.samples[-12:]
        return max(-500, min(500, round(statistics.median(recent))))

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
                if len(self.samples) >= 8:
                    self.app.settings.offset_ms = self.suggestion
                    self.app.settings.save()
                    self.applied_flash = now
            return
        if event.key == pygame.K_RETURN and len(self.samples) >= 4:
            self.app.settings.offset_ms = self.suggestion; self.app.settings.save(); self.applied_flash = now
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
        while now >= self.next_beat:
            self.last_beat = self.next_beat
            if self.tick:
                self.tick.set_volume(self.app.volume); self.tick.play()
            self.next_beat += self.BEAT_MS

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        screen.fill((13, 11, 24))
        self.app.text(screen, "AUDIO CALIBRATION", (WIDTH // 2, 55), 62, center=True, color=PINK, bold=True)
        self.app.text(screen, "TAP SPACE OR YOUR NOTE KEYS ON EACH CLICK", (WIDTH // 2, 135), 25, center=True)
        center = WIDTH // 2
        pygame.draw.line(screen, (80, 80, 95), (220, 300), (1060, 300), 5)
        pygame.draw.line(screen, WHITE, (center, 245), (center, 355), 4)
        phase = ((now - self.first_beat) % self.BEAT_MS) / self.BEAT_MS if now >= self.first_beat else 0
        distance = abs((phase + .5) % 1 - .5) * 2
        marker_x = round(center + (distance * 400) * (-1 if phase < .5 else 1))
        pygame.draw.circle(screen, CYAN, (marker_x, 300), 18)
        pulse = max(0, 1 - abs(now - self.last_beat) / 160)
        pygame.draw.circle(screen, (255, round(70 + 185 * pulse), 140), (center, 300), round(25 + pulse * 32), 5)
        for index, sample in enumerate(self.samples[-12:]):
            x = center + round(sample / 250 * 400)
            pygame.draw.circle(screen, LANE_COLORS[index % 4], (x, 390 + (index % 2) * 18), 6)
        measured = f"{self.suggestion:+d} ms" if self.samples else "-- ms"
        self.app.text(screen, "MEASURED OFFSET", (400, 460), 25, center=True, color=(180, 180, 195))
        self.app.text(screen, measured, (400, 500), 48, center=True, color=CYAN, bold=True)
        self.app.text(screen, "CURRENT OFFSET", (880, 460), 25, center=True, color=(180, 180, 195))
        self.app.text(screen, f"{self.app.settings.offset_ms:+d} ms", (880, 500), 48, center=True, color=(255, 225, 50), bold=True)
        if len(self.samples) >= 8:
            status = f"AUTO APPLIED: {self.app.settings.offset_ms:+d} ms — KEEP TAPPING TO REFINE"
        elif len(self.samples) >= 4:
            status = f"{len(self.samples)} / 8 TAPS — ENTER CAN APPLY NOW"
        else:
            status = f"{len(self.samples)} / 8 TAPS FOR AUTO CALIBRATION"
        if now - self.applied_flash < 900: status = f"AUTO CALIBRATION APPLIED: {self.app.settings.offset_ms:+d} ms"
        self.app.text(screen, status, (WIDTH // 2, 575), 27, center=True, color=(80, 255, 120) if now - self.applied_flash < 900 else WHITE, bold=True)
        self.app.text(screen, "←→ MANUAL (SHIFT = 10 ms)     C CLEAR     ESC BACK", (WIDTH // 2, 660), 21, center=True)


@dataclass
class PlayNote:
    time: float
    lane: int
    player: bool
    length: float
    state: str = "pending"


class PlayState(BaseState):
    def __init__(self, app: "FunkinApp", song_id: str, chart_key: str):
        super().__init__(app)
        self.song = app.data.songs[song_id]
        self.chart_key = chart_key if chart_key in self.song.charts else next(iter(self.song.charts))
        chart = app.data.load_chart(self.song, self.chart_key)
        self.profile = chart["profile"]
        self.notes = [PlayNote(**note) for note in chart["notes"]]
        self.events = sorted(chart["events"], key=lambda event: float(event.get("t", 0)))
        self.event_index = 0
        self.scroll_speed = chart["scroll_speed"]
        self.variation = chart["variation"]
        self.stage = Stage(app.assets, self.profile["stage"])
        self.player = Character(app.assets, self.profile["player"])
        self.opponent = Character(app.assets, self.profile["opponent"])
        self.girlfriend = Character(app.assets, self.profile["girlfriend"])
        self.song_started = False
        self.song_time = -3000.0
        self.countdown_last = 4
        self.paused = False
        self.score = 0; self.combo = 0; self.max_combo = 0; self.misses = 0
        self.sick = 0; self.good = 0; self.bad = 0; self.shit = 0; self.weighted = 0.0; self.judged = 0
        self.health = 50.0
        self.rating_text = ""; self.rating_at = 0
        self.key_down = [False] * 4
        self.key_lanes = {
            pygame.K_LEFT: 0, pygame.K_DOWN: 1, pygame.K_UP: 2, pygame.K_RIGHT: 3,
            **{key: lane for lane, key in enumerate(app.settings.keybinds)},
        }
        self.audio_sounds: list[pygame.mixer.Sound] = []
        self.audio_channels: list[pygame.mixer.Channel] = []
        self.instrument_channel: pygame.mixer.Channel | None = None
        self.audio_started_at = 0
        self.pause_started_at = 0
        self.finished = False
        self.note_atlas = SparrowAtlas(app.assets, app.assets.root / "shared" / "images" / "notes.png")
        self.strum_atlas = SparrowAtlas(app.assets, app.assets.root / "shared" / "images" / "noteStrumline.png")
        self.note_images = [self._scaled_note(name) for name in ("noteLeft", "noteDown", "noteUp", "noteRight")]
        self.static_strums = [self._scaled_strum(f"static{name.title()}0") for name in ("left", "down", "up", "right")]
        self.press_strums = [self._scaled_strum(f"press{name.title()}0") for name in ("left", "down", "up", "right")]
        self.confirm_strums = [self._scaled_strum(f"confirm{name.title()}0") for name in ("left", "down", "up", "right")]
        self.player_icon = self._load_icon(self.profile["player"])
        self.opponent_icon = self._load_icon(self.profile["opponent"])
        pygame.mixer.music.stop()
        self._prepare_audio()
        # Le countdown commence seulement une fois toutes les pistes décodées.
        self.started = pygame.time.get_ticks()

    def _scaled_note(self, prefix: str) -> pygame.Surface:
        return self._normalized_arrow(self.note_atlas.animation(prefix)[0])

    def _scaled_strum(self, prefix: str) -> pygame.Surface:
        return self._normalized_arrow(self.strum_atlas.animation(prefix)[0])

    @staticmethod
    def _normalized_arrow(surface: pygame.Surface, visible_size: int = 96) -> pygame.Surface:
        """Crop transparent atlas padding so notes and receptors look equally sized."""
        bounds = surface.get_bounding_rect()
        if bounds.width and bounds.height:
            surface = surface.subsurface(bounds).copy()
        factor = visible_size / max(surface.get_size())
        size = (max(1, round(surface.get_width() * factor)), max(1, round(surface.get_height() * factor)))
        return pygame.transform.smoothscale(surface, size)

    def _load_icon(self, character_id: str) -> pygame.Surface | None:
        candidates = [character_id, character_id.replace("-playable", ""), character_id.split("-")[0], "face"]
        for name in candidates:
            path = self.app.assets.root / "images" / "icons" / f"icon-{name}.png"
            if path.is_file():
                image = self.app.assets.image(path)
                frame_width = min(150, image.get_width())
                frame = image.subsurface((0, 0, frame_width, min(150, image.get_height()))).copy()
                return pygame.transform.smoothscale(frame, (58, 58))
        return None

    def _audio_paths(self) -> tuple[Path, list[Path]]:
        directory = self.app.assets.root / "songs" / self.song.song_id
        suffix = f"-{self.variation}" if self.variation else ""
        instrumental = directory / f"Inst{suffix}.ogg"
        if not instrumental.is_file(): instrumental = directory / "Inst.ogg"
        voices: list[Path] = []
        vocal_ids = [*self.profile.get("player_vocals", []), *self.profile.get("opponent_vocals", [])]
        removable_suffixes = (
            "-holding-nene", "-holding-gf", "-playable", "-christmas", "-pixel",
            "-tankmen", "-blazin", "-bloody", "-angry", "-car", "-dark",
        )
        for vocal_id in vocal_ids:
            aliases = [str(vocal_id)]
            simplified = str(vocal_id)
            for removable in removable_suffixes:
                simplified = simplified.replace(removable, "")
            if simplified not in aliases:
                aliases.append(simplified)
            candidates = []
            for alias in aliases:
                if self.variation:
                    candidates.append(directory / f"Voices-{alias}-{self.variation}.ogg")
                candidates.append(directory / f"Voices-{alias}.ogg")
            match = next((path for path in candidates if path.is_file()), None)
            if match and match not in voices:
                voices.append(match)
        if not voices and self.variation:
            voices.extend(sorted(directory.glob(f"Voices-*-{self.variation}.ogg"))[:2])
        elif not voices:
            voices.extend(path for path in sorted(directory.glob("Voices-*.ogg")) if path.stem.count("-") == 1)
        if not voices and (directory / f"Voices{suffix}.ogg").is_file(): voices.append(directory / f"Voices{suffix}.ogg")
        return instrumental, voices

    def _prepare_audio(self) -> None:
        instrumental, voices = self._audio_paths()
        if not instrumental.is_file():
            return
        self.audio_sounds = []
        for path in [instrumental, *voices[:6]]:
            try:
                sound = pygame.mixer.Sound(path)
                self.audio_sounds.append(sound)
            except pygame.error:
                pass

    def start_audio(self) -> None:
        if not self.audio_sounds:
            self.finish(); return
        self.audio_channels = []
        # Les canaux réservés sont armés dans la même itération du mixer SDL :
        # Inst et Voices démarrent donc sur le même buffer audio.
        for index, sound in enumerate(self.audio_sounds):
            channel = pygame.mixer.Channel(index)
            channel.stop(); channel.set_volume(self.app.volume); channel.play(sound)
            self.audio_channels.append(channel)
        self.instrument_channel = self.audio_channels[0]
        self.audio_started_at = pygame.time.get_ticks()
        self.song_time = 0
        self.song_started = True

    def event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.restart_song(); return
            if event.key == pygame.K_ESCAPE:
                if self.paused: self.exit_to_menu()
                else: self.toggle_pause()
                return
            if self.paused and event.key == pygame.K_RETURN:
                self.toggle_pause(); return
            if not self.paused and event.key in self.key_lanes:
                lane = self.key_lanes[event.key]
                if not self.key_down[lane]: self.hit_lane(lane)
                self.key_down[lane] = True
        elif event.type == pygame.KEYUP and event.key in self.key_lanes:
            self.key_down[self.key_lanes[event.key]] = False

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        if self.paused:
            self.pause_started_at = pygame.time.get_ticks()
            for channel in self.audio_channels:
                channel.pause()
        else:
            if self.audio_started_at:
                self.audio_started_at += pygame.time.get_ticks() - self.pause_started_at
            for channel in self.audio_channels:
                channel.unpause()

    def stop_audio(self) -> None:
        for channel in self.audio_channels:
            channel.stop()
        self.audio_channels.clear()

    def restart_song(self) -> None:
        self.stop_audio()
        for note in self.notes:
            note.state = "pending"
        self.event_index = 0
        self.song_started = False
        self.song_time = -3000.0
        self.countdown_last = 4
        self.paused = False
        self.finished = False
        self.score = 0; self.combo = 0; self.max_combo = 0; self.misses = 0
        self.sick = 0; self.good = 0; self.bad = 0; self.shit = 0
        self.weighted = 0.0; self.judged = 0
        self.health = 50.0
        self.rating_text = ""; self.rating_at = 0
        self.key_down = [False] * 4
        self.instrument_channel = None
        self.audio_started_at = 0
        self.pause_started_at = 0
        self.started = pygame.time.get_ticks()
        now = self.started
        for character in (self.player, self.opponent, self.girlfriend):
            if character.sprite:
                character.sprite.play("idle", now, force=True, loop=True)

    def exit_to_menu(self) -> None:
        self.stop_audio()
        self.app.play_menu_music()
        self.app.change(MainMenuState(self.app))

    def hit_lane(self, lane: int) -> None:
        if not self.song_started:
            return
        timing = self.chart_time
        candidates = [note for note in self.notes if note.player and note.lane == lane and note.state == "pending" and abs(note.time - timing) <= 166]
        if not candidates:
            return
        note = min(candidates, key=lambda item: abs(item.time - timing))
        difference = abs(note.time - timing)
        if difference <= 45: rating, points, weight = "SICK", 350, 1.0
        elif difference <= 90: rating, points, weight = "GOOD", 200, .75
        elif difference <= 135: rating, points, weight = "BAD", 100, .5
        else: rating, points, weight = "SHIT", 50, .25
        note.state = "holding" if note.length > 0 else "hit"
        setattr(self, rating.lower(), getattr(self, rating.lower()) + 1)
        self.combo += 1; self.max_combo = max(self.max_combo, self.combo)
        self.score += points + min(100, self.combo)
        self.weighted += weight; self.judged += 1; self.health = min(100, self.health + 1.8)
        self.player.sing(lane, pygame.time.get_ticks())
        self.show_rating(rating)

    def miss(self, note: PlayNote) -> None:
        note.state = "miss"
        self.combo = 0; self.misses += 1; self.judged += 1; self.health = max(0, self.health - 5)
        self.player.sing(note.lane, pygame.time.get_ticks(), miss=True)
        try: self.app.assets.sound(self.app.assets.root / "shared" / "sounds" / f"missnote{random.randint(1, 3)}.ogg").play()
        except pygame.error: pass
        self.show_rating("MISS")

    def show_rating(self, rating: str) -> None:
        self.rating_text = rating; self.rating_at = pygame.time.get_ticks()

    def accuracy(self) -> float:
        return self.weighted / self.judged * 100 if self.judged else 100

    @property
    def chart_time(self) -> float:
        """Position du chart après compensation de la latence mesurée."""
        return self.song_time - self.app.settings.offset_ms

    def update(self, dt: float) -> None:
        if self.paused or self.finished:
            return
        elapsed = pygame.time.get_ticks() - self.started
        if not self.song_started:
            self.song_time = elapsed - 3000
            count = math.ceil(-self.song_time / 1000)
            if count != self.countdown_last:
                self.countdown_last = count
                self.app.countdown_sound(count)
            if self.song_time >= 0: self.start_audio()
        else:
            self.song_time = float(pygame.time.get_ticks() - self.audio_started_at)
            if self.instrument_channel and not self.instrument_channel.get_busy() and self.song_time > 1000:
                self.finish(); return
        now = pygame.time.get_ticks()
        timing = self.chart_time
        while self.event_index < len(self.events) and float(self.events[self.event_index].get("t", 0)) <= timing:
            event = self.events[self.event_index]; self.event_index += 1
            if event.get("e") == "PlayAnimation" and isinstance(event.get("v"), dict):
                value = event["v"]; target = value.get("target"); anim = value.get("anim", "idle")
                character = self.player if target in ("bf", "boyfriend") else self.opponent if target in ("dad", "opponent") else self.girlfriend
                if character.sprite: character.sprite.play(anim, now, force=True, loop=False)
        for note in self.notes:
            if note.state == "holding":
                if timing >= note.time + note.length:
                    note.state = "hit"; self.score += round(note.length / 20); self.health = min(100, self.health + 2)
                elif timing > note.time + 90 and not self.key_down[note.lane]:
                    note.state = "miss"; self.combo = 0; self.misses += 1; self.health = max(0, self.health - 3); self.show_rating("MISS")
                else:
                    self.health = min(100, self.health + dt * .8)
                continue
            if note.state != "pending": continue
            if not note.player and note.time <= timing:
                note.state = "hit"; self.opponent.sing(note.lane, now)
            elif note.player and note.time < timing - 180:
                self.miss(note)
        if self.health <= 0:
            self.finish(failed=True)

    def finish(self, failed: bool = False) -> None:
        if self.finished: return
        self.finished = True
        self.stop_audio()
        self.app.change(ResultsState(self.app, self, failed))

    def _draw_notes(self, screen: pygame.Surface) -> None:
        receptor_y = 72
        lane_space = 120
        player_x, opponent_x = 715, 55
        pixels_per_ms = .33 * self.scroll_speed
        # Les récepteurs constituent le fond de la strumline : les notes qui
        # défilent sont dessinées ensuite afin de passer visiblement devant.
        for side_x in (opponent_x, player_x):
            for lane in range(4):
                if side_x == player_x and self.key_down[lane]: image = self.press_strums[lane]
                else: image = self.static_strums[lane]
                screen.blit(image, (side_x + lane * lane_space, receptor_y))
        for note in self.notes:
            if note.state not in ("pending", "holding"): continue
            distance = note.time - self.chart_time
            if note.state == "holding": distance = 0
            y = receptor_y + distance * pixels_per_ms
            if y < -120 or y > HEIGHT + 160: continue
            base_x = player_x if note.player else opponent_x
            x = base_x + note.lane * lane_space
            if note.length > 0:
                remaining = note.length if note.state == "pending" else max(0, note.time + note.length - self.chart_time)
                sustain_height = max(0, round(remaining * pixels_per_ms))
                if sustain_height:
                    center_x = x + self.note_images[note.lane].get_width() // 2
                    stem_y = y + round(self.note_images[note.lane].get_height() * .68)
                    pygame.draw.rect(screen, LANE_COLORS[note.lane], (center_x - 7, stem_y, 14, sustain_height), border_radius=7)
            screen.blit(self.note_images[note.lane], (x, y))

    def _draw_hud(self, screen: pygame.Surface) -> None:
        bar_rect = pygame.Rect(340, 646, 600, 20)
        pygame.draw.rect(screen, BLACK, bar_rect.inflate(8, 8))
        pygame.draw.rect(screen, (255, 40, 95), bar_rect)
        player_width = round(bar_rect.width * self.health / 100)
        pygame.draw.rect(screen, (80, 235, 65), (bar_rect.right - player_width, bar_rect.y, player_width, bar_rect.height))
        marker_x = bar_rect.right - player_width
        pygame.draw.line(screen, WHITE, (marker_x, bar_rect.y - 5), (marker_x, bar_rect.bottom + 5), 3)
        if self.opponent_icon:
            screen.blit(self.opponent_icon, (marker_x - 56, bar_rect.centery - 29))
        if self.player_icon:
            screen.blit(self.player_icon, (marker_x, bar_rect.centery - 29))
        self.app.text(screen, f"Score: {self.score} | Misses: {self.misses} | Accuracy: {self.accuracy():.2f}% | Combo: {self.combo}",
                      (WIDTH // 2, 680), 21, center=True, outline=True)
        if pygame.time.get_ticks() - self.rating_at < 650 and self.rating_text:
            rating_path = self.app.assets.root / "images" / "ui" / "popup" / "funkin" / f"{self.rating_text.lower()}.png"
            if rating_path.is_file():
                rating = fit(self.app.assets.image(rating_path), 250, 120)
                screen.blit(rating, (WIDTH // 2 - rating.get_width() // 2, 250))
            else:
                self.app.text(screen, self.rating_text, (WIDTH // 2, 280), 64, center=True, color=CYAN, bold=True, outline=True)
            if self.combo > 1: self.app.text(screen, str(self.combo), (WIDTH // 2, 365), 52, center=True, outline=True)

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        screen.fill((26, 22, 40))
        actors = [
            (self.stage.character_z["gf"], "gf", self.girlfriend, 390),
            (self.stage.character_z["dad"], "dad", self.opponent, 510),
            (self.stage.character_z["bf"], "bf", self.player, 490),
        ]
        lower = float("-inf")
        for z_index, key, character, max_height in sorted(actors, key=lambda item: item[0]):
            self.stage.draw_range(screen, lower, z_index)
            character.draw(screen, self.stage.characters[key], now, round(max_height * self.stage.character_scale))
            lower = z_index
        self.stage.draw_range(screen, lower, float("inf"))
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); shade.fill((0, 0, 0, 25)); screen.blit(shade, (0, 0))
        self._draw_notes(screen); self._draw_hud(screen)
        self.app.text(screen, f"{self.song.name}  [{self.chart_key.upper()}]", (16, 14), 21, outline=True)
        binds = " ".join(pygame.key.name(key).upper() for key in self.app.settings.keybinds)
        self.app.text(screen, f"{binds}  |  OFFSET {self.app.settings.offset_ms:+d} ms", (WIDTH - 16, 14), 17, outline=True, right=True)
        if not self.song_started:
            count = math.ceil(-self.song_time / 1000)
            word = {2: "READY?", 1: "SET!"}.get(count, "")
            if word: self.app.text(screen, word, (WIDTH // 2, HEIGHT // 2), 92, center=True, color=(255, 230, 20), bold=True, outline=True)
        elif self.song_time < 450:
            self.app.text(screen, "GO!", (WIDTH // 2, HEIGHT // 2), 92, center=True, color=(255, 230, 20), bold=True, outline=True)
        if self.paused:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); overlay.fill((0, 0, 0, 190)); screen.blit(overlay, (0, 0))
            self.app.text(screen, "PAUSED", (WIDTH // 2, 260), 90, center=True, color=PINK, bold=True)
            self.app.text(screen, "ENTER  RESUME", (WIDTH // 2, 375), 30, center=True)
            self.app.text(screen, "R  RESTART SONG", (WIDTH // 2, 425), 28, center=True, color=CYAN)
            self.app.text(screen, "ESC  BACK TO MENU", (WIDTH // 2, 475), 28, center=True, color=(255, 220, 60))


class ResultsState(BaseState):
    def __init__(self, app: "FunkinApp", play: PlayState, failed: bool):
        super().__init__(app)
        self.play = play; self.failed = failed
        accuracy = play.accuracy()
        self.grade = "F" if failed else "S" if accuracy >= 95 else "A" if accuracy >= 88 else "B" if accuracy >= 78 else "C" if accuracy >= 65 else "D"

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN: return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if not self.failed and self.app.advance_playlist(): return
            self.app.play_menu_music(); self.app.change(FreeplayState(self.app))
        elif event.key == pygame.K_r:
            self.play.restart_song()
            self.app.change(self.play)
        elif event.key == pygame.K_ESCAPE:
            self.app.play_menu_music(); self.app.change(MainMenuState(self.app))

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((12, 10, 22))
        self.app.text(screen, "SONG FAILED" if self.failed else "SONG COMPLETE!", (WIDTH // 2, 70), 62, center=True, color=PINK, bold=True)
        self.app.text(screen, self.grade, (WIDTH // 2, 180), 150, center=True, color=(255, 230, 20), bold=True, outline=True)
        self.app.text(screen, self.play.song.name.upper(), (WIDTH // 2, 330), 42, center=True, bold=True)
        lines = [
            f"SCORE  {self.play.score}", f"ACCURACY  {self.play.accuracy():.2f}%", f"MAX COMBO  {self.play.max_combo}",
            f"SICK {self.play.sick}   GOOD {self.play.good}   BAD {self.play.bad}   SHIT {self.play.shit}   MISSES {self.play.misses}",
        ]
        for index, line in enumerate(lines): self.app.text(screen, line, (WIDTH // 2, 395 + index * 45), 28, center=True)
        self.app.text(screen, "ENTER CONTINUE     R RETRY     ESC MENU", (WIDTH // 2, 650), 24, center=True, color=CYAN)


class FunkinApp:
    def __init__(self, root: Path):
        pygame.mixer.pre_init(44100, -16, 2, 1024)
        pygame.init()
        pygame.mixer.set_num_channels(16)
        pygame.mixer.set_reserved(7)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE | pygame.SCALED)
        pygame.display.set_caption("Friday Night Funkin' — Python Port")
        self.clock = pygame.time.Clock()
        self.assets = Assets(root)
        self.data = FunkinData(root)
        self.settings = Settings.load()
        self.volume = self.settings.volume
        self._fonts: dict[tuple[int, bool], pygame.font.Font] = {}
        background = self.assets.image(root / "images" / "menuBG.png")
        self.menu_background = pygame.transform.smoothscale(background, (WIDTH, HEIGHT))
        self.state: BaseState = TitleState(self)
        self.running = True
        self.playlist: list[str] = []
        self.playlist_index = 0
        self.playlist_difficulty = "normal"

    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._fonts:
            # Arial Black garde un poids proche de FNF sans écraser les petites lettres.
            names = "arial black,arial" if bold else "arial,dejavusans"
            self._fonts[key] = pygame.font.SysFont(names, size, bold=bold)
        return self._fonts[key]

    def text(self, screen: pygame.Surface, value: str, position: tuple[int, int], size: int,
             color: tuple[int, int, int] = WHITE, center: bool = False, bold: bool = False,
             outline: bool = False, right: bool = False) -> None:
        font = self.font(size, bold)
        image = font.render(str(value), True, color)
        x, y = position
        if center: x -= image.get_width() // 2
        elif right: x -= image.get_width()
        if outline:
            shadow = font.render(str(value), True, BLACK)
            for ox, oy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
                screen.blit(shadow, (x + ox, y + oy))
        screen.blit(image, (x, y))

    def change(self, state: BaseState) -> None:
        self.state = state

    def play_menu_music(self) -> None:
        menu_music = self.assets.root / "music" / "freakyMenu" / "freakyMenu.ogg"
        try:
            pygame.mixer.music.load(menu_music); pygame.mixer.music.set_volume(self.volume); pygame.mixer.music.play(-1)
        except pygame.error: pass

    def _play_sound(self, relative: str) -> None:
        path = self.assets.root / relative
        if path.is_file():
            try:
                sound = self.assets.sound(path); sound.set_volume(self.volume); sound.play()
            except pygame.error: pass

    def scroll_sound(self) -> None: self._play_sound("sounds/scrollMenu.ogg")
    def confirm_sound(self) -> None: self._play_sound("sounds/confirmMenu.ogg")
    def cancel_sound(self) -> None: self._play_sound("sounds/cancelMenu.ogg")
    def countdown_sound(self, count: int) -> None:
        name = {3: "introTHREE", 2: "introTWO", 1: "introONE", 0: "introGO"}.get(count)
        if name: self._play_sound(f"shared/sounds/gameplay/countdown/funkin/{name}.ogg")

    def start_playlist(self, song_ids: list[str], difficulty: str) -> None:
        self.playlist = song_ids; self.playlist_index = 0; self.playlist_difficulty = difficulty
        self.change(PlayState(self, song_ids[0], difficulty))

    def advance_playlist(self) -> bool:
        self.playlist_index += 1
        if self.playlist_index >= len(self.playlist): return False
        song_id = self.playlist[self.playlist_index]
        song = self.data.songs[song_id]
        key = self.playlist_difficulty if self.playlist_difficulty in song.charts else next(iter(song.charts))
        self.change(PlayState(self, song_id, key)); return True

    def draw_version(self, screen: pygame.Surface) -> None:
        self.text(screen, "PYTHON PORT 0.2  •  PYGAME-CE", (10, HEIGHT - 24), 14, color=(180, 180, 190))

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.state.event(event)
            self.state.update(dt)
            self.state.draw(self.screen)
            pygame.display.flip()
        self.settings.volume = self.volume
        self.settings.save()
        pygame.quit()
