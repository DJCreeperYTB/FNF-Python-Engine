"""Script GLOBAL du mod : deux nouveaux types de notes + les trophées d'Halloween Night.

  "k": "candy"  note OBLIGATOIRE (bonbon orange) : la rater = mort immédiate en Hard et Nightmare (sinon un simple raté plus 8 de vie)
  "k": "hex"    note À ÉVITER (violette) : la toucher = mort immédiate en Hard et Nightmare (sinon un simple raté, compté par le moteur).
La laisser passer ne coûte rien.
"""
import pygame

CANDY, HEX = (255, 150, 30), (170, 60, 255)
SONGS = {"cobweb-cadence", "midnight-candlewick", "pumpkin-moon-panic"}


def deadly(game):
    """Mort immédiate seulement en Hard et Nightmare."""
    return game.difficulty in ("hard", "nightmare")


def mine(game):
    """Scripts GLOBAUX : ne rien faire hors des 3 chansons du mod."""
    return game.song.song_id in SONGS


def on_create(game):
    if not mine(game):
        return
    game.candy_total = game.candy_hit = game.hex_total = game.hex_hit = 0
    for note in game.notes:
        if note.kind == "candy":
            note.color = CANDY
            game.candy_total += 1
        elif note.kind == "hex":
            note.color = HEX
            note.avoid = True  # la laisser passer ne compte pas comme un raté (et le botplay ne la touche pas)
            game.hex_total += 1


def on_note_hit(game, note, rating):
    if not mine(game):
        return
    now = pygame.time.get_ticks()
    if note.kind == "candy":
        game.candy_hit += 1
        game.health = min(100, game.health + 12)
        game.score += 500
        game.human.play_special("hey", now)  # human = le perso que tu joues (DJCreeper, ou l'adversaire en mode adversaire)
    elif note.kind == "hex":
        game.hex_hit += 1  # le moteur compte déjà le raté (précision, combo, vie, animation)
        if deadly(game):
            game.health = 0  # note maudite touchée : mort immédiate


def on_note_miss(game, note):
    if not mine(game):
        return
    if note.kind == "candy":
        game.health = 0 if deadly(game) else game.health - 8  # note obligatoire ratée : mort immédiate en Hard/Nightmare


def on_note_avoided(game, note):
    if not mine(game):
        return
    """Appelé quand une note `avoid` passe sans être touchée : bon réflexe, un peu de vie en bonus."""
    game.health = min(100, game.health + 5)


def on_song_end(game):
    if not mine(game):
        return
    song = game.song.song_id
    if game.candy_total and game.candy_hit == game.candy_total:
        game.unlock_achievement("trick-or-treat")
    if game.hex_total and game.hex_hit == 0:
        game.unlock_achievement("no-hex")
    if game.difficulty == "nightmare":
        game.unlock_achievement("nightmare-fuel")
    if song == "pumpkin-moon-panic" and game.misses == 0:
        game.unlock_achievement("lemon-squeezed")
    done = getattr(game.app, "halloween_done", set())
    done.add(song)
    game.app.halloween_done = done
    if done >= SONGS:
        game.unlock_achievement("spooky-season")
