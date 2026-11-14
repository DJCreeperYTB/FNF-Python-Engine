"""Sous-titres des cinématiques : videos/<nom>.subs.json = {"en": [[début, fin, texte]...], "fr": [...]}.

L'anglais vient des sous-titres intégrés aux .mkv officiels (ou d'une transcription pour les .mp4) ;
le français est traduit ici. Run: python tools/build_video_subs.py
"""
import json
import re
from pathlib import Path

VIDEOS = Path(__file__).resolve().parent.parent / "fnf_assets" / "videos"

FR = {
    # ughCutscene
    "Well, well, well, whadda we got here?": "Tiens, tiens, tiens, qu'est-ce qu'on a là ?",
    "Beep!": "Bip !",
    "We should just KILL you, but...": "On devrait juste te BUTER, mais...",
    "...what the hell, it's been a boring day.": "...et puis zut, la journée a été chiante.",
    "Let's see what you got!": "Voyons ce que t'as dans le ventre !",
    # gunsCutscene
    "Heheh, pretty tight bars": "Héhé, pas mal ces rimes",
    "for a little dude who's": "pour un petit gars qui",
    "SIMPING over an...": "BAVE devant une...",
    "UGLY, BORING little TEENAGER": "petite ADO MOCHE et CHIANTE",
    "that wears her mom's clothes!": "qui porte les fringues de sa mère !",
    "Hah!": "Ha !",
    "He he he...": "Hé hé hé...",
    # stressCutscene
    "God effing damn it.": "Bordel de saloperie de merde.",
    "Well played, you little SHIT.": "Bien joué, petite MERDE.",
    "But this is WAR.": "Mais c'est la GUERRE.",
    "...and in war, people DIE.": "...et à la guerre, les gens MEURENT.",
    "Men, get ready to FIRE!": "Les gars, prêts à TIRER !",
    "Sorry, no prom for you this year!": "Désolé, pas de bal de promo pour toi cette année !",
    "Ha ha ha!": "Ha ha ha !",
    "Ah, look who it is...": "Ah, regardez qui voilà...",
    "...your sexually ambiguous, angry little friend.": "...ton petit pote énervé à la sexualité ambiguë.",
    "Don't you have a school to shoot up?": "T'as pas une école à aller mitrailler ?",
    "There's one way to settle this...": "Il n'y a qu'une façon de régler ça...",
    "Let's rock, you little CUNT!": "On y va, petit CONNARD !",
    "Let's rock, you little ****!": "On y va, petit **** !",
    "laughs": "rit",
    "You little cunts!": "Bande de petits connards !",
    "You little ****s!": "Bande de petits **** !",
    # stressPicoCutscene
    "Back for some tasty revenge, huh?": "De retour pour une petite vengeance, hein ?",
    "Oh, that's cute.": "Oh, c'est mignon.",
    "Boys... Light 'em up.": "Les gars... Allumez-les.",
    "*SCREAMS*": "*HURLEMENTS*",
    "*LAUGHS*": "*RIRES*",
    "*Music slows to a stop*": "*La musique ralentit jusqu'à s'arrêter*",
    "Oh, come on, who the FUCK is this knockoff?": "Oh, sérieux, c'est QUI ce putain de sosie raté ?",
    "Oh, come on, who the **** is this knockoff?": "Oh, sérieux, c'est QUI ce **** de sosie raté ?",
    "Alright, alright.": "D'accord, d'accord.",
}


def embedded(path: Path) -> list[list]:
    import av
    container = av.open(str(path))
    streams = [stream for stream in container.streams if stream.type == "subtitle"]
    lines = []
    if streams:
        stream = streams[0]
        for packet in container.demux(stream):
            if packet.pts is None:
                continue
            raw = bytes(packet).decode("utf-8", "replace").split(",", 8)[-1]
            text = re.sub(r"\{[^}]*\}", "", raw).replace("\\N", " ").strip()
            if text:
                start = float(packet.pts * stream.time_base)
                lines.append([round(start, 2), round(start + float((packet.duration or 0) * stream.time_base), 2), text])
    container.close()
    return lines


def main() -> None:
    transcripts = VIDEOS / "transcripts.json"  # transcriptions des .mp4 sans sous-titres (facultatif)
    extra = json.loads(transcripts.read_text(encoding="utf-8")) if transcripts.is_file() else {}
    for path in sorted(VIDEOS.iterdir()):
        if path.suffix not in (".mkv", ".mp4"):
            continue
        english = embedded(path) if path.suffix == ".mkv" else extra.get(path.name, [])
        if not english:
            continue
        missing = [text for _, _, text in english if text not in FR]
        if missing:
            print("traduction manquante", path.name, missing)
            continue
        french = [[start, end, FR[text]] for start, end, text in english]
        (VIDEOS / f"{path.stem}.subs.json").write_text(json.dumps({"en": english, "fr": french}, indent=1, ensure_ascii=False), encoding="utf-8")
        print("ok", path.stem, len(english))


if __name__ == "__main__":
    main()
