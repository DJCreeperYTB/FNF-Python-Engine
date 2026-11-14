"""Annonces du menu principal (bouton parchemin) et vérification des mises à jour sur GitHub."""
from __future__ import annotations

import json
import threading
import urllib.request

REPO = "DJCreeperYTB/FNF-Python-Engine"
RELEASES = f"https://github.com/{REPO}/releases"

# Texte des annonces : « # » = titre de section, « - » = puce, « @img chemin » = image, ligne vide = espace.
# Texte des annonces : « # » = titre de section, « - » = puce, « @img chemin » = image, ligne vide = espace.
ANNOUNCEMENTS = [
    {"id": "v2.0", "title": "PYTHON ENGINE V2.0", "link": RELEASES, "image": "images/news/v2.png",
     "fr": """La V2 est là ! 🎉 C'est la plus grosse mise à jour du moteur : voici tout ce qui change depuis la V1, du plus gros au plus petit.
🎬 Pour rappel, ce moteur a été créé pour ma vidéo YouTube : https://www.youtube.com/watch?v=a-KVglrxrRQ

# 🎮 Les grosses nouveautés
- 🎃 Halloween Night : une semaine bonus complète, livrée comme mod d'exemple. 3 chansons (Cobweb Cadence, Midnight Candlewick, Pumpkin Moon Panic) contre Spooky Kids et Lemon Monster, avec DJCreeper au micro. Chaque chanson a sa version Nightmare avec un chart à elle (escaliers et trilles, notes longues et accords, rafales et jacks), des dialogues doublés avant chaque chanson, une cinématique sous-titrée, des notes spéciales (la note orange à toucher, la violette à éviter) et des effets façon Week 2 : éclairs, pluie, projecteur, zooms.
@img images/news/v2_halloween.png
- 🎵 Freeplay refait : les semaines dans l'ordre, les chansons de mods en bas, la recherche avec F, le côté Pico avec Tab (toutes les Pico Mix), la pochette de l'album de chaque version, la lettre de ton meilleur rang et NIGHTMARE animé.
@img images/news/v2_freeplay.png
- ⚙️ Modificateurs (Ctrl dans le freeplay) : vitesse de la chanson (jusqu'à x4), vitesse de défilement, jouer l'adversaire, jugement facile, mode entraînement et botplay.
@img images/news/v2_modificateurs.png
- 🏁 Les vrais écrans de résultats, avec les animations et la musique de Boyfriend ET de Pico pour chaque rang (de PERFECT à SHIT). En mode histoire, un seul écran à la fin de la semaine avec les totaux.
@img images/news/v2_resultats_pico.png
- 🔊 Les décors comme dans le jeu : Néné est assise sur son enceinte A-Bot dont l'écran affiche des barres de son qui suivent la musique (Otis et toutes les Néné des Pico Mix aussi), Darnell lance ses bombes de peinture que Pico abat, les éclairs tombent au hasard dans la Week 2 et, dans Stress, les soldats de Tankman courent au fond et se font abattre en rythme.
@img images/news/v2_nene_abot.png
@img images/news/v2_soldats.png
- 🏆 15 trophées, avec une notification à chaque déblocage (et ceux des mods).
- ⏸️ Menu pause façon FNF : musique Breakfast, infos de la chanson, changement de difficulté et mode entraînement.
- 🎬 Les cinématiques officielles (Week 7, Weekend 1, Pico Mix) et les dialogues, sous-titrés et traduits en français, avec un mode enfant qui prend les versions censurées.
- 🎮 Manettes Xbox, PlayStation et Switch, et un écran Touches façon FNF où chaque touche du clavier et chaque bouton de la manette se change.
@img images/news/v2_touches.png
- 📣 Menu principal : boutons DONATE et ONLINE, icônes des trophées et de ces annonces, et vérification des mises à jour.

# 🔧 Petits ajouts et corrections
- 🎯 Calibrage audio refait avec les vraies flèches du jeu et la voix de Boyfriend sur chaque temps.
- 🖥️ Plein écran avec F11 (ou Alt+Entrée, ou l'option), qualité d'affichage, limite de FPS.
- ⏩ La vitesse de défilement est une vraie vitesse fixe : choisis 3 et tous les charts défilent à 3 (AUTO garde celle de chaque chanson).
- 🗑️ Option EFFACER LES DONNÉES pour remettre tous les scores à zéro (elle demande confirmation).
- ❌ Ratés comme dans FNF : son, pose de raté, voix coupée, combo « 000 » et note qui continue en transparence.
- 💀 R pour mourir ; la caméra de la mort est centrée sur le personnage.
- ⏳ Écran de chargement avec pourcentage et barre ; volume avec + / - / 0 et la barre officielle.
- 📷 La caméra et l'interface battent la mesure comme dans le jeu officiel (tous les 4 temps), avec une option ZOOMS DE CAMÉRA pour couper ça.
- 🖱️ Le curseur de souris officiel.
- 🧍 Tous les personnages et les décors sont placés avec les règles du jeu officiel : plus personne ne flotte dans les Pico Mix, Darnell, Spirit, Otis et le public de la Week 5 sont à leur place.
- 🔉 Le son des cinématiques n'est plus accéléré ni coupé sur les cartes son 4 canaux ou surround.
- 🐛 Et aussi : lag des éclairs, « ERECT » sous NIGHTMARE, mauvais albums, précision des résultats, volume du mod, lettre de rang des Pico Mix, et bien d'autres.

# 🧩 Pour les moddeurs
- 📁 Mods en dossier ou en .zip, à activer ou désactiver dans le menu MODS (créer, ouvrir le dossier, recharger).
- 🐍 Scripts Python : on_create, on_beat, on_note_hit, on_update, on_draw, on_key_down... pour tout changer pendant une chanson.
- ✏️ Éditeurs de chart, de scène et de personnage dans TOOLS (7 en partie ouvre l'éditeur de chart).
@img images/news/v2_editeur.png
- 🧰 Éditeur de chart bien plus complet : sélection multiple (Ctrl + clic ou rectangle, Ctrl+A), copier / couper / coller, recopier d'un côté à l'autre, déplacer, miroir, rétablir (Ctrl+Y), forme d'onde des voix, barre de lecture cliquable, sons d'interface et métronome, et une saisie en direct au clavier (touche L) où une touche tenue fait une note longue.
- 🎛️ Panneau visuel d'événements dans l'éditeur (V ou double-clic) : liste, champs réglables, et les mods ajoutent les leurs avec un simple fichier data/events/<nom>.json.
- 🎥 Événements natifs : ZoomCamera, SetCameraBop, FlashScreen (respecte FLASHING LIGHTS), ShakeCamera, ChangeStage (changer de décor en pleine chanson), en plus de FocusCamera, PlayAnimation (même sur un élément du décor, comme l'éclair de la Week 2), ScrollSpeed et SetHealthIcon.
- 💬 Sous-titres FR / EN pendant les chansons et les cinématiques (fichier subtitles.json, événement Subtitle, game.show_subtitle) : police, taille, couleur, opacité, fond, contour et position réglables.
- 🐍 Nouveautés pour les scripts : game.camera_zoom, bop_rate, flash_screen, shake_camera, strum_offset (décale chaque flèche, les notes suivent), strum_alpha, note.alpha, lane_for_key (remapper les touches), et musique / son de game over par personnage.
- ❓ Écran AIDE (TOOLS > AIDE, H dans MODS, F1 dans l'éditeur) : choisis ton problème et le guide PDF s'ouvre à la bonne page.
- 🎯 Notes spéciales (obligatoire / à éviter), dialogues avec la voix de chaque personnage, vidéos sous-titrées, albums, icônes et trophées de mod.
- 📘 Guide PDF en français et en anglais, et le mod Halloween Night à ouvrir pour voir chaque possibilité en vrai.

🔜 Bientôt : le multijoueur en ligne (ONLINE), les Gameplay Modifiers et une vraie haute définition.""",
     "en": """V2 is here! 🎉 This is the biggest update of the engine: here is everything that changed since V1, from the biggest to the smallest.
🎬 As a reminder, this engine was created for my YouTube video: https://www.youtube.com/watch?v=a-KVglrxrRQ

# 🎮 Big new features
- 🎃 Halloween Night: a full bonus week, shipped as the example mod. 3 songs (Cobweb Cadence, Midnight Candlewick, Pumpkin Moon Panic) against Spooky Kids and Lemon Monster, with DJCreeper on the mic. Each song has a Nightmare version with its own chart (stairs and trills, holds and chords, bursts and jacks), voiced dialogues before each song, a subtitled cutscene, special notes (hit the orange one, avoid the purple one) and Week 2 style effects: lightning, rain, spotlight, zooms.
@img images/news/v2_halloween.png
- 🎵 New freeplay: weeks in order, mod songs at the bottom, search with F, Pico side with Tab (every Pico Mix), album cover for each version, the letter of your best rank and animated NIGHTMARE.
@img images/news/v2_freeplay.png
- ⚙️ Modifiers (Ctrl in freeplay): song speed (up to x4), scroll speed, play as opponent, easy judgment, practice mode and botplay.
@img images/news/v2_modificateurs.png
- 🏁 The real results screens, with the animations and music of Boyfriend AND Pico for every rank (PERFECT to SHIT). In story mode, one screen at the end of the week with the totals.
@img images/news/v2_resultats_pico.png
- 🔊 Stages like the original: Nene sits on her A-Bot speaker whose screen shows sound bars following the music (Otis and every Pico Mix Nene too), Darnell throws his paint cans and Pico shoots them, lightning strikes at random in Week 2 and, in Stress, Tankman's soldiers run in the back and get shot on the beat.
@img images/news/v2_nene_abot.png
@img images/news/v2_soldats.png
- 🏆 15 trophies, with a notification on each unlock (and mod trophies).
- ⏸️ FNF style pause menu: Breakfast music, song info, difficulty change and practice mode.
- 🎬 Official cutscenes (Week 7, Weekend 1, Pico Mix) and dialogues, subtitled, with a child mode that uses the censored versions.
- 🎮 Xbox, PlayStation and Switch controllers, and an FNF style Controls screen where every keyboard key and controller button can be changed.
@img images/news/v2_touches.png
- 📣 Main menu: DONATE and ONLINE buttons, trophy and news icons, and an update check.

# 🔧 Small additions and fixes
- 🎯 Audio calibration redone with the game's latency arrows and Boyfriend's voice on every beat.
- 🖥️ Fullscreen with F11 (or Alt+Enter, or the option), display quality, FPS limit.
- ⏩ Scroll speed is a real fixed speed: pick 3 and every chart scrolls at 3 (AUTO keeps each song's speed).
- 🗑️ CLEAR DATA option to reset every score (it asks first).
- ❌ FNF style misses: sound, miss pose, muted vocals, "000" combo and the note keeps going, faded.
- 💀 R to die; the death camera is centered on the character.
- ⏳ Loading screen with a percentage and a bar; volume with + / - / 0 and the official tray.
- 📷 The camera and the interface bump to the beat like the official game (every 4 beats), with a CAMERA ZOOMS option to turn it off.
- 🖱️ The official mouse cursor.
- 🧍 Every character and prop is placed with the rules of the official game: nobody floats in the Pico Mixes anymore, Darnell, Spirit, Otis and the Week 5 crowd are in their place.
- 🔉 Cutscene sound is no longer sped up or cut on 4-channel or surround sound cards.
- 🐛 And also: lightning lag, "ERECT" under NIGHTMARE, wrong albums, results accuracy, mod volume, Pico Mix rank letters, and much more.

# 🧩 For modders
- 📁 Mods as folders or .zip files, enabled or disabled in the MODS menu (create, open the folder, reload).
- 🐍 Python scripts: on_create, on_beat, on_note_hit, on_update, on_draw, on_key_down... to change anything during a song.
- ✏️ Chart, stage and character editors in TOOLS (7 in a song opens the chart editor).
@img images/news/v2_editeur.png
- 🧰 A much fuller chart editor: multiple selection (Ctrl+click or rectangle, Ctrl+A), copy / cut / paste, copy from one side to the other, move, mirror, redo (Ctrl+Y), voice waveforms, a clickable playback bar, interface sounds and metronome, and live keyboard input (L key) where a held key makes a long note.
- 🎛️ Visual event panel in the editor (V or double-click): list, adjustable fields, and mods add their own with a simple data/events/<name>.json file.
- 🎥 Native events: ZoomCamera, SetCameraBop, FlashScreen (respects FLASHING LIGHTS), ShakeCamera, ChangeStage (change the stage mid-song), on top of FocusCamera, PlayAnimation (even on a stage element, like the Week 2 lightning), ScrollSpeed and SetHealthIcon.
- 💬 FR / EN subtitles during songs and cutscenes (subtitles.json file, Subtitle event, game.show_subtitle): font, size, color, opacity, background, outline and position can be set.
- 🐍 New for scripts: game.camera_zoom, bop_rate, flash_screen, shake_camera, strum_offset (moves each arrow, notes follow), strum_alpha, note.alpha, lane_for_key (remap the keys), and game over music / sound per character.
- ❓ HELP screen (TOOLS > HELP, H in MODS, F1 in the editor): pick your problem and the PDF guide opens at the right page.
- 🎯 Special notes (must hit / avoid), dialogues with each character's voice, subtitled videos, albums, icons and mod trophies.
- 📘 PDF guide in French and English, and the Halloween Night mod to open and see every feature for real.

🔜 Coming soon: online multiplayer (ONLINE), the Gameplay Modifiers and true high definition."""},
    {"id": "vs-djcreeper", "title": "VS DJCREEPER", "link": "https://gamebanana.com/mods/732063", "image": "images/news/vs-djcreeper.png",
     "fr": """Le mod FNF VS DJCreeper est sorti sur GameBanana ! 💚

Chunk City, la nuit. Au cœur du Quartier Spawn, LE BLOC : le club dont les murs sont faits de blocs d'abonnés. Son DJ star ? Un creeper. 💥 Toi, tu as un micro... perds, et il le garde.

# 🎮 Dans la V1 Bêta
- 🎤 Week 1 « CREEPER NIGHT » : Mixtape, Sssound Check et Kaboom, racontée par des dialogues.
@img images/news/djcreeper_mixtape.png
- 🎁 3 chansons bonus en freeplay : Overcharged, Chain Reaction et Bedrock.
- 🔥 Remixes Erect et Nightmare pour les 6 chansons.
- 🗣️ Chanté avec la vraie voix de DJCreeper.
- 🏆 Conversion totale : écran titre, menus, HUD, flèches, résultats avec rangs SS à D, game over et 31 succès.
@img images/news/djcreeper_resultats.png
- 🌍 Français et anglais, guide de premier lancement, vitesse de lecture réglable.

⚠️ Langage vulgaire et flashs lumineux (le guide permet de les réduire).

👉 Appuie sur Entrée pour ouvrir sa page GameBanana.""",
     "en": """The FNF VS DJCreeper mod is out on GameBanana! 💚

Chunk City, at night. In the heart of the Spawn District, THE BLOCK: the club whose walls are made of subscriber blocks. Its star DJ? A creeper. 💥 You have a mic... lose, and he keeps it.

# 🎮 In the V1 Beta
- 🎤 Week 1 "CREEPER NIGHT": Mixtape, Sssound Check and Kaboom, told through dialogues.
@img images/news/djcreeper_mixtape.png
- 🎁 3 bonus songs in freeplay: Overcharged, Chain Reaction and Bedrock.
- 🔥 Erect and Nightmare remixes for all 6 songs.
- 🗣️ Sung with DJCreeper's real voice.
- 🏆 Total conversion: title screen, menus, HUD, arrows, results with SS to D ranks, game over and 31 achievements.
@img images/news/djcreeper_resultats.png
- 🌍 French and English, first launch guide, adjustable playback speed.

⚠️ Strong language and flashing lights (the guide lets you reduce them).

👉 Press Enter to open its GameBanana page."""},
    {"id": "v1.0", "title": "PYTHON ENGINE V1.0", "link": f"{RELEASES}/tag/v1.0.0", "image": "images/news/v1.png",
     "fr": """La toute première version du moteur, sortie le 09/08/2026 ! 🚀
🎬 Ce moteur a été créé pour ma vidéo YouTube : https://www.youtube.com/watch?v=a-KVglrxrRQ
🐍 Un moteur Friday Night Funkin' réécrit en Python, qui lit directement les données du jeu.

# 🎮 Pour les joueurs
- 📖 Mode histoire avec toutes les semaines, et freeplay avec les variantes et les difficultés.
- 🎵 Notes simples et longues, score, combo, précision, ratés et barre de vie.
- ⏱️ Compte à rebours, jugements, pause et écran de résultats.
- ⌨️ Touches modifiables (D F J K ou flèches) et calibrage audio avec un métronome.

# 🧩 Sous le capot
- 📄 Charts V-Slice modernes (notes, événements, vitesse).
- 🎨 Personnages Adobe Animate recomposés en Python, sprites Sparrow et scènes lues depuis les fichiers du jeu.
- 🔊 Instrumentale et voix synchronisées.""",
     "en": """The very first version of the engine, released on 08/09/2026! 🚀
🎬 This engine was created for my YouTube video: https://www.youtube.com/watch?v=a-KVglrxrRQ
🐍 A Friday Night Funkin' engine rewritten in Python, reading the game data directly.

# 🎮 For players
- 📖 Story mode with every week, and freeplay with variations and difficulties.
- 🎵 Normal and hold notes, score, combo, accuracy, misses and health bar.
- ⏱️ Countdown, judgments, pause and results screen.
- ⌨️ Rebindable keys (D F J K or arrows) and audio calibration with a metronome.

# 🧩 Under the hood
- 📄 Modern V-Slice charts (notes, events, speed).
- 🎨 Adobe Animate characters rebuilt in Python, Sparrow sprites and stages read from the game files.
- 🔊 Synced instrumental and vocals."""},
]


