"""Regénère les images des pages wiki/, gamebanana/ et GitHub/ (headless, sans fenêtre).

    python -I tools/build_store_pages.py                   # tout (captures puis montage)
    python -I tools/build_store_pages.py shoot             # seulement les captures brutes -> tools/_store_raw/
    python -I tools/build_store_pages.py shoot mod_light   # certaines scènes seulement
    python -I tools/build_store_pages.py compose           # seulement le montage depuis les captures brutes

Ne touche jamais au vrai %APPDATA% : le jeu tourne avec un APPDATA à part (tools/_store_appdata).
"""
import os, sys, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "tools" / "_store_raw"
ARGS = sys.argv[1:]
MODE = ARGS[0] if ARGS and ARGS[0] in ("shoot", "compose", "all") else "all"
ONLY = [a for a in ARGS if a not in ("shoot", "compose", "all")]

SCENES = ["title", "main", "story", "freeplay", "freeplay_mods", "options", "trophies", "mods", "tools",
          "chart_editor", "play", "play_mods", "week7", "dialogue", "video", "mod_freeplay", "mod_story",
          "mod_dialogue", "mod_spot", "mod_light", "mod_nightmare", "mod_middle"]


def shoot():
    os.environ["APPDATA"] = str(ROOT / "tools" / "_store_appdata")
    os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
    sys.path.insert(0, str(ROOT))
    import pygame
    clock = [100000]
    pygame.time.get_ticks = lambda: clock[0]
    import main
    from pyfnf import game, menus, dialogue, editors
    # Le temps de la chanson suit l'horloge simulée (sinon il se cale sur la vraie lecture du son : des minutes par capture).
    game.PlayState.start_audio = lambda self: (setattr(self, "audio_started_at", clock[0]), setattr(self, "song_time", 0),
                                               setattr(self, "song_started", True))
    RAW.mkdir(exist_ok=True)
    app = game.FunkinApp(main.resource_root())
    app.settings.language = "en"
    app.settings.achievements = []

    def save(name):
        app.state.draw(app.screen); app.draw_toasts(app.screen); app.draw_volume_tray(app.screen)
        pygame.image.save(app.screen, str(RAW / f"{name}.png")); print("ok", name, flush=True)

    def tick(ms):
        for _ in range(ms // 16):
            clock[0] += 16; app.state.update(.016)

    def key(k, up=False, unicode=""):
        app.state.event(pygame.event.Event(pygame.KEYUP if up else pygame.KEYDOWN, key=k, mod=0, unicode=unicode))

    def bot_play(st, until):
        release = {}
        while st.chart_time < until and not getattr(st, "finished", False):  # mort ou fin : on s'arrête au lieu de tourner sans fin
            clock[0] += 16
            for n in st.notes:
                if n.player and n.state == "pending" and not getattr(n, "avoid", False) and n.time <= st.chart_time + 5:
                    st.key_down[n.lane] = True; st.hit_lane(n.lane); release[n.lane] = n.time + n.length + 30
                elif n.time > st.chart_time + 50: break
            for lane, t in list(release.items()):
                if st.chart_time > t: st.key_down[lane] = False; del release[lane]
            st.update(.016)

    def week_index(name):
        return next(i for i, w in enumerate(app.data.weeks) if name.lower() in repr(vars(w) if hasattr(w, "__dict__") else w).lower())

    game.PlayState.start_audio = lambda self: (setattr(self, "audio_started_at", clock[0]), setattr(self, "song_time", 0), setattr(self, "song_started", True))

    def run(scene):
        app.toasts = []; app.tray_at = -10 ** 9; app.story_week = None
        if scene == "title":
            app.change(menus.TitleState(app)); tick(2500); save(scene)
        elif scene == "main":
            app.change(menus.MainMenuState(app)); tick(300); key(pygame.K_DOWN); key(pygame.K_DOWN); tick(1500); save(scene)
        elif scene == "story":
            app.change(menus.StoryMenuState(app, 0)); tick(1500); save(scene)
        elif scene == "freeplay":
            app.change(menus.FreeplayState(app, "bopeebo")); tick(1500); save(scene)
        elif scene == "freeplay_mods":
            app.change(menus.FreeplayState(app, "bopeebo")); tick(300); key(pygame.K_LCTRL); tick(200)
            key(pygame.K_DOWN); key(pygame.K_RIGHT); key(pygame.K_RIGHT); key(pygame.K_DOWN); key(pygame.K_RETURN)
            for _ in range(4): key(pygame.K_DOWN)
            key(pygame.K_RETURN); tick(400); save(scene)
            key(pygame.K_r); key(pygame.K_LCTRL); tick(300)
        elif scene == "options":
            app.change(menus.OptionsState(app)); tick(400)
            for _ in range(3): key(pygame.K_DOWN)
            tick(400); save(scene)
        elif scene == "trophies":
            app.settings.achievements = [a.id for a in app.achievements[:5]]
            app.change(menus.AchievementsState(app)); tick(600); save(scene)
            app.settings.achievements = []
        elif scene == "mods":
            app.change(menus.ModsState(app)); tick(600); save(scene)
        elif scene == "tools":
            app.change(editors.ToolsState(app)); tick(600); save(scene)
        elif scene == "chart_editor":
            app.change(editors.ChartEditorState(app, "bopeebo", "hard", 30000)); tick(600); save(scene)
        elif scene == "play":
            app.start_playlist(["bopeebo"], "hard"); st = app.state
            bot_play(st, 12000); app.unlock(app.achievements[0].id); app.tray_at = clock[0]
            clock[0] += 700; st.update(.016); save(scene); app.settings.achievements = []
        elif scene == "play_mods":
            app.modifiers = {"opponent": True, "rate": 1.25, "botplay": True}
            app.start_playlist(["bopeebo"], "hard"); st = app.state
            bot_play(st, 15000); save(scene); app.modifiers = {}
        elif scene == "week7":
            app.start_playlist(["ugh"], "hard", 6); st = app.state
            bot_play(st, 20000); save(scene)
        elif scene == "dialogue":
            app.start_playlist(["senpai"], "hard", 6); tick(2500); save(scene)
        elif scene == "video":
            app.change(menus.MainMenuState(app))
            v = dialogue.Video(app, app.assets.path("videos/ughCutscene.mkv"))
            class Holder(game.BaseState):
                def draw(self, screen): v.draw(screen)
            app.change(Holder(app)); v.started = clock[0] - 6500; v.update(.016)
            v.hold_started = clock[0] - 500; save(scene)
        elif scene == "mod_freeplay":
            app.change(menus.FreeplayState(app, "cobweb-cadence")); tick(1800); save(scene)
        elif scene == "mod_story":
            app.change(menus.StoryMenuState(app, week_index("halloween"))); tick(2000); save(scene)
        elif scene == "mod_dialogue":
            app.start_playlist(["cobweb-cadence"], "hard", week_index("halloween")); st = app.state
            st.overlays = [o for o in st.overlays if o[0] != "video"]  # le dialogue, pas la vidéo
            tick(4000); save(scene)
        elif scene == "mod_spot":
            app.start_playlist(["cobweb-cadence"], "hard"); st = app.state
            bot_play(st, 25500); tick(600); save(scene)
        elif scene == "mod_light":
            app.start_playlist(["cobweb-cadence"], "hard"); st = app.state
            bot_play(st, 3870 + 110); save(scene)
        elif scene == "mod_nightmare":
            app.start_playlist(["pumpkin-moon-panic"], "nightmare:erect"); st = app.state
            bot_play(st, 49000); save(scene)
        elif scene == "mod_middle":
            app.start_playlist(["pumpkin-moon-panic"], "hard"); st = app.state
            bot_play(st, 61500); save(scene)

    app.halloween_seen = {"notes"}  # encart des notes spéciales déjà vu : sinon il attend Entrée et la chanson ne démarre jamais
    for scene in (ONLY or SCENES):
        try: run(scene)
        except Exception: traceback.print_exc(limit=6)


def compose():
    from PIL import Image, ImageDraw, ImageFont
    for d in ("wiki", "gamebanana", "GitHub/images"): (ROOT / d).mkdir(parents=True, exist_ok=True)
    leaks = ROOT / "Leaks"; leaks.mkdir(exist_ok=True)

    def have(n): return (RAW / f"{n}.png").exists()
    def load(n): return Image.open(RAW / f"{n}.png").convert("RGB")

    def put(folder, name, im, size=None, leak=False):
        if size: im = im.resize(size, Image.LANCZOS)
        im.save(ROOT / folder / name); print("->", folder, name)
        if leak: im.save(leaks / ("v2_pages_" + name.replace(" ", "_")))

    gb = [("01_main_menu", "main"), ("02_freeplay_album", "freeplay"), ("03_modifiers", "freeplay_mods"),
          ("04_week7_gameplay", "week7"), ("05_week6_dialogue", "dialogue"), ("06_chart_editor", "chart_editor"),
          ("07_halloween_spotlight", "mod_spot"), ("08_halloween_lightning", "mod_light"),
          ("09_trophies", "trophies"), ("10_options", "options"), ("11_mods_menu", "mods"), ("12_halloween_week", "mod_story")]
    for out, src in gb:
        if have(src): put("gamebanana", out + ".png", load(src), (1920, 1080), leak=True)
    if have("week7"):
        base = load("week7").resize((1920, 1080), Image.LANCZOS)
        d = ImageDraw.Draw(base)
        try:
            f1 = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 150); f2 = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 54)
        except OSError:
            f1 = f2 = ImageFont.load_default()
        d.rectangle((0, 770, 1920, 1080), fill=(0, 0, 0))
        d.text((960, 855), "FNF PYTHON ENGINE", font=f1, fill=(255, 255, 255), anchor="mm")
        d.text((960, 990), "Mods  |  Chart editor  |  Trophies  |  Halloween Night example mod", font=f2, fill=(255, 190, 70), anchor="mm")
        put("gamebanana", "00_header_1920x1080.png", base, leak=True)
        put("gamebanana", "thumbnail_800x450.png", base, (800, 450))
    wiki = [("FNF Python Engine Main Menu.png", "main"), ("FNF Python Engine Freeplay.png", "freeplay"),
            ("FNF Python Engine Modifiers.png", "freeplay_mods"), ("FNF Python Engine Week 7.png", "week7"),
            ("FNF Python Engine Dialogue.png", "dialogue"), ("FNF Python Engine Chart Editor.png", "chart_editor"),
            ("FNF Python Engine Halloween Night Spotlight.png", "mod_spot"), ("FNF Python Engine Halloween Night Lightning.png", "mod_light"),
            ("FNF Python Engine Halloween Night Freeplay.png", "mod_freeplay"), ("FNF Python Engine Trophies.png", "trophies"),
            ("FNF Python Engine Options.png", "options"), ("FNF Python Engine Halloween Night Week.png", "mod_story")]
    for out, src in wiki:
        if have(src): put("wiki", out, load(src))
    import shutil
    for song in ("cobweb-cadence", "midnight-candlewick", "pumpkin-moon-panic"):  # extraits audio du mod pour le wiki
        for suffix, label in (("", ""), ("_nightmare", " Nightmare")):
            src = leaks / f"v2_mod_{song}{suffix}.mp3"
            if src.exists(): shutil.copy(src, ROOT / "wiki" / f"FNF Python Engine {song.replace('-', ' ').title()}{label}.mp3")
    icon = ROOT / "mods_src" / "ExampleMod" / "images" / "icons" / "icon-djcreeper.png"
    if icon.exists(): shutil.copy(icon, ROOT / "wiki" / "FNF Python Engine DJCreeper Icon.png")
    gh = [("banner.png", "mod_spot"), ("menu.png", "main"), ("freeplay.png", "freeplay"), ("modifiers.png", "freeplay_mods"),
          ("gameplay.png", "week7"), ("dialogue.png", "dialogue"), ("chart-editor.png", "chart_editor"),
          ("example-mod.png", "mod_light"), ("trophies.png", "trophies"), ("options.png", "options")]
    for out, src in gh:
        if have(src): put("GitHub/images", out, load(src))


if MODE in ("shoot", "all"): shoot()
if MODE in ("compose", "all"): compose()
