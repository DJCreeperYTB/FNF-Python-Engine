"""Dialogues (format V-Slice) et cinématiques vidéo, affichés par-dessus la partie avant/après une chanson.

Dialogue : data/dialogue/conversations/<id>.json, speakers/<id>.json, boxes/<id>.json
Vidéo    : videos/<nom>.mp4 (décodée avec PyAV)
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pygame

from .stage import Actor, HEIGHT, WIDTH
from .ui import draw_subtitle

SCREEN_CAM = (WIDTH / 2, HEIGHT / 2)
ORIGIN = (627, 370)  # position écran du point (0, 0) des offsets de portraits et de bulles


def _color(value: str, default=(0, 0, 0, 255)) -> tuple[int, int, int, int]:
    """#RRGGBB ou #AARRGGBB (format Flixel) -> RGBA."""
    text = str(value or "").lstrip("#")
    try:
        if len(text) == 8:
            return int(text[2:4], 16), int(text[4:6], 16), int(text[6:8], 16), int(text[0:2], 16)
        if len(text) == 6:
            return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), 255
    except ValueError:
        pass
    return default


def conversation_path(assets, conversation_id: str, language: str = "en", censored: bool = False) -> Path | None:
    """<id>-fr.json quand le jeu est en français (s'il existe), sinon <id>.json.
    Mode enfant : <id>-censored(-fr).json d'abord, s'il existe."""
    ids = [f"{conversation_id}-censored", conversation_id] if censored else [conversation_id]
    names = [name for base in ids for name in ([f"{base}-{language}"] if language != "en" else []) + [base]]
    for name in names:
        path = assets.path(f"data/dialogue/conversations/{name}.json")
        if path.is_file():
            return path
    return None


def video_path(assets, name: str) -> Path | None:
    for extension in (".mp4", ".mkv", ".webm", ".mov"):
        path = assets.search("videos", name + extension) or assets.path(f"videos/{name}{extension}")
        if path and path.is_file():
            return path
    return None


def _first_frame_size(anim) -> tuple[float, float]:
    """Taille (non agrandie) de la 1re image de la feuille : cadre Sparrow (frameWidth/Height) ou image d'atlas."""
    source = anim.source
    frames = getattr(source, "frames", None)
    if frames:
        surface = frames[0][1]
        ox, oy = source.origins.get(id(surface), (0, 0))  # image qui dépasse du cadre : on retire le dépassement
        return surface.get_width() + ox, surface.get_height() + oy
    return anim.raw(0)[0].get_size()


class _Piece:
    """Portrait ou bulle : Actor placé comme un FlxSprite (échelle autour du centre, puis offsets)."""

    def __init__(self, assets, data: dict, speaker: bool = False):
        scale = float(data.get("scale", 1))
        self.actor = Actor(assets, str(data.get("assetPath", "")), data.get("animations") or [], (scale, scale),
                           bool(data.get("flipX", False)), bool(data.get("isPixel", False)),
                           hidden_layers=tuple(str(name) for name in data.get("hiddenLayers", [])))
        self.data = data
        # Portraits et bulles : offsets d'animation en pixels d'écran, sans échelle.
        self.actor.scale_offsets = False
        if self.actor.anims:
            off_x, off_y = (data.get("offsets") or [0, 0])[:2]
            origin = ORIGIN  # bulle : repère calé sur la Week 6 (bulle centrée en bas)
            if speaker:
                # Speaker.hx officiel : sa 1re image est centrée à l'écran (screenCenter à l'échelle 1), puis
                # x = offsets globaux + position centrée + offsets d'animation (ajoutés).
                width, height = _first_frame_size(next(iter(self.actor.anims.values())))
                origin = ((WIDTH - width) / 2, (HEIGHT - height) / 2)
                for anim in self.actor.anims.values():
                    anim.offsets = (-anim.offsets[0], -anim.offsets[1])  # Actor.draw les retranche
            self.actor.x = float(off_x) + origin[0]
            self.actor.y = float(off_y) + origin[1]
            self.actor.play(next(iter(self.actor.anims)), 0)

    def play(self, name: str, now: int) -> None:
        if not self.actor.play(name, now, force=True) and "idle" in self.actor.anims:
            self.actor.play("idle", now, force=True)

    def draw(self, screen: pygame.Surface, now: int) -> None:
        self.actor.draw(screen, SCREEN_CAM, 1.0, now)


