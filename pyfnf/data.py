from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


BASE_WEEK_ORDER = ["tutorial", "week1", "week2", "week3", "week4", "week5", "week6", "week7", "weekend1", "sserafim"]


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
    mod: str = ""
    album: str = ""
    preview_start: float = 0.0


@dataclass
class WeekInfo:
    week_id: str
    name: str
    background: str
    title_asset: str
    songs: list[str]
    mod: str = ""
    props: list = field(default_factory=list)


class FunkinData:
    """Index des chansons et semaines. `roots` = dossiers des mods actifs puis le jeu de base."""

    def __init__(self, roots: Path | list[Path], mod_names: dict[Path, str] | None = None):
        self.roots = [roots] if isinstance(roots, Path) else list(roots)
        self.root = self.roots[-1]
        self.mod_names = mod_names or {}
        self.songs: dict[str, SongInfo] = {}
        self.weeks: list[WeekInfo] = []
        # Problèmes trouvés dans les mods (affichés dans l'écran MODS) : {dossier du mod: [(texte FR, texte EN)]}.
        self.warnings: dict[Path, list[tuple[str, str]]] = {}
        # Le jeu de base d'abord, puis les mods : un mod qui reprend un id remplace l'original.
        for root in reversed(self.roots):
            self._load_songs(root)
        self._load_weeks()

    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def _has_audio(self, song_id: str) -> bool:
        return any((root / "songs" / song_id).is_dir() and any((root / "songs" / song_id).glob("Inst*.ogg")) for root in self.roots)

    def _load_songs(self, root: Path) -> None:
        songs_root = root / "data" / "songs"
        if not songs_root.is_dir():
            return
        for directory in sorted(path for path in songs_root.iterdir() if path.is_dir()):
            metadata_files = sorted(directory.glob("*-metadata*.json"), key=lambda p: len(p.name))
            if not metadata_files:
                continue
            base_meta = next((path for path in metadata_files if path.name == f"{directory.name}-metadata.json"), metadata_files[0])
            try:
                metadata = self._read(base_meta)
            except (OSError, ValueError):
                continue
            play = metadata.get("playData", {})
            characters = play.get("characters", {})
            time_changes = metadata.get("timeChanges") or [{}]
            info = SongInfo(
                song_id=directory.name,
                name=metadata.get("songName", directory.name.replace("-", " ").title()),
                artist=metadata.get("artist", "Unknown"),
                stage=play.get("stage", "mainStage"),
                player=characters.get("player", "bf"),
                opponent=characters.get("opponent", "dad"),
                # Pas de GF déclarée = pas de GF (Tutorial : GF est l'adversaire).
                girlfriend=characters.get("girlfriend", ""),
                bpm=float(time_changes[0].get("bpm", 100)),
                mod=self.mod_names.get(root, ""),
                album=str(play.get("album", "")),
                preview_start=float(play.get("previewStart", 0) or 0),
            )
            for chart_path in sorted(directory.glob("*-chart*.json")):
                try:
                    chart = self._read(chart_path)
                except (OSError, ValueError):
                    continue
                variation = chart_path.stem.removeprefix(f"{directory.name}-chart").removeprefix("-")
                metadata_path = directory / f"{directory.name}-metadata{'-' + variation if variation else ''}.json"
                try:
                    variation_metadata = self._read(metadata_path) if metadata_path.is_file() else metadata
                except (OSError, ValueError):
                    variation_metadata = metadata
                variation_play = variation_metadata.get("playData", {})
                variation_characters = variation_play.get("characters", {})
                player = variation_characters.get("player", info.player)
                opponent = variation_characters.get("opponent", info.opponent)
                bpm_changes = [(float(change.get("t", 0)), float(change.get("bpm", info.bpm)))
                               for change in variation_metadata.get("timeChanges") or [] if "bpm" in change]
                listed = {str(name).lower() for name in variation_play.get("difficulties") or []}
                # Chart tout neuf (aucune note nulle part, ex. « + NOUVELLE CHANSON » de l'éditeur) : ses difficultés vides
                # restent listées, sinon la chanson serait invisible et impossible à charter dans le jeu.
                brand_new = not any(chart.get("notes", {}).values())
                for difficulty, chart_notes in chart.get("notes", {}).items():
                    # Charts internes (« picospeaker » : les tirs de Pico/Otis) absents des difficultés de la métadonnée : pas jouables.
                    if (not chart_notes and not brand_new) or (listed and difficulty.lower() not in listed):
                        continue
                    label = f"{difficulty}:{variation}" if variation else difficulty
                    info.charts[label] = (chart_path, difficulty)
                    info.profiles[label] = {
                        "stage": variation_play.get("stage", info.stage),
                        "player": player,
                        "opponent": opponent,
                        "girlfriend": variation_characters.get("girlfriend", info.girlfriend),
                        "player_vocals": variation_characters.get("playerVocals", [player]),
                        "opponent_vocals": variation_characters.get("opponentVocals", [opponent]),
                        "note_style": variation_play.get("noteStyle", "funkin"),
                        "bpm_changes": bpm_changes or [(0.0, info.bpm)],
                        "rating": int((variation_play.get("ratings") or {}).get(difficulty, 0) or 0),
                        "album": str(variation_play.get("album", info.album) or ""),  # chaque variation a son album
                    }
            if info.charts and self._has_audio(info.song_id):
                self.songs[info.song_id] = info
            else:
                fr, en = self._song_problem(info.song_id)
                self._warn(root, f"Chanson « {info.song_id} » ignorée : {fr}", f"Song \"{info.song_id}\" skipped: {en}")

    def _load_weeks(self) -> None:
        found: dict[str, tuple[Path, Path]] = {}
        for root in reversed(self.roots):
            for path in sorted((root / "data" / "levels").glob("*.json")):
                found[path.stem] = (path, root)
        ordered = [week for week in BASE_WEEK_ORDER if week in found]
        ordered += sorted(week for week in found if week not in BASE_WEEK_ORDER)
        # Les semaines des mods passent après celles du jeu de base.
        ordered.sort(key=lambda week: found[week][1] != self.root)
        for week_id in ordered:
            path, root = found[week_id]
            try:
                data = self._read(path)
            except (OSError, ValueError) as error:
                self._warn(root, f"data/levels/{path.name} : JSON illisible ({error})", f"data/levels/{path.name}: unreadable JSON ({error})")
                continue
            if data.get("visible") is False:
                continue
            for song in data.get("songs", []):
                if song not in self.songs:
                    fr, en = self._song_problem(str(song))
                    self._warn(root, f"Semaine « {week_id} », chanson « {song} » : {fr}", f"Week \"{week_id}\", song \"{song}\": {en}")
            songs = [song for song in data.get("songs", []) if song in self.songs]
            if not songs:
                self._warn(root, f"Semaine « {week_id} » cachée : aucune de ses chansons n'est utilisable.",
                           f"Week \"{week_id}\" hidden: none of its songs can be played.")
            if songs:
                self.weeks.append(WeekInfo(
                    week_id=week_id,
                    name=data.get("name", week_id.upper()),
                    background=data.get("background", "#F9CF51"),
                    title_asset=data.get("titleAsset", f"storymenu/titles/{week_id}"),
                    songs=songs,
                    mod=self.mod_names.get(root, ""),
                    props=data.get("props") or [],
                ))

    def _warn(self, root: Path, fr: str, en: str) -> None:
        if root != self.root:  # seulement pour les mods
            self.warnings.setdefault(root, []).append((fr, en))

    def _song_problem(self, song: str) -> tuple[str, str]:
        """Ce qui manque pour qu'une chanson soit jouable (premier problème trouvé), en français et en anglais."""
        folders = [root / "data" / "songs" / song for root in self.roots if (root / "data" / "songs" / song).is_dir()]
        base = f"data/songs/{song}/{song}"
        if not folders:
            return (f"introuvable, il manque le dossier data/songs/{song}/ avec {song}-metadata.json et {song}-chart.json.",
                    f"not found, the folder data/songs/{song}/ with {song}-metadata.json and {song}-chart.json is missing.")
        if not any(folder.glob("*-metadata*.json") for folder in folders):
            return f"il manque {base}-metadata.json.", f"{base}-metadata.json is missing."
        charts = [chart for folder in folders for chart in folder.glob("*-chart*.json")]
        if not charts:
            return f"il manque {base}-chart.json.", f"{base}-chart.json is missing."
        for path in [*charts, *(meta for folder in folders for meta in folder.glob("*-metadata*.json"))]:
            try:
                self._read(path)
            except (OSError, ValueError) as error:
                return f"{path.name} : JSON illisible ({error}).", f"{path.name}: unreadable JSON ({error})."
        if not self._has_audio(song):
            return (f"il manque la musique songs/{song}/Inst.ogg (et Voices-*.ogg pour les voix).",
                    f"the music songs/{song}/Inst.ogg is missing (and Voices-*.ogg for the vocals).")
        return ("aucune difficulté avec des notes dans le chart (\"notes\": {\"normal\": [...]}).",
                "no difficulty with notes in the chart (\"notes\": {\"normal\": [...]}).")

    def load_chart(self, song: SongInfo, chart_key: str) -> dict:
        path, difficulty = song.charts[chart_key]
        data = self._read(path)
        notes = []
        for raw in data.get("notes", {}).get(difficulty, []):
            direction = int(raw.get("d", 0))
            notes.append({
                "time": float(raw.get("t", 0)),
                "lane": direction % 4,
                "player": direction % 8 < 4,
                "length": max(0.0, float(raw.get("l", 0) or 0)),
                "kind": str(raw.get("k") or ""),
            })
        notes.sort(key=lambda note: note["time"])
        speeds = data.get("scrollSpeed", {})
        speed = speeds.get(difficulty, speeds.get("default", 1.5)) if isinstance(speeds, dict) else speeds
        return {
            "notes": notes,
            "events": data.get("events", []),
            "scroll_speed": float(speed),
            "difficulty": difficulty,
            "variation": path.stem.removeprefix(f"{song.song_id}-chart").removeprefix("-"),
            "profile": song.profiles.get(chart_key, {
                "stage": song.stage, "player": song.player, "opponent": song.opponent,
                "girlfriend": song.girlfriend, "player_vocals": [song.player], "opponent_vocals": [song.opponent],
                "note_style": "funkin", "bpm_changes": [(0.0, song.bpm)],
            }),
        }

    def common_difficulties(self, song_ids: list[str]) -> list[str]:
        if not song_ids:
            return []
        sets = [set(self.songs[song].charts) for song in song_ids if song in self.songs]
        common = set.intersection(*sets) if sets else set()
        return sorted(common, key=difficulty_sort_key)


def difficulty_sort_key(key: str) -> tuple[int, str, str]:
    difficulty, _, variation = key.partition(":")
    order = {"easy": 0, "normal": 1, "hard": 2, "erect": 3, "nightmare": 4}
    return order.get(difficulty, 10), variation, key
