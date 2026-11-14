# English content of the modding guide, part A (chapters 1-8). Executed by build_guide_pdf_en.py (shares its helpers).
H1("1. Introduction")
P("A **mod** is a folder (or a `.zip` file) placed in the `mods/` folder. It contains files that are **added** to the base game or that **replace** its files. You never touch the engine code: everything goes through JSON files, images, sounds and, if you want, Python scripts.")
P("With Python Engine, a mod can:")
BUL("add **songs** (audio, chart, metadata, difficulties, variations) that show up in Freeplay;",
    "add **weeks** for Story Mode, with their animated characters and their title;",
    "add **characters** (Sparrow, packer or Adobe Animate spritesheets) and their health icons;",
    "add **stages** (backgrounds, character positions, camera);",
    "add **dialogues** and **videos** (with subtitles) before and after a Story Mode song;",
    "change the **note style** and add **trophies**;",
    "replace any image, sound or music of the game (menus, background, menu music...);",
    "add **Python scripts** that react to the game: notes, beats, chart events, drawing on screen...")
P("This guide is deliberately practical. It relies on the **example mod** shipped with the engine (`mods/ExampleMod.zip`, sources in `mods_src/ExampleMod/`): three Halloween songs (with their Nightmare remixes), a week, a playable character, a stage, dialogues in two languages, a subtitled video cutscene, special notes, trophies and effect scripts. Everything explained here matches what the engine code really does.")
IMG("v2_menu_main.png", "The main menu: STORY MODE, FREEPLAY, MODS, TROPHIES, TOOLS, OPTIONS.")
NOTE("a mod's scripts are **Python code** run on your computer with all your rights. Only install mods from authors you trust (see chapter 12).")

H1("2. Installing and enabling a mod")
H2("2.1 Where is the mods folder?")
P("The `mods/` folder is **next to the executable** (`FNF Python.exe`) for the compiled version, or **next to `main.py`** if you run the game with Python. It is created automatically if it does not exist. In the MODS menu, the **O** key opens it in the file explorer.")
H2("2.2 A folder or a .zip")
BUL("**Folder**: `mods/MyMod/` with `mod.json` directly inside.",
    "**.zip file**: `mods/MyMod.zip`. `mod.json` must be at the root of the zip, or inside a single folder (when a folder was zipped as is). The engine extracts the zip once into `%APPDATA%\\FNF Python\\mod_cache\\` and extracts it again if the zip changes.",
    "Folders and files whose name starts with `.` or `_` are ignored: handy to put a mod aside.")
H2("2.3 The MODS menu")
IMG("v2_menu_mods.png", "The MODS menu: the list, the icon, the description and the ON / OFF state of the selected mod.")
TABLE(["Key", "Effect"], [
    ["Up / Down (or W / S)", "Choose a mod."],
    ["Enter (or Space)", "Enable / disable the mod. A mod in error (for example missing or unreadable `mod.json`) cannot be enabled: a message explains why."],
    ["N", "Create an empty mod (the template of chapter 3). Also unlocks the Modder trophy."],
    ["O", "Open the `mods/` folder."],
    ["F5", "Reload all mods now."],
    ["Esc", "Back to the main menu. If you enabled, disabled or created a mod, mods are reloaded at that moment."],
], [3, 8])
P("Disabled mods are remembered by **folder or zip name** in your settings.")
H2("2.4 Priority")
P("When two mods provide the same file, the one from the mod with the **highest priority** wins. Priority is the `priority` field of `mod.json` (integer, 0 by default; with equal priority, alphabetical order of the name). The base game always comes last: any active mod can therefore replace a base game file.")
P("The **Editor Saves** folder (next to `mods/`, filled by the editors, see chapter 13) is not a mod: it is always loaded and comes before every mod.")
H2("2.5 Trying the example mod")
P("`mods/ExampleMod.zip` is already installed. Open MODS, check it is ON, go back to the menu, then play **Cobweb** (or one of the other two) in Freeplay, or the **HALLOWEEN NIGHT** week in Story Mode. It has three songs with easy / normal / hard difficulties and their **Nightmare** remix.")
IMG("v2_mod_freeplay.png", "Cobweb in Freeplay: BPM, difficulty, rank letter, and the mod name at the bottom of the screen.")

