"""Manettes (Xbox, PlayStation, Switch... via SDL GameController).

Chaque bouton devient une touche du clavier, selon l'écran :
- en partie : croix directionnelle et X / A / Y / B (modifiables dans Options > Touches) = les 4 flèches, Start = pause ;
- dans les menus : croix ou stick gauche = flèches, A = Entrée, B = Échap, Start = Entrée,
  X = Tab (Pico Mix en freeplay), Y = Ctrl (modificateurs en freeplay), LB / RB = gauche / droite.
Les écrans n'ont donc rien à savoir des manettes.
"""
from __future__ import annotations

import pygame

try:
    from pygame._sdl2 import controller as sdl_controller
except ImportError:  # pygame trop ancien : pas de manette, le clavier marche toujours
    sdl_controller = None

BUTTON_EVENTS = (getattr(pygame, "CONTROLLERBUTTONDOWN", -1), getattr(pygame, "CONTROLLERBUTTONUP", -1))
OTHER_EVENTS = (getattr(pygame, "CONTROLLERAXISMOTION", -1), getattr(pygame, "CONTROLLERDEVICEADDED", -1),
                getattr(pygame, "CONTROLLERDEVICEREMOVED", -1))
DEADZONE = 16000

DPAD = {pygame.CONTROLLER_BUTTON_DPAD_LEFT: pygame.K_LEFT, pygame.CONTROLLER_BUTTON_DPAD_DOWN: pygame.K_DOWN,
        pygame.CONTROLLER_BUTTON_DPAD_UP: pygame.K_UP, pygame.CONTROLLER_BUTTON_DPAD_RIGHT: pygame.K_RIGHT}
LANE_KEYS = (pygame.K_LEFT, pygame.K_DOWN, pygame.K_UP, pygame.K_RIGHT)
PAUSE = {pygame.CONTROLLER_BUTTON_START: pygame.K_ESCAPE, pygame.CONTROLLER_BUTTON_BACK: pygame.K_ESCAPE}
RESERVED = (pygame.CONTROLLER_BUTTON_START, pygame.CONTROLLER_BUTTON_BACK, pygame.CONTROLLER_BUTTON_GUIDE)
DEFAULT_LANES = (pygame.CONTROLLER_BUTTON_X, pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_Y, pygame.CONTROLLER_BUTTON_B)
# shortcut: gâchettes LT/RT (axes) non assignables, à ajouter si quelqu'un le demande.
BUTTON_NAMES = {pygame.CONTROLLER_BUTTON_A: "A", pygame.CONTROLLER_BUTTON_B: "B", pygame.CONTROLLER_BUTTON_X: "X",
                pygame.CONTROLLER_BUTTON_Y: "Y", pygame.CONTROLLER_BUTTON_LEFTSHOULDER: "LB",
                pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: "RB", pygame.CONTROLLER_BUTTON_LEFTSTICK: "L3",
                pygame.CONTROLLER_BUTTON_RIGHTSTICK: "R3", pygame.CONTROLLER_BUTTON_DPAD_LEFT: "D-PAD LEFT",
                pygame.CONTROLLER_BUTTON_DPAD_DOWN: "D-PAD DOWN", pygame.CONTROLLER_BUTTON_DPAD_UP: "D-PAD UP",
                pygame.CONTROLLER_BUTTON_DPAD_RIGHT: "D-PAD RIGHT"}


def button_name(button: int) -> str:
    return BUTTON_NAMES.get(button, f"BUTTON {button}")
MENUS = {**DPAD, pygame.CONTROLLER_BUTTON_A: pygame.K_RETURN, pygame.CONTROLLER_BUTTON_B: pygame.K_ESCAPE,
         pygame.CONTROLLER_BUTTON_START: pygame.K_RETURN, pygame.CONTROLLER_BUTTON_BACK: pygame.K_ESCAPE,
         pygame.CONTROLLER_BUTTON_X: pygame.K_TAB, pygame.CONTROLLER_BUTTON_Y: pygame.K_LCTRL,
         pygame.CONTROLLER_BUTTON_LEFTSHOULDER: pygame.K_LEFT, pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: pygame.K_RIGHT}


def in_gameplay(state) -> bool:
    """Une chanson en cours, sans pause ni dialogue/vidéo : les boutons jouent les notes."""
    return hasattr(state, "hit_lane") and not getattr(state, "paused", False) and not getattr(state, "overlays", None)


def key_event(kind: int, key: int) -> pygame.event.Event:
    return pygame.event.Event(kind, key=key, mod=0, unicode="", scancode=0)


