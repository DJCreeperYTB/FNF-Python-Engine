# English content of the modding guide, part B (chapters 9-15). Executed by build_guide_pdf_en.py (shares its helpers).
H1("9. Dialogues and cutscenes")
H2("9.1 Automatic trigger (Story Mode)")
P("In **Story Mode only**, before the countdown, the engine looks for:")
BUL("a video `videos/<song-id>.mp4` (also `.mkv`, `.webm` or `.mov`), then",
    "a dialogue `data/dialogue/conversations/<song-id>.json`.")
P("**Languages**: when the game is in French, the engine first loads `<id>-fr.json`; otherwise (or if that file does not exist) `<id>.json`. So always write both: `cobweb-cadence.json` in English and `cobweb-cadence-fr.json` in French, with the same lines translated.")
P("**Child mode**: when the CHILD MODE option is on, the engine first loads `<id>-censored.json` (and `<id>-censored-fr.json`), like the censored versions of Roses in the base game, and `videos/<name>-censored.mp4` for videos. Without a censored version, the normal file is used. The example mod softens Lemon Monster's threat before Pumpkin this way.")
P("After the song (if the player did not lose it), it plays `videos/<id>-end.mp4` then `data/dialogue/conversations/<id>-end.json` the same way. For a song with a variation, `<id>-<variation>.json` is tried first. They do not replay when you restart the song (R or after a death) and do not trigger in Freeplay nor in the chart editor test. If no file exists, nothing happens.")
P("Videos are read with the PyAV library. If it is missing or the video is unreadable, a red message appears and the cutscene is skipped. To skip a video, **hold** Enter or Space: a circle fills at the bottom right (no more instant skip).")
H2("9.1b Video subtitles")
P("Put a file `videos/<name>.subs.json` next to the video. Subtitles are shown if the game's SUBTITLES option is on, in the game's language:")
CODE("""
{
  "en": [ [0.8, 3.2, "The old mansion never sleeps..."],
          [3.6, 6.2, "Thunder, candles, and a creeper."] ],
  "fr": [ [0.8, 3.2, "Le vieux manoir ne dort jamais..."],
          [3.6, 6.2, "Du tonnerre, des bougies, et un creeper."] ]
}
""")
P("Each line is `[start in seconds, end in seconds, text]`. The example mod provides `videos/cobweb-cadence.mp4` (9 seconds, built frame by frame by running the game's real stage, see `tools/build_example_video.py`) and its EN + FR subtitles.")
P("**Subtitles during a song**: same format in `data/songs/<id>/subtitles.json` (or `subtitles-<variation>.json`), with song times in seconds. For a one-off subtitle, place a `Subtitle` event in the chart instead (see 5.4), or call `game.show_subtitle(...)` from a script (cutscene on the stage, see 12.3). A line can contain `\\n` to break the line.")
P("**Subtitle style** (videos, songs, `Subtitle` event, `game.show_subtitle(text, duration, style)`): add `\"style\": {...}` to the file (every line) or a 4th element `{...}` to one line (`[start, end, text, {style}]`). In the chart editor, the panel of the `Subtitle` event offers the same settings. Possible keys:")
TABLE(["Key", "Effect"], [
    ["`font`", 'Font: name of an installed font (`"Comic Sans MS"`) or a `.ttf` file of the mod (`"fonts/my-font.ttf"`). Empty = game font.'],
    ["`size`", "Text size (28 by default, 30 for videos)."],
    ["`bold`", "`true` / `false`: bold (yes by default)."],
    ["`color`", "Text color `[r, g, b]` (white by default)."],
    ["`opacity`", "Text opacity, from 0 to 100."],
    ["`background`", "Background color `[r, g, b]` (black by default)."],
    ["`background_opacity`", "Background opacity, from 0 (no background) to 100 (63 by default)."],
    ["`outline`", "`true`: black outline around the letters (handy without background)."],
    ["`position`", '`"bottom"` (default), `"middle"` or `"top"`.'],
], [3, 9])
H2("9.2 A conversation")
CODE("""
{
  "backdrop": { "type": "solid", "fadeTime": 0.6, "color": "#7F0B2A1A" },
  "music":    { "asset": "breakfast", "looped": true },
  "outro":    { "type": "fade", "fadeTime": 0.6 },
  "dialogue": [
    { "speaker": "spooky-kids", "speakerAnimation": "talk",
      "box": "halloween-bubble", "boxAnimation": "idle",
      "text": [ "Hehe... a creeper in OUR mansion?" ] },
    { "speaker": "djcreeper", "speakerAnimation": "hey",
      "box": "halloween-bubble", "text": [ "Sss... I only came for the lights." ] }
  ]
}
""")
TABLE(["Field", "Role"], [
    ["`backdrop`", "Colored background: `color` as `#RRGGBB` or `#AARRGGBB` (AA = opacity, as in Flixel), `fadeTime` = fade-in duration (s)."],
    ["`music`", "`asset`: name of a file `music/<name>.ogg` or `music/<name>/<name>.ogg` (in the mod or the base game). `looped` (true by default)."],
    ["`outro.fadeTime`", "Fade-out duration, in seconds (0.5 by default)."],
    ["`dialogue`", "List of lines. Each line: `speaker` (id of a file in `speakers/`), `speakerAnimation` (default `talk`), `box` (id of a file in `boxes/`, default `default`), `boxAnimation` (default `idle`), `text` (a string, or a list of pieces glued with spaces)."],
], [2.5, 9])
P("Text is typed letter by letter (28 per second, with a small beep). **Enter** or **Space** shows all the text, then moves to the next line; **Esc** closes the dialogue. Text fits on 4 lines at most.")
H2("9.3 Speakers and boxes")
P("`data/dialogue/speakers/<id>.json` describes a portrait, `data/dialogue/boxes/<id>.json` a bubble. Both have the same base format:")
CODE("""
{
  "assetPath": "shared:characters/SpookyKids",
  "isPixel": false,
  "scale": 0.75,
  "flipX": false,
  "offsets": [-291, -54.5],
  "animations": [ { "name": "talk", "prefix": "spooky dance idle0",
                    "frameRate": 24, "looped": true } ]
}
""")
P("Like in the official game, a **speaker** starts from its first image centered on the screen (at scale 1), then its `offsets` [x, y] are added (and those of the current animation too): speakers from V-Slice mods are placed the same way. The `offsets` of a **box** are measured from the point (627, 370) of the 1280 x 720 screen. The first animation is the starting pose; if the animation asked by a line does not exist, `idle` is played when it exists. A **box** also has a `text` object: `offsets` (text position), `width` (width in pixels), `color` and `shadowColor` (`#RRGGBB`). Without a box, the text is written in dark brown at the bottom of the screen.")
TIP("tune the `offsets` by trial: restart the song in Story Mode after each JSON change (no need for F5).")
IMG("v2_mod_dialogue.png", "A dialogue of the example mod (DJCreeper and Lemon Monster portraits, Halloween bubble, text in French).")
H2("9.4 A scripted cutscene")
P("A script can also start its own videos or dialogues with `game.play_video(name)` and `game.start_dialogue(id)` (they return `False` if the file does not exist). The countdown waits for these cutscenes to end. For a cutscene made with code (moving the camera, drawing...), set `game.hold_countdown = True` in `on_create`: the countdown is frozen and only `on_update` is called. When you are done, call `game.start_countdown()`.")
CODE("""
def on_create(game):
    game.hold_countdown = True       # freeze the countdown
    game.t0 = 0.0
    game.focus_camera(1, instant=True)

def on_update(game, dt):
    if game.hold_countdown:
        game.t0 += dt
        if game.t0 > 3:              # after 3 seconds of cutscene
            game.start_countdown()   # the countdown starts
""")

