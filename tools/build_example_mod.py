"""Construit le mod d'exemple « Halloween Night » : images, fichiers JSON, puis mods/ExampleMod.zip

python tools/build_example_song.py    (la musique + les charts)
python tools/build_example_video.py   (la cinematique video)
python tools/build_example_mod.py     (images + JSON + zip)

Les scripts Python du mod (scripts/ et data/songs/<id>/*.py) sont ecrits a la main dans mods_src/ExampleMod/.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "fnf_assets"
SOURCE = ROOT / "mods_src" / "ExampleMod"
OUTPUT = ROOT / "mods" / "ExampleMod.zip"
DJC = Path(r"C:\Users\DJCre\Documents\FNF DJCREEPER\vs-djcreeper")
MC_JAR = Path(r"C:\Users\DJCre\AppData\Roaming\.minecraft\versions\1.19.2\1.19.2.jar")
WEEK = "halloween-night"
SONGS = ["cobweb-cadence", "midnight-candlewick", "pumpkin-moon-panic"]
OLD = ["snake-charmer"]  # ancien mod d'exemple, remplace


def hue_shift(image: Image.Image, degrees: float, saturation: float = 1.0, value: float = 1.0) -> Image.Image:
    rgba = image.convert("RGBA")
    a = rgba.getchannel("A")
    hsv = np.asarray(rgba.convert("RGB").convert("HSV")).astype(np.int32)
    hsv[..., 0] = (hsv[..., 0] + round(degrees / 360 * 255)) % 256
    hsv[..., 1] = np.clip(hsv[..., 1] * saturation, 0, 255)
    hsv[..., 2] = np.clip(hsv[..., 2] * value, 0, 255)
    out = Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB").convert("RGBA")
    out.putalpha(a)
    return out


def tint_mul(image: Image.Image, color) -> Image.Image:
    arr = np.asarray(image.convert("RGBA")).astype(np.float32)
    arr[..., :3] *= np.array(color, np.float32) / 255
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------ images
def mc_texture(name: str) -> Image.Image:
    with zipfile.ZipFile(MC_JAR) as jar:
        return Image.open(io.BytesIO(jar.read(f"assets/minecraft/textures/block/{name}.png"))).convert("RGBA")


def _affine(face: Image.Image, out_size, basis, origin) -> Image.Image:
    """Colle `face` (u horizontal, v vertical, en pixels) sur un parallelogramme : out = origin + u*bu + v*bv (sans lissage)."""
    (bux, buy), (bvx, bvy) = basis
    m = np.array([[bux, bvx], [buy, bvy]], float)
    inv = np.linalg.inv(m)
    a, b, d, e = inv[0, 0], inv[0, 1], inv[1, 0], inv[1, 1]
    c = -(a * origin[0] + b * origin[1])
    f = -(d * origin[0] + e * origin[1])
    return face.transform(out_size, Image.AFFINE, (a, b, c, d, e, f), resample=Image.NEAREST)


def pumpkin_cube(size: int = 230) -> Image.Image:
    """Citrouille-lanterne Minecraft vue en 3/4 : face sculptee devant, dessus et cote eclaires, contour noir comme DJCreeper."""
    s = size
    front = mc_texture("jack_o_lantern").resize((s, s), Image.NEAREST)
    top = mc_texture("pumpkin_top").resize((s, s), Image.NEAREST)
    side = mc_texture("pumpkin_side").resize((s, s), Image.NEAREST)
    dx, dy = int(s * .42), int(s * .30)          # vecteur de profondeur (haut-droite)
    pad = 24
    W, H = s + dx + 2 * pad, s + dy + 2 * pad
    canvas = Image.new("RGBA", (W, H))
    ox, oy = pad, pad + dy
    canvas.alpha_composite(_affine(tint_mul(side, (150, 110, 95)), (W, H), ((dx / s, -dy / s), (0, 1)), (ox + s, oy)))
    canvas.alpha_composite(_affine(tint_mul(top, (255, 235, 200)), (W, H), ((1, 0), (dx / s, -dy / s)), (ox, oy)))
    canvas.alpha_composite(front, (ox, oy))
    alpha = canvas.getchannel("A")
    outline = alpha.filter(ImageFilter.MaxFilter(13))
    out = Image.new("RGBA", canvas.size, (12, 6, 16, 0))
    out.putalpha(outline)
    out.alpha_composite(canvas)
    return out


def pumpkin_pile() -> Image.Image:
    cube = pumpkin_cube(230)
    small = cube.resize((round(cube.width * .62), round(cube.height * .62)), Image.LANCZOS)
    tiny = cube.resize((round(cube.width * .42), round(cube.height * .42)), Image.LANCZOS)
    W = cube.width + small.width + 30
    pile = Image.new("RGBA", (W, cube.height + tiny.height - 70))
    pile.alpha_composite(small, (cube.width - 40, cube.height - small.height + (tiny.height - 70)))
    pile.alpha_composite(cube, (0, tiny.height - 70))
    pile.alpha_composite(tiny, (30, 0))
    return pile


def smoke_sprite(seed: int, w: int = 640, h: int = 280) -> Image.Image:
    """Nuage doux (bruit fractal + flou) en alpha, blanc."""
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32)
    for octave, amp in ((6, 1.0), (12, .55), (24, .3)):
        small = rng.random((max(2, h * octave // w), octave)).astype(np.float32)
        acc += amp * np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
    acc = (acc - acc.min()) / (acc.max() - acc.min())
    yy, xx = np.mgrid[0:h, 0:w]
    fade = np.clip(1 - (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2), 0, 1) ** 1.3
    alpha = np.clip((acc - .35) * 1.9, 0, 1) * fade
    img = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))
    out = Image.new("RGBA", (w, h), (225, 215, 240, 0))
    out.putalpha(img)
    return out


def title_text(words: list[str]) -> Image.Image:
    atlas = Image.open(BASE / "images/alphabet.png").convert("RGBA")
    xml = (BASE / "images/alphabet.xml").read_text(encoding="utf-8")
    glyphs = {}
    for tag in re.finditer(r"<SubTexture\s(.*?)/?>\s*(?=<|$)", xml, re.S):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', tag.group(1)))
        name = attrs["name"]
        if name.endswith(" bold0000"):
            x, y, w, h = (int(attrs[k]) for k in ("x", "y", "width", "height"))
            glyphs[name[0]] = atlas.crop((x, y, x + w, y + h))
    text = " ".join(words)
    height = max(glyph.height for glyph in glyphs.values())
    width = sum(glyphs[c].width + 6 if c in glyphs else 40 for c in text)
    canvas = Image.new("RGBA", (width + 20, height + 20))
    x = 10
    for char in text:
        if char in glyphs:
            canvas.alpha_composite(glyphs[char], (x, 10 + height - glyphs[char].height))
            x += glyphs[char].width + 6
        else:
            x += 40
    return canvas


def bubble(path: Path) -> None:
    img = Image.new("RGBA", (1110, 230))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, 1100, 220), 46, fill=(28, 14, 44, 245), outline=(255, 140, 30, 255), width=8)
    d.rounded_rectangle((26, 26, 1082, 202), 34, outline=(120, 60, 160, 255), width=3)
    d.polygon([(900, 12), (960, 12), (990, -40)], fill=(255, 140, 30, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    path.with_suffix(".xml").write_text(
        f'<?xml version="1.0" encoding="utf-8"?>\n<TextureAtlas imagePath="{path.name}">\n'
        '\t<SubTexture name="bubble idle0000" x="0" y="0" width="1110" height="230"/>\n</TextureAtlas>\n', encoding="utf-8")


def build_images() -> None:
    images = SOURCE / "images"
    # --- DJCreeper (spritesheet du mod VS DJCreeper) + icones
    (images / "characters").mkdir(parents=True, exist_ok=True)
    shutil.copy2(DJC / "images/characters/djcreeper.png", images / "characters/djcreeper.png")
    shutil.copy2(DJC / "images/characters/djcreeper.xml", images / "characters/djcreeper.xml")
    (images / "icons").mkdir(parents=True, exist_ok=True)
    icon = Image.open(DJC / "images/icons/icon-djcreeper.png").convert("RGBA")
    icon.save(images / "icons/icon-djcreeper.png")
    night = tint_mul(icon, (255, 120, 120))
    night.save(images / "icons/icon-djcreeper-night.png")
    # icon.png (citrouille Minecraft) : tools/build_example_icon.py
    # --- decor
    (images / "halloween").mkdir(parents=True, exist_ok=True)
    pumpkin_pile().save(images / "halloween/pumpkins.png")
    for i in range(3):
        smoke_sprite(11 + i).save(images / f"halloween/smoke{i}.png")
    # --- notes aux couleurs d'Halloween (style de notes perso)
    for name in ("notes", "noteStrumline"):
        sheet = Image.open(BASE / "shared/images" / f"{name}.png")
        out = hue_shift(sheet, 20, 1.0) if name == "notes" else tint_mul(sheet, (255, 220, 185))
        out.save(images / f"halloween/{name}.png")
        shutil.copy2(BASE / "shared/images" / f"{name}.xml", images / f"halloween/{name}.xml")
        text = (images / f"halloween/{name}.xml").read_text(encoding="utf-8")
        (images / f"halloween/{name}.xml").write_text(re.sub(r'imagePath="[^"]*"', f'imagePath="{name}.png"', text), encoding="utf-8")
    # --- titre de la semaine (menu histoire)
    (images / "storymenu/titles").mkdir(parents=True, exist_ok=True)
    import build_example_title
    build_example_title.title("HALLOWEEN NIGHT").save(images / f"storymenu/titles/{WEEK}.png")
    # --- props du menu histoire : DJCreeper
    bubble(images / "dialogue/bubble.png")


# ------------------------------------------------------------------ donnees
def anim(name, prefix, **kw):
    return {"name": name, "prefix": prefix, "frameRate": 24, **kw}


def voices(name: str) -> list[str]:
    """Sons de voix des dialogues (tools/build_example_voxsounds.py -> sounds/dialogue/<nom>-N.ogg)."""
    return [f"sounds/dialogue/{p.name}" for p in sorted((SOURCE / "sounds" / "dialogue").glob(f"{name}-*.ogg"))]


def build_data() -> None:
    d = SOURCE / "data"
    # personnage joueur : DJCreeper. Son dessin regarde a droite ; cote joueur, flipX false = miroir -> il regarde l'adversaire.
    djc = {"version": "1.0.0", "name": "DJCreeper", "assetPath": "characters/djcreeper", "flipX": False, "scale": 1.0, "isPixel": False,
           "offsets": [0, 22], "cameraOffsets": [-20, 20], "singTime": 8.0, "startingAnimation": "idle",
           "healthIcon": {"id": "djcreeper"},
           "animations": [anim("idle", "DJC idle", looped=False),
                          *[anim(f"sing{n}", f"DJC sing{n}") for n in ("LEFT", "DOWN", "UP", "RIGHT")],
                          *[anim(f"sing{n}miss", "DJC sadIn") for n in ("LEFT", "DOWN", "UP", "RIGHT")],
                          anim("hey", "DJC hey"), anim("laugh", "DJC laugh", looped=True),
                          anim("firstDeath", "DJC sadIn"), anim("deathLoop", "DJC sad", looped=True), anim("deathConfirm", "DJC hey")]}
    write(d / "characters/djcreeper.json", djc)
    # scenes : la maison hantee de la Week 2 + citrouilles ; version Nightmare plus sombre
    def stage(name, night):
        props = [
            {"name": "halloweenBG", "assetPath": "halloween_bg", "position": [-395, -505], "scroll": [1, 1], "zIndex": -100,
             "danceEvery": 0, "animType": "animateatlas", "startingAnimation": "idle",
             "animations": [{"name": "idle", "prefix": "static", "looped": False}, {"name": "lightning", "prefix": "thunder", "looped": False}]},
            {"name": "pumpkinsLeft", "assetPath": "halloween/pumpkins", "position": [-100, 612], "scale": [.78, .78], "scroll": [1.25, 1.25], "zIndex": 500},
            {"name": "pumpkinsRight", "assetPath": "halloween/pumpkins", "position": [1215, 730], "scale": [.62, .62], "scroll": [1.25, 1.25], "flipX": True, "zIndex": 501},
        ]
        return {"version": "1.0.0", "name": name, "cameraZoom": 1.0, "directory": "week2", "props": props,
                "characters": {"bf": {"position": [1020, 885], "zIndex": 300, "cameraOffsets": [-100, -100]},
                               "gf": {"position": [751.5, 787], "zIndex": 100, "cameraOffsets": [0, 0]},
                               "dad": {"position": [382, 865], "zIndex": 200, "cameraOffsets": [150, -100]}}}
    write(d / "stages/halloween-night.json", stage("Halloween Night", False))
    write(d / "stages/halloween-night-nightmare.json", stage("Halloween Night [Nightmare]", True))
    # style de notes
    write(d / "notestyles/halloween.json", {
        "version": "1.1.0", "name": "Halloween", "fallback": "funkin",
        "assets": {"note": {"assetPath": "halloween/notes", "data": {k: {"prefix": f"note{k.title()}"} for k in ("left", "down", "up", "right")}},
                   "noteStrumline": {"assetPath": "halloween/noteStrumline", "data": {
                       f"{k}{s}": {"prefix": f"{p}{k.title()}0"} for k in ("left", "down", "up", "right")
                       for s, p in (("Static", "static"), ("Press", "press"), ("Confirm", "confirm"))}}}})
    # chansons : metadonnees
    info = {
        "cobweb-cadence": dict(name="Cobweb", opp="spooky", opp_night="spooky-dark", vocals="spooky", bpm=124, rating=(2, 5, 8, 11)),
        "midnight-candlewick": dict(name="Candlewick", opp="spooky", opp_night="spooky-dark", vocals="spooky", bpm=92, rating=(1, 4, 7, 10)),
        "pumpkin-moon-panic": dict(name="Pumpkin", opp="monster", opp_night="monster", vocals="monster", bpm=140, rating=(3, 6, 9, 13)),
    }
    for sid, s in info.items():
        bpm_changes = [{"t": 0, "bpm": s["bpm"]}]
        meta = {"version": "2.2.4", "songName": s["name"], "artist": "DJCreeper + Python Engine", "charter": "Python Engine",
                "playData": {"difficulties": ["easy", "normal", "hard"], "songVariations": ["erect"],
                             "characters": {"player": "djcreeper", "girlfriend": "gf", "opponent": s["opp"],
                                            "playerVocals": ["djcreeper"], "opponentVocals": [s["vocals"]]},
                             "stage": "halloween-night", "noteStyle": "halloween", "album": "halloween-night", "previewStart": 4000,
                             "ratings": dict(zip(("easy", "normal", "hard"), s["rating"]))},
                "timeChanges": bpm_changes}
        night = json.loads(json.dumps(meta))
        # Erect (comme le jeu officiel) : le remix noté comme Hard, puis Nightmare, plus dur.
        night["playData"].update({"difficulties": ["erect", "nightmare"], "stage": "halloween-night-nightmare",
                                  "ratings": {"erect": s["rating"][2] + 1, "nightmare": s["rating"][3]}})
        night["playData"]["characters"].update({"girlfriend": "gf-dark", "opponent": s["opp_night"]})
        night["playData"].pop("songVariations")
        if sid == "pumpkin-moon-panic":
            for m in (meta, night):
                m["timeChanges"] = [{"t": 0, "bpm": 140}, {"t": SONG3_CHANGE_MS, "bpm": 160}]
        write(d / f"songs/{sid}/{sid}-metadata.json", meta)
        write(d / f"songs/{sid}/{sid}-metadata-erect.json", night)
    # semaine
    spooky_dance = [{"name": "danceLeft", "prefix": "idle0", "frameIndices": list(range(8))},
                    {"name": "danceRight", "prefix": "idle0", "frameIndices": list(range(8, 16))}]
    gf_left = [30, *range(15)]
    write(d / f"levels/{WEEK}.json", {
        "version": "1.0.0", "name": "HALLOWEEN NIGHT", "titleAsset": f"storymenu/titles/{WEEK}", "background": "#E8731A", "songs": SONGS,
        "props": [
            {"assetPath": "storymenu/props/spooky", "scale": 1.0, "offsets": [60, 100], "animations": spooky_dance},
            {"assetPath": "characters/djcreeper", "scale": .57, "flipX": True, "offsets": [-21, -171], "animations": [
                {"name": "idle", "prefix": "DJC idle", "frameRate": 24}, {"name": "confirm", "prefix": "DJC hey", "frameRate": 24}]},
            {"assetPath": "storymenu/props/gf", "scale": 1.0, "offsets": [200, 80], "animations": [
                {"name": "danceLeft", "prefix": "idle0", "frameIndices": gf_left},
                {"name": "danceRight", "prefix": "idle0", "frameIndices": list(range(15, 30))}]}]})
    # dialogues : speakers, bulle, conversations FR + EN
    write(d / "dialogue/boxes/halloween-bubble.json", {
        "version": "1.1.0", "name": "Halloween bubble", "assetPath": "dialogue/bubble", "isPixel": False, "scale": 1.0, "offsets": [-542, 110],
        "text": {"offsets": [130, 520], "width": 1000, "color": "#F7EBD2", "shadowColor": "#3A1B00", "shadowWidth": 2},
        "animations": [{"name": "idle", "prefix": "bubble idle", "frameRate": 24}]})
    write(d / "dialogue/speakers/djcreeper.json", {
        "version": "1.0.0", "name": "DJCreeper", "assetPath": "characters/djcreeper", "isPixel": False, "scale": 1.05, "flipX": True,
        "offsets": [322, -204], "sounds": voices("djc"), "animations": [anim("talk", "DJC idle", looped=True), anim("hey", "DJC hey"), anim("laugh", "DJC laugh", looped=True)]})
    write(d / "dialogue/speakers/spooky-kids.json", {
        "version": "1.0.0", "name": "Spooky Kids", "assetPath": "shared:characters/SpookyKids", "isPixel": False, "scale": .75,
        "offsets": [-291, -54.5], "sounds": voices("spooky"), "animations": [anim("talk", "spooky dance idle0", looped=True)]})
    write(d / "dialogue/speakers/lemon-monster.json", {
        "version": "1.0.0", "name": "Lemon Monster", "assetPath": "shared:characters/monster", "isPixel": False, "scale": .8,
        "hiddenLayers": ["HAT"],  # pas de bonnet de Noël : c'est Halloween
        "offsets": [-714.5, -150.5], "sounds": voices("monster"), "animations": [anim("talk", "Idle", looped=True)]})
    L = {  # (locuteur, animation, EN, FR)
        "cobweb-cadence": [
            ("spooky-kids", "Hehe... a creeper in OUR mansion? On Halloween night?", "Hehe... un creeper dans NOTRE manoir ? La nuit d'Halloween ?"),
            ("djcreeper", "Sss... I only came to find out why the lights keep flickering.", "Sss... je venais juste voir pourquoi les lumières clignotent."),
            ("spooky-kids", "That's us! Skid, Pump and a thousand cobwebs. Sing for your life!", "C'est nous ! Skid, Pump et mille toiles d'araignée. Chante si tu veux sortir !"),
            ("djcreeper", "Fine. But I won't explode... probably.", "D'accord. Mais je n'exploserai pas... normalement.")],
        "midnight-candlewick": [
            ("djcreeper", "The candles are moving by themselves. Are they listening?", "Les bougies bougent toutes seules. Elles nous écoutent ?"),
            ("spooky-kids", "Of course. Midnight is their favorite song. Don't miss a beat!", "Bien sûr. Minuit est leur chanson préférée. Ne rate aucun temps !"),
            ("djcreeper", "Those pumpkins... are staring at me.", "Ces citrouilles... elles me regardent."),
            ("spooky-kids", "Then dance for them, little green one. Until the last flame.", "Alors danse pour elles, petit vert. Jusqu'à la dernière flamme.")],
        "pumpkin-moon-panic": [
            ("lemon-monster", "RAAAWR! Who dares sing in my pumpkin patch?! I'll carve your blocky skull like a jack-o'-lantern!",
             "RAAAWR ! Qui ose chanter dans mon champ de citrouilles ?! Je vais te creuser le crâne comme une citrouille d'Halloween !"),
            ("djcreeper", "Uh... a visitor. Is that... lemon?", "Euh... un visiteur. C'est... du citron ?"),
            ("lemon-monster", "LEMON MONSTER! The Pumpkin Moon rises... now we PANIC!", "LEMON MONSTER ! La Lune Citrouille se lève... maintenant on PANIQUE !"),
            ("djcreeper", "Sss... then let's make some noise!", "Sss... alors faisons du bruit !")],
        "pumpkin-moon-panic-end": [
            ("lemon-monster", "...Fine. Take the candy. And the moon too, while you're at it.", "...Bon. Prends les bonbons. Et la lune aussi, tant que tu y es."),
            ("djcreeper", "Happy Halloween, everyone!", "Joyeux Halloween, tout le monde !")]}
    # Mode enfant : <id>-censored(-fr).json remplace les répliques trop violentes (ici la menace de Lemon Monster).
    censored = {"pumpkin-moon-panic": {0: ("RAAAWR! Who dares sing in my pumpkin patch?! Get out of here!",
                                           "RAAAWR ! Qui ose chanter dans mon champ de citrouilles ?! Dégage d'ici !")}}
    for cid, changes in censored.items():
        L[f"{cid}-censored"] = [(line[0], *changes[i]) if i in changes else line for i, line in enumerate(L[cid])]
    for cid, lines in L.items():
        for lang, idx, suffix in (("en", 1, ""), ("fr", 2, "-fr")):
            write(d / f"dialogue/conversations/{cid}{suffix}.json", {
                "version": "1.0.0", "backdrop": {"type": "solid", "fadeTime": .6, "color": "#D00A0612"},
                "music": {"asset": "breakfast", "fadeTime": 1.0, "looped": True}, "outro": {"type": "fade", "fadeTime": .6},
                "dialogue": [{"speaker": line[0], "speakerAnimation": "hey" if (line[0] == "djcreeper" and "Happy" in line[1]) else "talk",
                              "box": "halloween-bubble", "boxAnimation": "idle", "text": [line[idx]]} for line in lines]})
    # trophees
    ach = {
        "trick-or-treat": ("Trick or Treat", "Hit every candy note of a song.", "Trick or Treat", "Touche toutes les notes bonbon d'une chanson.", "djcreeper", False),
        "no-hex": ("Hex-free", "Finish a song without hitting a single hex note.", "Sans maléfice", "Finis une chanson sans toucher une seule note maudite.", "djcreeper", False),
        "spooky-season": ("Spooky Season", "Finish the three songs of Halloween Night.", "Saison d'Halloween", "Finis les trois chansons de Halloween Night.", "djcreeper", False),
        "nightmare-fuel": ("Nightmare Fuel", "Finish a Nightmare remix.", "Cauchemar", "Finis un remix Nightmare.", "djcreeper-night", True),
        "lemon-squeezed": ("Lemon Squeezed", "Beat Pumpkin without a single miss.", "Citron pressé", "Bats Pumpkin sans aucun raté.", "djcreeper-night", True)}
    for aid, (n, de, nfr, dfr, icon, hidden) in ach.items():
        write(d / f"achievements/{aid}.json", {"name": n, "name_fr": nfr, "description": de, "description_fr": dfr, "icon": icon, "hidden": hidden})
    write(SOURCE / "mod.json", {
        "name": "Halloween Night (Example Mod)",
        "description": "Example mod: a Halloween week with 3 songs + Nightmare remixes, dialogues (EN/FR), a video, a playable DJCreeper, a stage, special notes, "
                       "Dadbattle-style effects and Python scripts. Read the PDF guide to learn how it works!",
        "author": "Python Engine", "version": "2.0.0", "icon": "icon.png", "priority": 0})


SONG3_CHANGE_MS = 0.0  # ecrase dans main()


def cleanup() -> None:
    for sid in OLD:
        for rel in (f"songs/{sid}", f"data/songs/{sid}"):
            shutil.rmtree(SOURCE / rel, ignore_errors=True)
    for rel in ("data/achievements/snake-charmer.json", "data/characters/snake-kids.json", "data/stages/snake-stage.json",
                "data/levels/snake-week.json", "data/dialogue/boxes/snake-bubble.json", "data/dialogue/conversations/snake-charmer.json",
                "data/dialogue/speakers/bf-example.json", "data/dialogue/speakers/snake-kids.json", "scripts/golden_notes.py"):
        (SOURCE / rel).unlink(missing_ok=True)
    for rel in ("images/characters/SnakeKids.png", "images/characters/SnakeKids.xml", "images/icons/icon-snake-kids.png",
                "images/snake-stage/back.png", "images/storymenu/titles/snake-week.png"):
        (SOURCE / rel).unlink(missing_ok=True)
    shutil.rmtree(SOURCE / "images/snake-stage", ignore_errors=True)


def build_zip() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SOURCE.rglob("*")):
            if path.is_file() and path.suffix not in (".pyc", ".md") and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(SOURCE).as_posix())
    print("ok", OUTPUT, round(OUTPUT.stat().st_size / 1e6, 2), "Mo")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    import build_example_song as bs
    bs.timeline(bs.SONGS["pumpkin-moon-panic"])
    SONG3_CHANGE_MS = bs.SONGS["pumpkin-moon-panic"]["starts"][28]
    cleanup()
    build_images()
    build_data()
    build_zip()
