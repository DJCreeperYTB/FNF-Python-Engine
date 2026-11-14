"""Met les chansons du mod d'exemple au volume des chansons officielles (point 80 du suivi).

Mesure le volume perçu (LUFS intégré, ffmpeg ebur128) du mélange Inst + Voix, applique le même gain à chaque piste
pour atteindre TARGET_LUFS, puis un limiteur commun (calculé sur le mélange) garde les crêtes sous CEILING_DB.
    python tools/normalize_mod_audio.py [cobweb-cadence ...]
Les chansons officielles (Bopeebo, Spookeez, Monster, Darnell, Senpai) mesurent entre -12,2 et -9,2 LUFS : moyenne -11.
"""
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf
from scipy.ndimage import maximum_filter1d
from scipy.signal import lfilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONGS = os.path.join(ROOT, "mods_src", "ExampleMod", "songs")
LEAKS = os.path.join(ROOT, "Leaks")
TARGET_LUFS = -11.0
CEILING_DB = -1.0


def lufs(audio, rate):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "mix.wav")
        sf.write(path, audio, rate)
        out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", out)[-1])


def limiter_gain(mix, rate, ceiling):
    """Gain (<= 1) par échantillon : crêtes du mélange sous le plafond, attaque anticipée 5 ms, relâchement ~150 ms."""
    need = np.maximum(1.0, np.abs(mix).max(axis=1) / ceiling)
    held = maximum_filter1d(need, size=int(rate * .005) * 2 + 1)  # voit la crête 5 ms avant
    a = np.exp(-1 / (rate * .15))
    smooth = lfilter([1 - a], [1, -a], held)
    return 1 / np.maximum(held, smooth)


def encode(audio, rate, path, extra):
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "x.wav")
        sf.write(wav, audio, rate, subtype="FLOAT")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, *extra, path], check=True)


def normalize(song, suffix):
    folder = os.path.join(SONGS, song)
    stems = sorted(f for f in os.listdir(folder) if f.endswith(f"{suffix}.ogg") and (suffix or "-erect" not in f))
    tracks = {name: sf.read(os.path.join(folder, name), always_2d=True) for name in stems}
    rate = next(iter(tracks.values()))[1]
    length = min(len(data) for data, _ in tracks.values())
    audio = {name: data[:length].astype(np.float64) for name, (data, _) in tracks.items()}
    mix = sum(audio.values())
    before = lufs(mix, rate)
    gain = 10 ** ((TARGET_LUFS - before) / 20)
    limit = limiter_gain(mix * gain, rate, 10 ** (CEILING_DB / 20))[:, None]
    audio = {name: data * gain * limit for name, data in audio.items()}
    mix = sum(audio.values())
    after, peak = lufs(mix, rate), 20 * np.log10(np.abs(mix).max())
    assert peak <= CEILING_DB + .05, (song, suffix, peak)
    for name, data in audio.items():
        encode(data, rate, os.path.join(folder, name), ["-c:a", "libvorbis", "-q:a", "3"])
    leak = os.path.join(LEAKS, f"v2_mod_{song}{'_nightmare' if suffix else ''}.mp3")
    encode(mix, rate, leak, ["-b:a", "160k"])
    print(f"{song}{suffix or ''} : {before:.1f} -> {after:.1f} LUFS, crête {peak:.1f} dBFS", flush=True)


if __name__ == "__main__":
    for song in sys.argv[1:] or sorted(os.listdir(SONGS)):
        for suffix in ("", "-erect"):
            normalize(song, suffix)