H1("3. Creating your first mod")
P("In the MODS menu, press **N**. The engine creates `mods/MyMod/` (or `MyMod2`, `MyMod3`... if the name exists) with this structure:")
CODE("""
mods/MyMod/
  mod.json
  data/
    songs/        <- one subfolder per song (metadata + chart)
    levels/       <- weeks (one .json per week)
    characters/   <- one .json per character
    stages/       <- one .json per stage
  songs/          <- audio files: songs/<id>/Inst.ogg ...
  images/
    characters/   <- character spritesheets
  scripts/
    script.py     <- a template script with on_create, on_beat, on_note_hit
""")
P("All these folders are optional and you can add others (`images/icons/`, `data/dialogue/`, `data/achievements/`, `videos/`, `music/`, `sounds/`...). Only `mod.json` is mandatory.")
H2("3.1 mod.json")
CODE("""
{
  "name": "Halloween Night (Example Mod)",
  "description": "Example mod: a Halloween week with 3 songs...",
  "author": "Python Engine",
  "version": "2.0.0",
  "icon": "icon.png",
  "priority": 0
}
""")
TABLE(["Field", "Role", "Default"], [
    ["`name`", "Name shown in the MODS menu (and at the bottom of Freeplay for its songs).", "folder / zip name"],
    ["`description`", "Text of the right-hand panel (line breaks are kept, 6 visible lines).", "empty"],
    ["`author`", "Shown as \"by ...\".", "empty"],
    ["`version`", "Free text, shown as \"v1.0.0\".", "\"1.0.0\""],
    ["`icon`", "Path of an image inside the mod (a square 150 x 150 icon is fine). Missing = no icon.", "\"icon.png\""],
    ["`priority`", "Integer: the higher it is, the more the mod's files win over other mods' files.", "0"],
], [2, 7, 2.4])
P("The file is read as UTF-8 (BOM accepted). If it is invalid, the mod appears as **ERROR** in the menu and cannot be enabled.")
H2("3.2 The work cycle")
BUL("For a **folder** mod, edit your files directly. Characters, stages, dialogues, icons and scripts are re-read every time a song starts: just restart the song.",
    "**New songs, weeks, trophies** and the content of `mod.json` are read when mods are (re)loaded: press **F5** in the MODS menu.",
    "For a **.zip**, you have to rebuild the zip after each change: the engine re-extracts it automatically. Work in a folder, zip at the end.",
    "If something does not work, look at the red text at the top left during the song and at the FAQ of chapter 15.")

H1("4. How layering works")
P("The engine copies nothing: when it looks for a file, it looks **in each active mod first** (by priority order), **then in the base game**. The first file found is used. So:")
BUL("a file with the same relative path **replaces** the base game's one;",
    "a file with a new path is **added**.")
TABLE(["File in your mod", "Effect"], [
    ["`images/menuBG.png`", "Replaces the menu background."],
    ["`music/freakyMenu/freakyMenu.ogg`", "Replaces the menu music."],
    ["`sounds/scrollMenu.ogg`", "Replaces the menu scroll sound."],
    ["`data/characters/bf.json`", "Replaces the Boyfriend definition."],
    ["`data/stages/mainStage.json`", "Replaces the main stage."],
    ["`data/songs/bopeebo/` (metadata + chart)", "Replaces the Bopeebo chart (same id); the base game audio is still used."],
], [5, 6])
NOTE("for a song's audio, the engine takes **the whole folder** `songs/<id>/` of the first mod that contains it. If you only replace `Voices-bf.ogg` of a base game song, you must therefore also put `Inst.ogg` (and the other tracks) in your mod's folder, otherwise the song will have no music.")
H2("4.1 Libraries and the lib:path syntax")
P("The base game stores its files in **libraries**: folders such as `shared`, `week1`... which themselves contain `images/`, `music/` or `sounds/`. A mod can create some: any folder at the root of the mod that contains `images/`, `music/` or `sounds/` becomes a library.")
P("In JSON files, an image path is written **without extension**, relative to an `images/` folder. Two forms:")
BUL("`characters/djcreeper`: searched in `images/` then `shared/images/` (mods then base game);",
    "`shared:stagefront`: searched in `shared/images/stagefront.png`. `week6:weeb/pixelUI/arrows-pixels` is `week6/images/weeb/pixelUI/arrows-pixels`. For your own library `jungle`, write `jungle:tree` and put `jungle/images/tree.png`.")
