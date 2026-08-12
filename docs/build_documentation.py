"""Generate the OpsPortal project documentation as a PDF.

    python build_docs.py <output.pdf>
"""

import sys
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
INK = colors.HexColor("#1a1a1a")
BODY = colors.HexColor("#2b2b2b")
MUTED = colors.HexColor("#6f6a63")
ACCENT = colors.HexColor("#d4a017")
ACCENT_SOFT = colors.HexColor("#fff3d6")
RULE = colors.HexColor("#d8d3ca")
CODE_BG = colors.HexColor("#f6f4f0")
OK = colors.HexColor("#2f7d4f")
WARN = colors.HexColor("#8a6100")
DANGER = colors.HexColor("#9a2f2f")
INFO = colors.HexColor("#1f5c7a")
PANEL = colors.HexColor("#faf8f4")

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

BASE = getSampleStyleSheet()


def style(name, **kw):
    kw.setdefault("parent", BASE["Normal"])
    return ParagraphStyle(name, **kw)


S = {
    "cover_title": style("ct", fontName="Helvetica-Bold", fontSize=32, leading=37,
                         textColor=colors.white),
    "cover_sub": style("cs", fontName="Helvetica", fontSize=13, leading=18,
                       textColor=colors.HexColor("#e8e2d6")),
    "cover_tag": style("ctg", fontName="Helvetica-Bold", fontSize=9.5, leading=13,
                       textColor=ACCENT),
    "h1": style("h1", fontName="Helvetica-Bold", fontSize=19, leading=23,
                textColor=INK, spaceBefore=0, spaceAfter=3),
    "h2": style("h2", fontName="Helvetica-Bold", fontSize=13, leading=17,
                textColor=INK, spaceBefore=13, spaceAfter=5),
    "h3": style("h3", fontName="Helvetica-Bold", fontSize=10.5, leading=14,
                textColor=BODY, spaceBefore=10, spaceAfter=3),
    "body": style("b", fontName="Helvetica", fontSize=9.6, leading=14.2,
                  textColor=BODY, alignment=TA_JUSTIFY, spaceAfter=6),
    "bullet": style("bu", fontName="Helvetica", fontSize=9.6, leading=14,
                    textColor=BODY, leftIndent=11, bulletIndent=2, spaceAfter=3),
    "small": style("sm", fontName="Helvetica", fontSize=8.4, leading=11.5, textColor=MUTED),
    "cell": style("c", fontName="Helvetica", fontSize=8.4, leading=11.4, textColor=BODY),
    "cellb": style("cb", fontName="Helvetica-Bold", fontSize=8.4, leading=11.4, textColor=INK),
    "cellm": style("cm", fontName="Courier", fontSize=8, leading=11, textColor=BODY),
    "th": style("th", fontName="Helvetica-Bold", fontSize=8.4, leading=11.4, textColor=INK),
    "code": style("co", fontName="Courier", fontSize=8.1, leading=11.6, textColor=INK),
    "toc1": style("t1", fontName="Helvetica-Bold", fontSize=10, leading=17, textColor=INK),
    "toc2": style("t2", fontName="Helvetica", fontSize=9.2, leading=14, textColor=MUTED,
                  leftIndent=12),
    "callout": style("ca", fontName="Helvetica", fontSize=9, leading=13, textColor=BODY),
    "callout_t": style("cat", fontName="Helvetica-Bold", fontSize=9, leading=13, textColor=INK),
    "caption": style("cap", fontName="Helvetica-Oblique", fontSize=8.2, leading=11,
                     textColor=MUTED, alignment=TA_CENTER, spaceBefore=4),
}

SECTIONS = []          # (number, title) captured for the running header
_current = {"title": ""}


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------
def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def p(text, s="body"):
    return Paragraph(text, S[s])


def bullets(items, style_name="bullet"):
    return [Paragraph(f"• {i}", S[style_name]) for i in items]


def code(lines, width=CONTENT_W):
    """A shaded monospace block.

    Leading spaces have to become non-breaking: the XML parser behind
    Paragraph collapses ordinary runs of whitespace, which would silently
    flatten the indentation of every code sample.
    """
    if isinstance(lines, str):
        lines = lines.strip("\n").split("\n")

    rendered = []
    for line in lines:
        if not line.strip():
            rendered.append("&nbsp;")
            continue
        indent = len(line) - len(line.lstrip(" "))
        rendered.append("&nbsp;" * indent + esc(line.lstrip(" ")))
    body = "<br/>".join(rendered)
    t = Table([[Paragraph(body, S["code"])]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def callout(title, text, tone="info"):
    tone_colour = {"info": INFO, "ok": OK, "warn": WARN, "danger": DANGER}[tone]
    tone_bg = {"info": colors.HexColor("#eef5fa"), "ok": colors.HexColor("#eef7f1"),
               "warn": ACCENT_SOFT, "danger": colors.HexColor("#fdf0f0")}[tone]
    inner = [Paragraph(title, ParagraphStyle("x", parent=S["callout_t"], textColor=tone_colour))]
    inner.append(Paragraph(text, S["callout"]))
    t = Table([[inner]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), tone_bg),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, tone_colour),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def table(rows, widths, header=True, zebra=True, align_right=()):
    data = []
    for r, row in enumerate(rows):
        cells = []
        for c, cell in enumerate(row):
            if isinstance(cell, Paragraph):
                cells.append(cell)
            else:
                st = "th" if (header and r == 0) else "cell"
                cells.append(Paragraph(str(cell), S[st]))
        data.append(cells)

    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
    ]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), ACCENT_SOFT),
                 ("LINEBELOW", (0, 0), (-1, 0), 1, ACCENT)]
    if zebra:
        start = 1 if header else 0
        cmds.append(("ROWBACKGROUNDS", (0, start), (-1, -1), [colors.white, PANEL]))
    for col in align_right:
        cmds.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    t.setStyle(TableStyle(cmds))
    return t


def h1(number, title):
    SECTIONS.append((number, title))
    bar = Table([[Paragraph(f'<font color="#d4a017">{number}</font>&nbsp;&nbsp;{title}', S["h1"])]],
                colWidths=[CONTENT_W])
    bar.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 1.6, INK),
    ]))
    return [bar, Spacer(1, 9)]


# ---------------------------------------------------------------------------
# Diagrams
# ---------------------------------------------------------------------------
class Diagram(Flowable):
    """Base for the hand-built diagrams."""

    def __init__(self, width, height):
        Flowable.__init__(self)
        self.width, self.height = width, height

    def box(self, x, y, w, h, label, sub=None, fill=colors.white, border=INK,
            text_colour=INK, radius=3, bold=True, size=8.2):
        c = self.canv
        c.setFillColor(fill)
        c.setStrokeColor(border)
        c.setLineWidth(0.9)
        c.roundRect(x, y, w, h, radius, stroke=1, fill=1)
        c.setFillColor(text_colour)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        if sub:
            c.drawCentredString(x + w / 2, y + h / 2 + 2, label)
            c.setFont("Helvetica", size - 1.4)
            c.setFillColor(MUTED)
            c.drawCentredString(x + w / 2, y + h / 2 - 7, sub)
        else:
            c.drawCentredString(x + w / 2, y + h / 2 - 3, label)

    def arrow(self, x1, y1, x2, y2, label=None, dashed=False, colour=INK):
        c = self.canv
        c.setStrokeColor(colour)
        c.setLineWidth(0.9)
        c.setDash(2, 2) if dashed else c.setDash()
        c.line(x1, y1, x2, y2)
        c.setDash()
        # arrow head
        import math
        ang = math.atan2(y2 - y1, x2 - x1)
        size = 4
        c.setFillColor(colour)
        pth = c.beginPath()
        pth.moveTo(x2, y2)
        pth.lineTo(x2 - size * math.cos(ang - 0.4), y2 - size * math.sin(ang - 0.4))
        pth.lineTo(x2 - size * math.cos(ang + 0.4), y2 - size * math.sin(ang + 0.4))
        pth.close()
        c.drawPath(pth, fill=1, stroke=0)
        if label:
            c.setFont("Helvetica", 6.8)
            c.setFillColor(MUTED)
            c.drawCentredString((x1 + x2) / 2, (y1 + y2) / 2 + 3, label)


