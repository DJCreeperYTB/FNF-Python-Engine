"""Construit mods/Guide de modding - Python Engine.pdf (reportlab).

python tools/build_guide_pdf.py
Les captures de Leaks/ ne sont ajoutees que si le fichier existe : on peut relancer le script plus tard.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parent.parent
LEAKS = ROOT / "Leaks"
OUT = ROOT / "mods" / "Guide de modding - Python Engine.pdf"
TEXT_W = A4[0] - 4.4 * cm

BLACK, GREY, LIGHT = colors.black, colors.HexColor("#777777"), colors.HexColor("#F0F0F0")
base = ParagraphStyle("base", fontName="Times-Roman", fontSize=10.8, leading=14.6, spaceAfter=6)
S = {
    "p": base,
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=19, leading=23, spaceAfter=10, keepWithNext=1, textColor=BLACK),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13.5, leading=17, spaceBefore=12, spaceAfter=6, textColor=BLACK, keepWithNext=1),
    "bul": ParagraphStyle("bul", parent=base, leftIndent=16, bulletIndent=4, spaceAfter=3),
    "cap": ParagraphStyle("cap", fontName="Times-Italic", fontSize=9.5, leading=12, alignment=TA_CENTER, spaceAfter=10),
    "cell": ParagraphStyle("cell", fontName="Times-Roman", fontSize=9.6, leading=12),
    "cellh": ParagraphStyle("cellh", fontName="Helvetica-Bold", fontSize=9.2, leading=12),
    "note": ParagraphStyle("note", parent=base, leftIndent=10, rightIndent=10, borderPadding=6, borderColor=BLACK,
                           borderWidth=0.8, spaceBefore=6, spaceAfter=12),
}


def fmt(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"`([^`]+)`", r'<font name="Courier" size="9.6">\1</font>', text)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)


class Heading(Paragraph):
    def __init__(self, text, level):
        super().__init__(fmt(text), S[f"h{level}"])
        self.level, self.plain = level, text


story: list = []


def H1(t): story.extend([CondPageBreak(9 * cm), Spacer(1, 14), Heading(t, 1)])
def H2(t): story.append(Heading(t, 2))
def P(t): story.append(Paragraph(fmt(t), S["p"]))
def NOTE(t): story.append(Paragraph("<b>Attention.</b> " + fmt(t), S["note"]))
def TIP(t): story.append(Paragraph("<b>Astuce.</b> " + fmt(t), S["note"]))


def BUL(*items):
    for item in items:
        story.append(Paragraph(fmt(item), S["bul"], bulletText="•"))


def CODE(src: str):
    lines = src.strip("\n").split("\n")
    for line in lines:
        assert len(line) <= 92, f"ligne de code trop longue ({len(line)}): {line}"
    table = Table([[line or " "] for line in lines], colWidths=[TEXT_W], rowHeights=[10.6] * len(lines))
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Courier"), ("FONTSIZE", (0, 0), (-1, -1), 8.4),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, 0), 5), ("BOTTOMPADDING", (0, -1), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.4, GREY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    table.hAlign = "LEFT"
    story.extend([table, Spacer(1, 8)])


def TABLE(header, rows, widths):
    data = [[Paragraph(fmt(h), S["cellh"]) for h in header]] + [[Paragraph(fmt(c), S["cell"]) for c in row] for row in rows]
    total = sum(widths)
    table = Table(data, colWidths=[TEXT_W * w / total for w in widths], repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, GREY), ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.extend([table, Spacer(1, 10)])


def IMG(name: str, caption: str, width=TEXT_W * 0.7):
    path = LEAKS / name
    if not path.is_file():
        return
    from PIL import Image as PI
    w, h = PI.open(path).size
    story.append(KeepTogether([Image(str(path), width=width, height=width * h / w), Paragraph(fmt(caption), S["cap"])]))


class Doc(BaseDocTemplate):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        frame = Frame(2.2 * cm, 2.3 * cm, TEXT_W, A4[1] - 4.8 * cm, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=self.footer)])
        self._n = 0
        self.pages = {}  # numéro de section (ou titre) -> page physique du PDF, pour l'écran AIDE

    @staticmethod
    def footer(canvas, doc):
        if doc.page > 1:  # la page de titre n'est pas numerotee
            canvas.setFont("Helvetica", 9)
            canvas.drawCentredString(A4[0] / 2, 1.3 * cm, str(doc.page - 1))
            canvas.setFont("Helvetica", 8)
            canvas.drawString(2.2 * cm, 1.3 * cm, "Python Engine - Guide de modding")

    def beforeDocument(self):
        self._n = 0  # multiBuild repasse plusieurs fois : les cles de signets doivent etre stables

    def afterFlowable(self, flowable):
        if isinstance(flowable, Heading):
            key = f"h{self._n}"
            self._n += 1
            self.canv.bookmarkPage(key)
            self.pages[flowable.plain.split()[0].rstrip(".") if flowable.plain[0].isdigit() else flowable.plain] = self.page
            self.canv.addOutlineEntry(flowable.plain, key, level=flowable.level - 1, closed=flowable.level == 1)
            self.notify("TOCEntry", (flowable.level - 1, flowable.plain, self.page - 1, key))


def title_page():
    def centered(name, size, leading, font="Helvetica-Bold", **kw):
        return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading, alignment=TA_CENTER, **kw)
    story.extend([
        Spacer(1, 6.5 * cm), Paragraph("Python Engine", centered("t", 40, 46)), Spacer(1, 0.6 * cm),
        Paragraph("Guide de modding", centered("t2", 26, 30)), Spacer(1, 1.2 * cm),
        Paragraph(fmt("Créer des chansons, des semaines, des personnages, des scènes, des dialogues, des trophées et des scripts Python "
                      "pour un moteur Friday Night Funkin' écrit en Python et pygame."),
                  centered("t3", 13, 18, "Times-Roman", leftIndent=30, rightIndent=30)),
        Spacer(1, 6 * cm), Paragraph("Version du moteur : 2.0", centered("t4", 11, 14, "Times-Italic")),
        PageBreak(), Paragraph("Sommaire", S["h1"]),
    ])
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("toc0", fontName="Helvetica-Bold", fontSize=10.5, leading=15, spaceBefore=4),
        ParagraphStyle("toc1", fontName="Times-Roman", fontSize=10, leading=12.5, leftIndent=18),
    ]
    story.append(toc)


title_page()
# ================================================================== 1
H1("1. Introduction")
P("Un **mod** est un dossier (ou un fichier `.zip`) rangé dans le dossier `mods/`. Il contient des fichiers qui **s'ajoutent** au jeu de base ou qui le **remplacent**. Pas besoin de toucher au code du moteur : tout passe par des fichiers JSON, des images, des sons et, si tu veux, des scripts Python.")
P("Avec Python Engine, un mod peut :")
BUL("ajouter des **chansons** (audio, chart, métadonnées, difficultés, variations) qui apparaissent dans Freeplay ;",
    "ajouter des **semaines** pour le Mode Histoire, avec leurs personnages animés et leur titre ;",
    "ajouter des **personnages** (spritesheets Sparrow, packer ou Adobe Animate) et leurs icônes de vie ;",
    "ajouter des **scènes** (décors, positions des personnages, caméra) ;",
    "ajouter des **dialogues** et des **vidéos** avant et après une chanson du Mode Histoire ;",
    "changer le **style des notes** et ajouter des **trophées** ;",
    "remplacer n'importe quelle image, son ou musique du jeu (menus, fond, musique du menu...) ;",
    "ajouter des **scripts Python** qui réagissent à la partie : notes, battements, événements du chart, dessin à l'écran...")
P("Ce guide est volontairement concret. Il s'appuie sur le **mod d'exemple** livré avec le moteur (`mods/ExampleMod.zip`, sources dans `mods_src/ExampleMod/`) : trois chansons d'Halloween (avec leurs remix Nightmare), une semaine, un personnage jouable, une scène, des dialogues en deux langues, une cinématique vidéo sous-titrée, des notes spéciales, des trophées et des scripts d'effets. Tout ce qui est expliqué ici correspond à ce que fait réellement le code du moteur.")
IMG("v2_menu_main.png", "Le menu principal : STORY MODE, FREEPLAY, MODS, TROPHIES, TOOLS, OPTIONS.")
NOTE("les scripts d'un mod sont du **code Python** exécuté sur ton ordinateur avec tous tes droits. N'installe que des mods dont tu fais confiance à l'auteur (voir le chapitre 12).")

# ================================================================== 2
H1("2. Installer et activer un mod")
H2("2.1 Où est le dossier mods ?")
P("Le dossier `mods/` se trouve **à côté de l'exécutable** (`FNF Python.exe`) pour la version compilée, ou **à côté de `main.py`** si tu lances le jeu avec Python. Il est créé automatiquement s'il n'existe pas. Dans le menu MODS, la touche **O** l'ouvre dans l'explorateur.")
H2("2.2 Un dossier ou un .zip")
BUL("**Dossier** : `mods/MonMod/` avec `mod.json` directement dedans.",
    "**Fichier .zip** : `mods/MonMod.zip`. `mod.json` doit être à la racine du zip, ou dans un seul dossier à l'intérieur (cas d'un dossier compressé tel quel). Le moteur extrait le zip une seule fois dans `%APPDATA%\\FNF Python\\mod_cache\\` et le ré-extrait si le zip change.",
    "Les dossiers et fichiers dont le nom commence par `.` ou `_` sont ignorés : pratique pour mettre un mod de côté.")
H2("2.3 Le menu MODS")
IMG("v2_menu_mods.png", "Le menu MODS : la liste, l'icône, la description et l'état ON / OFF du mod sélectionné.")
TABLE(["Touche", "Effet"], [
    ["Haut / Bas (ou W / S)", "Choisir un mod."],
    ["Entrée (ou Espace)", "Activer / désactiver le mod. Un mod en erreur (par exemple `mod.json` manquant ou illisible) ne peut pas être activé : un message explique pourquoi."],
    ["N", "Créer un mod vide (le mod modèle du chapitre 3). Débloque aussi le trophée Modder."],
    ["O", "Ouvrir le dossier `mods/`."],
    ["F5", "Recharger tous les mods maintenant."],
    ["Échap", "Revenir au menu principal. Si tu as activé, désactivé ou créé un mod, les mods sont rechargés à ce moment-là."],
], [3, 8])
P("Les mods désactivés sont retenus par **nom de dossier ou de zip** dans tes réglages.")
H2("2.4 La priorité")
P("Quand deux mods fournissent le même fichier, c'est celui du mod de **priorité la plus haute** qui gagne. La priorité est le champ `priority` de `mod.json` (entier, 0 par défaut ; à priorité égale, ordre alphabétique du nom). Le jeu de base passe toujours en dernier : n'importe quel mod actif peut donc remplacer un fichier du jeu de base.")
P("Le dossier **Editor Saves** (à côté de `mods/`, rempli par les éditeurs, voir chapitre 13) n'est pas un mod : il est toujours chargé et passe avant tous les mods.")
H2("2.5 Essayer le mod d'exemple")
P("`mods/ExampleMod.zip` est déjà installé. Ouvre MODS, vérifie qu'il est sur ON, reviens au menu, puis lance **Cobweb** (ou une des deux autres) dans Freeplay, ou la semaine **HALLOWEEN NIGHT** dans Story Mode. Elle contient trois chansons avec les difficultés easy / normal / hard et leur remix **Nightmare**.")
IMG("v2_mod_freeplay.png", "Cobweb dans Freeplay : BPM, difficulté, lettre de notation, et le nom du mod en bas de l'écran.")

# ================================================================== 3
H1("3. Créer ton premier mod")
P("Dans le menu MODS, appuie sur **N**. Le moteur crée `mods/MyMod/` (ou `MyMod2`, `MyMod3`... si le nom existe déjà) avec cette structure :")
CODE("""
mods/MyMod/
  mod.json
  data/
    songs/        <- un sous-dossier par chanson (metadata + chart)
    levels/       <- les semaines (un .json par semaine)
    characters/   <- un .json par personnage
    stages/       <- un .json par scène
  songs/          <- les fichiers audio : songs/<id>/Inst.ogg ...
  images/
    characters/   <- les spritesheets des personnages
  scripts/
    script.py     <- un script modèle avec on_create, on_beat, on_note_hit
