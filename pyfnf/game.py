"""Partie en cours (PlayState), écran de mort, résultats et application principale."""
from __future__ import annotations

import math
import random
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pygame

from .achievements import Achievement, load_all as load_achievements
from .assets import Assets, SparrowAtlas
from .data import FunkinData, difficulty_sort_key
from .dialogue import Dialogue, Video, conversation_path, video_path
from .gamepad import Gamepads
from .lang import translate
from .mods import ScriptHost, discover, editor_saves_dir, mods_dir
from .settings import Settings
from .stage import Character, Stage, to_screen
from .ui import SUBTITLE_STYLE, draw_subtitle
from .ui import (BLACK, CYAN, DIRECTIONS, HEIGHT, LANE_COLORS, RED, WHITE, WIDTH, YELLOW, BaseState, colorize, ease_out, fit, key_hints, lerp,
                 parse_color, scale_by, shade, tint)
from . import menus

FPS = 60
OUTLINE_8 = ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, -2), (-2, 2), (2, 2))
VERSION = "2.0"
# Cinématiques vidéo officielles (nom du fichier dans videos/) : début et fin de chanson en mode histoire.
OFFICIAL_INTRO = {"ugh": "ughCutscene", "guns": "gunsCutscene", "stress": "stressCutscene", "stress:pico": "stressPicoCutscene",
                  "darnell": "darnellCutscene"}
OFFICIAL_END = {"2hot": "2hotCutscene", "blazin": "blazinCutscene"}
MENU_BPM = 102


def slice_sound(sound: pygame.mixer.Sound, start_ms: float) -> pygame.mixer.Sound:
    """Copie du son à partir de start_ms (pygame ne sait pas démarrer un Sound au milieu)."""
    frequency, size, channels = pygame.mixer.get_init()
    frame_bytes = abs(size) // 8 * channels
    raw = sound.get_raw()
    offset = int(start_ms / 1000 * frequency) * frame_bytes
    return pygame.mixer.Sound(buffer=raw[min(offset, len(raw)):] or b"\0" * frame_bytes)


def resample_sound(sound: pygame.mixer.Sound, rate: float) -> pygame.mixer.Sound:
    """Son joué `rate` fois plus vite (la hauteur suit, comme le playback rate de Psych). Par blocs pour la mémoire."""
    import numpy as np
    source = pygame.sndarray.array(sound)
    count = len(source)
    out_count = max(1, int(count / rate))
    out = np.empty((out_count, *source.shape[1:]), dtype=source.dtype)
    block = 1 << 19
    for start in range(0, out_count, block):
        position = np.arange(start, min(out_count, start + block)) * rate
        index = position.astype(np.int64)
        frac = position - index
        if source.ndim > 1:
            frac = frac[:, None]
        following = np.minimum(index + 1, count - 1)
        out[start:start + len(position)] = (source[index] * (1 - frac) + source[following] * frac).astype(source.dtype)
    return pygame.sndarray.make_sound(out)


def flx_ease(name: str, direction: str | None = None):
    """Courbe d'animation FlxEase : « expoOut », ou « expo » + easeDir « Out » (événements ZoomCamera)."""
    for suffix in ("InOut", "In", "Out"):
        if name.endswith(suffix) and name != suffix:
            name, direction = name[:-len(suffix)], suffix
            break
    bounce_out = lambda t: (7.5625 * t * t if t < 1 / 2.75 else 7.5625 * (t - 1.5 / 2.75) ** 2 + .75 if t < 2 / 2.75
                            else 7.5625 * (t - 2.25 / 2.75) ** 2 + .9375 if t < 2.5 / 2.75 else 7.5625 * (t - 2.625 / 2.75) ** 2 + .984375)
    ease_in = {
        "sine": lambda t: 1 - math.cos(t * math.pi / 2), "quad": lambda t: t ** 2, "cube": lambda t: t ** 3,
        "quart": lambda t: t ** 4, "quint": lambda t: t ** 5, "expo": lambda t: 0.0 if t <= 0 else 2 ** (10 * (t - 1)),
        "circ": lambda t: 1 - math.sqrt(max(0.0, 1 - t * t)), "back": lambda t: t * t * (2.70158 * t - 1.70158),
        "elastic": lambda t: 1 - (2 ** (-10 * (1 - t)) * math.sin((1 - t - .1) * 2 * math.pi / .4) + 1),
        "bounce": lambda t: 1 - bounce_out(1 - t), "smoothStep": lambda t: 2 * (t / 2) ** 2 * (3 - t),
    }.get(name)
    if ease_in is None:
        return lambda t: t  # linear, ou nom inconnu
    if direction == "Out":
        return lambda t: 1 - ease_in(1 - t)
    if direction == "InOut":
        return lambda t: ease_in(2 * t) / 2 if t < .5 else 1 - ease_in(2 - 2 * t) / 2
    return ease_in


def audio_paths(assets, song_id: str, variation: str, profile: dict) -> tuple[Path, list[Path]]:
    """Instru + pistes de voix d'une chanson (variation comprise : Inst-erect.ogg, Voices-bf-erect.ogg...).

    Chaque fichier est cherché séparément dans les mods puis le jeu de base : un mod peut remplacer
    une seule voix sans devoir recopier l'instru.
    """
    folders = assets.all_paths(f"songs/{song_id}") or [assets.path(f"songs/{song_id}")]

    def find(name: str) -> Path | None:
        return next((folder / name for folder in folders if (folder / name).is_file()), None)

    def glob(pattern: str) -> list[Path]:
        seen, found = set(), []
        for folder in folders:
            for path in sorted(folder.glob(pattern)):
                if path.name not in seen:
                    seen.add(path.name)
                    found.append(path)
        return found

    suffix = f"-{variation}" if variation else ""
    instrumental = find(f"Inst{suffix}.ogg") or find("Inst.ogg") or folders[0] / "Inst.ogg"
    voices: list[Path] = []
    vocal_ids = [*profile.get("player_vocals", []), *profile.get("opponent_vocals", [])]
    removable_suffixes = ("-holding-nene", "-holding-gf", "-playable", "-christmas", "-pixel",
                          "-tankmen", "-blazin", "-bloody", "-angry", "-car", "-dark")
    for vocal_id in vocal_ids:
        aliases = [str(vocal_id)]
        simplified = str(vocal_id)
        for removable in removable_suffixes:
            simplified = simplified.replace(removable, "")
        if simplified not in aliases:
            aliases.append(simplified)
        names = []
        for alias in aliases:
            if variation:
                names.append(f"Voices-{alias}-{variation}.ogg")
            names.append(f"Voices-{alias}.ogg")
        match = next((path for path in map(find, names) if path), None)
        if match and match not in voices:
            voices.append(match)
    if not voices and variation:
        voices.extend(glob(f"Voices-*-{variation}.ogg")[:2])
    elif not voices:
        voices.extend(path for path in glob("Voices-*.ogg") if path.stem.count("-") == 1)
    if not voices and find(f"Voices{suffix}.ogg"):
        voices.append(find(f"Voices{suffix}.ogg"))
    return instrumental, voices


@dataclass
class PlayNote:
    time: float
    lane: int
    player: bool
    length: float
    kind: str = ""
    state: str = "pending"
    color: tuple[int, int, int] | None = None  # teinte optionnelle posée par un script
    avoid: bool = False  # note à éviter (posé par un script) : la laisser passer ne compte pas comme un raté
    alpha: float = 1.0  # opacité posée par un script (0 = invisible : notes fantômes, Hidden / Sudden)


