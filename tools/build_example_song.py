"""Construit les 3 chansons Halloween du mod d'exemple (+ leur remix Nightmare) a partir d'UNE liste de notes.

Instruments = vrais samples FL Studio (sequences puis reechantillonnes, aucune synthese).
Voix : Skid & Pump (opposant Spooky) et Monster = presets chromatiques du SoundFont FNF definitif ;
       DJCreeper = son SF2 (FNF DJCREEPER/tools/sing.py). Chart V-Slice genere depuis la meme liste.
    python tools/build_example_song.py [cobweb-cadence|midnight-candlewick|pumpkin-moon-panic ...]
"""
import glob, io, json, os, random, re, shutil, struct, subprocess, sys, tempfile
import mido
import numpy as np
import soundfile as sf
from scipy import signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = r'D:\FLStudio\Data\Patches\Packs'
DJC = r'C:\Users\DJCre\Documents\FNF DJCREEPER'
DEFSF2 = os.path.join(DJC, 'work', 'voice', 'sf2', 'ref', 'fnf_definitive.sf2')
FLUID = os.path.join(DJC, 'work', 'tools', 'fluidsynth', 'fluidsynth-v2.5.7-win10-x64-cpp11', 'bin', 'fluidsynth.exe')
MOD = os.path.join(ROOT, 'mods_src', 'ExampleMod')
LEAKS = os.path.join(ROOT, 'Leaks')
SR = 44100
sys.path.insert(0, os.path.join(DJC, 'tools'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nightmare import night_seq, night_notes

NOTE_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def midi_of(name):
    m = re.fullmatch(r'([A-G])([#b]?)(\d)', name)
    return 12 * (int(m.group(3)) + 1) + NOTE_PC[m.group(1)] + {'#': 1, 'b': -1, '': 0}[m.group(2)]


def motif(text):
    out = []
    for tok in text.replace('|', ' ').split():
        n, d = tok.split(':')
        out.append((None if n == '-' else midi_of(n), int(d)))
    assert sum(d for _, d in out) == 32, (text, sum(d for _, d in out))
    return out


SONGS = {
    'cobweb-cadence': dict(
        name='Cobweb', bpm=124, bpm_changes={}, opp='skid-pump', stage='halloween-night', opp_id='spooky',
        motifs=[('Dm A', 'D5:2 F5:2 A5:2 F5:2 D5:4 -:2 E5:2 | F5:2 A5:2 C6:2 A5:2 F5:4 -:2 E5:2'),
                ('Gm A', 'G5:2 Bb5:2 D6:2 Bb5:2 G5:4 -:2 A5:2 | A5:2 C#6:2 E6:2 C#6:2 A5:4 -:4'),
                ('Bb C', 'Bb5:3 A5:1 G5:2 F5:2 G5:2 A5:2 Bb5:4 | C6:3 Bb5:1 A5:2 G5:2 A5:2 Bb5:2 C6:4'),
                ('Dm A', 'A5:1 A5:1 D6:2 D6:2 F6:2 E6:2 D6:6 | C#6:2 E6:2 A6:2 E6:2 D6:4 -:4')],
        order=[0, 0, 1, 1, 2, 2, 0, 0, 1, 1, 2, 2, 3, 3, 3, 3, 0, 0, 3, 3], both=(18, 19), style='bright', sy=124),
    'midnight-candlewick': dict(
        name='Candlewick', bpm=92, bpm_changes={}, opp='skid-pump', stage='halloween-night', opp_id='spooky',
        motifs=[('Am F', 'A5:4 C6:4 E6:4 C6:2 B5:2 | A5:4 C6:2 A5:2 F5:4 -:4'),
                ('C G', 'G5:4 E5:2 G5:2 C6:4 B5:2 A5:2 | B5:4 D6:4 G6:4 F#6:2 D6:2'),
                ('Dm E', 'F5:2 A5:2 D6:4 C6:2 A5:2 F5:4 | E5:2 G#5:2 B5:4 E6:6 -:2'),
                ('F Am', 'C6:2 C6:2 F6:4 E6:2 C6:2 A5:4 | B5:2 G#5:2 E6:6 A5:6')],
        order=[0, 1, 2, 0, 1, 2, 3, 3, 0, 1, 2, 3, 3, 3, 3, 3], both=(14, 15), style='lyric', sy=92),
    'pumpkin-moon-panic': dict(
        name='Pumpkin', bpm=140, bpm_changes={28: 160}, opp='monster', stage='halloween-night', opp_id='monster',
        motifs=[('Em C', 'E5:2 E5:2 G5:2 E5:2 B5:4 A5:2 G5:2 | G5:2 G5:2 C6:2 G5:2 E6:4 D6:2 C6:2'),
                ('D B', 'F#5:2 F#5:2 A5:2 F#5:2 D6:4 C#6:2 A5:2 | D#5:2 F#5:2 B5:2 F#5:2 B5:4 A5:2 F#5:2'),
                ('Am E', 'A5:2 C6:2 E6:2 C6:2 A5:2 B5:2 C6:4 | B5:2 B5:2 E6:2 B5:2 G6:4 F#6:2 E6:2'),
                ('C B', 'G5:1 G5:1 C6:2 E6:2 G6:2 E6:2 C6:6 | B5:1 B5:1 D#6:2 F#6:2 B6:2 F#6:2 B5:6')],
        order=[0, 0, 1, 1, 2, 2, 0, 0, 1, 1, 2, 2, 3, 3, 0, 0, 3, 3, 1, 1, 3, 3, 3, 3], both=(22, 23), style='rock', sy=140),
}
INTRO, OUTRO = 4, 2


def chord_notes(name):
    """(racine de basse, triade) : basse entre MIDI 33 et 44, triade autour de MIDI 55-66."""
    pc = (NOTE_PC[name[0]] + (1 if '#' in name else 0) + (-1 if len(name) > 1 and name[1] == 'b' else 0)) % 12
    bass = 36 + pc - (12 if pc > 6 else 0)
    base = 60 + pc - (12 if pc > 6 else 0)
    third = 3 if name.endswith('m') else 4
    return bass, (base, base + third, base + 7)


def bar_chords(spec, bar):
    if bar < INTRO:
        return spec['motifs'][bar % 4][0].split()[0]
    k = bar - INTRO
    if k >= len(spec['order']) * 2:
        return spec['motifs'][spec['order'][-1]][0].split()[0] if bar < spec['bars'] - 1 else spec['motifs'][0][0].split()[0]
    return spec['motifs'][spec['order'][k // 2]][0].split()[k % 2]


# ------------------------------------------------------------------ temps
def timeline(spec):
    spec['bars'] = INTRO + len(spec['order']) * 2 + OUTRO
    bpm, starts, t = spec['bpm'], [], 0.0
    spec['bar_bpm'] = []
    for b in range(spec['bars'] + 1):
        bpm = spec['bpm_changes'].get(b, bpm)
        spec['bar_bpm'].append(bpm)
        starts.append(t)
        t += 4 * 60000.0 / bpm
    spec['starts'] = starts
    spec['T'] = lambda bar, u=0: starts[bar] + u * 15000.0 / spec['bar_bpm'][bar]
    spec['unit'] = lambda bar: 15000.0 / spec['bar_bpm'][bar]


def build_phrases(spec, night):
    """Une phrase = 2 mesures. side = opp | player | both. notes = [(t_ms, pitch, duree_ms, unites, mesure)]."""
    rng, out = random.Random(spec['sy']), []
    for k, mi in enumerate(spec['order']):
        side = 'both' if k >= spec['both'][0] else ('opp' if k % 2 == 0 else 'player')
        seq, u = [], 0
        bar0 = INTRO + 2 * k
        for p, d in motif(spec['motifs'][mi][1]):
            if p is not None:
                bar = bar0 + u // 16
                t = spec['T'](bar, u % 16)
                dur = d * spec['unit'](bar)
                seq.append((t, p, dur, d, bar))
            u += d
        if k >= 8 and not night and side != 'opp':      # petite variation melodique en 2e moitie
            seq = [(t, p + (2 if (d == 2 and rng.random() < .12) else 0), du, d, b) for t, p, du, d, b in seq]
        if night:   # remix Nightmare : rythme propre a chaque chanson (tools/nightmare.py)
            seq = night_seq(spec, dict(k=k, motif=mi, side=side), seq)
        out.append(dict(side=side, bar=bar0, k=k, motif=mi, notes=seq))
    return out


# ------------------------------------------------------------------ samples
def load(path):
    b = open(path, 'rb').read()
    i = b.find(b'data')
    try:
        ln = struct.unpack('<I', b[i + 4:i + 8])[0]
        d = b[i + 8:i + 8 + ln]
        x, sr = sf.read(io.BytesIO(d)) if d[:4] == b'OggS' else sf.read(path)
    except Exception:
        x, sr = sf.read(path)
    x = x if x.ndim == 1 else x.mean(1)
    if sr != SR:
        x = signal.resample_poly(x, SR, sr)
    return x / (np.abs(x).max() + 1e-9)


def f0(x):
    seg = x[int(.03 * SR):int(.5 * SR)] if len(x) > .55 * SR else x
    n = 1 << 16
    f = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n))
    fr = np.fft.rfftfreq(n, 1 / SR)
    h = f.copy()
    for k in (2, 3, 4):
        h[:len(f) // k] *= f[::k][:len(f) // k]
    m = (fr > 40) & (fr < 1500)
    return 69 + 12 * np.log2(fr[m][h[m].argmax()] / 440)


class Bank:
    def __init__(self, paths, roots=None):
        self.s = {}
        for i, p in enumerate(paths):
            x = load(p)
            self.s[int(round(roots[i] if roots else f0(x)))] = x
        self._c = {}

    def note(self, midi, loop_to=None):
        root = min(self.s, key=lambda r: abs(r - midi))
        key = (root, midi, loop_to)
        if key not in self._c:
            x = self.s[root]
            ratio = 2 ** ((midi - root) / 12)
            x = np.interp(np.arange(0, len(x) - 1, ratio), np.arange(len(x)), x)
            if loop_to and loop_to > len(x):
                x = sustain(x, loop_to)
            self._c[key] = x
        return self._c[key]


def sustain(x, need):
    a, b = int(len(x) * .3), int(len(x) * .75)
    seg, fx = x[a:b], int(.04 * SR)
    out = x[:b].copy()
    while len(out) < need:
        w = np.linspace(0, 1, fx)
        out[-fx:] = out[-fx:] * (1 - w) + seg[:fx] * w
        out = np.concatenate([out, seg[fx:]])
    return out


def P(*a):
    return os.path.join(PACK, *a)


class Kit:
    def __init__(self):
        L = lambda *a: load(P(*a))
        self.kick = L('Legacy', 'Drums', 'FPC', 'Kick Drums', 'FPC_Kick_GiReal_003.wav')
        self.snare = L('Legacy', 'Drums', 'FPC', 'Snare Drums', 'FPC_Snr_2L002.wav')
        self.rim = L('Legacy', 'Drums', 'FPC', 'SideStick_Rims', sorted(os.listdir(P('Legacy', 'Drums', 'FPC', 'SideStick_Rims')))[0])
        self.hat = L('Legacy', 'Drums', 'FPC', 'Hi Hats', 'FPC_ClHH_GCsta_001.wav')
        self.crash = L('Legacy', 'Drums', 'FPC', 'Cymbals', 'FPC_Crash_G18InMed_01.wav')
        self.ridebell = L('Legacy', 'Drums', 'FPC', 'Cymbals', 'FPC_RideBell_F_010.wav')
        self.tom = [L('Legacy', 'Drums', 'FPC', 'Toms', n) for n in ('FPC_Tom_GtomLow_001.wav', 'FPC_Tom_GtomMid_001.wav', 'FPC_Tom_GtomHi_001.wav')]
        self.bigtom = L('SFX', 'SFX Big Tom.wav')
        self.thunder = L('SFX', 'SFX Thunder Sheet.wav')
        self.toll = L('Legacy', 'FX', 'FX_Toilings.wav')
        self.orch = L('Legacy', 'Instruments', 'Hits', 'HIT_Orch.wav')
        self.harp = Bank([P('Legacy', 'Instruments', 'Strings', 'STR_Harpsy_C4.wav')], [60])
        self.kalim = Bank([P('Legacy', 'Instruments', 'Percs', 'PERC_Kalim_C4.wav'), P('Legacy', 'Instruments', 'Percs', 'PERC_Isle Mallet_C4.wav')], [60, 61])
        self.organ = Bank([P('Legacy', 'Instruments', 'Strings', 'STR_Morg_C2.wav')], [48])
        self.choir = Bank(sorted(glob.glob(P('Instruments', 'Orchestral', 'Choir Ooh', '*.wav'))))
        self.strings = Bank(sorted(glob.glob(P('Instruments', 'Orchestral', 'Strings Solo', '*.wav'))))
        self.bass = Bank(sorted(glob.glob(P('Instruments', 'Bass', 'Acoustic', '*.wav'))))


def place(buf, x, t_ms, gain=1.0, gate_ms=None, pan=0.0, rel_ms=40):
    s = int(round(t_ms * SR / 1000))
    if gate_ms is not None:
        n = int(gate_ms * SR / 1000)
        x = x[:n].copy()
        r = min(len(x), int(rel_ms * SR / 1000))
        x[-r:] *= np.linspace(1, 0, r)
    e = min(len(buf), s + len(x))
    if e <= s or s < 0:
        return
    a = (pan + 1) * np.pi / 4
    seg = x[:e - s] * gain
    buf[s:e, 0] += seg * np.cos(a)
    buf[s:e, 1] += seg * np.sin(a)


def render_inst(spec, K, night, n_samples):
    buf = np.zeros((n_samples, 2))
    rng = random.Random(7)
    st = spec['style']
    for bar in range(spec['bars']):
        t0, U = spec['starts'][bar], spec['unit'](bar)
        at = lambda u: t0 + u * U
        name = bar_chords(spec, bar)
        root, tri = chord_notes(name)
        intro, last = bar < INTRO, bar == spec['bars'] - 1
        body = INTRO <= bar < spec['bars'] - OUTRO
        climax = body and spec['order'][min((bar - INTRO) // 2, len(spec['order']) - 1)] == 3
        barlen = 16 * U
        # --- couche harmonique
        if night:    # remix : orgue + choeur tenus, cordes, clavecin une octave plus bas
            for i, nt in enumerate(tri):
                place(buf, K.organ.note(nt - 12, int(barlen * SR / 1000)), at(0), .30, gate_ms=barlen * (1.0 if not last else 3.5), pan=(-.3, 0, .3)[i], rel_ms=120)
                if body:
                    place(buf, K.choir.note(nt, int(barlen * SR / 1000)), at(0), .34, gate_ms=barlen, pan=(.3, 0, -.3)[i], rel_ms=150)
            if body and bar % 2 == 0:
                for u in (0, 3, 6, 10, 12, 14):
                    for nt in tri[:2]:
                        place(buf, K.harp.note(nt - 12), at(u), .5, gate_ms=U * 2, pan=-.2)
        elif st == 'bright':
            stabs = [(0, 16, .5)] if intro and bar < 2 else [(0, 3, .55), (4, 2, .4), (8, 3, .5), (12, 2, .4)]
            for u, d, g in stabs:
                for i, nt in enumerate(tri):
                    place(buf, K.organ.note(nt - 12), at(u), g * .42, gate_ms=d * U, pan=(-.3, 0, .3)[i], rel_ms=50)
            for j in range(16):      # arpeggio de clavecin aux croches
                if j % 2 == 0 and not last:
                    nt = (tri[0], tri[1], tri[2], tri[1])[(j // 2) % 4] + (12 if bar % 2 else 0)
                    place(buf, K.harp.note(nt), at(j), .55 if j % 4 == 0 else .38, gate_ms=U * 2.2, pan=.25 if j % 4 else -.2)
            if climax:
                for u in (0, 6, 8, 14):
                    place(buf, K.kalim.note(tri[2] + 12), at(u), .5, gate_ms=U * 3, pan=.3)
        elif st == 'lyric':
            for i, nt in enumerate(tri):
                place(buf, K.strings.note(nt - 12, int(barlen * SR / 1000)), at(0), .42, gate_ms=barlen, pan=(-.4, 0, .4)[i], rel_ms=200)
            for j in range(0, 16, 2):   # boite a musique : arpege aux croches
                nt = (tri[0], tri[2], tri[1] + 12, tri[2])[(j // 2) % 4] + 12
                place(buf, K.kalim.note(nt), at(j), .5 if j % 4 == 0 else .34, gate_ms=U * 4, pan=.3 if j % 4 else -.3)
            if climax or last:
                for i, nt in enumerate(tri):
                    place(buf, K.choir.note(nt, int(barlen * SR / 1000)), at(0), .34, gate_ms=barlen, pan=(.3, 0, -.3)[i], rel_ms=200)
        else:   # rock : orgue + cordes en accords syncopes
            for u, d in ((0, 3), (3, 3), (6, 2), (8, 3), (11, 3), (14, 2)):
                for i, nt in enumerate(tri):
                    place(buf, K.organ.note(nt - 12), at(u), .36, gate_ms=d * U, pan=(-.3, 0, .3)[i], rel_ms=40)
                    place(buf, K.strings.note(nt), at(u), .24, gate_ms=d * U, pan=(.3, 0, -.3)[i], rel_ms=60)
            if climax:
                for i, nt in enumerate(tri):
                    place(buf, K.choir.note(nt, int(barlen * SR / 1000)), at(0), .36, gate_ms=barlen, pan=(.3, 0, -.3)[i], rel_ms=100)
                for u in (0, 8):
                    place(buf, K.kalim.note(tri[0] + 24), at(u + 2), .4, gate_ms=U * 3)
        # --- basse
        if bar >= 2 and not last:
            if st == 'lyric' and not night:
                place(buf, K.bass.note(root), at(0), .75, gate_ms=U * 7, rel_ms=80)
                place(buf, K.bass.note(root + 7), at(8), .6, gate_ms=U * 7, rel_ms=80)
            else:
                pat = (0, 0, 12, 0, 0, 7, 12, 7) if st != 'rock' or night else (0, 0, 0, 12, 0, 0, 7, 0)
                for u, off in zip(range(0, 16, 2), pat):
                    place(buf, K.bass.note(root + off), at(u), .8 if u % 4 == 0 else .6, gate_ms=U * 1.8, rel_ms=30)
        elif last:
            place(buf, K.bass.note(root), at(0), .85, gate_ms=U * 12, rel_ms=300)
        # --- percussions
        if bar >= 2 and not last:
            heavy = night or st == 'rock'
            if st == 'lyric' and not night:
                place(buf, K.kick, at(0), .7)
                place(buf, K.tom[0], at(8), .55)
                place(buf, K.rim, at(4), .35); place(buf, K.rim, at(12), .45)
                if climax:
                    place(buf, K.tom[1], at(14), .5); place(buf, K.tom[2], at(15), .45)
                for u in range(0, 16, 4):
                    place(buf, K.ridebell, at(u), .16, gate_ms=U * 3, pan=.3)
            else:
                for b in range(4):
                    if b in (0, 2) or (heavy and b == 3 and bar % 2) or (night and b == 1 and bar % 2 == 0):
                        place(buf, K.kick, at(b * 4), .9)
                    if b in (1, 3):
                        place(buf, K.snare if heavy else K.rim, at(b * 4), .6 if heavy else .5)
                step = 1 if (night or climax) else 2
                for u in range(0, 16, step):
                    place(buf, K.hat, at(u), (.32 if u % 4 == 0 else .2) * (.8 + .4 * rng.random()), pan=.25 if (u // step) % 2 else -.15)
                if bar % 4 == 3:    # roulement de toms
                    for j, u in enumerate((12, 13, 14, 15)):
                        place(buf, K.tom[min(2, j)], at(u), .45 + .08 * j)
                if night:
                    place(buf, K.bigtom, at(8), .5)
        if bar in (INTRO, INTRO + 8, INTRO + 16, INTRO + 24, spec['bars'] - 1) or (climax and (bar - INTRO) % 8 == 0):
            place(buf, K.crash, t0, .5, pan=-.2)
        if bar == 0 or (bar % 8 == 0 and night) or last:
            place(buf, K.toll, t0, .5 if not night else .6, gate_ms=barlen * 2)
        if bar == INTRO - 1 or (night and bar == INTRO - 2):   # montee avant l'entree des voix : crash inverse
            place(buf, K.crash[::-1], t0 + barlen - len(K.crash) / SR * 1000, .5)
        if bar == 1 and st == 'rock':
            place(buf, K.thunder, at(0), .6)
        if climax and (bar - INTRO) % 2 == 0 and st == 'rock':
            place(buf, K.orch, at(0), .7)
    return buf


# ------------------------------------------------------------------ voix
def write_mid(path, notes, n_ms):
    """notes = [(t_ms, len_ms, key, program)] ; une voie MIDI par programme (Skid / Pump separes)."""
    mid = mido.MidiFile(ticks_per_beat=1000)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage('set_tempo', tempo=1000000, time=0))
    progs = sorted({p for *_, p in notes})
    for ch, p in enumerate(progs):
        tr.append(mido.Message('program_change', program=p, channel=ch, time=0))
    ev = []
    for t, ln, key, p in notes:
        ch = progs.index(p)
        ev += [(round(t), 1, key, ch), (round(t + ln), 0, key, ch)]
    ev.sort(key=lambda e: (e[0], e[1]))
    last = 0
    for t, on, key, ch in ev:
        tr.append(mido.Message('note_on' if on else 'note_off', note=key, velocity=100 if on else 0, channel=ch, time=t - last))
        last = t
    tr.append(mido.MetaMessage('end_of_track', time=max(0, int(n_ms) - last)))
    mid.save(path)


def fluid(sf2, midpath, n):
    wav = midpath + '.wav'
    r = subprocess.run([FLUID, '-ni', '-R', '0', '-C', '0', '-g', '0.6', '-r', str(SR), '-o', 'synth.polyphony=64', '-F', wav, sf2, midpath],
                       capture_output=True, text=True)
    if r.returncode or not os.path.exists(wav):
        raise RuntimeError(r.stdout + r.stderr)
    x, _ = sf.read(wav)
    x = x if x.ndim == 2 else np.stack([x, x], 1)
    out = np.zeros((n, 2))
    out[:min(n, len(x))] = x[:n]
    return out


def mono_notes(seq, cut=True):
    """monophonique : une note est coupee quand la suivante commence, petit trou pour re-articuler."""
    out = []
    for i, (t, ln, key, tag) in enumerate(seq):
        if cut and i + 1 < len(seq):
            ln = min(ln, seq[i + 1][0] - t - 8)
        out.append((t, max(ln, 40), key, tag))
    return out


def process(dry):
    import sing as S
    return S.process(dry, 'player')


SYLS = ['ba', 'bee', 'bop', 'da', 'doo', 'hey', 'oh', 'ah', 'yeah']



def _skid_pump(opp, n, n_ms, night, tmp):
    """Skid & Pump et Monster : SoundFont FNF definitif."""
    groups = {}
    for t, ln, key, prog in opp:
        groups.setdefault(prog, []).append((t, ln, key, prog))
    seq = [x for g in groups.values() for x in mono_notes(g)]
    mp = os.path.join(tmp, f'opp{int(night)}.mid')
    write_mid(mp, sorted(seq), n_ms)
    dry = fluid(DEFSF2, mp, n)
    if night:   # remix : couche une octave plus bas (voix plus sombre)
        seq2 = [(t, ln, key - 12, prog) for t, ln, key, prog in seq]
        mp2 = os.path.join(tmp, f'opp{int(night)}b.mid')
        write_mid(mp2, sorted(seq2), n_ms)
        dry = dry + .6 * fluid(DEFSF2, mp2, n)
    return process(dry)


MONSTER_DROP = 32   # demi-tons : mediane des notes (MIDI 83) -> MIDI 51 = 156 Hz, comme le vrai Monster (159 Hz)


def _monster(opp, n, n_ms, night, tmp):
    """Monster : ses vraies syllabes chantees (tools/monster_voice.py), une par note, recalees en hauteur ; pas de SF2."""
    import monster_voice as MV
    seq = mono_notes(sorted((t, ln, key - MONSTER_DROP, 1) for t, ln, key, _ in opp))
    notes = [(t, ln, 440 * 2 ** ((key - 69) / 12)) for t, ln, key, _ in seq]
    mono = MV.sing(notes, n)
    if night:   # remix : couche grave une octave plus bas
        mono = mono + .45 * MV.sing(notes, n, -12)
    return process(np.stack([mono, mono], 1))


def render_voices(spec, phrases, n, night, tmp):
    n_ms = n * 1000 / SR
    opp, ply = [], []
    for ph in phrases:
        for t, p, du, d, bar in ph['notes']:
            ln = du - (spec['unit'](bar) * (.25 if d <= 2 else .5))
            if ph['side'] in ('opp', 'both'):
                if spec['opp'] == 'skid-pump':   # Skid sur la 1re mesure, Pump sur la 2e ; ensemble sur 'both'
                    if ph['side'] == 'both':
                        opp += [(t, ln, p, 9), (t, ln, p, 8)]
                    else:
                        opp.append((t, ln, p, 9 if bar == ph['bar'] else 8))
                else:
                    opp.append((t, ln, p, 10))  # Monster a la hauteur ecrite (une octave plus bas = trop grave)
            if ph['side'] in ('player', 'both'):
                ply.append((t, ln, p, SYLS[(len(ply) * 5 + ph['k']) % len(SYLS)]))
    opp_v = _monster(opp, n, n_ms, night, tmp) if spec['opp'] == 'monster' else _skid_pump(opp, n, n_ms, night, tmp)
    # joueur : DJCreeper.sf2 via sing.py
    import sing as S
    # DJCreeper.sf2 couvre les touches 48-76 : la melodie (octaves 5-6) chantee deux octaves plus bas, sinon trop aigu.
    mel = {'bpm': 120, 'offsetMs': 0, 'opponent': [dict(t=t, len=ln, midi=int(p) - 24, syl=s) for t, ln, p, s in ply], 'player': []}
    out = os.path.join(tmp, 'djc.wav')
    ply_v = S.sing(mel, 'opponent', out, n_ms)
    if night:
        mel2 = {'bpm': 120, 'offsetMs': 0, 'opponent': [dict(t=t, len=ln, midi=int(p) - 36, syl=s) for t, ln, p, s in ply], 'player': []}
        low = S.sing(mel2, 'opponent', os.path.join(tmp, 'djc2.wav'), n_ms)
        ply_v = ply_v + .5 * low[:len(ply_v)]
    fix = lambda v: np.concatenate([v, np.zeros((max(0, n - len(v)), 2))])[:n]
    return fix(opp_v), fix(ply_v)


def reverb(x, wet=.25, sec=1.8):
    rng = np.random.default_rng(5)
    m = int(sec * SR)
    ir = rng.standard_normal((m, 2)) * (10 ** (-3 * np.arange(m) / (1.4 * SR)))[:, None]
    ir /= np.sqrt((ir ** 2).sum(0))
    return x + wet * np.stack([signal.fftconvolve(x.mean(1), ir[:, c])[:len(x)] for c in range(2)], 1)


# ------------------------------------------------------------------ chart
def lanes(seq):
    out, prev_l, prev_p = [], None, None
    for t, p in seq:
        if prev_l is None:
            l = 1 if p < 70 else 2
        elif p > prev_p:
            l = 3 if prev_l == 2 else 2
        elif p < prev_p:
            l = 0 if prev_l == 1 else 1
        else:
            l = prev_l ^ 1
        out.append(l)
        prev_l, prev_p = l, p
    for a in range(3, len(out)):
        if out[a] == out[a - 1] == out[a - 2] == out[a - 3]:
            out[a] ^= 1
    return out


def reduce(seq, diff, spec):
    """seq = [(t, pitch, ms, unites, bar)] -> notes gardees selon la difficulte."""
    if diff in ('hard', 'erect', 'nightmare'):
        return list(seq)
    keep = []
    for t, p, du, d, bar in seq:
        u = round((t - spec['starts'][bar]) / spec['unit'](bar))
        if diff == 'normal' and d == 1 and u % 2 == 1:
            continue
        if diff == 'normal' and spec['style'] == 'lyric' and d == 2 and u % 8 == 6:
            continue
        if diff == 'easy' and u % 4 != 0:
            continue
        keep.append((t, p, du, d, bar))
    return keep


def hex_notes(spec, plr_notes, each):
    """Notes maudites (k=hex), JAMAIS a la place d'une note chantee : en plus, dans les silences du joueur, entre deux notes
    chantees, ou a cote d'une note chantee (autre colonne, meme instant). Chaque note est a >= 230 ms de toute note de sa colonne."""
    real = sorted((n['t'], n['t'] + n['l'], n['d']) for n in plr_notes if n['d'] < 4)
    free = lambda t, lane: all(not (a - 230 < t < b + 230) for a, b, d in real if d == lane)
    used = []
    ok = lambda t, lane: free(t, lane) and all(abs(t - u) > 250 or l != lane for u, l in used)
    spread = lambda c: [c[round(i * (len(c) - 1) / max(1, each - 1))] for i in range(each)] if len(c) > each else list(c)
    gaps = [(real[i][1], real[i + 1][0], real[i][2], real[i + 1][2]) for i in range(len(real) - 1)]
    silence = [(a + (b - a) * f, lane) for a, b, l1, l2 in gaps if b - a > 3000 for f, lane in ((.4, (l1 + 2) % 4),)]
    between = [((a + b) / 2, lane) for a, b, l1, l2 in gaps if 600 < b - a < 2500 for lane in range(4) if lane not in (l1, l2)]
    beside = [(a, lane) for a, b, l1 in real if b - a > 3 * spec['unit'](INTRO) for lane in ((l1 + 2) % 4, (l1 + 1) % 4, (l1 + 3) % 4)]
    out = []
    for cands in (silence, between, beside):
        picked = 0
        for t, lane in (c for c in spread([c for c in cands if free(*c)]) ):
            if ok(t, lane):
                out.append({'t': round(t, 3), 'd': lane, 'l': 0, 'k': 'hex'}); used.append((t, lane)); picked += 1
    return out


def build_chart(spec, phrases, diffs, extra_events, speeds, night):
    notes = {d: [] for d in diffs}
    ev = [{'t': 0, 'e': 'FocusCamera', 'v': {'char': 1}}]
    for ph in phrases:
        who = {'opp': 1, 'player': 0, 'both': 2}[ph['side']]
        ev.append({'t': round(spec['T'](ph['bar']), 3), 'e': 'FocusCamera', 'v': {'char': who}})
    for bar, u, name, val in extra_events:
        ev.append({'t': round(spec['T'](bar, u), 3), 'e': name, 'v': val})
    ev.sort(key=lambda e: e['t'])
    plr = [n for ph in phrases if ph['side'] in ('player', 'both') for n in ph['notes']]
    if night:
        notes['nightmare'] = night_notes(spec, phrases, 'player') + night_notes(spec, phrases, 'opp')
        # bonbons : 7 notes d'au moins une croche, hors accords, reparties sur la chanson
        cands = sorted((n for n in notes['nightmare'] if n['d'] < 4 and n['_c'] >= 2 and not n['_ch']), key=lambda n: n['t'])
        for i in range(7):
            cands[round(i * (len(cands) - 1) / 6)]['k'] = 'candy'
        for n in notes['nightmare']:
            n.pop('_c'); n.pop('_ch')
        if len(cands) > 12:
            notes['nightmare'] += hex_notes(spec, notes['nightmare'], 3)
        notes['nightmare'].sort(key=lambda n: (n['t'], n['d']))
        diffs = [d for d in diffs if d != 'nightmare']  # erect : la mélodie du remix notée comme Hard (voir plus bas)
        plr = [n for ph in phrases if ph['side'] in ('player', 'both') for n in ph['notes']]
        if not diffs:
            return {'version': '2.0.0', 'scrollSpeed': speeds, 'events': ev, 'notes': notes, 'generatedBy': 'tools/build_example_song.py'}
    cands = [n for n in reduce(plr, 'normal', spec) if n[3] >= 4]
    pick = lambda m: {round(cands[round(i * (len(cands) - 1) / (m - 1))][0], 3) for i in range(m)}
    candy = pick(7)
    for diff in diffs:
        for side, base in (('player', 0), ('opp', 4)):
            seq = [n for ph in phrases if side == 'player' and ph['side'] in ('player', 'both') or side == 'opp' and ph['side'] in ('opp', 'both')
                   for n in ph['notes']]
            seq = sorted(reduce(seq, diff, spec))
            for (t, p, du, d, bar), l in zip(seq, lanes([(a[0], a[1]) for a in seq])):
                n = {'t': round(t, 3), 'd': base + l, 'l': round(du - spec['unit'](bar), 3) if d >= 4 else 0}
                if side == 'player' and diff != 'easy' and round(t, 3) in candy:
                    n['k'] = 'candy'
                notes[diff].append(n)
        if diff in ('hard', 'erect') and len(cands) > 12:
            notes[diff] += hex_notes(spec, notes[diff], 2)
        notes[diff].sort(key=lambda n: (n['t'], n['d']))
    return {'version': '2.0.0', 'scrollSpeed': speeds, 'events': ev, 'notes': notes, 'generatedBy': 'tools/build_example_song.py'}


def db(x):
    return 20 * np.log10(max(x, 1e-9))


def encode(x, path, codec):
    p = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-threads', '2', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', *codec, path],
                         stdin=subprocess.PIPE)
    p.communicate(x.astype('<f4').tobytes())
    assert p.returncode == 0


def main():
    from song_events import EVENTS, META
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    chart_only = '--chart' in sys.argv
    ids = args or list(SONGS)
    K = None if chart_only else Kit()
    for sid in ids:
        spec = SONGS[sid]
        spec['style'] = spec['style']
        timeline(spec)
        out_audio = os.path.join(MOD, 'songs', sid)
        out_data = os.path.join(MOD, 'data', 'songs', sid)
        os.makedirs(out_audio, exist_ok=True); os.makedirs(out_data, exist_ok=True)
        for night in (False, True):
            phrases = build_phrases(spec, night)
            n = int((spec['starts'][spec['bars']] + 2200) * SR / 1000)
            suf = '-erect' if night else ''
            if chart_only:
                diffs = ['erect', 'nightmare'] if night else ['easy', 'normal', 'hard']
                speeds = META[sid]['speeds_night'] if night else META[sid]['speeds']
                chart = build_chart(spec, phrases, diffs, EVENTS[sid](spec, night), speeds, night)
                json.dump(chart, open(os.path.join(out_data, f'{sid}-chart{suf}.json'), 'w'), indent=1)
                print(sid, suf, {d: len(v) for d, v in chart['notes'].items()}, flush=True)
                continue
            inst = render_inst(spec, K, night, n)
            with tempfile.TemporaryDirectory() as tmp:
                opp, ply = render_voices(spec, phrases, n, night, tmp)
            if night:
                inst = reverb(inst, .22)
            inst *= 10 ** (-8 / 20) / np.abs(inst).max()
            for v in (opp, ply):
                v *= 10 ** (-6.5 / 20) / np.abs(v).max()
            k = 10 ** (-1 / 20) / np.abs(inst + opp + ply).max()
            inst, opp, ply = inst * k, opp * k, ply * k
            mix = inst + opp + ply
            assert np.abs(mix).max() < 1.0
            print(sid, 'nightmare' if night else 'normal', 'peak', round(db(np.abs(mix).max()), 1), 'dB bars', spec['bars'],
                  'dur', round(spec['starts'][spec['bars']] / 1000, 1), 's', flush=True)
            suf = '-erect' if night else ''
            ogg = ['-c:a', 'libvorbis', '-q:a', '3']
            encode(inst, os.path.join(out_audio, f'Inst{suf}.ogg'), ogg)
            encode(opp, os.path.join(out_audio, f'Voices-{spec["opp_id"]}{suf}.ogg'), ogg)
            encode(ply, os.path.join(out_audio, f'Voices-djcreeper{suf}.ogg'), ogg)
            os.makedirs(LEAKS, exist_ok=True)
            # Leak = la chanson entiere (copiee aussi dans le dossier d'attente du jugement).
            leak = os.path.join(LEAKS, f'v2_mod_{sid}{"_nightmare" if night else ""}.mp3')
            encode(mix, leak, ['-b:a', '160k'])
            waiting = os.path.join(ROOT, "en attente d'un jugement du grand maître")
            if os.path.isdir(waiting):
                shutil.copy2(leak, waiting)
            diffs = ['erect', 'nightmare'] if night else ['easy', 'normal', 'hard']
            speeds = META[sid]['speeds_night'] if night else META[sid]['speeds']
            chart = build_chart(spec, phrases, diffs, EVENTS[sid](spec, night), speeds, night)
            json.dump(chart, open(os.path.join(out_data, f'{sid}-chart{suf}.json'), 'w'), indent=1)
            print({d: len(v) for d, v in chart['notes'].items()}, flush=True)


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