""")
P("Tous ces dossiers sont facultatifs et tu peux en ajouter d'autres (`images/icons/`, `data/dialogue/`, `data/achievements/`, `videos/`, `music/`, `sounds/`...). Seul `mod.json` est obligatoire.")
H2("3.1 mod.json")
CODE("""
{
  "name": "Python Engine Example",
  "description": "Example mod: a new song, a week, a character...",
  "author": "Python Engine",
  "version": "1.0.0",
  "icon": "icon.png",
  "priority": 0
}
""")
TABLE(["Champ", "Rôle", "Par défaut"], [
    ["`name`", "Nom affiché dans le menu MODS (et en bas de l'écran Freeplay pour ses chansons).", "nom du dossier / du zip"],
    ["`description`", "Texte du panneau de droite (les retours à la ligne sont conservés, 6 lignes visibles).", "vide"],
    ["`author`", "Affiché « par ... ».", "vide"],
    ["`version`", "Texte libre, affiché « v1.0.0 ».", "\"1.0.0\""],
    ["`icon`", "Chemin d'une image dans le mod (une icône carrée de 150 x 150 convient). Absente = pas d'icône.", "\"icon.png\""],
    ["`priority`", "Entier : plus il est grand, plus les fichiers du mod gagnent sur ceux des autres mods.", "0"],
], [2, 7, 2.4])
P("Le fichier est lu en UTF-8 (BOM accepté). S'il est invalide, le mod apparaît en **ERROR** dans le menu et ne peut pas être activé.")
H2("3.2 Le cycle de travail")
BUL("Pour un mod **en dossier**, modifie tes fichiers directement. Les personnages, scènes, dialogues, icônes et scripts sont relus à chaque lancement d'une chanson : il suffit de relancer la chanson.",
    "Les **nouvelles chansons, semaines, trophées** et le contenu de `mod.json` sont lus quand les mods sont (re)chargés : appuie sur **F5** dans le menu MODS.",
    "Pour un **.zip**, il faut refaire le zip à chaque changement : le moteur le ré-extrait automatiquement. Travaille en dossier, zippe à la fin.",
    "Si quelque chose ne marche pas, regarde le texte rouge en haut à gauche pendant la chanson et la FAQ du chapitre 15.")

# ================================================================== 4
H1("4. Comment fonctionne la superposition")
P("Le moteur ne copie rien : quand il cherche un fichier, il regarde **dans chaque mod actif d'abord** (par ordre de priorité), **puis dans le jeu de base**. Le premier fichier trouvé est utilisé. Donc :")
BUL("un fichier de même chemin relatif **remplace** celui du jeu de base ;",
    "un fichier de chemin nouveau **s'ajoute**.")
TABLE(["Fichier dans ton mod", "Effet"], [
    ["`images/menuBG.png`", "Remplace le fond du menu."],
    ["`music/freakyMenu/freakyMenu.ogg`", "Remplace la musique du menu."],
    ["`sounds/scrollMenu.ogg`", "Remplace le son de défilement des menus."],
    ["`data/characters/bf.json`", "Remplace la définition de Boyfriend."],
    ["`data/stages/mainStage.json`", "Remplace la scène principale."],
    ["`data/songs/bopeebo/` (metadata + chart)", "Remplace le chart de Bopeebo (même id) ; l'audio du jeu de base reste utilisé."],
], [5, 6])
NOTE("pour l'audio d'une chanson, le moteur prend **tout le dossier** `songs/<id>/` du premier mod qui le contient. Si tu remplaces seulement `Voices-bf.ogg` d'une chanson du jeu de base, il faut donc aussi mettre `Inst.ogg` (et les autres pistes) dans le dossier de ton mod, sinon la chanson n'aura plus de musique.")
H2("4.1 Les bibliothèques et la syntaxe lib:chemin")
P("Le jeu de base range ses fichiers en **bibliothèques** : des dossiers comme `shared`, `week1`... qui contiennent eux-mêmes `images/`, `music/` ou `sounds/`. Un mod peut en créer : tout dossier à la racine du mod qui contient `images/`, `music/` ou `sounds/` devient une bibliothèque.")
P("Dans les JSON, un chemin d'image s'écrit **sans extension**, relatif à un dossier `images/`. Deux formes :")
BUL("`characters/djcreeper` : cherché dans `images/` puis `shared/images/` (mods puis jeu de base) ;",
    "`shared:stagefront` : cherché dans `shared/images/stagefront.png`. `week6:weeb/pixelUI/arrows-pixels` est `week6/images/weeb/pixelUI/arrows-pixels`. Pour ta propre bibliothèque `jungle`, écris `jungle:arbre` et place `jungle/images/arbre.png`.")
P("Quand tu écris un chemin sans préfixe, le moteur essaie aussi chaque bibliothèque, mais le préfixe est plus sûr.")
H2("4.2 Formats d'images supportés")
TABLE(["Format", "Fichiers", "Remarques"], [
    ["Image simple", "`nom.png`", "Une seule image."],
    ["Sparrow / Starling", "`nom.png` + `nom.xml`", "Balises `SubTexture` (`name`, `x`, `y`, `width`, `height`, `frameX`, `frameY`, `frameWidth`, `frameHeight`, `rotated`). Le XML est lu de manière tolérante."],
    ["Packer", "`nom.png` + `nom.txt`", "Une ligne par image : `nom = x y largeur hauteur`. Utilisé seulement s'il n'y a pas de `.xml`."],
    ["Adobe Animate (Texture Atlas)", "dossier `nom/` avec `Animation.json`, `spritemap1.json`, `spritemap1.png`", "Les « labels » de la timeline servent de préfixes d'animation."],
], [3, 4, 5])
P("Dans une spritesheet, le **préfixe** d'une animation est le début du nom des frames (`idle0000`, `idle0001`... ont le préfixe `idle0`). Le moteur compare sans tenir compte des majuscules et trie les frames par leur numéro final.")

# ================================================================== 5
H1("5. Ajouter une chanson")
P("Une chanson, c'est quatre choses : l'**audio**, les **métadonnées**, le **chart** et, au besoin, un **script**. Remplace `<id>` par l'identifiant de ta chanson (minuscules, sans espace, par exemple `cobweb-cadence`).")
CODE("""
songs/<id>/Inst.ogg                       <- obligatoire
songs/<id>/Voices-bf.ogg                  <- voix du joueur (facultatif)
songs/<id>/Voices-dad.ogg                 <- voix de l'adversaire (facultatif)
data/songs/<id>/<id>-metadata.json        <- obligatoire
data/songs/<id>/<id>-chart.json           <- obligatoire
data/songs/<id>/<id>.py                   <- script de la chanson (facultatif)
""")
NOTE("une chanson n'apparaît dans Freeplay que si elle a au moins un fichier `Inst*.ogg`, un fichier `*-metadata*.json` et un chart (avec au moins une note, ou tout neuf et vide, créé par « + NOUVELLE CHANSON »). Si elle manque, l'écran MODS dit en rouge ce qui ne va pas.")
H2("5.1 L'audio")
BUL("Format **OGG** (Vorbis). `Inst.ogg` est l'instrumental.",
    "Les voix s'appellent `Voices-<personnage>.ogg`, où `<personnage>` est le nom donné dans `playerVocals` et `opponentVocals` des métadonnées (`Voices-bf.ogg`, `Voices-dad.ogg`). Jusqu'à 6 pistes de voix sont lues, en même temps que l'instrumental.",
    "Si aucune voix nommée n'est trouvée, le moteur prend les fichiers `Voices-*.ogg` du dossier, puis un éventuel `Voices.ogg`.",
    "Une **variation** (voir 5.5) ajoute son nom en suffixe : `Inst-erect.ogg`, `Voices-bf-erect.ogg`. Si `Inst-<variation>.ogg` n'existe pas, `Inst.ogg` est utilisé.",
    "Sans `Inst.ogg` utilisable, un message rouge `songs/<id>/Inst.ogg not found` s'affiche et la chanson ne démarre pas.")
H2("5.2 Les métadonnées")
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
  "timeChanges": [ { "t": 0, "bpm": 130 } ]
}
""")
TABLE(["Champ", "Rôle"], [
    ["`songName`", "Nom affiché (par défaut : l'id mis en forme)."],
    ["`artist`", "Lu par le moteur mais pas affiché pour l'instant."],
    ["`playData.characters.player` / `opponent`", "Ids de personnages (fichiers `data/characters/<id>.json`). Défauts : `bf` et `dad`."],
    ["`playData.characters.girlfriend`", "Id de la GF. **Si absent, il n'y a pas de GF** dans la chanson."],
    ["`playerVocals` / `opponentVocals`", "Noms utilisés pour trouver les `Voices-<nom>.ogg` (par défaut l'id du personnage)."],
    ["`playData.stage`", "Id de scène (`data/stages/<id>.json`). Défaut : `mainStage`. Une scène introuvable affiche un message rouge."],
    ["`playData.noteStyle`", "Style des notes (chapitre 10). Défaut : `funkin`."],
    ["`playData.album`", "Texte affiché en haut de Freeplay : `volume1` donne « OST: VOLUME 1 ». N'importe quel texte convient."],
    ["`playData.previewStart`", "Position (en ms) où l'aperçu de la chanson démarre dans Freeplay."],
    ["`timeChanges`", "Liste de `{\"t\": ms, \"bpm\": nombre}`. Le premier BPM est celui de la chanson ; les suivants changent le tempo à l'instant `t` (en ms)."],
    ["`playData.difficulties`", "Informatif seulement : les difficultés réelles sont celles du chart qui contiennent des notes."],
], [4, 7])
H2("5.3 Le chart")
CODE("""
{
  "version": "2.0.0",
  "scrollSpeed": { "easy": 1.6, "normal": 2.0, "hard": 2.4 },
  "events": [
    { "t": 0,        "e": "FocusCamera", "v": { "char": 1 } },
    { "t": 8000, "e": "Spotlight", "v": { "on": true, "char": 1 } },
    { "t": 9000, "e": "Lightning", "v": {} }
  ],
  "notes": {
    "normal": [
      { "t": 8000.0, "d": 5, "l": 0 },
      { "t": 12000.0, "d": 0, "l": 432.692, "k": "candy" }
    ]
  }
}
""")
TABLE(["Champ", "Rôle"], [
    ["`notes`", "Un objet : une clé par difficulté (`easy`, `normal`, `hard`, ou un nom à toi), chacune avec la liste de ses notes. Une difficulté vide n'est pas proposée."],
    ["`t`", "Temps de la note en **millisecondes** depuis le début de la musique."],
    ["`d`", "Direction. **0 à 3 = joueur** (0 gauche, 1 bas, 2 haut, 3 droite), **4 à 7 = adversaire** (même ordre : 4 gauche ... 7 droite)."],
    ["`l`", "Longueur de la note longue (sustain) en ms. 0 = note simple."],
    ["`k`", "Type de note (texte libre, facultatif). `\"noanim\"` : le personnage ne joue pas son animation de chant sur cette note. Les autres valeurs ne font rien toutes seules : c'est ton script qui leur donne un sens (chapitre 12)."],
    ["`scrollSpeed`", "Vitesse de défilement : un objet `{\"easy\": 1.6, ...}` (clé `default` acceptée) ou un simple nombre. Le joueur peut imposer la sienne dans OPTIONS, qui l'emporte alors sur le chart."],
    ["`events`", "Liste d'événements `{\"t\": ms, \"e\": nom, \"v\": valeur}`. Voir 5.4."],
], [2, 9])
P("Les notes sont triées automatiquement par temps. Les fenêtres de jugement, utiles pour ton équilibrage : SICK jusqu'à 45 ms d'écart, GOOD 90 ms, BAD 135 ms, SHIT 166 ms ; une note est ratée quand elle a plus de 180 ms de retard.")
TIP("tu n'as pas besoin d'écrire les charts à la main : l'éditeur de chart (chapitre 13) pose les notes à la souris, gère les sustains et enregistre ce JSON pour toi.")
H2("5.4 Les événements du chart")
P("Le moteur comprend dix événements de base. Tous les événements, **y compris ceux que tu inventes**, sont aussi envoyés au hook `on_event` de tes scripts.")
TABLE(["`e`", "Valeur `v`", "Effet"], [
    ["`FocusCamera`", "`{\"char\": 0|1|2, \"x\": 0, \"y\": 0, \"ease\": \"INSTANT\"}` (ou juste un nombre = `char`)", "La caméra suit le joueur (0), l'adversaire (1) ou la GF (2 ; s'il n'y a pas de GF, le milieu des deux). `x` et `y` décalent le point. `ease` = `INSTANT` : saut immédiat, sinon glissement."],
    ["`PlayAnimation`", "`{\"target\": \"bf\", \"anim\": \"hey\"}`", "Joue une animation. `target` : `bf` / `dad` / `gf` (aussi `player`, `opponent`, `girlfriend`) ou le `name` d'un décor animé de la scène."],
    ["`ScrollSpeed`", "`{\"scroll\": 1.5, \"absolute\": false}`", "Change la vitesse : multiplie la vitesse du chart par `scroll`, ou la fixe si `absolute` est vrai. Ignoré si le joueur impose sa vitesse dans OPTIONS."],
    ["`SetHealthIcon`", "`{\"char\": 0|1, \"id\": \"djcreeper-night\"}`", "Change l'icône de vie du joueur (0) ou de l'adversaire (autre valeur)."],
    ["`ZoomCamera`", "`{\"zoom\": 1.2, \"duration\": 4, \"mode\": \"stage\", \"ease\": \"expo\", \"easeDir\": \"Out\"}`", "Zoome la caméra en douceur. `duration` est en **pas** (un pas = une double-croche ; 4 = un temps). `mode` = `stage` : `zoom` multiplie le zoom du décor (1 = normal) ; `direct` : zoom exact. `ease` : `linear` (défaut), `sine`, `quad`, `cube`, `quart`, `quint`, `expo`, `circ`, `back`, `elastic`, `bounce`, `smoothStep` ou `INSTANT` (saut immédiat) ; `easeDir` : `In`, `Out` ou `InOut`."],
    ["`SetCameraBop`", "`{\"rate\": 4, \"intensity\": 1.0}`", "Règle le petit coup de zoom de la caméra et de l'interface sur le rythme : tous les `rate` temps (0 = jamais), avec la force `intensity`. Par défaut, tous les 4 temps, comme le jeu officiel."],
    ["`FlashScreen`", "`{\"color\": [255, 255, 255], \"duration\": 400}`", "Flash plein écran de la couleur donnée (r, g, b), qui s'efface en `duration` ms. **Respecte l'option FLASHING LIGHTS** : rien n'est affiché si elle est coupée."],
    ["`ShakeCamera`", "`{\"intensity\": 10, \"duration\": 400}`", "Secoue la caméra de `intensity` pixels, de moins en moins fort pendant `duration` ms."],
    ["`Subtitle`", '`{"fr": "Salut !", "en": "Hi!", "duration": 3000}`', "Affiche un sous-titre pendant `duration` ms, dans la langue du jeu (option SOUS-TITRES respectée). Se pose aussi depuis le panneau d'événements de l'éditeur de chart."],
    ["`ChangeStage`", "`{\"stage\": \"spookyMansion\"}`", "Change de décor en pleine chanson : les personnages vont aux places du nouveau décor et la caméra se recadre. Le décor est chargé avant la chanson (pas de saccade). Les scripts reçoivent `on_stage_change(game, stage_id)`."],
], [2.3, 4.2, 5.5])
P("`PlayAnimation` marche aussi sur un élément du décor : l'éclair de la Week 2 est simplement `{\"target\": \"halloweenBG\", \"anim\": \"lightning\"}`. Les joueurs peuvent couper les petits coups de zoom sur le rythme avec l'option **ZOOMS DE CAMÉRA** (OPTIONS) ; `ZoomCamera` continue alors de fonctionner.")
P("Dans le mod d'exemple, `Lightning`, `Spotlight`, `Zoom`, `ZoomBeat`, `Shake`, `Tint`, `Rain`, `ArrowWave` et `Scroll` n'existent pas dans le moteur : c'est le script `scripts/halloween_fx.py` qui les interprète (chapitre 12). Dans l'éditeur de chart, la touche V ouvre le panneau d'événements (13.2) ; tes propres événements s'y ajoutent avec un simple fichier JSON (13.6).")
H2("5.5 Difficultés et variations")
P("Les difficultés sont les clés de `notes`. Pour le Mode Histoire, ce sont les difficultés **communes** à toutes les chansons de la semaine. Dans Freeplay, les flèches gauche/droite changent de difficulté. Une image `images/freeplay/freeplay<difficulté>.png` (et `images/storymenu/difficulties/<difficulté>.png` en Story) sert de titre de difficulté ; sans image, le nom s'affiche en texte : un nom de difficulté inventé fonctionne donc sans rien faire de plus.")
P("Une **variation** (par exemple `erect`) est un second jeu de fichiers pour la même chanson, nommés avec le suffixe :")
CODE("""
data/songs/bopeebo/bopeebo-chart-erect.json        (difficultés erect, nightmare)
data/songs/bopeebo/bopeebo-metadata-erect.json     (scène, personnages, BPM de la variation)
songs/bopeebo/Inst-erect.ogg   Voices-bf-erect.ogg   Voices-dad-erect.ogg
""")
P("Dans Freeplay, la variation est affichée sous la difficulté. Le chart d'une variation utilise ses propres métadonnées si le fichier existe, sinon celles de base.")
P("Le mod d'exemple utilise une variation `erect` pour ses remix **Nightmare** : `cobweb-cadence-chart-erect.json` contient une seule difficulté, `nightmare` ; `cobweb-cadence-metadata-erect.json` change la scène (`halloween-night-nightmare`), la GF (`gf-dark`) et l'opposant (`spooky-dark`) ; l'audio est `Inst-erect.ogg`, `Voices-spooky-erect.ogg`, `Voices-djcreeper-erect.ogg`. Dans Freeplay, la difficulté s'affiche NIGHTMARE. Un remix n'est pas un simple chart plus dur : l'instrumental et les voix sont refaits (même mélodie, orgue, choeurs et cordes à la place du clavecin, notes tenues hachées en répétitions).")
IMG("v2_mod_nightmare.png", "Cobweb en Nightmare : scène sombre teintée de rouge par l'événement Tint.")