class PlayState(BaseState):
    """Une chanson en cours. Les scripts des mods reçoivent cet objet sous le nom `game`."""

    LANE_SPACE = 112
    ARROW_SIZE = 104
    PLAYER_X, OPPONENT_X = 740, 100  # chaque ligne de 4 flèches centrée dans sa moitié d'écran

    def __init__(self, app: "FunkinApp", song_id: str, chart_key: str, audio: list[pygame.mixer.Sound] | None = None,
                 start_ms: float = 0.0, intro: bool = True):
        super().__init__(app)
        self.assets = app.assets
        self.settings = app.settings
        self.song = app.data.songs[song_id]
        self.chart_key = chart_key if chart_key in self.song.charts else next(iter(self.song.charts))
        chart = app.data.load_chart(self.song, self.chart_key)
        self.profile = chart["profile"]
        self.difficulty = chart["difficulty"]
        self.notes = [PlayNote(**note) for note in chart["notes"]]
        self.events = sorted(chart["events"], key=lambda event: float(event.get("t", 0)))
        self.event_index = 0
        self.chart_speed = chart["scroll_speed"]
        self.story = app.story_week is not None and not app.editor_return
        # Modificateurs du menu Ctrl du freeplay ; le mode histoire et l'éditeur gardent les réglages normaux.
        modifiers = {} if self.story or app.editor_return else app.modifiers
        self.fixed_scroll = float(modifiers.get("scroll", app.settings.scroll_speed))  # 0 = AUTO (vitesse du chart)
        self.rate = float(modifiers.get("rate", 1.0))
        self.opponent_mode = bool(modifiers.get("opponent", False))
        self.judgment = str(modifiers.get("judgment", app.settings.judgment))
        self.practice = bool(modifiers.get("practice", False))  # impossible de perdre
        self.botplay = bool(modifiers.get("botplay", False))  # le jeu joue tout seul
        self.base_scroll_speed = self.scroll_speed = self.fixed_scroll if self.fixed_scroll > 0 else self.chart_speed
        if self.opponent_mode:
            for note in self.notes:  # jouer l'adversaire : ses notes deviennent celles du joueur
                note.player = not note.player
        self.variation = chart["variation"]
        self.bpm_changes = sorted(self.profile.get("bpm_changes") or [(0.0, self.song.bpm)])
        self.note_style = self.profile.get("note_style") or "funkin"
        self.pixel = self.note_style == "pixel"
        self.start_ms = max(0.0, start_ms)
        self.downscroll = app.settings.downscroll
        self.receptor_y = HEIGHT - 50 - self.ARROW_SIZE if self.downscroll else 50
        self.warnings: list[str] = []
        app.loading_step(.1)
        self.stage = Stage(app.assets, self.profile["stage"])
        app.loading_step(.35)
        if not app.assets.path(f"data/stages/{self.profile['stage']}.json").is_file():
            self.warnings.append(f"Stage '{self.profile['stage']}' not found")
        self.player = self._character(self.profile["player"], player=True)
        app.loading_step(.5)
        self.opponent = self._character(self.profile["opponent"])
        gf_id = self.profile.get("girlfriend") or ""
        self.girlfriend = self._character(gf_id) if gf_id else None
        if self.girlfriend:
            self.stage.add_character("gf", self.girlfriend)
        # Tutorial : sans GF déclarée, une adversaire "gf" prend la place de GF sur les enceintes.
        self.stage.add_character("dad", self.opponent, "gf" if not gf_id and self.profile["opponent"].startswith("gf") else None)
        self.stage.add_character("bf", self.player)
        self.characters = [character for character in (self.player, self.opponent, self.girlfriend) if character]
        # Personnage piloté par le joueur et personnage automatique (inversés en mode adversaire).
        self.human, self.cpu = (self.opponent, self.player) if self.opponent_mode else (self.player, self.opponent)
        for index, character in enumerate(self.characters):
            app.loading_step(.55 + .2 * index / len(self.characters))
            # Repos, chant, et les poses que les scripts déclenchent (cheer, hey, peur) ; GF : toutes ses poses.
            # Sinon l'image est calculée en direct à sa 1re apparition (pic à 30 ms, ex. GF qui applaudit dans le mod).
            base = ("idle", "danceleft", "danceright", "sing", "hey", "cheer", "scared")
            names = [name for name in character.anims if character is self.girlfriend or name.lower().startswith(base)]
            character.warm([name for name in names if not name.lower().startswith(("firstdeath", "death"))], self.stage.zoom)
        # Décors animés en atlas Animate (éclairs de la Week 2...) : préparés au chargement, sinon le jeu saccade
        # la première fois que l'animation se joue.
        animated = [prop for prop in self.stage.props.values() if hasattr(prop, "anims") and len(prop.anims) > 1
                    and any(anim.frames is None for anim in prop.anims.values())]
        for prop in animated:
            app.loading_step(.8)
            prop.warm(list(prop.anims), self.stage.zoom)
        # Décors des événements ChangeStage : chargés maintenant, sinon la chanson saccade au changement.
        self.next_stages = {}
        for event in self.events:
            value = event.get("v")
            stage_id = str(value.get("stage", "") if isinstance(value, dict) else value)
            if event.get("e") == "ChangeStage" and stage_id not in self.next_stages and app.assets.path(f"data/stages/{stage_id}.json").is_file():
                self.next_stages[stage_id] = Stage(app.assets, stage_id)
        self.cam = list(self._midpoint())
        self.cam_target = list(self.cam)
        self.song_started = False
        self.countdown_beat = -6
        self.countdown_image: pygame.Surface | None = None
        self.countdown_at = 0
        self.song_time = self.start_ms - 5 * self.beat_length(self.start_ms)
        self.last_beat = math.floor(self.beat_at(self.song_time))
        self.last_step = math.floor(self.beat_at(self.song_time) * 4)
        self.paused = False
        self.pause_menu: PauseMenu | None = None
        self.score = 0; self.combo = 0; self.max_combo = 0; self.misses = 0
        self.sick = 0; self.good = 0; self.bad = 0; self.shit = 0; self.weighted = 0.0; self.judged = 0
        self.health = 50.0
        self.rating_text = ""; self.rating_at = 0
        self.key_down = [False] * 4
        self.confirm_at = [[-10 ** 9] * 4, [-10 ** 9] * 4]
        self.key_lanes = {
            pygame.K_LEFT: 0, pygame.K_DOWN: 1, pygame.K_UP: 2, pygame.K_RIGHT: 3,
            **{key: lane for lane, key in enumerate(app.settings.keybinds)},
        }
        self.audio_sounds: list[pygame.mixer.Sound] = audio or []
        self.audio_channels: list[pygame.mixer.Channel] = []
        self.instrument_channel: pygame.mixer.Channel | None = None
        self.audio_started_at = 0
        self.pause_started_at = 0
        self.finished = False
        self.ending = False
        self.icon_bop = 0
        # Zoom de caméra comme V-Slice : camera_zoom multiplie le zoom du décor (événement ZoomCamera) ; la caméra et
        # l'interface « battent » tous les bop_rate temps (événement SetCameraBop, option ZOOMS DE CAMÉRA).
        self.camera_zoom = 1.0
        self.zoom_tween = None  # (départ, cible, début en ms de chanson, durée ms, courbe)
        self.bop_rate, self.bop_intensity, self.hud_bop_intensity = 4, 1.015, .03
        self.cam_bop, self.hud_zoom = 1.0, 1.0
        self.flash = self.shake = None  # événements FlashScreen / ShakeCamera (voir flash_screen, shake_camera)
        self._canvas = None  # toile du zoom arrière
        self.strum_alpha = [[1.0] * 4, [1.0] * 4]  # opacité des récepteurs [adversaire, joueur][flèche], pour les scripts
        self.subtitle = None  # (texte, fin en ms, style) : événement Subtitle ou show_subtitle() d'un script
        self.subtitle_style: dict = {}  # style commun du fichier subtitles.json ("style")
        self.song_subtitles = self._load_song_subtitles()
        self.hold_countdown = False  # un script peut le mettre à True pour une cinématique scriptée
        self.hud_visible = True  # un script peut cacher les flèches et le HUD (cinématique dans le décor)
        self.middle_strums = False  # un script peut mettre les flèches du joueur au milieu et cacher celles de l'adversaire
        self.end_scripted = False  # fin de chanson jouée par un script (voir finish)
        self.overlays: list = []
        self._tinted: dict = {}
        self._load_arrows()
        self.player_icon = self._load_icon(self.player)
        self.opponent_icon = self._load_icon(self.opponent)
        pygame.mixer.music.stop()
        if not self.audio_sounds:
            app.loading_step(.75)
            self._prepare_audio()
        app.loading_step(.95)
        if self.start_ms:
            for note in self.notes:
                if note.time < self.start_ms - 20:
                    note.state = "skip"
        # Comme le jeu officiel : cinématique / dialogue en mode histoire, et toujours pour les Pico Mix (même en freeplay).
        self.intro = intro  # False quand on recommence la chanson (les scripts ne rejouent pas leur cinématique)
        if intro and (self.story or (self.variation == "pico" and not app.editor_return)) and not self.start_ms:
            song_id = self.song.song_id
            self.play_video(song_id) or self.play_video(OFFICIAL_INTRO.get(f"{song_id}:{self.variation}", OFFICIAL_INTRO.get(song_id, "")))
            self.start_dialogue(self._conversation_id())
        self.scripts = ScriptHost(app.script_paths(self.song.song_id), mods_dir() / "errors.log")
        self.scripts.call("on_create", self)
        if self.start_ms:
            while self.event_index < len(self.events) and float(self.events[self.event_index].get("t", 0)) <= self.start_ms:
                self.run_event(self.events[self.event_index]); self.event_index += 1
            self.cam = list(self.cam_target)
        # Le countdown commence seulement une fois tout chargé (audio, persos, scripts, cinématiques).
        self.started = pygame.time.get_ticks()
        now = datetime.now()
        if now.weekday() == 4 and now.hour >= 18:
            app.unlock("friday-night")

    # ---------- chargement ----------
    def _character(self, character_id: str, player: bool = False) -> Character:
        character = Character(self.app.assets, character_id, player)
        if not character.loaded:
            self.warnings.append(f"Character '{character_id}' not found")
        return character

    def _midpoint(self) -> tuple[float, float]:
        (ax, ay), (bx, by) = self.opponent.focus(), self.player.focus()
        return (ax + bx) / 2, (ay + by) / 2

    def _conversation_id(self, suffix: str = "") -> str:
        if self.variation and conversation_path(self.assets, f"{self.song.song_id}-{self.variation}{suffix}"):
            return f"{self.song.song_id}-{self.variation}{suffix}"
        return self.song.song_id + suffix

    def _note_style(self) -> dict:
        path = self.assets.path(f"data/notestyles/{self.note_style}.json")
        try:
            return self.assets.json(path).get("assets", {}) if path.is_file() else {}
        except ValueError:
            return {}

    def _load_arrows(self) -> None:
        style = self._note_style()
        note_cfg, strum_cfg = style.get("note", {}), style.get("noteStrumline", {})
        notes = self.assets.atlas(str(note_cfg.get("assetPath", "shared:notes")))
        strums = self.assets.atlas(str(strum_cfg.get("assetPath", "shared:noteStrumline")))
        if not isinstance(notes, SparrowAtlas):
            notes = self.assets.atlas("shared:notes")
        if not isinstance(strums, SparrowAtlas):
            strums = self.assets.atlas("shared:noteStrumline")
        pixel = bool(note_cfg.get("isPixel", False))
        strum_data, note_data = strum_cfg.get("data", {}), note_cfg.get("data", {})
        self.note_images, self.static_strums, self.press_strums, self.confirm_strums = [], [], [], []
        for direction in DIRECTIONS:
            title = direction.title()

            def prefix(key: str, default: str) -> str:
                return str(strum_data.get(f"{direction}{key}", {}).get("prefix", default))

            static = strums.animation(prefix("Static", f"static{title}0"))[0]
            bounds = static.get_bounding_rect()
            # Même facteur pour repos / appui / confirm : le halo du confirm dépasse au lieu de rétrécir la flèche.
            factor = self.ARROW_SIZE / max(1, bounds.width, bounds.height)
            self.static_strums.append(self._crop_scale(static, factor, pixel))
            self.press_strums.append(self._crop_scale(strums.animation(prefix("Press", f"press{title}0"))[0], factor, pixel))
            self.confirm_strums.append(self._crop_scale(strums.animation(prefix("Confirm", f"confirm{title}0"))[0], factor, pixel))
            note = notes.animation(str(note_data.get(direction, {}).get("prefix", f"note{title}")))[0]
            note_bounds = note.get_bounding_rect()
            self.note_images.append(self._crop_scale(note, self.ARROW_SIZE / max(1, note_bounds.width, note_bounds.height), pixel))
            note_factor = self.ARROW_SIZE / max(1, note_bounds.width, note_bounds.height)
        self._load_holds(style.get("holdNote", {}), note_factor, float(note_cfg.get("scale", 1) or 1))
        self._load_splashes(style.get("noteSplash", {}), factor / float(strum_cfg.get("scale", 1) or 1))
        self._load_hold_covers(style.get("holdNoteCover", {}), factor / float(strum_cfg.get("scale", 1) or 1))

    def _load_hold_covers(self, config: dict, k: float) -> None:
        """Éclaboussures des notes longues (NoteHoldCover officiel) : départ, boucle tant que la note est tenue,
        explosion quand le joueur la finit. Chaque lane : {"start": [...], "hold": [...], "end": [...]}."""
        self.hold_covers: dict = {}
        self.cover_frames: list[dict] = [{} for _ in range(4)]
        data = config.get("data") or {}
        if not config or data.get("enabled") is False:
            return
        scale = float(config.get("scale", 1) or 1) * k
        pixel = bool(config.get("isPixel", False))
        for lane, direction in enumerate(DIRECTIONS):
            entry = data.get(direction) or {}
            atlas = self.assets.atlas(str(entry.get("assetPath") or config.get("assetPath") or ""))
            if not isinstance(atlas, SparrowAtlas):
                continue
            parts = {}
            for part in ("start", "hold", "end"):
                prefix = str((entry.get(part) or {}).get("prefix", ""))
                parts[part] = [scale_by(frame, scale, pixel) for frame in atlas.animation(prefix)] if prefix and atlas.has(prefix) else []
            if parts["hold"]:
                cx, cy = parts["hold"][0].get_bounding_rect().center  # même repère pour les 3 : centré sur la flèche
                self.cover_frames[lane] = {part: [(image, -cx, -cy) for image in images] for part, images in parts.items()}

    def _draw_hold_covers(self, screen: pygame.Surface, center_y: int) -> None:
        if not any(self.cover_frames):
            return
        now = pygame.time.get_ticks()
        for note in self.notes:  # une note longue commence à être tenue : départ de l'éclaboussure
            if note.state == "holding" and self.cover_frames[note.lane] and (note.player, note.lane) not in self.hold_covers:
                if not (self.middle_strums and not note.player):
                    self.hold_covers[(note.player, note.lane)] = [note, "start", now]
        for key, cover in list(self.hold_covers.items()):
            note, part, start = cover
            frames = self.cover_frames[key[1]]
            index = int((now - start) * 24 / 1000)
            if note.state == "holding":
                if part == "start" and index >= len(frames["start"]):
                    cover[1:] = ["hold", now]; part, index = "hold", 0
            elif part != "end" and note.state == "hit" and key[0] and frames["end"]:
                cover[1:] = ["end", now]; part, index = "end", 0  # note longue finie par le joueur : explosion
            elif part != "end" or index >= len(frames["end"]):
                del self.hold_covers[key]
                continue
            images = frames[part] or frames["hold"]
            image, dx, dy = images[index % len(images)] if part == "hold" else images[min(index, len(images) - 1)]
            ox, oy = self.strum_offset(key[0], key[1])
            screen.blit(image, (round(self.strum_x(key[0], key[1]) + ox + dx), round(center_y + oy + dy)))

    def _load_splashes(self, config: dict, k: float) -> None:
        """Splashs des SICK!! comme NoteSplash.hx / Strumline.playNoteSplash : 2 ou 3 variantes par couleur, au hasard,
        24 ± 2 images/s, transparence du style ; k = notre échelle des flèches / celle du jeu officiel."""
        self.splashes: list = []
        self.splash_frames: list[list[list[tuple[pygame.Surface, float, float]]]] = [[] for _ in range(4)]
        data = config.get("data") or {}
        if not config or data.get("enabled") is False:
            return
        atlas = self.assets.atlas(str(config.get("assetPath", "shared:noteSplashes")))
        if not isinstance(atlas, SparrowAtlas):
            return
        scale = float(config.get("scale", 1) or 1) * k
        pixel = bool(config.get("isPixel", False))
        self.splash_add = str(data.get("blendMode", "")).lower() in ("screen", "add")  # le noir du splash pixel disparaît
        self.splash_alpha = round(255 * float(config.get("alpha", 1) if config.get("alpha") is not None else 1))
        self.splash_fps = (int(data.get("framerateDefault", 24)), int(data.get("framerateVariance", 2)))
        for lane, direction in enumerate(DIRECTIONS):
            for entry in data.get(f"{direction}Splashes", []):
                frames = atlas.animation(str(entry.get("prefix", "")))
                if not frames or not atlas.has(str(entry.get("prefix", ""))):
                    continue
                images = [scale_by(frame, scale, pixel) for frame in frames]
                # Le dessin de la 1re image est centré sur la flèche ; les suivantes gardent le même repère.
                center = images[0].get_bounding_rect().center
                self.splash_frames[lane].append([(image, -center[0], -center[1]) for image in images])

    def _splash(self, lane: int, now: int) -> None:
        variants = self.splash_frames[lane] if hasattr(self, "splash_frames") else []
        if variants:
            fps = self.splash_fps[0] + random.randint(-self.splash_fps[1], self.splash_fps[1])
            self.splashes.append((lane, random.choice(variants), now, max(1, fps)))

    def _draw_splashes(self, screen: pygame.Surface, center_y: int) -> None:
        now = pygame.time.get_ticks()
        alive = []
        for lane, frames, start, fps in self.splashes:
            index = int((now - start) * fps / 1000)
            if index >= len(frames):
                continue
            alive.append((lane, frames, start, fps))
            image, dx, dy = frames[index]
            ox, oy = self.strum_offset(True, lane)
            position = (round(self.strum_x(True, lane) + ox + dx), round(center_y + oy + dy))
            if self.splash_add:
                screen.blit(image, position, special_flags=pygame.BLEND_RGB_ADD)
                continue
            if self.splash_alpha < 255:
                image = image.copy(); image.set_alpha(self.splash_alpha)
            screen.blit(image, position)
        self.splashes = alive

    def _load_holds(self, config: dict, note_factor: float, note_scale: float) -> None:
        """Vraies traînées de FNF (NOTE_hold_assets) : 8 colonnes, pour chaque direction le morceau répété puis le bout."""
        self.hold_pieces: list[pygame.Surface | None] = [None] * 4
        self.hold_ends: list[pygame.Surface | None] = [None] * 4
        path = self.assets.resolve_image(str(config.get("assetPath", "NOTE_hold_assets")))
        if not path or path.suffix != ".png":
            path = self.assets.resolve_image("NOTE_hold_assets")
        if not path or path.suffix != ".png":
            return
        sheet = self.assets.image(path)
        column = sheet.get_width() // 8
        pixel = bool(config.get("isPixel", False)) or self.pixel
        factor = note_factor * float(config.get("scale", note_scale) or note_scale) / note_scale
        for lane in range(4):
            piece = sheet.subsurface((lane * 2 * column, 0, column, sheet.get_height())).copy()
            end = sheet.subsurface(((lane * 2 + 1) * column, 0, column, sheet.get_height())).copy()
            # Le bout s'arrête à la première ligne vide (une fine bande décorative traîne en bas de la feuille).
            rows = next((y for y in range(end.get_height()) if all(end.get_at((x, y)).a == 0 for x in range(end.get_width()))), end.get_height())
            end = end.subsurface((0, 0, column, max(1, rows))).copy()
            bounds = piece.get_bounding_rect()
            if bounds.width:
                piece = piece.subsurface((bounds.x, 0, bounds.width, piece.get_height())).copy()
                end = end.subsurface((bounds.x, 0, min(bounds.width, end.get_width() - bounds.x), end.get_height())).copy()
            self.hold_pieces[lane] = scale_by(piece, factor, pixel)
            self.hold_ends[lane] = scale_by(end, factor, pixel)

    @staticmethod
    def _crop_scale(surface: pygame.Surface, factor: float, pixel: bool = False) -> pygame.Surface:
        bounds = surface.get_bounding_rect()
        if bounds.width and bounds.height:
            surface = surface.subsurface(bounds).copy()
        return scale_by(surface, factor, pixel)

    def _load_icon(self, character: Character) -> list[pygame.Surface] | None:
        frames = self.app.icon_frames(character.icon_id)
        scaler = pygame.transform.scale if character.icon_pixel else pygame.transform.smoothscale
        return [scaler(frame, (130, 130)) for frame in frames] if frames else None

    def _audio_paths(self) -> tuple[Path, list[Path]]:
        return audio_paths(self.app.assets, self.song.song_id, self.variation, self.profile)

    def _prepare_audio(self) -> None:
        instrumental, voices = self._audio_paths()
        if not instrumental.is_file():
            self.warnings.append(f"songs/{self.song.song_id}/Inst.ogg not found")
            return
        for path in [instrumental, *voices[:6]]:
            try:
                sound = pygame.mixer.Sound(path)
                self.audio_sounds.append(resample_sound(sound, self.rate) if abs(self.rate - 1) > .001 else sound)
            except pygame.error:
                self.warnings.append(f"Can't read {path.name}")

    # ---------- API pour les scripts ----------
    def start_dialogue(self, conversation_id: str) -> bool:
        """Lance une conversation data/dialogue/conversations/<id>.json. Le countdown attend sa fin."""
        if conversation_path(self.assets, conversation_id):
            self.overlays.append(("dialogue", conversation_id))
            return True
        return False

    def play_video(self, name: str) -> bool:
        """Joue videos/<name>.mp4 en plein écran. Le countdown attend sa fin."""
        path = None
        if name and self.settings.child_mode:
            path = video_path(self.assets, f"{name}-censored")
        path = path or (video_path(self.assets, name) if name else None)
        if path:
            self.overlays.append(("video", path))
            return True
        return False

    def start_countdown(self) -> None:
        """Fin d'une cinématique scriptée (hold_countdown) : le countdown démarre maintenant."""
        self.hold_countdown = False
        self.started = pygame.time.get_ticks()

    def unlock_achievement(self, achievement_id: str) -> None:
        self.app.unlock(achievement_id)

    def world_to_screen(self, x: float, y: float, scroll=(1.0, 1.0)) -> tuple[float, float]:
        """Point du décor -> position à l'écran avec la caméra actuelle."""
        return to_screen(x, y, self.cam, self.view_zoom, scroll)

    def flash_screen(self, color=(255, 255, 255), duration: float = 400.0) -> None:
        """Flash de la couleur donnée sur le décor, qui s'efface en `duration` ms (rien si FLASHING LIGHTS est coupé)."""
        if self.settings.flashing_lights:
            self.flash = (pygame.time.get_ticks(), max(1.0, duration), tuple(int(c) for c in list(color)[:3]))

    def shake_camera(self, intensity: float = 10.0, duration: float = 400.0) -> None:
        """Secousse de la caméra du décor : `intensity` pixels au début, qui s'amortit en `duration` ms."""
        self.shake = (pygame.time.get_ticks(), intensity, max(1.0, duration))

    @property
    def view_zoom(self) -> float:
        """Zoom réel de la caméra : décor x ZoomCamera x bop."""
        return self.stage.zoom * self.camera_zoom * self.cam_bop

    def _active_overlay(self):
        if not self.overlays:
            return None
        kind, value = self.overlays[0]
        if kind == "dialogue":
            self.overlays[0] = ("running", Dialogue(self.app, value))
        elif kind == "video":
            self.overlays[0] = ("running", Video(self.app, value))
        overlay = self.overlays[0][1]
        if getattr(overlay, "error", "") and overlay.error not in self.warnings:
            self.warnings.append(overlay.error)
        return overlay

    # ---------- temps / rythme ----------
    def beat_at(self, time_ms: float) -> float:
        beats = 0.0
        for index, (start, bpm) in enumerate(self.bpm_changes):
            end = self.bpm_changes[index + 1][0] if index + 1 < len(self.bpm_changes) else None
            if end is None or time_ms < end:
                return beats + (time_ms - start) * bpm / 60000
            beats += (end - start) * bpm / 60000
        return beats

    def beat_length(self, time_ms: float) -> float:
        bpm = next((bpm for start, bpm in reversed(self.bpm_changes) if time_ms >= start), self.bpm_changes[0][1])
        return 60000 / max(1.0, bpm)

    def current_song_time(self) -> float:
        """Temps exact au moment de l'appel (les touches ne doivent pas être jugées avec le temps de la frame d'avant)."""
        if self.song_started and not self.paused:
            return float(pygame.time.get_ticks() - self.audio_started_at) * self.rate
        return self.song_time

    @property
    def chart_time(self) -> float:
        """Position du chart après compensation de la latence mesurée."""
        return self.song_time - self.app.settings.offset_ms

    # ---------- audio ----------
    def start_audio(self) -> None:
        if not self.audio_sounds:
            self.finish(); return
        self.audio_channels = []
        sounds = [slice_sound(sound, self.start_ms / self.rate) for sound in self.audio_sounds] if self.start_ms else self.audio_sounds
        # Les canaux réservés sont armés dans la même itération du mixer SDL : Inst et Voices restent synchro.
        for index, sound in enumerate(sounds):
            channel = pygame.mixer.Channel(index)
            channel.stop(); channel.set_volume(self.app.volume); channel.play(sound)
            self.audio_channels.append(channel)
        self.instrument_channel = self.audio_channels[0]
        self.audio_started_at = pygame.time.get_ticks() - round(self.start_ms / self.rate)
        self.song_time = self.start_ms
        self.song_started = True

    def stop_audio(self) -> None:
        for channel in self.audio_channels:
            channel.stop()
        self.audio_channels.clear()

    # ---------- entrées ----------
    def event(self, event: pygame.event.Event) -> None:
        overlay = self.overlays[0][1] if self.overlays and self.overlays[0][0] == "running" else None
        if overlay:
            overlay.event(event)
            return
        if self.paused and self.pause_menu:
            self.pause_menu.event(event)
            return
        # Hook de script : on_key_down(game, event) renvoie True pour garder la touche (encart, mini-jeu...).
        if event.type == pygame.KEYDOWN and any(self.scripts.call("on_key_down", self, event)):
            return
        if event.type == pygame.KEYDOWN:
            if event.key in self.key_lanes and not self.paused and not self.botplay:
                lane = self.lane_for_key(self.key_lanes[event.key])
                if not self.key_down[lane]: self.hit_lane(lane)
                self.key_down[lane] = True
                return
            if event.key == pygame.K_7:
                self.open_chart_editor(); return
            if event.key == pygame.K_r and self.song_started and not self.finished:
                self.health = 0; self.game_over(); return
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.toggle_pause()
                return
        elif event.type == pygame.KEYUP and event.key in self.key_lanes:
            self.key_down[self.lane_for_key(self.key_lanes[event.key])] = False
        elif event.type == pygame.WINDOWFOCUSLOST and not self.paused and not self.finished:
            self.toggle_pause()

    def open_chart_editor(self) -> None:
        from .editors import ChartEditorState
        self.stop_audio()
        self.app.editor_return = None
        self.app.change(ChartEditorState(self.app, self.song.song_id, self.chart_key, max(0.0, self.chart_time)))

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        now = pygame.time.get_ticks()
        if self.paused:
            self.pause_started_at = now
            self.key_down = [False] * 4
            for channel in self.audio_channels:
                channel.pause()
            self.pause_menu = PauseMenu(self)
        else:
            if self.pause_menu:
                self.pause_menu.close()
            self.pause_menu = None
            paused_for = now - self.pause_started_at
            # Pendant le countdown c'est `started` qui porte le temps : on le décale aussi.
            self.started += paused_for
            if self.audio_started_at:
                self.audio_started_at += paused_for
            for channel in self.audio_channels:
                channel.unpause()

    def restart_song(self) -> None:
        self.stop_audio()
        self.app.change(PlayState(self.app, self.song.song_id, self.chart_key, self.audio_sounds, self.start_ms, intro=False))

    def exit_to_menu(self) -> None:
        self.stop_audio()
        self.app.back_to_menu()

    def hit_lane(self, lane: int) -> None:
        # Fin du compte à rebours comptée aussi : une note au temps 0 (Blazin') se tape souvent un peu en avance.
        if not self.song_started and (self.hold_countdown or self.overlays or self.song_time < self.start_ms - 200):
            return
        timing = self.current_song_time() - self.app.settings.offset_ms
        candidates = [note for note in self.notes if note.player and note.lane == lane and note.state == "pending" and abs(note.time - timing) <= 166]
        now = pygame.time.get_ticks()
        if not candidates:
            if self.settings.ghost_tapping and self.settings.hitsounds:
                self.app.play_sound("sounds/hitsound.mp3", self.settings.hitsound_volume)
            if not self.settings.ghost_tapping:
                self.break_combo(now); self.misses += 1; self.judged += 1; self.health = max(0, self.health - 4)
                self.human.sing(lane, now, miss=True)
                self.app.play_sound(f"shared/sounds/missnote{random.randint(1, 3)}.ogg", .5)
                self.scripts.call("on_ghost_miss", self, lane)
            return
        note = min(candidates, key=lambda item: abs(item.time - timing))
        if note.avoid:  # note à éviter touchée : compte comme un raté, précision comprise
            note.state = "hit"
            self.break_combo(now); self.misses += 1; self.judged += 1; self.health = max(0, self.health - 4)
            self.human.sing(lane, now, miss=True)
            self.app.play_sound(f"shared/sounds/missnote{random.randint(1, 3)}.ogg", .5)
            self.scripts.call("on_note_hit", self, note, "MISS")
            return
        difference = abs(note.time - timing)
        if difference <= 45: rating, points, weight = "SICK", 350, 1.0
        elif difference <= 90: rating, points, weight = "GOOD", 200, 1.0 if self.judgment == "easy" else .75
        elif difference <= 135: rating, points, weight = "BAD", 100, .5
        else: rating, points, weight = "SHIT", 50, .25
        note.state = "holding" if note.length > 0 else "hit"
        setattr(self, rating.lower(), getattr(self, rating.lower()) + 1)
        self.combo += 1; self.max_combo = max(self.max_combo, self.combo)
        self._set_human_voice(True)
        if self.combo >= 200:
            self.app.unlock("combo-200")
        if self.combo == 50 and self.girlfriend and self.girlfriend.has("combo50"):
            self.girlfriend.play_special("combo50", now)
        self.score += points + min(100, self.combo)
        self.weighted += weight; self.judged += 1; self.health = min(100, self.health + 1.8)
        if note.kind != "noanim":
            self.human.sing(lane, now)
        self.confirm_at[1][lane] = now
        if self.settings.hitsounds:
            self.app.play_sound("sounds/hitsound.mp3", self.settings.hitsound_volume)
        self.show_rating(rating)
        if rating == "SICK":
            self._splash(lane, now)
        self.scripts.call("on_note_hit", self, note, rating)

    def miss(self, note: PlayNote) -> None:
        note.state = "miss"
        self.break_combo(pygame.time.get_ticks()); self.misses += 1; self.judged += 1; self.health = max(0, self.health - 5)
        self.human.sing(note.lane, pygame.time.get_ticks(), miss=True)
        self.app.play_sound(f"shared/sounds/missnote{random.randint(1, 3)}.ogg", .5)
        self.scripts.call("on_note_miss", self, note)

    def break_combo(self, now: int) -> None:
        """Raté façon FNF : la voix du joueur se coupe jusqu'à la prochaine note, un combo de 10+ cassé
        affiche « 000 », GF fait la tête (drop70 au-delà de 70, sinon sad)."""
        if self.combo >= 10:
            self.show_rating("BREAK")
        gf = self.girlfriend
        if gf and self.combo >= 70 and gf.has("drop70"):
            gf.play_special("drop70", now)
        elif gf and self.combo > 5 and gf.has("sad"):
            gf.play_special("sad", now)
        self.combo = 0
        self._set_human_voice(False)

    def _set_human_voice(self, audible: bool) -> None:
        channels = self.audio_channels
        index = (2 if self.opponent_mode else 1) if len(channels) >= 3 else 1 if len(channels) == 2 else None
        if index is not None:
            channels[index].set_volume(self.app.volume if audible else 0)

    def show_rating(self, rating: str) -> None:
        self.rating_text = rating; self.rating_at = pygame.time.get_ticks()

    def accuracy(self) -> float:
        return self.weighted / self.judged * 100 if self.judged else 100

    # ---------- événements du chart ----------
    def focus_camera(self, target: int, x: float = 0, y: float = 0, instant: bool = False) -> None:
        self.cam_focus = (target, x, y)  # gardé pour recadrer après un changement de décor
        if target == 0: point = self.player.focus()
        elif target == 1: point = self.opponent.focus()
        elif target == 2 and self.girlfriend: point = self.girlfriend.focus()
        elif target == 2: point = self._midpoint()
        else: point = (0.0, 0.0)
        self.cam_target = [point[0] + x, point[1] + y]
        if instant:
            self.cam = list(self.cam_target)

    def _load_song_subtitles(self) -> list:
        """data/songs/<id>/subtitles.json (ou subtitles-<variation>.json) : {"en": [[début s, fin s, "texte"], ...],
        "fr": [...]}, temps de la chanson en secondes, même format que les sous-titres des vidéos."""
        if not self.app.settings.subtitles:
            return []
        folder = f"data/songs/{self.song.song_id}"
        path = self.app.assets.path(f"{folder}/subtitles-{self.variation}.json") if self.variation else None
        if path is None or not path.is_file():
            path = self.app.assets.path(f"{folder}/subtitles.json")
        try:
            data = self.app.assets.json(path) if path.is_file() else {}
        except ValueError:
            return []
        if not isinstance(data, dict):
            return []
        self.subtitle_style = data.get("style") if isinstance(data.get("style"), dict) else {}
        return data.get(self.app.settings.language) or data.get("en") or []

    def show_subtitle(self, text, duration: float = 3000.0, style: dict | None = None) -> None:
        """Affiche un sous-titre `duration` ms (option SOUS-TITRES respectée). `text` : une chaîne, ou
        {"fr": "...", "en": "..."} pour suivre la langue du jeu. `style` : voir ui.draw_subtitle (police, taille, couleurs...)."""
        if isinstance(text, dict):
            text = text.get(self.app.settings.language) or text.get("en") or text.get("text") or ""
        if self.app.settings.subtitles and text:
            self.subtitle = (str(text), pygame.time.get_ticks() + max(1.0, duration), style or {})

    def _draw_subtitles(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        line, style = (self.subtitle[0], self.subtitle[2]) if self.subtitle and now < self.subtitle[1] else ("", {})
        if not line and self.song_subtitles:
            seconds = self.chart_time / 1000
            entry = next((entry for entry in self.song_subtitles if entry[0] <= seconds < entry[1]), None)
            if entry:  # [début, fin, texte] ou [début, fin, texte, {style de cette ligne}]
                line = str(entry[2])
                style = {**self.subtitle_style, **(entry[3] if len(entry) > 3 and isinstance(entry[3], dict) else {})}
        if line:
            bottom = HEIGHT - 44 if self.downscroll or not self.hud_visible else 610  # au-dessus de la barre de vie
            draw_subtitle(self.app, screen, line, style, bottom)

    def change_stage(self, stage_id: str) -> bool:
        """Change de décor en pleine chanson (événement ChangeStage) : les personnages vont aux places du nouveau décor
        et la caméra se recadre. Les scripts reçoivent on_stage_change(game, stage_id)."""
        if not self.app.assets.path(f"data/stages/{stage_id}.json").is_file():
            self.warnings.append(f"Stage '{stage_id}' not found")
            return False
        stage = self.next_stages.pop(stage_id, None) or Stage(self.app.assets, stage_id)
        if self.girlfriend:
            stage.add_character("gf", self.girlfriend)
        stage.add_character("dad", self.opponent, "gf" if not self.girlfriend and self.opponent.id.startswith("gf") else None)
        stage.add_character("bf", self.player)
        self.stage = stage
        self.focus_camera(*getattr(self, "cam_focus", (1, 0, 0)), instant=True)
        self.scripts.call("on_stage_change", self, stage_id)
        return True

    def character_by_name(self, name) -> Character | None:
        name = str(name).lower()
        if name in ("bf", "boyfriend", "player", "0"): return self.player
        if name in ("dad", "opponent", "1"): return self.opponent
        if name in ("gf", "girlfriend", "2"): return self.girlfriend
        return None

    def run_event(self, event: dict) -> None:
        kind, value = event.get("e"), event.get("v")
        now = pygame.time.get_ticks()
        try:
            if kind == "FocusCamera":
                data = value if isinstance(value, dict) else {"char": value}
                self.focus_camera(int(float(data.get("char", 0))), float(data.get("x", 0) or 0), float(data.get("y", 0) or 0),
                                  str(data.get("ease", "")).upper() == "INSTANT")
            elif kind == "PlayAnimation" and isinstance(value, dict):
                character = self.character_by_name(value.get("target", "")) or self.stage.props.get(str(value.get("target")))
                if isinstance(character, Character):
                    character.play_special(str(value.get("anim", "idle")), now)
                elif character is not None:
                    character.play(str(value.get("anim", "idle")), now, force=True)
            elif kind == "ScrollSpeed" and isinstance(value, dict) and self.fixed_scroll <= 0:
                # Vitesse fixe choisie par le joueur : les changements de vitesse du chart sont ignorés.
                scroll = float(value.get("scroll", 1))
                self.scroll_speed = scroll if value.get("absolute") else self.chart_speed * scroll
            elif kind == "ZoomCamera" and isinstance(value, dict):
                zoom = float(value.get("zoom", 1) or 1)
                if value.get("mode") == "direct":  # « direct » : zoom absolu ; « stage » (défaut) : x zoom du décor
                    zoom /= self.stage.zoom
                ease = str(value.get("ease", "linear"))
                length = float(value.get("duration", 4) or 0) * self.beat_length(self.chart_time) / 4  # en pas (1/16)
                if ease == "INSTANT" or length <= 0:
                    self.camera_zoom, self.zoom_tween = zoom, None
                else:
                    began = float(event.get("t", self.chart_time))
                    self.zoom_tween = (self.camera_zoom, zoom, began, length, flx_ease(ease, value.get("easeDir")))
            elif kind == "Subtitle":
                data = value if isinstance(value, dict) else {"text": value}
                style = {key: data[key] for key in SUBTITLE_STYLE if key in data}
                self.show_subtitle(data, float(data.get("duration", 3000) or 3000), style)
            elif kind == "ChangeStage":
                self.change_stage(str(value.get("stage", "") if isinstance(value, dict) else value))
            elif kind == "FlashScreen":
                data = value if isinstance(value, dict) else {}
                self.flash_screen(data.get("color") or (255, 255, 255), float(data.get("duration", 400) or 400))
            elif kind == "ShakeCamera":
                data = value if isinstance(value, dict) else {}
                self.shake_camera(float(data.get("intensity", 10) or 0), float(data.get("duration", 400) or 400))
            elif kind == "SetCameraBop" and isinstance(value, dict):
                intensity = float(value.get("intensity", 1))
                self.bop_rate = int(float(value.get("rate", 4)))
                self.bop_intensity, self.hud_bop_intensity = 1 + .015 * intensity, .03 * intensity
            elif kind == "SetHealthIcon" and isinstance(value, dict):
                target = self.player if int(float(value.get("char", 0))) == 0 else self.opponent
                target.icon_id = str(value.get("id", target.icon_id))
                if target is self.player: self.player_icon = self._load_icon(target)
                else: self.opponent_icon = self._load_icon(target)
        except (TypeError, ValueError):
            pass
        self.scripts.call("on_event", self, event)

    # ---------- boucle ----------
    def update(self, dt: float) -> None:
        if self.paused and self.pause_menu:
            self.pause_menu.update(dt)
        if self.paused or self.finished:
            return
        now = pygame.time.get_ticks()
        overlay = self._active_overlay()
        if overlay:
            overlay.update(dt)
            if overlay.done:
                self.overlays.pop(0)
                if not self.overlays:
                    self.started = now
                    if self.ending:
                        self._complete()
                        return
            if not self.song_started:
                self.started = now
                return
        if self.ending:
            if self.end_scripted:
                self.scripts.call("on_update", self, dt)
            return
        if self.hold_countdown and not self.song_started:
            self.started = now
            self.scripts.call("on_update", self, dt)
            return
        if not self.song_started:
            self.song_time = self.start_ms + (now - self.started) * self.rate - 5 * self.beat_length(self.start_ms)
            count = math.floor(self.beat_at(self.song_time) - self.beat_at(self.start_ms))
            if count != self.countdown_beat:
                self.countdown_beat = count
                self.countdown_step(count)
            if self.song_time >= self.start_ms: self.start_audio()
        else:
            self.song_time = float(now - self.audio_started_at) * self.rate
            if self.instrument_channel and not self.instrument_channel.get_busy() and self.song_time > self.start_ms + 1000:
                self.finish(); return
        timing = self.chart_time
        beat_float = self.beat_at(timing)
        step_ms = self.beat_length(timing) / 4
        for beat in range(self.last_beat + 1, math.floor(beat_float) + 1):
            self.stage.beat(beat, now, step_ms)
            self.icon_bop = now
            if beat >= 0 and self.bop_rate > 0 and beat % self.bop_rate == 0 and self.settings.camera_zooms and self.hud_zoom < 1.35:
                self.cam_bop, self.hud_zoom = self.bop_intensity, self.hud_zoom + self.hud_bop_intensity
            self.scripts.call("on_beat", self, beat)
        self.last_beat = max(self.last_beat, math.floor(beat_float))
        settle = .95 ** (dt * 60)  # comme V-Slice : le bop revient vers 1 de 5 % par image (à 60 i/s)
        self.cam_bop, self.hud_zoom = 1 + (self.cam_bop - 1) * settle, 1 + (self.hud_zoom - 1) * settle
        if self.zoom_tween:
            start, target, began, length, curve = self.zoom_tween
            progress = min(1.0, max(0.0, (timing - began) / length))
            self.camera_zoom = start + (target - start) * curve(progress)
            if progress >= 1:
                self.zoom_tween = None
        for step in range(self.last_step + 1, math.floor(beat_float * 4) + 1):
            self.scripts.call("on_step", self, step)
        self.last_step = max(self.last_step, math.floor(beat_float * 4))
        while self.event_index < len(self.events) and float(self.events[self.event_index].get("t", 0)) <= timing:
            event = self.events[self.event_index]; self.event_index += 1
            self.run_event(event)
        self.human.holding = False
        if self.botplay and self.song_started:
            self.key_down = [any(n.player and n.lane == lane and n.state == "holding" for n in self.notes) for lane in range(4)]
            for note in self.notes:
                if note.time > timing:
                    break
                if note.player and note.state == "pending" and not note.avoid:
                    self.key_down[note.lane] = True
                    self.hit_lane(note.lane)
        for note in self.notes:
            if note.state == "holding":
                if not note.player:
                    self.confirm_at[0][note.lane] = now
                    self.cpu.last_sing = now
                    if timing >= note.time + note.length: note.state = "hit"
                elif timing >= note.time + note.length or (not self.key_down[note.lane] and timing >= note.time + note.length - 100):
                    note.state = "hit"; self.score += round(note.length / 20); self.health = min(100, self.health + 2)
                elif timing > note.time + 90 and not self.key_down[note.lane]:
                    note.state = "miss"; self.break_combo(now); self.misses += 1; self.health = max(0, self.health - 3)
                    self.human.sing(note.lane, now, miss=True)
                    self.scripts.call("on_note_miss", self, note)
                else:
                    self.human.holding = True
                    self.human.last_sing = now
                    self.health = min(100, self.health + dt * .8)
                continue
            if note.state != "pending": continue
            if note.time > timing + 400: break
            if not note.player and note.time <= timing:
                note.state = "holding" if note.length > 0 else "hit"
                if note.kind != "noanim":
                    self.cpu.sing(note.lane, now)
                self.confirm_at[0][note.lane] = now
                self.scripts.call("on_opponent_hit", self, note)
            elif note.player and note.time < timing - 180:
                if note.avoid:
                    note.state = "avoided"
                    self.scripts.call("on_note_avoided", self, note)
                else:
                    self.miss(note)
        follow = 1 - (1 - .04) ** (dt * 60)
        self.cam[0] += (self.cam_target[0] - self.cam[0]) * follow
        self.cam[1] += (self.cam_target[1] - self.cam[1]) * follow
        self.scripts.call("on_update", self, dt)
        if self.health <= 0 and not self.finished and not self.practice:
            self.game_over()

    def countdown_step(self, beat: int) -> None:
        style = "pixel" if self.pixel else "funkin"
        steps = {-4: ("introTHREE", None), -3: ("introTWO", "ready"), -2: ("introONE", "set"), -1: ("introGO", "go")}
        if beat not in steps:
            return
        sound, image = steps[beat]
        self.app.play_sound(f"shared/sounds/gameplay/countdown/{style}/{sound}.ogg")
        self.countdown_image = None
        if image:
            path = self.app.assets.path(f"shared/images/ui/countdown/{style}/{image}.png")
            if path.is_file():
                surface = self.app.assets.image(path)
                if self.pixel:
                    surface = scale_by(surface, 6, pixel=True)
                self.countdown_image = fit(surface, 640, 300)
        self.countdown_at = pygame.time.get_ticks()
        self.scripts.call("on_countdown", self, beat + 4)

    def game_over(self) -> None:
        self.finished = True
        self.stop_audio()
        self.scripts.call("on_game_over", self)
        self.app.deaths += 1
        if not self.app.editor_return:
            self.app.settings.stats["deaths"] = self.app.settings.stats.get("deaths", 0) + 1
            self.app.settings.save()
            self.app.unlock("death")
            if self.app.settings.stats["deaths"] >= 25:
                self.app.unlock("deaths-25")
        self.app.change(GameOverState(self.app, self))

    def finish(self, failed: bool = False) -> None:
        if self.finished or self.ending: return
        self.stop_audio()
        # Un script qui renvoie True joue sa propre fin dans le décor (ex. Stress Pico Mix) ; il appelle
        # game.end_cutscene_done() quand c'est fini.
        if True in self.scripts.call("on_song_end", self) and not failed:
            self.ending = self.end_scripted = True
            return
        if self.story and not failed:
            self.play_video(f"{self.song.song_id}-end") or self.play_video(OFFICIAL_END.get(self.song.song_id, ""))
            self.start_dialogue(self._conversation_id("-end"))
        if self.overlays:
            self.ending = True  # dialogue/vidéo de fin d'abord
            return
        self._complete(failed)

    def end_cutscene_done(self) -> None:
        """Fin d'une cinématique de fin jouée par un script (on_song_end a renvoyé True)."""
        self.end_scripted = False
        self._complete()

    def _complete(self, failed: bool = False) -> None:
        self.finished = True
        if self.app.editor_return:
            editor, self.app.editor_return = self.app.editor_return, None
            self.app.change(editor)
            return
        if not failed and not (self.botplay or self.practice):
            self.app.settings.save_score(f"{self.song.song_id}|{self.chart_key}", self.score)
            self.app.settings.save_accuracy(f"{self.song.song_id}|{self.chart_key}", self.accuracy())
            self.app.week_misses += self.misses
            self.app.unlock("first-song")
            if self.misses == 0:
                self.app.unlock("full-combo")
                if self.good == self.bad == self.shit == 0 and self.sick:
                    self.app.unlock("sick-only")
            if self.difficulty == "hard":
                self.app.unlock("hard")
            if self.difficulty in ("erect", "nightmare"):
                self.app.unlock("erect")
            if self.pixel:
                self.app.unlock("pixel")
        if self.story and not failed:
            # Mode histoire : un seul écran de résultats, à la fin de la semaine, avec les totaux de toutes les chansons.
            stats = self.app.week_stats
            for name in ("sick", "good", "bad", "shit", "misses", "score", "weighted", "judged"):
                stats[name] = stats.get(name, 0) + getattr(self, name)
            stats["max_combo"] = max(stats.get("max_combo", 0), self.max_combo)
            stats["total"] = stats.get("total", 0) + sum(1 for note in self.notes if note.player and note.state != "skip" and not note.avoid)
            if self.app.playlist_index + 1 < len(self.app.playlist):
                self.app.advance_playlist()
                return
            week = self.app.data.weeks[self.app.story_week]
            self.app.settings.save_score(f"week:{week.week_id}|{self.chart_key}", stats["score"])
            self.app.change(ResultsState(self.app, WeekResult(self, stats, week), failed))
            return
        self.app.change(ResultsState(self.app, self, failed))

    # ---------- dessin ----------
    def strum_x(self, player: bool, lane: int) -> int:
        """player = flèches du joueur humain (à gauche en mode adversaire)."""
        if self.middle_strums and player:  # Blazin' : flèches du joueur au milieu de l'écran
            return (WIDTH - 3 * self.LANE_SPACE - self.ARROW_SIZE) // 2 + lane * self.LANE_SPACE + self.ARROW_SIZE // 2
        right = player != self.opponent_mode
        return (self.PLAYER_X if right else self.OPPONENT_X) + lane * self.LANE_SPACE + self.ARROW_SIZE // 2

    def strum_offset(self, player: bool, lane: int) -> tuple[float, float]:
        """Décalage (dx, dy) d'une flèche ; ses notes, splashs et hold covers suivent. Un script peut remplacer cette
        fonction : game.strum_offset = lambda player, lane: (0, 20 * math.sin(...))."""
        return 0.0, 0.0

    def lane_for_key(self, lane: int) -> int:
        """Flèche jouée par une touche. Un script peut la remplacer (ex. miroir : game.lane_for_key = lambda lane: 3 - lane)."""
        return lane

    def _note_image(self, note: PlayNote) -> pygame.Surface:
        image = self.note_images[note.lane]
        if note.color is None:
            return image
        key = (note.lane, tuple(note.color))
        if key not in self._tinted:
            self._tinted[key] = colorize(image, tuple(note.color))
        return self._tinted[key]

    def _hold_parts(self, note: PlayNote) -> tuple[pygame.Surface | None, pygame.Surface | None]:
        """Morceau et bout de traînée de la note (recolorés comme la flèche si un script lui a donné une couleur)."""
        key = ("hold", note.lane, tuple(note.color) if note.color else None)
        if key not in self._tinted:
            piece, end = self.hold_pieces[note.lane], self.hold_ends[note.lane]
            if note.color and piece and end:
                piece, end = colorize(piece, tuple(note.color)), colorize(end, tuple(note.color))
            if piece and end:
                piece, end = piece.copy(), end.copy()
                piece.set_alpha(220); end.set_alpha(220)
                if self.downscroll:
                    piece, end = pygame.transform.flip(piece, False, True), pygame.transform.flip(end, False, True)
            self._tinted[key] = (piece, end)
        return self._tinted[key]

    def _draw_hold(self, screen: pygame.Surface, note: PlayNote, x: int, head: float, tail: float, alpha: int = 220) -> None:
        piece, end = self._hold_parts(note)
        if piece is not None and end is not None and alpha != 220:
            piece, end = piece.copy(), end.copy()
            piece.set_alpha(alpha); end.set_alpha(alpha)
        top, bottom = sorted((head, tail))
        if piece is None or end is None:
            color = note.color or LANE_COLORS[note.lane]
            rect = (x - 12, round(top), 24, round(bottom - top))
            pygame.draw.rect(screen, color, rect, border_radius=0 if self.pixel else 12)
            pygame.draw.rect(screen, BLACK, rect, 3, border_radius=0 if self.pixel else 12)
            return
        left = x - piece.get_width() // 2
        length = bottom - top
        end_h = min(end.get_height(), length)
        clip = screen.get_clip()
        screen.set_clip(pygame.Rect(0, round(top), screen.get_width(), max(1, round(length))).clip(clip))
        if self.downscroll:  # le bout est en haut, le morceau se répète vers la flèche
            screen.blit(end, (left, round(top)))
            y = top + end_h
            while y < bottom:
                screen.blit(piece, (left, round(y))); y += piece.get_height() - 1
        else:
            y = top
            while y < bottom - end_h:
                screen.blit(piece, (left, round(y))); y += piece.get_height() - 1
            screen.blit(end, (left, round(bottom - end.get_height())))
        screen.set_clip(clip)

    def _draw_notes(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        center_y = self.receptor_y + self.ARROW_SIZE // 2
        direction = -1 if self.downscroll else 1
        pixels_per_ms = .45 * self.scroll_speed / self.rate
        holding = {(note.player, note.lane): note.color for note in self.notes if note.state == "holding"}
        for side, player in ((0, False), (1, True)):
            if self.middle_strums and not player:
                continue  # flèches de l'adversaire cachées
            for lane in range(4):
                glowing = now - self.confirm_at[side][lane] < 140 or (player, lane) in holding
                if player and self.key_down[lane]:
                    image = self.confirm_strums[lane] if glowing else self.press_strums[lane]
                else:
                    image = self.confirm_strums[lane] if glowing and not player else self.static_strums[lane]
                color = holding.get((player, lane))
                if color and image is self.confirm_strums[lane]:
                    # Note tenue colorée par un script (ex. note dorée) : le récepteur brille de la même couleur.
                    key = ("confirm", lane, tuple(color))
                    if key not in self._tinted:
                        self._tinted[key] = colorize(image, tuple(color))
                    image = self._tinted[key]
                alpha = self.strum_alpha[side][lane]
                if alpha <= 0:
                    continue
                if alpha < 1:
                    image = image.copy(); image.set_alpha(round(255 * alpha))
                dx, dy = self.strum_offset(player, lane)
                screen.blit(image, image.get_rect(center=(self.strum_x(player, lane) + dx, center_y + dy)))
        timing = self.chart_time
        for note in self.notes:
            if note.state not in ("pending", "holding", "miss"): continue
            distance = note.time - timing
            if distance > (HEIGHT + 100) / pixels_per_ms: break
            if self.middle_strums and not note.player:
                continue
            missed = note.state == "miss"
            if missed and (-distance - note.length) * pixels_per_ms > HEIGHT:
                continue  # la note ratée est sortie de l'écran
            if note.alpha <= 0:
                continue
            dx, dy = self.strum_offset(note.player, note.lane)  # la note suit sa flèche
            head = center_y + dy + direction * (max(0, distance) if note.state == "holding" else distance) * pixels_per_ms
            x = self.strum_x(note.player, note.lane) + dx
            if note.length > 0:
                tail = center_y + dy + direction * (note.time + note.length - timing) * pixels_per_ms
                if (tail - head) * direction > 0:
                    self._draw_hold(screen, note, x, head, tail, round((70 if missed else 220) * note.alpha))
            if note.state in ("pending", "miss") and -self.ARROW_SIZE < head < HEIGHT + self.ARROW_SIZE:
                image = self._note_image(note)
                alpha = (77 if missed else 255) * note.alpha
                if alpha < 255:
                    image = image.copy(); image.set_alpha(round(alpha))
                screen.blit(image, image.get_rect(center=(x, round(head))))

    def _popup(self, name: str) -> pygame.Surface | None:
        style = "pixel" if self.pixel else "funkin"
        path = self.app.assets.path(f"images/ui/popup/{style}/{name}.png")
        if not path.is_file():
            path = self.app.assets.path(f"images/ui/popup/funkin/{name}.png")
        if not path.is_file():
            return None
        key = ("popup", path)
        if key not in self.app.cache:
            surface = self.app.assets.image(path)
            if self.pixel and surface.get_width() < 150:
                surface = scale_by(surface, 4.2, pixel=True)
            self.app.cache[key] = surface
        return self.app.cache[key]

    def _draw_hud(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        bar_y = 78 if self.downscroll else 640
        bar_rect = pygame.Rect(340, bar_y, 600, 18)
        pygame.draw.rect(screen, BLACK, bar_rect.inflate(8, 8))
        pygame.draw.rect(screen, (255, 40, 95), bar_rect)
        shown = 100 - self.health if self.opponent_mode else self.health
        player_width = round(bar_rect.width * shown / 100)
        pygame.draw.rect(screen, (80, 235, 65), (bar_rect.right - player_width, bar_rect.y, player_width, bar_rect.height))
        marker_x = bar_rect.right - player_width
        bop = max(0.0, 1 - (now - self.icon_bop) / 250) * .2
        size = round(130 * (1 + bop))
        if self.opponent_icon:
            frame = self.opponent_icon[1 if shown > 80 and len(self.opponent_icon) > 1 else 0]
            frame = pygame.transform.smoothscale(frame, (size, size))
            screen.blit(frame, frame.get_rect(midright=(marker_x + 18, bar_rect.centery)))
        if self.player_icon:
            frame = self.player_icon[1 if shown < 20 and len(self.player_icon) > 1 else 0]
            frame = pygame.transform.flip(pygame.transform.smoothscale(frame, (size, size)), True, False)
            screen.blit(frame, frame.get_rect(midleft=(marker_x - 18, bar_rect.centery)))
        tr = self.app.tr
        self.app.text(screen, f"{tr('Score')}: {self.score} | {tr('Misses')}: {self.misses} | {tr('Accuracy')}: {self.accuracy():.2f}% | {tr('Combo')}: {self.combo}",
                      (WIDTH // 2, bar_y + 36), 21, center=True, outline=True, raw=True)
        age = now - self.rating_at
        if age < 650 and self.rating_text:
            rise = round(age / 650 * 24)
            if self.rating_text == "BREAK":
                self._draw_combo(screen, 380 - rise)
            else:
                rating = self._popup(self.rating_text.lower())
                if rating:
                    rating = fit(rating, 260, 110)
                    screen.blit(rating, (WIDTH // 2 - rating.get_width() // 2, 260 - rise))
                if self.combo >= 10:
                    self._draw_combo(screen, 380 - rise)

    def _draw_combo(self, screen: pygame.Surface, y: int) -> None:
        images = [self._popup(f"num{digit}") for digit in f"{self.combo:03d}"]
        if not all(images):
            self.app.text(screen, str(self.combo), (WIDTH // 2, y), 52, center=True, outline=True, raw=True); return
        images = [fit(image, 52, 60) for image in images]
        x = WIDTH // 2 - sum(image.get_width() for image in images) // 2
        for image in images:
            screen.blit(image, (x, y)); x += image.get_width()

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        overlay = self.overlays[0][1] if self.overlays and self.overlays[0][0] == "running" else None
        if isinstance(overlay, Video):
            overlay.draw(screen)
            return
        screen.fill(BLACK)
        # Zoom de caméra : le décor est toujours dessiné au zoom du décor (images déjà en cache : pas de saccade), puis
        # l'image est agrandie (zoom avant, bop) ou dessinée sur une toile plus grande puis réduite (zoom arrière).
        factor = self.camera_zoom * self.cam_bop
        cam = self.cam
        if self.shake:
            start, power, length = self.shake
            power *= 1 - (now - start) / length
            if power <= 0:
                self.shake = None
            else:
                spread = power / self.view_zoom
                cam = (cam[0] + random.uniform(-spread, spread), cam[1] + random.uniform(-spread, spread))
        if factor < .998:
            size = (math.ceil(WIDTH / factor), math.ceil(HEIGHT / factor))
            if self._canvas is None or self._canvas.get_width() < size[0] or self._canvas.get_height() < size[1]:
                self._canvas = pygame.Surface(size)
            canvas = self._canvas.subsurface((0, 0, *size))
            canvas.fill(BLACK)
            self.stage.draw(canvas, cam, now)
            screen.blit(pygame.transform.smoothscale(canvas, screen.get_size()), (0, 0))
        else:
            self.stage.draw(screen, cam, now)
            self._zoom_layer(screen, factor)
        self.scripts.call("on_draw_stage", self, screen)
        if self.flash:
            start, length, color = self.flash
            alpha = round(255 * (1 - (now - start) / length))
            if alpha <= 0:
                self.flash = None
            else:
                veil = pygame.Surface(screen.get_size()); veil.fill(color); veil.set_alpha(alpha)
                screen.blit(veil, (0, 0))
        if overlay:
            overlay.draw(screen)
            return
        if self.hud_visible:
            hud = screen
            if self.hud_zoom > 1.003:  # en dessous : moins de 2 pixels au bord de l'écran, pas la peine d'agrandir
                if getattr(self, "_hud_layer", None) is None:
                    self._hud_layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
                hud = self._hud_layer
                hud.fill((0, 0, 0, 0))
            self._draw_notes(hud)
            self._draw_hold_covers(hud, self.receptor_y + self.ARROW_SIZE // 2)
            self._draw_splashes(hud, self.receptor_y + self.ARROW_SIZE // 2)
            self._draw_hud(hud)
            if hud is not screen:
                self._zoom_layer(hud, self.hud_zoom, smooth=False)  # bop de 3 % au plus : agrandissement simple, 3x plus rapide
                screen.blit(hud, (0, 0))
            self._draw_hud_texts(screen)
        if self.countdown_image and now - self.countdown_at < 600:
            image = self.countdown_image.copy()
            image.set_alpha(max(0, 255 - round((now - self.countdown_at) / 600 * 255)))
            screen.blit(image, image.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
        self.scripts.call("on_draw", self, screen)
        self._draw_subtitles(screen)
        self._draw_messages(screen)

    @staticmethod
    def _zoom_layer(surface: pygame.Surface, factor: float, smooth: bool = True) -> None:
        """Agrandit l'image autour du centre de l'écran (zoom de caméra et bop)."""
        if factor <= 1.002:
            return
        width, height = surface.get_size()
        crop = pygame.Rect(0, 0, round(width / factor), round(height / factor))
        crop.center = (width // 2, height // 2)
        scaled = (pygame.transform.smoothscale if smooth else pygame.transform.scale)(surface.subsurface(crop), (width, height))
        if surface.get_flags() & pygame.SRCALPHA:
            surface.fill((0, 0, 0, 0))
        surface.blit(scaled, (0, 0))

    def _draw_hud_texts(self, screen: pygame.Surface) -> None:
        self.app.text(screen, f"{self.song.name}  [{self.chart_key.upper()}]", (16, 14 if self.downscroll else HEIGHT - 34), 19, outline=True, raw=True)
        tr = self.app.tr
        info = [f"{tr('JUDGMENT')} : {tr('EASY' if self.judgment == 'easy' else 'NORMAL')}"]
        if abs(self.rate - 1) > .001:
            info.insert(0, f"{tr('SONG SPEED')} x{self.rate:g}")
        if self.opponent_mode:
            info.insert(0, tr("OPPONENT MODE"))
        if self.practice:
            info.insert(0, tr("PRACTICE MODE"))
        if self.botplay:
            info.insert(0, "BOTPLAY")
        for index, line in enumerate(reversed(info)):  # une ligne par réglage, empilées au-dessus du jugement
            y = 14 + index * 24 if self.downscroll else HEIGHT - 34 - index * 24
            self.app.text(screen, line, (WIDTH - 16, y), 19, outline=True, right=True, raw=True)

    def _draw_messages(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        messages = [text for at, text in self.scripts.errors if time.monotonic() - at < 8] + (self.warnings if self.song_time < self.start_ms + 4000 else [])
        for index, text in enumerate(messages[-4:]):
            self.app.text(screen, text[:110], (16, 170 + index * 26), 18, color=RED, outline=True, raw=True)
        if self.botplay and self.hud_visible:
            label = self.app.alphabet("BOTPLAY", 64).copy()
            label.set_alpha(round(150 + 105 * math.sin(now / 450)))
            screen.blit(label, label.get_rect(center=(WIDTH // 2, HEIGHT - 190 if self.downscroll else 190)))
        if self.paused and self.pause_menu:
            self.pause_menu.draw(screen)


class WeekResult:
    """Totaux d'une semaine du mode histoire, avec ce que l'écran de résultats lit d'une partie."""
    is_week = True

    def __init__(self, play: PlayState, stats: dict, week):
        self.app, self.player, self.difficulty, self.chart_key = play.app, play.player, play.difficulty, play.chart_key
        self.audio_sounds, self.start_ms = [], 0.0
        self.song = type("WeekSong", (), {"song_id": f"week:{week.week_id}", "name": week.name.title()})()
        self.notes = [PlayNote(0.0, 0, True, 0.0)] * stats.get("total", 0)  # l'écran de résultats ne fait que les compter
        for name in ("sick", "good", "bad", "shit", "misses", "score", "weighted", "judged", "max_combo"):
            setattr(self, name, stats.get(name, 0))

    def accuracy(self) -> float:
        return self.weighted / self.judged * 100 if self.judged else 100


class PauseMenu:
    """Menu pause façon FNF : l'écran s'assombrit, musique Breakfast, infos de la chanson en haut à droite,
    choix en police alphabet qui défilent en diagonale, sous-menu pour changer de difficulté."""

    def __init__(self, play: "PlayState"):
        self.play, self.app = play, play.app
        self.opened_at = pygame.time.get_ticks()
        self.mode = "main"
        self.selected = 0
        self.scroll = 0.0
        self.items = self._main_items()
        name = "breakfast-pixel" if play.pixel else "breakfast-pico" if "pico" in play.player.id else "breakfast"
        for relative in (f"shared/music/{name}/{name}.ogg", f"week6/music/{name}/{name}.ogg", "shared/music/breakfast/breakfast.ogg"):
            path = self.app.assets.path(relative)
            if path.is_file():
                try:
                    pygame.mixer.music.load(path); pygame.mixer.music.set_volume(0); pygame.mixer.music.play(-1)
                except pygame.error:
                    pass
                break

    def _charts(self) -> list[str]:
        variation = self.play.chart_key.partition(":")[2]
        return [key for key in sorted(self.play.song.charts, key=difficulty_sort_key) if key.partition(":")[2] == variation]

    def _main_items(self) -> list[tuple[str, str]]:
        items = [("resume", "RESUME"), ("restart", "RESTART SONG")]
        if len(self._charts()) > 1:
            items.append(("difficulty", "CHANGE DIFFICULTY"))
        items.append(("practice", "DISABLE PRACTICE MODE" if self.play.practice else "ENABLE PRACTICE MODE"))
        items += [("editor", "CHART EDITOR"), ("exit", "EXIT TO MENU")]
        return items

    def _open(self, mode: str) -> None:
        self.mode = mode
        self.items = self._main_items() if mode == "main" else [(f"chart:{key}", key.partition(":")[0].upper()) for key in self._charts()] + [("back", "BACK")]
        self.selected = 0
        self.scroll = 0.0

    def close(self) -> None:
        pygame.mixer.music.stop()

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + (-1 if event.key in (pygame.K_UP, pygame.K_w) else 1)) % len(self.items)
            self.app.scroll_sound()
        elif event.key == pygame.K_ESCAPE:
            if self.mode == "main":
                self.play.toggle_pause()
            else:
                self._open("main")
        elif event.key == pygame.K_7:
            self.close(); self.play.open_chart_editor()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            self._activate(self.items[self.selected][0])

    def _activate(self, action: str) -> None:
        play = self.play
        if action == "resume":
            play.toggle_pause()
        elif action == "restart":
            self.close(); play.restart_song()
        elif action == "difficulty":
            self._open("difficulty"); self.app.scroll_sound()
        elif action == "back":
            self._open("main")
        elif action == "practice":
            play.practice = not play.practice
            self.items = self._main_items()
            self.app.confirm_sound()
        elif action == "editor":
            self.close(); play.open_chart_editor()
        elif action == "exit":
            self.close(); play.exit_to_menu()
        elif action.startswith("chart:"):
            key = action.partition(":")[2]
            self.close(); play.stop_audio()
            self.app.playlist_difficulty = key
            self.app.change(PlayState(self.app, play.song.song_id, key, play.audio_sounds, play.start_ms, intro=False))

    def update(self, dt: float) -> None:
        self.scroll = lerp(self.scroll, self.selected, dt, 12)
        age = (pygame.time.get_ticks() - self.opened_at) / 1000
        pygame.mixer.music.set_volume(min(.5, age / 20) * self.app.volume)  # monte doucement, comme FNF

    def draw(self, screen: pygame.Surface) -> None:
        age = pygame.time.get_ticks() - self.opened_at
        screen.blit(self.app.shade(round(min(1.0, age / 400) * 165)), (0, 0))
        tr = self.app.tr
        play = self.play
        info = [play.song.name, play.chart_key.partition(":")[0].upper(), f"{tr('BLUE BALLED')}: {self.app.deaths}"]
        if play.practice:
            info.append(tr("PRACTICE MODE"))
        for index, line in enumerate(info):
            appear = ease_out((age - 300 - index * 100) / 400)
            if appear <= 0:
                continue
            font = self.app.font(30, True)
            text = font.render(line, True, WHITE)
            text.set_alpha(round(255 * appear))
            shadow = font.render(line, True, BLACK)
            shadow.set_alpha(round(255 * appear))
            x, y = WIDTH - 20 - text.get_width(), round(15 + index * 40 - 5 * (1 - appear))
            screen.blit(shadow, (x + 3, y + 3)); screen.blit(text, (x, y))
        for index, (_, label) in enumerate(self.items):
            offset = index - self.scroll
            y = HEIGHT * .48 + offset * 120
            if y < -100 or y > HEIGHT + 100:
                continue
            text = self.app.alphabet(tr(label), 74).copy()
            text.set_alpha(255 if index == self.selected else 150)
            screen.blit(text, text.get_rect(midleft=(round(90 + offset * 20), round(y))))


class GameOverState(BaseState):
    """Écran de mort façon FNF : animation de mort du joueur, musique en boucle, Entrée pour réessayer."""

    def __init__(self, app: "FunkinApp", play: PlayState):
        super().__init__(app)
        self.play = play
        self.player = play.player
        self.started = pygame.time.get_ticks()
        self.confirmed_at = 0
        player_id = play.player.id
        self.suffix = ("-pixel" if "pixel" in player_id else "") + ("-pico" if "pico" in player_id else "")
        self.has_death = self.player.has("firstDeath")
        if self.has_death:
            self.player.play("firstDeath", self.started, force=True)
        self.looping = False
        play.focus_camera(0)
        if self.has_death:
            # La caméra centre exactement la pose de mort qui boucle (celle qui reste à l'écran).
            pose = "deathLoop" if self.player.has("deathLoop") else "firstDeath"
            x, y, width, height = self.player.world_rect(self.started, play.stage.zoom, pose, 0)
            play.cam_target = [x + width / 2, y + height / 2]
        # data/characters/<id>.json : "death": {"sfx": ..., "music": ..., "musicEnd": ...} (chemins d'assets) pour un mod.
        death = self.player.config.get("death") if isinstance(getattr(self.player, "config", None), dict) else None
        self.custom = {key: str(death[key]) for key in ("sfx", "music", "musicEnd") if isinstance(death, dict) and death.get(key)}
        self.app.play_sound(self.custom.get("sfx", f"shared/sounds/gameplay/gameover/fnf_loss_sfx{self.suffix}.ogg"))

    def _music(self, name: str, loops: int) -> None:
        custom = self.custom.get("music" if name == "gameOver" else "musicEnd")
        path = self.app.assets.path(custom or f"shared/music/gameplay/gameover/{name}{self.suffix}.ogg")
        if not path.is_file():
            path = self.app.assets.path(f"shared/music/gameplay/gameover/{name}.ogg")
        try:
            pygame.mixer.music.load(path); pygame.mixer.music.set_volume(self.app.volume); pygame.mixer.music.play(loops)
        except pygame.error:
            pass

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN or self.confirmed_at:
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.confirmed_at = pygame.time.get_ticks()
            self.player.play("deathConfirm", self.confirmed_at, force=True)
            self._music("gameOverEnd", 0)
        elif event.key == pygame.K_ESCAPE:
            pygame.mixer.music.stop()
            self.app.back_to_menu()

    def update(self, dt: float) -> None:
        now = pygame.time.get_ticks()
        if not self.looping and not self.confirmed_at and (now - self.started > 2600 or (self.has_death and self.player.finished(now))):
            self.looping = True
            self.player.play("deathLoop", now, force=True)
            self._music("gameOver", -1)
        if self.confirmed_at and now - self.confirmed_at > 2200:
            pygame.mixer.music.stop()
            self.app.change(PlayState(self.app, self.play.song.song_id, self.play.chart_key, self.play.audio_sounds, self.play.start_ms, intro=False))
        follow = 1 - (1 - .04) ** (dt * 60)
        self.play.cam[0] += (self.play.cam_target[0] - self.play.cam[0]) * follow
        self.play.cam[1] += (self.play.cam_target[1] - self.play.cam[1]) * follow

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        screen.fill(BLACK)
        if self.has_death:
            self.player.draw(screen, self.play.cam, self.play.stage.zoom, now)
        else:
            title = self.app.alphabet(self.app.tr("GAME OVER"), 100)
            screen.blit(title, title.get_rect(center=(WIDTH // 2, 300)))
        if self.looping and not self.confirmed_at:
            key_hints(self.app, screen, "ENTER RETRY     ESC MENU", HEIGHT - 30)
        if self.confirmed_at:
            screen.blit(shade(min(255, round(max(0, now - self.confirmed_at - 1000) / 1200 * 255))), (0, 0))


class ResultsState(BaseState):
    """Écran de résultats façon FNF (V-Slice) avec ses vrais assets : bannière RESULTS, enceinte, compteurs,
    score digital, pourcentage CLEAR qui monte, puis révélation du rang (musique + animation de BF ou Pico)."""

    FOLDER = "shared/images/resultScreen"
    REVEAL = 3000  # ms : fin du comptage, le rang apparaît
    CONFIG_KEYS = {"PERFECT_GOLD": "perfectGold", "PERFECT": "perfect", "EXCELLENT": "excellent",
                   "GREAT": "great", "GOOD": "good", "SHIT": "loss"}
    SCRIPT_ASSETS = {"BFBedPerfectResults": "shared:resultScreen/results-bf/resultsPERFECT/bed",
                     "BFShitResults": "shared:resultScreen/results-bf/resultsSHIT",
                     "PicoPerfectResults": "shared:resultScreen/results-pico/resultsPERFECT",
                     "PicoGreatResults": "shared:resultScreen/results-pico/resultsGREAT",
                     "PicoGoodResults": "shared:resultScreen/results-pico/resultsGOOD"}
    # Le script officiel BFBedPerfectResults place le lit autrement que les offsets du JSON : décalage mesuré à l'écran.
    EXTRA_OFFSETS = {"shared:resultScreen/results-bf/resultsPERFECT/bed": (560, 0)}
    TALLY_COLORS = {"sick": (137, 229, 158), "good": (137, 201, 229), "bad": (230, 207, 138),
                    "shit": (230, 140, 138), "missed": (198, 138, 230)}

    def __init__(self, app: "FunkinApp", play: PlayState, failed: bool):
        super().__init__(app)
        self.play, self.failed = play, failed
        total = sum(1 for note in play.notes if note.player and note.state != "skip" and not note.avoid)
        hits = play.sick + play.good + play.bad + play.shit
        completion = play.accuracy() / 100 if total else 0.0
        self.clear = min(100, int(completion * 100))
        if failed:
            self.rank = "SHIT"
        elif completion >= 1 and play.sick >= total:
            self.rank = "PERFECT_GOLD"
        else:
            self.rank = ("PERFECT" if completion >= 1 else "EXCELLENT" if completion >= .9 else "GREAT" if completion >= .8
                         else "GOOD" if completion >= .6 else "SHIT")
        self.grade = self.rank  # compatibilité avec les scripts qui lisaient la lettre
        self.best = app.settings.scores.get(f"{play.song.song_id}|{play.chart_key}", 0)
        self.new_record = not failed and play.score >= self.best and play.score > 0
        self.tallies = [("total", hits, 375, 150), ("combo", play.max_combo, 375, 200), ("sick", play.sick, 230, 257),
                        ("good", play.good, 210, 307), ("bad", play.bad, 190, 357), ("shit", play.shit, 220, 407),
                        ("missed", play.misses, 260, 457)]
        self.opened_at = pygame.time.get_ticks()
        self.revealed = False
        self.layers = self._character_layers()
        self._frame_cache: dict = {}
        pygame.mixer.music.stop()

    # ----- données
    def _sprites(self, name: str, prefix: str = "") -> list[pygame.Surface]:
        return menus.frames(self.app, f"{self.FOLDER}/{name}.png", prefix)

    def _image(self, name: str) -> pygame.Surface | None:
        return menus.image(self.app, f"{self.FOLDER}/{name}.png")

    def _character_layers(self) -> list[dict]:
        """Animations du personnage pour le rang, lues dans data/players/<bf|pico>.json comme le jeu officiel."""
        kind = "pico" if "pico" in self.play.player.id else "bf"
        path = self.app.assets.path(f"data/players/{kind}.json")
        try:
            results = self.app.assets.json(path).get("results", {}) if path.is_file() else {}
        except ValueError:
            results = {}
        self.music = (results.get("music") or {}).get(self.rank, "")
        layers = []
        child = self.app.settings.child_mode
        for entry in results.get(self.CONFIG_KEYS[self.rank], []):
            if entry.get("filter") == ("naughty" if child else "safe"):
                continue
            asset = entry.get("assetPath") or self.SCRIPT_ASSETS.get(str(entry.get("scriptClass")), "")
            try:
                atlas = self.app.assets.atlas(str(asset)) if asset else None
            except (OSError, ValueError, KeyError, pygame.error):
                atlas = None
            if atlas is None:
                continue
            extra = self.EXTRA_OFFSETS.get(str(asset), (0, 0))
            offsets = [float((entry.get("offsets") or [0, 0])[0]) + extra[0], float((entry.get("offsets") or [0, 0])[1]) + extra[1]]
            layer = {"atlas": atlas, "offsets": offsets, "scale": float(entry.get("scale", 1) or 1),
                     "delay": float(entry.get("delay", 0) or 0) * 1000, "z": int(entry.get("zIndex", 500))}
            if isinstance(atlas, SparrowAtlas):
                layer["frames"] = atlas.animation("")
                layer["start"], layer["end"] = 0, len(layer["frames"])
                layer["loop"] = int(entry.get("loopFrame", 0) or 0)
            else:
                labels = sorted(atlas.labels.items(), key=lambda item: item[1][0])
                length = atlas._timeline_length(atlas.animation.get("TL", {}))
                start_label, loop_label = str(entry.get("startFrameLabel", "")).lower(), str(entry.get("loopFrameLabel", "")).lower()
                start = atlas.labels[start_label][0] if start_label in atlas.labels else 0
                loop = atlas.labels[loop_label][0] if loop_label in atlas.labels else start + int(entry.get("loopFrame", 0) or 0)
                end = next((first for name, (first, _) in labels if first > loop), length)
                # La position donnée est celle du coin de la première image ; si elle est vide (Pico entre en scène après
                # quelques images), on prend le coin du cadre de toute l'animation, comme flixel-animate dans le jeu.
                first, anchor = atlas.frame_at(0)
                if first.get_width() <= 2 and first.get_height() <= 2:
                    anchor = atlas.whole_bounds()[:2]
                layer.update(start=start, loop=loop, end=max(loop + 1, end), anchor=anchor)
            layers.append(layer)
        return sorted(layers, key=lambda layer: layer["z"])

    def _play_music(self) -> None:
        if not self.music:
            return
        intro = self.app.assets.path(f"shared/music/{self.music}/{self.music}-intro.ogg")
        loop = self.app.assets.path(f"shared/music/{self.music}/{self.music}.ogg")
        try:
            if intro.is_file():
                pygame.mixer.music.load(intro); pygame.mixer.music.set_volume(self.app.volume); pygame.mixer.music.play()
                if loop.is_file():
                    pygame.mixer.music.queue(loop, loops=-1)
            elif loop.is_file():
                pygame.mixer.music.load(loop); pygame.mixer.music.set_volume(self.app.volume); pygame.mixer.music.play(-1)
        except (pygame.error, TypeError):
            pass

    # ----- entrées
    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN or pygame.time.get_ticks() - self.opened_at < 500:
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            pygame.mixer.music.stop()
            if not self.failed and self.app.advance_playlist(): return
            self.app.back_to_menu()
        elif event.key == pygame.K_r:
            pygame.mixer.music.stop()
            if getattr(self.play, "is_week", False):  # rejouer toute la semaine
                self.app.start_playlist(list(self.app.playlist), self.app.playlist_difficulty, self.app.story_week)
                return
            self.app.change(PlayState(self.app, self.play.song.song_id, self.play.chart_key, self.play.audio_sounds, intro=False))
        elif event.key == pygame.K_ESCAPE:
            pygame.mixer.music.stop()
            self.app.back_to_menu()

    def update(self, dt: float) -> None:
        age = pygame.time.get_ticks() - self.opened_at
        if not self.revealed and age >= self.REVEAL:
            self.revealed = True
            self._play_music()
            self.app.play_sound("sounds/confirmMenu.ogg", .6)

    # ----- dessin
    def _layer_frame(self, layer: dict, age_ms: float) -> tuple[pygame.Surface, float, float] | None:
        if age_ms < 0:
            return None
        index = int(age_ms * 24 / 1000) + layer["start"]
        if index >= layer["end"]:
            span = max(1, layer["end"] - layer["loop"])
            index = layer["loop"] + (index - layer["end"]) % span
        key = (id(layer), index)
        if key in self._frame_cache:
            return self._frame_cache[key]
        if "frames" in layer:
            surface, origin = layer["frames"][index % len(layer["frames"])], (0, 0)
        else:
            surface, (ox, oy) = layer["atlas"].frame_at(index)
            origin = (ox - layer["anchor"][0], oy - layer["anchor"][1])
        scale = layer["scale"]
        if scale != 1:
            surface = scale_by(surface, scale)
        result = (surface, layer["offsets"][0] + origin[0] * scale, layer["offsets"][1] + origin[1] * scale)
        if len(self._frame_cache) < 400:
            self._frame_cache[key] = result
        return result

    def _anim(self, screen: pygame.Surface, name: str, prefix: str, position: tuple[int, int], age_ms: float, alpha: int = 255) -> None:
        sprites = self._sprites(name, prefix)
        if not sprites or age_ms < 0:
            return
        frame = sprites[min(len(sprites) - 1, int(age_ms * 24 / 1000))]
        if alpha < 255:
            frame = frame.copy(); frame.set_alpha(alpha)
        screen.blit(frame, position)

    def _digits(self, screen: pygame.Surface, sheet: str, value: int, x: int, y: int, names, color=None, gap: int = 0,
                width: int = 0) -> int:
        text = str(max(0, value))
        if width:
            text = text.rjust(width, " ")
        for char in text:
            prefix = names(char)
            sprites = self._sprites(sheet, prefix) if prefix else []
            if sprites:
                sprite = sprites[0]
                if color:
                    sprite = tint(sprite, color)
                screen.blit(sprite, (x, y))
                x += sprite.get_width() + gap
        return x

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        age = now - self.opened_at
        reveal = age - self.REVEAL
        # Fond jaune dégradé (plus clair au flash de la révélation).
        if "results-bg" not in self.app.cache:
            bg = pygame.Surface((WIDTH, HEIGHT))
            for y in range(HEIGHT):
                mix = y / HEIGHT
                pygame.draw.line(bg, (254, round(204 - 18 * mix), round(92 - 22 * mix)), (0, y), (WIDTH, y))
            self.app.cache["results-bg"] = bg
        screen.blit(self.app.cache["results-bg"], (0, 0))
        # Texte du rang qui défile en diagonale derrière tout le reste.
        if reveal >= 0:
            scroll = self._image(f"rankText/rankScroll{self.rank.replace('_GOLD', '')}")
            if scroll:
                key = ("rank-scroll", self.rank)
                if key not in self.app.cache:
                    faded = scroll.copy(); faded.set_alpha(110)
                    self.app.cache[key] = faded
                faded = self.app.cache[key]
                layer = pygame.Surface((WIDTH + 400, HEIGHT + 300), pygame.SRCALPHA)
                for row in range(9):
                    step = faded.get_width() + 30
                    offset = (reveal * (.05 if row % 2 else -.05)) % step
                    x = -step + offset
                    while x < layer.get_width():
                        layer.blit(faded, (x, 60 + row * 85)); x += step
                rotated = pygame.transform.rotate(layer, 3.8)
                screen.blit(rotated, rotated.get_rect(center=(WIDTH // 2 + 200, HEIGHT // 2)))
        self._anim(screen, "soundSystem", "sound system", (-15, -180), age - 250)
        if reveal >= 0:
            for layer in self.layers:
                frame = self._layer_frame(layer, reveal - layer["delay"])
                if frame:
                    surface, x, y = frame
                    screen.blit(surface, (round(x), round(y)))
        # Barre noire, bannière RESULTS, difficulté et nom de la chanson.
        bar = self._image("topBarBlack")
        if bar:
            screen.blit(bar, (0, round(-bar.get_height() * (1 - ease_out(age / 400)))))
        self._anim(screen, "results", "results instance", (-200, -10), age)
        difficulty = self._image(f"diff_{self.play.difficulty}")
        if difficulty and age > 300:
            slide = ease_out((age - 300) / 400)
            screen.blit(difficulty, (555, round(87 - 60 * (1 - slide))))
            name_x = 555 + difficulty.get_width() + 24
        else:
            name_x = 580
        if age > 400:
            font = self.app.font(38, True)
            label = font.render(self.play.song.name, True, WHITE)
            shadow = font.render(self.play.song.name, True, BLACK)
            for image, (dx, dy) in ((shadow, (3, 3)), (label, (0, 0))):
                rotated = pygame.transform.rotate(image, 4.4)
                screen.blit(rotated, (name_x + dx, 72 + dy))
        # Catégories, compteurs (qui montent), score.
        self._anim(screen, "ratingsPopin", "Categories", (-135, 135), age - 400)
        for index, (name, value, x, y) in enumerate(self.tallies):
            start = 600 + index * 120
            if age < start:
                continue
            shown = round(value * min(1.0, (age - start) / 700))
            self._digits(screen, "tallieNumber", shown, x, y, lambda char: f"{char} small" if char.isdigit() else "",
                         self.TALLY_COLORS.get(name), gap=-2)
        self._anim(screen, "scorePopin", "tally score", (-180, 515), age - 600)
        if age > 900:
            score = round(self.play.score * min(1.0, (age - 900) / 1200))
            names = ("ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE")
            self._digits(screen, "score-digital-numbers", score, 70, 600,
                         lambda char: f"{names[int(char)]} DIGITAL" if char.isdigit() else "DISABLED", gap=-14, width=10)
        # Pourcentage CLEAR : compte jusqu'à la révélation, puis petit à côté du personnage.
        if 1300 < age < self.REVEAL + 250:
            value = round(self.clear * min(1.0, (age - 1300) / (self.REVEAL - 1500)))
            x = self._digits(screen, "clearPercent/clearPercentNumberRight", value, 830, 290,
                             lambda char: f"number {char} " if char.isdigit() else "", gap=-6)
            text = self._image("clearPercent/clearPercentText")
            if text:
                screen.blit(text, (x + 8, 260))
        elif reveal >= 0:
            x = self._digits(screen, "clearPercent/clearPercentNumberSmall", self.clear, 1050, 150,
                             lambda char: f"number {char} " if char.isdigit() else "", gap=-2)
            text = self._image("clearPercent/clearPercentTextSmall")
            if text:
                screen.blit(text, (x + 4, 154))
        if reveal >= 0:
            # Texte vertical du rang qui défile à droite.
            vertical = self._image(f"rankText/rankText{self.rank.replace('_GOLD', '')}")
            if vertical:
                step = vertical.get_height() + 30
                y = -((reveal * .08) % step)
                while y < HEIGHT:
                    screen.blit(vertical, (WIDTH - 52, round(y))); y += step
            if self.new_record:
                self._anim(screen, "highscoreNew", "highscoreAnim", (44, 557), reveal)
            if reveal < 260:  # flash blanc de la révélation
                screen.blit(shade(round(255 * (1 - reveal / 260)), WHITE), (0, 0))
            if reveal > 600:
                key_hints(self.app, screen, "ENTER CONTINUE     R RETRY     ESC MENU", HEIGHT - 26, anchor="right", x=WIDTH - 70, bar=False, size=14)


class FunkinApp:
    def __init__(self, root: Path):
        pygame.mixer.pre_init(44100, -16, 2, 1024)
        pygame.init()
        pygame.mixer.set_num_channels(16)
        pygame.mixer.set_reserved(7)
        self.settings = Settings.load()
        self.apply_display_quality()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE | pygame.SCALED)
        pygame.display.set_caption("Friday Night Funkin' — Python Engine")
        self.is_fullscreen = False
        self._crisp: list = []  # textes de l'image en cours, redessinés nets en qualité HAUTE (voir present)
        self._hd = None
        if self.settings.fullscreen:
            self.set_fullscreen(True)
        self.clock = pygame.time.Clock()
        self.base_root = root
        self.volume = self.settings.volume
        self._fonts: dict[tuple[int, bool], pygame.font.Font] = {}
        self._shades: dict[int, pygame.Surface] = {}
        self.cache: dict = {}
        self.toasts: list[tuple[Achievement, int]] = []
        self.modifiers: dict = {}  # menu Ctrl du freeplay : scroll, rate, opponent, judgment, practice, botplay
        self.freeplay_character = "bf"  # Tab dans le freeplay : "bf" ou "pico"
        self.tray_at = -10 ** 9  # dernière action sur le volume (+ / - / 0)
        self.gamepads = Gamepads(self.settings)  # manettes : boutons traduits en touches du clavier
        self.update_info = None  # annonce « mise à jour disponible » (vérifiée sur GitHub en arrière-plan)
        from .news import check_update
        check_update(self, VERSION)
        self.volume_before_mute = .5
        self.playlist: list[str] = []
        self.playlist_index = 0
        self.playlist_difficulty = "normal"
        self.deaths = 0  # morts depuis le lancement de la chanson (« Blue balled » du menu pause)
        self.loading = False  # True pendant le chargement d'une chanson : PlayState affiche sa progression
        self.week_stats: dict = {}  # totaux de la semaine en cours (mode histoire)
        self.story_week: int | None = None
        self.week_misses = 0
        self.editor_return: BaseState | None = None
        self.music_started_at = pygame.time.get_ticks()
        self.reload_mods()
        self.state: BaseState = menus.TitleState(self)
        self.running = True

    # ---------- mods ----------
    def reload_mods(self) -> None:
        editor_saves_dir()  # déplace l'ancien mod « Editor Saves » hors de mods/ avant de lister les mods
        self.mods = discover(self.settings.disabled_mods)
        roots = [mod.root for mod in self.mods if mod.enabled]
        # Enregistrements des éditeurs : partie du jeu par défaut (pas un mod), prioritaires sur tout le reste.
        self.assets = Assets(self.base_root, [editor_saves_dir(), *roots])
        try:  # curseur officiel du jeu (images/cursor/cursor-default.png), remplaçable par un mod
            pygame.mouse.set_cursor(pygame.cursors.Cursor((0, 0), pygame.image.load(str(self.assets.path("images/cursor/cursor-default.png")))))
        except (pygame.error, FileNotFoundError):
            pass
        names = {mod.root: mod.name for mod in self.mods}
        self.data = FunkinData([editor_saves_dir(), *roots, self.base_root], names)
        self.achievements = load_achievements(roots, names)
        self.cache = {}
        self._alphabet_atlas: SparrowAtlas | None = None

    def script_paths(self, song_id: str) -> list[Path]:
        """Scripts du jeu de base puis des mods actifs : scripts/*.py et data/songs/<id>/*.py."""
        paths: list[Path] = []
        for root in reversed(self.assets.roots):
            paths += sorted((root / "scripts").glob("*.py"))
            paths += sorted((root / "data" / "songs" / song_id).glob("*.py"))
        return paths

    # ---------- succès ----------
    def unlock(self, achievement_id: str) -> None:
        if achievement_id in self.settings.achievements or self.editor_return:
            return
        item = next((entry for entry in self.achievements if entry.id == achievement_id), None)
        if item is None:
            return
        self.settings.achievements.append(achievement_id)
        self.settings.save()
        self.toasts.append((item, pygame.time.get_ticks()))
        self.play_sound("sounds/confirmMenu.ogg", .6)

    def achievement_name(self, item: Achievement) -> str:
        return item.name_fr if self.settings.language == "fr" and item.name_fr else item.name

    def achievement_description(self, item: Achievement) -> str:
        return item.description_fr if self.settings.language == "fr" and item.description_fr else item.description

    def achievement_icon(self, item: Achievement, size: int) -> pygame.Surface | None:
        key = ("ach-icon", item.id, size)
        if key not in self.cache:
            icon = None
            if "/" in item.icon or item.icon.endswith(".png"):
                path = self.assets.path(item.icon)
                if path.is_file():
                    icon = pygame.transform.smoothscale(self.assets.image(path), (size, size))
            else:
                frames = self.icon_frames(item.icon or "face")
                icon = pygame.transform.smoothscale(frames[0], (size, size)) if frames else None
            self.cache[key] = icon
        return self.cache[key]

    def draw_toasts(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        self.toasts = [(item, at) for item, at in self.toasts if now - at < 3600]
        for index, (item, at) in enumerate(self.toasts[:3]):
            age = now - at
            slide = min(1.0, age / 250, (3600 - age) / 250)
            box = pygame.Rect(0, 0, 440, 96)
            box.topleft = (20 - round((1 - slide) * 470), (44 if self.settings.show_fps else 20) + index * 106)
            panel = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.rect(panel, (12, 10, 24, 230), panel.get_rect(), border_radius=16)
            pygame.draw.rect(panel, (255, 210, 80, 255), panel.get_rect(), 3, border_radius=16)
            screen.blit(panel, box.topleft)
            icon = self.achievement_icon(item, 72)
            if icon:
                screen.blit(icon, (box.x + 12, box.y + 12))
            label = "SUCCÈS DÉBLOQUÉ" if self.settings.language == "fr" else "ACHIEVEMENT UNLOCKED"
            self.text(screen, label, (box.x + 96, box.y + 16), 18, color=(255, 210, 80), bold=True, raw=True)
            self.text(screen, self.achievement_name(item), (box.x + 96, box.y + 44), 26, bold=True, raw=True)

    def apply_display_quality(self, reopen: bool = False) -> None:
        """HAUTE : l'image 1280 x 720 est agrandie en douceur (filtre linéaire) ; PIXELS : agrandissement net, au plus proche."""
        import os
        os.environ["SDL_RENDER_SCALE_QUALITY"] = "1" if self.settings.quality == "high" else "0"
        self._hd = None
        if not reopen:
            return
        # Recréer la fenêtre peut échouer (« failed to create renderer ») : on réessaie en relançant l'affichage,
        # et en dernier recours on garde l'image actuelle (le réglage s'appliquera au prochain lancement), jamais de crash.
        fullscreen = self.is_fullscreen
        for attempt in range(2):
            try:
                if attempt:
                    pygame.display.quit(); pygame.display.init()
                    pygame.display.set_caption("Friday Night Funkin' — Python Engine")
                self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE | pygame.SCALED)
                self.is_fullscreen = False
                if fullscreen:
                    self.set_fullscreen(True)
                return
            except pygame.error:
                continue
        self.screen = pygame.display.get_surface() or pygame.display.set_mode((WIDTH, HEIGHT))

    def set_fullscreen(self, on: bool) -> None:
        """Plein écran (F11, ou Options) : l'image 1280 x 720 est agrandie à tout l'écran, bandes noires si besoin."""
        self.settings.fullscreen = on
        if on == self.is_fullscreen:
            return
        try:
            self._hd = None
            pygame.display.toggle_fullscreen()
            self.is_fullscreen = on
        except pygame.error:
            self.settings.fullscreen = self.is_fullscreen

    # ---------- volume (+ / - / 0, comme le soundtray de FNF) ----------
    def volume_key(self, event: pygame.event.Event) -> bool:
        """Touches globales du volume. Ignorées quand l'écran attend du texte (state.text_input)."""
        if getattr(self.state, "text_input", False) or getattr(self.state, "prompt", None):
            return False
        char = getattr(event, "unicode", "")
        if event.key in (pygame.K_KP_PLUS, pygame.K_PLUS, pygame.K_EQUALS) or char == "+":
            step = 1
        elif event.key in (pygame.K_KP_MINUS, pygame.K_MINUS) or char == "-":
            step = -1
        elif event.key in (pygame.K_KP0, pygame.K_0) or char == "0":
            step = 0
        else:
            return False
        level = round(self.volume * 10)
        if step == 0:
            if level:
                self.volume_before_mute, level = self.volume, 0
            else:
                level = max(1, round(self.volume_before_mute * 10))
        else:
            level = max(0, min(10, level + step))
        self.set_volume(level / 10)
        self.tray_at = pygame.time.get_ticks()
        sound = "VolMAX" if level == 10 and step > 0 else "Volup" if step > 0 else "Voldown"
        self.play_sound(f"sounds/soundtray/{sound}.ogg", 1.0 if self.volume else 0)
        return True

    def set_volume(self, volume: float) -> None:
        self.volume = self.settings.volume = round(volume, 2)
        pygame.mixer.music.set_volume(self.volume)
        for index in range(pygame.mixer.get_num_channels()):
            pygame.mixer.Channel(index).set_volume(self.volume)
        self.settings.save()

    def draw_volume_tray(self, screen: pygame.Surface) -> None:
        age = pygame.time.get_ticks() - self.tray_at
        if age > 1600:
            return
        key = ("soundtray",)
        if key not in self.cache:
            def load(name):
                path = self.assets.path(f"images/soundtray/{name}.png")
                return scale_by(self.assets.image(path), .6) if path.is_file() else None
            self.cache[key] = (load("volumebox"), [load(f"bars_{index}") for index in range(1, 11)])
        box, bars = self.cache[key]
        if box is None:
            return
        # Descend en 150 ms, reste affiché, remonte après 1,2 s (comme FNF).
        slide = min(1.0, age / 150, max(0.0, (1600 - age) / 400))
        x, y = WIDTH // 2 - box.get_width() // 2, round(-box.get_height() + slide * (box.get_height() + 8))
        screen.blit(box, (x, y))
        backing = bars[-1]
        if backing:
            faded = backing.copy(); faded.set_alpha(90)
            screen.blit(faded, (x + round(28 * .6), y + round(22 * .6)))
        level = round(self.volume * 10)
        if level and bars[level - 1]:
            screen.blit(bars[level - 1], (x + round(28 * .6), y + round(22 * .6)))

    # ---------- dessin utilitaire ----------
    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._fonts:
            # Arial Black garde un poids proche de FNF sans écraser les petites lettres.
            names = "arial black,arial" if bold else "arial,dejavusans"
            self._fonts[key] = pygame.font.SysFont(names, size, bold=bold)
        return self._fonts[key]

    def shade(self, alpha: int) -> pygame.Surface:
        if alpha not in self._shades:
            self._shades[alpha] = shade(alpha)
        return self._shades[alpha]

    def menu_bg(self, color: tuple[int, int, int]) -> pygame.Surface:
        """Fond désaturé de FNF teinté (options, mods, succès...)."""
        key = ("menu-bg", color)
        if key not in self.cache:
            path = self.assets.path("images/menuDesat.png")
            base = self.assets.image(path) if path.is_file() else pygame.Surface((WIDTH, HEIGHT))
            self.cache[key] = tint(pygame.transform.smoothscale(base, (WIDTH, HEIGHT)), color)
        return self.cache[key]

    def icon_frames(self, icon_id: str, pixel: bool = False) -> list[pygame.Surface]:
        key = ("icon", icon_id)
        if key not in self.cache:
            frames = []
            for name in (icon_id, icon_id.replace("-playable", ""), icon_id.split("-")[0], "face"):
                path = self.assets.path(f"images/icons/icon-{name}.png")
                if path.is_file():
                    image = self.assets.image(path)
                    size = image.get_height()
                    frames = [image.subsurface((x, 0, size, size)).copy() for x in range(0, max(size, image.get_width() - size + 1), size)][:2]
                    break
            self.cache[key] = frames
        return self.cache[key]

    def text(self, screen: pygame.Surface, value: str, position: tuple[int, int], size: int,
             color: tuple[int, int, int] = WHITE, center: bool = False, bold: bool = False,
             outline: bool = False, right: bool = False, raw: bool = False) -> None:
        """raw=True pour un texte venant des données (nom de chanson, de mod...) : jamais traduit."""
        value = str(value) if raw else self.tr(str(value))
        font = self.font(size, bold)
        image = font.render(value, True, color)
        x, y = position
        if center: x -= image.get_width() // 2
        elif right: x -= image.get_width()
        crisp = screen is self.screen and self.settings.quality == "high" and self._hd is not False
        if crisp:
            margin = 3 if outline else 0
            rect = pygame.Rect(x - margin, y - margin, image.get_width() + 2 * margin, image.get_height() + 2 * margin).clip(screen.get_rect())
            before = screen.subsurface(rect).copy() if rect.width and rect.height else None
        if outline:
            shadow = font.render(value, True, BLACK)
            for ox, oy in OUTLINE_8:  # contour tout autour (4 copies seulement = lettres fantômes aux angles)
                screen.blit(shadow, (x + ox, y + oy))
        screen.blit(image, (x, y))
        if crisp and before is not None:
            after = pygame.image.tobytes(screen.subsurface(rect), "RGB")
            self._crisp.append((rect, before, after, (value, position, size, color, bold, outline, center, right)))

    def present(self) -> None:
        """Affiche l'image. En qualité HAUTE, la carte graphique agrandit l'image 1280 x 720 puis les textes sont
        redessinés nets à la taille réelle de l'écran (sauf ceux recouverts depuis, qui gardent leur version 1280 x 720)."""
        crisp, self._crisp = self._crisp, []
        if self.settings.quality != "high" or self._hd is False:
            pygame.display.flip()
            return
        renderer = None
        try:
            if self._hd is None:
                from pygame._sdl2 import video
                renderer = video.Renderer.from_window(video.Window.from_display_module())
                self._hd = (video, renderer, video.Texture(renderer, (WIDTH, HEIGHT), streaming=True), {})
            video, renderer, frame, cache = self._hd
            renderer.logical_size = (0, 0)  # le temps de dessiner : coordonnées en vrais pixels de l'écran
            width, height = renderer.get_viewport().size
            k = min(width / WIDTH, height / HEIGHT)
            left, top = (width - WIDTH * k) / 2, (height - HEIGHT * k) / 2
            valid = [entry for entry in crisp if k > 1.05 and pygame.image.tobytes(self.screen.subsurface(entry[0]), "RGB") == entry[2]]
            source = self.screen
            if valid:  # l'image sans ces textes (rien n'a été dessiné dessus depuis), puis les textes nets par-dessus
                source = self.screen.copy()
                for rect, before, _, _ in reversed(valid):
                    source.blit(before, rect)
            frame.update(source)
            renderer.draw_color = (0, 0, 0, 255)
            renderer.clear()
            renderer.blit(frame, pygame.Rect(round(left), round(top), round(WIDTH * k), round(HEIGHT * k)))
            if len(cache) > 300:
                cache.clear()
            for _, _, _, (value, (x, y), size, color, bold, outline, center, right) in valid:
                key = (value, round(size * k), tuple(color), bold, outline)
                if key not in cache:
                    font = self.font(max(1, round(size * k)), bold)
                    image = font.render(value, True, color)
                    pad = round(3 * k) if outline else 0
                    surface = pygame.Surface((image.get_width() + 2 * pad, image.get_height() + 2 * pad), pygame.SRCALPHA)
                    if outline:  # contour lisse : 16 directions sur un cercle de rayon pad
                        shadow = font.render(value, True, BLACK)
                        for step in range(16):
                            angle = step * math.pi / 8
                            surface.blit(shadow, (pad + round(pad * math.cos(angle)), pad + round(pad * math.sin(angle))))
                    surface.blit(image, (pad, pad))
                    texture = video.Texture.from_surface(renderer, surface)
                    texture.blend_mode = 1  # SDL_BLENDMODE_BLEND
                    cache[key] = (texture, pad, image.get_width())
                texture, pad, text_width = cache[key]
                sx = left + x * k - (text_width / 2 if center else text_width if right else 0) - pad
                renderer.blit(texture, pygame.Rect(round(sx), round(top + y * k - pad), texture.width, texture.height))
            renderer.logical_size = (WIDTH, HEIGHT)
            renderer.present()
        except Exception:  # pilote sans rendu SDL2 utilisable : agrandissement simple, comme en qualité PIXELS
            self._hd = False
            if renderer is not None:
                try:
                    renderer.logical_size = (WIDTH, HEIGHT)
                except Exception:
                    pass
            pygame.display.flip()

    def tr(self, text: str) -> str:
        return translate(text, self.settings.language)

    def alphabet(self, value: str, height: int = 70) -> pygame.Surface:
        """Texte avec la police "alphabet" de FNF (lettres en gras des menus). Les accents sont retirés."""
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        key = ("alphabet", value, height)
        if key in self.cache:
            return self.cache[key]
        if self._alphabet_atlas is None:
            self._alphabet_atlas = SparrowAtlas(self.assets, self.assets.path("images/alphabet.png"))
        symbols = {"-": "-", ".": "period", "!": "exclamation point", "?": "question mark", "'": "apostraphie",
                   ",": "comma", ":": ":", "&": "amp", "%": "%", "+": "+", "/": "forward slash", "(": "start parentheses",
                   ")": "end parentheses", "<": "<", ">": ">", "#": "hashtag "}
        glyphs: list[pygame.Surface | None] = []
        for char in value:
            prefix = f"{char.upper()} bold" if char.isalpha() else char if char.isdigit() else symbols.get(char)
            if prefix and self._alphabet_atlas.has(prefix):
                frame = self._alphabet_atlas.animation(prefix)[0]
                bounds = frame.get_bounding_rect()
                glyphs.append(frame.subsurface(bounds).copy() if bounds.width else frame)
            else:
                glyphs.append(None)
        tallest = max((glyph.get_height() for glyph in glyphs if glyph and glyph.get_height() > 30), default=60)
        width = sum(glyph.get_width() + 4 if glyph else 36 for glyph in glyphs) or 1
        canvas = pygame.Surface((width, tallest + 10), pygame.SRCALPHA)
        x = 0
        for glyph in glyphs:
            if glyph:
                canvas.blit(glyph, (x, tallest - glyph.get_height()))
                x += glyph.get_width() + 4
            else:
                x += 36
        scaled = pygame.transform.smoothscale(canvas, (max(1, round(width * height / tallest)), max(1, round((tallest + 10) * height / tallest))))
        self.cache[key] = scaled
        return scaled

    def loading_screen(self, label: str = "LOADING...", progress: float | None = None) -> None:
        """Gros texte au centre ; avec `progress` (0 à 1) : pourcentage et barre de progression."""
        self.screen.fill(BLACK)
        text = fit(self.alphabet(self.tr(label).rstrip(".").upper(), 110), WIDTH - 80, 140)
        self.screen.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 50)))
        if progress is not None:
            value = max(0.0, min(1.0, progress))
            self.text(self.screen, f"{round(value * 100)} %", (WIDTH // 2, HEIGHT // 2 + 40), 64, center=True, bold=True, raw=True)
            bar = pygame.Rect(0, 0, 700, 22); bar.center = (WIDTH // 2, HEIGHT // 2 + 150)
            pygame.draw.rect(self.screen, (60, 60, 70), bar, border_radius=11)
            if value > 0:
                pygame.draw.rect(self.screen, WHITE, (bar.x, bar.y, max(22, round(bar.width * value)), bar.height), border_radius=11)
        self.present()
        pygame.event.pump()

    def loading_step(self, progress: float) -> None:
        """Étape du chargement d'une chanson (rien à l'écran si la chanson est relancée sans écran de chargement)."""
        if self.loading:
            self.loading_screen(progress=progress)

    def draw_version(self, screen: pygame.Surface) -> None:
        active = sum(mod.enabled for mod in self.mods)
        label = self.tr("MOD ACTIVE" if active == 1 else "MODS ACTIVE")
        line = f"Python Engine v{VERSION}  •  {active} {label}"
        self.text(screen, line, (12, HEIGHT - 25), 17, color=BLACK, raw=True)
        self.text(screen, line, (10, HEIGHT - 27), 17, color=WHITE, raw=True)

    # ---------- sons ----------
    def change(self, state: BaseState) -> None:
        self.state = state

    def play_menu_music(self) -> None:
        try:
            pygame.mixer.music.load(self.assets.path("music/freakyMenu/freakyMenu.ogg"))
            pygame.mixer.music.set_volume(self.volume); pygame.mixer.music.play(-1)
            self.music_started_at = pygame.time.get_ticks()
        except pygame.error: pass

    def menu_beat(self) -> float:
        return (pygame.time.get_ticks() - self.music_started_at) * MENU_BPM / 60000

    def play_sound(self, relative: str, volume: float = 1.0) -> None:
        path = self.assets.path(relative)
        if path.is_file():
            try:
                sound = self.assets.sound(path); sound.set_volume(self.volume * volume); sound.play()
            except pygame.error: pass

    def scroll_sound(self) -> None: self.play_sound("sounds/scrollMenu.ogg")
    def confirm_sound(self) -> None: self.play_sound("sounds/confirmMenu.ogg")
    def cancel_sound(self) -> None: self.play_sound("sounds/cancelMenu.ogg")

    # ---------- enchaînement des chansons ----------
    def start_playlist(self, song_ids: list[str], difficulty: str, story_week: int | None = None) -> None:
        self.playlist = song_ids; self.playlist_index = 0; self.playlist_difficulty = difficulty
        self.story_week = story_week
        self.week_misses = 0
        self.week_stats: dict = {}
        self.deaths = 0
        self.editor_return = None
        self._start_song(song_ids[0], difficulty)

    def _start_song(self, song_id: str, difficulty: str) -> None:
        self.loading = True
        self.loading_screen(progress=0)
        # Les atlas d'une chanson ne servent plus à la suivante : on libère la mémoire.
        self.assets.clear()
        self.cache = {}
        song = self.data.songs[song_id]
        key = difficulty if difficulty in song.charts else sorted(song.charts, key=difficulty_sort_key)[0]
        try:
            self.change(PlayState(self, song_id, key))
        finally:
            self.loading = False

    def advance_playlist(self) -> bool:
        self.playlist_index += 1
        if self.playlist_index >= len(self.playlist):
            if self.story_week is not None:
                self.unlock("week")
                if self.week_misses == 0:
                    self.unlock("week-fc")
            return False
        self._start_song(self.playlist[self.playlist_index], self.playlist_difficulty)
        return True

    def back_to_menu(self) -> None:
        pygame.mixer.music.stop()
        if self.editor_return:
            editor, self.editor_return = self.editor_return, None
            self.change(editor)
            return
        self.play_menu_music()
        if self.story_week is not None:
            self.change(menus.StoryMenuState(self, self.story_week, self.playlist_difficulty))
        elif self.playlist:
            self.change(menus.FreeplayState(self, self.playlist[0], self.playlist_difficulty))
        else:
            self.change(menus.MainMenuState(self))

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(self.settings.fps_limit) / 1000, .1)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and self.volume_key(event):
                    continue
                elif event.type == pygame.KEYDOWN and (event.key == pygame.K_F11 or
                                                       (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT)):
                    self.set_fullscreen(not self.is_fullscreen); self.settings.save()
                    continue
                elif self.gamepads.handles(event):
                    for translated in self.gamepads.translate(event, self.state):
                        self.state.event(translated)
                else:
                    self.state.event(event)
            self.state.update(dt)
            self.state.draw(self.screen)
            self.draw_toasts(self.screen)
            self.draw_volume_tray(self.screen)
            if self.settings.show_fps:
                self.text(self.screen, f"FPS {self.clock.get_fps():.0f}", (8, 6), 18, color=WHITE, outline=True, raw=True)
            self.present()
        self.settings.volume = self.volume
        self.settings.save()
        pygame.quit()


# Compatibilité : anciens noms importés depuis pyfnf.game.
TitleState, MainMenuState, StoryMenuState, FreeplayState = menus.TitleState, menus.MainMenuState, menus.StoryMenuState, menus.FreeplayState
OptionsState, ModsState = menus.OptionsState, menus.ModsState
