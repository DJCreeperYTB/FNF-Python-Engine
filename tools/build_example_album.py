"""Pochette d'album du mod d'exemple pour le freeplay : images/freeplay/albumRoll/halloween-night.png (+ titre -text).

Rendue avec le vrai décor du mod (moteur en headless), puis recadrée et titrée avec la police alphabet de FNF.
Run: python tools/build_example_album.py   (puis python tools/build_example_mod.py)
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="pyfnf_album_")  # jamais les réglages du joueur
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

clock = [100000]
pygame.time.get_ticks = lambda: clock[0]

import main  # noqa: E402
from pyfnf import game  # noqa: E402

OUT = os.path.join(ROOT, "mods_src", "ExampleMod", "images", "freeplay", "albumRoll")
SIZE = 262  # taille des pochettes officielles (volume1.png...)


def render_stage(app) -> pygame.Surface:
    game.PlayState._prepare_audio = lambda self: None
    app.start_playlist(["cobweb-cadence"], "hard")
    play = app.state
    play.focus_camera(2, instant=True)
    for _ in range(40):
        clock[0] += 16
        play.stage.beat(0, clock[0], 120)
    screen = pygame.Surface((1280, 720))
    play.stage.zoom = .6  # plan large : Spooky Kids, GF et DJCreeper devant le manoir
    play.stage.draw(screen, play.cam, clock[0])
    return screen


def main_build() -> None:
    os.makedirs(OUT, exist_ok=True)
    app = game.FunkinApp(main.resource_root())
    shot = render_stage(app)
    square = shot.subsurface(pygame.Rect(250, 0, 720, 720)).copy()
    art = pygame.transform.smoothscale(square, (SIZE, SIZE))
    # Ambiance : voile orange-violet, vignette, bordure noire épaisse comme les pochettes FNF.
    tint = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    for y in range(SIZE):
        mix = y / SIZE
        pygame.draw.line(tint, (round(90 + 140 * mix), round(30 + 60 * mix), round(120 - 90 * mix), 95), (0, y), (SIZE, y))
    art.blit(tint, (0, 0))
    logo = app.alphabet("HALLOWEEN", 46)
    logo = pygame.transform.rotozoom(logo, 6, min(1.0, (SIZE - 30) / logo.get_width()))
    art.blit(logo, logo.get_rect(center=(SIZE // 2, 40)))
    night = pygame.transform.rotozoom(app.alphabet("NIGHT", 40), 6, 1.0)
    art.blit(night, night.get_rect(center=(SIZE // 2 + 40, SIZE - 36)))
    pygame.draw.rect(art, (0, 0, 0), art.get_rect(), 8)
    pygame.image.save(art, os.path.join(OUT, "halloween-night.png"))
    # Titre sous la pochette (sprite Sparrow « idle », comme volume1-text).
    title = app.alphabet("HALLOWEEN NIGHT", 26)
    pygame.image.save(title, os.path.join(OUT, "halloween-night-text.png"))
    w, h = title.get_size()
    with open(os.path.join(OUT, "halloween-night-text.xml"), "w", encoding="utf-8") as xml:
        xml.write(f'<?xml version="1.0" encoding="utf-8"?>\n<TextureAtlas imagePath="halloween-night-text.png">\n'
                  f'  <SubTexture name="idle0000" x="0" y="0" width="{w}" height="{h}"/>\n</TextureAtlas>\n')
    print("ok", OUT)


if __name__ == "__main__":
    main_build()