# ================================================================== 6
H1("6. Ajouter une semaine")
P("Une semaine est un fichier `data/levels/<id>.json`. Elle regroupe des chansons jouées à la suite dans le Mode Histoire.")
H2("Créer une semaine pas à pas (tout dans le jeu)")
BUL("**1. La chanson** : TOOLS > ÉDITEUR DE CHART > « + NOUVELLE CHANSON ». Donne le dossier du mod, l'id (minuscules, sans espace, ex. `misra`), le nom et le BPM. Le jeu crée `data/songs/misra/misra-metadata.json` et `misra-chart.json` (Easy, Normal, Hard vides).",
    "**2. La musique** : mets `Inst.ogg` (et `Voices-bf.ogg`, `Voices-dad.ogg` pour les voix) dans `mods/<mod>/songs/misra/`. Le dossier s'ouvre tout seul ; ensuite F5 dans l'écran MODS ou relance la nouvelle chanson : l'éditeur s'ouvre directement dessus.",
    "**3. Le chart** : place les notes dans l'éditeur, Ctrl+S pour enregistrer, Tab pour passer à la difficulté suivante.",
    "**4. La semaine** : crée `mods/<mod>/data/levels/<id-de-la-semaine>.json` avec `\"songs\": [\"misra\"]` (exemple ci-dessous). L'id de chaque chanson doit être exactement le nom de son dossier dans `data/songs/`.",
    "**5. Vérifier** : la semaine apparaît dans le MODE HISTOIRE. Sinon, ouvre l'écran MODS et sélectionne ton mod : le jeu écrit en rouge ce qui manque (dossier `data/songs/<id>/`, métadonnées, chart, musique `Inst.ogg` ou JSON illisible).")
NOTE("Le dossier `songs/<id>/` ne contient que la musique. Le chart et les métadonnées vont dans `data/songs/<id>/` : sans eux la chanson (et donc la semaine) n'existe pas pour le jeu.")
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
TABLE(["Champ", "Rôle"], [
    ["`name`", "Nom affiché en haut à droite (par défaut : l'id en majuscules)."],
    ["`titleAsset`", "Image du titre dans la liste (sans extension). Défaut : `storymenu/titles/<id>`. Sans image, le nom est écrit avec la police du jeu. L'image est réduite pour tenir dans 380 x 100 ; le mod d'exemple utilise du 537 x 90."],
    ["`background`", "Couleur de la bande derrière les personnages, `#RRGGBB` (défaut : jaune `#F9CF51`)."],
    ["`songs`", "Liste d'ids de chansons dans l'ordre. Les ids inconnus sont ignorés ; sans aucune chanson valable, la semaine n'apparaît pas."],
    ["`props`", "Les personnages animés de la bande. Chaque élément : `assetPath`, `scale`, `flipX`, `isPixel`, `offsets` [x, y], `animations`."],
    ["`visible`", "`false` cache la semaine."],
], [2.5, 9])
P("Les props sont répartis de gauche à droite (un quart de l'écran par prop, plus l'`offset`). Ils dansent à chaque temps ; si un prop a une animation `confirm`, elle est jouée quand le joueur valide la semaine. Le mod d'exemple réutilise les props du jeu de base (`storymenu/props/spooky`, `gf`) et en fabrique un à partir de la spritesheet de DJCreeper (`characters/djcreeper`, réduit à 0.42) : un prop peut utiliser n'importe quelle spritesheet du mod.")
P("Les semaines des mods sont placées **après** celles du jeu de base. Les chansons s'enchaînent ; finir une semaine sans aucun raté débloque le trophée Untouchable.")
IMG("v2_mod_semaine.png", "La semaine du mod d'exemple dans le Mode Histoire.")