def version_tuple(text: str) -> tuple[int, ...]:
    numbers = []
    for part in str(text).lstrip("vV").split("."):
        digits = "".join(char for char in part if char.isdigit())
        numbers.append(int(digits) if digits else 0)
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers[:3])


def check_update(app, current: str) -> None:
    """Demande la dernière release GitHub en arrière-plan ; pose app.update_info si elle est plus récente."""
    def work():
        try:
            request = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest",
                                             headers={"User-Agent": "FNF-Python-Engine", "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(request, timeout=6) as response:
                data = json.loads(response.read().decode("utf-8"))
            tag = str(data.get("tag_name", ""))
            if version_tuple(tag) > version_tuple(current):
                body = str(data.get("body") or "").strip()
                app.update_info = {"id": f"update-{tag}", "title": f"UPDATE {tag}", "link": data.get("html_url") or RELEASES,
                                   "fr": f"🆕 Une nouvelle version ({tag}) est disponible !\n👉 Appuie sur Entrée pour la télécharger.\n\n{body[:600]}",
                                   "en": f"🆕 A new version ({tag}) is available!\n👉 Press Enter to download it.\n\n{body[:600]}"}
        except Exception:
            pass  # hors ligne ou GitHub indisponible : pas d'annonce de mise à jour

    threading.Thread(target=work, daemon=True).start()


def all_news(app) -> list[dict]:
    update = getattr(app, "update_info", None)
    return ([update] if update else []) + ANNOUNCEMENTS


if __name__ == "__main__":  # auto-test : python -m pyfnf.news
    assert version_tuple("v1.0.0") < version_tuple("2.0") < version_tuple("v2.0.1")
    assert version_tuple("v2.0") == version_tuple("2.0.0")
    print("news ok")
