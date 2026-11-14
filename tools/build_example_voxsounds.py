"""Sons de voix des dialogues du mod (data/dialogue/speakers/<id>.json -> "sounds") :
 - Skid & Pump : syllabes decoupees dans leurs vraies voix (fnf_assets/songs/spookeez/Voices-spooky.ogg)
 - Lemon Monster : idem dans fnf_assets/songs/monster/Voices-monster.ogg
 - DJCreeper : sons de dialogue de VS DJCreeper (SoundFont DJCreeper.sf2) copies tels quels.
python tools/build_example_voxsounds.py"""
import os, shutil, sys
import numpy as np
import soundfile as sf
import librosa
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vox_extract as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'mods_src', 'ExampleMod', 'sounds', 'dialogue')
DJC = r'C:\Users\DJCre\Documents\FNF DJCREEPER\vs-djcreeper\sounds\dialogue'
os.makedirs(OUT, exist_ok=True)


def blip(x, start, ms=150):
    a = int((start + .03) * V.SR)
    y = x[a:a + int(ms / 1000 * V.SR)].copy()
    n = len(y)
    f_in, f_out = int(.006 * V.SR), int(.05 * V.SR)
    y[:f_in] *= np.linspace(0, 1, f_in)
    y[-f_out:] *= np.linspace(1, 0, f_out)
    return .6 * y / (np.abs(y).max() + 1e-9)


def pick(path, name, lo, hi, count=6, ms=150):
    x = V.load(path)
    segs = [s for s in V.segments(x, min_ms=ms + 80) if lo <= s[2] <= hi]
    segs.sort(key=lambda s: s[2])                           # etale sur toute la hauteur disponible : voix variee
    chosen = [segs[round(i * (len(segs) - 1) / (count - 1))] for i in range(count)]
    for i, s in enumerate(chosen, 1):
        sf.write(os.path.join(OUT, f'{name}-{i}.ogg'), blip(x, s[0], ms), V.SR, format='OGG', subtype='VORBIS')
    print(name, [round(s[2]) for s in chosen], flush=True)


pick(os.path.join(ROOT, 'fnf_assets', 'songs', 'spookeez', 'Voices-spooky.ogg'), 'spooky', 200, 700, 6, 130)
pick(os.path.join(ROOT, 'fnf_assets', 'songs', 'monster', 'Voices-monster.ogg'), 'monster', 110, 230, 6, 170)
for i in (1, 3, 5, 7, 9, 11):
    shutil.copy2(os.path.join(DJC, f'djcreeper-{i}.ogg'), os.path.join(OUT, f'djc-{(i + 1) // 2}.ogg'))
