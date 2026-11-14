"""Écran AIDE : arbre de questions -> page du guide PDF (ouvert dans Edge/Chrome à la bonne page)."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pygame

from .menus import ListMenu
from .mods import mods_dir
from .ui import HEIGHT

# Noeud = (label FR, label EN, phrase FR, phrase EN, cible). Cible = n° de section du guide ("13.2") ou liste de noeuds.
TREE = [
    ("MA CHANSON", "MY SONG", "Elle n'apparaît pas, n'a pas de son, mauvais tempo...", "Missing, silent, wrong tempo...", [
        ("DANS FREEPLAY", "IN FREEPLAY", "Les fichiers qu'il faut (chart, audio, métadonnées) et F5 dans MODS.", "The files you need (chart, audio, metadata) and F5 in MODS.", "5"),
        ("DANS LE MODE HISTOIRE", "IN STORY MODE", "Une chanson n'y est que si elle est dans une semaine.", "A song only shows up there if it is in a week.", "6"),
        ("PAS DE SON", "NO SOUND", "Inst.ogg et Voices : noms et dossiers attendus.", "Inst.ogg and Voices: expected names and folders.", "5.1"),
        ("MAUVAIS TEMPO", "WRONG TEMPO", "BPM et changements de tempo (timeChanges).", "BPM and tempo changes (timeChanges).", "5.2"),
        ("DIFFICULTÉS ET VARIATIONS", "DIFFICULTIES AND VARIATIONS", "Easy/hard, version erect, difficulté vide.", "Easy/hard, erect version, empty difficulty.", "5.5"),
        ("MON CHANGEMENT N'APPARAÎT PAS", "MY CHANGE DOESN'T SHOW", "Refaire le zip, F5, priorité des mods.", "Re-zip, F5, mod priority.", "15.3"),
    ]),
    ("MON PERSONNAGE", "MY CHARACTER", "Placement, animations, icônes.", "Placement, animations, icons.", [
        ("EST MAL PLACÉ / DÉCALÉ", "IS MISPLACED / OFFSET", "Régler les décalages dans l'éditeur de personnage.", "Fix the offsets in the character editor.", "13.4"),
        ("NE S'ANIME PAS", "DOESN'T ANIMATE", "Les noms d'animations que le moteur cherche.", "The animation names the engine looks for.", "7.3"),
        ("SON ICÔNE DE VIE", "ITS HEALTH ICON", "Créer ou changer l'icône de la barre de vie.", "Create or change the health bar icon.", "7.4"),
        ("SON ICÔNE FREEPLAY", "ITS FREEPLAY ICON", "L'icône pixel et la pochette d'album.", "The pixel icon and the album cover.", "7.5"),
        ("CRÉER UN PERSONNAGE", "CREATE A CHARACTER", "Le fichier JSON et ses champs, pas à pas.", "The JSON file and its fields, step by step.", "7.1"),
    ]),
    ("LE DÉCOR", "THE STAGE", "Scène, props, positions.", "Stage, props, positions.", [
        ("CRÉER UNE SCÈNE", "CREATE A STAGE", "Le fichier de scène et ses champs.", "The stage file and its fields.", "8"),
        ("PLACER LES PROPS", "PLACE PROPS", "Images et décors animés de la scène.", "Images and animated props of the stage.", "8.2"),
        ("PLACER LES PERSONNAGES", "PLACE CHARACTERS", "Positions des personnages dans la scène.", "Where characters stand in the stage.", "8.3"),
        ("L'ÉDITEUR DE SCÈNE", "THE STAGE EDITOR", "Déplacer et régler la caméra à la souris.", "Move things and set the camera with the mouse.", "13.3"),
    ]),
    ("LES NOTES / LE CHART", "NOTES / THE CHART", "Poser des notes, événements, vitesse.", "Placing notes, events, speed.", [
        ("PLACER DES NOTES", "PLACE NOTES", "L'éditeur de chart, à la souris.", "The chart editor, with the mouse.", "13.2"),
        ("ÉVÉNEMENTS DE CAMÉRA", "CAMERA EVENTS", "FocusCamera et les autres événements.", "FocusCamera and the other events.", "5.4"),
        ("VITESSE DES NOTES", "NOTE SPEED", "scrollSpeed et l'événement ScrollSpeed.", "scrollSpeed and the ScrollSpeed event.", "5.3"),
        ("FORMAT DU FICHIER CHART", "CHART FILE FORMAT", "Les champs t, d, l, k du JSON.", "The t, d, l, k fields of the JSON.", "5.3"),
        ("STYLE DES NOTES", "NOTE STYLES", "Changer l'apparence des flèches.", "Change how the arrows look.", "10"),
    ]),
    ("LES SCRIPTS", "SCRIPTS", "Code Python qui modifie le jeu.", "Python code that changes the game.", [
        ("HOOKS DISPONIBLES", "AVAILABLE HOOKS", "La liste des fonctions on_... que le moteur appelle.", "The on_... functions the engine calls.", "12.2"),
        ("L'OBJET GAME", "THE GAME OBJECT", "Ce que ton script peut lire et changer.", "What your script can read and change.", "12.3"),
        ("MON SCRIPT PLANTE", "MY SCRIPT CRASHES", "Le texte rouge et mods/errors.log.", "The red text and mods/errors.log.", "12.6"),
        ("EXEMPLES", "EXAMPLES", "Notes spéciales et effets complets.", "Special notes and complete effects.", "12.4"),
        ("OÙ METTRE UN SCRIPT", "WHERE TO PUT A SCRIPT", "Les dossiers qui comptent.", "The folders that matter.", "12.1"),
    ]),
    ("DIALOGUES / CINÉMATIQUES", "DIALOGUES / CUTSCENES", "Conversations et vidéos.", "Conversations and videos.", [
        ("LANCER UN DIALOGUE", "START A DIALOGUE", "Quand et comment il se déclenche.", "When and how it triggers.", "9.1"),
        ("ÉCRIRE UNE CONVERSATION", "WRITE A CONVERSATION", "Le fichier de dialogue.", "The dialogue file.", "9.2"),
        ("PERSONNAGES ET BULLES", "SPEAKERS AND BOXES", "Les speakers et les boxes.", "Speakers and boxes.", "9.3"),
        ("VIDÉO ET SOUS-TITRES", "VIDEO AND SUBTITLES", "Cinématique vidéo et ses sous-titres.", "Video cutscene and its subtitles.", "9.1b"),
        ("CINÉMATIQUE SCRIPTÉE", "SCRIPTED CUTSCENE", "Une cinématique pilotée par un script.", "A cutscene driven by a script.", "9.4"),
    ]),
    ("MUSIQUE / AUDIO", "MUSIC / AUDIO", "Fichiers sonores et tempo.", "Sound files and tempo.", [
        ("INST ET VOICES", "INST AND VOICES", "Noms et emplacements des fichiers audio.", "Names and locations of audio files.", "5.1"),
        ("TEMPO (BPM)", "TEMPO (BPM)", "BPM de départ et changements.", "Starting BPM and changes.", "5.2"),
        ("APERÇU DANS FREEPLAY", "FREEPLAY PREVIEW", "Le champ previewStart.", "The previewStart field.", "5.2"),
    ]),
    ("LES TROPHÉES", "TROPHIES", "Créer un succès à débloquer.", "Create an achievement to unlock.", "11"),
    ("PREMIERS PAS", "GETTING STARTED", "Installer, créer son premier mod.", "Install, create your first mod.", [
        ("INSTALLER UN MOD", "INSTALL A MOD", "Dossier ou .zip, menu MODS, priorité.", "Folder or .zip, MODS menu, priority.", "2"),
        ("CRÉER MON PREMIER MOD", "CREATE MY FIRST MOD", "mod.json et le cycle de travail.", "mod.json and the work cycle.", "3"),
        ("COMMENT ÇA SE SUPERPOSE", "HOW LAYERING WORKS", "Un mod remplace les fichiers du jeu.", "A mod overrides game files.", "4"),
        ("LE MOD D'EXEMPLE", "THE EXAMPLE MOD", "Chaque fichier expliqué.", "Every file explained.", "14"),
        ("LES OUTILS DE MODDEUR", "MODDER TOOLS", "Les trois éditeurs du menu TOOLS.", "The three editors in the TOOLS menu.", "13"),
    ]),
    ("PARTAGER MON MOD", "SHARE MY MOD", "Zip, tests, problèmes fréquents.", "Zip, tests, common problems.", [
        ("CRÉER LE .ZIP", "CREATE THE .ZIP", "Comment zipper pour que ça marche.", "How to zip so it works.", "15.1"),
        ("CHECKLIST DE TEST", "TEST CHECKLIST", "À vérifier avant d'envoyer.", "To check before you send it.", "15.2"),
        ("PROBLÈMES FRÉQUENTS (FAQ)", "COMMON PROBLEMS (FAQ)", "Les pannes les plus courantes.", "The most common failures.", "15.3"),
    ]),
]


def _browser() -> str | None:
    for var in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(var)
        for sub in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
            if base and (Path(base) / sub).is_file():
                return str(Path(base) / sub)
    return None


def launch(args: list[str]) -> None:
    """Lance sans bloquer (remplacée par un faux dans les tests)."""
    subprocess.Popen(args, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0), close_fds=True)


def guide_page(lang: str, section: str) -> int | None:
    try:
        return json.loads((mods_dir() / f"guide_pages_{lang}.json").read_text(encoding="utf-8")).get(section)
    except (OSError, ValueError):
        return None


def open_guide(app, section: str) -> str:
    """Ouvre le guide à la page de la section. Renvoie un message à afficher si la page n'a pas pu être ciblée."""
    fr = app.settings.language == "fr"
    pdf = mods_dir() / ("Guide de modding - Python Engine.pdf" if fr else "Modding Guide - Python Engine.pdf")
    if not pdf.is_file():
        return f"{pdf.name} " + ("introuvable" if fr else "not found")
    page = guide_page("fr" if fr else "en", section) or 2  # section inconnue : table des matières (page 2)
    try:
        exe = _browser()
        if exe:
            launch([exe, f"{pdf.as_uri()}#page={page}"])
            return ""
        os.startfile(pdf)
    except (OSError, AttributeError):
        return str(pdf)
    return (f"Page {page} du PDF : lis la section {section}" if fr else f"PDF page {page}: read section {section}")