P("When you write a path without prefix, the engine also tries every library, but the prefix is safer.")
H2("4.2 Supported image formats")
TABLE(["Format", "Files", "Notes"], [
    ["Single image", "`name.png`", "One image."],
    ["Sparrow / Starling", "`name.png` + `name.xml`", "`SubTexture` tags (`name`, `x`, `y`, `width`, `height`, `frameX`, `frameY`, `frameWidth`, `frameHeight`, `rotated`). The XML is read tolerantly."],
    ["Packer", "`name.png` + `name.txt`", "One line per image: `name = x y width height`. Only used when there is no `.xml`."],
    ["Adobe Animate (Texture Atlas)", "folder `name/` with `Animation.json`, `spritemap1.json`, `spritemap1.png`", "The timeline \"labels\" are used as animation prefixes."],
], [3, 4, 5])
P("In a spritesheet, the **prefix** of an animation is the beginning of the frame names (`idle0000`, `idle0001`... have the prefix `idle0`). The engine compares ignoring case and sorts frames by their final number.")

H1("5. Adding a song")
P("A song is four things: the **audio**, the **metadata**, the **chart** and, if needed, a **script**. Replace `<id>` with your song identifier (lowercase, no spaces, for example `cobweb-cadence`).")
CODE("""
songs/<id>/Inst.ogg                       <- mandatory
songs/<id>/Voices-bf.ogg                  <- player vocals (optional)
songs/<id>/Voices-dad.ogg                 <- opponent vocals (optional)
data/songs/<id>/<id>-metadata.json        <- mandatory
data/songs/<id>/<id>-chart.json           <- mandatory
data/songs/<id>/<id>.py                   <- song script (optional)
""")
NOTE("a song only appears in Freeplay if it has at least one `Inst*.ogg` file, one `*-metadata*.json` file and a chart (with at least one note, or brand new and empty, made with `+ NEW SONG`). If it is missing, the MODS screen tells in red what is wrong.")
H2("5.1 The audio")
BUL("**OGG** (Vorbis) format. `Inst.ogg` is the instrumental.",
    "Vocals are named `Voices-<character>.ogg`, where `<character>` is the name given in `playerVocals` and `opponentVocals` of the metadata (`Voices-bf.ogg`, `Voices-dad.ogg`). Up to 6 vocal tracks are played together with the instrumental.",
    "If no named vocals are found, the engine takes the `Voices-*.ogg` files of the folder, then a possible `Voices.ogg`.",
    "A **variation** (see 5.5) adds its name as suffix: `Inst-erect.ogg`, `Voices-bf-erect.ogg`. If `Inst-<variation>.ogg` does not exist, `Inst.ogg` is used.",
    "Without a usable `Inst.ogg`, a red message `songs/<id>/Inst.ogg not found` appears and the song does not start.")
