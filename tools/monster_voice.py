"""Voix chantee de Lemon Monster : echantillonneur chromatique construit avec de VRAIS extraits de Monster qui chante
(fnf_assets/songs/monster + winter-horrorland, Voices-monster.ogg). Une syllabe tenue par note, recalee en hauteur par
reechantillonnage (au plus quelques demi-tons : timbre et formants restent ceux de Monster)."""
import os
import numpy as np
import librosa
import vox_extract as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 44100
FILES = [os.path.join(ROOT, 'fnf_assets', 'songs', n, 'Voices-monster.ogg') for n in ('monster', 'winter-horrorland')]
_cache = {}


def bank():
    """-> liste de (f0_hz, signal 44.1 kHz normalise) : syllabes a hauteur stable, nettes, de 250 ms a 1,5 s."""
    if 'b' in _cache:
        return _cache['b']
    out = []
    for path in FILES:
        x = V.load(path)                                  # 22 kHz : detection des syllabes
        full, _ = librosa.load(path, sr=SR, mono=True)    # 44.1 kHz : le son garde ses aigus
        segs = [s for s in V.segments(x, min_ms=250, fmin=75, fmax=420, tol=.9) if s[1] - s[0] < 1.5]
        floor = np.percentile([s[3] for s in segs], 35)
        for a, b, f0, rms in segs:
            if rms < floor:
                continue
            seg = full[int(max(0, a - .01) * SR):int(b * SR)].astype(float)
            seg = seg - seg.mean()
            out.append((f0, seg / (np.sqrt((seg ** 2).mean()) + 1e-9) * .1))
    _cache['b'] = out
    return out


def _sustain(x, need):
    """Prolonge une syllabe en rebouclant sa partie centrale avec un fondu enchaine."""
    a, b = int(len(x) * .35), int(len(x) * .8)
    seg, fx = x[a:b], int(.05 * SR)
    out = x[:b].copy()
    while len(out) < need:
        w = np.linspace(0, 1, fx)
        out[-fx:] = out[-fx:] * (1 - w) + seg[:fx] * w
        out = np.concatenate([out, seg[fx:]])
    return out


def sing(notes, n_samples, shift_semitones=0.):
    """notes = [(t_ms, len_ms, hz_cible)] -> piste mono. Chaque note = une syllabe reelle de Monster, la plus proche en hauteur,
    jamais deux fois de suite la meme."""
    bk = bank()
    freqs = np.array([f for f, _ in bk])
    buf = np.zeros(n_samples)
    recent = []
    for t, ln, hz in notes:
        hz = hz * 2 ** (shift_semitones / 12)
        cost = np.abs(12 * np.log2(freqs / hz))
        cost[[i for i in recent if i < len(cost)]] += 1.5
        i = int(cost.argmin())
        recent = (recent + [i])[-6:]
        f0, x = bk[i]
        ratio = hz / f0
        y = np.interp(np.arange(0, len(x) - 1, ratio), np.arange(len(x)), x)
        need = int(ln * SR / 1000)
        if len(y) < need:
            y = _sustain(y, need)
        y = y[:need].copy()
        fi = min(len(y), int(.008 * SR))
        fo = min(len(y), int(max(.03, min(.08, ln / 1000 * .3)) * SR))
        y[:fi] *= np.linspace(0, 1, fi)
        y[-fo:] *= np.linspace(1, 0, fo)
        s = int(t * SR / 1000)
        e = min(n_samples, s + len(y))
        if e > s >= 0:
            buf[s:e] += y[:e - s]
    return buf


if __name__ == '__main__':  # auto-test : une gamme chantee, hauteur mesuree = hauteur demandee (a 0,7 demi-ton pres : une vraie voix bouge)
    for k, hz in enumerate((130.8, 155.6, 196.0)):
        y = sing([(0, 900, hz)], SR)
        f0 = librosa.yin(y[2000:30000].astype(np.float32), fmin=60, fmax=500, sr=SR)
        got = float(np.median(f0))
        assert abs(12 * np.log2(got / hz)) < .7, (hz, got)
    print('ok', len(bank()), 'syllabes')
