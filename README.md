# FNF Python Engine

A Friday Night Funkin' engine written in **Python** with pygame. It reads the data and assets of Friday Night Funkin' (V-Slice charts, Sparrow spritesheets, Adobe Animate atlases, stages, weeks) and plays them natively, without Haxe or `Funkin.exe`.

**Current version: 1.0.0**. Download the ready-to-play Windows build from the [Releases](https://github.com/DJCreeperYTB/FNF-Python-Engine/releases) page.

## Features (V1.0)

- Title screen with the `Freaky Menu` music
- Main menu with the original animated sprites
- Story Mode: every week found in the game data
- Freeplay: every song with an `Inst` track, with its variations and difficulties
- Modern V-Slice charts (`notes`, `events`, `scrollSpeed`)
- `Inst` and multiple `Voices` tracks played in sync
- Adobe Animate atlas characters rebuilt and animated in Python
- Sparrow/XML spritesheets for the UI, arrows and notes
- Stages built from `data/stages`
- Normal and hold notes, score, combo, accuracy, misses and health bar
- Countdown, ratings, pause, results screen and week playlists
- Remappable keys, audio offset, volume and an audio calibration tool

## Play

1. Download `FNF-Python-Engine-v1.0.0-Windows.zip` from the latest release.
2. Extract it anywhere.
3. Run `FNF Python.exe`.

## Run from source

```powershell
python -m pip install -r requirements.txt
python main.py
```

The source code does not include the game assets. Put a `fnf_assets/` folder next to `main.py` containing the `assets/` folder of your Friday Night Funkin' copy, with the content of `assets/preload/` placed at the root of `fnf_assets/`.

## Controls

- Menus: arrow keys or `WASD`, `Enter` to confirm, `Escape` to go back
- Gameplay: `D F J K` or the arrow keys (remappable in `Options > Controls`)
- In game: `R` restarts the song, `Escape` pauses
- Results: `Enter` continue, `R` retry, `Escape` menu

Settings are saved in `%APPDATA%\FNF Python\settings.json`.

## Credits

- FNF Python Engine by **DJCreeperYTB**
- Friday Night Funkin' by **The Funkin' Crew**: all game assets (art, music, characters) belong to them

---

# FNF Python Engine (français)

Un moteur Friday Night Funkin' écrit en **Python** avec pygame. Il lit directement les données et les assets de Friday Night Funkin' (charts V-Slice, spritesheets Sparrow, atlas Adobe Animate, scènes, semaines) et les fait tourner nativement, sans Haxe ni `Funkin.exe`.

**Version actuelle : 1.0.0**. Le jeu prêt à lancer pour Windows se télécharge dans les [Releases](https://github.com/DJCreeperYTB/FNF-Python-Engine/releases).

## Jouer

1. Télécharge `FNF-Python-Engine-v1.0.0-Windows.zip` dans la dernière release.
2. Extrais-le où tu veux.
3. Lance `FNF Python.exe`.

## Lancer depuis le code source

```powershell
python -m pip install -r requirements.txt
python main.py
```

Le code source ne contient pas les assets du jeu : place à côté de `main.py` un dossier `fnf_assets/` qui contient le dossier `assets/` de ta copie de Friday Night Funkin', avec le contenu de `assets/preload/` à la racine de `fnf_assets/`.

## Contrôles

- Menus : flèches ou `WASD`, `Entrée` pour valider, `Échap` pour revenir
- Partie : `D F J K` ou les flèches (modifiables dans `Options > Controls`)
- En partie : `R` recommence la chanson, `Échap` met en pause
- Résultats : `Entrée` continuer, `R` rejouer, `Échap` menu

Les réglages sont sauvegardés dans `%APPDATA%\FNF Python\settings.json`.