H2("5.2 The metadata")
CODE("""
{
  "version": "2.2.4",
  "songName": "Cobweb",
  "artist": "DJCreeper + Python Engine",
  "playData": {
    "characters": {
      "player": "djcreeper",
      "girlfriend": "gf",
      "opponent": "spooky",
      "playerVocals": ["djcreeper"],
      "opponentVocals": ["spooky"]
    },
    "stage": "halloween-night",
    "noteStyle": "halloween",
    "album": "Halloween Night",
    "songVariations": ["erect"],
    "previewStart": 4000
  },
  "timeChanges": [ { "t": 0, "bpm": 124 } ]
}
""")
TABLE(["Field", "Role"], [
    ["`songName`", "Displayed name (default: the formatted id)."],
    ["`artist`", "Read by the engine but not displayed for now."],
    ["`playData.characters.player` / `opponent`", "Character ids (files `data/characters/<id>.json`). Defaults: `bf` and `dad`."],
    ["`playData.characters.girlfriend`", "GF id. **If missing, there is no GF** in the song."],
    ["`playerVocals` / `opponentVocals`", "Names used to find the `Voices-<name>.ogg` files (default: the character id)."],
    ["`playData.stage`", "Stage id (`data/stages/<id>.json`). Default: `mainStage`. A stage that cannot be found shows a red message."],
    ["`playData.noteStyle`", "Note style (chapter 10). Default: `funkin`."],
    ["`playData.album`", "Text shown at the top of Freeplay: `volume1` gives \"OST: VOLUME 1\". Any text works."],
    ["`playData.previewStart`", "Position (in ms) where the song preview starts in Freeplay."],
    ["`timeChanges`", "List of `{\"t\": ms, \"bpm\": number}`. The first BPM is the song's; the next ones change the tempo at time `t` (in ms)."],
    ["`playData.difficulties`", "Informative only: the real difficulties are the ones of the chart that contain notes."],
], [4, 7])
H2("5.3 The chart")
CODE("""
{
  "version": "2.0.0",
  "scrollSpeed": { "easy": 1.6, "normal": 2.0, "hard": 2.4 },
  "events": [
    { "t": 0,    "e": "FocusCamera", "v": { "char": 1 } },
    { "t": 8000, "e": "Spotlight", "v": { "on": true, "char": 1 } },
    { "t": 9000, "e": "Lightning", "v": {} }
  ],
  "notes": {
    "normal": [
      { "t": 8000.0,  "d": 5, "l": 0 },
      { "t": 12000.0, "d": 0, "l": 432.692, "k": "candy" }
    ]
  }
}
""")
TABLE(["Field", "Role"], [
    ["`notes`", "An object: one key per difficulty (`easy`, `normal`, `hard`, or a name of your own), each with its list of notes. An empty difficulty is not offered."],
    ["`t`", "Note time in **milliseconds** since the start of the music."],
    ["`d`", "Direction. **0 to 3 = player** (0 left, 1 down, 2 up, 3 right), **4 to 7 = opponent** (same order: 4 left ... 7 right)."],
    ["`l`", "Sustain length in ms. 0 = single note."],
    ["`k`", "Note type (free text, optional). `\"noanim\"`: the character does not play its sing animation on this note. Other values do nothing by themselves: your script gives them a meaning (chapter 12)."],
    ["`scrollSpeed`", "Scroll speed: an object `{\"easy\": 1.6, ...}` (key `default` accepted) or a plain number. The player can force their own in OPTIONS, which then wins over the chart."],
    ["`events`", "List of events `{\"t\": ms, \"e\": name, \"v\": value}`. See 5.4."],
], [2, 9])
P("Notes are sorted by time automatically. The judgment windows, useful for balancing: SICK up to 45 ms off, GOOD 90 ms, BAD 135 ms, SHIT 166 ms; a note is missed when it is more than 180 ms late.")
TIP("you do not need to write charts by hand: the chart editor (chapter 13) places notes with the mouse, handles sustains and saves this JSON for you.")
H2("5.4 Chart events")
P("The engine understands ten base events. All events, **including the ones you invent**, are also sent to the `on_event` hook of your scripts.")
TABLE(["`e`", "Value `v`", "Effect"], [
    ["`FocusCamera`", "`{\"char\": 0|1|2, \"x\": 0, \"y\": 0, \"ease\": \"INSTANT\"}` (or just a number = `char`)", "The camera follows the player (0), the opponent (1) or the GF (2; with no GF, the middle of both). `x` and `y` offset the point. `ease` = `INSTANT`: immediate jump, otherwise it glides."],
    ["`PlayAnimation`", "`{\"target\": \"bf\", \"anim\": \"hey\"}`", "Plays an animation. `target`: `bf` / `dad` / `gf` (also `player`, `opponent`, `girlfriend`) or the `name` of an animated stage prop."],
    ["`ScrollSpeed`", "`{\"scroll\": 1.5, \"absolute\": false}`", "Changes the speed: multiplies the chart speed by `scroll`, or sets it if `absolute` is true. Ignored if the player forces their speed in OPTIONS."],
    ["`SetHealthIcon`", "`{\"char\": 0|1, \"id\": \"djcreeper-night\"}`", "Changes the health icon of the player (0) or the opponent (anything else)."],
    ["`ZoomCamera`", "`{\"zoom\": 1.2, \"duration\": 4, \"mode\": \"stage\", \"ease\": \"expo\", \"easeDir\": \"Out\"}`", "Zooms the camera smoothly. `duration` is in **steps** (one step = one sixteenth note; 4 = one beat). `mode` = `stage`: `zoom` multiplies the stage zoom (1 = normal); `direct`: exact zoom. `ease`: `linear` (default), `sine`, `quad`, `cube`, `quart`, `quint`, `expo`, `circ`, `back`, `elastic`, `bounce`, `smoothStep` or `INSTANT` (immediate jump); `easeDir`: `In`, `Out` or `InOut`."],
    ["`SetCameraBop`", "`{\"rate\": 4, \"intensity\": 1.0}`", "Sets the small zoom bump of the camera and the interface on the beat: every `rate` beats (0 = never), with strength `intensity`. By default every 4 beats, like the official game."],
    ["`FlashScreen`", "`{\"color\": [255, 255, 255], \"duration\": 400}`", "Full-screen flash of the given color (r, g, b), fading out in `duration` ms. **Respects the FLASHING LIGHTS option**: nothing is shown when it is off."],
    ["`ShakeCamera`", "`{\"intensity\": 10, \"duration\": 400}`", "Shakes the camera by `intensity` pixels, weaker and weaker during `duration` ms."],
    ["`Subtitle`", '`{"fr": "Salut !", "en": "Hi!", "duration": 3000}`', "Shows a subtitle for `duration` ms, in the game's language (SUBTITLES option respected). Can also be placed from the event panel of the chart editor."],
    ["`ChangeStage`", "`{\"stage\": \"spookyMansion\"}`", "Changes the stage during the song: the characters go to the places of the new stage and the camera re-centers. The stage is loaded before the song (no stutter). Scripts receive `on_stage_change(game, stage_id)`."],
], [2.3, 4.2, 5.5])
P("`PlayAnimation` also works on a stage element: the Week 2 lightning is simply `{\"target\": \"halloweenBG\", \"anim\": \"lightning\"}`. Players can turn the small beat zooms off with the **CAMERA ZOOMS** option (OPTIONS); `ZoomCamera` keeps working then.")
P("In the example mod, `Lightning`, `Spotlight`, `Zoom`, `ZoomBeat`, `Shake`, `Tint`, `Rain`, `ArrowWave` and `Scroll` do not exist in the engine: the script `scripts/halloween_fx.py` interprets them (chapter 12). In the chart editor, the V key opens the event panel (13.2); your own events are added to it with a simple JSON file (13.6).")
H2("5.5 Difficulties and variations")
P("Difficulties are the keys of `notes`. For Story Mode, they are the difficulties **common** to all the songs of the week. In Freeplay, the left/right arrows change the difficulty. An image `images/freeplay/freeplay<difficulty>.png` (and `images/storymenu/difficulties/<difficulty>.png` in Story) is used as the difficulty title; without an image, the name is written as text: an invented difficulty name therefore works with nothing else to do.")
P("A **variation** (for example `erect`) is a second set of files for the same song, named with the suffix:")
CODE("""
data/songs/bopeebo/bopeebo-chart-erect.json        (erect, nightmare difficulties)
data/songs/bopeebo/bopeebo-metadata-erect.json     (stage, characters, BPM of the variation)
songs/bopeebo/Inst-erect.ogg   Voices-bf-erect.ogg   Voices-dad-erect.ogg
""")
P("In Freeplay, the variation is shown under the difficulty. A variation's chart uses its own metadata if the file exists, otherwise the base ones.")
P("The example mod uses an `erect` variation for its **Nightmare** remixes: `cobweb-cadence-chart-erect.json` holds a single difficulty, `nightmare`; `cobweb-cadence-metadata-erect.json` changes the stage (`halloween-night-nightmare`), the GF (`gf-dark`) and the opponent (`spooky-dark`); the audio is `Inst-erect.ogg`, `Voices-spooky-erect.ogg`, `Voices-djcreeper-erect.ogg`. In Freeplay the difficulty reads NIGHTMARE. A remix is not just a harder chart: the instrumental and vocals are redone (same melody, organ, choir and strings instead of the harpsichord, held notes chopped into repeats).")
IMG("v2_mod_nightmare.png", "Cobweb in Nightmare: dark stage tinted red by the Tint event.")