H1("10. Note styles")
P("The style is the `playData.noteStyle` field of the metadata (`funkin` or `pixel` in the base game). The file `data/notestyles/<style>.json` says where the images come from. **Only these keys are read**:")
CODE("""
{
  "assets": {
    "note": {
      "assetPath": "week6:weeb/pixelUI/arrows-pixels",
      "isPixel": true,
      "data": { "left": { "prefix": "noteLeft" }, "down": { "prefix": "noteDown" },
                "up": { "prefix": "noteUp" },     "right": { "prefix": "noteRight" } }
    },
    "noteStrumline": {
      "assetPath": "week6:weeb/pixelUI/arrows-pixels",
      "data": { "leftStatic": { "prefix": "staticLeft0" },
                "leftPress": { "prefix": "pressedLeft0" },
                "leftConfirm": { "prefix": "confirmLeft0" } }
    }
  }
}
""")
BUL("`assets.note.assetPath`: **Sparrow** spritesheet of the notes; `data.<left|down|up|right>.prefix`: the frame of each arrow (default `noteLeft`...). `isPixel` enables upscaling without smoothing.",
    "`assets.noteStrumline.assetPath`: spritesheet of the receptors; `data.<direction>Static`, `<direction>Press`, `<direction>Confirm`: the three states (defaults `static<Direction>0`, `press<Direction>0`, `confirm<Direction>0`). Only the **first frame** of each prefix is used.",
    "Arrows are always resized to the same size: `scale`, `offsets`, `fallback`, `holdNote`, `noteSplash`... are ignored. Sustains are drawn by the engine (colored bar).",
    "If a spritesheet is not a valid Sparrow, the engine falls back on the default arrows (`shared:notes`, `shared:noteStrumline`).")
P("The example mod defines the `halloween` style (`data/notestyles/halloween.json`): it points to `images/halloween/notes.png` and `noteStrumline.png`, copies of the base game's ones tinted orange, and declares `\"fallback\": \"funkin\"`. Each song's metadata has `\"noteStyle\": \"halloween\"`.")
NOTE("only the style named exactly `pixel` also turns on the pixel version of the countdown and ranks (SICK, GOOD...). A custom style keeps the normal style's ones.")

H1("11. Trophies")
P("A trophy is a file `data/achievements/<id>.json`. The id is the file name. The trophy appears in the TROPHIES menu (with the mod name in brackets) and a notification pops up when it is unlocked.")
CODE("""
{
  "name": "Trick or Treat",
  "name_fr": "Trick or Treat",
  "description": "Hit every candy note of a song.",
  "description_fr": "Touche toutes les notes bonbon d'une chanson.",
  "icon": "djcreeper",
  "hidden": false
}
""")
TABLE(["Field", "Role"], [
    ["`name`, `description`", "English texts (default: the id, and nothing)."],
    ["`name_fr`, `description_fr`", "Used instead when the game is in French."],
    ["`icon`", "Either the id of a health icon (`djcreeper` -> `images/icons/icon-djcreeper.png`), or an image path in the mod (if it contains `/` or ends with `.png`)."],
    ["`hidden`", "`true`: the name and description show \"???\" until the trophy is unlocked."],
], [3, 8])
P("A trophy is unlocked from a script with `game.unlock_achievement(\"my-id\")`. An id that does not exist is ignored, as is an already earned trophy. Engine trophies (First Beat, Full Combo...) cannot be replaced: a mod file whose id is already taken is ignored. **During a test started from the chart editor, no trophy is unlocked.**")

