# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2026-11-14

The second major release of FNF Python Engine: mods, tools for modders, trophies and a lot of fixes.

This engine was created for my YouTube video: https://www.youtube.com/watch?v=a-KVglrxrRQ

### Added

- Mods: `mods/` folder (folders or `.zip`), MODS menu to turn them on and off, create an empty mod (`N`), open the folder (`O`), reload (`F5`). A mod can replace any file or add songs, weeks, characters, stages, dialogues, trophies and note styles, and can contain Python scripts.
- Example mod `ExampleMod.zip`: Halloween Night, a custom week with three songs against Spooky Kids and Lemon Monster, DJCreeper as the player, dialogues (English and French), a video cutscene, Nightmare remixes, special notes and Dadbattle-style effects.
- Modding guide (PDF) in the `mods/` folder.
- Chart editor (notes, sustains, camera events, test from the cursor), stage and camera editor, character editor. `7` in a song opens the chart editor.
- Chart editor upgrades: long note up to the end of the cell under the mouse, multiple selection (`Ctrl`+click, `Ctrl`+drag, `Ctrl+A`), copy / cut / paste, copy to the other side (`Ctrl+D`), move, mirror, redo, voice waveforms (`O`), clickable playback bar, live keyboard input (`L`), interface sounds and metronome, help (`F1`).
- Visual event panel in the chart editor (`V` or double-click); mods add their own events with `data/events/<name>.json`.
- HELP screen (TOOLS > HELP, `H` in MODS, `F1` in the editor): opens the PDF guide at the right page.
- Native events `ZoomCamera`, `SetCameraBop`, `FlashScreen` (respects the flashing lights option) , `ShakeCamera` and `ChangeStage` (change the stage mid-song), next to `FocusCamera`, `PlayAnimation` (also on a stage element), `ScrollSpeed` and `SetHealthIcon`.
- FR / EN subtitles during songs and cutscenes (`subtitles.json`, `Subtitle` event, `game.show_subtitle`), with font, size, color, opacity, background, outline and position.
- The camera and the interface bump to the beat like the official game (CAMERA ZOOMS option to turn it off), and the official mouse cursor.
- Script API: `game.camera_zoom`, `bop_rate`, `bop_intensity`, `hud_bop_intensity`, `view_zoom`, `flash_screen()`, `shake_camera()`, `strum_offset`, `strum_alpha`, `note.alpha`, `lane_for_key`; per-character game over sound and music with `death` in `data/characters/<id>.json`.
- 15 trophies inspired by Psych Engine, with an in-game notification.
- Freeplay: songs in the order of the weeks, search bar, Pico Mix with `Tab`, album art, DJ Boyfriend, music preview.
- Modifiers menu (`Ctrl` on a song): scroll speed, song speed (up to x4), play as the opponent, judgment level, practice mode, botplay.
- Week 6 dialogues (V-Slice format), video cutscenes in Story Mode with subtitles, hold-to-skip and a child mode.
- Options: English/French (dialogues included), fixed scroll speed (AUTO keeps each song's speed), hitsounds and their volume, judgment level, FPS limit, display quality, fullscreen (`F11` / `Alt+Enter`), CLEAR DATA with confirmation, flashing lights, FPS counter, downscroll, ghost tapping.
- **Main menu**: a DONATE button, ONLINE (locked, coming later), trophy and news icons with in-game announcements, and an update check on GitHub.
- **Controls**: keyboard and controllers (Xbox, PlayStation, Switch); every key and button can be changed in an FNF-style Controls screen.
- **Audio calibration** with the official latency arrows and Boyfriend's voice on every beat.
- **Results screens** of Boyfriend and Pico for every rank, and one results screen at the end of a week in Story Mode.
- **Stages like the original**: Nene sits on her A-Bot speaker with a working sound visualizer (Otis and every Nene of the Pico Mixes too), Darnell's paint cans, random lightning in Week 2, Tankman's soldiers running and shot in Stress.
- Official-style game over screen and results screen with saved records.
- Volume keys (`+`, `-`, `0`) with the volume bar at the top of the screen.

### Changed

- Menus redone: main menu buttons, Story Mode with animated characters, Freeplay.
- The scroll speed option sets one fixed speed for every chart (AUTO keeps the speed chosen by each song).
- Controls screen and audio calibration redone in the style of the game.
- The official "MISS" popup is used when a note is missed.
- Trophy notifications appear on the left of the screen.

### Fixed

- Characters jumping or changing size between animation frames.
- Broken faces of Mommy Mearest and the parents (Adobe Animate atlases drawn with the real matrix and color effects).
- The camera not following the singing character.
- Characters, Animate atlases and props placed with the rules of the official game (global offsets, whole-timeline bounds, Animate stage matrix, animation offsets scaled): no more floating characters in the Pico Mixes, Darnell and Spirit fixed.
- Cutscene sound on 4-channel or surround sound cards: no more sped-up sound or silence.
- Faster example mod (about 40% less time per frame).
- Opponent hold notes not visible; Week 6 using the normal arrows instead of the pixel ones.
- Tutorial showing GF twice; Blazin' without its combat.
- Inputs not judged at the exact time of the key press; pause during the countdown; countdown not following the BPM.
- Sparrow XML reading (the alphabet no longer crashes), "packer" format (Spirit), long-format Animate atlases.
- Volume of the miss sounds, Story Mode menu overflowing, returning to the right menu after a song.

### Coming later

- Multiplayer and the "Gameplay Modifiers" entry (locked in the menu for now).

## [1.0.0] - 2026-08-09

The first public release of FNF Python Engine!

### Added

- Title screen with the `Freaky Menu` music.
- Main menu with the original animated sprites.
- Story Mode with every week found in the game data.
- Freeplay with every song that has an `Inst` track, including variations and difficulties.
- Support for modern V-Slice charts (`notes`, `events`, `scrollSpeed`).
- `Inst` and multiple `Voices` tracks played in sync.
- Adobe Animate atlas characters, rebuilt and animated in Python.
- Sparrow/XML spritesheets for the UI, arrows and notes.
- Stages built from `data/stages`.
- Normal and hold notes, score, combo, accuracy, misses and health bar.
- Countdown, ratings, pause menu, results screen and week playlists.
- Remappable keys, audio offset, volume and an audio calibration tool (metronome at 120 BPM).
- Settings saved in `%APPDATA%\FNF Python\settings.json`.

### Known issues

- Some characters jump or change size between animation frames.
- Some Adobe Animate characters (Mommy Mearest, the parents) have broken faces.
- The camera does not follow the singing character.
- The opponent's hold notes are not visible.
- Week 6 uses the normal arrows instead of the pixel ones.