class ArchitectureDiagram(Diagram):
    def __init__(self):
        Diagram.__init__(self, CONTENT_W, 168)

    def draw(self):
        c = self.canv
        W = self.width
        cx = W / 2

        # browser
        self.box(cx - 45, 148, 90, 18, "Browser", fill=colors.white)

        # nginx container
        c.setStrokeColor(RULE); c.setFillColor(PANEL); c.setLineWidth(0.8)
        c.setDash(3, 2); c.roundRect(cx - 145, 96, 290, 44, 4, stroke=1, fill=1); c.setDash()
        c.setFont("Helvetica-Bold", 6.8); c.setFillColor(MUTED)
        c.drawString(cx - 140, 132, "frontend container  ·  nginx :80")
        self.box(cx - 137, 102, 128, 22, "React SPA", sub="static build", fill=colors.white)
        self.box(cx + 9, 102, 128, 22, "reverse proxy", sub="/api /accounts /admin", fill=colors.white)

        # backend container
        c.setStrokeColor(RULE); c.setFillColor(PANEL)
        c.setDash(3, 2); c.roundRect(cx - 145, 40, 290, 46, 4, stroke=1, fill=1); c.setDash()
        c.setFont("Helvetica-Bold", 6.8); c.setFillColor(MUTED)
        c.drawString(cx - 140, 78, "backend container  ·  gunicorn :8000  ·  Django 5.2 + DRF")
        apps = ["accounts", "crm", "inventory", "sales", "core"]
        bw = 52
        for i, name in enumerate(apps):
            self.box(cx - 138 + i * (bw + 3), 46, bw, 20, name, fill=colors.white, size=7.2)

        # data stores
        self.box(cx - 148, 4, 88, 22, "PostgreSQL 16", sub="business data", fill=colors.white, size=7.6)
        self.box(cx - 44, 4, 88, 22, "Cloudinary", sub="product images", fill=colors.white, size=7.6)
        self.box(cx + 60, 4, 88, 22, "SMTP", sub="Mailpit / Gmail", fill=colors.white, size=7.6)

        self.arrow(cx, 148, cx, 141)
        self.arrow(cx - 73, 102, cx - 73, 88, colour=MUTED)
        self.arrow(cx + 73, 102, cx + 73, 88, colour=MUTED)
        self.arrow(cx - 104, 40, cx - 104, 28, colour=MUTED)
        self.arrow(cx, 40, cx, 28, dashed=True, colour=MUTED)
        self.arrow(cx + 104, 40, cx + 104, 28, dashed=True, colour=MUTED)


class ChallanStateDiagram(Diagram):
    def __init__(self):
        Diagram.__init__(self, CONTENT_W, 132)

    def draw(self):
        W = self.width
        c = self.canv
        y = 86
        bw, bh = 92, 26

        x_draft = 18
        x_conf = W / 2 - bw / 2
        x_canc = W - bw - 18

        self.box(x_draft, y, bw, bh, "DRAFT", fill=colors.HexColor("#eef5fa"), border=INFO,
                 text_colour=INFO)
        self.box(x_conf, y, bw, bh, "CONFIRMED", fill=colors.HexColor("#eef7f1"), border=OK,
                 text_colour=OK)
        self.box(x_canc, y, bw, bh, "CANCELLED", fill=colors.HexColor("#fdf0f0"), border=DANGER,
                 text_colour=DANGER)

        self.arrow(x_draft + bw, y + bh / 2, x_conf, y + bh / 2, "confirm")
        self.arrow(x_conf + bw, y + bh / 2, x_canc, y + bh / 2, "cancel")

        # draft -> cancelled, routed underneath
        c.setStrokeColor(INK); c.setLineWidth(0.9)
        c.line(x_draft + bw / 2, y, x_draft + bw / 2, y - 22)
        c.line(x_draft + bw / 2, y - 22, x_canc + bw / 2, y - 22)
        self.arrow(x_canc + bw / 2, y - 22, x_canc + bw / 2, y - 1)
        c.setFont("Helvetica", 6.8); c.setFillColor(MUTED)
        c.drawCentredString(W / 2, y - 30, "cancel  ·  no stock effect")

        # stock effect notes
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(OK)
        c.drawCentredString((x_draft + bw + x_conf) / 2, y + bh + 8, "stock OUT")
        c.setFillColor(MUTED); c.setFont("Helvetica", 6.4)
        c.drawCentredString((x_draft + bw + x_conf) / 2, y + bh + 1, "reason = SALE")

        c.setFont("Helvetica-Bold", 7); c.setFillColor(DANGER)
        c.drawCentredString((x_conf + bw + x_canc) / 2, y + bh + 8, "stock IN")
        c.setFillColor(MUTED); c.setFont("Helvetica", 6.4)
        c.drawCentredString((x_conf + bw + x_canc) / 2, y + bh + 1, "reason = CHALLAN_CANCELLED")

        # legend
        c.setFillColor(MUTED); c.setFont("Helvetica-Oblique", 7)
        c.drawCentredString(W / 2, 8, "A draft reserves nothing. Confirmed documents are immutable "
                                      "— edit and delete both return HTTP 400.")


# ---------------------------------------------------------------------------
# Page furniture
# ---------------------------------------------------------------------------
def cover_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, PAGE_H - 300, PAGE_W, 300, stroke=0, fill=1)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, PAGE_H - 306, PAGE_W, 6, stroke=0, fill=1)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(PAGE_W / 2, 22,
                             "OpsPortal — Technical Documentation · "
                             f"generated {date.today():%d %B %Y}")
    canvas.restoreState()


def body_page(canvas, doc):
    canvas.saveState()
    # header
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, PAGE_H - MARGIN + 8, PAGE_W - MARGIN, PAGE_H - MARGIN + 8)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, PAGE_H - MARGIN + 12, "OpsPortal — Mini ERP + CRM Operations Portal")
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 12, _current["title"])
    # footer
    canvas.line(MARGIN, MARGIN - 10, PAGE_W - MARGIN, MARGIN - 10)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(MARGIN, MARGIN - 19, "Full Stack Developer Case Study")
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(INK)
    canvas.drawRightString(PAGE_W - MARGIN, MARGIN - 19, str(canvas.getPageNumber()))
    canvas.restoreState()


class SectionMarker(Flowable):
    """Zero-height flowable that updates the running header."""

    def __init__(self, title):
        Flowable.__init__(self)
        self.title = title
        self.width = self.height = 0

    def draw(self):
        _current["title"] = self.title


