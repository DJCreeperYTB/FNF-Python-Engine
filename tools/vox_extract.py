"""Decoupe de vraies voix FNF en syllabes chantees : segments a hauteur stable (yin + energie)."""
import numpy as np
import librosa

SR = 22050
HOP = 256


def load(path):
    x, _ = librosa.load(path, sr=SR, mono=True)
    return x


def segments(x, min_ms=200, fmin=70, fmax=700, tol=1.2):
    """-> [(debut_s, fin_s, f0_median_hz, rms)] : zones voisees ou la hauteur reste dans +-tol demi-tons de la mediane glissante."""
    f0 = librosa.yin(x, fmin=fmin, fmax=fmax, sr=SR, frame_length=2048, hop_length=HOP)
    rms = librosa.feature.rms(y=x, frame_length=2048, hop_length=HOP)[0][:len(f0)]
    thr = max(np.percentile(rms, 60) * .5, 0.01)
    midi = librosa.hz_to_midi(f0)
    out, i, n = [], 0, len(f0)
    while i < n:
        if rms[i] < thr:
            i += 1; continue
        j = i
        while j + 1 < n and rms[j + 1] >= thr * .6 and abs(midi[j + 1] - np.median(midi[i:j + 1])) <= tol:
            j += 1
        if (j - i) * HOP / SR * 1000 >= min_ms:
            out.append((i * HOP / SR, (j + 1) * HOP / SR, float(np.median(f0[i:j + 1])), float(rms[i:j + 1].mean())))
        i = j + 1
    return out
