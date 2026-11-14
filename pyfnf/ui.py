"""Constantes et petits outils d'affichage partagés par tous les écrans."""
from __future__ import annotations

import math

import pygame

from .stage import Actor

WIDTH, HEIGHT = 1280, 720
SCREEN_CAM = (WIDTH / 2, HEIGHT / 2)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
PINK = (255, 0, 110)
CYAN = (0, 220, 255)
RED = (255, 60, 80)
YELLOW = (255, 220, 60)
TRACK_PINK = (229, 87, 119)
LANE_COLORS = ((194, 75, 255), (0, 220, 255), (43, 255, 93), (255, 55, 70))
LANE_NAMES = ("LEFT", "DOWN", "UP", "RIGHT")
DIRECTIONS = ("left", "down", "up", "right")


def fit(surface: pygame.Surface, max_width: int, max_height: int) -> pygame.Surface:
    factor = min(max_width / surface.get_width(), max_height / surface.get_height())
    if factor >= 1:
        return surface
    return pygame.transform.smoothscale(surface, (max(1, round(surface.get_width() * factor)), max(1, round(surface.get_height() * factor))))


def scale_by(surface: pygame.Surface, factor: float, pixel: bool = False) -> pygame.Surface:
    size = (max(1, round(surface.get_width() * factor)), max(1, round(surface.get_height() * factor)))
    return pygame.transform.scale(surface, size) if pixel else pygame.transform.smoothscale(surface, size)


def tint(surface: pygame.Surface, color: tuple[int, int, int]) -> pygame.Surface:
    copy = surface.copy()
    copy.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return copy


def colorize(surface: pygame.Surface, color: tuple[int, int, int]) -> pygame.Surface:
    """Recolore un sprite (note dorée, bonbon...) : niveaux de gris éclaircis puis teinte, le contour reste foncé."""
    gray = pygame.transform.grayscale(surface)
    gray.fill((70, 70, 70), special_flags=pygame.BLEND_RGB_ADD)
    gray.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return gray


def parse_color(value: str) -> tuple[int, int, int]:
    value = str(value).lstrip("#")
    if len(value) == 8:
        value = value[2:]
    try:
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
    except (ValueError, TypeError):
        return (249, 207, 81)


def shade(alpha: int, color=(0, 0, 0)) -> pygame.Surface:
    surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    surface.fill((*color, alpha))
    return surface


def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def lerp(current: float, target: float, dt: float, speed: float = 12.0) -> float:
    """Rapprochement doux indépendant du FPS."""
    return current + (target - current) * (1 - math.exp(-speed * dt))


def make_actor(assets, asset_path: str, animations: list[dict], scale: float = 1.0, flip: bool = False, pixel: bool = False) -> Actor:
    actor = Actor(assets, asset_path, animations, (scale, scale), flip, pixel)
    if actor.anims:
        actor.play(next(iter(actor.anims)), 0)
    return actor


# Thème des outils : comme les éditeurs officiels de FNF (fenêtres gris clair, damier, texte foncé).
UI_BG = (236, 236, 239)
UI_TITLE = (206, 206, 214)
UI_BORDER = (140, 140, 150)
UI_TEXT = (28, 28, 34)
UI_MUTED = (95, 95, 108)
UI_ACCENT = (146, 90, 230)
CHECKER = ((231, 230, 230), (217, 213, 213))


def window(app, screen: pygame.Surface, rect: pygame.Rect, title: str) -> int:
    """Fenêtre grise avec barre de titre ; renvoie le y du contenu."""
    shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 70))
    screen.blit(shadow, (rect.x + 4, rect.y + 4))
    pygame.draw.rect(screen, UI_BG, rect)
    pygame.draw.rect(screen, UI_TITLE, (rect.x, rect.y, rect.width, 26))
    pygame.draw.line(screen, UI_BORDER, (rect.x, rect.y + 26), (rect.right - 1, rect.y + 26))
    pygame.draw.rect(screen, UI_BORDER, rect, 1)
    app.text(screen, title, (rect.x + 10, rect.y + 4), 16, color=UI_TEXT, bold=True, raw=True)
    return rect.y + 34


def is_emoji(char: str) -> bool:
    code = ord(char)
    return code >= 0x1F000 or 0x2300 <= code < 0x2400 or 0x2600 <= code < 0x2800 or code in (0x200D, 0xFE0F, 0x2B50, 0x2B06)