H1("6. Adding a week")
P("A week is a file `data/levels/<id>.json`. It groups songs played one after the other in Story Mode.")
H2("Create a week step by step (all in the game)")
BUL("**1. The song**: TOOLS > CHART EDITOR > \"+ NEW SONG\". Give the mod folder, the id (lowercase, no space, e.g. `misra`), the name and the BPM. The game creates `data/songs/misra/misra-metadata.json` and `misra-chart.json` (empty Easy, Normal, Hard).",
    "**2. The music**: put `Inst.ogg` (and `Voices-bf.ogg`, `Voices-dad.ogg` for the vocals) in `mods/<mod>/songs/misra/`. The folder opens by itself; then press F5 in the MODS screen or create the song again: the editor opens right on it.",
    "**3. The chart**: place the notes in the editor, Ctrl+S to save, Tab for the next difficulty.",
    "**4. The week**: create `mods/<mod>/data/levels/<week-id>.json` with `\"songs\": [\"misra\"]` (example below). Each song id must be exactly the name of its folder in `data/songs/`.",
    "**5. Check**: the week shows up in STORY MODE. If not, open the MODS screen and select your mod: the game writes in red what is missing (`data/songs/<id>/` folder, metadata, chart, `Inst.ogg` music or unreadable JSON).")
