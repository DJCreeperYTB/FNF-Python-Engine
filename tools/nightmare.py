"""Nightmare : rythme chante + chart, une identite par chanson (utilise par build_example_song.py).

Le rythme de la voix est decoupe par `night_seq` (cellules : doubles-croches, croches, syncopes 3+1, galop 1-1-2, tenues) ;
le chart pose UNE note par cellule chantee (+ quelques coups de caisse claire / grosse caisse du morceau pendant les tenues).
Colonnes : cycles (escaliers, trilles, jacks, mains alternees...) choisis par section, miroir/rotation tires par phrase.
"""
import random

PATS = {   # cycles de colonnes
    'up': [[0, 1, 2, 3]], 'dn': [[3, 2, 1, 0]], 'zig': [[0, 1, 2, 3, 2, 1]], 'tr': [[0, 1], [1, 2], [2, 3]],
    'lr': [[0, 2, 1, 3]], 'lrm': [[0, 3, 1, 2]], 'ctr': None,
    'j2': [[0, 0, 2, 2, 1, 1, 3, 3]], 'j3': [[0, 0, 0, 2, 2, 2, 1, 1, 1, 3, 3, 3]], 'gal': [[0, 0, 1, 3, 3, 2]],
    'hmr': [[0, 3, 3, 0, 1, 2, 2, 1]],
}
LOG = []   # (cote, phrase, motif, motif de colonnes) pour les comptes rendus
OUTER = {0: 3, 1: 3, 2: 0, 3: 0}
STYLE = {
    'Cobweb': dict(big={0: '8', 1: '16', 2: '8', 3: '16'}, dbl={0: .3, 1: .6, 2: .4, 3: .8}, maxrun=2, taps=False,
                   menu={0: ['up', 'tr'], 1: ['dn', 'zig', 'tr'], 2: ['zig', 'up', 'tr'], 3: ['up', 'dn', 'zig']},
                   chord=lambda au, m, k, both: (both and au % 4 == 0) or (m == 3 and au % 8 == 0) or (k >= 8 and m == 1 and au % 16 == 0),
                   partner=lambda l: (l + 2) % 4),
    'Candlewick': dict(big={0: 'hold', 1: 'sync', 2: 'sync', 3: '8'}, dbl={0: 0, 1: .2, 2: .3, 3: .6}, maxrun=2, taps=True,
                       menu={0: ['lr', 'ctr'], 1: ['lrm', 'ctr', 'lr'], 2: ['ctr', 'lrm'], 3: ['lr', 'lrm']},
                       chord=lambda au, m, k, both: (au % 4 == 0 and (m in (1, 3) or both)) or au % 16 == 0,
                       partner=lambda l: OUTER[l]),
    'Pumpkin': dict(big={0: 'gallop', 1: '16', 2: '16', 3: '16'}, dbl={0: .6, 1: .8, 2: .9, 3: 1.0}, maxrun=3, taps=False,
                    menu={0: ['gal', 'j2'], 1: ['j2', 'hmr', 'gal'], 2: ['j3', 'hmr', 'j2'], 3: ['j2', 'j3', 'hmr']},
                    chord=lambda au, m, k, both: (au % 16 == 0 and k >= 2) or (m == 3 and au % 8 == 0),
                    partner=lambda l: 3 - l),
}