H1("12. Python scripts")
NOTE("a script is a full Python program, run with **all the rights** of your account (it can read, write or delete files, open the network...). The engine does not isolate it. **Only install mods from people you trust**, and read the `.py` files of a downloaded mod before enabling it.")
H2("12.1 Where to put a script")
BUL("`scripts/*.py` in a mod: **global** script, loaded for **all** songs as long as the mod is active;",
    "`data/songs/<id>/*.py`: **song** script, loaded only for the song `<id>`.")
P("Scripts are loaded at the start of each song (so at each restart with R). Order: mods from the lowest to the highest priority, and alphabetical order in each folder. Each file is an independent module: **a script cannot import another** one of the mod. Its file-level variables are reset on each song.")
P("Every function is optional. The script simply defines the ones it needs; the engine calls them with the `game` object as first argument.")
H2("12.2 The hooks")
TABLE(["Function", "When it is called"], [
    ["`on_create(game)`", "Once, when the song is loaded (characters, stage, notes ready), before the countdown. This is where you prepare variables, tint notes, set `hold_countdown`, start a dialogue."],
    ["`on_countdown(game, n)`", "At each countdown step: `n` is 0 (three), 1 (two), 2 (one), 3 (GO)."],
    ["`on_beat(game, beat)`", "On every beat (integer `beat`). Countdown beats are negative: the music starts at beat 0."],
    ["`on_step(game, step)`", "On every sixteenth note (4 per beat; integer `step`)."],
    ["`on_update(game, dt)`", "Every frame (60 per second), `dt` in seconds. Not called during pause, nor during a dialogue or video before the song. Called during a `hold_countdown`."],
    ["`on_note_hit(game, note, rating)`", "The player hits a note. `rating` is `\"SICK\"`, `\"GOOD\"`, `\"BAD\"` or `\"SHIT\"`. For a sustain, called at the head of the note."],
    ["`on_note_miss(game, note)`", "The player misses a note, or releases a sustain too early."],
    ["`on_note_avoided(game, note)`", "A note marked `note.avoid = True` went by untouched (no miss counted, botplay never hits it)."],
    ["`on_stage_change(game, stage_id)`", "The stage just changed (`ChangeStage` event or `game.change_stage(id)`)."],
    ["`on_ghost_miss(game, lane)`", "The player presses with no note, **only if** ghost tapping is off in OPTIONS. `lane`: 0 to 3."],
    ["`on_opponent_hit(game, note)`", "The opponent plays a note."],
    ["`on_event(game, event)`", "A chart event is reached (the engine already handled it if it knows it). `event` = `{\"t\": ms, \"e\": name, \"v\": value}`."],
    ["`on_key_down(game, event)`", "A key is pressed during the song (`event.key`). Return `True` to keep the key: the game does not use it (e.g. Enter on an info card without pausing the game)."],
    ["`on_draw_stage(game, screen)`", "After drawing the stage and characters, **before** notes and interface."],
    ["`on_draw(game, screen)`", "After the interface (notes, health bar, score, countdown), before pause and error messages. `screen` is a 1280 x 720 pygame surface."],
    ["`on_game_over(game)`", "Health drops to zero."],
    ["`on_song_end(game)`", "The music ends (before the Story Mode end dialogue). Not called if the player quits with Esc."],
], [4.2, 8])
P("When you test from the chart editor with a start in the middle, the events already passed are replayed at once at startup (so they call `on_event`).")
H2("12.3 The game object")
P("This is the song being played. Everything below really exists. The characters' `now` time is `pygame.time.get_ticks()`.")
TABLE(["Name", "Content"], [
    ["`game.health`", "Health, from **0 to 100** (starts at 50). Modifiable; at 0: game over."],
    ["`game.score`, `combo`, `max_combo`, `misses`", "Score, combo, best combo, miss count. `sick`, `good`, `bad`, `shit` count judgments. `game.accuracy()` gives the accuracy in %."],
    ["`game.notes`", "List of all notes. See the table below."],
    ["`game.song`", "Song info: `song_id`, `name`, `artist`, `bpm`, `mod`, `album`, `stage`, `player`, `opponent`, `girlfriend`."],
    ["`game.difficulty`, `game.variation`, `game.chart_key`", "Difficulty played (`\"hard\"`...), variation (`\"\"` if none), full key."],
    ["`game.song_time`", "Song time in ms (negative during the countdown). `game.chart_time`: the same, corrected by the delay set in OPTIONS; the one notes use."],
    ["`game.beat_at(ms)`, `game.beat_length(ms)`", "Beat number (with decimals) at a time, and length of a beat in ms."],
    ["`game.scroll_speed`", "Current scroll speed (modifiable). `chart_speed`: the chart's. `downscroll`: true if notes go down."],
    ["`game.player`, `game.opponent`, `game.girlfriend`", "The characters (`girlfriend` is `None` when there is none). See below. Since the Freeplay modifiers, `game.human` / `game.cpu` are the character controlled by the player / the automatic one."],
    ["`game.rate`, `game.opponent_mode`, `game.judgment`, `game.scroll_mult`", "Freeplay modifiers: song speed (up to x4), \"play as opponent\" mode, judgment (\"normal\" / \"easy\"), scroll speed multiplier."],
    ["`game.stage`", "The stage: `stage.props` (dictionary name -> prop), `stage.zoom`, `stage.camera_zoom`."],
    ["`game.camera_zoom`", "Multiplier of the stage zoom (1.0 = normal), the same as the `ZoomCamera` event; you can change it by hand. `game.view_zoom` (read-only) is the real zoom: stage x `camera_zoom` x small beat bump."],
    ["`game.bop_rate`, `game.bop_intensity`, `game.hud_bop_intensity`", "The zoom bump on the beat: every `bop_rate` beats (4 by default, 0 = never), strength of the camera (1.015 by default) and of the interface (0.03 by default). This is what the `SetCameraBop` event sets."],
    ["`game.flash_screen(color, duration)`", "Full-screen flash: `color` = (r, g, b), `duration` in ms. Respects FLASHING LIGHTS."],
    ["`game.shake_camera(intensity, duration)`", "Camera shake: `intensity` in pixels, `duration` in ms."],
    ["`game.show_subtitle(text, duration)`", 'Shows a subtitle for `duration` ms (3000 by default). `text`: a string, or `{"fr": "...", "en": "..."}` to follow the game language. Handy for a cutscene played on the stage.'],
    ["`game.strum_offset`", "A **function** `strum_offset(player, lane) -> (dx, dy)` that you replace (`player` is `True` for the player's arrows, `lane` goes from 0 to 3). It moves the arrow by pixels; notes, splashes and hold covers follow. Example: `game.strum_offset = lambda player, lane: (0, 20 * math.sin(game.song_time / 300 + lane))`."],
    ["`game.strum_alpha`", "Opacity of the fixed arrows, 0.0 to 1.0: `game.strum_alpha[0][lane]` for the opponent, `game.strum_alpha[1][lane]` for the player (`lane` 0 to 3)."],
    ["`game.lane_for_key`", "A **function** `lane_for_key(lane) -> lane` telling which arrow a key plays. Replace it to remap the keys: `game.lane_for_key = lambda lane: 3 - lane` gives a mirror."],
    ["`game.cam`, `game.cam_target`", "Camera position `[x, y]` and the point it aims at (it glides toward it). `game.focus_camera(target, x=0, y=0, instant=False)`: `target` 0 player, 1 opponent, 2 GF."],
    ["`game.world_to_screen(x, y, scroll=(1, 1))`", "Converts a stage point to a screen position with the current camera."],
    ["`game.start_dialogue(id)`, `game.play_video(name)`", "See chapter 9."],
    ["`game.hold_countdown`, `game.start_countdown()`", "See 9.4."],
    ["`game.unlock_achievement(id)`", "See chapter 11."],
    ["`game.app`", "The application: `app.text(screen, text, (x, y), size, color=..., center=False, bold=False, outline=False, right=False, raw=False)` to write (use `raw=True` for your own text, otherwise the engine tries to translate it), `app.font(size, bold)`, `app.play_sound(\"sounds/xxx.ogg\", volume)`, `app.settings` (for example `app.settings.flashing_lights`), `app.assets`, `app.volume`."],
    ["`game.warnings`", "List of texts shown in red at the start of the song: you can add your own."],
    ["`game.paused`, `game.finished`, `game.song_started`", "Game states."],
], [4.4, 8])
P("**A note** (`PlayNote`):")
TABLE(["Attribute", "Meaning"], [
    ["`time`", "Time in ms."],
    ["`lane`", "0 left, 1 down, 2 up, 3 right."],
    ["`player`", "`True` if it is a player note."],
    ["`length`", "Sustain length in ms (0 = single note)."],
    ["`kind`", "The chart's `k` (empty string if missing)."],
    ["`state`", "`\"pending\"`, `\"holding\"`, `\"hit\"`, `\"miss\"` or `\"skip\"`."],
    ["`color`", "`None`, or an (r, g, b) tuple to set: tints the arrow and the sustain."],
    ["`alpha`", "Opacity of the note: 1.0 (normal) to 0.0 (invisible, but still playable)."],
    ["`avoid`", "`True`: a note to avoid (letting it pass is not a miss; see `on_note_avoided`)."],
], [2, 9])
P("**A character** (`Character`): `play(name, now, force=False)` plays an animation (returns `False` if it does not exist), `play_special(name, now)` plays an event animation that dancing does not cut, `has(name)` tests its existence, `sing(lane, now, miss=False)` makes it sing, `x` and `y` give the position, `visible` shows or hides it, `id` is its id.")
NOTE("hooks run in the game loop, at 60 frames per second: do nothing slow in them (no file reading nor big computation on every frame). Create your pygame surfaces in `on_create` instead.")
H2("12.4 Example: special notes (pumpkin_notes.py)")
P("Here is the idea of the example mod's global script. It gives a meaning to two note types placed in the chart: `\"candy\"` (orange bonus) and `\"hex\"` (purple cursed note to **avoid**):")
CODE("""
import pygame
CANDY, HEX = (255, 150, 30), (170, 60, 255)

def on_create(game):
    game.candy_total = game.candy_hit = game.hex_hit = 0
    for note in game.notes:
        if note.kind == "candy":
            note.color = CANDY            # tint of the arrow and its trail
            game.candy_total += 1
        elif note.kind == "hex":
            note.color = HEX
            note.avoid = True             # note to avoid: letting it pass is not a miss

def on_note_hit(game, note, rating):
    now = pygame.time.get_ticks()
    if note.kind == "candy":
        game.candy_hit += 1
        game.health = min(100, game.health + 12)
        game.human.play_special("hey", now)   # human = the character you play
    elif note.kind == "hex":              # hitting a cursed note = a miss
        game.hex_hit += 1
        pass                              # the engine already counts the miss

def on_note_avoided(game, note):          # an `avoid` note went by untouched
    game.health = min(100, game.health + 5)

def on_song_end(game):
    if game.candy_total and game.candy_hit == game.candy_total:
        game.unlock_achievement("trick-or-treat")
""")
P("The example mod only has two special notes, **explained to the player** by an info card (`scripts/halloween_tuto.py`, EN/FR from `game.app.settings.language`, once per session; it holds the countdown with `game.hold_countdown` then calls `game.start_countdown()`): the **mandatory** note (`candy`, orange) and the **note to avoid** (`hex`, purple). In **Hard and Nightmare** only, missing the first or hitting the second is **instant death** (`game.health = 0`); in Easy and Normal it is just a miss. `hex` notes never replace a sung note: the generator adds them in the silences, between two notes or next to a sung note. Global scripts check `game.song.song_id` so they do nothing on base-game songs.")
H2("12.5 Example: Dadbattle-style effects (halloween_fx.py)")
P("The script `scripts/halloween_fx.py` reproduces the Dadbattle effects of Psych Online with **custom events** placed in the chart (field `\"e\"`) and read by `on_event`. It covers pretty much everything a script can do on the picture:")
TABLE(["Event", "Value `v`", "Effect"], [
    ["`Lightning`", "`{}`", "Lightning (the engine can do the same with `PlayAnimation`): the stage's `lightning` animation, bluish flash, thunder (`week2/sounds/thunder_*.ogg`), small zoom."],

    ["`Zoom`", "`{\"amount\": 0.06, \"ms\": 500}`", "Camera zoom punch that falls back."],
    ["`ZoomBeat`", "`{\"every\": 2, \"amount\": 0.03}`", "Zoom on the rhythm every N beats (`every` 0 = off)."],
    ["`Shake`", "`{\"power\": 10, \"ms\": 400}`", "Damped camera shake."],
    ["`Tint`", "`{\"color\": [r,g,b], \"alpha\": 60, \"ms\": 600}`", "Color veil over the stage, with fade (mood change: blue, orange, Nightmare red)."],
    ["`Spotlight`", "`{\"on\": true, \"char\": 0|1|2}`", "Spotlight: darkened screen, light cone on the singer, smoke at the bottom of the screen."],
    ["`Rain`", "`{\"level\": 0|1|2}`", "Rain."],
    ["`ArrowWave`", "`{\"on\": true, \"amp\": 14}`", "The arrows sway."],
    ["`Scroll`", "`{\"mode\": \"middle\"|\"normal\"|\"flip\"}`", "Player arrows to the center, back, or inverted scroll (up/down)."],
], [2.2, 4.6, 5.8])
P("The techniques used, all possible for your own mod:")
BUL("**Camera zoom and shake**: in `on_draw_stage`, copy the screen already drawn (`screen.copy()`), resize it (`pygame.transform.scale`) and draw it back centered, shifted for the shake. Notes and interface (drawn afterwards) do not move.",
    "**Spotlight**: a semi-transparent black layer from which the alpha of a cone image is **subtracted** (`special_flags=pygame.BLEND_RGBA_SUB`), then a warm beam, then drifting smoke clouds (`images/halloween/smoke*.png`).",
    "**Arrow movement**: `game.strum_x` is replaced by a function that adds a sine wave; `game.PLAYER_X` / `game.OPPONENT_X` glide toward the center; inverting `game.downscroll` and recomputing `game.receptor_y` flips the scroll mid-song.",
    "**Animated stage**: `game.stage.props[\"halloweenBG\"].play(\"lightning\", now, force=True)` plays a prop's animation.",
    "**Camera during the countdown**: the song script `pumpkin-moon-panic.py` starts on DJCreeper then, in `on_beat` (negative beats = countdown), slides the camera to Lemon Monster. For a real pause before the song, the info card `scripts/halloween_tuto.py` uses `hold_countdown = True` then `start_countdown()` (see 9.4).")
