"""Script de CHANSON (data/songs/midnight-candlewick/) : les bougies — un halo qui palpite sur chaque temps."""
import math

import pygame

state = {"beat": 0}


def on_beat(game, beat):
    state["beat"] = pygame.time.get_ticks()


def on_draw_stage(game, screen):
    age = pygame.time.get_ticks() - state["beat"]
    if age < 400:
        layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        layer.fill((255, 150, 60, round(26 * (1 - age / 400))))
        screen.blit(layer, (0, 0))
