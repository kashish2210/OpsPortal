"""PDF rendering for sales challans (bonus: "export invoice as PDF").

Uses ReportLab's platypus flowables rather than a HTML-to-PDF converter, so the
production image needs no cairo/pango system libraries - it stays a slim,
pure-Python dependency.

The document deliberately renders the *snapshot* columns stored on the challan,
not the live product/customer records, so a re-print months later reproduces the
document exactly as it was issued.
"""

from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import ChallanStatus

# -- palette ---------------------------------------------------------------
INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#6f6a63")
ACCENT = colors.HexColor("#ffd54f")
PAPER = colors.HexColor("#fdfbf7")
RULE = colors.HexColor("#c9c4bb")

STATUS_COLOURS = {
    ChallanStatus.DRAFT: colors.HexColor("#1f5c7a"),
    ChallanStatus.CONFIRMED: colors.HexColor("#2f7d4f"),
    ChallanStatus.CANCELLED: colors.HexColor("#9a2f2f"),
}


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=20, leading=24, textColor=INK, alignment=0, spaceAfter=0,
        ),
        "company": ParagraphStyle(
            "company", parent=base["Normal"], fontSize=8.5, leading=12, textColor=MUTED,
        ),
        "doc_label": ParagraphStyle(
            "doc_label", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=14, leading=17, textColor=INK, alignment=TA_RIGHT,
        ),
        "doc_meta": ParagraphStyle(
            "doc_meta", parent=base["Normal"], fontSize=9, leading=13,
            textColor=MUTED, alignment=TA_RIGHT,
        ),
        "h": ParagraphStyle(
            "h", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=9, leading=12, textColor=MUTED,
        ),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=9.5, leading=13, textColor=INK),
        "small": ParagraphStyle("small", parent=base["Normal"], fontSize=8, leading=11, textColor=MUTED),
        "cell": ParagraphStyle("cell", parent=base["Normal"], fontSize=8.5, leading=11, textColor=INK),
        "cell_b": ParagraphStyle(
            "cell_b", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=8.5, leading=11, textColor=INK,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"], fontSize=7.5, leading=10,
            textColor=MUTED, alignment=TA_CENTER,
        ),
    }


def _money(value):
    """Indian-format a Decimal: 1234567.5 -> '12,34,567.50'."""
    amount = Decimal(value or 0).quantize(Decimal("0.01"))
    sign = "-" if amount < 0 else ""
    whole, _, frac = f"{abs(amount):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"{sign}{whole}.{frac}"


