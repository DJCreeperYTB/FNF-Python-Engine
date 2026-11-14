"""Script GLOBAL du mod (dossier scripts/) : tous les effets façon Dadbattle (Psych Online) pilotés par des événements du chart.

Événements perso reconnus (champ "e" du chart, valeur "v") :
  Lightning {}                                  éclair : animation du décor + flash + tonnerre + petit zoom
  (FlashScreen {"color": [r,g,b], "duration": ms} et ShakeCamera sont des événements natifs du moteur.)
  Zoom {"amount": 0.06, "ms": 500}              coup de zoom de la caméra qui retombe
  ZoomBeat {"every": 2, "amount": 0.03}         zoom sur le rythme tous les N temps (every 0 = arrêt)
  Shake {"power": 10, "ms": 400}                secousse amortie de la caméra
  Tint {"color": [r,g,b], "alpha": 60, "ms": 600}  voile de couleur sur la scène (fondu)
  Spotlight {"on": true, "char": 0|1|2}         projecteur : écran assombri + cône de lumière + fumée en bas
  Rain {"level": 0|1|2}                         pluie
  ArrowWave {"on": true, "amp": 14}             les flèches ondulent
  Scroll {"mode": "middle"|"normal"|"flip"}     flèches au centre / retour / scroll inversé
"""
import math
import random

import numpy as np
import pygame

SONGS = {"cobweb-cadence", "midnight-candlewick", "pumpkin-moon-panic"}


def mine(game):
    """Scripts GLOBAUX : ne rien faire hors des 3 chansons du mod (Darnell, Bopeebo... restent intacts)."""
    return game.song.song_id in SONGS

W, H = 1280, 720
fx = {}


