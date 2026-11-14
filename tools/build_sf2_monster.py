"""Monster.sf2 : SoundFont de la voix de Lemon Monster avec le pipeline valide de DJCreeper (FNF DJCREEPER/tools/build_sf2.py) :
consonne + voyelle tenue de VRAIES syllabes chantees de Monster, hauteur aplatie par touche avec WORLD (formants conserves),
voyelle bouclee. Sources : fnf_assets/songs/monster + winter-horrorland (Voices-monster.ogg).
    python tools/build_sf2_monster.py --list      candidats (hauteur, formants, duree)
    python tools/build_sf2_monster.py             construit work/monster/Monster.sf2 (+ selftest)"""
import os, sys, json
import numpy as np, soundfile as sf, librosa
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DJC_TOOLS = r'C:\Users\DJCre\Documents\FNF DJCREEPER\tools'
sys.path.insert(0, DJC_TOOLS)
import build_sf2 as B

W = os.path.join(ROOT, 'work', 'monster')
os.makedirs(os.path.join(W, 'cache'), exist_ok=True)
SRC_FILES = {'M1': os.path.join(ROOT, 'fnf_assets', 'songs', 'monster', 'Voices-monster.ogg'),
             'M2': os.path.join(ROOT, 'fnf_assets', 'songs', 'winter-horrorland', 'Voices-monster.ogg')}
for k, p in SRC_FILES.items():           # wav mono 44,1 kHz (le pipeline lit les prises telles quelles)
    wav = os.path.join(W, f'{k}.wav')
    if not os.path.exists(wav):
        x, _ = librosa.load(p, sr=44100, mono=True)
        sf.write(wav, x, 44100)
B.SRC = {k: os.path.join(W, f'{k}.wav') for k in SRC_FILES}
B.CACHE = os.path.join(W, 'cache')
B.house_eq = lambda: np.zeros(1025)      # garde le timbre de Monster (pas d'egalisation vers Boyfriend)


def candidates(min_ms=150):
    """Notes tenues propres : f0 stable (+-0.35 demi-ton), voisees, niveau fort, formants F1/F2 mesures."""
    out = []
    for sid in B.SRC:
        f0, db = B.track(sid)
        y = B.take(sid)
        pk = np.percentile(db, 99.5)
        v = (f0 > 0) & (db > pk - 22)
        i, n = 0, len(f0)
        while i < n:
            if not v[i]:
                i += 1; continue
            j = i
            while j < n and v[j]:
                j += 1
            if j - i >= min_ms / B.FP:
                m = B.midi(np.maximum(f0[i:j], 1))
                med = np.array([np.median(m[max(0, k - 6):k + 7]) for k in range(len(m))])
                ok = np.abs(m - med) < 0.35
                best, cur = (0, 0), 0
                for k, o in enumerate(ok):
                    cur = cur + 1 if o and (cur == 0 or abs(m[k] - m[k - 1]) < 0.15) else (1 if o else 0)
                    if cur > best[1] - best[0]:
                        best = (k - cur + 1, k + 1)
                a, b = i + best[0], i + best[1]
                if (b - a) * B.FP >= min_ms:
                    seg = y[int(a * B.FP / 1000 * B.SR):int(b * B.FP / 1000 * B.SR)]
                    F1, F2 = B.formants(seg)
                    clip = np.mean(np.abs(y[int(i * B.FP / 1000 * B.SR):int(j * B.FP / 1000 * B.SR)]) > .97) * 100
                    out.append(dict(src=sid, i=i * B.FP / 1000, a=a * B.FP / 1000, b=b * B.FP / 1000, ms=(b - a) * B.FP,
                                    midi=float(np.median(m[best[0]:best[1]])), F1=F1, F2=F2, lvl=float(db[a:b].mean() - pk), clip=float(clip),
                                    flat=float(np.std(m[best[0]:best[1]]))))
            i = j
    return out


if __name__ == '__main__' and sys.argv[1:2] == ['--list']:
    c = candidates()
    c.sort(key=lambda d: d['F1'])
    for d in c:
        print(f"{d['src']} {d['a']:7.2f}-{d['b']:7.2f} {d['ms']:4.0f}ms midi={d['midi']:5.2f} ({B.hz(d['midi']):4.0f}Hz) F1={d['F1']:4.0f} F2={d['F2']:4.0f} lvl={d['lvl']:5.1f} clip={d['clip']:.1f} flat={d['flat']:.2f}")
    print(len(c))


def pick_tokens(n=10):
    """Une seule voyelle (F1 480-620, F2 1250-1700 : le « e/a » central de Monster), notes tenues plates >= 280 ms, fortes, sans ecretage,
    reparties sur toute la tessiture (39-58) : attaque naturelle = 30 premieres ms de la meme note."""
    c = [d for d in candidates(250) if 470 <= d['F1'] <= 640 and 1250 <= d['F2'] <= 1750 and d['flat'] <= .25 and d['lvl'] > -14 and d['clip'] < .1]
    chosen = []
    for target in np.linspace(41, 57, n):
        pool = [d for d in c if d not in chosen]
        chosen.append(min(pool, key=lambda d: abs(d['midi'] - target) + 4 * d['flat'] - .004 * d['ms']))
    return chosen


KEYS = range(38, 66)
B.KEYS = KEYS
B.SYLS = ['ah']
B.ROTATION = ['ah']
B.NAME = 'Monster'
B.OUT = os.path.join(W, 'Monster.sf2')
B.FLATTEN = True   # enveloppe de voyelle quasi statique : pas de pulsation dans la boucle


def set_tokens():
    toks = []
    for d in pick_tokens():
        a = round(d['a'], 3)
        toks.append(dict(on=(d['src'], a, a + .03), vow=(d['src'], a + .03, round(d['b'], 3))))
        print('token', d['src'], a, f"{d['ms']:.0f}ms", f"{B.hz(d['midi']):.0f}Hz F1={d['F1']:.0f} F2={d['F2']:.0f}")
    B.TOKENS = {'ah': toks}


if __name__ == '__main__' and sys.argv[1:2] != ['--list']:
    set_tokens()
    B.build(out=B.OUT, syls=B.SYLS, keys=KEYS)
    sys.exit(0 if B.selftest(B.OUT) else 1)