# ================================================================== 7
H1("7. Ajouter un personnage")
P("Un personnage est un fichier `data/characters/<id>.json` plus une image (spritesheet) et une icône de vie. L'id est celui que tu écris dans les métadonnées (`player`, `opponent`, `girlfriend`).")
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
H2("7.1 Champs du personnage")
TABLE(["Champ", "Rôle", "Défaut"], [
    ["`assetPath`", "Image de base (chapitre 4.2).", "`characters/<id>`"],
    ["`animations`", "Liste des animations (7.2).", "aucune"],
    ["`scale`", "Taille (6 pour les personnages pixel).", "1"],
    ["`flipX`", "Miroir horizontal. **Le sens est inversé quand le personnage joue côté joueur** : `bf.json` a `flipX: true` et est donc dessiné sans miroir côté joueur ; un personnage avec `flipX: false` est retourné s'il joue côté joueur.", "false"],
    ["`isPixel`", "Agrandissement sans lissage (pixel art). Sert aussi pour l'icône si `healthIcon.isPixel` est absent.", "false"],
    ["`danceEvery`", "Danse tous les N temps.", "1"],
    ["`singTime`", "Durée (en doubles-croches) pendant laquelle il reste sur l'animation de chant avant de revenir à la danse.", "8"],
    ["`offsets`", "[x, y] ajouté à la position du personnage dans la scène.", "[0, 0]"],
    ["`cameraOffsets`", "[x, y] ajouté au point que la caméra vise sur ce personnage.", "[0, 0]"],
    ["`healthIcon`", "`{\"id\": \"...\", \"isPixel\": false}` : l'id de l'icône de vie.", "l'id du personnage"],
    ["`startingAnimation`", "Animation de départ, qui sert aussi de pose de référence pour ancrer les pieds. Sinon : `idle`, `danceRight`, `danceLeft`, ou la première.", "-"],
], [2.4, 7, 2])
P("D'autres champs peuvent être présents dans les fichiers (`name`, `version`, `renderType`...) : le moteur les ignore.")
H2("7.2 Les animations")
TABLE(["Champ", "Rôle", "Défaut"], [
    ["`name`", "Nom de l'animation (voir 7.3).", "`idle`"],
    ["`prefix`", "Début du nom des frames dans la spritesheet (ou label Animate).", "le `name`"],
    ["`frameIndices`", "Liste de numéros de frames à jouer. Permet de couper une animation en deux (danceLeft / danceRight).", "toutes les frames"],
    ["`frameRate`", "Images par seconde.", "24"],
    ["`looped`", "Boucle l'animation.", "false"],
    ["`offsets`", "[x, y] de l'animation (voir plus bas).", "[0, 0]"],
    ["`assetPath`", "Une autre spritesheet pour cette animation seulement.", "celle du personnage"],
], [2.4, 7, 2])
P("Une animation dont le `prefix` n'existe pas dans la spritesheet est **ignorée silencieusement**. Si un personnage n'a aucune animation valide, un message rouge `Character '<id>' not found` s'affiche. Les `offsets` fonctionnent comme dans FNF : augmenter un offset décale le sprite vers la gauche / le haut. Le plus simple est de les régler avec l'éditeur de personnage (chapitre 13).")
H2("7.3 Les noms d'animations utilisés par le moteur")
TABLE(["Nom", "Quand"], [
    ["`idle` **ou** `danceLeft` + `danceRight`", "La danse. Avec la paire, le personnage alterne gauche/droite à chaque temps ; sinon `idle` est rejoué."],
    ["`singLEFT`, `singDOWN`, `singUP`, `singRIGHT`", "Quand une note de cette direction est jouée (par le joueur ou l'adversaire)."],
    ["`singLEFTmiss`, `singDOWNmiss`, `singUPmiss`, `singRIGHTmiss`", "Quand le joueur rate une note."],
    ["`hey`, `cheer`...", "Animations spéciales jouées par un événement `PlayAnimation` ou par un script (`play_special`). La danse ne les coupe pas avant la fin."],
    ["`firstDeath`, `deathLoop`, `deathConfirm`", "Écran de mort du **joueur**. Sans `firstDeath`, l'écran affiche simplement GAME OVER."],
], [5, 6])
P("Le son et les musiques de game over peuvent changer pour chaque personnage, avec un champ `death` dans `data/characters/<id>.json` (des chemins d'assets). Chaque clé est facultative : pour celles qui manquent, le son de base est gardé.")
CODE("""
"death": {
  "sfx": "sounds/mon_loss.ogg",
  "music": "music/mon_gameover.ogg",
  "musicEnd": "music/mon_gameover_fin.ogg"
}
""")
BUL("`sfx` : le son joué à la mort ; `music` : la musique qui boucle sur l'écran GAME OVER ; `musicEnd` : la musique quand le joueur confirme pour recommencer. C'est le personnage **joueur** de la chanson qui compte.")
P("Les majuscules comptent : `singLEFT`, pas `singleft`. Il n'est pas obligatoire de tout définir : une animation absente ne change simplement rien à l'écran.")
H2("7.4 L'icône de vie")
P("Un fichier `images/icons/icon-<id>.png` où `<id>` est `healthIcon.id`. C'est une image avec **deux icônes carrées côte à côte** (typiquement **300 x 150** : normale à gauche, en difficulté à droite). La seconde s'affiche quand la vie du personnage est basse (joueur sous 20, adversaire quand la vie du joueur dépasse 80). Une image carrée seule fonctionne aussi. Si l'icône n'est pas trouvée, le moteur essaie le nom sans `-playable`, le nom avant le premier tiret, puis `face`.")
H2("7.5 L'icône pixel de Freeplay (facultatif)")
P("Freeplay affiche d'abord une petite icône pixel `images/freeplay/icons/<id-adversaire>pixel.png` (+ son `.xml`, animation de préfixe `idle`). Sans elle, l'icône de vie de l'adversaire est utilisée : c'est ce que fait le mod d'exemple.")
H2("7.6 Cacher des calques (atlas Adobe Animate)")
P("`\"hiddenLayers\": [\"HAT\"]` dans `data/characters/<id>.json` (ou dans un speaker de dialogue) cache les calques dont le nom commence par ces mots. Le jeu de base s'en sert pour Monster : son atlas contient le bonnet de Noël de la Week 5, caché partout ailleurs. Le mod d'exemple fait pareil pour le portrait de Lemon Monster.")
H2("7.7 La pochette d'album de Freeplay")
P("Dans les métadonnées, `playData.album` donne l'id de l'album (le mod d'exemple : `\"halloween-night\"`). Freeplay affiche alors à droite `images/freeplay/albumRoll/<album>.png` (pochette carrée, 262 x 262 comme les officielles) et, dessous, son titre `images/freeplay/albumRoll/<album>-text.png` + `.xml` (animation de préfixe `idle`). Le script `tools/build_example_album.py` fabrique celle du mod d'exemple à partir du vrai décor.")
IMG("v2_editeur_personnage.png", "L'éditeur de personnage, pour régler les offsets de chaque animation.")

# ================================================================== 8
H1("8. Ajouter une scène")
P("Une scène est un fichier `data/stages/<id>.json` : une liste d'éléments de décor (`props`), la position des trois personnages et le zoom de la caméra. L'espace de la scène est en pixels, l'axe y vers le bas.")
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
H2("8.1 Champs de la scène")
TABLE(["Champ", "Rôle"], [
    ["`cameraZoom`", "Zoom de la caméra pendant la chanson (1 = taille normale ; plus petit = on voit plus large). Défaut 1."],
    ["`directory`", "Bibliothèque dans laquelle chercher les images des props (défaut `shared`)."],
    ["`props`", "Liste du décor (8.2). Sans aucun prop valable, le fond `shared/images/stageback.png` est utilisé."],
    ["`characters`", "Réglages de `bf`, `dad`, `gf` (8.3). Les valeurs absentes viennent des défauts (`bf` : [989.5, 885] ; `dad` : [335, 885] ; `gf` : [751.5, 787])."],
], [2.5, 9])
H2("8.2 Les props")
TABLE(["Champ", "Rôle", "Défaut"], [
    ["`name`", "Nom du prop (utile pour `PlayAnimation` et les scripts : `game.stage.props[\"nom\"]`).", "son numéro"],
    ["`assetPath`", "Image (chapitre 4). **`#RRGGBB`** crée un rectangle de couleur : `scale` = [largeur, hauteur] en pixels de scène.", "-"],
    ["`position`", "[x, y] du coin haut-gauche.", "[0, 0]"],
    ["`scale`", "Nombre, ou [x, y].", "1"],
    ["`scroll`", "Parallaxe : 1 = bouge avec la caméra, 0 = fixe à l'écran, 0.9 = un peu plus lent (arrière-plan), 1.3 = avant-plan.", "[1, 1]"],
    ["`zIndex`", "Ordre de dessin : plus grand = devant. Les personnages ont leur propre `zIndex` (GF 100, adversaire 200, joueur 300 par défaut) : mets le tien entre eux pour passer entre deux personnages.", "0"],
    ["`alpha`", "Opacité, de 0 à 1.", "1"],
    ["`isPixel`", "Agrandissement sans lissage.", "false"],
    ["`flipX`", "Miroir horizontal.", "false"],
    ["`animations`", "Fait un prop animé (mêmes champs que 7.2).", "aucune"],
    ["`danceEvery`", "Un prop animé danse tous les N temps (0 = ne danse pas).", "0"],
    ["`startingAnimation`", "Animation de départ d'un prop animé.", "la première"],
], [2.4, 7.2, 2])
H2("8.3 Les personnages dans la scène")
P("Pour chacun de `bf` (joueur), `dad` (adversaire) et `gf` (petite amie) : `position` est l'endroit où se posent les **pieds** du personnage (le bas-centre de sa pose de repos). `zIndex` fixe sa profondeur. `cameraOffsets` s'ajoute à celui du personnage pour décider où regarde la caméra quand elle le suit.")
P("Tu n'as pas besoin de deviner ces nombres : l'éditeur de scène et caméra (chapitre 13) déplace les personnages et les props à la souris et enregistre le JSON.")
P("Le décor du mod d'exemple **réutilise** le manoir de la Week 2 (`directory: \"week2\"`, atlas Adobe Animate `halloween_bg` dont les animations `idle` et `lightning` sont celles du jeu de base) et lui ajoute ses propres props : des citrouilles (blocs Minecraft rendus avec un contour noir) devant les personnages, avec une parallaxe de 1.25. La pluie, la brume, la lueur des citrouilles et les éclairs sont dessinés par le script du mod (chapitre 12) ; l'éclair joue l'animation `lightning` du prop avec `game.stage.props[\"halloweenBG\"].play(\"lightning\", now, force=True)`.")
IMG("v2_mod_decor.png", "Le décor Halloween du mod d'exemple : manoir de la Week 2, citrouilles, pluie, brume et braises.")
IMG("v2_editeur_scene_camera.png", "L'éditeur de scène et caméra : on déplace les personnages et on voit le cadre de la caméra.")

# ================================================================== 9
H1("9. Dialogues et cinématiques")
H2("9.1 Déclenchement automatique (Mode Histoire)")
P("En **Mode Histoire seulement**, avant le compte à rebours, le moteur cherche :")
BUL("une vidéo `videos/<id-chanson>.mp4` (aussi `.mkv`, `.webm` ou `.mov`), puis",
    "un dialogue `data/dialogue/conversations/<id-chanson>.json`.")