class HelpState(ListMenu):
    TINT = (255, 214, 120)
    ROW = dict(x=90, height=50, spacing=80, center_y=340)

    def __init__(self, app, back):
        super().__init__(app)
        self.back, self.nodes = back, TREE
        self.path, self.stack = [], []  # noeuds choisis / sélections des niveaux parents

    def fr(self) -> bool:
        return self.app.settings.language == "fr"

    def label(self, node) -> str:
        return node[0] if self.fr() else node[1]

    def entries(self) -> list:
        return self.nodes

    def choose(self) -> None:
        node = self.nodes[self.selected]
        self.app.confirm_sound()
        if isinstance(node[4], list):
            self.path.append(node); self.stack.append(self.selected)
            self.nodes, self.selected, self.scroll = node[4], 0, 0.0
        else:
            message = open_guide(self.app, node[4])
            if message:
                self.notify(message)

    def up(self) -> None:
        self.app.cancel_sound()
        if not self.path:
            self.app.change(self.back() if callable(self.back) else self.back)
            return
        self.path.pop()
        self.nodes = self.path[-1][4] if self.path else TREE
        self.selected = self.stack.pop()

    def event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            self.move(-event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            row = round((event.pos[1] - self.ROW["center_y"]) / self.ROW["spacing"] + self.scroll)
            if 0 <= row < len(self.nodes) and 150 < event.pos[1] < HEIGHT - 100:
                self.selected = row; self.choose()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self.up()
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.move(-1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.move(1)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.choose()
            elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.up()

    def draw(self, screen: pygame.Surface) -> None:
        self.background(screen)
        self.draw_rows(screen, [self.label(n) for n in self.nodes], max_width=1100, **self.ROW)
        self.title(screen, "HELP")
        node = self.nodes[self.selected]
        desc = node[2] if self.fr() else node[3]
        if isinstance(node[4], str):
            desc += f"   [{node[4]}]"
        hint = "↑↓ CHOISIR     ENTRÉE OUVRIR     ÉCHAP RETOUR" if self.fr() else "↑↓ SELECT     ENTER OPEN     ESC BACK"
        self.draw_footer(screen, hint, desc)


def open_help(app, return_state) -> None:
    """return_state : un état déjà créé, ou une fonction sans argument qui en crée un."""
    app.change(HelpState(app, return_state))
