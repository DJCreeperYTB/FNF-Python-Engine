"""Script de CHANSON (data/songs/cobweb-cadence/) : il ne tourne que sur cette chanson.

GF applaudit tous les 8 temps pendant le refrain, et le fantôme du décor « respire » avec la musique.
"""
import pygame


def on_beat(game, beat):
    if 80 <= beat < 160 and beat % 8 == 0 and game.girlfriend:
        game.girlfriend.play_special("cheer", pygame.time.get_ticks())