P("**Langues** : quand le jeu est en français, le moteur charge d'abord `<id>-fr.json` ; sinon (ou si ce fichier n'existe pas) `<id>.json`. Écris donc toujours les deux : `cobweb-cadence.json` en anglais et `cobweb-cadence-fr.json` en français, avec les mêmes répliques traduites.")
P("**Mode enfant** : quand l'option MODE ENFANT est active, le moteur prend d'abord `<id>-censored.json` (et `<id>-censored-fr.json`), comme les versions censurées de Roses dans le jeu de base, et `videos/<nom>-censored.mp4` pour les vidéos. Sans version censurée, le fichier normal est utilisé. Le mod d'exemple adoucit ainsi la menace de Lemon Monster avant Pumpkin.")
P("Après la chanson (si le joueur ne l'a pas perdue), il joue de la même façon `videos/<id>-end.mp4` puis `data/dialogue/conversations/<id>-end.json`. Pour une chanson avec variation, `<id>-<variation>.json` est essayé d'abord. Ils ne se rejouent pas quand tu recommences la chanson (R ou après une mort) et ne s'activent pas dans Freeplay ni dans le test de l'éditeur de chart. Si aucun fichier n'existe, rien ne se passe.")
P("Les vidéos sont lues avec la bibliothèque PyAV. Si elle manque ou que la vidéo est illisible, un message rouge s'affiche et la cinématique est sautée. Pour passer une vidéo, il faut **maintenir** Entrée ou Espace : un rond se remplit en bas à droite (plus de passage instantané).")
H2("9.1b Les sous-titres d'une vidéo")
P("Place à côté de la vidéo un fichier `videos/<nom>.subs.json`. Les sous-titres s'affichent si l'option SOUS-TITRES du jeu est active, dans la langue du jeu :")
CODE("""
{
  "en": [ [0.8, 3.2, "The old mansion never sleeps..."],
          [3.6, 6.2, "Thunder, candles, and a creeper."] ],
  "fr": [ [0.8, 3.2, "Le vieux manoir ne dort jamais..."],
          [3.6, 6.2, "Du tonnerre, des bougies, et un creeper."] ]
}
""")
P("Chaque ligne est `[début en secondes, fin en secondes, texte]`. Le mod d'exemple fournit `videos/cobweb-cadence.mp4` (9 secondes, fabriquées image par image en faisant tourner le vrai décor du jeu, voir `tools/build_example_video.py`) et ses sous-titres EN + FR.")
P("**Sous-titres pendant une chanson** : même format dans `data/songs/<id>/subtitles.json` (ou `subtitles-<variation>.json`), avec les temps de la chanson en secondes. Pour un sous-titre ponctuel, pose plutôt un événement `Subtitle` dans le chart (voir 5.4), ou appelle `game.show_subtitle(...)` depuis un script (cinématique dans le décor, voir 12.3). Une ligne peut contenir `\\n` pour passer à la ligne.")
P("**Style des sous-titres** (vidéos, chansons, événement `Subtitle`, `game.show_subtitle(texte, duration, style)`) : ajoute `\"style\": {...}` au fichier (toutes les lignes) ou un 4e élément `{...}` à une ligne (`[début, fin, texte, {style}]`). Dans l'éditeur de chart, le panneau de l'événement `Subtitle` propose les mêmes réglages. Clés possibles :")
TABLE(["Clé", "Effet"], [
    ["`font`", 'Police : nom d\'une police installée (`"Comic Sans MS"`) ou fichier `.ttf` du mod (`"fonts/ma-police.ttf"`). Vide = police du jeu.'],
    ["`size`", "Taille du texte (28 par défaut, 30 pour les vidéos)."],
    ["`bold`", "`true` / `false` : gras (oui par défaut)."],
    ["`color`", "Couleur du texte `[r, g, b]` (blanc par défaut)."],
    ["`opacity`", "Opacité du texte, de 0 à 100."],
    ["`background`", "Couleur du fond `[r, g, b]` (noir par défaut)."],
    ["`background_opacity`", "Opacité du fond, de 0 (pas de fond) à 100 (63 par défaut)."],
    ["`outline`", "`true` : contour noir autour des lettres (pratique sans fond)."],
    ["`position`", '`"bottom"` (par défaut), `"middle"` ou `"top"`.'],
], [3, 9])
H2("9.2 Une conversation")
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
TABLE(["Champ", "Rôle"], [
    ["`backdrop`", "Fond coloré : `color` en `#RRGGBB` ou `#AARRGGBB` (AA = opacité, comme dans Flixel), `fadeTime` = durée (s) de l'apparition."],
    ["`music`", "`asset` : nom d'un fichier `music/<nom>.ogg` ou `music/<nom>/<nom>.ogg` (dans le mod ou le jeu de base). `looped` (vrai par défaut)."],
    ["`outro.fadeTime`", "Durée de la disparition, en secondes (0.5 par défaut)."],
    ["`dialogue`", "Liste de répliques. Chaque réplique : `speaker` (id d'un fichier `speakers/`), `speakerAnimation` (défaut `talk`), `box` (id d'un fichier `boxes/`, défaut `default`), `boxAnimation` (défaut `idle`), `text` (une chaîne, ou une liste de morceaux collés avec des espaces)."],
], [2.5, 9])
P("Le texte s'écrit lettre par lettre (28 par seconde, avec un petit bip). **Entrée** ou **Espace** affiche tout le texte, puis passe à la réplique suivante ; **Échap** ferme le dialogue. Le texte tient sur 4 lignes au maximum.")
H2("9.3 Les speakers et les boxes")
P("`data/dialogue/speakers/<id>.json` décrit un portrait, `data/dialogue/boxes/<id>.json` une bulle. Les deux ont le même format de base :")
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
P("Comme dans le jeu officiel, un **speaker** part de sa première image centrée à l'écran (à l'échelle 1), puis ses `offsets` [x, y] sont ajoutés (et ceux de l'animation en cours aussi) : des speakers de mods V-Slice se placent donc pareil. Les `offsets` d'une **box** sont mesurés depuis le point (627, 370) de l'écran 1280 x 720. La première animation est la pose de départ ; si l'animation demandée par une réplique n'existe pas, `idle` est jouée quand elle existe. Une **box** a en plus un objet `text` : `offsets` (position du texte), `width` (largeur en pixels), `color` et `shadowColor` (`#RRGGBB`). Sans box, le texte est écrit en brun foncé en bas de l'écran.")
TIP("ajuste les `offsets` par essais : relance la chanson en Mode Histoire après chaque modification du JSON (pas besoin de F5).")
IMG("v2_mod_dialogue.png", "Un dialogue du mod d'exemple (portraits DJCreeper et Lemon Monster, bulle Halloween, texte en français).")
H2("9.4 Une cinématique scriptée")
P("Un script peut aussi lancer ses propres vidéos ou dialogues avec `game.play_video(nom)` et `game.start_dialogue(id)` (ils renvoient `False` si le fichier n'existe pas). Le compte à rebours attend la fin de ces cinématiques. Pour une cinématique faite avec du code (déplacer la caméra, dessiner...), mets `game.hold_countdown = True` dans `on_create` : le compte à rebours est gelé et seul `on_update` est appelé. Quand tu as fini, appelle `game.start_countdown()`.")
CODE("""
def on_create(game):
    game.hold_countdown = True       # on gele le compte à rebours
    game.t0 = 0.0
    game.focus_camera(1, instant=True)

def on_update(game, dt):
    if game.hold_countdown:
        game.t0 += dt
        if game.t0 > 3:              # après 3 secondes de cinématique
            game.start_countdown()   # le compte à rebours démarre
""")

# ================================================================== 10
H1("10. Les styles de notes")
P("Le style est le champ `playData.noteStyle` des métadonnées (`funkin` ou `pixel` dans le jeu de base). Le fichier `data/notestyles/<style>.json` indique d'où viennent les images. **Seules ces clés sont lues** :")
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
BUL("`assets.note.assetPath` : spritesheet **Sparrow** des notes ; `data.<left|down|up|right>.prefix` : la frame de chaque flèche (défaut `noteLeft`...). `isPixel` active l'agrandissement sans lissage.",
    "`assets.noteStrumline.assetPath` : spritesheet des récepteurs ; `data.<direction>Static`, `<direction>Press`, `<direction>Confirm` : les trois états (défauts `static<Direction>0`, `press<Direction>0`, `confirm<Direction>0`). Seule la **première frame** de chaque préfixe est utilisée.",
    "Les flèches sont toujours redimensionnées à la même taille : `scale`, `offsets`, `fallback`, `holdNote`, `noteSplash`... sont ignorés. Les notes longues sont dessinées par le moteur (barre colorée).",
    "Si une spritesheet n'est pas un Sparrow valide, le moteur retombe sur les flèches par défaut (`shared:notes`, `shared:noteStrumline`).")
P("Le mod d'exemple définit le style `halloween` (`data/notestyles/halloween.json`) : il pointe vers `images/halloween/notes.png` et `noteStrumline.png`, des copies de celles du jeu de base teintées en orange, et déclare `\"fallback\": \"funkin\"`. Les métadonnées de chaque chanson ont `\"noteStyle\": \"halloween\"`.")
NOTE("seul le style nommé exactement `pixel` active aussi le compte à rebours et les rangs (SICK, GOOD...) en version pixel. Un style personnalisé garde ceux du style normal.")

# ================================================================== 11
H1("11. Les trophées")
P("Un trophée est un fichier `data/achievements/<id>.json`. L'id est le nom du fichier. Le trophée s'affiche dans le menu TROPHIES (avec le nom du mod entre crochets) et une notification apparaît quand il est débloqué.")
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
TABLE(["Champ", "Rôle"], [
    ["`name`, `description`", "Textes en anglais (par défaut : l'id, et rien)."],
    ["`name_fr`, `description_fr`", "Utilisés à la place quand le jeu est en français."],
    ["`icon`", "Soit l'id d'une icône de vie (`djcreeper` -> `images/icons/icon-djcreeper.png`), soit un chemin d'image dans le mod (s'il contient `/` ou finit par `.png`)."],
    ["`hidden`", "`true` : le nom et la description s'affichent « ??? » tant que le trophée n'est pas débloqué."],
], [3, 8])
P("Un trophée se débloque depuis un script avec `game.unlock_achievement(\"mon-id\")`. Un id qui n'existe pas est ignoré, de même qu'un trophée déjà obtenu. Les trophées du moteur (First Beat, Full Combo...) ne peuvent pas être remplacés : un fichier de mod dont l'id est déjà pris est ignoré. **Pendant un test lancé depuis l'éditeur de chart, aucun trophée n'est débloqué.**")

# ================================================================== 12
H1("12. Les scripts Python")
NOTE("un script est un programme Python complet, lancé avec **tous les droits** de ton compte (il peut lire, écrire ou effacer des fichiers, ouvrir le réseau...). Le moteur ne l'isole pas. **N'installe que des mods de personnes de confiance**, et lis les fichiers `.py` d'un mod téléchargé avant de l'activer.")
H2("12.1 Où mettre un script")
BUL("`scripts/*.py` dans un mod : script **global**, chargé pour **toutes** les chansons tant que le mod est actif ;",
    "`data/songs/<id>/*.py` : script de **chanson**, chargé seulement pour la chanson `<id>`.")