IMG("v2_mod_projecteur.png", "The Spotlight event: darkened screen, light cone on DJCreeper, smoke at the bottom.")
IMG("v2_mod_eclair.png", "The Lightning event: the stage's lightning animation, a flash and a zoom.")
IMG("v2_mod_fleches_milieu.png", "The Scroll (arrows in the center) and ArrowWave events, with Tint's red veil.")
TIP("since the Freeplay modifiers update, `game.human` is the character the player controls and `game.cpu` the automatic one; use them rather than `game.player` / `game.opponent` when you mean \"whoever is playing\". They come with `game.rate` (song speed), `game.opponent_mode`, `game.judgment` (\"normal\" or \"easy\") and `game.scroll_mult`.")
H2("12.6 Errors and available modules")
BUL("A script that crashes **never crashes the game**. The message (`file.py / hook: last error line`) appears in **red** at the top left for 8 seconds, and the full detail is appended to **`mods/errors.log`** (with the date).",
    "The function that crashed is **disabled** for the rest of the song (the script's other hooks keep going): no flood of errors at 60 frames per second. Restart the song with R to re-enable it.",
    "A syntax or import error when loading the file is shown the same way with `load` instead of the hook name, and the script is not used.",
    "Modules: `pygame`, `math`, `random`, `json` and `pathlib` are safe, including in the `.exe` version (the engine uses them itself). For any other module, nothing is guaranteed in the `.exe`: it only bundles what the engine imports. Do not count on separately installed libraries.")

