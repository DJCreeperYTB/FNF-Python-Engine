"""Version française des dialogues du jeu de base : data/dialogue/conversations/<id>-fr.json.

Le moteur charge <id>-fr.json quand la langue est le français, sinon <id>.json.
Run: python tools/build_dialogues_fr.py
"""
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent / "fnf_assets" / "data" / "dialogue" / "conversations"

FR = {
    "Not bad for an ugly worm.": "Pas mal, pour un affreux vermisseau.",
    "But this time I'm gonna make you scream...": "Mais cette fois, je vais te faire hurler...",
    "Almost as loud as I'll make your girlfriend scream later tonight, you fat midget.":
        "Presque aussi fort que ta copine hurlera ce soir, espèce de gros nabot.",
    "You disgusting orange boy and your awful way of 'singing'.": "Toi, l'orange répugnant, et ta façon atroce de « chanter ».",
    "You'll ruin the neighborhood acting like that.": "Tu vas ruiner le quartier à te comporter comme ça.",
    "Keep it up and I'll show your girlfriend here a better time tonight than you ever could.":
        "Continue comme ça et ce soir, je ferai passer à ta copine une meilleure soirée que tu ne pourras jamais.",
    "She's not my girlfriend, do whatever you want with her.": "C'est pas ma copine, fais-en ce que tu veux.",
    "I'll enjoy watching you both cry like dogs once I tell the authorities you brought a fake gun to school!":
        "Je vais adorer vous voir pleurer comme des chiens quand je dirai aux autorités que tu as apporté un faux flingue au lycée !",
    "Let's kill this guy.": "On le bute.",
    "Deal.": "Marché conclu.",
    "Keep at it and I'll knock your teeth out right after I knock your ugly girlfriend up.":
        "Continue et je te pète les dents, juste après avoir mis en cloque ta copine dégueulasse.",
    "But this time I'll rip your nuts off right after your girlfriend finishes gargling mine.":
        "Mais cette fois, je vais t'arracher les couilles, juste après que ta copine ait fini de me les gober.",
    "Ah, another lovely fair maiden has graced m-": "Ah, une autre charmante demoiselle m'honore de sa prés-",
    "wait": "attends",
    "Ew.": "Beurk.",
    "Who are you two?": "Vous êtes qui, vous deux ?",
    "I'm Nene.": "Moi, c'est Nene.",
    "He's Pico.": "Lui, c'est Pico.",
    "Hey.": "Salut.",
    "My my, such odd clothing...": "Ma foi, quelle tenue étrange...",
    " How queer...": " Comme c'est bizarre...",
    "Look who's talking.": "C'est l'hôpital qui se fout de la charité.",
    "And bringing a gun to school?": "Et tu amènes une arme au lycée ?",
    " How uncouth!": " Quel rustre !",
    "You've scared away all the lovely roses who enjoy my performances so...":
        "Tu as fait fuir toutes les charmantes roses qui adorent tant mes représentations...",
    "Even if it IS fake, you know that's at least 3 days suspension!":
        "Même si elle EST fausse, tu sais que ça vaut au moins 3 jours d'exclusion !",
    "No that's real it-": "Non, elle est vraie, c'-",
    "I'll enjoy informing the principal, right after I teach you what's stronger than bad manners...":
        "Je préviendrai le proviseur avec plaisir, juste après t'avoir appris ce qui est plus fort que les mauvaises manières...",
    "The beauty of SONG!": "La beauté de la CHANSON !",
    "...": "...",
    "Ah, a new fair maiden has come in search of true love!": "Ah, une nouvelle demoiselle est venue chercher le grand amour !",
    "A serenade between gentlemen shall decide where her beautiful heart shall reside.":
        "Une sérénade entre gentlemen décidera à qui reviendra son joli cœur.",
    "Direct contact with real humans, after being trapped in here for so long...":
        "Un contact direct avec de vrais humains, après être resté enfermé ici si longtemps...",
    " and HER of all people.": " et ELLE, entre toutes.",
    "I'll make her father pay for what he's done to me and all the others...":
        "Je vais faire payer son père pour ce qu'il m'a fait, à moi et à tous les autres...",
    "I'll beat you and make you take my place.": "Je vais te battre et te forcer à prendre ma place.",
    "You don't mind your bodies being borrowed right?": "Ça ne vous dérange pas qu'on vous emprunte vos corps, hein ?",
    " It's only fair...": " C'est de bonne guerre...",
}
# Les « bip bop » de Boyfriend ne se traduisent pas.
KEEP = {"Bop beep be be skdoo bep", "Beep bo bop"}

for path in sorted(FOLDER.glob("*.json")):
    if path.stem.endswith("-fr"):
        continue
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data["dialogue"]:
        missing = [line for line in entry["text"] if line not in FR and line not in KEEP]
        assert not missing, (path.name, missing)
        entry["text"] = [FR.get(line, line) for line in entry["text"]]
    (path.parent / f"{path.stem}-fr.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("ok", path.stem + "-fr")