P("Les scripts sont chargés au début de chaque chanson (donc à chaque recommencement avec R). Ordre : les mods de la priorité la plus basse à la plus haute, et par ordre alphabétique dans chaque dossier. Chaque fichier est un module indépendant : **un script ne peut pas en importer un autre** du mod. Ses variables au niveau du fichier sont remises à zéro à chaque chanson.")
P("Chaque fonction est facultative. Le script définit simplement celles dont il a besoin ; le moteur les appelle avec l'objet `game` en premier argument.")
H2("12.2 Les hooks")
TABLE(["Fonction", "Quand elle est appelée"], [
    ["`on_create(game)`", "Une fois, quand la chanson est chargée (personnages, scène, notes prêts), avant le compte à rebours. C'est ici qu'on prépare ses variables, qu'on teinte des notes, qu'on met `hold_countdown`, qu'on lance un dialogue."],
    ["`on_countdown(game, n)`", "À chaque étape du compte à rebours : `n` vaut 0 (trois), 1 (deux), 2 (un), 3 (GO)."],
    ["`on_beat(game, beat)`", "À chaque temps (`beat` entier). Les temps du compte à rebours sont négatifs : la musique commence au temps 0."],
    ["`on_step(game, step)`", "À chaque double-croche (4 par temps ; `step` entier)."],
    ["`on_update(game, dt)`", "À chaque image (60 par seconde), `dt` en secondes. Pas appelé pendant la pause, ni pendant un dialogue ou une vidéo avant la chanson. Appelé pendant un `hold_countdown`."],
    ["`on_note_hit(game, note, rating)`", "Le joueur touche une note. `rating` vaut `\"SICK\"`, `\"GOOD\"`, `\"BAD\"` ou `\"SHIT\"`. Pour un sustain, appelé à la tête de la note."],
    ["`on_note_miss(game, note)`", "Le joueur rate une note, ou lâche un sustain trop tôt."],
    ["`on_note_avoided(game, note)`", "Une note marquée `note.avoid = True` est passée sans être touchée (pas de raté compté, le botplay ne la touche pas)."],
    ["`on_stage_change(game, stage_id)`", "Le décor vient de changer (événement `ChangeStage` ou `game.change_stage(id)`)."],
    ["`on_ghost_miss(game, lane)`", "Le joueur appuie sans note, **seulement si** « appuis libres » (ghost tapping) est désactivé dans OPTIONS. `lane` : 0 à 3."],
    ["`on_opponent_hit(game, note)`", "L'adversaire joue une note."],
    ["`on_event(game, event)`", "Un événement du chart est atteint (le moteur l'a déjà traité s'il le connaît). `event` = `{\"t\": ms, \"e\": nom, \"v\": valeur}`."],
    ["`on_key_down(game, event)`", "Une touche est enfoncée pendant la chanson (`event.key`). Renvoyer `True` garde la touche : le jeu ne l'utilise pas (ex. Entrée sur un encart sans mettre le jeu en pause)."],
    ["`on_draw_stage(game, screen)`", "Après le dessin de la scène et des personnages, **avant** les notes et l'interface."],
    ["`on_draw(game, screen)`", "Après l'interface (notes, barre de vie, score, compte à rebours), avant la pause et les messages d'erreur. `screen` est une surface pygame de 1280 x 720."],
    ["`on_game_over(game)`", "La vie tombe à zéro."],
    ["`on_song_end(game)`", "La musique se termine (avant le dialogue de fin du Mode Histoire). Pas appelé si le joueur quitte avec Échap."],
], [4.2, 8])
P("Quand tu testes depuis l'éditeur de chart avec un départ au milieu, les événements déjà passés sont rejoués d'un coup au démarrage (ils appellent donc `on_event`).")
H2("12.3 L'objet game")
P("C'est la partie en cours. Tout ce qui suit existe vraiment. Le temps `now` des personnages est `pygame.time.get_ticks()`.")
TABLE(["Nom", "Contenu"], [
    ["`game.health`", "La vie, de **0 à 100** (départ 50). Modifiable ; à 0 : game over."],
    ["`game.score`, `combo`, `max_combo`, `misses`", "Score, combo, meilleur combo, nombre de ratés. `sick`, `good`, `bad`, `shit` comptent les jugements. `game.accuracy()` donne la précision en %."],
    ["`game.notes`", "Liste de toutes les notes. Voir le tableau plus bas."],
    ["`game.song`", "Infos de la chanson : `song_id`, `name`, `artist`, `bpm`, `mod`, `album`, `stage`, `player`, `opponent`, `girlfriend`."],
    ["`game.difficulty`, `game.variation`, `game.chart_key`", "Difficulté jouée (`\"hard\"`...), variation (`\"\"` si aucune), clé complète."],
    ["`game.song_time`", "Temps de la chanson en ms (négatif pendant le compte à rebours). `game.chart_time` : le même, corrigé du délai réglé dans OPTIONS ; c'est celui que les notes utilisent."],
    ["`game.beat_at(ms)`, `game.beat_length(ms)`", "Numéro de temps (avec virgule) à un instant, et durée d'un temps en ms."],
    ["`game.scroll_speed`", "Vitesse de défilement actuelle (modifiable). `chart_speed` : celle du chart. `downscroll` : vrai si les notes descendent."],
    ["`game.player`, `game.opponent`, `game.girlfriend`", "Les personnages (`girlfriend` vaut `None` s'il n'y en a pas). Voir plus bas."],
    ["`game.stage`", "La scène : `stage.props` (dictionnaire nom -> prop), `stage.zoom`, `stage.camera_zoom`."],
    ["`game.camera_zoom`", "Multiplicateur du zoom du décor (1.0 = normal), le même que celui de l'événement `ZoomCamera` ; tu peux le changer à la main. `game.view_zoom` (lecture seule) est le zoom réel : décor x `camera_zoom` x petit coup sur le rythme."],
    ["`game.bop_rate`, `game.bop_intensity`, `game.hud_bop_intensity`", "Le coup de zoom sur le rythme : tous les `bop_rate` temps (4 par défaut, 0 = jamais), force de la caméra (1.015 par défaut) et de l'interface (0.03 par défaut). C'est ce que règle l'événement `SetCameraBop`."],
    ["`game.flash_screen(color, duration)`", "Flash plein écran : `color` = (r, g, b), `duration` en ms. Respecte FLASHING LIGHTS."],
    ["`game.shake_camera(intensity, duration)`", "Secousse de la caméra : `intensity` en pixels, `duration` en ms."],
    ["`game.show_subtitle(texte, duration)`", 'Affiche un sous-titre `duration` ms (3000 par défaut). `texte` : une chaîne, ou `{"fr": "...", "en": "..."}` pour suivre la langue du jeu. Pratique pour une cinématique jouée dans le décor.'],
    ["`game.strum_offset`", "Une **fonction** `strum_offset(player, lane) -> (dx, dy)` que tu remplaces (`player` vaut `True` pour les flèches du joueur, `lane` va de 0 à 3). Elle décale la flèche en pixels ; les notes, les splashs et les hold covers suivent. Exemple : `game.strum_offset = lambda player, lane: (0, 20 * math.sin(game.song_time / 300 + lane))`."],
    ["`game.strum_alpha`", "Opacité des flèches fixes, de 0.0 à 1.0 : `game.strum_alpha[0][lane]` pour l'adversaire, `game.strum_alpha[1][lane]` pour le joueur (`lane` de 0 à 3)."],
    ["`game.lane_for_key`", "Une **fonction** `lane_for_key(lane) -> lane` qui dit quelle flèche une touche joue. Remplace-la pour remapper les touches : `game.lane_for_key = lambda lane: 3 - lane` donne un miroir."],
    ["`game.cam`, `game.cam_target`", "Position de la caméra `[x, y]` et point qu'elle vise (elle glisse vers lui). `game.focus_camera(cible, x=0, y=0, instant=False)` : `cible` 0 joueur, 1 adversaire, 2 GF."],
    ["`game.world_to_screen(x, y, scroll=(1, 1))`", "Convertit un point de la scène en position à l'écran avec la caméra actuelle."],
    ["`game.start_dialogue(id)`, `game.play_video(nom)`", "Voir chapitre 9."],
    ["`game.hold_countdown`, `game.start_countdown()`", "Voir 9.4."],
    ["`game.unlock_achievement(id)`", "Voir chapitre 11."],
    ["`game.app`", "L'application : `app.text(screen, texte, (x, y), taille, color=..., center=False, bold=False, outline=False, right=False, raw=False)` pour écrire (mets `raw=True` pour un texte à toi, sinon le moteur tente de le traduire), `app.play_sound(\"sounds/xxx.ogg\", volume)`, `app.settings` (par exemple `app.settings.flashing_lights`), `app.assets`, `app.volume`."],
    ["`game.warnings`", "Liste de textes affichés en rouge au début de la chanson : tu peux y ajouter les tiens."],
    ["`game.paused`, `game.finished`, `game.song_started`", "États de la partie."],
], [4.4, 8])
P("**Une note** (`PlayNote`) :")
TABLE(["Attribut", "Sens"], [
    ["`time`", "Temps en ms."],
    ["`lane`", "0 gauche, 1 bas, 2 haut, 3 droite."],
    ["`player`", "`True` si c'est une note du joueur."],
    ["`length`", "Longueur du sustain en ms (0 = note simple)."],
    ["`kind`", "Le `k` du chart (chaîne vide si absent)."],
    ["`state`", "`\"pending\"`, `\"holding\"`, `\"hit\"`, `\"miss\"` ou `\"skip\"`."],
    ["`color`", "`None`, ou un tuple (r, g, b) à poser : teinte la flèche et le sustain."],
    ["`alpha`", "Opacité de la note : 1.0 (normale) à 0.0 (invisible, mais toujours jouable)."],
    ["`avoid`", "`True` : note à éviter (la laisser passer n'est pas un raté ; voir `on_note_avoided`)."],
], [2, 9])
P("**Un personnage** (`Character`) : `play(nom, now, force=False)` joue une animation (renvoie `False` si elle n'existe pas), `play_special(nom, now)` joue une animation d'événement que la danse ne coupe pas, `has(nom)` teste son existence, `sing(lane, now, miss=False)` fait chanter, `x` et `y` donnent la position, `visible` l'affiche ou le cache, `id` est son id.")
NOTE("les hooks s'exécutent dans la boucle du jeu, à 60 images par seconde : ne fais rien de lent dedans (pas de lecture de fichier ni de gros calcul à chaque image). Crée plutôt tes surfaces pygame dans `on_create`.")
H2("12.4 Exemple : des notes spéciales (pumpkin_notes.py)")
P("Voici l'idée du script global du mod d'exemple. Il donne un sens à deux types de notes posés dans le chart : `\"candy\"` (bonus orange) et `\"hex\"` (note maudite violette qu'il faut **éviter**) :")
CODE("""
import pygame
CANDY, HEX = (255, 150, 30), (170, 60, 255)

def on_create(game):
    game.candy_total = game.candy_hit = game.hex_hit = 0
    for note in game.notes:
        if note.kind == "candy":
            note.color = CANDY            # teinte de la flèche et de sa traînée
            game.candy_total += 1
        elif note.kind == "hex":
            note.color = HEX
            note.avoid = True             # à éviter : la laisser passer = pas un raté

def on_note_hit(game, note, rating):
    now = pygame.time.get_ticks()
    if note.kind == "candy":
        game.candy_hit += 1
        game.health = min(100, game.health + 12)
        game.human.play_special("hey", now)   # human = le perso que tu joues
    elif note.kind == "hex":              # toucher une note maudite = un raté
        game.hex_hit += 1
        pass                              # le moteur compte déjà le raté : rien en plus

def on_note_avoided(game, note):          # une note `avoid` est passée sans être touchée
    game.health = min(100, game.health + 5)

def on_song_end(game):
    if game.candy_total and game.candy_hit == game.candy_total:
        game.unlock_achievement("trick-or-treat")
""")
P("Le mod d'exemple n'a que deux notes spéciales, **expliquées au joueur** par un encart (`scripts/halloween_tuto.py`, FR/EN selon `game.app.settings.language`, une fois par session ; il retient le countdown avec `game.hold_countdown` puis appelle `game.start_countdown()`) : la note **obligatoire** (`candy`, orange) et la note **à éviter** (`hex`, violette). En **Hard et Nightmare** seulement, rater la première ou toucher la seconde est une **mort immédiate** (`game.health = 0`) ; en Easy et Normal ce n'est qu'un raté. Les notes `hex` ne remplacent jamais une note chantée : le générateur les ajoute dans les silences, entre deux notes ou à côté d'une note chantée. Les scripts globaux vérifient `game.song.song_id` pour ne rien faire sur les chansons du jeu de base.")
H2("12.5 Exemple : des effets façon Dadbattle (halloween_fx.py)")
P("Le script `scripts/halloween_fx.py` reproduit les effets de Dadbattle dans Psych Online avec des **événements personnalisés** posés dans le chart (champ `\"e\"`) et lus par `on_event`. Il couvre à peu près tout ce qu'un script peut faire sur l'image :")
TABLE(["Événement", "Valeur `v`", "Effet"], [
    ["`Lightning`", "`{}`", "Éclair (le moteur sait faire pareil avec `PlayAnimation`) : animation `lightning` du décor, flash bleuté, tonnerre (`week2/sounds/thunder_*.ogg`), petit zoom."],

    ["`Zoom`", "`{\"amount\": 0.06, \"ms\": 500}`", "Coup de zoom de la caméra qui retombe."],
    ["`ZoomBeat`", "`{\"every\": 2, \"amount\": 0.03}`", "Zoom sur le rythme tous les N temps (`every` 0 = arrêt)."],
    ["`Shake`", "`{\"power\": 10, \"ms\": 400}`", "Secousse amortie de la caméra."],
    ["`Tint`", "`{\"color\": [r,g,b], \"alpha\": 60, \"ms\": 600}`", "Voile de couleur sur la scène, avec fondu (changement d'ambiance : bleu, orange, rouge Nightmare)."],
    ["`Spotlight`", "`{\"on\": true, \"char\": 0|1|2}`", "Projecteur : écran assombri, cône de lumière sur le chanteur, fumée en bas de l'écran."],
    ["`Rain`", "`{\"level\": 0|1|2}`", "Pluie."],
    ["`ArrowWave`", "`{\"on\": true, \"amp\": 14}`", "Les flèches ondulent."],
    ["`Scroll`", "`{\"mode\": \"middle\"|\"normal\"|\"flip\"}`", "Flèches du joueur au centre, retour, ou scroll inversé (haut/bas)."],
], [2.2, 4.6, 5.8])
P("Les techniques employées, toutes possibles pour ton propre mod :")
BUL("**Zoom et secousse de la caméra** : dans `on_draw_stage`, on copie l'écran déjà dessiné (`screen.copy()`), on le redimensionne (`pygame.transform.scale`) et on le redessine centré, décalé pour la secousse. Les notes et l'interface (dessinées après) ne bougent pas.",
    "**Projecteur** : un calque noir semi-transparent dont on **soustrait** l'alpha d'une image de cône (`special_flags=pygame.BLEND_RGBA_SUB`), puis un faisceau chaud, puis des nuages de fumée (`images/halloween/smoke*.png`) qui dérivent.",
    "**Mouvement des flèches** : `game.strum_x` est remplacé par une fonction qui ajoute une sinusoïde ; `game.PLAYER_X` / `game.OPPONENT_X` glissent vers le centre ; inverser `game.downscroll` et recalculer `game.receptor_y` retourne le scroll en pleine chanson.",
    "**Décor animé** : `game.stage.props[\"halloweenBG\"].play(\"lightning\", now, force=True)` joue l'animation d'un prop.",
    "**Caméra pendant le compte à rebours** : le script de chanson `pumpkin-moon-panic.py` part sur DJCreeper puis, dans `on_beat` (temps négatifs = compte à rebours), fait glisser la caméra vers Lemon Monster. Pour une vraie pause avant la chanson, l'encart `scripts/halloween_tuto.py` utilise `hold_countdown = True` puis `start_countdown()` (voir 9.4).")