NOTE("The `songs/<id>/` folder only holds the music. The chart and metadata go in `data/songs/<id>/`: without them the song (and so the week) does not exist for the game.")
CODE("""
{
  "name": "HALLOWEEN NIGHT",
  "titleAsset": "storymenu/titles/halloween-night",
  "background": "#E8731A",
  "songs": [ "cobweb-cadence", "midnight-candlewick", "pumpkin-moon-panic" ],
  "props": [
    { "assetPath": "characters/djcreeper", "scale": 0.42, "offsets": [60, -40],
      "animations": [
        { "name": "idle",    "prefix": "DJC idle", "frameRate": 24 },
        { "name": "confirm", "prefix": "DJC hey",  "frameRate": 24 } ] }
  ]
}
""")
TABLE(["Field", "Role"], [
    ["`name`", "Name shown at the top right (default: the id in capitals)."],
    ["`titleAsset`", "Title image in the list (no extension). Default: `storymenu/titles/<id>`. Without an image, the name is written with the game font. The image is shrunk to fit 380 x 100; the example mod uses a wide title image."],
    ["`background`", "Color of the band behind the characters, `#RRGGBB` (default: yellow `#F9CF51`)."],
    ["`songs`", "List of song ids in order. Unknown ids are ignored; with no valid song, the week does not appear."],
    ["`props`", "The animated characters of the band. Each item: `assetPath`, `scale`, `flipX`, `isPixel`, `offsets` [x, y], `animations`."],
    ["`visible`", "`false` hides the week."],
], [2.5, 9])
P("Props are spread from left to right (a quarter of the screen per prop, plus the `offset`). They dance on every beat; if a prop has a `confirm` animation, it plays when the player confirms the week. The example mod reuses base game props (`storymenu/props/spooky`, `gf`) and builds one from DJCreeper's spritesheet (`characters/djcreeper`, shrunk to 0.42): a prop can use any spritesheet of the mod.")
P("Mod weeks are placed **after** the base game ones. Songs follow each other; finishing a week without a single miss unlocks the Untouchable trophy.")
IMG("v2_mod_semaine.png", "The example mod's week in Story Mode.")