H1("13. Modder tools")
P("The **TOOLS** menu contains three editors: the chart editor, the stage and camera editor, the character editor. They let you almost never write JSON by hand.")
IMG("v2_outils.png", "The TOOLS menu.")
H2("13.1 Where files are saved")
BUL("If the file comes from a **folder mod**, it is modified **in place**.",
    "If the file comes from the **base game** or a **.zip** mod, a copy is written to the **`Editor Saves/`** folder, next to `mods/`. It is not a mod: the game always loads it, before every mod. Your changes apply immediately, without touching the originals; delete the file from `Editor Saves` to go back to the original.",
    "Every save reloads the mods.")
H2("13.2 The chart editor")
P("TOOLS > CHART EDITOR, choose a song; left/right arrows choose the difficulty. The **+ NEW SONG** entry creates a new song: the engine asks for the mod folder, the id, the name and the BPM, writes the metadata and an empty chart (easy, normal, hard), then, if there is no `Inst.ogg` yet, opens the `songs/<id>/` folder so you can put the audio there; then reload with F5 in MODS.")
P("The grid has 9 columns: **events**, 4 **opponent** columns, 4 **player** columns. The red line is the playback position; one cell = one sixteenth note.")
IMG("v2_chart_editor.png", "The chart editor.")
TABLE(["Control", "Effect"], [
    ["Left click on an empty cell", "Places a note (columns 1-4 opponent, 5-8 player) or a FocusCamera event (column 0)."],
    ["Left click on an item", "Selects it. Clicking a selected FocusCamera event again changes its target (0, 1, 2)."],
    ["Ctrl + click", "Adds or removes an item from the multiple selection."],
    ["Ctrl + drag", "Draws a rectangle: everything it touches is selected."],
    ["Ctrl + A", "Selects everything."],
    ["Drag down (button held)", "Stretches the note into a sustain: it goes up to the end of the cell under the mouse."],
    ["Right click", "Deletes the item under the mouse."],
    ["Wheel", "Moves playback by one grid step (Shift: 4 steps)."],
    ["Ctrl + wheel", "Vertical zoom."],
    ["Space", "Play / stop (with audio)."],
    ["Up / Down (or W / S)", "Move by one grid step (Shift: 4 steps)."],
    ["Page up / Page down", "One measure (4 beats) back / forward."],
    ["Home", "Back to the start of the song."],
    ["Left / Right", "Change the grid: 1/4, 1/8, 1/12, 1/16, 1/24, 1/32, 1/48, 1/64 (default 1/16)."],
    ["Q / E", "Shorten / lengthen the selected note's sustain by one step."],
    ["Del / Backspace", "Deletes the selected item, or the whole multiple selection."],
    ["Ctrl + C / X / V", "Copy / cut / paste the selection. Nothing selected: copies or cuts the measure of the red line. Pasting happens at the red line."],
    ["Ctrl + D", "Copies the selection to the other side (with no selection: the opponent's notes of the measure go to the player). Shift + Ctrl + D: the other way round."],
    ["Ctrl + up / down", "Moves the selection by one grid step (Shift: 4 steps). Ctrl + left / right: changes column."],
    ["Ctrl + F", "Mirror: swaps the columns of the selection."],
    ["K", "Type the type (`k`) of the selected note (empty = normal)."],
    ["V (or double-click on an event)", "Opens the **event panel** (see 13.6): pick the event from a list and set its fields. The Text tab also accepts `name|JSON value`, for example `FlashScreen|{\"duration\": 400}`."],
    ["O", "Shows / hides the waveform of the opponent's and the player's voices."],
    ["L", "**Live input** (see below the table)."],
    ["F1", "Opens the help (13.7)."],
    ["B", "Change the BPM (20 to 400; modifies the first BPM of the metadata)."],
    ["N", "Change the difficulty's scroll speed (0.5 to 6)."],
    ["Tab", "Next difficulty."],
    ["M / H", "Metronome / hit sounds."],
    ["Ctrl + Z / Ctrl + Y", "Undo (80 levels) / redo."],
    ["Ctrl + S", "Save the chart and metadata."],
    ["Enter", "**Test**: saves, then starts the song from the playback position. At the end or when quitting, you return to the editor."],
    ["Esc", "First clears a multiple selection. Otherwise: back; if unsaved changes remain, press twice (within 2 seconds)."],
    ["Playback bar (bottom)", "Click or drag it to go anywhere in the song."],
], [4, 8])
P("**Live input (L key)**: during playback, you play the notes on the keyboard and they are placed on the grid. Keys **1 to 8** match the 8 columns from left to right (1-4 opponent, 5-8 player). The other setting: **WASD** for the opponent and the **arrow keys** for the player. A **held** key makes a long note. Press L again to switch setting or stop.")
P("For listening: hit sounds (H) play at full volume, the editor has small interface sounds like the official game's editor, and the metronome (M) makes a deeper sound at the start of each measure. The **Controls** window on the right reminds you of the main keys.")
P("Input boxes (K, B, N, new song): **Enter** confirms, **Esc** cancels. During a song, the **7** key also opens the chart editor at the current position (shown in the pause menu).")
H2("13.3 The stage and camera editor")
P("TOOLS > STAGE & CAMERA EDITOR, choose a stage. The three base characters (bf, dad, gf) are displayed. A cross marks each character's camera point; for the selected character, a white frame shows what the game camera sees when it follows it.")
IMG("v2_editeur_scene_camera.png", "The stage and camera editor (white frame = the game camera view).")
TABLE(["Control", "Effect"], [
    ["Drag (left click)", "Moves the selected element."],
    ["Arrows (Shift: x10)", "Moves the element by 1 pixel (10 with Shift)."],
    ["Tab / Shift + Tab", "Next / previous selection: bf, dad, gf, then each prop."],
    ["1 / 2 / 3", "Select bf / dad / gf."],
    ["C", "Switches between **POSITION** mode and **CAMERA OFFSETS** mode (moving then changes the character's `cameraOffsets`)."],
    ["Z / X", "Game camera zoom (`cameraZoom`): less / more (steps of 0.05, from 0.2 to 3)."],
    ["Right or middle click + drag", "Moves the view (pan)."],
    ["Wheel", "Zoom of the editor view (outside preview)."],
    ["P", "Preview: shows the stage as in game, the camera following the selected character."],
    ["Ctrl + S (or F2)", "Saves the stage JSON."],
    ["Esc", "Back to the TOOLS menu (without warning)."],
], [4, 8])
H2("13.4 The character editor")
P("TOOLS > CHARACTER EDITOR, choose a character. It stands on a grid; the ghost image (\"onion skin\") shows the rest pose so that you align each animation on it.")
TABLE(["Control", "Effect"], [
    ["W / S", "Previous / next animation (list on the left; only animations that load are listed)."],
    ["Space", "Replay the animation."],
    ["Arrows (Shift: x10)", "Moves the animation's sprite: the animation's `offsets` are changed accordingly (FNF sense: the value decreases when the sprite goes right / down)."],
    ["C", "**Camera point** mode: arrows change the character's `cameraOffsets`."],
    ["G", "Show / hide the ghost image of the rest pose."],
    ["F", "Player view (mirror) / opponent view."],
    ["Ctrl + S (or F2)", "Saves the character JSON."],
    ["Esc", "Back to the TOOLS menu."],
], [4, 8])
H2("13.5 A recommended workflow")
BUL("Create the mod with N in MODS, put in your images and music.",
    "Create the character (simple JSON with the prefixes) then tune its offsets in the character editor.",
    "Create the stage, place the characters in the stage editor.",
    "Place the notes with the chart editor; test often with **Enter**.",
    "Add dialogue, week, trophy and scripts.")

