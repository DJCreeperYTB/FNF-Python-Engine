"""Evenements perso (lus par scripts/halloween_fx.py) et vitesses de defilement des 3 chansons.
Chaque evenement = (mesure, double-croche dans la mesure, nom, valeur)."""

F = lambda d=450, c=(255, 255, 255): {'color': list(c), 'duration': d}
ORANGE, PURPLE, RED, BLUE = (255, 140, 30), (150, 70, 220), (230, 30, 40), (60, 90, 255)


def cobweb(spec, night):
    ev = [(0, 0, 'Rain', {'level': 1}), (0, 0, 'Tint', {'color': list(BLUE), 'alpha': 60, 'ms': 1}),
          (2, 0, 'Lightning', {}), (3, 8, 'Zoom', {'amount': .06, 'ms': 600}),
          (4, 0, 'FlashScreen', F()), (4, 0, 'Lightning', {}), (4, 0, 'ZoomBeat', {'every': 4, 'amount': .015}),
          (4, 0, 'Tint', {'color': list(ORANGE), 'alpha': 22, 'ms': 800}),
          (4, 0, 'PlayAnimation', {'target': 'gf', 'anim': 'cheer'})]
    for k in range(4, 8):           # projecteur sur celui qui chante
        ev.append((4 + 2 * k, 0, 'Spotlight', {'on': True, 'char': 1 if k % 2 == 0 else 0}))
    ev += [(20, 0, 'Spotlight', {'on': False}), (20, 0, 'ZoomBeat', {'every': 2, 'amount': .03}), (20, 0, 'Rain', {'level': 2}),
           (20, 0, 'Lightning', {}), (28, 0, 'FlashScreen', F(600, ORANGE)), (28, 0, 'Shake', {'power': 9, 'ms': 450}),
           (28, 0, 'Lightning', {}), (28, 0, 'ArrowWave', {'on': True, 'amp': 14}),
           (28, 0, 'Tint', {'color': list(PURPLE), 'alpha': 55, 'ms': 600}),
           (36, 0, 'ArrowWave', {'on': False}), (36, 0, 'Scroll', {'mode': 'middle'}), (36, 0, 'Spotlight', {'on': True, 'char': 0}),
           (40, 0, 'Scroll', {'mode': 'normal'}), (40, 0, 'Spotlight', {'on': False}), (40, 0, 'ZoomBeat', {'every': 1, 'amount': .04}),
           (40, 0, 'Lightning', {}), (40, 8, 'Lightning', {}), (44, 0, 'ZoomBeat', {'every': 0}), (44, 0, 'Tint', {'color': list(BLUE), 'alpha': 40, 'ms': 1500}),
           (45, 0, 'FlashScreen', F(900)), (45, 0, 'PlayAnimation', {'target': 'bf', 'anim': 'hey'})]
    if night:
        ev += [(0, 0, 'SetHealthIcon', {'char': 0, 'id': 'djcreeper-night'}), (4, 0, 'Tint', {'color': list(RED), 'alpha': 60, 'ms': 600}),
               (12, 0, 'Shake', {'power': 7, 'ms': 300}), (20, 0, 'Shake', {'power': 8, 'ms': 300}), (36, 0, 'ArrowWave', {'on': True, 'amp': 22}),
               (40, 0, 'Shake', {'power': 12, 'ms': 600}), (40, 0, 'Tint', {'color': list(RED), 'alpha': 95, 'ms': 400})]
    return ev


def candlewick(spec, night):
    ev = [(0, 0, 'Rain', {'level': 1}), (0, 0, 'Tint', {'color': list(PURPLE), 'alpha': 45, 'ms': 1}), (3, 0, 'Lightning', {}),
          (4, 0, 'ZoomBeat', {'every': 4, 'amount': .012}), (4, 0, 'Spotlight', {'on': True, 'char': 1})]
    for k in range(1, 16):           # le projecteur suit la phrase
        side = 1 if k % 2 == 0 else 0
        if k >= 14:
            side = 2
        ev.append((4 + 2 * k, 0, 'Spotlight', {'on': True, 'char': side}))
    ev += [(20, 0, 'Scroll', {'mode': 'flip'}), (20, 0, 'FlashScreen', F(500, PURPLE)), (28, 0, 'Scroll', {'mode': 'flip'}),
           (28, 0, 'FlashScreen', F(500, PURPLE)), (28, 0, 'ScrollSpeed', {'scroll': 1.15, 'absolute': False}),
           (28, 0, 'Lightning', {}), (28, 0, 'Zoom', {'amount': .08, 'ms': 700}), (28, 0, 'ZoomBeat', {'every': 2, 'amount': .025}),
           (28, 0, 'ArrowWave', {'on': True, 'amp': 10}), (36, 0, 'ScrollSpeed', {'scroll': 1.0, 'absolute': False}),
           (36, 0, 'ArrowWave', {'on': False}), (36, 0, 'ZoomBeat', {'every': 0}), (36, 0, 'Spotlight', {'on': True, 'char': 0}),
           (37, 8, 'Lightning', {}), (37, 8, 'FlashScreen', F(900)), (37, 8, 'Spotlight', {'on': False}),
           (37, 8, 'PlayAnimation', {'target': 'bf', 'anim': 'hey'})]
    if night:
        ev += [(0, 0, 'SetHealthIcon', {'char': 0, 'id': 'djcreeper-night'}), (4, 0, 'Tint', {'color': list(RED), 'alpha': 55, 'ms': 800}),
               (12, 0, 'Lightning', {}), (20, 0, 'Shake', {'power': 8, 'ms': 400}), (28, 0, 'Shake', {'power': 12, 'ms': 600}),
               (28, 0, 'Tint', {'color': list(RED), 'alpha': 100, 'ms': 400})]
    return ev