def rich_text(app, value: str, size: int, color: tuple[int, int, int], bold: bool = False) -> pygame.Surface:
    """Texte avec émojis en couleur (police Segoe UI Emoji de Windows) : annonces."""
    key = ("rich-text", value, size, color, bold)
    if key in app.cache:
        return app.cache[key]
    runs: list[list] = []
    for char in value:
        emoji = is_emoji(char)
        if runs and runs[-1][0] == emoji:
            runs[-1][1] += char
        else:
            runs.append([emoji, char])
    if ("emoji-font", size) not in app.cache:
        # shortcut: hors Windows sans police d'émojis, ils s'affichent en carrés.
        app.cache[("emoji-font", size)] = pygame.font.SysFont("segoe ui emoji,noto color emoji,apple color emoji", size)
    fonts = [(app.cache[("emoji-font", size)] if emoji else app.font(size, bold), text) for emoji, text in runs]
    images = [font.render(text, True, color) for font, text in fonts if font.size(text)[0]]  # sélecteur seul = largeur 0
    height = max((image.get_height() for image in images), default=1)
    surface = pygame.Surface((max(1, sum(image.get_width() for image in images)), height), pygame.SRCALPHA)
    x = 0
    for image in images:
        surface.blit(image, (x, (height - image.get_height()) // 2))
        x += image.get_width()
    app.cache[key] = surface
    return surface


def rows(app, screen: pygame.Surface, x: int, y: int, lines, size: int = 16, gap: int = 22) -> int:
    for line in lines:
        if isinstance(line, tuple):
            label, value = line
            app.text(screen, label, (x, y), size, color=UI_MUTED, raw=True)
            app.text(screen, str(value), (x + 130, y), size, color=UI_TEXT, raw=True)
        else:
            app.text(screen, line, (x, y), size, color=UI_TEXT, raw=True)
        y += gap
    return y


SUBTITLE_STYLE = {"font": "", "size": 28, "bold": True, "color": [255, 255, 255], "opacity": 100,
                  "background": [0, 0, 0], "background_opacity": 63, "outline": False, "position": "bottom"}


def draw_subtitle(app, screen: pygame.Surface, line: str, style: dict | None = None, bottom: int = HEIGHT - 44) -> None:
    """Sous-titre (une ou plusieurs lignes séparées par \n) avec le style d'un mod : font (police du système ou fichier
    .ttf du mod, ex. "fonts/vcr.ttf"), size, bold, color [r, g, b], opacity (0-100), background [r, g, b],
    background_opacity (0-100), outline (contour noir), position ("bottom", "middle", "top")."""
    style = {**SUBTITLE_STYLE, **(style or {})}
    key = ("subtitle-font", str(style["font"]), int(style["size"]), bool(style["bold"]))
    font = app.cache.get(key)
    if font is None:
        path = app.assets.path(str(style["font"])) if style["font"] else None
        try:
            if path is not None and path.is_file():
                font = pygame.font.Font(str(path), key[2])
            elif style["font"]:
                font = pygame.font.SysFont(str(style["font"]), key[2], bold=key[3])
        except (pygame.error, OSError):
            font = None
        font = app.cache[key] = font or app.font(key[2], key[3])
    color = tuple(int(c) for c in list(style["color"])[:3])
    images = []
    for part in str(line).split("\n"):
        image = font.render(part, True, color)
        if style["outline"]:
            shadow, framed = font.render(part, True, (0, 0, 0)), pygame.Surface((image.get_width() + 4, image.get_height() + 4), pygame.SRCALPHA)
            for ox, oy in ((0, 2), (4, 2), (2, 0), (2, 4), (0, 0), (4, 0), (0, 4), (4, 4)):
                framed.blit(shadow, (ox, oy))
            framed.blit(image, (2, 2))
            image = framed
        if image.get_width() > WIDTH - 80:
            image = pygame.transform.smoothscale(image, (WIDTH - 80, round(image.get_height() * (WIDTH - 80) / image.get_width())))
        images.append(image)
    box = pygame.Rect(0, 0, max(image.get_width() for image in images) + 28, sum(image.get_height() for image in images) + 12)
    position = str(style["position"])
    if position == "top":
        box.midtop = (WIDTH // 2, 40)
    elif position == "middle":
        box.center = (WIDTH // 2, HEIGHT // 2)
    else:
        box.midbottom = (WIDTH // 2, bottom)
    back_alpha = round(255 * max(0, min(100, float(style["background_opacity"]))) / 100)
    if back_alpha:
        back = pygame.Surface(box.size, pygame.SRCALPHA)
        back.fill((*[int(c) for c in list(style["background"])[:3]], back_alpha))
        screen.blit(back, box)
    text_alpha = round(255 * max(0, min(100, float(style["opacity"]))) / 100)
    y = box.y + 6
    for image in images:
        if text_alpha < 255:
            image.set_alpha(text_alpha)
        screen.blit(image, image.get_rect(midtop=(WIDTH // 2, y)))
        y += image.get_height()


def toolbar(app, screen: pygame.Surface, left: str, right: str = "") -> None:
    pygame.draw.rect(screen, (244, 244, 246), (0, 0, WIDTH, 30))
    pygame.draw.line(screen, UI_BORDER, (0, 30), (WIDTH, 30))
    app.text(screen, left, (12, 6), 16, color=UI_TEXT, bold=True, raw=True)
    if right:
        app.text(screen, right, (WIDTH - 12, 7), 15, color=UI_MUTED, right=True, raw=True)


def toast(app, screen: pygame.Surface, message: str, at: int, y: int = HEIGHT - 90) -> None:
    if message and pygame.time.get_ticks() - at < 4000:
        font = app.font(16)
        width = min(WIDTH - 40, font.size(message)[0] + 30)
        box = pygame.Rect(0, 0, width, 34); box.center = (WIDTH // 2, y)
        pygame.draw.rect(screen, (255, 250, 220), box)
        pygame.draw.rect(screen, (190, 160, 60), box, 1)
        app.text(screen, message[:150], (box.centerx, box.y + 8), 16, center=True, color=UI_TEXT, raw=True)


ARROWS = {"↑": 0, "→": 90, "↓": 180, "←": 270}


def keycap(app, label: str, size: int = 17) -> pygame.Surface:
    """Touche de clavier dessinée (face claire, tranche foncée). Les flèches sont tracées, pas écrites."""
    key = ("keycap", label, size)
    if key in app.cache:
        return app.cache[key]
    font = app.font(size, True)
    arrow = label in ARROWS
    text = None if arrow else font.render(label, True, (36, 36, 44))
    height = size + 14
    width = height if arrow else max(height, text.get_width() + 18)
    cap = pygame.Surface((width, height + 5), pygame.SRCALPHA)
    pygame.draw.rect(cap, (24, 24, 30), (0, 0, width, height + 5), border_radius=8)
    pygame.draw.rect(cap, (150, 150, 166), (2, 4, width - 4, height - 1), border_radius=6)
    pygame.draw.rect(cap, (250, 250, 253), (2, 2, width - 4, height - 4), border_radius=6)
    center = (width / 2, height / 2)
    if arrow:
        r = size * .42
        points = [(0, -r), (r * .9, r * .55), (-r * .9, r * .55)]
        angle = math.radians(ARROWS[label])
        rotated = [(center[0] + x * math.cos(angle) - y * math.sin(angle), center[1] + x * math.sin(angle) + y * math.cos(angle)) for x, y in points]
        pygame.draw.polygon(cap, (36, 36, 44), rotated)
    else:
        cap.blit(text, text.get_rect(center=(round(center[0]), round(center[1]))))
    app.cache[key] = cap
    return cap


def key_hints(app, screen: pygame.Surface, hint: str, y: int = HEIGHT - 30, anchor: str = "center", x: int | None = None,
              bar: bool = True, size: int = 17) -> None:
    """Aide de touches « ↑↓ CHOISIR     ENTRÉE OUVRIR » : chaque touche en vrai bouton de clavier, l'action à côté."""
    import re
    groups = []
    for group in re.split(r"\s{3,}", app.tr(hint).strip()):
        keys, _, action = group.partition(" ")
        caps = [keycap(app, char, size) for char in keys] if all(char in ARROWS for char in keys) else [keycap(app, keys, size)]
        label = app.font(size + 1, True).render(action.strip(), True, WHITE)
        shadow = app.font(size + 1, True).render(action.strip(), True, BLACK)
        groups.append((caps, label, shadow))
    gap, spacing = 6, 28
    total = sum(sum(cap.get_width() + 3 for cap in caps) + gap + label.get_width() for caps, label, _ in groups) + spacing * (len(groups) - 1)
    if bar:
        strip = pygame.Surface((WIDTH, size + 34), pygame.SRCALPHA)
        strip.fill((0, 0, 0, 175))
        screen.blit(strip, (0, y - (size + 34) // 2))
    height = size + 24
    row = pygame.Surface((total + 4, height), pygame.SRCALPHA)
    left, middle = 0, height // 2
    for caps, label, shadow in groups:
        for cap in caps:
            row.blit(cap, cap.get_rect(midleft=(left, middle)))
            left += cap.get_width() + 3
        left += gap
        rect = label.get_rect(midleft=(left, middle))
        row.blit(shadow, rect.move(2, 2))
        row.blit(label, rect)
        left += label.get_width() + spacing
    if row.get_width() > WIDTH - 32:  # trop de touches : la ligne est réduite pour tenir dans l'écran
        row = pygame.transform.smoothscale(row, (WIDTH - 32, round(height * (WIDTH - 32) / row.get_width())))
    origin = x if x is not None else WIDTH // 2
    rect = row.get_rect(midleft=(origin, y)) if anchor == "left" else row.get_rect(midright=(origin, y)) if anchor == "right" else row.get_rect(center=(origin, y))
    rect.clamp_ip(pygame.Rect(16, 0, WIDTH - 32, HEIGHT))
    screen.blit(row, rect)


class BaseState:
    def __init__(self, app):
        self.app = app

    def event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        pass