H2("13.6 Adding your events to the editor")
P("The event panel (V key) lists the engine's events (`FocusCamera`, `ZoomCamera`, `FlashScreen`...) and those of the mods. For **your** event to appear there with adjustable fields, create a file `data/events/<name>.json` in your mod:")
CODE("""
{
  "name": "Pulse",
  "description": "Small colored flash on the beat.",
  "fields": [
    { "key": "color", "type": "color", "default": [255, 255, 255], "label": "Color" },
    { "key": "ms", "type": "int", "default": 300, "label": "Length (ms)", "step": 50 },
    { "key": "mode", "type": "choice", "choices": ["soft", "hard"], "default": "soft" }
  ]
}
""")
TABLE(["Field", "Role"], [
    ["`name`", "The event name, as written in the chart (`e`). A name already used by the engine is ignored."],
    ["`description`", "One sentence shown in the panel."],
    ["`fields`", "The list of fields. Each has a `key` (the key in `v`), a `type`, a `default` value, a `label` (the panel text) and a `step` (the arrow step for numbers)."],
    ["`type`", "`number` (decimal), `int` (integer), `text`, `bool` (checkbox), `choice` (list: `choices` holds values, or pairs `[value, \"shown name\"]`) or `color` (an r, g, b color)."],
], [2.2, 9.8])
P("The event placed in the chart is then `{\"t\": ms, \"e\": \"Pulse\", \"v\": {\"color\": [255, 255, 255], \"ms\": 300}}`, and your script reads it with `on_event` (chapter 12). A badly written file is ignored, without blocking the game.")
H2("13.7 The HELP screen")
P("If you are stuck, open the **HELP** screen: TOOLS > HELP, the **H** key in the MODS screen, or **F1** in the chart editor. Pick a problem category (my song, my character, my stage, the chart, scripts, dialogues...), then the question that looks like your case. The game then opens **this PDF guide right at the correct page**.")
TIP("page numbers are recorded when the PDF is generated (`mods/guide_pages_fr.json` and `mods/guide_pages_en.json`). If you change the guide, run `tools/build_guide_pdf.py` and `tools/build_guide_pdf_en.py` again.")

