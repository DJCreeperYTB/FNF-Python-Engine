"""Icone du mod : citrouille eclairee (jack-o'-lantern) Minecraft, vraie texture 16x16 de 1.19.2 agrandie x9 sans lissage (net)."""
import io, os, zipfile
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
z = zipfile.ZipFile(os.path.expanduser(r'~\AppData\Roaming\.minecraft\versions\1.19.2\1.19.2.jar'))
tex = Image.open(io.BytesIO(z.read('assets/minecraft/textures/block/jack_o_lantern.png'))).convert('RGBA')
icon = Image.new('RGBA', (150, 150), (0, 0, 0, 0))
icon.paste(tex.resize((144, 144), Image.NEAREST), (3, 3))
icon.save(os.path.join(ROOT, 'mods_src', 'ExampleMod', 'icon.png'))
big = icon.resize((300, 300), Image.NEAREST)
bg = Image.new('RGBA', (300, 300), (22, 18, 34, 255)); bg.paste(big, (0, 0), big)
bg.save(os.path.join(ROOT, 'Leaks', 'v2_mod_icone.png'))