IMG("v2_mod_projecteur.png", "L'événement Spotlight : écran assombri, cône de lumière sur DJCreeper, fumée en bas.")
IMG("v2_mod_eclair.png", "L'événement Lightning : l'animation d'éclair du décor, un flash et un zoom.")
IMG("v2_mod_fleches_milieu.png", "Les événements Scroll (flèches au centre) et ArrowWave, avec le voile rouge de Tint.")
TIP("depuis la mise à jour des modificateurs de Freeplay, `game.human` est le personnage que le joueur contrôle et `game.cpu` celui qui est automatique ; utilise-les plutôt que `game.player` / `game.opponent` quand tu veux parler de « celui qui joue ». Ils sont accompagnés de `game.rate` (vitesse de la chanson, jusqu'à x4), `game.opponent_mode`, `game.judgment` (`\"normal\"` ou `\"easy\"`) et `game.scroll_mult`.")
H2("12.6 Erreurs et modules disponibles")
BUL("Un script qui plante **ne fait jamais planter le jeu**. Le message (`fichier.py / hook: dernière ligne de l'erreur`) s'affiche en **rouge** en haut à gauche pendant 8 secondes, et le détail complet est écrit à la suite dans **`mods/errors.log`** (avec la date).",
    "La fonction qui a planté est **désactivée** pour le reste de la chanson (les autres hooks du script continuent) : pas de déluge d'erreurs à 60 images par seconde. Recommence la chanson avec R pour la réactiver.",
    "Une erreur de syntaxe ou d'import au chargement du fichier s'affiche de la même façon avec `load` à la place du nom du hook, et le script n'est pas utilisé.",
    "Modules : `pygame`, `math`, `random`, `json` et `pathlib` sont sûrs, y compris dans la version `.exe` (le moteur les utilise lui-même). Pour tout autre module, rien n'est garanti dans le `.exe` : il n'embarque que ce que le moteur importe. Ne compte pas sur des bibliothèques installées à part.")

# ================================================================== 13
H1("13. Les outils de moddeur")
P("Le menu **TOOLS** contient trois éditeurs : l'éditeur de chart, l'éditeur de scène et caméra, l'éditeur de personnage. Ils permettent de ne presque jamais écrire de JSON à la main.")
IMG("v2_outils.png", "Le menu TOOLS.")
H2("13.1 Où les fichiers sont enregistrés")
BUL("Si le fichier vient d'un **mod en dossier**, il est modifié **sur place**.",
    "Si le fichier vient du **jeu de base** ou d'un mod en **.zip**, une copie est écrite dans le dossier **`Editor Saves/`**, à côté de `mods/`. Ce n'est pas un mod : le jeu le charge toujours, avant tous les mods. Tes changements s'appliquent tout de suite, sans toucher aux originaux ; supprime le fichier de `Editor Saves` pour revenir à l'original.",
    "Chaque enregistrement recharge les mods.")
H2("13.2 L'éditeur de chart")
P("TOOLS > CHART EDITOR, choisis une chanson ; les flèches gauche/droite choisissent la difficulté. L'entrée **+ NEW SONG** crée une nouvelle chanson : le moteur demande le dossier du mod, l'id, le nom et le BPM, écrit les métadonnées et un chart vide (easy, normal, hard), puis, s'il n'y a pas encore d'`Inst.ogg`, ouvre le dossier `songs/<id>/` pour que tu y mettes l'audio ; recharge ensuite avec F5 dans MODS.")
P("La grille a 9 colonnes : **événements**, 4 colonnes **adversaire**, 4 colonnes **joueur**. La ligne rouge est la position de lecture ; une case = une double-croche.")
IMG("v2_chart_editor.png", "L'éditeur de chart.")
TABLE(["Contrôle", "Effet"], [
    ["Clic gauche sur une case vide", "Pose une note (colonnes 1-4 adversaire, 5-8 joueur) ou un événement FocusCamera (colonne 0)."],
    ["Clic gauche sur un élément", "Le sélectionne. Re-cliquer un événement FocusCamera sélectionné change sa cible (0, 1, 2)."],
    ["Glisser vers le bas (bouton enfoncé)", "Allonge la note en sustain : elle va jusqu'au bout de la case sous la souris."],
    ["Ctrl + clic", "Ajoute ou retire un élément de la sélection multiple."],
    ["Ctrl + glisser", "Dessine un rectangle : tout ce qu'il touche est sélectionné."],
    ["Ctrl + A", "Sélectionne tout."],
    ["Clic droit", "Supprime l'élément sous la souris."],
    ["Molette", "Déplace la lecture d'un cran de grille (Maj : 4 crans)."],
    ["Ctrl + molette", "Zoom vertical."],
    ["Espace", "Lecture / arrêt (avec l'audio)."],
    ["Haut / Bas (ou W / S)", "Se déplacer d'un cran de grille (Maj : 4 crans)."],
    ["Page haut / Page bas", "Une mesure (4 temps) en arrière / en avant."],
    ["Début (Home)", "Retour au début de la chanson."],
    ["Gauche / Droite", "Change la grille : 1/4, 1/8, 1/12, 1/16, 1/24, 1/32, 1/48, 1/64 (défaut 1/16)."],
    ["Q / E", "Raccourcit / allonge le sustain de la note sélectionnée d'un cran."],
    ["Suppr / Retour arrière", "Supprime l'élément sélectionné, ou toute la sélection multiple."],
    ["Ctrl + C / X / V", "Copier / couper / coller la sélection. Rien de sélectionné : copie ou coupe la mesure de la ligne rouge. Le collage se fait à la ligne rouge."],
    ["Ctrl + D", "Recopie la sélection de l'autre côté (sans sélection : les notes de l'adversaire de la mesure vont chez le joueur). Maj + Ctrl + D : dans l'autre sens."],
    ["Ctrl + haut / bas", "Déplace la sélection d'un cran de grille (Maj : 4 crans). Ctrl + gauche / droite : change de colonne."],
    ["Ctrl + F", "Miroir : inverse les colonnes de la sélection."],
    ["K", "Saisir le type (`k`) de la note sélectionnée (vide = normal)."],
    ["V (ou double-clic sur un événement)", "Ouvre le **panneau d'événements** (voir 13.6) : tu choisis l'événement dans une liste et tu règles ses champs. L'onglet Texte accepte aussi `nom|valeur JSON`, par exemple `FlashScreen|{\"duration\": 400}`."],
    ["O", "Affiche / cache la forme d'onde des voix de l'adversaire et du joueur."],
    ["L", "**Saisie en direct** (voir sous le tableau)."],
    ["F1", "Ouvre l'aide (13.7)."],
    ["B", "Changer le BPM (20 à 400 ; modifie le premier BPM des métadonnées)."],
    ["N", "Changer la vitesse de défilement de la difficulté (0.5 à 6)."],
    ["Tab", "Difficulté suivante."],
    ["M / H", "Métronome / sons de frappe."],
    ["Ctrl + Z / Ctrl + Y", "Annuler (80 niveaux) / rétablir."],
    ["Ctrl + S", "Enregistrer le chart et les métadonnées."],
    ["Entrée", "**Tester** : enregistre, puis lance la chanson depuis la position de la lecture. À la fin ou en quittant, tu reviens dans l'éditeur."],
    ["Échap", "Vide d'abord une sélection multiple. Sinon : retour ; s'il reste des changements non enregistrés, il faut appuyer deux fois (dans les 2 secondes)."],
    ["Barre de lecture (en bas)", "Clique ou glisse dessus pour aller n'importe où dans la chanson."],
], [4, 8])
P("**Saisie en direct (touche L)** : pendant la lecture, tu joues les notes au clavier et elles se posent sur la grille. Les touches **1 à 8** correspondent aux 8 colonnes, de gauche à droite (1-4 adversaire, 5-8 joueur). L'autre réglage : **WASD** pour l'adversaire et les **flèches** pour le joueur. Une touche **tenue** crée une note longue. Appuie encore sur L pour changer de réglage ou arrêter.")
P("Pour l'écoute : les sons de frappe (H) sont joués à plein volume, l'éditeur a de petits sons d'interface comme celui du jeu officiel, et le métronome (M) fait un son plus grave au début de chaque mesure. La fenêtre **Controls**, à droite, rappelle les touches principales.")
P("Les zones de saisie (K, B, N, nouvelle chanson) : **Entrée** valide, **Échap** annule. Pendant une chanson, la touche **7** ouvre aussi l'éditeur de chart à la position courante (indiqué dans le menu pause).")
H2("13.3 L'éditeur de scène et caméra")
P("TOOLS > STAGE & CAMERA EDITOR, choisis une scène. Les trois personnages de base (bf, dad, gf) sont affichés. Une croix marque le point de caméra de chaque personnage ; pour le personnage sélectionné, un cadre blanc montre ce que la caméra du jeu voit quand elle le suit.")
IMG("v2_editeur_scene_camera.png", "L'éditeur de scène et caméra (cadre blanc = vue de la caméra du jeu).")
TABLE(["Contrôle", "Effet"], [
    ["Glisser (clic gauche)", "Déplace l'élément sélectionné."],
    ["Flèches (Maj : x10)", "Déplace l'élément de 1 pixel (10 avec Maj)."],
    ["Tab / Maj + Tab", "Sélection suivante / précédente : bf, dad, gf, puis chaque prop."],
    ["1 / 2 / 3", "Sélectionner bf / dad / gf."],
    ["C", "Bascule entre le mode **POSITION** et le mode **CAMERA OFFSETS** (le déplacement modifie alors `cameraOffsets` du personnage)."],
    ["Z / X", "Zoom de la caméra du jeu (`cameraZoom`) : moins / plus (pas de 0.05, de 0.2 à 3)."],
    ["Clic droit ou milieu + glisser", "Déplace la vue (panoramique)."],
    ["Molette", "Zoom de la vue de l'éditeur (hors aperçu)."],
    ["P", "Aperçu : affiche la scène comme en jeu, la caméra suivant le personnage sélectionné."],
    ["Ctrl + S (ou F2)", "Enregistre le JSON de la scène."],
    ["Échap", "Retour au menu TOOLS (sans avertissement)."],
], [4, 8])
H2("13.4 L'éditeur de personnage")
P("TOOLS > CHARACTER EDITOR, choisis un personnage. Il est posé sur une grille ; l'image fantôme (« onion skin ») montre la pose de repos pour que tu alignes chaque animation dessus.")
TABLE(["Contrôle", "Effet"], [
    ["W / S", "Animation précédente / suivante (liste à gauche ; seules les animations qui se chargent y figurent)."],
    ["Espace", "Rejouer l'animation."],
    ["Flèches (Maj : x10)", "Déplace le sprite de l'animation : l'`offsets` de l'animation est modifié en conséquence (sens FNF : la valeur diminue quand le sprite part à droite / en bas)."],
    ["C", "Mode **point de caméra** : les flèches modifient `cameraOffsets` du personnage."],
    ["G", "Affiche / cache l'image fantôme de la pose de repos."],
    ["F", "Vue joueur (miroir) / vue adversaire."],
    ["Ctrl + S (ou F2)", "Enregistre le JSON du personnage."],
    ["Échap", "Retour au menu TOOLS."],
], [4, 8])
H2("13.5 Un flux de travail conseillé")
BUL("Crée le mod avec N dans MODS, mets tes images et ta musique.",
    "Crée le personnage (JSON simple avec les préfixes) puis règle ses offsets dans l'éditeur de personnage.",
    "Crée la scène, place les personnages dans l'éditeur de scène.",
    "Pose les notes avec l'éditeur de chart ; teste souvent avec **Entrée**.",
    "Ajoute dialogue, semaine, trophée et scripts.")