def _amount_in_words(amount):
    """Rupees in words - required on Indian delivery/tax documents."""
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def under_hundred(n):
        if n < 20:
            return ones[n]
        return (tens[n // 10] + (" " + ones[n % 10] if n % 10 else "")).strip()

    def under_thousand(n):
        if n < 100:
            return under_hundred(n)
        rest = n % 100
        return (ones[n // 100] + " Hundred" + (" " + under_hundred(rest) if rest else "")).strip()

    amount = Decimal(amount or 0).quantize(Decimal("0.01"))
    rupees = int(amount)
    paise = int((amount - rupees) * 100)

    if rupees == 0:
        words = "Zero"
    else:
        chunks = [(10_000_000, "Crore"), (100_000, "Lakh"), (1_000, "Thousand")]
        parts = []
        remaining = rupees
        for divisor, label in chunks:
            if remaining >= divisor:
                parts.append(f"{under_thousand(remaining // divisor)} {label}")
                remaining %= divisor
        if remaining:
            parts.append(under_thousand(remaining))
        words = " ".join(parts)

    text = f"Rupees {words}"
    if paise:
        text += f" and {under_hundred(paise)} Paise"
    return text + " only"


def _header(challan, styles):
    company = (
        f"<b>{settings.COMPANY_NAME}</b><br/>"
        f"{settings.COMPANY_ADDRESS}<br/>"
        f"GSTIN: {settings.COMPANY_GSTIN} &nbsp;|&nbsp; {settings.COMPANY_PHONE}<br/>"
        f"{settings.COMPANY_EMAIL}"
    )
    # hexval() -> '0x2f7d4f'; ReportLab's <font color> wants '#2f7d4f'.
    status_colour = f"#{STATUS_COLOURS.get(challan.status, INK).hexval()[2:]}"
    meta = (
        f"<b>No.</b> {challan.challan_number}<br/>"
        f"<b>Date</b> {challan.challan_date:%d %b %Y}<br/>"
        f'<b>Status</b> <font color="{status_colour}">'
        f"{challan.get_status_display().upper()}</font>"
    )

    table = Table(
        [[Paragraph(company, styles["company"]),
          [Paragraph("DELIVERY CHALLAN", styles["doc_label"]),
           Spacer(1, 4),
           Paragraph(meta, styles["doc_meta"])]]],
        colWidths=[105 * mm, 65 * mm],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 1.2, INK),
    ]))
    return table


def _parties(challan, styles):
    billed = [f"<b>{challan.customer_name or '-'}</b>"]
    if challan.customer_business_name:
        billed.append(challan.customer_business_name)
    if challan.customer_address:
        billed.append(challan.customer_address)
    if challan.customer_mobile:
        billed.append(f"Mobile: {challan.customer_mobile}")
    if challan.customer_gst_number:
        billed.append(f"GSTIN: {challan.customer_gst_number}")

    dispatch = []
    dispatch.append(challan.delivery_address or "Same as the billing address")
    if challan.vehicle_number:
        dispatch.append(f"Vehicle: {challan.vehicle_number}")
    dispatch.append(f"Raised by: {challan.created_by.display_name if challan.created_by else '-'}")
    if challan.confirmed_at:
        dispatch.append(
            f"Confirmed: {timezone.localtime(challan.confirmed_at):%d %b %Y %H:%M} "
            f"by {challan.confirmed_by.display_name if challan.confirmed_by else '-'}"
        )

    table = Table(
        [[Paragraph("BILL / SHIP TO", styles["h"]), Paragraph("DISPATCH DETAILS", styles["h"])],
         [Paragraph("<br/>".join(billed), styles["body"]),
          Paragraph("<br/>".join(dispatch), styles["body"])]],
        colWidths=[85 * mm, 85 * mm],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("LEFTPADDING", (1, 0), (1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEAFTER", (0, 0), (0, -1), 0.5, RULE),
    ]))
    return table


def _lines(challan, styles):
    header = ["#", "SKU", "Product", "Qty", "Rate", "Amount", "GST", "Total"]
    rows = [[Paragraph(f"<b>{h}</b>", styles["cell"]) for h in header]]

    for index, item in enumerate(challan.items.all(), start=1):
        rows.append([
            Paragraph(str(index), styles["cell"]),
            Paragraph(item.product_sku, styles["cell"]),
            Paragraph(
                f"{item.product_name}"
                + (f"<br/><font size=7 color='#6f6a63'>{item.product_category}</font>"
                   if item.product_category else ""),
                styles["cell"],
            ),
            Paragraph(f"{item.quantity} {item.product_unit}", styles["cell"]),
            Paragraph(_money(item.unit_price), styles["cell"]),
            Paragraph(_money(item.line_total), styles["cell"]),
            Paragraph(f"{item.tax_rate:g}%<br/>{_money(item.line_tax)}", styles["cell"]),
            Paragraph(_money(item.line_total + item.line_tax), styles["cell_b"]),
        ])

    table = Table(
        rows,
        colWidths=[8 * mm, 26 * mm, 54 * mm, 17 * mm, 19 * mm, 20 * mm, 16 * mm, 20 * mm],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("LINEBELOW", (0, 0), (-1, 0), 1, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
        ("BOX", (0, 0), (-1, -1), 0.8, INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
    ]))
    return table


def _totals(challan, styles):
    rows = [
        ["Total quantity", f"{challan.total_quantity}"],
        ["Taxable value", _money(challan.total_amount)],
        ["GST", _money(challan.total_tax)],
        ["Grand total", _money(challan.grand_total)],
    ]
    table = Table(
        [[Paragraph(label, styles["cell"] if i < 3 else styles["cell_b"]),
          Paragraph(value, styles["cell"] if i < 3 else styles["cell_b"])]
         for i, (label, value) in enumerate(rows)],
        colWidths=[35 * mm, 30 * mm],
        hAlign="RIGHT",
    )
    table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, 3), (-1, 3), 0.8, INK),
        ("BACKGROUND", (0, 3), (-1, 3), ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
    ]))
    return table


