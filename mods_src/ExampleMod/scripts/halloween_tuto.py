"""Script GLOBAL du mod : encarts d'explication (FR/EN selon la langue du jeu) montres UNE fois par session, avant la
première chanson où elles apparaissent : note obligatoire (bonbon orange) et note à éviter (violette).
Entrée ou Espace : page suivante, puis le countdown démarre. Jamais en botplay ni hors des chansons du mod."""
import pygame

SONGS = {"cobweb-cadence", "midnight-candlewick", "pumpkin-moon-panic"}
W, H = 1280, 720
CANDY, HEX = (255, 150, 30), (170, 60, 255)
PAGES = {
    "notes": {
        "title": {"fr": "NOTES SPECIALES", "en": "SPECIAL NOTES"},
        "rows": [
            (CANDY, "good", {"fr": "NOTE OBLIGATOIRE (orange) : TOUCHE-LA", "en": "MANDATORY NOTE (orange): HIT IT"},
             {"fr": "C'est une vraie note chantée. La rater = mort immédiate en Hard et Nightmare (en Easy et Normal : un raté et un peu de vie en moins).",
              "en": "It is a real sung note. Missing it = instant death in Hard and Nightmare (in Easy and Normal: a miss and a little health lost)."}),
            (HEX, "avoid", {"fr": "NOTE À ÉVITER (violette) : NE LA TOUCHE PAS", "en": "NOTE TO AVOID (purple): DO NOT HIT IT"},
             {"fr": "Laisse-la passer. La toucher = mort immédiate en Hard et Nightmare. S'ajoute aux notes chantées : "
                    "dans les silences, entre deux notes ou à côté d'une vraie note.",
              "en": "Let it go by. Hitting it = instant death in Hard and Nightmare. It is added on top of the sung notes: "
                    "in the silences, between two notes or right next to a real note."})]},
}
st = {}


def mine(game):
    return game.song.song_id in SONGS


def on_create(game):
    if not mine(game):
        return
    st.clear()
    if game.botplay or game.start_ms:
        return
    kinds = {n.kind for n in game.notes if n.player}
    topics = ["notes"] if kinds & {"candy", "hex"} else []
    seen = getattr(game.app, "halloween_seen", set())
    topics = [t for t in topics if t not in seen]
    if topics:
        game.hold_countdown = True
        st.update(pages=topics, i=0, prev=None)


NEXT = (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER)


def on_key_down(game, event):
    """Entrée / Espace tournent la page de l'encart ; renvoyer True garde la touche (sinon Entrée mettrait le jeu en pause)."""
    if not mine(game) or not st.get("pages") or game.overlays or event.key not in NEXT:
        return False
    st["i"] += 1
    if st["i"] >= len(st["pages"]):
        seen = getattr(game.app, "halloween_seen", set())
        seen.update(st["pages"])
        game.app.halloween_seen = seen
        st["pages"] = []
        game.start_countdown()
    return True


def _arrow(screen, cx, cy, color, size=84, angle=0):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    k = size / 100
    pts = [(x * k, y * k) for x, y in ((50, 6), (94, 52), (68, 52), (68, 94), (32, 94), (32, 52), (6, 52))]
    pygame.draw.polygon(s, (0, 0, 0), pts, 0)
    inner = [(50 * k + (x - 50 * k) * .8, 50 * k + (y - 50 * k) * .8) for x, y in pts]
    pygame.draw.polygon(s, color, inner, 0)
    s = pygame.transform.rotate(s, angle)
    screen.blit(s, s.get_rect(center=(cx, cy)))


def _icon(screen, kind, cx, cy, color):
    if kind in ("good", "avoid"):
        _arrow(screen, cx, cy, color)
        if kind == "avoid":
            pygame.draw.circle(screen, (235, 30, 40), (cx, cy), 52, 7)
            pygame.draw.line(screen, (235, 30, 40), (cx - 37, cy - 37), (cx + 37, cy + 37), 7)
    elif kind == "mirror":
        _arrow(screen, cx - 36, cy, (255, 255, 255), 56, 90)
        _arrow(screen, cx + 36, cy, (170, 220, 255), 56, -90)
    else:
        pygame.draw.circle(screen, (0, 0, 0), (cx, cy), 46)
        pygame.draw.circle(screen, color, (cx, cy), 38)
        pygame.draw.polygon(screen, (0, 0, 0), [(cx - 20, cy - 8), (cx, cy + 22), (cx + 20, cy - 8)])


def _wrap(font, text, width):
    rows, cur = [], ""
    for word in text.split():
        test = f"{cur} {word}".strip()
        if cur and font.size(test)[0] > width:
            rows.append(cur)
            cur = word
        else:
            cur = test
    return rows + [cur]


def on_draw(game, screen):
    if not mine(game) or not st.get("pages") or game.overlays:
        return
    lang = "fr" if game.app.settings.language == "fr" else "en"
    page = PAGES[st["pages"][st["i"]]]
    veil = pygame.Surface((W, H), pygame.SRCALPHA)
    veil.fill((6, 4, 14, 225))
    screen.blit(veil, (0, 0))
    title = game.app.alphabet(page["title"][lang], 74)
    screen.blit(title, title.get_rect(center=(W // 2, 110)))
    y = 210
    head, body = game.app.font(34, True), game.app.font(26, False)
    for color, kind, name, text in page["rows"]:
        _icon(screen, kind, 150, y + 60, color)
        screen.blit(head.render(name[lang], True, (255, 255, 255)), (240, y))
        for i, line in enumerate(_wrap(body, text[lang], 880)):
            screen.blit(body.render(line, True, (225, 220, 235)), (240, y + 48 + 32 * i))
        y += 190
    n, total = st["i"] + 1, len(st["pages"])
    prompt = {"fr": "ENTRÉE : continuer", "en": "ENTER: continue"}[lang] + (f"   ({n}/{total})" if total > 1 else "")
    img = body.render(prompt, True, (255, 200, 120))
    screen.blit(img, img.get_rect(center=(W // 2, H - 50)))