def build(path):
    doc = BaseDocTemplate(
        path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title="OpsPortal — Technical Documentation",
        author="Kashish Shrivastav",
        subject="Mini ERP + CRM Operations Portal — Full Stack Developer Case Study",
    )
    frame_cover = Frame(0, 0, PAGE_W, PAGE_H, id="cover",
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    frame_body = Frame(MARGIN, MARGIN, CONTENT_W, PAGE_H - 2 * MARGIN, id="body",
                       leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[frame_cover], onPage=cover_page),
        # onPageEnd, not onPage: the running header names the section, and
        # onPage fires before the frame's flowables draw - so the SectionMarker
        # for a section starting on this page would not have run yet and the
        # header would lag one page behind.
        PageTemplate(id="Body", frames=[frame_body], onPageEnd=body_page),
    ])
    doc.build(story())


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------
def story():
    F = []

    # ---------------- cover ----------------
    # The frame fills from the top of the page, and the dark band occupies the
    # top 300pt, so everything below has to be placed inside that budget.
    def band_row(flowable, bottom_pad=0):
        return Table([[flowable]], colWidths=[PAGE_W], style=TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), MARGIN),
            ("RIGHTPADDING", (0, 0), (-1, -1), MARGIN),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), bottom_pad),
        ]))

    F.append(Spacer(1, 118))
    F.append(band_row(Paragraph("FULL STACK DEVELOPER CASE STUDY", S["cover_tag"]), 14))
    F.append(band_row(Paragraph("OpsPortal", S["cover_title"]), 6))
    F.append(band_row(Paragraph("Mini ERP + CRM Operations Portal<br/>"
                                "Technical Documentation", S["cover_sub"])))
    # Clear the remaining dark band before the metadata table.
    F.append(Spacer(1, 96))

    meta = [
        ["Project", "OpsPortal — wholesale & distribution ERP/CRM"],
        ["Backend", "Django 5.2.7 · Django REST Framework 3.16 · PostgreSQL 16"],
        ["Frontend", "React 19 · TypeScript 5.9 · Vite 7"],
        ["Infrastructure", "Docker Compose · nginx · gunicorn · GitHub Actions"],
        ["Test suite", "168 automated tests · 79.6% line coverage"],
        ["API surface", "42 documented paths · 67 operations · OpenAPI 3"],
        ["Author", "Kashish Shrivastav"],
        ["Repository", "github.com/kashish2210/OpsPortal"],
        ["Date", f"{date.today():%d %B %Y}"],
    ]
    t = table([[Paragraph(k, S["cellb"]), Paragraph(v, S["cell"])] for k, v in meta],
              [38 * mm, CONTENT_W - 38 * mm], header=False, zebra=True)
    F.append(Table([[t]], colWidths=[PAGE_W],
                   style=TableStyle([("LEFTPADDING", (0, 0), (-1, -1), MARGIN),
                                     ("RIGHTPADDING", (0, 0), (-1, -1), MARGIN)])))

    F.append(NextPageTemplate("Body"))
    F.append(PageBreak())

    # ---------------- contents ----------------
    F.append(SectionMarker("Contents"))
    F.extend(h1("", "Contents"))
    toc = [
        ("1", "Overview and scope", "What the system does, and what was deliberately left out"),
        ("2", "Technology stack", "Every dependency and why it is there"),
        ("3", "Architecture", "Containers, request routing, and the single-origin decision"),
        ("4", "Data model", "Five apps, eight tables, and the snapshot columns"),
        ("5", "Core modules", "Auth & roles, CRM, inventory, sales challans"),
        ("6", "Business rules", "The stock engine, concurrency safety, and immutability"),
        ("7", "Authentication and authorisation", "Two login surfaces, one session; the role matrix"),
        ("8", "API reference", "Conventions, the error envelope, and every endpoint"),
        ("9", "Bonus features", "PDF export, Cloudinary media, SMTP, CI/CD"),
        ("10", "Testing", "What is covered, and how to run it"),
        ("11", "CI/CD pipeline", "Five jobs, PR reporting, and local runs with act"),
        ("12", "Deployment", "Server setup, environments, and hosting options"),
        ("13", "Configuration reference", "Every environment variable"),
        ("14", "Assumptions", "Decisions taken where the brief was silent"),
        ("15", "Known limitations", "What is not built, and what would come next"),
        ("A", "Command reference", "Everything you need to run and operate the project"),
    ]
    rows = []
    for num, title, sub in toc:
        rows.append([Paragraph(f'<font color="#d4a017">{num}</font>&nbsp;&nbsp;<b>{title}</b>',
                               S["toc1"]),
                     Paragraph(sub, S["toc2"])])
    F.append(table(rows, [62 * mm, CONTENT_W - 62 * mm], header=False, zebra=True))
    F.append(Spacer(1, 14))
    F.append(callout(
        "How to read this document",
        "Sections 1–5 describe what was built. Section 6 is the part worth reading closely — "
        "it covers the stock and challan rules the brief calls out, and the concurrency "
        "guarantees behind them. Sections 10–13 are operational.", "info"))
    F.append(PageBreak())

    # ---------------- 1. overview ----------------
    F.append(SectionMarker("1 · Overview and scope"))
    F.extend(h1("1", "Overview and scope"))
    F.append(p(
        "OpsPortal is a small ERP/CRM system for a wholesale and distribution company. It covers "
        "the day-to-day operations of three internal teams — sales, warehouse and accounts — "
        "across customers, products, stock and outbound deliveries."))
    F.append(p(
        "The brief asked for four core modules. All four are complete, and the emphasis throughout "
        "has been on the business rules rather than on breadth: stock that cannot go negative, "
        "documents that stay immutable once issued, and an audit trail that explains every change."))

    F.append(Paragraph("Delivered", S["h2"]))
    F.append(table([
        ["Module", "Scope", "Status"],
        ["Authentication & roles",
         "Four roles, JWT for the API, Django sessions for the server-rendered pages, "
         "16 auth screens", "Complete"],
        ["Customer CRM",
         "Add / edit / search / detail, dated follow-up notes, lead pipeline", "Complete"],
        ["Products & inventory",
         "Catalogue plus an append-only stock ledger with balances", "Complete"],
        ["Sales challans",
         "Multi-line documents, auto numbering, draft / confirmed / cancelled with "
         "stock deduction", "Complete"],
        ["REST API",
         "Validation, status codes, uniform errors, pagination, search and filtering", "Complete"],
        ["Frontend",
         "React SPA, responsive, light and dark themes", "Complete"],
        ["Bonus",
         "Challan PDF export, Cloudinary media, SMTP, Docker, CI/CD", "Complete"],
    ], [38 * mm, CONTENT_W - 38 * mm - 22 * mm, 22 * mm]))

    F.append(Paragraph("Out of scope", S["h2"]))
    F.append(p(
        "Purchase orders and invoices appear in the brief's scene-setting paragraph but not in its "
        "list of required modules, so they are not built. That was a deliberate reading: the four "
        "named modules were taken to their proper depth instead of adding two more shallow ones."))

    F.append(Paragraph("Scale of the implementation", S["h2"]))
    F.append(table([
        ["Area", "Files", "Lines"],
        ["Backend application code", "58", "6,682"],
        ["Backend tests", "7", "1,875"],
        ["Frontend TypeScript / React", "32", "6,119"],
        ["Django templates (auth screens)", "25", "776"],
        ["Shared stylesheet", "2", "1,804"],
    ], [CONTENT_W - 60 * mm, 30 * mm, 30 * mm], align_right=(1, 2)))
    F.append(Spacer(1, 10))
    F.append(callout(
        "A note on the technology choice",
        "The brief specifies Node.js with TypeScript and Express or NestJS. This implementation "
        "uses <b>Django and Django REST Framework</b> instead, at the reviewer's explicit request, "
        "together with Django's built-in auth for the server-rendered login pages. Every other "
        "requirement is met as written, and the frontend is React with TypeScript, so the "
        "TypeScript requirement holds there.", "warn"))
    F.append(PageBreak())

    # ---------------- 2. stack ----------------
    F.append(SectionMarker("2 · Technology stack"))
    F.extend(h1("2", "Technology stack"))
    F.append(p("Every dependency is pinned. Nothing is included that is not actually used."))

    F.append(Paragraph("Backend", S["h2"]))
    F.append(table([
        ["Package", "Version", "Why"],
        ["Django", "5.2.7 LTS", "ORM, migrations, auth, admin, template engine"],
        ["djangorestframework", "3.16.1", "REST API layer, serializers, viewsets"],
        ["djangorestframework-simplejwt", "5.5.1", "JWT issue / refresh / blacklist"],
        ["psycopg[binary]", "3.2.10", "PostgreSQL driver"],
        ["django-filter", "25.2", "Declarative query-string filtering"],
        ["django-cors-headers", "4.9.0", "CORS for split-origin development"],
        ["django-environ", "0.12.0", "Typed environment configuration"],
        ["drf-spectacular", "0.28.0", "OpenAPI 3 schema, Swagger UI and ReDoc"],
        ["reportlab", "4.4.4", "Challan PDF generation, no system libraries needed"],
        ["cloudinary + storage", "1.44.1 / 0.3.0", "Product image CDN"],
        ["django-storages + boto3", "1.14.6 / 1.40.29", "Alternative S3 / R2 / MinIO backend"],
        ["whitenoise", "6.11.0", "Hashed, compressed static files"],
        ["gunicorn", "23.0.0", "WSGI server"],
        ["pillow", "11.3.0", "Image validation and processing"],
    ], [52 * mm, 27 * mm, CONTENT_W - 79 * mm]))

    F.append(Paragraph("Frontend", S["h2"]))
    F.append(table([
        ["Package", "Version", "Why"],
        ["react / react-dom", "19.1.1", "UI runtime"],
        ["react-router-dom", "7.9.1", "Client-side routing and route guards"],
        ["typescript", "5.9.2", "Strict mode, no implicit any"],
        ["vite", "7.1.5", "Dev server with API proxy, production bundler"],
    ], [52 * mm, 27 * mm, CONTENT_W - 79 * mm]))
    F.append(p(
        "No component library, state manager or data-fetching library is used. The UI is built on a "
        "single hand-written stylesheet and a small set of shared components; server state is "
        "handled by a purpose-built hook with request cancellation. This keeps the bundle at "
        "roughly 99 KB gzipped and the dependency surface small.", "body"))

    F.append(Paragraph("Development and CI", S["h2"]))
    F.append(table([
        ["Tool", "Purpose"],
        ["Docker Compose", "The whole stack in one command"],
        ["coverage.py", "Line and branch coverage, reported on every pull request"],
        ["unittest-xml-reporting", "JUnit XML so CI can annotate failing tests on the diff"],
        ["ruff", "Linting and formatting, enforced in CI"],
        ["Mailpit", "Local SMTP server with a web inbox"],
        ["act", "Runs the GitHub Actions workflows locally"],
    ], [52 * mm, CONTENT_W - 52 * mm]))
    F.append(PageBreak())

    # ---------------- 3. architecture ----------------
    F.append(SectionMarker("3 · Architecture"))
    F.extend(h1("3", "Architecture"))
    F.append(ArchitectureDiagram())
    F.append(Paragraph("Figure 1 — container topology. Solid arrows are always-on; "
                       "dashed arrows are optional integrations.", S["caption"]))
    F.append(Spacer(1, 10))

    F.append(Paragraph("The single-origin decision", S["h2"]))
    F.append(p(
        "nginx fronts both the React bundle and Django. Every request arrives on one origin and is "
        "routed by path, which has three consequences worth stating explicitly."))
    F.extend(bullets([
        "The session cookie Django sets on its login page is also sent to "
        "<font face='Courier' size='8.4'>/api/auth/session-token/</font>. That is what makes the "
        "session-to-JWT handoff possible at all.",
        "CORS and CSRF friction disappears — there is no cross-origin request to configure.",
        "The Vite dev server proxies the same five path prefixes, so development and production "
        "behave identically rather than diverging in ways that only surface after deployment.",
    ]))

    F.append(Paragraph("Request routing", S["h2"]))
    F.append(table([
        ["Path", "Handled by", "Notes"],
        ["/", "React SPA", "History fallback to index.html"],
        ["/assets/*", "nginx, from disk", "Content-hashed, cached for a year"],
        ["/api/*", "Django REST Framework", "JWT bearer authentication"],
        ["/accounts/*", "Django auth views", "Session cookie, server-rendered"],
        ["/admin/*", "Django admin", "Staff only"],
        ["/static/*", "WhiteNoise, via Django", "Hashed filenames"],
        ["/media/*", "nginx, from a shared volume", "Only when media is stored locally"],
    ], [30 * mm, 48 * mm, CONTENT_W - 78 * mm]))
    F.append(Spacer(1, 8))
    F.append(callout(
        "Why /media/ is served by nginx rather than proxied",
        "Django only serves <font face='Courier' size='8.4'>MEDIA_URL</font> when "
        "<font face='Courier' size='8.4'>DEBUG=True</font>. Proxying it would therefore return 404 "
        "in the production image. The media volume is mounted read-only into the nginx container "
        "and served straight from disk. With Cloudinary enabled the URLs point at the CDN and never "
        "reach nginx at all.", "info"))

    F.append(Paragraph("Backend layering", S["h2"]))
    F.append(p(
        "Views are deliberately thin. The rules that must never break live in service modules that "
        "are called from the API, the seed command and the tests alike, so there is exactly one "
        "implementation of each rule."))
    F.append(table([
        ["App", "Responsibility"],
        ["core", "Pagination, role permissions, the error envelope, audit base models, "
                 "gap-free document numbering, dashboard aggregation, demo seeding"],
        ["accounts", "Custom user with a role, JWT endpoints, and the complete "
                     "server-rendered auth screen set"],
        ["crm", "Customer and FollowUp"],
        ["inventory", "Product, StockMovement, and the stock engine"],
        ["sales", "SalesChallan, ChallanItem, the state machine and PDF rendering"],
    ], [26 * mm, CONTENT_W - 26 * mm]))

    F.append(Paragraph("Frontend structure", S["h2"]))
    F.append(code([
        "src/",
        "  api/          fetch client with silent JWT refresh, typed endpoints, API types",
        "  auth/         AuthContext, route guards, client-side role matrix",
        "  components/   layout, shared UI kit, toasts, theme toggle",
        "  hooks/        data fetching with cancellation, debounce",
        "  pages/        one folder per module",
        "  styles/       sketch.css — the shared design system",
    ]))
    F.append(PageBreak())

    # ---------------- 4. data model ----------------
    F.append(SectionMarker("4 · Data model"))
    F.extend(h1("4", "Data model"))
    F.append(p("Eight tables across five apps. Relationships are shown with the deletion "
               "behaviour, because that is where the audit guarantees actually live."))
    F.append(table([
        ["Table", "Key fields", "Notes"],
        ["accounts_user", "username, email (unique), role, is_active",
         "One role per user: ADMIN, SALES, WAREHOUSE or ACCOUNTS"],
        ["crm_customer", "code (CUST-00001), name, mobile (unique), business_name, "
                         "gst_number, customer_type, status, follow_up_date",
         "Never deleted — archived by setting status to INACTIVE"],
        ["crm_followup", "customer, note, channel, next_follow_up_date, created_by",
         "Writing one rolls the customer's next-contact date forward"],
        ["inventory_product", "sku (unique), name, category, unit_price, current_stock, "
                              "min_stock_alert, location, image",
         "current_stock is a running balance maintained only by the ledger"],
        ["inventory_stockmovement", "product, movement_type (IN/OUT), quantity, reason, "
                                    "reference, balance_after, created_by",
         "Append-only. Not editable or deletable, including in Django admin"],
        ["sales_saleschallan", "challan_number (CH-YYYYMM-00001), customer, status, "
                               "customer_* snapshot columns, totals, audit columns",
         "PROTECT on customer, so a customer with challans cannot be removed"],
        ["sales_challanitem", "challan, product, product_* snapshot columns, quantity, "
                              "unit_price, line_total",
         "PROTECT on product"],
        ["core_sequence", "key, last_value", "Locked counter behind document numbering"],
    ], [36 * mm, 60 * mm, CONTENT_W - 96 * mm]))

    F.append(Spacer(1, 10))
    F.append(callout(
        "Why the snapshot columns exist",
        "A challan line copies the product's name, SKU, category, unit and price at the moment it "
        "is saved, and the challan copies the customer's billing details. Renaming or repricing a "
        "product later must never rewrite a document that has already been issued to a customer. "
        "The brief asks for this explicitly, and there is a test that renames and reprices a "
        "product then asserts the challan totals are unchanged.", "ok"))
    F.append(PageBreak())

    # ---------------- 5. modules ----------------
    F.append(SectionMarker("5 · Core modules"))
    F.extend(h1("5", "Core modules"))

    F.append(Paragraph("5.1  Authentication and roles", S["h2"]))
    F.append(p("Four roles matching the teams named in the brief. A single role per user keeps "
               "permission checks cheap and matches how a company of this size actually works."))
    F.append(p("Sixteen server-rendered screens cover the whole account lifecycle: login, signup, "
               "signup-closed, logout confirmation, signed-out, profile, password change and done, "
               "password set, the four-step password reset, e-mail management, e-mail confirmation, "
               "verification sent, verification required, and account inactive."))

    F.append(Paragraph("5.2  Customer CRM", S["h2"]))
    F.append(table([
        ["Field", "Rule"],
        ["Customer name", "Required, at least two characters"],
        ["Mobile number", "Required and unique — it is how field staff look customers up"],
        ["E-mail", "Optional, normalised to lower case"],
        ["Business name", "Optional"],
        ["GST number", "Required for wholesale and distributor; optional for retail. "
                       "Validated against the 15-character GSTIN format"],
        ["Customer type", "Retail, Wholesale or Distributor"],
        ["Address", "Street, city, state and pincode"],
        ["Status", "Lead, Active or Inactive"],
        ["Follow-up date", "Required when creating a lead, so nothing is forgotten"],
        ["Notes", "Free text, plus a separate dated follow-up log"],
    ], [34 * mm, CONTENT_W - 34 * mm]))
    F.append(p("Search covers name, business name, mobile, e-mail, customer code, GSTIN and city in "
               "a single query parameter. Filters exist for status, type, city, GST presence and "
               "follow-up state (due, upcoming or unscheduled).", "body"))

    F.append(Paragraph("5.3  Products and inventory", S["h2"]))
    F.append(p("Products carry the fields the brief lists — name, SKU, category, unit price, "
               "current stock, minimum stock alert and location — plus unit of measure, HSN code "
               "and GST rate, which a distribution business needs in practice."))
    F.append(p("The stock movement log records exactly what the brief asks for: the product, the "
               "quantity changed, whether it was IN or OUT, the reason, who did it and when. It "
               "also stores the resulting balance, so the ledger and the running total can be "
               "reconciled at any point."))

    F.append(Paragraph("5.4  Sales challans", S["h2"]))
    F.append(p("A sales user selects a customer, adds multiple products with quantities, and saves "
               "the challan as a draft or confirms it immediately. Challan numbers are generated "
               "automatically in the form CH-YYYYMM-00001, restarting each month."))
    F.append(ChallanStateDiagram())
    F.append(Paragraph("Figure 2 — challan state machine and the stock movements each "
                       "transition produces.", S["caption"]))
    F.append(Spacer(1, 14))

    # No page break here: the figure tends to wrap onto a fresh page on its own,
    # and forcing a break after it would leave that page almost empty.

    # ---------------- 6. business rules ----------------
    F.append(SectionMarker("6 · Business rules"))
    F.extend(h1("6", "Business rules"))
    F.append(p("This section covers the parts of the brief that are easy to implement naively and "
               "hard to implement correctly."))

    F.append(Paragraph("6.1  Stock can never go negative", S["h2"]))
    F.append(p("Every change to a product's stock goes through one module. It locks the product "
               "rows before reading them, so two sales users confirming challans at the same "
               "instant serialise on the lock instead of both passing the availability check."))
    F.append(code([
        "# inventory/services.py",
        "products = Product.objects.select_for_update()",
        "                  .filter(pk__in=sorted(product_ids))   # sorted → no deadlock",
        "                  .order_by('pk')",
        "",
        "# every short line is collected before raising, not just the first",
        "if shortages:",
        "    raise InsufficientStockError(message, details={'shortages': shortages})",
    ]))
    F.append(p("Products are locked in a deterministic order, which removes the classic deadlock "
               "where two transactions grab the same two rows in opposite orders.", "body"))

    F.append(Paragraph("6.2  All-or-nothing, with every shortage reported", S["h2"]))
    F.append(p("A challan with three lines where two are short does not partially ship. The engine "
               "collects every shortage before raising, so the interface can highlight all the bad "
               "lines at once rather than making the user fix them one at a time."))
    F.append(code([
        "HTTP 400",
        "{",
        '  "success": false,',
        '  "error": {',
        '    "code": "insufficient_stock",',
        '    "message": "Insufficient stock for: SF-GL-CR (need 10, have 0).",',
        '    "details": {',
        '      "shortages": [{',
        '        "product_id": 17, "sku": "SF-GL-CR",',
        '        "product_name": "Cut-resistant Gloves (Pair)",',
        '        "requested": 10, "available": 0, "short_by": 10',
        "      }]",
        "    }",
        "  }",
        "}",
    ]))

    F.append(Paragraph("6.3  Drafts reserve nothing", S["h2"]))
    F.append(p("Stock moves only on confirmation. Creating a challan with "
               "<font face='Courier' size='8.4'>confirm: true</font> is all-or-nothing as well — a "
               "stock failure rolls the challan back too, so a rejected request never leaves an "
               "orphaned draft behind. There is a test asserting the challan count is unchanged "
               "after a failed save-and-confirm."))

    F.append(Paragraph("6.4  Cancelling is compensating, not destructive", S["h2"]))
    F.append(p("Cancelling a confirmed challan writes IN movements with the reason "
               "CHALLAN_CANCELLED and returns the stock. Cancelling a draft touches nothing. The "
               "ledger stays a faithful record of what actually happened rather than being edited "
               "after the fact — which is the whole point of an append-only log."))

    F.append(Paragraph("6.5  Confirmed documents are immutable", S["h2"]))
    F.append(p("Only drafts can be edited or deleted. A confirmed challan must be cancelled and "
               "re-raised. This is enforced in three places — the serializer, the service layer and "
               "Django admin — because a rule enforced in only one of them is a rule that will "
               "eventually be bypassed."))

    F.append(Paragraph("6.6  Document numbers do not collide", S["h2"]))
    F.append(p("<font face='Courier' size='8.4'>MAX(id) + 1</font> breaks the moment two users save "
               "at the same instant. Numbering uses a counter table locked with SELECT … FOR "
               "UPDATE, so concurrent requests serialise on the counter instead of colliding on a "
               "unique index."))

    F.append(Paragraph("6.7  Stock is a ledger, not a field", S["h2"]))
    F.append(p("The product's stock figure is a running balance; the movement log explains every "
               "change to it and stores the balance after each one. A reconciliation helper can "
               "rebuild the balance from the ledger to prove the two agree."))
    F.append(PageBreak())

    # ---------------- 7. auth ----------------
    F.append(SectionMarker("7 · Authentication and authorisation"))
    F.extend(h1("7", "Authentication and authorisation"))
    F.append(p("There are two ways in. They share one user table, one password and one session."))

    F.append(Paragraph("Route A — signing in inside the application", S["h3"]))
    F.append(p("The React login posts to <font face='Courier' size='8.4'>/api/auth/login/</font> and "
               "stores a JWT pair. Access tokens last 60 minutes; the client refreshes them "
               "silently on a 401 and replays the original request. Refresh tokens rotate, and the "
               "previous one is blacklisted on use."))
    F.append(Paragraph("Route B — signing in on the Django page", S["h3"]))
    F.append(p("The server-rendered pages use Django sessions. After signing in, the profile page "
               "offers an <b>Open OpsPortal</b> button that lands on a handoff route, which calls "
               "<font face='Courier' size='8.4'>/api/auth/session-token/</font>. That endpoint "
               "authenticates with the session cookie and returns a JWT pair, so the SPA picks the "
               "session up without a second login."))
    F.append(p("Both routes accept a username or an e-mail address.", "body"))
    F.append(Spacer(1, 6))

    F.append(Paragraph("Role permission matrix", S["h2"]))
    F.append(table([
        ["Module", "Admin", "Sales", "Warehouse", "Accounts"],
        ["Customers and follow-ups", "read + write", "read + write", "read", "read"],
        ["Products", "read + write", "read", "read + write", "read"],
        ["Stock movements", "read + write", "read", "read + write", "read"],
        ["Sales challans", "read + write", "read + write", "read", "read"],
        ["Challan PDF download", "yes", "yes", "yes", "yes"],
        ["Users and roles", "full", "—", "—", "—"],
    ], [52 * mm, 26 * mm, 26 * mm, 30 * mm, 26 * mm]))
    F.append(Spacer(1, 8))
    F.append(p("The matrix is declared once per viewset and mirrored in the frontend purely to "
               "decide what to <i>offer</i>. The server is always the enforcer: a crafted request "
               "still returns 403, and there are tests for each denial.", "body"))
    F.append(Spacer(1, 6))
    F.append(callout(
        "Accounts can download PDFs but cannot edit anything",
        "The accounts team needs the paperwork without the ability to change documents. That is why "
        "the PDF endpoint is readable by every role while every write endpoint is not — a small "
        "detail, but it is the difference between a role model that fits the business and one that "
        "merely looks tidy.", "ok"))

    F.append(Paragraph("Security measures", S["h2"]))
    F.extend(bullets([
        "Passwords hashed with Django's default PBKDF2, and validated against length, "
        "similarity, common-password and numeric-only rules.",
        "Refresh-token rotation with blacklisting, so a stolen refresh token is single-use.",
        "Login throttled to 20 requests a minute; password reset to 10 an hour.",
        "Emailed reset links are built from configuration, not the request's Host header, so a "
        "spoofed or misconfigured proxy header cannot redirect them. Tested explicitly.",
        "ALLOWED_HOSTS rejects unknown hosts before any view runs.",
        "Uploads are validated by Pillow for real image content and restricted by size and format.",
        "Accounts are deactivated rather than deleted, preserving the audit trail.",
        "HSTS, secure cookies and SSL redirect switch on automatically when DEBUG is off.",
    ]))
    F.append(PageBreak())

    # ---------------- 8. API ----------------
    F.append(SectionMarker("8 · API reference"))
    F.extend(h1("8", "API reference"))
    F.append(p("42 documented paths, 67 operations. Interactive documentation is generated from the "
               "code and served at <font face='Courier' size='8.4'>/api/docs/</font>; a Postman "
               "collection with 67 requests ships in the repository."))

    F.append(Paragraph("Conventions", S["h2"]))
    F.append(p("Every list endpoint is paginated with the same envelope:"))
    F.append(code([
        '{ "count": 137, "page": 2, "page_size": 20, "total_pages": 7,',
        '  "next": "…", "previous": "…", "results": [ … ] }',
    ]))
    F.append(p("Every error uses one envelope, so the client parses a single shape:"))
    F.append(code([
        '{ "success": false,',
        '  "error": { "code": "validation_error",',
        '             "message": "Human readable summary",',
        '             "details": { "field": ["reason"] } } }',
    ]))
    F.append(table([
        ["Status", "Meaning"],
        ["200 / 201 / 204", "Success, created, deleted"],
        ["205", "Logged out — refresh token blacklisted"],
        ["400", "Validation failure or business-rule violation"],
        ["401", "Missing or expired token"],
        ["403", "Authenticated, but the role does not permit it"],
        ["404", "Not found"],
        ["429", "Throttled"],
    ], [30 * mm, CONTENT_W - 30 * mm]))

    F.append(Paragraph("Authentication", S["h2"]))
    F.append(table([
        ["Method", "Path", "Purpose"],
        ["POST", "/api/auth/login/", "Username or e-mail and password → JWT pair"],
        ["POST", "/api/auth/refresh/", "Rotate the access token"],
        ["POST", "/api/auth/logout/", "Blacklist the refresh token"],
        ["GET / PATCH", "/api/auth/me/", "Current user; PATCH edits own details, not the role"],
        ["POST", "/api/auth/change-password/", "Change own password"],
        ["POST", "/api/auth/session-token/", "Django session → JWT pair"],
    ], [24 * mm, 52 * mm, CONTENT_W - 76 * mm]))

    F.append(Paragraph("Customers", S["h2"]))
    F.append(table([
        ["Method", "Path", "Purpose"],
        ["GET / POST", "/api/customers/", "List with search and filters; create"],
        ["GET / PATCH / DELETE", "/api/customers/{id}/", "Detail; edit; archive (sets INACTIVE)"],
        ["GET / POST", "/api/customers/{id}/follow-ups/", "Follow-up history; record one"],
        ["GET", "/api/customers/options/", "Slim picker list for the challan builder"],
        ["GET", "/api/customers/stats/", "CRM counters"],
        ["GET", "/api/follow-ups/", "Follow-ups across all customers"],
    ], [34 * mm, 56 * mm, CONTENT_W - 90 * mm]))
    F.append(p("Filters: <font face='Courier' size='8'>q, status, customer_type, city, has_gst, "
               "follow_up=due|upcoming|none, created_after, created_before</font>.", "small"))

    F.append(Paragraph("Products and stock", S["h2"]))
    F.append(table([
        ["Method", "Path", "Purpose"],
        ["GET / POST", "/api/products/", "List; create (opening_stock logs an OPENING movement)"],
        ["GET / PATCH / DELETE", "/api/products/{id}/", "Detail; edit; archive"],
        ["POST / DELETE", "/api/products/{id}/image/", "Upload or remove the product photo"],
        ["GET", "/api/products/{id}/movements/", "Ledger for one product"],
        ["POST", "/api/products/{id}/adjust-stock/", "Stock-take correction to an absolute figure"],
        ["GET", "/api/products/low-stock/", "At or below the alert level"],
        ["GET", "/api/products/categories/  ·  /locations/", "Distinct values for dropdowns"],
        ["GET / POST", "/api/stock-movements/", "The full ledger; record a movement"],
    ], [34 * mm, 56 * mm, CONTENT_W - 90 * mm]))
    F.append(p("Filters: <font face='Courier' size='8'>q, category, location, stock=low|out|in, "
               "is_active, movement_type, reason, reference, created_after, created_before</font>.",
               "small"))

    F.append(Paragraph("Sales challans", S["h2"]))
    F.append(table([
        ["Method", "Path", "Purpose"],
        ["GET / POST", "/api/challans/", "List; create (confirm: true saves and confirms)"],
        ["GET / PATCH / DELETE", "/api/challans/{id}/", "Detail; edit or delete drafts only"],
        ["POST", "/api/challans/{id}/confirm/", "Deduct stock and confirm"],
        ["POST", "/api/challans/{id}/cancel/", "Cancel; restores stock if it was confirmed"],
        ["GET", "/api/challans/{id}/pdf/", "Download the challan as a PDF"],
        ["GET", "/api/challans/{id}/stock-movements/", "Movements this challan produced"],
    ], [34 * mm, 56 * mm, CONTENT_W - 90 * mm]))

    F.append(Paragraph("Administration and utility", S["h2"]))
    F.append(table([
        ["Method", "Path", "Purpose"],
        ["GET / POST / PATCH", "/api/users/", "Employee administration (admin only)"],
        ["POST", "/api/users/{id}/activate/  ·  /deactivate/", "Toggle account access"],
        ["GET", "/api/dashboard/", "All KPI counters and recent activity in one call"],
        ["GET", "/api/health/", "Liveness probe, public, checks the database"],
        ["GET", "/api/schema/  ·  /docs/  ·  /redoc/", "OpenAPI 3 schema and interactive docs"],
    ], [34 * mm, 56 * mm, CONTENT_W - 90 * mm]))
    F.append(PageBreak())

    # ---------------- 9. bonus ----------------
    F.append(SectionMarker("9 · Bonus features"))
    F.extend(h1("9", "Bonus features"))
    F.append(p("All four bonus items in the brief are implemented, plus a real SMTP server for "
               "local development."))

    F.append(Paragraph("9.1  Challan PDF export", S["h2"]))
    F.append(p("A proper A4 delivery-challan document rendered with ReportLab — chosen over an "
               "HTML-to-PDF converter so the production image needs no cairo or pango system "
               "libraries and stays slim."))
    F.extend(bullets([
        "Renders from the stored snapshot columns, so a reprint months later reproduces the "
        "document exactly as it was issued.",
        "Indian digit grouping (12,34,567.50) and rupees in words, both of which Indian delivery "
        "documents require.",
        "Drafts and cancelled challans are watermarked diagonally so a draft cannot be mistaken "
        "for a live document.",
        "Company details, GSTIN and address come from configuration.",
        "Available to every role, including read-only Accounts.",
    ]))

    F.append(Paragraph("9.2  Product images on a CDN", S["h2"]))
    F.append(p("Media storage is selected by a single environment variable with three options, and "
               "switching between them requires no code change because everything is written "
               "through Django's storage API."))
    F.append(table([
        ["MEDIA_STORAGE", "Backend", "Notes"],
        ["local", "Filesystem volume", "Default. Zero setup, works offline"],
        ["cloudinary", "Cloudinary CDN", "25 GB free, image transformations, currently active"],
        ["s3", "S3-compatible", "AWS S3, Cloudflare R2, Backblaze B2 or MinIO"],
    ], [30 * mm, 38 * mm, CONTENT_W - 68 * mm]))
    F.append(p("Uploads are validated for real image content, restricted to JPEG, PNG and WebP "
               "under 5 MB, namespaced by SKU, and given a unique key so replacing an image never "
               "collides with a cached copy. Replacing or deleting an image removes the previous "
               "object rather than orphaning it.", "body"))

    F.append(Paragraph("9.3  SMTP", S["h2"]))
    F.append(p("Docker Compose runs Mailpit, a real SMTP server with a searchable web inbox on port "
               "8025. Password-reset and verification e-mails can be walked through end to end "
               "without a mail provider and without anything leaving the machine. Switching to "
               "Brevo, SendGrid, SES or Gmail is an environment change; ready-made blocks for each "
               "are in the example file."))

    F.append(Paragraph("9.4  Docker", S["h2"]))
    F.append(p("One command builds both images, starts PostgreSQL, waits for it to become healthy, "
               "runs migrations, collects static files, seeds demo data and starts gunicorn. The "
               "backend image runs as a non-root user; the frontend is a two-stage build whose "
               "runtime layer contains no Node and no source."))

    F.append(Paragraph("9.5  GitHub Actions", S["h2"]))
    F.append(p("Covered in section 11."))
    F.append(PageBreak())

    # ---------------- 10. testing ----------------
    F.append(SectionMarker("10 · Testing"))
    F.extend(h1("10", "Testing"))
    F.append(p("168 automated tests at 79.6% line coverage. The suite is weighted towards the rules "
               "that would cause real damage if they broke, rather than spread evenly for the sake "
               "of a coverage number."))
    F.append(table([
        ["Area", "Tests", "What is covered"],
        ["Stock engine", "13", "IN/OUT, never-negative, bulk all-or-nothing, duplicate-line "
                               "merging, archived products, stock-take, ledger rebuild"],
        ["Challan workflow", "40", "State machine, stock deduction and restoration, "
                                   "immutability, snapshots, numbering, role enforcement"],
        ["PDF export", "16", "Valid output in all three states, snapshot fidelity, "
                             "money formatting, amount in words, endpoint behaviour"],
        ["Product images", "18", "Upload, replace, delete, validation, role enforcement, "
                                 "storage-backend selection"],
        ["CRM", "26", "Validation rules, GST requirement, search, filters, follow-ups"],
        ["Accounts and auth", "45", "JWT lifecycle, session handoff, role matrix, "
                                    "every rendered auth page"],
        ["Emailed links", "10", "Correct origin, port preservation, host-header spoofing"],
    ], [34 * mm, 18 * mm, CONTENT_W - 52 * mm], align_right=(1,)))

    F.append(Paragraph("Running the tests", S["h2"]))
    F.append(code([
        "# in Docker",
        "docker compose exec backend python manage.py test",
        "",
        "# locally",
        "cd backend && python manage.py test",
        "",
        "# one module, or one test",
        "python manage.py test sales",
        "python manage.py test sales.tests.ChallanServiceTests.test_confirm_reduces_stock",
        "",
        "# with coverage",
        "coverage run manage.py test && coverage report && coverage html",
        "",
        "# frontend type safety",
        "cd frontend && npm run typecheck",
    ]))
    F.append(Spacer(1, 8))
    F.append(callout(
        "Tests do not touch live services",
        "The image-upload tests force local filesystem storage even when the developer's environment "
        "is configured for Cloudinary, so running the suite never uploads to a real account. "
        "E-mail uses Django's in-memory backend.", "ok"))
    F.append(PageBreak())

    # ---------------- 11. CI/CD ----------------
    F.append(SectionMarker("11 · CI/CD pipeline"))
    F.extend(h1("11", "CI/CD pipeline"))
    F.append(p("Continuous integration runs on every push and pull request. Five jobs, four of them "
               "in parallel."))
    F.append(table([
        ["Job", "What it does", "Blocking"],
        ["lint", "ruff check and ruff format --check across the backend", "Yes"],
        ["backend-tests", "168 tests against a real PostgreSQL 16 service, with coverage and "
                          "JUnit XML; also asserts there are no missing migrations and that the "
                          "demo seed still works", "Yes"],
        ["frontend-build", "TypeScript typecheck and a production Vite build", "Yes"],
        ["docker-build", "Builds both images so a broken Dockerfile fails CI", "Yes"],
        ["report", "Publishes results back onto the pull request", "No"],
    ], [30 * mm, CONTENT_W - 30 * mm - 20 * mm, 20 * mm]))

    F.append(Paragraph("Pull-request reporting", S["h2"]))
    F.append(p("Two free actions, both authenticated with the token GitHub injects automatically — "
               "no third-party bot to install and no account to create."))
    F.extend(bullets([
        "<b>publish-unit-test-result-action</b> — a check run with pass, fail and skip counts, "
        "and every failing test annotated inline on the diff.",
        "<b>sticky-pull-request-comment</b> — one comment carrying the overall status and coverage "
        "percentage, edited in place on each push rather than piling up.",
    ]))
    F.append(Spacer(1, 4))
    F.append(callout(
        "The report job only runs on pull requests",
        "It is gated on the event type, because a PR comment has nowhere to go on a plain push. A "
        "push shows the same information on the workflow summary page instead.", "info"))

    F.append(Paragraph("Running the workflows locally", S["h2"]))
    F.append(p("The workflows are written to run under act. Steps that need the GitHub API — "
               "artifact upload and the PR comments — are skipped automatically when act is "
               "detected, so a local run exercises the real build and test steps without failing on "
               "calls it cannot make."))
    F.append(code([
        "cp .github/act.secrets.example .secrets   # required: .actrc points at it",
        "",
        "act pull_request                # the whole CI workflow",
        "act -j backend-tests            # one job",
        "act -l                          # list what would run",
    ]))

    F.append(Paragraph("Continuous deployment", S["h2"]))
    F.append(p("Pushing to the main branch, or tagging a release, builds both images and publishes "
               "them to the GitHub Container Registry, then optionally calls a deploy hook and "
               "smoke-tests the health endpoint until the new revision responds. The deploy step "
               "skips cleanly when no hook is configured, so the workflow is not a permanent "
               "failure on a repository that is not yet deployed."))
    F.append(PageBreak())

    # ---------------- 12. deployment ----------------
    F.append(SectionMarker("12 · Deployment"))
    F.extend(h1("12", "Deployment"))

    F.append(Paragraph("How the server is set up", S["h2"]))
    F.append(p("The backend image is built on python:3.13-slim. It installs the pinned "
               "requirements, copies the project, creates a non-root user and exposes port 8000. "
               "The entrypoint runs on every start and:"))
    F.extend(bullets([
        "waits for PostgreSQL, retrying for up to a minute, so a cold start has no ordering race;",
        "applies migrations;",
        "collects static files into a named volume;",
        "seeds demo data when enabled — the command is idempotent, so restarts are safe;",
        "hands over to gunicorn with three workers and two threads each.",
    ]))
    F.append(p("The health endpoint backs the container healthcheck, and the frontend waits for the "
               "backend to report healthy, so nginx never starts in front of a dead upstream.",
               "body"))

    F.append(Paragraph("Local", S["h2"]))
    F.append(code([
        "docker compose up --build",
        "",
        "#   http://localhost:8080            the React application",
        "#   http://localhost:8080/accounts/  Django auth pages",
        "#   http://localhost:8080/admin/     Django admin",
        "#   http://localhost:8080/api/docs/  Swagger UI",
        "#   http://localhost:8025            Mailpit inbox",
    ]))

    F.append(Paragraph("Hosting", S["h2"]))
    F.append(table([
        ["Component", "Options", "Notes"],
        ["Database", "Neon, Supabase, Render PostgreSQL", "Set DATABASE_URL"],
        ["Backend", "Render, Railway, Fly.io", "Deploy the backend Dockerfile"],
        ["Frontend", "Vercel, Netlify, Render Static", "Build command npm run build, output dist"],
        ["Media", "Cloudinary", "Already configured"],
        ["E-mail", "Brevo, SendGrid, SES", "Free tiers available"],
    ], [26 * mm, 52 * mm, CONTENT_W - 78 * mm]))
    F.append(Spacer(1, 8))
    F.append(callout(
        "Prefer deploying the stack as one unit",
        "On split origins the JWT login works fine, but the session-to-JWT handoff needs a cookie "
        "that survives cross-site, which means SameSite=None and Secure over HTTPS. Deploying the "
        "Compose stack as a single unit keeps the single origin and everything behaves exactly as "
        "it does locally.", "warn"))

    F.append(Paragraph("Production checklist", S["h2"]))
    F.extend(bullets([
        "Generate a fresh SECRET_KEY and a strong database password.",
        "Set DEBUG=False and SECURE_SSL_REDIRECT=True.",
        "Set ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS and FRONTEND_URL to the real domain — "
        "FRONTEND_URL in particular, because emailed links are built from it.",
        "Point EMAIL_BACKEND at a real SMTP provider.",
        "Set SEED_DEMO_DATA=False once real data exists.",
        "Run <font face='Courier' size='8.4'>manage.py check --deploy</font>.",
    ]))
    F.append(PageBreak())

    # ---------------- 13. config ----------------
    F.append(SectionMarker("13 · Configuration reference"))
    F.extend(h1("13", "Configuration reference"))
    F.append(p("Nothing environment-specific is hard-coded. Every value is read through typed "
               "environment variables with safe defaults, so the same image runs unchanged in "
               "development, Docker and production."))
    F.append(table([
        ["Variable", "Default", "Purpose"],
        ["DEBUG", "False", "Never enable in production"],
        ["SECRET_KEY", "placeholder", "Must be replaced when deploying"],
        ["ALLOWED_HOSTS", "localhost, backend, frontend", "Comma separated"],
        ["CSRF_TRUSTED_ORIGINS", "localhost:8080", "Required for the Django forms"],
        ["DATABASE_URL", "empty → SQLite", "Compose builds it from the POSTGRES_* values"],
        ["FRONTEND_URL", "localhost:8080", "Origin used to build emailed links"],
        ["ACCESS_TOKEN_LIFETIME_MINUTES", "60", "JWT access lifetime"],
        ["REFRESH_TOKEN_LIFETIME_DAYS", "7", "Rotated and blacklisted on use"],
        ["SIGNUP_OPEN", "True", "False shows the sign-up-closed page"],
        ["REQUIRE_EMAIL_VERIFICATION", "False", "True gates login behind confirmation"],
        ["EMAIL_BACKEND / EMAIL_HOST", "SMTP → Mailpit", "Console backend outside Docker"],
        ["MEDIA_STORAGE", "local", "local, cloudinary or s3"],
        ["CLOUDINARY_*", "empty", "Cloud name, API key and secret"],
        ["COMPANY_*", "sample values", "Printed on the challan PDF"],
        ["SEED_DEMO_DATA", "True", "Entrypoint runs the demo seed"],
        ["SECURE_SSL_REDIRECT", "False", "Enable behind HTTPS"],
    ], [50 * mm, 32 * mm, CONTENT_W - 82 * mm]))
    F.append(Spacer(1, 8))
    F.append(p("Four example files ship with the repository and are safe to commit: the Compose "
               "environment, the backend environment, the frontend build variables and the act "
               "secrets. The real files they are copied to are all git-ignored. A dedicated "
               "environment guide documents where to obtain each credential.", "body"))
    F.append(PageBreak())

    # ---------------- 14. assumptions ----------------
    F.append(SectionMarker("14 · Assumptions"))
    F.extend(h1("14", "Assumptions"))
    F.append(p("Decisions taken where the brief was silent. Each is reversible, and the reasoning "
               "matters more than the choice."))
    items = [
        ("Django instead of Node", "Requested explicitly by the reviewer."),
        ("One role per user",
         "A company of this size has staff sitting in one team. Multiple roles would need a "
         "many-to-many and a permission union."),
        ("Mobile number is unique per customer",
         "It is the field staff actually search by, and duplicate CRM records for one number are "
         "the classic data-quality problem. Relax the constraint if a shared office line must be "
         "allowed."),
        ("GST is mandatory for wholesale and distributor customers",
         "Those two invoice against a GSTIN; retail customers frequently do not have one."),
        ("New leads require a follow-up date",
         "A lead with no next action gets forgotten, which is the failure mode a CRM exists to "
         "prevent."),
        ("Self-service signup creates an active Sales user",
         "An administrator changes the role afterwards. Set SIGNUP_OPEN=False for an invite-only "
         "deployment."),
        ("Nothing is hard-deleted",
         "Customers become Inactive, products Archived, users Deactivated — challans and the stock "
         "ledger reference them for audit. Only draft challans can truly be deleted."),
        ("Cancelling a confirmed challan returns the stock in full",
         "Partial returns would need a separate sales-return document."),
        ("Prices exclude GST, computed per line from the product's rate",
         "No CGST/SGST/IGST split, which needs place-of-supply logic."),
        ("Line prices may be overridden on a challan",
         "Negotiated rates are normal in wholesale; the snapshot then keeps the agreed price."),
        ("Currency is INR and the timezone Asia/Kolkata", "Both configurable."),
        ("E-mail verification is off by default",
         "So the demo has no friction. Enable it and point at a real SMTP provider for production."),
    ]
    F.append(table([[Paragraph(f"<b>{i+1}. {t}</b><br/>{d}", S["cell"])]
                    for i, (t, d) in enumerate(items)],
                   [CONTENT_W], header=False))
    F.append(PageBreak())

    # ---------------- 15. limitations ----------------
    F.append(SectionMarker("15 · Known limitations"))
    F.extend(h1("15", "Known limitations"))
    F.append(p("Stated plainly, because a case study that claims no weaknesses is not credible."))
    F.append(table([
        ["Limitation", "Impact and what would fix it"],
        ["No live deployment URL",
         "The submission is the Docker stack plus documentation. Section 12 documents exactly how "
         "to deploy it."],
        ["No frontend unit tests",
         "TypeScript in strict mode and 168 backend tests carry the correctness load. Component "
         "tests with Vitest and Testing Library would be the next addition."],
        ["Dashboard aggregates computed per request",
         "Fine at this data volume; a large dataset would want caching or materialised counters."],
        ["Search is ILIKE-based",
         "Good to a few hundred thousand rows. Beyond that, PostgreSQL full-text search or a "
         "trigram index."],
        ["No CSV import or export",
         "A natural next step for both customers and products, and commonly expected in this "
         "domain."],
        ["No field-level audit history",
         "Rows carry created_by, updated_by and timestamps, but not a full change log. "
         "django-simple-history would provide it."],
        ["Single-warehouse semantics",
         "Location is a label on the product, not a separate balance per warehouse. Real "
         "multi-warehouse stock needs a per-location quantity table."],
        ["Session-to-JWT handoff assumes one origin",
         "Cross-site cookies would need SameSite=None and Secure. See section 12."],
        ["Rate limiting only on login and password reset",
         "Broader throttling would be sensible before exposing the API publicly."],
        ["Purchase orders and invoices not built",
         "Deliberate — outside the four required modules. Stock IN movements already model goods "
         "receipt, so purchase orders would layer on top cleanly."],
    ], [46 * mm, CONTENT_W - 46 * mm]))
    F.append(PageBreak())

    # ---------------- appendix ----------------
    F.append(SectionMarker("Appendix A · Command reference"))
    F.extend(h1("A", "Command reference"))

    F.append(Paragraph("Running the stack", S["h2"]))
    F.append(code([
        "docker compose up --build      # build and start everything",
        "docker compose down            # stop, keeping the database",
        "docker compose down -v         # stop and delete the database volume",
        "docker compose logs -f backend # tail the backend logs",
        "",
        "./run.sh                       # wrapper: WSL / Linux / macOS / Git Bash",
        ".\\run.ps1                      # wrapper: Windows PowerShell",
        "make up                        # wrapper: make",
    ]))

    F.append(Paragraph("Database and demo data", S["h2"]))
    F.append(code([
        "docker compose exec backend python manage.py migrate",
        "docker compose exec backend python manage.py makemigrations",
        "docker compose exec backend python manage.py seed_demo",
        "docker compose exec backend python manage.py seed_demo --reset",
        "docker compose exec backend python manage.py createsuperuser",
        "docker compose exec db psql -U opsportal -d opsportal",
    ]))

    F.append(Paragraph("Tests and quality", S["h2"]))
    F.append(code([
        "docker compose exec backend python manage.py test",
        "cd backend && coverage run manage.py test && coverage report",
        "cd backend && ruff check . && ruff format --check .",
        "cd frontend && npm run typecheck && npm run build",
        "docker compose exec backend python manage.py check --deploy",
    ]))

    F.append(Paragraph("Local development without Docker", S["h2"]))
    F.append(code([
        "conda create -n opsportal python=3.12 -y && conda activate opsportal",
        "cd backend && pip install -r requirements-dev.txt",
        "python manage.py migrate && python manage.py seed_demo",
        "python manage.py runserver 0.0.0.0:8000",
        "",
        "cd frontend && npm install && npm run dev      # http://localhost:5173",
    ]))

    F.append(Paragraph("Test logins", S["h2"]))
    F.append(table([
        ["Role", "Username", "Password"],
        ["Admin", "admin", "Admin@12345"],
        ["Sales", "sales", "Sales@12345"],
        ["Warehouse", "warehouse", "Warehouse@12345"],
        ["Accounts", "accounts", "Accounts@12345"],
    ], [40 * mm, 50 * mm, CONTENT_W - 90 * mm]))
    F.append(Spacer(1, 10))
    F.append(callout(
        "Repository documentation",
        "README.md — setup and overview  ·  docs/ARCHITECTURE.md — Mermaid diagrams  ·  "
        "docs/ENVIRONMENT.md — every environment variable and where to obtain it  ·  "
        "docs/OpsPortal.postman_collection.json — 67 API requests with assertions.", "info"))

    return F


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "OpsPortal-Documentation.pdf"
    build(out)
    import os
    print(f"wrote {out} ({os.path.getsize(out):,} bytes)")