class Dialogue:
    """Conversation à la Week 6 : fond, musique, portrait qui parle, bulle et texte tapé lettre par lettre."""

    CHARS_PER_SECOND = 28

    def __init__(self, app, conversation_id: str):
        self.app = app
        self.assets = app.assets
        path = conversation_path(app.assets, conversation_id, app.settings.language, app.settings.child_mode)
        data = app.assets.json(path) if path else {}
        self.lines = [line for line in data.get("dialogue", []) if isinstance(line, dict)]
        backdrop = data.get("backdrop") or {}
        self.backdrop = _color(backdrop.get("color"), (0, 0, 0, 0)) if backdrop.get("type", "solid") == "solid" else (0, 0, 0, 0)
        self.fade_ms = float(backdrop.get("fadeTime", 0) or 0) * 1000
        self.outro_ms = float((data.get("outro") or {}).get("fadeTime", .5) or .5) * 1000
        self.speakers: dict[str, _Piece] = {}
        self.boxes: dict[str, _Piece] = {}
        self.index = -1
        self.typed = 0.0
        self.line_started = 0
        self.opened_at = pygame.time.get_ticks()
        self.closing_at = 0
        self.done = not self.lines
        self.blip_at = 0
        music = data.get("music") or {}
        if music.get("asset"):
            name = str(music["asset"])
            track = self.assets.search("music", f"{name}.ogg") or self.assets.search("music", f"{name}/{name}.ogg")
            if track:
                try:
                    pygame.mixer.music.load(track); pygame.mixer.music.set_volume(app.volume * .8)
                    pygame.mixer.music.play(-1 if music.get("looped", True) else 0)
                except pygame.error:
                    pass
        self.voice: list[Path] = []
        self.blip = self.assets.search("sounds", "pixelText.ogg")
        self.click = self.assets.search("sounds", "clickText.ogg")
        self.next_line()

    def _piece(self, cache: dict, kind: str, piece_id: str) -> _Piece | None:
        if not piece_id:
            return None
        if piece_id not in cache:
            path = self.assets.path(f"data/dialogue/{kind}/{piece_id}.json")
            try:
                cache[piece_id] = _Piece(self.assets, self.assets.json(path), kind == "speakers") if path.is_file() else None
            except (OSError, ValueError, KeyError, pygame.error):
                cache[piece_id] = None
        return cache[piece_id]

    @property
    def line(self) -> dict:
        return self.lines[self.index] if 0 <= self.index < len(self.lines) else {}

    @property
    def text(self) -> str:
        value = self.line.get("text", "")
        return " ".join(value) if isinstance(value, list) else str(value)

    def next_line(self) -> None:
        self.index += 1
        if self.index >= len(self.lines):
            self.close(); return
        now = pygame.time.get_ticks()
        self.typed, self.line_started = 0.0, now
        speaker = self._piece(self.speakers, "speakers", str(self.line.get("speaker", "")))
        box = self._piece(self.boxes, "boxes", str(self.line.get("box", "default")))
        # Voix du personnage qui parle : "sounds" dans data/dialogue/speakers/<id>.json (sinon le bip de FNF).
        self.voice = [path for path in (self.assets.path(str(rel)) for rel in (speaker.data.get("sounds") or [] if speaker else []))
                      if path.is_file()]
        if speaker:
            speaker.play(str(self.line.get("speakerAnimation", "talk")), now)
        if box:
            box.play(str(self.line.get("boxAnimation", "idle")), now)

    def close(self) -> None:
        if not self.closing_at:
            self.closing_at = pygame.time.get_ticks()

    def event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN or self.closing_at:
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.typed < len(self.text):
                self.typed = len(self.text)
            else:
                self._sound(self.click)
                self.next_line()
        elif event.key == pygame.K_ESCAPE:
            self.close()

    def _sound(self, path: Path | None) -> None:
        if path:
            try:
                sound = self.assets.sound(path); sound.set_volume(self.app.volume * .6); sound.play()
            except pygame.error:
                pass

    def update(self, dt: float) -> None:
        now = pygame.time.get_ticks()
        if self.closing_at:
            if now - self.closing_at >= self.outro_ms:
                self.done = True
                pygame.mixer.music.fadeout(300)
            return
        before = int(self.typed)
        self.typed = min(len(self.text), self.typed + dt * self.CHARS_PER_SECOND)
        if int(self.typed) > before and now - self.blip_at > (95 if self.voice else 45):
            self.blip_at = now
            self._sound(random.choice(self.voice) if self.voice else self.blip)

    def draw(self, screen: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        fade_in = min(1.0, (now - self.opened_at) / self.fade_ms) if self.fade_ms else 1.0
        fade_out = 1 - min(1.0, (now - self.closing_at) / self.outro_ms) if self.closing_at else 1.0
        if self.backdrop[3]:
            layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            layer.fill((*self.backdrop[:3], round(self.backdrop[3] * fade_in * fade_out)))
            screen.blit(layer, (0, 0))
        if self.closing_at:
            return
        speaker = self.speakers.get(str(self.line.get("speaker", "")))
        box = self.boxes.get(str(self.line.get("box", "default")))
        if speaker:
            speaker.draw(screen, now)
        if box:
            box.draw(screen, now)
        text_data = (box.data.get("text") if box else None) or {"offsets": [225, 450], "width": 830, "color": "#3F2021"}
        x, y = (text_data.get("offsets") or [225, 450])[:2]
        width = int(text_data.get("width", 830))
        color = _color(text_data.get("color"), (63, 32, 33, 255))[:3]
        shadow = _color(text_data.get("shadowColor"), (0, 0, 0, 0))
        size = int(text_data.get("size", 40))
        font = self.app.font(size, bold=True)
        line_height = round(size * 1.3)
        # Retour à la ligne mesuré sur le texte complet : les mots ne sautent pas de ligne pendant la frappe.
        rows, current = [], ""
        for word in self.text.split():
            candidate = f"{current} {word}".strip()
            if current and font.size(candidate)[0] > width:
                rows.append(current)
                current = word
            else:
                current = candidate
        rows.append(current)
        remaining = int(self.typed)
        shadow_offset = max(2, int(text_data.get("shadowWidth", 2)))
        for row, full in enumerate(rows[:4]):
            line = full[:max(0, remaining)]
            remaining -= len(full) + 1
            if not line:
                break
            if shadow[3]:
                screen.blit(font.render(line, True, shadow[:3]), (x + shadow_offset, y + row * line_height + shadow_offset))
            screen.blit(font.render(line, True, color), (x, y + row * line_height))
        if self.typed >= len(self.text) and (now // 400) % 2:
            self.app.text(screen, "▼", (x + width - 20, y + min(4, len(rows)) * line_height - 10), 24, color=color, raw=True)


def make_sound(stereo_s16: bytes, channels: int) -> pygame.mixer.Sound:
    """Son pygame depuis du PCM stéréo 16 bits, adapté au nombre de canaux réel du mixeur (1, 2, 6, 8...)."""
    import numpy as np
    pcm = np.frombuffer(stereo_s16, dtype=np.int16)
    pcm = pcm[: len(pcm) // 2 * 2].reshape(-1, 2)
    if channels == 1:
        pcm = pcm.mean(axis=1).astype(np.int16)
    elif channels > 2:  # gauche/droite sur les deux premiers haut-parleurs, les autres muets
        wide = np.zeros((len(pcm), channels), dtype=np.int16)
        wide[:, :2] = pcm
        pcm = wide
    return pygame.sndarray.make_sound(np.ascontiguousarray(pcm))


class Video:
    """Cinématique vidéo plein écran. Maintenir Entrée/Espace remplit un rond : plein = cinématique passée.

    Sous-titres facultatifs : videos/<nom>.subs.json = {"en": [[début, fin, texte]...], "fr": [...]}.
    """

    HOLD_MS = 900
    SKIP_KEYS = (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_ESCAPE)

    def __init__(self, app, path: Path):
        self.app = app
        self.done = False
        self.hold_started = 0
        self.subtitles = []
        self.subtitle_style = {}
        subs = path.with_name(path.stem + ".subs.json")
        if app.settings.subtitles and subs.is_file():
            try:
                data = json.loads(subs.read_text(encoding="utf-8"))
                self.subtitles = data.get(app.settings.language) or data.get("en") or []
                self.subtitle_style = data.get("style") if isinstance(data.get("style"), dict) else {}
            except (OSError, ValueError):
                pass
        self.error = ""
        self.frame: pygame.Surface | None = None
        self.next_time = 0.0
        self.sound_channel = None
        try:
            import av  # PyAV : décode la vidéo et le son sans ffmpeg installé
            self.container = av.open(str(path))
            stream = self.container.streams.video[0]
            self.frames = self.container.decode(stream)
            audio = av.open(str(path))
            if audio.streams.audio:
                # Le son est fabriqué à la fréquence réelle de la carte son (souvent 48 kHz) : sinon il passe
                # trop vite et trop aigu (effet « nightcore »).
                # Et avec le vrai nombre de canaux : une carte son en 5.1 / 7.1 ouvre le mixeur en 6 ou 8 canaux, et un son
                # stéréo relu comme du 6 canaux passe 3 fois trop vite (effet nightcore des cinématiques de la Week 7).
                frequency, _, channels = pygame.mixer.get_init()
                resampler = av.AudioResampler(format="s16", layout="stereo", rate=frequency)
                chunks = []
                for packet_frame in audio.decode(audio.streams.audio[0]):
                    for converted in resampler.resample(packet_frame):
                        chunks.append(bytes(converted.planes[0])[: converted.samples * 4])
                for converted in resampler.resample(None):  # vide le tampon du rééchantillonneur (fin du son)
                    chunks.append(bytes(converted.planes[0])[: converted.samples * 4])
                audio.close()
                sound = make_sound(b"".join(chunks), channels)
                sound.set_volume(app.volume)
                self.sound_channel = sound.play()
            pygame.mixer.music.stop()
        except Exception as error:  # vidéo illisible ou PyAV absent : on passe la cinématique
            self.error = f"{path.name}: {error}"
            self.done = True
        self.started = pygame.time.get_ticks()

    def stop(self) -> None:
        self.done = True
        if self.sound_channel:
            self.sound_channel.stop()
        try:
            self.container.close()
        except Exception:
            pass

    def event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in self.SKIP_KEYS and not self.hold_started:
            self.hold_started = pygame.time.get_ticks()
        elif event.type == pygame.KEYUP and event.key in self.SKIP_KEYS:
            self.hold_started = 0

    def hold_progress(self) -> float:
        return min(1.0, (pygame.time.get_ticks() - self.hold_started) / self.HOLD_MS) if self.hold_started else 0.0

    def update(self, dt: float) -> None:
        if self.done:
            return
        if self.hold_progress() >= 1:
            self.stop()
            return
        elapsed = (pygame.time.get_ticks() - self.started) / 1000
        try:
            while elapsed >= self.next_time:
                frame = next(self.frames)
                self.next_time = float(frame.time or 0) + 1 / 60
                image = frame.to_image()
                surface = pygame.image.frombytes(image.tobytes(), image.size, "RGB")
                scale = min(WIDTH / image.width, HEIGHT / image.height)
                self.frame = pygame.transform.smoothscale(surface, (round(image.width * scale), round(image.height * scale)))
        except StopIteration:
            self.stop()

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((0, 0, 0))
        if self.frame:
            screen.blit(self.frame, self.frame.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
        elapsed = (pygame.time.get_ticks() - self.started) / 1000
        entry = next((entry for entry in self.subtitles if entry[0] <= elapsed < entry[1]), None)
        if entry:  # [début, fin, texte] ou [début, fin, texte, {style}]
            style = {"size": 30, **self.subtitle_style, **(entry[3] if len(entry) > 3 and isinstance(entry[3], dict) else {})}
            draw_subtitle(self.app, screen, str(entry[2]), style)
        progress = self.hold_progress()
        if progress > 0:
            center, radius = (WIDTH - 58, HEIGHT - 58), 30
            disk = pygame.Surface((radius * 2 + 8, radius * 2 + 8), pygame.SRCALPHA)
            mid = (radius + 4, radius + 4)
            pygame.draw.circle(disk, (0, 0, 0, 170), mid, radius + 4)
            points = [mid] + [(mid[0] + radius * math.sin(2 * math.pi * progress * i / 40),
                               mid[1] - radius * math.cos(2 * math.pi * progress * i / 40)) for i in range(41)]
            if len(points) > 2:
                pygame.draw.polygon(disk, (255, 255, 255, 235), points)
            pygame.draw.circle(disk, (255, 255, 255, 255), mid, radius, 3)
            screen.blit(disk, disk.get_rect(center=center))
