"""Renders a markdown document as a PDF.

    python3 docs/build_pdf.py                 # the business proposal
    python3 docs/build_pdf.py README.md       # or any other document

Generated from the markdown rather than laid out by hand, so a corrected figure
reaches the PDF by re-running this instead of by someone remembering to.
"""
import html
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
DOCS = {
    "docs/proposal.md": ("ControlPlane_Business_Proposal.pdf",
                         "ControlPlane · Business Proposal · Team Nexus, IIT Jodhpur"),
    "README.md":        ("ControlPlane_README.pdf",
                         "ControlPlane · Repository guide · Team Nexus, IIT Jodhpur"),
}

INK = colors.HexColor("#16202B")
BODY = colors.HexColor("#333F4B")
MUTED = colors.HexColor("#5C6B7A")
FAINT = colors.HexColor("#8A97A3")
ACCENT = colors.HexColor("#0E7C86")
RULE = colors.HexColor("#DCE2E8")
BAND = colors.HexColor("#EEF2F5")
SOFT = colors.HexColor("#E4F1F2")

MARGIN, TOP, BOT = 22 * mm, 20 * mm, 18 * mm

S = {
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=21, leading=25,
                         textColor=INK, spaceBefore=0, spaceAfter=5),
    "lede": ParagraphStyle("lede", fontName="Helvetica", fontSize=10, leading=15,
                           textColor=MUTED, spaceAfter=14),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13.5, leading=17,
                         textColor=INK, spaceBefore=17, spaceAfter=7),
    "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10.5, leading=14,
                         textColor=ACCENT, spaceBefore=11, spaceAfter=4),
    "p": ParagraphStyle("p", fontName="Helvetica", fontSize=9.5, leading=14.2,
                        textColor=BODY, alignment=TA_LEFT, spaceAfter=7),
    "li": ParagraphStyle("li", fontName="Helvetica", fontSize=9.5, leading=14.2,
                         textColor=BODY, leftIndent=11, bulletIndent=2, spaceAfter=5),
    "quote": ParagraphStyle("quote", fontName="Helvetica-Oblique", fontSize=9.5,
                            leading=14, textColor=MUTED, leftIndent=10,
                            borderPadding=0, spaceBefore=4, spaceAfter=9),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.2, leading=11.4,
                           textColor=BODY),
    "cellb": ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=8.2,
                            leading=11.4, textColor=INK),
    "th": ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=7.2, leading=10,
                         textColor=MUTED),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=8.2, leading=12,
                           textColor=BODY, backColor=BAND, borderPadding=6,
                           spaceBefore=3, spaceAfter=9),
}


def inline(s):
    """Bold, code, links and the handful of entities the sources actually use."""
    s = html.escape(s)
    # links first: their label may itself contain code or bold
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
               lambda m: f'<link href="{m.group(2)}" color="#0E7C86">{m.group(1)}</link>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r'<font color="#16202B"><b>\1</b></font>', s)
    s = re.sub(r"`(.+?)`", r'<font face="Courier" size="8.5">\1</font>', s)
    for a, b in (("—", "&#8212;"), ("×", "&#215;"), ("→", "&#8594;"),
                 ("·", "&#183;"), ("–", "&#8211;")):
        s = s.replace(a, b)
    return s


def build_table(rows, width):
    head, body = rows[0], rows[1:]
    n = len(head)
    # first column carries the label and gets the room; the rest share evenly
    first = width * (0.34 if n > 2 else 0.5)
    rest = (width - first) / max(n - 1, 1)
    widths = [first] + [rest] * (n - 1)

    data = [[Paragraph(inline(c), S["th"]) for c in head]]
    emphasis = []
    for i, row in enumerate(body, start=1):
        strong = any("**" in c for c in row)
        if strong:
            emphasis.append(i)
        data.append([Paragraph(inline(c), S["cellb"] if strong else S["cell"]) for c in row])

    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BAND),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#C3CDD6")),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
    ]
    for r in emphasis:
        style.append(("BACKGROUND", (0, r), (-1, r), SOFT))
    t.setStyle(TableStyle(style))
    return t