H1("7. Adding a character")
P("A character is a file `data/characters/<id>.json` plus an image (spritesheet) and a health icon. The id is the one you write in the metadata (`player`, `opponent`, `girlfriend`).")
CODE("""
{
  "name": "DJCreeper",
  "assetPath": "characters/djcreeper",
  "flipX": true,
  "scale": 1.0,
  "startingAnimation": "idle",
  "cameraOffsets": [-20, 20],
  "healthIcon": { "id": "djcreeper" },
  "animations": [
    { "name": "idle",       "prefix": "DJC idle" },
    { "name": "singLEFT",   "prefix": "DJC singLEFT" },
    { "name": "singLEFTmiss", "prefix": "DJC sadIn" },
    { "name": "firstDeath", "prefix": "DJC sadIn" },
    { "name": "deathLoop",  "prefix": "DJC sad", "looped": true },
    { "name": "deathConfirm", "prefix": "DJC hey" }
  ]
}
""")
H2("7.1 Character fields")
TABLE(["Field", "Role", "Default"], [
    ["`assetPath`", "Base image (chapter 4.2).", "`characters/<id>`"],
    ["`animations`", "List of animations (7.2).", "none"],
    ["`scale`", "Size (6 for pixel characters).", "1"],
    ["`flipX`", "Horizontal mirror. **The meaning is inverted when the character plays on the player side**: `bf.json` has `flipX: true` and is therefore drawn without mirror on the player side; a character with `flipX: false` is flipped if it plays on the player side. DJCreeper uses `true` so that its left/right sing poses stay as drawn.", "false"],
    ["`isPixel`", "Upscaling without smoothing (pixel art). Also used for the icon if `healthIcon.isPixel` is missing.", "false"],
    ["`danceEvery`", "Dances every N beats.", "1"],
    ["`singTime`", "Duration (in sixteenth notes) the character stays on the sing animation before going back to dancing.", "8"],
    ["`offsets`", "[x, y] added to the character's position on the stage.", "[0, 0]"],
    ["`cameraOffsets`", "[x, y] added to the point the camera aims at on this character.", "[0, 0]"],
    ["`healthIcon`", "`{\"id\": \"...\", \"isPixel\": false}`: the health icon id.", "the character id"],
    ["`startingAnimation`", "Starting animation, which also serves as the reference pose to anchor the feet. Otherwise: `idle`, `danceRight`, `danceLeft`, or the first one.", "-"],
], [2.4, 7, 2])
H2("7.2 Animations")
TABLE(["Field", "Role", "Default"], [
    ["`name`", "Animation name (7.3).", "`idle`"],
    ["`prefix`", "Beginning of the frame names in the spritesheet.", "the name"],
    ["`frameIndices`", "List of frames to use (from 0): lets you cut one animation into several (danceLeft / danceRight).", "all"],
    ["`frameRate`", "Frames per second.", "24"],
    ["`looped`", "Repeats the animation.", "false"],
    ["`offsets`", "[x, y] of the animation (see below).", "[0, 0]"],
    ["`assetPath`", "Another spritesheet for this animation only.", "the character's"],
], [2.4, 7, 2])
P("An animation whose `prefix` does not exist in the spritesheet is **silently ignored**. If a character has no valid animation, a red message `Character '<id>' not found` appears. `offsets` work as in FNF: increasing an offset moves the sprite to the left / up. The easiest way to tune them is the character editor (chapter 13).")
H2("7.3 Animation names used by the engine")
TABLE(["Name", "When"], [
    ["`idle` **or** `danceLeft` + `danceRight`", "Dancing. With the pair, the character alternates left/right on each beat; otherwise `idle` is replayed."],
    ["`singLEFT`, `singDOWN`, `singUP`, `singRIGHT`", "When a note of this direction is played (by the player or the opponent)."],
    ["`singLEFTmiss`, `singDOWNmiss`, `singUPmiss`, `singRIGHTmiss`", "When the player misses a note."],
    ["`hey`, `cheer`...", "Special animations played by a `PlayAnimation` event or by a script (`play_special`). Dancing does not cut them before they end."],
    ["`firstDeath`, `deathLoop`, `deathConfirm`", "Game over screen of the **player**. Without `firstDeath`, the screen simply shows GAME OVER. The example mod maps them to DJCreeper's `sadIn`, `sad` and `hey` poses: a custom game over."],
], [5, 6])
P("The game over sound and music can change for each character, with a `death` field in `data/characters/<id>.json` (asset paths). Every key is optional: for the missing ones, the base sound is kept.")
CODE("""
"death": {
  "sfx": "sounds/my_loss.ogg",
  "music": "music/my_gameover.ogg",
  "musicEnd": "music/my_gameover_end.ogg"
}
""")
BUL("`sfx`: the sound played on death; `music`: the music looping on the GAME OVER screen; `musicEnd`: the music when the player confirms to retry. The song's **player** character is the one that counts.")
P("Capitals matter: `singLEFT`, not `singleft`. You do not have to define everything: a missing animation simply changes nothing on screen.")
H2("7.4 The health icon")
P("A file `images/icons/icon-<id>.png` where `<id>` is `healthIcon.id`. It is an image with **two square icons side by side** (typically **300 x 150**: normal on the left, losing on the right). The second one is shown when the character's health is low (player under 20, opponent when the player's health exceeds 80). A single square image also works. If the icon is not found, the engine tries the name without `-playable`, the name before the first dash, then `face`.")
H2("7.5 The Freeplay pixel icon (optional)")
P("Freeplay first shows a small pixel icon `images/freeplay/icons/<opponent-id>pixel.png` (+ its `.xml`, animation with prefix `idle`). Without it, the opponent's health icon is used: this is what the example mod does.")
H2("7.6 Hiding layers (Adobe Animate atlases)")
P("`\"hiddenLayers\": [\"HAT\"]` in `data/characters/<id>.json` (or in a dialogue speaker) hides the layers whose name starts with these words. The base game uses it for Monster: its atlas contains the Week 5 Christmas hat, hidden everywhere else. The example mod does the same for Lemon Monster's portrait.")
H2("7.7 The Freeplay album cover")
P("In the metadata, `playData.album` gives the album id (example mod: `\"halloween-night\"`). Freeplay then shows `images/freeplay/albumRoll/<album>.png` on the right (square cover, 262 x 262 like the official ones) and, below it, its title `images/freeplay/albumRoll/<album>-text.png` + `.xml` (animation with prefix `idle`). The script `tools/build_example_album.py` makes the example mod's cover from the real stage.")
IMG("v2_editeur_personnage.png", "The character editor, to tune the offsets of each animation.")

