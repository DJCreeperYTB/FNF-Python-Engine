"""Sprites animés, personnages et scènes FNF dessinés à travers une caméra (position + zoom + parallaxe)."""
from __future__ import annotations

import pygame

from .assets import AnimateAtlas, Assets, SparrowAtlas

WIDTH, HEIGHT = 1280, 720
ORIGIN = [0.0, 0.0]  # décalage du dessin du décor (toile agrandie pour le zoom arrière, voir Stage.draw)
LANE_NAMES = ("LEFT", "DOWN", "UP", "RIGHT")
DANCE_ANIMS = ("idle", "danceLeft", "danceRight")


def to_screen(x: float, y: float, cam: tuple[float, float], zoom: float, scroll=(1.0, 1.0)) -> tuple[float, float]:
    """Point du monde -> écran, comme une caméra Flixel (scrollFactor puis zoom autour du centre)."""
    return ((x - (cam[0] - WIDTH / 2) * scroll[0] - WIDTH / 2) * zoom + WIDTH / 2 + ORIGIN[0],
            (y - (cam[1] - HEIGHT / 2) * scroll[1] - HEIGHT / 2) * zoom + HEIGHT / 2 + ORIGIN[1])


def _pair(value, default: float = 1.0) -> tuple[float, float]:
    if isinstance(value, (int, float)):
        return float(value), float(value)
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return float(value[0]), float(value[1])
    return default, default


class Anim:
    def __init__(self, source, prefix: str, indices, fps: float, loop: bool, offsets: tuple[float, float], hidden: tuple[str, ...] = ()):
        self.source, self.prefix, self.fps, self.loop, self.offsets = source, prefix, fps, loop, offsets
        self.hidden = hidden
        self.shift = (0.0, 0.0)  # personnage multi-atlas : passe du repère de cet atlas à celui de l'atlas principal
        self.frames = source.animation(prefix) if isinstance(source, SparrowAtlas) else None
        total = len(self.frames) if self.frames is not None else source.find_label(prefix)[2]
        self.indices = [int(i) for i in indices] if indices else list(range(total))

    def raw(self, i: int) -> tuple[pygame.Surface, tuple[int, int]]:
        index = self.indices[i % len(self.indices)]
        if self.frames is not None:
            frame = self.frames[index % len(self.frames)]
            return frame, self.source.origins.get(id(frame), (0, 0))
        surface, (ox, oy) = self.source.frame(self.prefix, index, self.hidden) if self.hidden else self.source.frame(self.prefix, index)
        return surface, (ox + self.shift[0], oy + self.shift[1])


