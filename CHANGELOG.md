# Changelog

All notable changes to this project will be documented in this file.

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
