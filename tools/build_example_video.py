"""Fabrique la cinematique video du mod (videos/cobweb-cadence.mp4 et cobweb... -end) en rendant le VRAI decor du jeu,
image par image, avec les scripts du mod (pluie, brume, lueur des citrouilles, eclairs). Camera lente, sans secousse.

python tools/build_example_mod.py      (le zip doit exister : le jeu charge le mod depuis mods/)
python tools/build_example_video.py
"""
import os, subprocess, sys, tempfile
import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="fnfvid_")
os.environ["APPDATA"] = TMP
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, ROOT)
import pygame
clock = [100000]
pygame.time.get_ticks = lambda: clock[0]
import main
from pyfnf import game

game.PlayState._prepare_audio = lambda self: None
FPS, SECONDS = 24, 7.0
OUT = os.path.join(ROOT, "mods_src", "ExampleMod", "videos")
SR = 44100


def audio(path):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import build_example_song as bs
    K = bs.Kit()
    buf = np.zeros((round(SR * SECONDS), 2))
    bs.place(buf, K.toll, 100, .5, gate_ms=5000)
    for t, g in ((600, .8), (2300, .7), (4500, .9)):
        bs.place(buf, K.thunder, t, g)
    root, tri = bs.chord_notes("Dm")
    for i, n in enumerate(tri):
        bs.place(buf, K.choir.note(n, 7 * SR), 800, .28, gate_ms=6000, pan=(-.4, 0, .4)[i], rel_ms=700)
        bs.place(buf, K.organ.note(n - 12, 7 * SR), 800, .2, gate_ms=6000, rel_ms=700)
    fade = np.minimum(1, np.minimum(np.arange(len(buf)) / (SR * .3), (len(buf) - np.arange(len(buf))) / (SR * .6)))
    buf *= fade[:, None] * .9 / max(1e-9, np.abs(buf).max())
    sf.write(path, buf.astype(np.float32), SR)


# Plans : (instant, x, y) ; entre deux points, interpolation « smootherstep » (vitesse ET acceleration nulles aux extremites : aucune secousse).
KEYS = [(0.0, 470, 560), (1.9, 520, 540), (2.6, 700, 480), (4.1, 740, 500), (4.8, 900, 560), (7.0, 930, 545)]


def camera(t):
    for (t0, x0, y0), (t1, x1, y1) in zip(KEYS, KEYS[1:]):
        if t0 <= t <= t1:
            p = (t - t0) / (t1 - t0)
            e = p ** 3 * (p * (6 * p - 15) + 10)
            return x0 + (x1 - x0) * e, y0 + (y1 - y0) * e
    return KEYS[-1][1:]


def main_():
    app = game.FunkinApp(main.resource_root())
    app.start_playlist(["cobweb-cadence"], "hard")
    st = app.state
    st.overlays.clear()
    st.hold_countdown = True
    title = pygame.image.load(os.path.join(ROOT, "mods_src", "ExampleMod", "images", "storymenu", "titles", "halloween-night.png")).convert_alpha()
    title = pygame.transform.smoothscale(title, (760, round(900 * title.get_height() / title.get_width())))
    shade = title.copy(); shade.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)
    os.makedirs(OUT, exist_ok=True)
    silent = os.path.join(TMP, "silent.mp4")
    import av
    container = av.open(silent, "w")
    stream = container.add_stream("libx264", rate=FPS)
    stream.width, stream.height, stream.pix_fmt = 1280, 720, "yuv420p"
    stream.options = {"crf": "24", "preset": "medium"}
    events = {0.6: "Lightning", 2.3: "Lightning", 4.5: "Lightning"}
    st.run_event({"t": 0, "e": "Rain", "v": {"level": 2}})
    st.run_event({"t": 0, "e": "Tint", "v": {"color": [60, 90, 255], "alpha": 55, "ms": 1}})
    done = set()
    sing_lane = [0]
    for frame_i in range(round(FPS * SECONDS)):
        t = frame_i / FPS
        clock[0] += round(1000 / FPS)
        for at, name in events.items():
            if t >= at and at not in done:
                done.add(at); st.run_event({"t": 0, "e": name, "v": {}})
        if frame_i % 12 == 0:
            st.stage.beat(frame_i // 12, clock[0], 150)
        st.cam[0], st.cam[1] = camera(t)
        if frame_i % 12 == 6 and t < 2.3:
            st.opponent.sing(sing_lane[0] % 4, clock[0]); sing_lane[0] += 1       # Skid & Pump chantent dans le premier plan
        if t >= 2.8 and "gf" not in done and st.girlfriend:
            done.add("gf"); st.girlfriend.play_special("cheer", clock[0])
        if t >= 5.0 and "hey" not in done:
            done.add("hey"); st.player.play_special("hey", clock[0])
        st.scripts.call("on_update", st, 1 / FPS)
        screen = app.screen
        screen.fill((0, 0, 0))
        st.stage.draw(screen, st.cam, clock[0])
        st.scripts.call("on_draw_stage", st, screen)
        # fondu d'entree/sortie + titre
        vignette = pygame.Surface((1280, 720), pygame.SRCALPHA)
        vignette.fill((0, 0, 0, 70))
        screen.blit(vignette, (0, 0))
        if 4.7 < t < 6.8:
            a = min(1.0, (t - 4.7) / .4, (6.8 - t) / .4)
            title.set_alpha(round(255 * max(0, a))); shade.set_alpha(round(190 * max(0, a)))
            for dx, dy in ((-3, 0), (3, 0), (0, 3), (0, -3), (0, 0), (4, 4)):          # fond sombre : le contour reste lisible
                screen.blit(shade, shade.get_rect(center=(640 + dx, 300 + dy)))
            screen.blit(title, title.get_rect(center=(640, 300)))
        black = max(0.0, 1 - t / .4, (t - (SECONDS - .5)) / .5)
        if black > 0:
            veil = pygame.Surface((1280, 720)); veil.set_alpha(round(255 * min(1, black))); screen.blit(veil, (0, 0))
        img = av.VideoFrame.from_ndarray(np.transpose(pygame.surfarray.array3d(screen), (1, 0, 2)).copy(), format="rgb24")
        for packet in stream.encode(img):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    wav = os.path.join(TMP, "a.wav")
    audio(wav)
    final = os.path.join(OUT, "cobweb-cadence.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", silent, "-i", wav, "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", final], check=True)
    subs = {"en": [[.3, 2.1, "The old mansion never sleeps on Halloween night..."], [2.3, 4.3, "Thunder, candles, and a creeper with a microphone."],
                   [4.5, 6.8, "Let the cobwebs sing."]],
            "fr": [[.3, 2.1, "Le vieux manoir ne dort jamais la nuit d'Halloween..."], [2.3, 4.3, "Du tonnerre, des bougies, et un creeper avec un micro."],
                   [4.5, 6.8, "Que les toiles d’araignée chantent."]]}
    import json
    json.dump(subs, open(os.path.join(OUT, "cobweb-cadence.subs.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("ok", final, round(os.path.getsize(final) / 1e6, 2), "Mo")
    pygame.image.save(app.screen, os.path.join(ROOT, "Leaks", "v2_mod_cinematique_image.png"))


if __name__ == "__main__":
    main_()