H1("8. Adding a stage")
P("A stage is a file `data/stages/<id>.json`: a list of decor elements (`props`), the position of the three characters and the camera zoom. Stage space is in pixels, y axis pointing down.")
CODE("""
{
  "name": "Halloween Night",
  "cameraZoom": 1.0,
  "directory": "week2",
  "props": [
    { "name": "halloweenBG", "assetPath": "halloween_bg", "position": [-395, -505],
      "zIndex": -100, "animType": "animateatlas", "startingAnimation": "idle",
      "animations": [ { "name": "idle", "prefix": "static" },
                      { "name": "lightning", "prefix": "thunder" } ] },
    { "name": "pumpkinsLeft", "assetPath": "halloween/pumpkins", "position": [-100, 612],
      "scale": [0.78, 0.78], "scroll": [1.25, 1.25], "zIndex": 500 },
    { "name": "pumpkinsRight", "assetPath": "halloween/pumpkins", "position": [1215, 730],
      "scale": [0.62, 0.62], "scroll": [1.25, 1.25], "flipX": true, "zIndex": 501 }
  ],
  "characters": {
    "bf":  { "position": [1020, 885],  "zIndex": 300, "cameraOffsets": [-100, -100] },
    "dad": { "position": [382, 865],   "zIndex": 200, "cameraOffsets": [150, -100] },
    "gf":  { "position": [751.5, 787], "zIndex": 100, "cameraOffsets": [0, 0] }
  }
}
""")
H2("8.1 Stage fields")
TABLE(["Field", "Role"], [
    ["`cameraZoom`", "Camera zoom during the song (1 = normal size; smaller = you see wider). Default 1."],
    ["`directory`", "Library in which to look for prop images (default `shared`)."],
    ["`props`", "The decor list (8.2). With no valid prop, the background `shared/images/stageback.png` is used."],
    ["`characters`", "Settings for `bf`, `dad`, `gf` (8.3). Missing values come from the defaults (`bf`: [989.5, 885]; `dad`: [335, 885]; `gf`: [751.5, 787])."],
], [2.5, 9])
H2("8.2 Props")
TABLE(["Field", "Role", "Default"], [
    ["`name`", "Prop name (useful for `PlayAnimation` and scripts: `game.stage.props[\"name\"]`).", "its number"],
    ["`assetPath`", "Image (chapter 4). **`#RRGGBB`** creates a colored rectangle: `scale` = [width, height] in stage pixels.", "-"],
    ["`position`", "[x, y] of the top-left corner.", "[0, 0]"],
    ["`scale`", "A number, or [x, y].", "1"],
    ["`scroll`", "Parallax: 1 = moves with the camera, 0 = fixed on screen, 0.9 = a bit slower (background), 1.3 = foreground.", "[1, 1]"],
    ["`zIndex`", "Draw order: bigger = in front. Characters have their own `zIndex` (GF 100, opponent 200, player 300 by default): put yours between them to pass between two characters.", "0"],
    ["`alpha`", "Opacity, from 0 to 1.", "1"],
    ["`isPixel`", "Upscaling without smoothing.", "false"],
    ["`flipX`", "Horizontal mirror.", "false"],
    ["`animations`", "Makes an animated prop (same fields as 7.2).", "none"],
    ["`danceEvery`", "An animated prop dances every N beats (0 = does not dance).", "0"],
    ["`startingAnimation`", "Starting animation of an animated prop.", "the first one"],
], [2.4, 7.2, 2])
H2("8.3 Characters in the stage")
P("For each of `bf` (player), `dad` (opponent) and `gf` (girlfriend): `position` is where the character's **feet** land (the bottom-center of its rest pose). `zIndex` sets its depth. `cameraOffsets` is added to the character's own to decide where the camera looks when it follows it.")
P("You do not have to guess these numbers: the stage and camera editor (chapter 13) moves characters and props with the mouse and saves the JSON.")
P("The example mod's stage **reuses** the Week 2 mansion (`directory: \"week2\"`, Adobe Animate atlas `halloween_bg` whose `idle` and `lightning` animations are the base game's) and adds its own props: pumpkins (Minecraft blocks rendered with a black outline) in front of the characters, with a parallax of 1.25. Rain, fog, pumpkin glow and lightning are drawn by the mod's script (chapter 12); lightning plays the prop's `lightning` animation with `game.stage.props[\"halloweenBG\"].play(\"lightning\", now, force=True)`.")
IMG("v2_mod_decor.png", "The example mod's Halloween stage: Week 2 mansion, pumpkins, rain, fog and embers.")
IMG("v2_editeur_scene_camera.png", "The stage and camera editor: characters are moved and the camera frame is visible.")