def cells(d, mode):
    if mode == 'hold':
        return [d]
    if mode == '16':
        return [1] * d
    if mode == '8':
        return [2] * (d // 2) + [1] * (d % 2)
    out, r = [], d
    unit = [3, 1] if mode == 'sync' else [1, 1, 2]
    while r >= 4:
        out += unit
        r -= 4
    return out + ([r] if mode == 'sync' and r else [1] * r)


def night_seq(spec, ph, seq):
    """Remplace le decoupage Nightmare : seq = [(t, p, du, d, bar)] -> cellules (t, p, du, unites, bar)."""
    st = STYLE[spec['name']]
    rng = random.Random(f"{spec['name']}-r{ph['k']}")
    m = 3 if ph['side'] == 'both' else ph['motif']
    out = []
    for idx, (t, p, du, d, b) in enumerate(seq):
        U = spec['unit'](b)
        if d == 1:
            cs = [1]
        elif d == 2:
            cs = [1, 1] if rng.random() < st['dbl'][m] else [2]
        elif idx == len(seq) - 1 and d >= 4:
            cs = [d]            # la derniere note de la phrase reste tenue
        else:
            cs = cells(d, st['big'][m])
        pos = 0
        for c in cs:
            out.append((t + pos * U, p, du if len(cs) == 1 else (c * U if c >= 2 else .8 * U), c, b))
            pos += c
    return out


def drum_hits(spec, bar):
    """(u, 'kick'|'snare') du Nightmare (cf. render_inst) pour une mesure de corps de chanson."""
    ks = [0, 8] + ([12] if bar % 2 else [4])
    return [(u, 'kick') for u in ks] + [(4, 'snare'), (12, 'snare')]


def _choose(rng, st, m, prev):
    menu = [x for x in st['menu'][m] if x != prev] or st['menu'][m]
    return rng.choice(menu)


def night_notes(spec, phrases, side):
    """Notes de chart d'un cote ('player' -> colonnes 0-3, 'opp' -> 4-7). Cle '_c' (cellule), '_ch' (accord) a retirer ensuite."""
    st, base = STYLE[spec['name']], (0 if side == 'player' else 4)
    notes, busy, prev, run, prev_pat = [], [-1e9] * 4, None, 0, None
    free = lambda t, U: [x for x in range(4) if t >= busy[x] + .9 * U]
    for ph in phrases:
        if not (ph['side'] in ('player', 'both') if side == 'player' else ph['side'] in ('opp', 'both')):
            continue
        both = ph['side'] == 'both'
        m = 3 if both else ph['motif']
        rng = random.Random(f"{spec['name']}-{side}-{ph['k']}")
        T0, U0 = spec['T'](ph['bar']), spec['unit'](ph['bar'])
        segs = {}
        for n in sorted(ph['notes']):
            au = round((n[0] - T0) / U0)
            segs.setdefault(au // 8, []).append((au, n))
        pp = None
        for sg in sorted(segs):
            pat = _choose(rng, st, m, pp)
            pp = pat
            LOG.append((side, ph['k'], m, pat))
            cyc = rng.choice(PATS[pat]) if PATS[pat] else None
            if cyc and rng.random() < .5:
                cyc = [3 - x for x in cyc]
            rot = rng.randrange(len(cyc)) if cyc else 0
            if cyc:   # 1re colonne differente de la precedente (sauf si le cycle est un jack)
                rots = [r for r in range(len(cyc)) if prev is None or cyc[r] != prev or pat in ('j2', 'j3', 'gal')]
                rot = rng.choice(rots or [rot])
            pl = None
            for i, (au, (t, p, du, c, b)) in enumerate(segs[sg]):
                U = spec['unit'](b)
                fr = free(t, U)
                if cyc:
                    raw = cyc[(rot + i) % len(cyc)]
                else:   # contour melodique
                    pr = prev if prev is not None else 1
                    raw = (min(3, pr + 1) if pr < 3 else 2) if pl is not None and p > pl[1] else ((max(0, pr - 1) if pr > 0 else 1) if pl is not None and p < pl[1] else (pr ^ 1 if pl is not None else (1 if p < 70 else 2)))
                pl = (raw, p)
                lane = raw
                bad = lambda x: x not in fr or (x == prev and run >= st['maxrun'])
                if bad(lane):
                    alt = sorted((x for x in range(4) if not bad(x)), key=lambda x: (abs(x - raw), x))
                    if not alt:
                        alt = sorted((x for x in fr if x != prev), key=lambda x: abs(x - raw)) or fr
                    lane = alt[0]
                run = run + 1 if lane == prev else 1
                prev = lane
                hold = c >= 3
                ln = round(du - U, 3) if hold else 0
                lanes_ = [lane]
                if st['chord'](au, m, ph['k'], both) and len(fr) == 4:
                    q = st['partner'](lane)
                    if q != lane:
                        lanes_.append(q)
                for x in lanes_:
                    notes.append({'t': round(t, 3), 'd': base + x, 'l': ln, '_c': c, '_ch': len(lanes_) > 1})
                    busy[x] = t + ln
    if side == 'player' and st['taps']:
        notes += _taps(spec, notes)
    return notes


def _taps(spec, notes):
    """Pendant une tenue (une seule colonne), l'autre main joue la grosse caisse / caisse claire reelles du morceau."""
    out, bars = [], spec['starts']
    for n in notes:
        if n['l'] <= 0 or n['_ch'] or n['_c'] < 4:
            continue
        bar = max(b for b in range(spec['bars']) if bars[b] <= n['t'] + 1e-6)
        U = spec['unit'](bar)
        t1 = n['t'] + n['l'] + U
        for b in (bar, bar + 1):
            if b >= spec['bars'] - 1:
                continue
            for u, kind in drum_hits(spec, b):
                t = bars[b] + u * U
                if n['t'] + U <= t < t1 - .5 * U:
                    left = n['d'] < 2
                    lane = (3 if left else 0) if kind == 'snare' else (2 if left else 1)
                    if not any(abs(o['t'] - t) < 1 for o in out):
                        out.append({'t': round(t, 3), 'd': lane, 'l': 0, '_c': 1, '_ch': False})
    return out
