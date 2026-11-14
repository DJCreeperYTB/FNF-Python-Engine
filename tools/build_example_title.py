"""Titre du menu histoire (images/storymenu/titles/halloween-night.png) dans le style des titres de semaine officiels
(week6.png : lettres epaisses, contour blanc, interieur transparent), construit avec les lettres de images/fonts/bold.png :
on prend le remplissage blanc de chaque lettre, on l'epaissit, puis on ne garde que le contour blanc."""
import os, re
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, 'fnf_assets', 'images', 'fonts')
atlas = Image.open(os.path.join(FONT, 'bold.png')).convert('RGBA')
frames = {m[0]: tuple(int(v) for v in m[1:]) for m in re.findall(r'name="([^"]+0000)" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', open(os.path.join(FONT, 'bold.xml'), encoding='utf-8-sig').read())}
SS, GAP = 4, 22     # supersampling, espace entre lettres (px a 4x)


def glyph_mask(ch):
    x, y, w, h = frames[ch + '0000']
    a = np.asarray(atlas.crop((x, y, x + w, y + h))).astype(np.int32)
    fill = (a[..., 3] > 128) & (a[..., :3].min(-1) > 190)
    ys, xs = np.nonzero(fill)
    return fill[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def disk(r):
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return xx * xx + yy * yy <= r * r


def title(text, height=84, ring=3.2):
    letters = []
    for ch in text:
        if ch == ' ':
            letters.append(None); continue
        m = glyph_mask(ch)
        m = np.array(Image.fromarray(m.astype(np.uint8) * 255).resize((round(m.shape[1] * SS * 1.5), round(m.shape[0] * SS * 1.5)), Image.LANCZOS)) > 127
        m = ndi.binary_dilation(m, disk(round(SS * 1.5)))                       # lettres plus grasses
        letters.append(m)
    cap = max(m.shape[0] for m in letters if m is not None)
    pad = round(SS * (ring + 1))
    width = sum((m.shape[1] if m is not None else SS * 22) + GAP for m in letters) + 2 * pad
    canvas = np.zeros((cap + 2 * pad, width), bool)
    x = pad
    for m in letters:
        if m is None:
            x += SS * 22 + GAP; continue
        y = pad + (cap - m.shape[0]) // 2
        canvas[y:y + m.shape[0], x:x + m.shape[1]] |= m
        x += m.shape[1] + GAP
    r = round(SS * ring)
    outer = ndi.binary_dilation(canvas, disk(r))
    inner = ndi.binary_erosion(canvas, disk(r))
    band = outer & ~inner
    img = Image.fromarray(band.astype(np.uint8) * 255)
    scale = height / img.height
    img = img.resize((round(img.width * scale), height), Image.LANCZOS)
    out = Image.new('RGBA', img.size, (255, 255, 255, 0))
    out.putalpha(img)
    return out


if __name__ == '__main__':
    out = title('HALLOWEEN NIGHT')
    out.save(os.path.join(ROOT, 'mods_src', 'ExampleMod', 'images', 'storymenu', 'titles', 'halloween-night.png'))
    ref = Image.open(os.path.join(ROOT, 'fnf_assets', 'images', 'storymenu', 'titles', 'week6.png')).convert('RGBA')
    sheet = Image.new('RGBA', (max(out.width, ref.width) + 20, out.height + ref.height + 30), (60, 60, 200, 255))
    sheet.alpha_composite(ref, (10, 10)); sheet.alpha_composite(out, (10, ref.height + 20))
    sheet.save(os.path.join(ROOT, 'Leaks', 'v2_mod_titre_semaine.png'))
    print(out.size)
