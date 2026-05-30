"""PDF receipt generation using ReportLab."""

import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
)
from reportlab.lib.utils import ImageReader

import config


_NAVY = colors.HexColor(config.COLORS["primary"])
_ACCENT = colors.HexColor(config.COLORS["accent"])
_MUTED = colors.HexColor(config.COLORS["text_muted"])


def _fmt_qty(unit, qty):
    """Weights under 1 kg are shown in grams on the receipt."""
    if unit == "kg" and qty < 1:
        return f"{int(round(qty * 1000))} g"
    return f"{qty:g} {unit}"


def _logo_flowable(max_w):
    """Return a scaled logo Image flowable, or None."""
    path = config.LOGO_PATH
    if not path:
        return None
    if not os.path.isabs(path):
        path = os.path.join(config.IMAGES_DIR, path)
    if not os.path.exists(path):
        return None
    try:
        iw, ih = ImageReader(path).getSize()
        target_h = 18 * mm
        target_w = target_h * (iw / ih)
        if target_w > max_w:
            target_w = max_w
            target_h = target_w * (ih / iw)
        img = Image(path, width=target_w, height=target_h)
        img.hAlign = "CENTER"
        return img
    except Exception:
        return None


def generate_receipt(bill_number, created_at, items, subtotal, discount,
                     total, customer_name="Walk-in", out_dir=config.RECEIPTS_DIR,
                     payment=None, customer_phone=None):
    """Create a PDF receipt and return its file path.

    items   : list of dicts with name, unit, quantity, price, line_total.
    payment : optional dict (payment_method, amount_paid, change_due,
              redeem_discount, points_earned, points_redeemed, points_balance).
    """
    cur = config.CURRENCY
    payment = payment or {}
    pdf_path = os.path.join(out_dir, f"{bill_number}.pdf")

    doc = SimpleDocTemplate(
        pdf_path, pagesize=A5,
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"Receipt {bill_number}",
    )

    styles = getSampleStyleSheet()
    h_store = ParagraphStyle(
        "store", parent=styles["Title"], fontSize=20, textColor=_NAVY,
        spaceAfter=2, alignment=1,
    )
    h_tag = ParagraphStyle(
        "tag", parent=styles["Normal"], fontSize=9, textColor=_MUTED,
        alignment=1, spaceAfter=2,
    )
    h_contact = ParagraphStyle(
        "contact", parent=styles["Normal"], fontSize=8, textColor=_MUTED,
        alignment=1, spaceAfter=1,
    )
    meta = ParagraphStyle(
        "meta", parent=styles["Normal"], fontSize=9, textColor=_MUTED,
    )
    thanks = ParagraphStyle(
        "thanks", parent=styles["Normal"], fontSize=10, textColor=_NAVY,
        alignment=1, spaceBefore=14,
    )

    story = []
    logo = _logo_flowable(doc.width)
    if logo is not None:
        story.append(logo)
        story.append(Spacer(1, 4))
    story.append(Paragraph(config.STORE_NAME, h_store))
    if config.STORE_TAGLINE:
        story.append(Paragraph(config.STORE_TAGLINE, h_tag))
    if config.STORE_ADDRESS:
        story.append(Paragraph(config.STORE_ADDRESS, h_contact))
    contact_bits = []
    if config.STORE_PHONE:
        contact_bits.append(f"Tel: {config.STORE_PHONE}")
    if config.STORE_TRN:
        contact_bits.append(f"TRN: {config.STORE_TRN}")
    if contact_bits:
        story.append(Paragraph("  |  ".join(contact_bits), h_contact))
    story.append(Spacer(1, 10))

    # Bill meta block
    cust_line = f"<b>Customer:</b> {customer_name or 'Walk-in'}"
    if customer_phone:
        cust_line += f" ({customer_phone})"
    meta_tbl = Table(
        [
            [Paragraph(f"<b>Bill No:</b> {bill_number}", meta),
             Paragraph(f"<b>Date:</b> {created_at}", meta)],
            [Paragraph(cust_line, meta), ""],
        ],
        colWidths=[doc.width / 2.0] * 2,
    )
    meta_tbl.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_tbl)

    # Items table
    header = ["#", "Item", "Qty", "Rate", "Amount"]
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=9)
    data = [header]
    for idx, it in enumerate(items, start=1):
        data.append([
            str(idx),
            Paragraph(it["name"], cell),
            _fmt_qty(it["unit"], it["quantity"]),
            f"{it['price']:.2f}",
            f"{it['line_total']:.2f}",
        ])

    col_w = [doc.width * w for w in (0.08, 0.42, 0.18, 0.16, 0.16)]
    tbl = Table(data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f4f6fb")]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, _NAVY),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8))

    # Totals block (right-aligned)
    payable = round(total, 2)

    totals_rows = [["Subtotal", f"{cur} {subtotal:.2f}"]]
    if discount > 0:
        totals_rows.append(["Discount", f"- {cur} {discount:.2f}"])
    totals_rows.append(["TOTAL", f"{cur} {payable:.2f}"])
    if payment.get("payment_method"):
        totals_rows.append([f"Paid ({payment['payment_method']})",
                            f"{cur} {payment.get('amount_paid', payable):.2f}"])
        if payment.get("change_due", 0):
            totals_rows.append(["Change",
                               f"{cur} {payment['change_due']:.2f}"])

    last_total_row = 2 + (1 if discount > 0 else 0)
    totals_tbl = Table(totals_rows,
                       colWidths=[doc.width * 0.32, doc.width * 0.28],
                       hAlign="RIGHT")
    totals_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("FONTNAME", (0, last_total_row), (-1, last_total_row),
         "Helvetica-Bold"),
        ("FONTSIZE", (0, last_total_row), (-1, last_total_row), 12),
        ("TEXTCOLOR", (0, last_total_row), (-1, last_total_row), _ACCENT),
        ("LINEABOVE", (0, last_total_row), (-1, last_total_row), 0.5, _NAVY),
        ("TOPPADDING", (0, last_total_row), (-1, last_total_row), 6),
    ]))
    story.append(totals_tbl)

    footer_msg = config.RECEIPT_FOOTER or f"Thank you for shopping at {config.STORE_NAME}!"
    story.append(Paragraph(footer_msg, thanks))

    doc.build(story)
    return pdf_path