H1("14. The example mod, file by file")
P("`mods/ExampleMod.zip` is built from `mods_src/ExampleMod/`. Open these files next to this guide.")
TABLE(["File", "Role"], [
    ["`mod.json`", "Name, description, author, version, icon, priority 0."],
    ["`songs/<id>/Inst.ogg`, `Voices-<char>.ogg` (+ `-erect`)", "The audio of the three songs and their Nightmare remixes (Skid & Pump / Lemon Monster voices: presets of the FNF SoundFont; DJCreeper: SF2 sound). Built by `tools/build_example_song.py` from real FL Studio samples."],
    ["`data/songs/<id>/<id>-metadata.json`, `<id>-metadata-erect.json`", "Name, characters, stage, `halloween` note style, album, BPM (Pumpkin changes tempo at measure 28)."],
    ["`data/songs/<id>/<id>-chart.json`, `<id>-chart-erect.json`", "easy / normal / hard, then nightmare; FocusCamera events and custom events (Spotlight, Lightning...); `candy` and `hex` notes."],
    ["`data/songs/<id>/<id>.py`", "Song scripts: GF cheering; candle halo; Lemon Monster's scripted cutscene."],
    ["`scripts/halloween_fx.py`", "Global script: all the Dadbattle-style effects (chapter 12.5)."],
    ["`scripts/pumpkin_notes.py`", "Global script: `candy` (mandatory) and `hex` (avoid) notes, instant death in Hard/Nightmare, trophies."],
    ["`scripts/halloween_tuto.py`", "Global script: info cards explaining the mechanics (EN/FR)."],
    ["`data/levels/halloween-night.json` + `images/storymenu/titles/halloween-night.png`", "The week and its title image."],
    ["`data/characters/djcreeper.json` + `images/characters/djcreeper.png/.xml`", "Playable DJCreeper (VS DJCreeper's spritesheet), with misses and death animations (custom game over screen)."],
    ["`images/icons/icon-djcreeper.png`, `icon-djcreeper-night.png`", "300 x 150 health icons; the second one is set by the `SetHealthIcon` event in Nightmare."],
    ["`data/stages/halloween-night.json`, `halloween-night-nightmare.json` + `images/halloween/`", "The stages (Week 2 mansion + pumpkins), the smoke clouds."],
    ["`data/notestyles/halloween.json` + `images/halloween/notes.*`, `noteStrumline.*`", "The orange note style."],
    ["`data/dialogue/conversations/<id>.json` and `<id>-fr.json`", "A dialogue before each song (and after the last one), in English and French."],
    ["`data/dialogue/speakers/*.json`, `boxes/halloween-bubble.json` + `images/dialogue/`", "The portraits (DJCreeper, Spooky Kids, Lemon Monster) and the bubble."],
    ["`videos/cobweb-cadence.mp4` + `.subs.json`", "The video cutscene and its EN / FR subtitles."],
    ["`data/achievements/*.json`", "Five bilingual trophies, two of them hidden."],
    ["`ENGINE_REQUESTS.md`", "Features the engine could offer to simplify this mod (ignored by the engine)."],
], [5, 7])
P("To build a mod, the quickest way is to **copy this folder** and replace its files one by one.")

