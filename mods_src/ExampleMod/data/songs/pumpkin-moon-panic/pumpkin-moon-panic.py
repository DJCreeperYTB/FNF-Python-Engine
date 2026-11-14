"""Script de CHANSON (data/songs/pumpkin-moon-panic/) : il ne tourne que sur cette chanson.

La caméra part sur DJCreeper puis glisse vers Lemon Monster pendant le compte à rebours (sans pause avant).
"""


def on_create(game):
    game.focus_camera(0, instant=True)


def on_beat(game, beat):
    if beat == -3:  # deuxième temps du compte à rebours : la caméra glisse vers le monstre
        game.focus_camera(1)