def _cone(width, height):
    """Cône de lumière : alpha 255 au centre, doux sur les bords, plus large vers le bas."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    half = (0.18 + 0.82 * yy / height) * width / 2
    edge = np.clip(1 - np.abs(xx - width / 2) / half, 0, 1)
    vertical = np.clip(yy / (height * .15), 0, 1) * np.clip(1 - (yy / height - .78) / .22, 0, 1)
    alpha = (edge ** .6 * vertical * 255).astype(np.uint8)
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    arr = pygame.surfarray.pixels_alpha(surf)
    arr[:] = alpha.T
    del arr
    return surf


def _glow(radius, color):
    size = radius * 2
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    dist = np.sqrt((xx - radius) ** 2 + (yy - radius) ** 2) / radius
    value = np.clip(1 - dist, 0, 1) ** 2
    surf = pygame.Surface((size, size))
    rgb = pygame.surfarray.pixels3d(surf)
    for i in range(3):
        rgb[..., i] = (value.T * color[i]).astype(np.uint8)
    del rgb
    return surf


def on_create(game):
    if not mine(game):
        return
    now = pygame.time.get_ticks()
    fx.clear()
    fx.update(rain=0, drops=[], zoom_punch=(0, 0.0, 1), beat=(0, 0, 0.0), shake=(-10 ** 9, 0, 1), flash=(-10 ** 9, 1, (255, 255, 255), 0),
              tint=((0, 0, 0), 0.0, (0, 0, 0), 0.0, 0, 1), spot=0.0, spot_target=0.0, spot_chars=(1,), wave=(False, 0.0), amp=0.0,
              ptx=game.PLAYER_X, opx=game.OPPONENT_X, ember=[], smoke=[], title=True, now0=now)
    rng = random.Random(3)
    fx["cone"] = _cone(420, 760)
    beam = fx["cone"].copy()
    rgb, alpha = pygame.surfarray.pixels3d(beam), pygame.surfarray.pixels_alpha(beam)
    rgb[:] = (255, 226, 160)
    alpha[:] = (alpha * .2).astype(np.uint8)
    del rgb, alpha
    fx["beam"] = beam
    fx["glow"] = _glow(150, (255, 120, 20))
    fx["smoke_imgs"] = []
    for i in range(3):
        path = game.assets.path(f"images/halloween/smoke{i}.png")
        if path.is_file():
            image = game.assets.image(path)
            smoke = pygame.transform.smoothscale(image, (image.get_width() * 2 // 3 * 2, image.get_height() * 2 // 3 * 2))
            fx["smoke_imgs"].append(smoke.convert_alpha() if pygame.display.get_surface() else smoke)  # format écran : blit bien plus rapide
    for i in range(12):
        fx["smoke"].append([rng.uniform(-400, W), H - rng.uniform(40, 200), rng.uniform(6, 16) * rng.choice((-1, 1)), rng.randrange(3), rng.random() * 6.28])
    fx["ember"] = [[rng.uniform(0, W), rng.uniform(0, H), rng.uniform(10, 34), rng.uniform(1.5, 3.5), rng.random() * 6.28] for _ in range(26)]
    fx["drops"] = [[rng.uniform(0, W + 200), rng.uniform(0, H), rng.uniform(900, 1500), rng.uniform(14, 30)] for _ in range(320)]
    fx["orig_strum_x"] = game.strum_x
    fx["rng"] = rng

    def wave_strum(player, lane):
        x = fx["orig_strum_x"](player, lane)
        if fx["amp"] > .5:
            t = pygame.time.get_ticks() / 1000
            x += fx["amp"] * math.sin(t * 3.2 + lane * 1.1 + (1.7 if player else 0))
        return round(x)
    game.strum_x = wave_strum


def _flash_ok(game):
    return game.app.settings.flashing_lights


def on_event(game, event):
    if not mine(game):
        return
    kind, v = event.get("e"), event.get("v") or {}
    now = pygame.time.get_ticks()
    if kind == "Lightning":
        prop = game.stage.props.get("halloweenBG")
        if prop is not None and hasattr(prop, "play"):
            prop.play("lightning", now, force=True)
        game.app.play_sound(f"week2/sounds/thunder_{random.randint(1, 2)}.ogg", .6)
        if _flash_ok(game):
            fx["flash"] = (now, 380, (210, 215, 255), 150)
        fx["zoom_punch"] = (now, .018, 450)
    elif kind == "Zoom":
        fx["zoom_punch"] = (now, float(v.get("amount", .05)), float(v.get("ms", 500)))
    elif kind == "ZoomBeat":
        fx["beat"] = (int(v.get("every", 0)), 0, float(v.get("amount", .03)))
    elif kind == "Shake":
        fx["shake"] = (now, float(v.get("power", 8)), float(v.get("ms", 400)))
    elif kind == "Tint":
        cur = _tint_now(now)
        fx["tint"] = (cur[0], cur[1], tuple(v.get("color", (0, 0, 0))), float(v.get("alpha", 0)), now, max(1.0, float(v.get("ms", 500))))
    elif kind == "Spotlight":
        fx["spot_target"] = 1.0 if v.get("on") else 0.0
        if v.get("on"):
            c = int(v.get("char", 1))
            fx["spot_chars"] = (0, 1) if c == 2 else (c,)
    elif kind == "Rain":
        fx["rain"] = int(v.get("level", 1))
    elif kind == "ArrowWave":
        fx["amp_target"] = float(v.get("amp", 12)) if v.get("on") else 0.0
    elif kind == "Scroll":
        mode = v.get("mode")
        if mode == "middle":
            fx["ptx"], fx["opx"] = 410, -560
        elif mode == "normal":
            fx["ptx"], fx["opx"] = 740, 100
        elif mode == "flip":
            game.downscroll = not game.downscroll
            game.receptor_y = H - 50 - game.ARROW_SIZE if game.downscroll else 50


def _tint_now(now):
    c0, a0, c1, a1, t0, dur = fx["tint"]
    p = min(1.0, max(0.0, (now - t0) / dur))
    return tuple(a + (b - a) * p for a, b in zip(c0, c1)), a0 + (a1 - a0) * p


def on_beat(game, beat):
    if not mine(game):
        return
    every, _, amount = fx["beat"]
    if every > 0 and beat % every == 0:
        fx["beat"] = (every, pygame.time.get_ticks(), amount)


def on_update(game, dt):
    if not mine(game):
        return
    now = pygame.time.get_ticks()
    prop = game.stage.props.get("halloweenBG")
    if prop is not None and getattr(prop, "current", "") == "lightning" and prop.finished(now):
        prop.play("idle", now, force=True)
    fx["spot"] += (fx["spot_target"] - fx["spot"]) * min(1.0, dt * 4)
    fx["amp"] += (fx.get("amp_target", 0.0) - fx["amp"]) * min(1.0, dt * 3)
    game.PLAYER_X += (fx["ptx"] - game.PLAYER_X) * min(1.0, dt * 5)
    game.OPPONENT_X += (fx["opx"] - game.OPPONENT_X) * min(1.0, dt * 5)
    if abs(fx["ptx"] - game.PLAYER_X) < 1:
        game.PLAYER_X = fx["ptx"]
    if abs(fx["opx"] - game.OPPONENT_X) < 1:
        game.OPPONENT_X = fx["opx"]


def _stage_layer(game, screen, now):
    """Zoom de caméra + secousse appliqués à la scène déjà dessinée (les notes et l'interface restent fixes)."""
    z = 1.0
    t0, amount, ms = fx["zoom_punch"]
    if now - t0 < ms:
        z += amount * (1 - (now - t0) / ms) ** 2
    every, tb, amount = fx["beat"]
    if every > 0 and tb:
        length = game.beat_length(game.song_time) * .85
        p = (now - tb) / length
        if p < 1:
            z += amount * (1 - p) ** 2
    s0, power, sms = fx["shake"]
    dx = dy = 0
    if now - s0 < sms:
        decay = (1 - (now - s0) / sms) ** 2
        dx, dy = power * decay * math.sin(now * .09), power * decay * math.cos(now * .113)
        z = max(z, 1.0 + power * .0022 * decay + .01)
    if z > 1.0005 or dx or dy:
        layer = screen.copy()
        size = (round(W * z), round(H * z))
        scaled = pygame.transform.scale(layer, size) if z > 1.0005 else layer
        screen.fill((0, 0, 0))
        screen.blit(scaled, ((W - size[0]) // 2 + dx, (H - size[1]) // 2 + dy))


def _where(game, character):
    """Centre visuel du personnage à l'écran (et non son point de caméra, décalé par les cameraOffsets)."""
    return game.world_to_screen(character.x + character.center[0] * character.scale[0], character.y + character.center[1] * character.scale[1])


def _spotlight(game, screen, now):
    a = fx["spot"]
    if a < .01:
        return
    dark = pygame.Surface((W, H), pygame.SRCALPHA)
    dark.fill((4, 2, 14, round(205 * a)))
    for who in fx["spot_chars"]:
        character = game.opponent if who == 1 else game.player
        x, y = _where(game, character)
        cone = fx["cone"]
        dark.blit(cone, (round(x - cone.get_width() / 2), round(y + 190 - cone.get_height())), special_flags=pygame.BLEND_RGBA_SUB)
    screen.blit(dark, (0, 0))
    beams = pygame.Surface((W, H), pygame.SRCALPHA)
    for who in fx["spot_chars"]:
        character = game.opponent if who == 1 else game.player
        x, y = _where(game, character)
        cone = fx["beam"]
        beams.blit(cone, (round(x - cone.get_width() / 2), round(y + 190 - cone.get_height())))
    beams.set_alpha(round(255 * a))
    screen.blit(beams, (0, 0))
    _smoke(screen, now, .55 * a)


def _smoke(screen, now, strength):
    for puff in fx["smoke"]:
        puff[0] += puff[2] * .016
        if puff[0] > W + 100:
            puff[0] = -fx["smoke_imgs"][puff[3]].get_width()
        if puff[0] < -fx["smoke_imgs"][puff[3]].get_width() - 100:
            puff[0] = W
        if not fx["smoke_imgs"]:
            return
        # Transparence « cuite » dans une copie (par paliers de 16, créées au besoin) : 7 fois plus rapide à dessiner que set_alpha.
        level = round(255 * strength * (.55 + .45 * math.sin(now / 1400 + puff[4])) / 16) * 16
        if level <= 0:
            continue
        key = (puff[3], min(255, level))
        img = fx.setdefault("smoke_faded", {}).get(key)
        if img is None:
            img = fx["smoke_imgs"][puff[3]].copy()
            img.fill((255, 255, 255, key[1]), special_flags=pygame.BLEND_RGBA_MULT)
            fx["smoke_faded"][key] = img
        screen.blit(img, (round(puff[0]), round(puff[1] - 80)))


def _rain(screen, now):
    level = fx["rain"]
    if not level:
        return
    layer = fx.get("rain_layer")
    if layer is None:  # une seule image plein écran, vidée à chaque image (au lieu d'en créer une)
        layer = fx["rain_layer"] = pygame.Surface((W, H), pygame.SRCALPHA)
    layer.fill((0, 0, 0, 0))
    count = 150 if level == 1 else 320
    for drop in fx["drops"][:count]:
        drop[0] -= drop[2] * .016 * .22
        drop[1] += drop[2] * .016
        if drop[1] > H or drop[0] < -40:
            drop[0], drop[1] = fx["rng"].uniform(0, W + 260), -30
        pygame.draw.line(layer, (170, 190, 255, 70 if level == 1 else 95), (drop[0], drop[1]), (drop[0] - drop[3] * .22, drop[1] + drop[3]), 1)
    screen.blit(layer, (0, 0))


def _pumpkin_glow(game, screen, now):
    glow = fx["glow"]
    flicker = .55 + .25 * math.sin(now / 130) + .15 * math.sin(now / 53) + .05 * math.sin(now / 27)
    for name in ("pumpkinsLeft", "pumpkinsRight"):
        prop = game.stage.props.get(name)
        if prop is None:
            continue
        x, y = game.world_to_screen(prop.x, prop.y, prop.scroll)
        cx, cy = x + prop.surface.get_width() * .38, y + prop.surface.get_height() * .66
        level = max(0, min(31, round(flicker * 31)))  # 32 intensités préparées une fois
        g = fx.setdefault("glow_levels", {}).get(level)
        if g is None:
            g = glow.copy()
            g.fill((round(255 * level / 31),) * 3, special_flags=pygame.BLEND_RGB_MULT)
            fx["glow_levels"][level] = g
        screen.blit(g, (round(cx - 150), round(cy - 150)), special_flags=pygame.BLEND_RGB_ADD)
    for e in fx["ember"]:
        e[1] -= e[2] * .016
        e[0] += math.sin(now / 900 + e[4]) * .6
        if e[1] < -10:
            e[0], e[1] = fx["rng"].uniform(0, W), H + 10
        pygame.draw.circle(screen, (255, 150 + round(60 * math.sin(now / 200 + e[4])), 40), (round(e[0]), round(e[1])), round(e[3]))


def on_draw_stage(game, screen):
    if not mine(game):
        return
    now = pygame.time.get_ticks()
    _stage_layer(game, screen, now)
    _pumpkin_glow(game, screen, now)
    _smoke(screen, now, .22)
    _spotlight(game, screen, now)
    _rain(screen, now)
    color, alpha = _tint_now(now)
    if alpha > .5:
        veil = fx.get("veil")
        if veil is None:
            veil = fx["veil"] = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((*[round(c) for c in color], round(alpha)))
        screen.blit(veil, (0, 0))


def on_draw(game, screen):
    if not mine(game):
        return
    now = pygame.time.get_ticks()
    t0, duration, color, peak = fx["flash"]
    age = now - t0
    if age < duration:
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        layer.fill((*color, round(peak * (1 - age / duration))))
        screen.blit(layer, (0, 0))
    _title(game, screen)


def _fade(img, a):
    img = img.copy()
    img.set_alpha(round(255 * max(0.0, min(1.0, a))))
    return img


def _title(game, screen):
    """Carte de titre sobre dans la police des menus de FNF (alphabet) : nom de la chanson, puis la semaine en plus petit."""
    t = game.song_time
    if not -1500 <= t < 3400:
        return
    a = min(1.0, (t + 1500) / 400, (3400 - t) / 600)
    name = _fade(game.app.alphabet(game.song.name.upper(), 96), a)
    week = _fade(game.app.alphabet("HALLOWEEN NIGHT", 40), a)
    screen.blit(name, name.get_rect(center=(W // 2, 290)))
    screen.blit(week, week.get_rect(center=(W // 2, 372)))