H1("15. Sharing your mod")
H2("15.1 Creating the .zip")
BUL("Select the **contents** of your mod folder (the one that contains `mod.json`) and compress it into a `.zip`: `mod.json` must be at the root of the zip. Compressing the folder itself also works (a single folder level).",
    "The `.zip` name serves as the mod identifier: avoid changing it along the way (the \"disabled mod\" setting remembers it).",
    "The player just drops the zip into `mods/` then enables it in MODS.")
H2("15.2 Test checklist")
BUL("The mod appears in MODS, without ERROR, with its icon and description.",
    "The song is in Freeplay, with all its difficulties; music and vocals are in sync.",
    "No red text during the song (countdown included); `mods/errors.log` is empty.",
    "Sing, dance and miss animations are all there; the health icon changes properly.",
    "The week appears in Story Mode, dialogues chain, the last song leads to the results.",
    "Test with the **zip version** (not only the folder).",
    "Test with FLASHING LIGHTS off if you make flashes.",
    "Re-read your scripts: they must do nothing but what players expect.")
H2("15.3 Troubleshooting (FAQ)")
TABLE(["Problem", "Likely cause"], [
    ["My song is not in Freeplay.", "`songs/<id>/Inst.ogg` (or another `Inst*.ogg`) is missing, or the file `data/songs/<id>/<id>-metadata.json`, or the chart; or the JSON is invalid; or you did not press F5 in MODS. The MODS screen shows in red the exact cause for your mod."],
    ["Red `Character 'xxx' not found`.", "`data/characters/xxx.json` does not exist, or no animation finds its `prefix` in the spritesheet (wrong `assetPath`, wrong name)."],
    ["`Stage 'xxx' not found`.", "`data/stages/xxx.json` is missing or its name does not match `playData.stage`."],
    ["`songs/<id>/Inst.ogg not found` and the song does not start.", "File missing or misnamed; or another higher-priority mod contains an incomplete `songs/<id>/` folder (see chapter 4)."],
    ["The character is invisible or backwards.", "Wrong `assetPath` (the name has no extension, relative to `images/`); check `flipX` (inverted for the player)."],
    ["The character slides or jumps between animations.", "Offsets to tune in the character editor."],
    ["The mod is in ERROR and will not enable.", "`mod.json` missing (or not at the zip root), invalid JSON, or corrupt zip. The error message is in the menu panel."],
    ["My change does not appear.", "`.zip` mod: rebuild the zip. New song / week / trophy: F5 in MODS. Another higher-priority mod may provide the same file."],
    ["My script does nothing.", "Look at `mods/errors.log` and the red text. The function name must be exact (`on_note_hit`...). A song script must be in `data/songs/<id>/` with the right id."],
    ["My video cutscene is skipped.", "Red message: unreadable format or PyAV missing. The name must be `videos/<id>.mp4`."],
    ["My dialogue does not show.", "It only starts in Story Mode, not in Freeplay nor in the editor test."],
    ["The trophy does not unlock.", "The `unlock_achievement` id does not match the file name; or the test came from the chart editor."],
], [4, 8])
P("Happy modding!")
