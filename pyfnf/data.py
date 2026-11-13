from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SongInfo:
    song_id: str
    name: str
    artist: str
    stage: str
    player: str
    opponent: str
    girlfriend: str
    bpm: float
    charts: dict[str, tuple[Path, str]] = field(default_factory=dict)
    profiles: dict[str, dict] = field(default_factory=dict)


@dataclass
class WeekInfo:
    week_id: str
    name: str
    background: str
    title_asset: str
    songs: list[str]


class FunkinData:
    def __init__(self, root: Path):
        self.root = root
        self.songs: dict[str, SongInfo] = {}
        self.weeks: list[WeekInfo] = []
        self._load_songs()
        self._load_weeks()

    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def _load_songs(self) -> None:
        songs_root = self.root / "data" / "songs"
        for directory in sorted(path for path in songs_root.iterdir() if path.is_dir()):
            metadata_files = sorted(directory.glob("*-metadata*.json"), key=lambda p: len(p.name))
            if not metadata_files:
                continue
            base_meta = next((path for path in metadata_files if path.name == f"{directory.name}-metadata.json"), metadata_files[0])
            metadata = self._read(base_meta)
            play = metadata.get("playData", {})
            characters = play.get("characters", {})
            time_changes = metadata.get("timeChanges", [{}])
            info = SongInfo(
                song_id=directory.name,
                name=metadata.get("songName", directory.name.replace("-", " ").title()),
                artist=metadata.get("artist", "Kawai Sprite"),
                stage=play.get("stage", "mainStage"),
                player=characters.get("player", "bf"),
                opponent=characters.get("opponent", "dad"),
                girlfriend=characters.get("girlfriend", "gf"),
                bpm=float(time_changes[0].get("bpm", 100)) if time_changes else 100,
            )
            for chart_path in directory.glob("*-chart*.json"):
                try:
                    chart = self._read(chart_path)
                except (OSError, json.JSONDecodeError):
                    continue
                variation = chart_path.stem.removeprefix(f"{directory.name}-chart").removeprefix("-")
                metadata_path = directory / f"{directory.name}-metadata{'-' + variation if variation else ''}.json"
                variation_metadata = self._read(metadata_path) if metadata_path.is_file() else metadata
                variation_play = variation_metadata.get("playData", {})
                variation_characters = variation_play.get("characters", {})
                for difficulty, chart_notes in chart.get("notes", {}).items():
                    if not chart_notes:
                        continue
                    label = f"{difficulty}:{variation}" if variation else difficulty
                    info.charts[label] = (chart_path, difficulty)
                    info.profiles[label] = {
                        "stage": variation_play.get("stage", info.stage),
                        "player": variation_characters.get("player", info.player),
                        "opponent": variation_characters.get("opponent", info.opponent),
                        "girlfriend": variation_characters.get("girlfriend", info.girlfriend),
                        "player_vocals": variation_characters.get("playerVocals", [variation_characters.get("player", info.player)]),
                        "opponent_vocals": variation_characters.get("opponentVocals", [variation_characters.get("opponent", info.opponent)]),
                    }
            audio_directory = self.root / "songs" / directory.name
            if info.charts and audio_directory.is_dir() and any(audio_directory.glob("Inst*.ogg")):
                self.songs[info.song_id] = info

    def _load_weeks(self) -> None:
        order = ["tutorial", "week1", "week2", "week3", "week4", "week5", "week6", "week7", "weekend1", "sserafim"]
        levels_root = self.root / "data" / "levels"
        for week_id in order:
            path = levels_root / f"{week_id}.json"
            if not path.is_file():
                continue
            data = self._read(path)
            songs = [song for song in data.get("songs", []) if song in self.songs]
            if songs:
                self.weeks.append(WeekInfo(
                    week_id=week_id,
                    name=data.get("name", week_id.upper()),
                    background=data.get("background", "#F9CF51"),
                    title_asset=data.get("titleAsset", f"storymenu/titles/{week_id}"),
                    songs=songs,
                ))

    def load_chart(self, song: SongInfo, chart_key: str) -> dict:
        path, difficulty = song.charts[chart_key]
        data = self._read(path)
        notes = []
        for raw in data.get("notes", {}).get(difficulty, []):
            direction = int(raw.get("d", 0))
            notes.append({
                "time": float(raw.get("t", 0)),
                "lane": direction % 4,
                "player": direction < 4,
                "length": max(0.0, float(raw.get("l", 0))),
            })
        notes.sort(key=lambda note: note["time"])
        return {
            "notes": notes,
            "events": data.get("events", []),
            "scroll_speed": float(data.get("scrollSpeed", {}).get(difficulty, 1.5)),
            "difficulty": difficulty,
            "variation": path.stem.removeprefix(f"{song.song_id}-chart").removeprefix("-"),
            "profile": song.profiles.get(chart_key, {
                "stage": song.stage, "player": song.player, "opponent": song.opponent,
                "girlfriend": song.girlfriend, "player_vocals": [song.player], "opponent_vocals": [song.opponent],
            }),
        }

    def common_difficulties(self, song_ids: list[str]) -> list[str]:
        if not song_ids:
            return []
        sets = [set(self.songs[song].charts) for song in song_ids if song in self.songs]
        common = set.intersection(*sets) if sets else set()
        priority = {"easy": 0, "normal": 1, "hard": 2, "erect:erect": 3, "nightmare:erect": 4}
        return sorted(common, key=lambda key: (priority.get(key, 10), key))