def parse(md, width):
    """Markdown wraps a paragraph across lines; inline markup does not respect
    that. Bold opened on one line and closed on the next left literal asterisks
    in the output, so lines are joined into their paragraph before any inline
    rule runs."""
    flow, rows, code, para = [], [], [], []

    def flush_table():
        nonlocal rows
        if rows:
            flow.append(Spacer(1, 3))
            flow.append(build_table(rows, width))
            flow.append(Spacer(1, 9))
            rows = []

    def flush_code():
        nonlocal code
        if code:
            body = "<br/>".join(html.escape(l).replace(" ", "&nbsp;") for l in code)
            flow.append(Paragraph(body, S["code"]))
            code = []

    def flush_para():
        nonlocal para
        if para:
            text = " ".join(para)
            style = "lede" if text.startswith("**Accenture") else "p"
            if text.startswith("- "):
                flow.append(Paragraph(inline(text[2:]), S["li"], bulletText="\u2022"))
            elif text.startswith("*") and text.endswith("*") and "**" not in text:
                flow.append(Paragraph(inline(text.strip("*")), S["quote"]))
            else:
                flow.append(Paragraph(inline(text), S[style]))
            para = []

    in_code = False
    for line in md.splitlines():
        s = line.rstrip()

        if s.strip().startswith("```"):
            in_code = not in_code
            if not in_code:
                flush_code()
            continue
        if in_code:
            code.append(s)
            continue

        if s.strip().startswith("|"):
            flush_para()
            cells = [c.strip() for c in s.strip().strip("|").split("|")]
            if not set("".join(cells)) <= set("-: "):
                rows.append(cells)
            continue
        flush_table()

        t = s.strip()
        if not t:
            flush_para()
            continue
        if t == "---":
            flush_para()
            flow.append(Spacer(1, 4))
            flow.append(HRFlowable(width="100%", thickness=0.5, color=RULE,
                                   spaceBefore=2, spaceAfter=9))
        elif t.startswith("### "):
            flush_para()
            flow.append(Paragraph(inline(t[4:]), S["h3"]))
        elif t.startswith("## "):
            flush_para()
            flow.append(Paragraph(inline(t[3:]), S["h2"]))
        elif t.startswith("# "):
            flush_para()
            flow.append(Paragraph(inline(t[2:]), S["h1"]))
        elif t.startswith("- "):
            flush_para()          # a new bullet ends the previous block
            para.append(t)
        else:
            para.append(t)
    flush_para()
    flush_table()
    flush_code()
    return flow


def furniture(canvas, doc, heading=""):
    canvas.saveState()
    w, h = A4
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, h - TOP + 7 * mm, w - MARGIN, h - TOP + 7 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(FAINT)
    canvas.drawString(MARGIN, h - TOP + 9 * mm, heading)
    canvas.drawRightString(w - MARGIN, h - TOP + 9 * mm,
                           "Accenture Innovation Challenge 2026 · Round 2")
    canvas.line(MARGIN, BOT + 4 * mm, w - MARGIN, BOT + 4 * mm)
    canvas.drawString(MARGIN, BOT - 1 * mm,
                      "github.com/m25csa003-glitch/controlplane")
    canvas.drawRightString(w - MARGIN, BOT - 1 * mm, str(doc.page))
    canvas.restoreState()


def main(rel="docs/proposal.md"):
    if rel not in DOCS:
        sys.exit(f"no PDF recipe for {rel!r}; known: {', '.join(DOCS)}")
    src = ROOT / rel
    if not src.exists():
        sys.exit(f"missing {src}")
    out_name, heading = DOCS[rel]
    out = ROOT / "docs" / out_name
    w, h = A4
    width = w - 2 * MARGIN
    doc = BaseDocTemplate(str(out), pagesize=A4,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=TOP, bottomMargin=BOT,
                          title=heading.split(" · ")[1],
                          author="Team Nexus, IIT Jodhpur",
                          subject="Accenture Innovation Challenge 2026, Round 2")
    frame = Frame(MARGIN, BOT, width, h - TOP - BOT, id="body",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(
        id="main", frames=[frame],
        onPage=lambda c, d: furniture(c, d, heading))])
    doc.build(parse(src.read_text(), width))
    return out


if __name__ == "__main__":
    out = main(sys.argv[1] if len(sys.argv) > 1 else "docs/proposal.md")
    print(f"wrote {out.relative_to(ROOT)}  ({out.stat().st_size // 1024} KB)")