class Gamepads:
    def __init__(self, settings=None):
        self.settings = settings  # pad_binds : boutons des 4 flèches choisis dans Options > Touches
        self.pads: dict[int, object] = {}
        self.held: dict[tuple[int, int], int] = {}  # (manette, bouton) -> touche envoyée, pour relâcher la bonne
        self.stick: dict[tuple[int, int], int | None] = {}  # (manette, axe) -> flèche tenue par le stick
        if sdl_controller is None:
            return
        try:
            sdl_controller.init()
            for index in range(sdl_controller.get_count()):
                self._open(index)
        except pygame.error:
            pass

    def _open(self, index: int) -> None:
        try:
            if sdl_controller and sdl_controller.is_controller(index):
                pad = sdl_controller.Controller(index)
                self.pads[pad.id] = pad
        except pygame.error:
            pass

    def gameplay(self) -> dict[int, int]:
        lanes = getattr(self.settings, "pad_binds", DEFAULT_LANES)
        return {**DPAD, **{button: LANE_KEYS[lane] for lane, button in enumerate(lanes)}, **PAUSE}

    @staticmethod
    def handles(event: pygame.event.Event) -> bool:
        return event.type in BUTTON_EVENTS or event.type in OTHER_EVENTS

    def translate(self, event: pygame.event.Event, state) -> list[pygame.event.Event]:
        """Événement manette -> événements clavier équivalents (liste vide si rien à faire)."""
        if event.type == getattr(pygame, "CONTROLLERDEVICEADDED", -1):
            self._open(event.device_index)
            return []
        if event.type == getattr(pygame, "CONTROLLERDEVICEREMOVED", -1):
            self.pads.pop(getattr(event, "instance_id", -1), None)
            return []
        pad = getattr(event, "instance_id", 0)
        if event.type == BUTTON_EVENTS[0]:
            if getattr(state, "pad_listening", False):  # écran Touches : le bouton est capturé tel quel
                state.pad_button(event.button)
                return []
            key = (self.gameplay() if in_gameplay(state) else MENUS).get(event.button)
            if key is None:
                return []
            self.held[(pad, event.button)] = key
            return [key_event(pygame.KEYDOWN, key)]
        if event.type == BUTTON_EVENTS[1]:
            key = self.held.pop((pad, event.button), None)
            return [key_event(pygame.KEYUP, key)] if key is not None else []
        if event.type == OTHER_EVENTS[0] and event.axis in (pygame.CONTROLLER_AXIS_LEFTX, pygame.CONTROLLER_AXIS_LEFTY):
            horizontal = event.axis == pygame.CONTROLLER_AXIS_LEFTX
            wanted = None
            if event.value <= -DEADZONE:
                wanted = pygame.K_LEFT if horizontal else pygame.K_UP
            elif event.value >= DEADZONE:
                wanted = pygame.K_RIGHT if horizontal else pygame.K_DOWN
            current = self.stick.get((pad, event.axis))
            if wanted == current:
                return []
            self.stick[(pad, event.axis)] = wanted
            events = [key_event(pygame.KEYUP, current)] if current is not None else []
            if wanted is not None:
                events.append(key_event(pygame.KEYDOWN, wanted))
            return events
        return []


if __name__ == "__main__":  # auto-test sans manette : python -m pyfnf.gamepad
    pygame.init()

    class Menu: pass

    class Play:
        paused, overlays = False, []
        def hit_lane(self, lane): pass

    pads = Gamepads()
    down = lambda button: pygame.event.Event(BUTTON_EVENTS[0], instance_id=0, button=button)
    up = lambda button: pygame.event.Event(BUTTON_EVENTS[1], instance_id=0, button=button)
    assert pads.translate(down(pygame.CONTROLLER_BUTTON_A), Menu())[0].key == pygame.K_RETURN
    assert pads.translate(up(pygame.CONTROLLER_BUTTON_A), Play())[0].key == pygame.K_RETURN  # relâche la touche envoyée
    assert pads.translate(down(pygame.CONTROLLER_BUTTON_A), Play())[0].key == pygame.K_DOWN
    assert pads.translate(down(pygame.CONTROLLER_BUTTON_START), Play())[0].key == pygame.K_ESCAPE
    class Binds: pad_binds = [pygame.CONTROLLER_BUTTON_LEFTSHOULDER, pygame.CONTROLLER_BUTTON_A,
                              pygame.CONTROLLER_BUTTON_Y, pygame.CONTROLLER_BUTTON_B]
    custom = Gamepads(Binds())
    assert custom.translate(down(pygame.CONTROLLER_BUTTON_LEFTSHOULDER), Play())[0].key == pygame.K_LEFT
    assert custom.translate(down(pygame.CONTROLLER_BUTTON_X), Play()) == []  # X n'est plus une flèche

    class Listening:
        pad_listening, got = True, None
        def pad_button(self, button): self.got = button
    listening = Listening()
    assert pads.translate(down(pygame.CONTROLLER_BUTTON_RIGHTSTICK), listening) == [] and listening.got == pygame.CONTROLLER_BUTTON_RIGHTSTICK
    stick = pygame.event.Event(OTHER_EVENTS[0], instance_id=0, axis=pygame.CONTROLLER_AXIS_LEFTY, value=-30000)
    assert [e.key for e in pads.translate(stick, Menu())] == [pygame.K_UP]
    back = pygame.event.Event(OTHER_EVENTS[0], instance_id=0, axis=pygame.CONTROLLER_AXIS_LEFTY, value=0)
    assert [(e.type, e.key) for e in pads.translate(back, Menu())] == [(pygame.KEYUP, pygame.K_UP)]
    print("gamepad ok,", len(pads.pads), "manette(s) branchée(s)")