# ================================================================== 14
H2("13.6 Ajouter tes événements dans l'éditeur")
P("Le panneau d'événements (touche V) liste les événements du moteur (`FocusCamera`, `ZoomCamera`, `FlashScreen`...) et ceux des mods. Pour que **ton** événement y apparaisse avec ses champs réglables, crée un fichier `data/events/<nom>.json` dans ton mod :")
CODE("""
{
  "name": "Pulse",
  "description": "Petit flash colore sur le rythme.",
  "fields": [
    { "key": "color", "type": "color", "default": [255, 255, 255], "label": "Couleur" },
    { "key": "ms", "type": "int", "default": 300, "label": "Duree (ms)", "step": 50 },
    { "key": "mode", "type": "choice", "choices": ["soft", "hard"], "default": "soft" }
  ]
}
""")
TABLE(["Champ", "Rôle"], [
    ["`name`", "Le nom de l'événement, tel qu'il est écrit dans le chart (`e`). Un nom déjà pris par le moteur est ignoré."],
    ["`description`", "Une phrase affichée dans le panneau."],
    ["`fields`", "La liste des champs. Chacun a une `key` (la clé dans `v`), un `type`, une valeur `default`, un `label` (le texte du panneau) et un `step` (le pas des flèches pour les nombres)."],
    ["`type`", "`number` (décimal), `int` (entier), `text`, `bool` (case à cocher), `choice` (liste : `choices` contient des valeurs, ou des paires `[valeur, \"nom affiché\"]`) ou `color` (une couleur r, g, b)."],
], [2.2, 9.8])
P("L'événement posé dans le chart vaut alors `{\"t\": ms, \"e\": \"Pulse\", \"v\": {\"color\": [255, 255, 255], \"ms\": 300}}`, et c'est ton script qui le lit avec `on_event` (chapitre 12). Un fichier mal écrit est ignoré, sans bloquer le jeu.")
H2("13.7 L'écran AIDE")
P("Si tu bloques, ouvre l'écran **AIDE** : TOOLS > AIDE, la touche **H** dans l'écran MODS, ou **F1** dans l'éditeur de chart. Choisis une catégorie de problème (ma chanson, mon personnage, ma scène, le chart, les scripts, les dialogues...), puis la question qui ressemble à ton cas. Le jeu ouvre alors **ce guide PDF directement à la bonne page**.")
TIP("les numéros de pages sont notés quand le PDF est généré (`mods/guide_pages_fr.json` et `mods/guide_pages_en.json`). Si tu modifies le guide, relance `tools/build_guide_pdf.py` et `tools/build_guide_pdf_en.py`.")

H1("14. Le mod d'exemple, fichier par fichier")
P("`mods/ExampleMod.zip` est construit à partir de `mods_src/ExampleMod/`. Ouvre ces fichiers à côté de ce guide.")
TABLE(["Fichier", "Rôle"], [
    ["`mod.json`", "Nom, description, auteur, version, icône, priorité 0."],
    ["`songs/<id>/Inst.ogg`, `Voices-<perso>.ogg` (+ `-erect`)", "L'audio des trois chansons et de leurs remix Nightmare (voix de Skid & Pump / Lemon Monster : presets du SoundFont FNF ; DJCreeper : son SF2). Fabriqué par `tools/build_example_song.py` avec de vrais samples FL Studio."],
    ["`data/songs/<id>/<id>-metadata.json`, `<id>-metadata-erect.json`", "Nom, personnages, scène, style de notes `halloween`, album, BPM (Pumpkin change de tempo à la mesure 28)."],
    ["`data/songs/<id>/<id>-chart.json`, `<id>-chart-erect.json`", "easy / normal / hard, puis nightmare ; événements FocusCamera et événements perso (Spotlight, Lightning...) ; notes `candy` et `hex`."],
    ["`data/songs/<id>/<id>.py`", "Scripts de chanson : GF qui applaudit ; halo des bougies ; cinématique scriptée de Lemon Monster."],
    ["`scripts/halloween_fx.py`", "Script global : tous les effets façon Dadbattle (chapitre 12.5)."],
    ["`scripts/pumpkin_notes.py`", "Script global : notes `candy` (obligatoire) et `hex` (à éviter), mort immédiate Hard/Nightmare, trophées."],
    ["`scripts/halloween_tuto.py`", "Script global : encarts d'explication des mécaniques (FR/EN)."],
    ["`data/levels/halloween-night.json` + `images/storymenu/titles/halloween-night.png`", "La semaine et l'image de son titre."],
    ["`data/characters/djcreeper.json` + `images/characters/djcreeper.png/.xml`", "DJCreeper jouable (spritesheet de VS DJCreeper), avec miss et animations de mort (écran de game over perso)."],
    ["`images/icons/icon-djcreeper.png`, `icon-djcreeper-night.png`", "Icônes de vie 300 x 150 ; la seconde est mise en place par l'événement `SetHealthIcon` en Nightmare."],
    ["`data/stages/halloween-night.json`, `halloween-night-nightmare.json` + `images/halloween/`", "Les scènes (manoir de la Week 2 + citrouilles), les nuages de fumée."],
    ["`data/notestyles/halloween.json` + `images/halloween/notes.*`, `noteStrumline.*`", "Le style de notes orange."],
    ["`data/dialogue/conversations/<id>.json` et `<id>-fr.json`", "Un dialogue avant chaque chanson (et après la dernière), en anglais et en français."],
    ["`data/dialogue/speakers/*.json`, `boxes/halloween-bubble.json` + `images/dialogue/`", "Les portraits (DJCreeper, Spooky Kids, Lemon Monster) et la bulle."],
    ["`videos/cobweb-cadence.mp4` + `.subs.json`", "La cinématique vidéo et ses sous-titres EN / FR."],
    ["`data/achievements/*.json`", "Cinq trophées bilingues, dont deux cachés."],
    ["`ENGINE_REQUESTS.md`", "Les fonctions que le moteur pourrait offrir pour simplifier ce mod (ignoré du moteur)."],
], [5, 7])
P("Pour construire un mod, le plus rapide est de **copier ce dossier** et de remplacer ses fichiers un par un.")

# ================================================================== 15
H1("15. Partager ton mod")
H2("15.1 Créer le .zip")
BUL("Sélectionne le **contenu** du dossier de ton mod (celui qui contient `mod.json`) et compresse-le en `.zip` : `mod.json` doit se trouver à la racine du zip. Compresser le dossier lui-même fonctionne aussi (un seul niveau de dossier).",
    "Le nom du `.zip` sert d'identifiant au mod : évite d'en changer en cours de route (le réglage « mod désactivé » s'en souvient).",
    "Le joueur n'a qu'à déposer le zip dans `mods/` puis à l'activer dans MODS.")
H2("15.2 Checklist de test")
BUL("Le mod apparaît dans MODS, sans ERROR, avec son icône et sa description.",
    "La chanson est dans Freeplay, avec toutes ses difficultés ; la musique et les voix sont synchronisées.",
    "Aucun texte rouge pendant la chanson (compte à rebours compris) ; `mods/errors.log` est vide.",
    "Les animations de chant, de danse et de miss sont toutes là ; l'icône de vie change bien.",
    "La semaine apparaît dans Story Mode, les dialogues s'enchaînent, la dernière chanson mène aux résultats.",
    "Teste avec la **version zip** (pas seulement le dossier).",
    "Teste avec FLASHING LIGHTS désactivé si tu fais des flashs.",
    "Relis tes scripts : ils ne doivent rien faire d'autre que ce que les joueurs attendent.")
H2("15.3 Dépannage (FAQ)")
TABLE(["Problème", "Cause probable"], [
    ["Ma chanson n'est pas dans Freeplay.", "Il manque `songs/<id>/Inst.ogg` (ou un autre `Inst*.ogg`), le fichier `data/songs/<id>/<id>-metadata.json`, ou le chart ; ou le JSON est invalide ; ou tu n'as pas appuyé sur F5 dans MODS. L'écran MODS affiche en rouge la cause exacte pour ton mod."],
    ["`Character 'xxx' not found` en rouge.", "`data/characters/xxx.json` n'existe pas, ou aucune animation ne trouve son `prefix` dans la spritesheet (mauvais `assetPath`, mauvais nom)."],
    ["`Stage 'xxx' not found`.", "`data/stages/xxx.json` est absent ou son nom ne correspond pas à `playData.stage`."],
    ["`songs/<id>/Inst.ogg not found` et la chanson ne démarre pas.", "Fichier absent ou mal nommé ; ou un autre mod prioritaire contient un dossier `songs/<id>/` incomplet (voir chapitre 4)."],
    ["Le personnage est invisible ou à l'envers.", "`assetPath` faux (le nom est sans extension, relatif à `images/`) ; vérifie `flipX` (inversé pour le joueur)."],
    ["Le personnage glisse ou saute d'une animation à l'autre.", "Offsets à régler dans l'éditeur de personnage."],
    ["Le mod est en ERROR et ne s'active pas.", "`mod.json` manquant (ou pas à la racine du zip), JSON invalide, ou zip corrompu. Le message d'erreur est dans le panneau du menu."],
    ["Mon changement n'apparaît pas.", "Mod en `.zip` : refais le zip. Nouvelle chanson / semaine / trophée : F5 dans MODS. Un autre mod de priorité plus haute fournit peut-être le même fichier."],
    ["Mon script ne fait rien.", "Regarde `mods/errors.log` et le texte rouge. Le nom de fonction doit être exact (`on_note_hit`...). Un script de chanson doit se trouver dans `data/songs/<id>/` avec le bon id."],
    ["Ma cinématique vidéo est sautée.", "Message rouge : format non lisible ou PyAV absent. Le nom doit être `videos/<id>.mp4`."],
    ["Mon dialogue ne s'affiche pas.", "Il ne se lance qu'en Mode Histoire, pas dans Freeplay ni dans le test de l'éditeur."],
    ["Le trophée ne se débloque pas.", "L'id du `unlock_achievement` ne correspond pas au nom du fichier ; ou le test vient de l'éditeur de chart."],
], [4, 8])
P("Bon moddage !")



def save_pages(doc, lang):
    (OUT.parent / f"guide_pages_{lang}.json").write_text(json.dumps(doc.pages, ensure_ascii=False, indent=0), encoding="utf-8")


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = Doc(str(OUT), pagesize=A4, title="Python Engine - Guide de modding", author="Python Engine",
              subject="Guide de modding", leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2.4 * cm, bottomMargin=2.3 * cm)
    doc.multiBuild(story)
    save_pages(doc, "fr")
    print("OK", OUT)


if __name__ == "__main__":
    build()