def pumpkin(spec, night):
    ev = [(0, 0, 'Rain', {'level': 2}), (0, 0, 'Tint', {'color': list(BLUE), 'alpha': 70, 'ms': 1}), (1, 0, 'Lightning', {}),
          (3, 0, 'Zoom', {'amount': .07, 'ms': 900}),
          (4, 0, 'FlashScreen', F(500, (255, 230, 120))), (4, 0, 'ZoomBeat', {'every': 2, 'amount': .02}),
          (4, 0, 'Tint', {'color': list(ORANGE), 'alpha': 30, 'ms': 600}), (4, 0, 'Spotlight', {'on': True, 'char': 1}),
          (12, 0, 'Spotlight', {'on': False}), (12, 0, 'Lightning', {}), (20, 0, 'ArrowWave', {'on': True, 'amp': 12}),
          (20, 0, 'Shake', {'power': 7, 'ms': 300}), (28, 0, 'FlashScreen', F(700, (255, 255, 255))), (28, 0, 'Shake', {'power': 14, 'ms': 700}),
          (28, 0, 'Lightning', {}), (28, 0, 'ScrollSpeed', {'scroll': 1.15, 'absolute': False}), (28, 0, 'ZoomBeat', {'every': 1, 'amount': .035}),
          (28, 0, 'Tint', {'color': list(RED), 'alpha': 60, 'ms': 300}), (28, 0, 'SetHealthIcon', {'char': 1, 'id': 'monster'}),
          (36, 0, 'Scroll', {'mode': 'middle'}), (36, 0, 'Spotlight', {'on': True, 'char': 0}), (38, 0, 'Spotlight', {'on': True, 'char': 2}),
          (40, 0, 'Scroll', {'mode': 'normal'}), (40, 0, 'Spotlight', {'on': False}), (40, 0, 'Lightning', {}), (40, 8, 'Lightning', {}),
          (44, 0, 'ArrowWave', {'on': False}), (44, 0, 'Shake', {'power': 10, 'ms': 500}), (52, 0, 'ZoomBeat', {'every': 0}),
          (52, 0, 'Tint', {'color': list(ORANGE), 'alpha': 50, 'ms': 1500}), (53, 0, 'FlashScreen', F(1000)),
          (53, 0, 'PlayAnimation', {'target': 'bf', 'anim': 'hey'})]
    if night:
        ev += [(0, 0, 'SetHealthIcon', {'char': 0, 'id': 'djcreeper-night'}), (4, 0, 'Tint', {'color': list(RED), 'alpha': 65, 'ms': 600}),
               (12, 0, 'Shake', {'power': 9, 'ms': 400}), (36, 0, 'ArrowWave', {'on': True, 'amp': 24}), (40, 0, 'Shake', {'power': 12, 'ms': 600})]
    return ev


EVENTS = {'cobweb-cadence': cobweb, 'midnight-candlewick': candlewick, 'pumpkin-moon-panic': pumpkin}
META = {
    'cobweb-cadence': dict(speeds={'easy': 1.6, 'normal': 2.0, 'hard': 2.4}, speeds_night={'erect': 2.5, 'nightmare': 2.9}),
    'midnight-candlewick': dict(speeds={'easy': 1.6, 'normal': 2.0, 'hard': 2.4}, speeds_night={'erect': 2.4, 'nightmare': 2.8}),
    'pumpkin-moon-panic': dict(speeds={'easy': 1.7, 'normal': 2.1, 'hard': 2.6}, speeds_night={'erect': 2.7, 'nightmare': 3.1}),
}