class Actor:
    """Sprite FNF avec animations nommées (frameIndices, frameRate, looped, offsets) et danse sur le beat."""

    def __init__(self, assets: Assets, asset_path: str, animations: list[dict], scale=(1.0, 1.0),
                 flip: bool = False, pixel: bool = False, library: str | None = None, alpha: float = 1.0,
                 hidden_layers: tuple[str, ...] = ()):
        self.x = self.y = 0.0
        self.scale_offsets = True  # Bopper (persos) : offsets d'animation x échelle ; portraits et bulles de dialogue : non
        self.scroll = (1.0, 1.0)
        self.scale = _pair(scale)
        self.flip, self.pixel, self.alpha = flip, pixel, alpha
        self.visible = True
        self.dance_every = 0
        self.anchor = (0.0, 0.0)
        try:
            default = assets.atlas(asset_path, library) if asset_path else None
        except (OSError, ValueError, KeyError, pygame.error):
            default = None
        self.anims: dict[str, Anim] = {}
        for item in animations:
            try:
                source = assets.atlas(str(item["assetPath"]), library) if item.get("assetPath") else default
            except (OSError, ValueError, KeyError, pygame.error):
                continue  # une animation cassée ne doit pas empêcher le perso de s'afficher
            prefix = str(item.get("prefix", item.get("name", "")))
            if source is None or not source.has(prefix):
                continue
            offsets = _pair(item.get("offsets"), 0.0)
            self.anims[str(item.get("name", "idle"))] = Anim(
                source, prefix, item.get("frameIndices"), float(item.get("frameRate", 24) or 24),
                bool(item.get("looped", False)), offsets, hidden_layers)
        self.current = ""
        self.started = 0
        self._cache: dict[tuple[str, int, float], tuple[pygame.Surface, float, float]] = {}

    def has(self, name: str) -> bool:
        return name in self.anims

    def play(self, name: str, now: int, force: bool = False) -> bool:
        if name not in self.anims:
            return False
        if force or name != self.current:
            self.current, self.started = name, now
        return True

    def frame_number(self, now: int) -> int:
        anim = self.anims[self.current]
        index = max(0, int((now - self.started) * anim.fps / 1000))
        return index % len(anim.indices) if anim.loop else min(index, len(anim.indices) - 1)

    def finished(self, now: int) -> bool:
        anim = self.anims.get(self.current)
        return anim is None or (not anim.loop and (now - self.started) * anim.fps / 1000 >= len(anim.indices))

    def dance(self, beat: int, now: int) -> None:
        if "danceLeft" in self.anims and "danceRight" in self.anims:
            self.play("danceLeft" if beat % 2 == 0 else "danceRight", now, force=True)
        else:
            self.play("idle" if "idle" in self.anims else self.current, now, force=True)

    def beat(self, beat: int, now: int) -> None:
        if self.dance_every > 0 and beat % self.dance_every == 0:
            self.dance(beat, now)

    def _frame(self, anim_name: str, index: int, zoom: float) -> tuple[pygame.Surface, float, float]:
        key = (anim_name, index, zoom)
        cached = self._cache.get(key)
        if cached is not None and len(cached) == 4:
            # Image géante gardée en demi-résolution : ré-agrandie à l'affichage (rapide, au plus proche).
            half, left, top, size = cached
            return pygame.transform.scale(half, size), left, top
        if key not in self._cache:
            anim = self.anims[anim_name]
            raw, (ox, oy) = anim.raw(index)
            size = (max(1, round(raw.get_width() * self.scale[0] * zoom)), max(1, round(raw.get_height() * self.scale[1] * zoom)))
            if size == raw.get_size():
                surface = raw  # même taille : pas de redimensionnement (gros gain sur les décors géants)
            else:
                surface = pygame.transform.scale(raw, size) if self.pixel else pygame.transform.smoothscale(raw, size)
            left = ox
            if self.flip:
                surface = pygame.transform.flip(surface, True, False)
                # Atlas Animate : miroir autour de l'axe fixe du perso (sinon il glisse) ; Sparrow : sur place.
                if anim.frames is None:
                    left = 2 * self.anchor[0] - (ox + raw.get_width())
            top = oy
            # On ne garde que la partie visible : les spritesheets ont souvent de grandes marges vides (mémoire / 2 à / 4).
            bounds = surface.get_bounding_rect()
            if bounds.width and bounds.height and bounds.size != surface.get_size():
                surface = surface.subsurface(bounds).copy()
                left += bounds.x / (self.scale[0] * zoom)
                top += bounds.y / (self.scale[1] * zoom)
            if self.alpha < 1:
                surface.set_alpha(round(self.alpha * 255))
            if surface.get_width() * surface.get_height() > 2_500_000:
                # Image géante (décor animé de la Week 2 : ~2500 x 1800, 18 Mo) : les 6 premières (le décor au repos)
                # restent nettes, les suivantes (les 30 images de l'éclair) sont gardées en demi-résolution.
                self._big_count = getattr(self, "_big_count", 0) + 1
                if self._big_count > 6:
                    size = surface.get_size()
                    self._cache[key] = (pygame.transform.smoothscale(surface, (size[0] // 2, size[1] // 2)), left, top, size)
                    return surface, left, top
            self._cache[key] = (surface, left, top)
        return self._cache[key]

    def warm(self, names, zoom: float) -> None:
        for name in names:
            if name in self.anims:
                for index in range(len(self.anims[name].indices)):
                    self._frame(name, index, zoom)

    def world_rect(self, now: int, zoom: float, anim: str | None = None, index: int | None = None) -> tuple[float, float, float, float]:
        """Rectangle (x, y, largeur, hauteur) d'une image (par défaut celle affichée), dans le repère de la scène."""
        anim = anim or self.current
        surface, left, top = self._frame(anim, self.frame_number(now) if index is None else index, zoom)
        offset_x, offset_y = self.anims[anim].offsets
        if self.scale_offsets:  # comme V-Slice : offsets x échelle
            offset_x, offset_y = offset_x * self.scale[0], offset_y * self.scale[1]
        return (self.x + left * self.scale[0] - offset_x, self.y + top * self.scale[1] - offset_y,
                surface.get_width() / zoom, surface.get_height() / zoom)

    def draw(self, screen: pygame.Surface, cam: tuple[float, float], zoom: float, now: int, tint: tuple | None = None) -> None:
        if not self.visible or self.current not in self.anims:
            return
        index = self.frame_number(now)
        surface, left, top = self._frame(self.current, index, zoom)
        if tint:
            key = ("tint", self.current, index, zoom, tint)
            if key not in self._cache:
                tinted = surface.copy()
                tinted.fill(tint, special_flags=pygame.BLEND_RGB_MULT)
                self._cache[key] = tinted
            surface = self._cache[key]
        offset_x, offset_y = self.anims[self.current].offsets
        # V-Slice (Bopper.getScreenPosition) multiplie les offsets d'animation par l'échelle : x6 pour les sprites pixel.
        if self.scale_offsets:
            offset_x, offset_y = offset_x * self.scale[0], offset_y * self.scale[1]
        x, y = to_screen(self.x + left * self.scale[0] - offset_x, self.y + top * self.scale[1] - offset_y, cam, zoom, self.scroll)
        screen.blit(surface, (round(x), round(y)))


class Character(Actor):
    """Personnage défini par data/characters/<id>.json (format V-Slice)."""

    def __init__(self, assets: Assets, character_id: str, player: bool = False):
        self.id = character_id
        self.is_player = player
        path = assets.path(f"data/characters/{character_id}.json")
        try:
            config = assets.json(path) if path.is_file() else {}
        except ValueError:
            config = {}
        self.config = config
        scale = float(config.get("scale", 1))
        super().__init__(assets, str(config.get("assetPath", f"characters/{character_id}")), config.get("animations") or [],
                         (scale, scale), bool(config.get("flipX", False)) != player, bool(config.get("isPixel", False)),
                         hidden_layers=tuple(str(name) for name in config.get("hiddenLayers", [])))
        self.dance_every = max(0, round(float(config.get("danceEvery", 1))))
        self.sing_steps = float(config.get("singTime", 8))
        self.global_offsets = _pair(config.get("offsets"), 0.0)
        self.camera_offsets = _pair(config.get("cameraOffsets"), 0.0)
        self.stage_camera_offsets = (0.0, 0.0)
        icon = config.get("healthIcon") or {}
        self.icon_id = str(icon.get("id", character_id))
        self.icon_pixel = bool(icon.get("isPixel", config.get("isPixel", False)))
        self.last_sing = -10 ** 9
        self.holding = False
        # Scripts (ex. tankman_bloody.py) : suffixe essayé en premier pour chaque animation ("-bloody" -> idle-bloody...)
        # et animation qui ne se laisse pas couper avant sa fin (canPlayOtherAnims = false du jeu officiel).
        self.anim_suffix = ""
        self.locked = ""
        start = config.get("startingAnimation")
        reference = next((name for name in (start, "idle", "danceRight", "danceLeft") if name in self.anims), next(iter(self.anims), None))
        self.center = (0.0, 0.0)
        self.frame0 = (0.0, 0.0)
        if reference:
            raw, (ox, oy) = self.anims[reference].raw(0)
            width, height = raw.get_size()
            source = self.anims[reference].source
            if config.get("renderType") in ("animateatlas", "multianimateatlas") and isinstance(source, AnimateAtlas):
                # Comme le jeu officiel (flixel-animate) : repère = cadre de toutes les animations, pas la 1re image.
                ox, oy, width, height = source.whole_bounds()
                # flixel-animate place chaque timeline par SON cadre : une animation d'un autre atlas (multi-atlas) est
                # ramenée dans le repère de l'atlas principal (les offsets du JSON officiel comptent là-dessus).
                for anim in self.anims.values():
                    if isinstance(anim.source, AnimateAtlas) and anim.source is not source:
                        sx, sy = anim.source.whole_bounds()[:2]
                        anim.shift = (ox - sx, oy - sy)
            self.anchor = (ox + width / 2, oy + height)
            self.center = (ox + width / 2, oy + height / 2)
            self.frame0 = (ox, oy)
            self.play(reference, 0)
        self.attachments = [Attachment(assets, item) for item in config.get("attachments") or []]

    @property
    def loaded(self) -> bool:
        return bool(self.anims)

    def place(self, x: float, y: float) -> None:
        """Pieds (bas-centre de la pose de repos) posés sur la position de la scène, comme V-Slice.
        V-Slice ajoute les offsets globaux deux fois : setScale (+offset) puis getScreenPosition (+offset x échelle)."""
        self.x = x - self.anchor[0] * self.scale[0] + self.global_offsets[0] * (1 + self.scale[0])
        self.y = y - self.anchor[1] * self.scale[1] + self.global_offsets[1] * (1 + self.scale[1])

    def focus(self) -> tuple[float, float]:
        """BaseCharacter.resetCameraFocusPoint : centre du perso à sa position d'origine, où les offsets globaux ne comptent
        qu'une fois (le second ajout, x échelle, n'est qu'à l'affichage) : sinon x7 pour les pixel (Spirit, caméra trop bas)."""
        sx, sy = self.scale
        gx, gy = self.global_offsets
        return (self.x + self.center[0] * sx - gx * sx + self.camera_offsets[0] + self.stage_camera_offsets[0],
                self.y + self.center[1] * sy - gy * sy + self.camera_offsets[1] + self.stage_camera_offsets[1])

    MISS_TINT = (140, 110, 255)

    def sing(self, lane: int, now: int, miss: bool = False) -> None:
        name = f"sing{LANE_NAMES[lane]}"
        self.missing = False
        if miss and not self.has(name + "miss") and self.has(name):
            # Pas d'animation de raté (adversaire joué par le joueur...) : sa pose de chant, teintée en violet.
            self.play(name, now, force=True)
            self.missing = True
            self.last_sing = now
            return
        if self.play(f"{name}{'miss' if miss else ''}", now, force=True) or miss:
            self.last_sing = now

    def play(self, name: str, now: int, force: bool = False) -> bool:
        if self.locked and self.current == self.locked and name != self.locked and not self.finished(now):
            return False
        if self.anim_suffix and name + self.anim_suffix in self.anims:
            name += self.anim_suffix
        return super().play(name, now, force)

    def play_special(self, name: str, now: int) -> None:
        """Animation d'événement (hey, cheer...) : la danse ne l'interrompt pas avant sa fin."""
        if self.play(name, now, force=True):
            self.last_sing = -10 ** 9

    def draw(self, screen: pygame.Surface, cam: tuple[float, float], zoom: float, now: int) -> None:
        if self.visible and self.attachments:
            # Repère des scripts officiels (nene.hxc) : coin de la première image du personnage tel qu'il est dessiné.
            base_x = self.x + self.frame0[0] * self.scale[0]
            base_y = self.y + self.frame0[1] * self.scale[1]
            for attachment in self.attachments:
                attachment.draw(screen, cam, zoom, now, base_x, base_y, self.scroll)
        tint = self.MISS_TINT if getattr(self, "missing", False) and self.current.startswith("sing") else None
        super().draw(screen, cam, zoom, now, tint)

    def beat(self, beat: int, now: int, step_ms: float = 150) -> None:
        for attachment in self.attachments:
            attachment.beat(beat, now)
        if self.dance_every <= 0 or beat % self.dance_every != 0:
            return
        if self.current.startswith("sing"):
            if self.holding or now - self.last_sing < self.sing_steps * step_ms:
                return
        elif self.current not in DANCE_ANIMS and not self.finished(now):
            return
        self.dance(beat, now)


class Attachment:
    """Élément dessiné derrière un personnage et qui le suit (ex. l'enceinte A-Bot de Néné).

    Champ "attachments" de data/characters/<id>.json : assetPath (image, Sparrow ou atlas Animate), prefix,
    position [x, y] par rapport au coin de la première image du personnage, scale, isPixel, beat (rejoue à chaque temps),
    color + size pour un simple rectangle. Les éléments sont dessinés dans l'ordre de la liste, sous le personnage.
    """

    def __init__(self, assets: Assets, data: dict):
        self.data = data
        self.position = _pair(data.get("position"), 0.0)
        self.scale = float(data.get("scale", 1) or 1)
        self.pixel = bool(data.get("isPixel", False))
        self.on_beat = bool(data.get("beat", False))
        self.center_scale = bool(data.get("centerScale", False))  # FlxSprite agrandi autour de son centre (sans updateHitbox)
        self.surface: pygame.Surface | None = None
        self.actor: Actor | None = None
        self.origin0 = (0.0, 0.0)
        if "color" in data:
            width, height = _pair(data.get("size"), 10.0)
            self.surface = pygame.Surface((max(1, round(width)), max(1, round(height))))
            self.surface.fill(tuple(data["color"])[:3])
            return
        asset = str(data.get("assetPath", ""))
        path = assets.resolve_image(asset)
        if path and path.suffix == ".png" and not path.with_suffix(".xml").is_file():
            self.surface = assets.image(path)
            self.size0 = self.surface.get_size()
            return
        actor = Actor(assets, asset, [{"name": "idle", "prefix": str(data.get("prefix", "")), "looped": bool(data.get("looped", False))}],
                      (self.scale, self.scale), False, self.pixel)
        if actor.anims:
            actor.play("idle", 0)
            raw, origin = actor.anims["idle"].raw(0)
            self.origin0 = origin
            self.size0 = raw.get_size()
            source = actor.anims["idle"].source
            if isinstance(source, AnimateAtlas):  # atlas (A-Bot) : placé par le cadre de toute sa timeline, comme le jeu
                self.origin0 = source.whole_bounds()[:2]
            self.actor = actor

    def beat(self, beat: int, now: int) -> None:
        if self.actor and self.on_beat:
            self.actor.play("idle", now, force=True)

    def draw(self, screen: pygame.Surface, cam, zoom: float, now: int, base_x: float, base_y: float, scroll) -> None:
        x, y = base_x + self.position[0], base_y + self.position[1]
        if self.center_scale:
            width, height = getattr(self, "size0", (0, 0))
            x -= width * (self.scale - 1) / 2
            y -= height * (self.scale - 1) / 2
        if self.actor:
            self.actor.scroll = scroll
            self.actor.x, self.actor.y = x - self.origin0[0] * self.scale, y - self.origin0[1] * self.scale
            self.actor.draw(screen, cam, zoom, now)
        elif self.surface:
            key = (zoom, self.scale)
            if getattr(self, "_scaled_key", None) != key:
                size = (max(1, round(self.surface.get_width() * self.scale * zoom)), max(1, round(self.surface.get_height() * self.scale * zoom)))
                self._scaled = pygame.transform.scale(self.surface, size) if self.pixel or "color" in self.data else pygame.transform.smoothscale(self.surface, size)
                self._scaled_key = key
            sx, sy = to_screen(x, y, cam, zoom, scroll)
            screen.blit(self._scaled, (round(sx), round(sy)))


class StaticProp:
    def __init__(self, surface: pygame.Surface, x: float, y: float, scroll: tuple[float, float]):
        self.surface, self.x, self.y, self.scroll = surface, x, y, scroll

    def beat(self, beat: int, now: int) -> None:
        pass

    def draw(self, screen: pygame.Surface, cam: tuple[float, float], zoom: float, now: int) -> None:
        x, y = to_screen(self.x, self.y, cam, zoom, self.scroll)
        surface = self.surface
        if x < screen.get_width() and y < screen.get_height() and x + surface.get_width() > 0 and y + surface.get_height() > 0:
            screen.blit(surface, (round(x), round(y)))


class Stage:
    DEFAULT_CHARACTERS = {
        "bf": {"position": [989.5, 885], "zIndex": 300, "cameraOffsets": [-100, -100]},
        "dad": {"position": [335, 885], "zIndex": 200, "cameraOffsets": [150, -100]},
        "gf": {"position": [751.5, 787], "zIndex": 100, "cameraOffsets": [0, 0]},
    }

    def __init__(self, assets: Assets, stage_id: str, zoom: float | None = None):
        self.assets = assets
        self.id = stage_id
        self.zoom = 1.0
        self.items: list[tuple[float, int, StaticProp | Actor]] = []
        self.props: dict[str, StaticProp | Actor] = {}
        self.characters = {key: dict(value) for key, value in self.DEFAULT_CHARACTERS.items()}
        path = assets.path(f"data/stages/{stage_id}.json")
        try:
            data = assets.json(path) if path.is_file() else {}
        except ValueError:
            data = {}
        self.data = data
        self.camera_zoom = float(data.get("cameraZoom", 1.0) or 1.0)
        # L'éditeur de scène dessine à un autre zoom que celui du jeu.
        self.zoom = zoom or self.camera_zoom
        library = data.get("directory", "shared")
        for key, values in (data.get("characters") or {}).items():
            if key in self.characters:
                self.characters[key].update(values)
        for order, prop in enumerate(data.get("props", [])):
            try:
                item = self._make_prop(prop, library)
            except (pygame.error, OSError, ValueError, KeyError, IndexError):
                continue
            if item is not None:
                item.prop_index = order
                self.items.append((float(prop.get("zIndex", 0)), order, item))
                self.props[str(prop.get("name", order))] = item
        if not self.items:
            image = assets.path("shared/images/stageback.png")
            if image.is_file():
                self.items.append((0, 0, StaticProp(assets.image(image), -600, -200, (.9, .9))))

    def _make_prop(self, prop: dict, library: str) -> StaticProp | Actor | None:
        asset_path = str(prop.get("assetPath", ""))
        scale = _pair(prop.get("scale", 1))
        x, y = _pair(prop.get("position"), 0.0)
        scroll = _pair(prop.get("scroll", 1))
        alpha = float(prop.get("alpha", 1))
        pixel = bool(prop.get("isPixel", False))
        flip = bool(prop.get("flipX", False))
        if asset_path.startswith("#"):
            surface = pygame.Surface((max(1, round(scale[0] * self.zoom)), max(1, round(scale[1] * self.zoom))), pygame.SRCALPHA)
            color = pygame.Color(asset_path)
            surface.fill((color.r, color.g, color.b, round(255 * alpha)))
            return StaticProp(surface, x, y, scroll)
        animations = prop.get("animations") or []
        if animations:
            actor = Actor(self.assets, asset_path, animations, scale, flip, pixel, library, alpha)
            if actor.anims:
                actor.x, actor.y, actor.scroll = x, y, scroll
                source = next(iter(actor.anims.values())).source
                if isinstance(source, AnimateAtlas):
                    if (prop.get("atlasSettings") or {}).get("applyStageMatrix"):
                        # Placé « comme dans Animate » : la matrice de l'instance sur la scène d'Animate s'ajoute à la position.
                        # shortcut: seule la translation est prise en compte (les décors concernés n'ont ni rotation ni échelle).
                        mx = ((source.animation.get("STI") or {}).get("SI") or {}).get("MX") or [1, 0, 0, 1, 0, 0]
                        actor.x, actor.y = x + float(mx[4]) * scale[0], y + float(mx[5]) * scale[1]
                    else:  # le jeu place un atlas par le cadre de toute sa timeline
                        bounds = source.whole_bounds()
                        actor.x, actor.y = x - bounds[0] * scale[0], y - bounds[1] * scale[1]
                actor.dance_every = int(prop.get("danceEvery", 0) or 0)
                start = prop.get("startingAnimation")
                actor.play(start if start in actor.anims else next(iter(actor.anims)), 0)
                return actor
        resolved = self.assets.resolve_image(asset_path, library)
        if resolved is None:
            return None
        if resolved.is_dir():
            atlas = self.assets.atlas(asset_path, library)
            raw, (ox, oy) = atlas.frame("", 0)
            if (prop.get("atlasSettings") or {}).get("applyStageMatrix"):
                # Placé « comme dans Animate » : translation de l'instance sur la scène d'Animate (cf. décors animés plus haut).
                mx = ((atlas.animation.get("STI") or {}).get("SI") or {}).get("MX") or [1, 0, 0, 1, 0, 0]
                x, y = x + (float(mx[4]) + ox) * scale[0], y + (float(mx[5]) + oy) * scale[1]
            else:
                bounds = atlas.whole_bounds()  # repère officiel : cadre de toute la timeline
                x, y = x + (ox - bounds[0]) * scale[0], y + (oy - bounds[1]) * scale[1]
        else:
            raw = self.assets.image(resolved)
        size = (max(1, round(raw.get_width() * scale[0] * self.zoom)), max(1, round(raw.get_height() * scale[1] * self.zoom)))
        surface = pygame.transform.scale(raw, size) if pixel else pygame.transform.smoothscale(raw, size)
        if flip:
            surface = pygame.transform.flip(surface, True, False)
        if alpha < 1:
            surface.set_alpha(round(alpha * 255))
        return StaticProp(surface, x, y, scroll)

    def add_character(self, key: str, character: Character, slot: str | None = None) -> None:
        data = self.characters[slot or key]
        position = _pair(data.get("position"), 0.0)
        character.place(*position)
        character.stage_camera_offsets = _pair(data.get("cameraOffsets"), 0.0)
        self.items.append((float(data.get("zIndex", 0)), 10_000 + len(self.items), character))

    def beat(self, beat: int, now: int, step_ms: float) -> None:
        for _, _, item in self.items:
            if isinstance(item, Character):
                item.beat(beat, now, step_ms)
            else:
                item.beat(beat, now)

    def draw(self, screen: pygame.Surface, cam: tuple[float, float], now: int) -> None:
        # Toile plus grande que l'écran (zoom arrière de la caméra) : le centre de la caméra reste au centre de la toile.
        ORIGIN[0], ORIGIN[1] = (screen.get_width() - WIDTH) / 2, (screen.get_height() - HEIGHT) / 2
        try:
            for _, _, item in sorted(self.items, key=lambda entry: (entry[0], entry[1])):
                item.draw(screen, cam, self.zoom, now)
        finally:
            ORIGIN[0] = ORIGIN[1] = 0.0
