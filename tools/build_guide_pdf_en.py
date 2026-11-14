"""Builds mods/Modding Guide - Python Engine.pdf (English version of the guide).

python tools/build_guide_pdf_en.py
Reuses the layout helpers of build_guide_pdf.py (French) and the English text of tools/guide_en_a.py and guide_en_b.py.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = (HERE / "build_guide_pdf.py").read_text(encoding="utf-8")
infra = src[:src.index("\ntitle_page()\n")]
infra = (infra.replace("Guide de modding - Python Engine.pdf", "Modding Guide - Python Engine.pdf")
         .replace("Python Engine - Guide de modding", "Python Engine - Modding Guide")
         .replace("<b>Attention.</b>", "<b>Warning.</b>").replace("<b>Astuce.</b>", "<b>Tip.</b>")
         .replace("ligne de code trop longue", "code line too long"))
ns = {"__name__": "guide_en", "__file__": str(HERE / "build_guide_pdf.py")}
exec(compile(infra, "build_guide_pdf(infra)", "exec"), ns)
S, story, fmt, Paragraph, PageBreak, Spacer = ns["S"], ns["story"], ns["fmt"], ns["Paragraph"], ns["PageBreak"], ns["Spacer"]
ParagraphStyle, TA_CENTER, TableOfContents = ns["ParagraphStyle"], ns["TA_CENTER"], ns["TableOfContents"]


def title_page():
    def centered(name, size, leading, font="Helvetica-Bold", **kw):
        return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading, alignment=TA_CENTER, **kw)
    story.extend([
        Spacer(1, 6.5 * ns["cm"]), Paragraph("Python Engine", centered("t", 40, 46)), Spacer(1, 0.6 * ns["cm"]),
        Paragraph("Modding Guide", centered("t2", 26, 30)), Spacer(1, 1.2 * ns["cm"]),
        Paragraph(fmt("Create songs, weeks, characters, stages, dialogues, trophies and Python scripts "
                      "for a Friday Night Funkin' engine written in Python and pygame."),
                  centered("t3", 13, 18, "Times-Roman", leftIndent=30, rightIndent=30)),
        Spacer(1, 6 * ns["cm"]), Paragraph("Engine version: 2.0", centered("t4", 11, 14, "Times-Italic")),
        PageBreak(), Paragraph("Contents", S["h1"]),
    ])
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("toc0", fontName="Helvetica-Bold", fontSize=10.5, leading=15, spaceBefore=4),
        ParagraphStyle("toc1", fontName="Times-Roman", fontSize=10, leading=12.5, leftIndent=18),
    ]
    story.append(toc)


ns["title_page"] = title_page
title_page()
for part in ("guide_en_a.py", "guide_en_b.py"):
    exec(compile((HERE / part).read_text(encoding="utf-8"), part, "exec"), ns)
doc = ns["Doc"](str(ns["OUT"]), pagesize=ns["A4"], title="Python Engine - Modding Guide", author="Python Engine",
                subject="Modding guide", leftMargin=2.2 * ns["cm"], rightMargin=2.2 * ns["cm"], topMargin=2.4 * ns["cm"], bottomMargin=2.3 * ns["cm"])
doc.multiBuild(story)
import json
(ns["OUT"].parent / "guide_pages_en.json").write_text(json.dumps(doc.pages, ensure_ascii=False, indent=0), encoding="utf-8")
print("OK", ns["OUT"])