def _signatures(styles):
    table = Table(
        [[Paragraph("Receiver's signature", styles["small"]),
          Paragraph(f"For {settings.COMPANY_NAME}", styles["small"])]],
        colWidths=[85 * mm, 85 * mm],
        rowHeights=[20 * mm],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LINEABOVE", (0, 0), (0, 0), 0.5, INK),
        ("LINEABOVE", (1, 0), (1, 0), 0.5, INK),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    return table


def _page_furniture(canvas, doc, challan):
    """Watermark drafts/cancellations and stamp the page footer."""
    canvas.saveState()

    if challan.status != ChallanStatus.CONFIRMED:
        canvas.setFont("Helvetica-Bold", 68)
        canvas.setFillColor(STATUS_COLOURS.get(challan.status, MUTED))
        canvas.setFillAlpha(0.12)
        canvas.translate(A4[0] / 2, A4[1] / 2)
        canvas.rotate(38)
        canvas.drawCentredString(0, 0, challan.get_status_display().upper())
        canvas.rotate(-38)
        canvas.translate(-A4[0] / 2, -A4[1] / 2)
        canvas.setFillAlpha(1)

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        20 * mm, 12 * mm,
        f"{challan.challan_number} · generated {timezone.localtime():%d %b %Y %H:%M}",
    )
    canvas.drawRightString(190 * mm, 12 * mm, f"Page {canvas.getPageNumber()}")
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.4)
    canvas.line(20 * mm, 15 * mm, 190 * mm, 15 * mm)
    canvas.restoreState()


def render_challan_pdf(challan):
    """Return the challan as PDF bytes."""
    styles = _styles()
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=16 * mm,
        bottomMargin=20 * mm,
        title=f"Challan {challan.challan_number}",
        author=settings.COMPANY_NAME,
        subject=f"Delivery challan for {challan.customer_name}",
    )

    story = [
        _header(challan, styles),
        Spacer(1, 8),
        _parties(challan, styles),
        Spacer(1, 10),
        _lines(challan, styles),
        Spacer(1, 8),
        _totals(challan, styles),
        Spacer(1, 6),
        Paragraph(
            f"<b>Amount in words:</b> {_amount_in_words(challan.grand_total)}", styles["small"]
        ),
    ]

    if challan.notes:
        story += [Spacer(1, 8), Paragraph(f"<b>Notes:</b> {challan.notes}", styles["small"])]

    if challan.status == ChallanStatus.CANCELLED:
        reason = challan.cancellation_reason or "No reason recorded"
        story += [
            Spacer(1, 6),
            Paragraph(
                f"<b>Cancelled</b> on "
                f"{timezone.localtime(challan.cancelled_at):%d %b %Y %H:%M} - {reason}"
                if challan.cancelled_at
                else f"<b>Cancelled</b> - {reason}",
                styles["small"],
            ),
        ]

    story += [
        Spacer(1, 14),
        KeepTogether([
            Paragraph(
                "Goods once dispatched are covered by the terms agreed with the customer. "
                "Please check the quantities before signing.",
                styles["footer"],
            ),
            Spacer(1, 10),
            _signatures(styles),
        ]),
    ]

    doc.build(
        story,
        onFirstPage=lambda c, d: _page_furniture(c, d, challan),
        onLaterPages=lambda c, d: _page_furniture(c, d, challan),
    )

    buffer.seek(0)
    return buffer.getvalue()


def challan_pdf_filename(challan):
    return f"{challan.challan_number}.pdf"
