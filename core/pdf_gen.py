import os
import os.path
import tempfile
import threading
import time
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.pdfgen import canvas
from num2words import num2words
from datetime import date

def format_inr(number):
    return f"INR {number:,.2f}"

def print_pdf(pdf_path):
    """
    Send a PDF directly to the system default printer, then delete
    the temp file after a short delay to allow the print spooler to read it.
    """
    try:
        if os.name == 'nt':
            os.startfile(pdf_path, "print")
        else:
            import subprocess
            subprocess.run(["lp", pdf_path], check=True)
    except Exception:
        # Fallback: open normally so user can print via viewer
        if hasattr(os, "startfile"):
            os.startfile(pdf_path)

    # Clean up the temp file after a delay (give print spooler time)
    def _cleanup():
        time.sleep(15)
        try:
            os.remove(pdf_path)
        except:
            pass
    threading.Thread(target=_cleanup, daemon=True).start()

class PDFGenerator:
    def __init__(self):
        self.output_dir = tempfile.gettempdir()
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name='CenterBold',
            parent=self.styles['Normal'],
            alignment=1,
            fontSize=14,
            leading=18,
            fontName='Helvetica-Bold'
        ))
        self.styles.add(ParagraphStyle(
            name='DocTitle',
            parent=self.styles['Normal'],
            alignment=1,
            fontSize=18,
            leading=22,
            fontName='Helvetica-Bold',
            spaceAfter=12
        ))
        self.styles.add(ParagraphStyle(
            name='Small',
            parent=self.styles['Normal'],
            fontSize=8,
            leading=10
        ))
        self.styles.add(ParagraphStyle(
            name='RightAlign',
            parent=self.styles['Normal'],
            alignment=2
        ))

    def _get_company_header(self, company_data):
        # Coerce None to safe defaults — .get() only uses default when key is MISSING, not when value is None
        name = str(company_data.get("name") or "YOUR COMPANY NAME")
        addr = str(company_data.get("address") or "123, Tirupur Textile Hub, Tamil Nadu")
        gst  = str(company_data.get("gst_details") or "GSTIN: 33AAAAA0000A1Z5")

        header = [
            Paragraph(name.upper(), self.styles['DocTitle']),
            Paragraph(addr, self.styles['Normal']),
            Paragraph(gst, self.styles['Normal']),
            Spacer(1, 0.2 * inch),
            HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=5, spaceAfter=5)
        ]
        return header

    def generate_packing_slip(self, slip_header, items, company_data={}):
        filename = f"Packing_Slip_{slip_header.get('slip_no', 'TEMP')}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        elements = []

        # 1. Header
        elements.extend(self._get_company_header(company_data))
        elements.append(Paragraph("PACKING SLIP", self.styles['CenterBold']))
        elements.append(Spacer(1, 0.1 * inch))

        # 2. Info Grid
        info_data = [
            [f"Slip No: {slip_header.get('slip_no')}", f"Date: {slip_header.get('slip_date')}"],
            [f"Party: {slip_header.get('party_name')}", f"Order No: {slip_header.get('party_order_no', '-')}"],
            [f"Destination: {slip_header.get('destination', '-')}", f"Cases: {slip_header.get('no_of_cases', 0)}"]
        ]
        t = Table(info_data, colWidths=[3 * inch, 3 * inch])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.2 * inch))

        # 3. Items Table
        data = [["Item Description", "Size", "Qty (Pcs)", "Boxes"]]
        for it in items:
            data.append([
                str(it.get("item_name") or ""),
                str(it.get("size_value") or ""),
                str(it.get("qty_pieces") or 0),
                f"{float(it.get('qty_boxes') or 0):.1f}"
            ])

        # Totals Row
        data.append(["TOTAL", "", str(slip_header.get("total_pcs") or 0), f"{float(slip_header.get('total_boxes') or 0):.1f}"])

        t = Table(data, colWidths=[2.5*inch, 1.5*inch, 1*inch, 1*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'), # Item name left aligned
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -2), 1, colors.grey),
            ('LINEBELOW', (0, -1), (-1, -1), 2, colors.black), # Total line
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        elements.append(t)

        # 4. Footer
        elements.append(Spacer(1, 0.5 * inch))
        elements.append(Paragraph("Prepared By: ____________________", self.styles['Normal']))
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph("Checked By: ____________________", self.styles['Normal']))

        doc.build(elements)
        return filepath

    def generate_tax_invoice(self, inv_header, items, company_data={}):
        filename = f"Tax_Invoice_{inv_header.get('invoice_no', 'TEMP')}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        doc = SimpleDocTemplate(filepath, pagesize=A4, leftMargin=0.5*inch, rightMargin=0.5*inch)
        elements = []

        # 1. Header
        elements.extend(self._get_company_header(company_data))
        elements.append(Paragraph("TAX INVOICE", self.styles['DocTitle']))

        # 2. Party Details
        party_info = [
            [Paragraph(f"<b>Billed To:</b><br/>{inv_header.get('party_name') or '-'}<br/>{inv_header.get('party_address') or ''}<br/>GSTIN: {inv_header.get('party_gstin') or '-'}", self.styles['Normal']),
             Paragraph(f"Invoice No: <b>{inv_header.get('invoice_no') or '-'}</b><br/>Date: {inv_header.get('invoice_date') or '-'}<br/>LR No: {inv_header.get('lr_no') or '-'}<br/>Place of Supply: {inv_header.get('destination') or '-'}", self.styles['Normal'])]
        ]
        t = Table(party_info, colWidths=[3.5 * inch, 3.5 * inch])
        t.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
        elements.append(t)
        elements.append(Spacer(1, 0.2 * inch))

        # 3. Itemized Table
        data = [["Sl", "Description", "HSN", "Qty", "Rate", "Amount", "Tax %", "Tax Amt"]]
        for i, it in enumerate(items, 1):
            # Estimate tax for row if not provided
            amt   = float(it.get("amount") or 0)
            tax_p = float(it.get("tax_percent") or 5)
            tax_amt = amt * (tax_p / 100)
            data.append([
                str(i),
                f"{it.get('item_name') or ''} ({it.get('size_value') or ''})",
                str(it.get("hsn_code") or "-"),
                str(it.get("qty_pieces") or 0),
                f"{float(it.get('rate') or 0):.2f}",
                f"{amt:.2f}",
                f"{tax_p}%",
                f"{tax_amt:.2f}"
            ])

        t = Table(data, colWidths=[0.3*inch, 2.5*inch, 0.7*inch, 0.6*inch, 0.8*inch, 1*inch, 0.5*inch, 0.8*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ]))
        elements.append(t)

        # 4. Totals & Discounts
        total_taxable = float(inv_header.get("taxable_amount") or 0)
        total_gst     = float(inv_header.get("igst_amount") or 0) or (float(inv_header.get("cgst_amount") or 0) + float(inv_header.get("sgst_amount") or 0))
        net_amt       = float(inv_header.get("net_amount") or 0)
        roff          = float(inv_header.get("round_off") or 0)

        summary_data = [
            ["", "Taxable Value:", f"\u20b9 {total_taxable:,.2f}"],
            ["", f"{inv_header.get('tax_type') or 'GST'} Total:", f"\u20b9 {total_gst:,.2f}"],
            ["", "Round Off:", f"{roff:.2f}"],
            ["", Paragraph("<b>NET AMOUNT:</b>", self.styles['Normal']), Paragraph(f"<b>\u20b9 {net_amt:,.2f}</b>", self.styles['Normal'])]
        ]
        t = Table(summary_data, colWidths=[4.5*inch, 1.5*inch, 1.2*inch])
        t.setStyle(TableStyle([('ALIGN', (1,0), (-1,-1), 'RIGHT')]))
        elements.append(t)

        # 5. Amount in Words
        words = num2words(int(net_amt), lang='en_IN').capitalize() + " Rupees Only"
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Paragraph(f"<b>Amount in Words:</b> {words}", self.styles['Normal']))

        # 6. Declaration & Sign
        elements.append(Spacer(1, 0.4 * inch))
        elements.append(Paragraph("<b>Declaration:</b> We declare that this invoice shows the actual price of the goods described and that all particulars are true and correct.", self.styles['Small']))
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph(f"For <b>{str(company_data.get('name') or 'YOUR COMPANY')}</b>", self.styles['RightAlign']))
        elements.append(Spacer(1, 0.4 * inch))
        elements.append(Paragraph("Authorised Signatory", self.styles['RightAlign']))

        doc.build(elements)
        return filepath

    def generate_voucher(self, v_header, company_data={}):
        filename = f"Cheque_{v_header.get('voucher_no', 'TEMP')}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        elements = []

        elements.extend(self._get_company_header(company_data))
        v_type = v_header.get('type', 'RECEIPT').upper()
        elements.append(Paragraph(f"{v_type} CHEQUE", self.styles['DocTitle']))
        elements.append(Spacer(1, 0.2 * inch))

        direction = v_header.get("direction_label", "Paid To / Received From")

        data = [
            ["Cheque No:", str(v_header.get("voucher_no") or "-"), "Date:", str(v_header.get("voucher_date") or "-")],
            [f"{direction}:", str(v_header.get("party_name") or "-"), "Mode:", str(v_header.get("mode") or "Cash")],
            ["Amount:", format_inr(float(v_header.get("amount") or 0)), "", ""]
        ]
        t = Table(data, colWidths=[1.5*inch, 2.5*inch, 1*inch, 1.5*inch])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 11),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.3 * inch))

        elements.append(Paragraph(f"<b>Narration:</b> {v_header.get('narration', '-')}", self.styles['Normal']))
        elements.append(Spacer(1, 0.5 * inch))

        words = num2words(int(v_header.get("amount", 0)), lang='en_IN').capitalize() + " Rupees Only"
        elements.append(Paragraph(f"<b>Amount in Words:</b> {words}", self.styles['Normal']))
        elements.append(Spacer(1, 0.8 * inch))

        # Footer Signatures
        sig_data = [
            [Paragraph("____________________<br/>Receiver's Signature", self.styles['Normal']),
             Paragraph("____________________<br/>Authorised Signatory", self.styles['RightAlign'])]
        ]
        sig_table = Table(sig_data, colWidths=[3.5*inch, 3.5*inch])
        elements.append(sig_table)

        doc.build(elements)
        return filepath

    def generate_order(self, order_header, items, company_data={}):
        filename = f"Order_{order_header.get('order_no', 'TEMP')}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        elements = []

        # 1. Header
        elements.extend(self._get_company_header(company_data))
        elements.append(Paragraph("SALES ORDER CONFIRMATION", self.styles['CenterBold']))
        elements.append(Spacer(1, 0.1 * inch))

        # 2. Info Grid
        info_data = [
            [f"Order No: {order_header.get('order_no')}", f"Date: {order_header.get('order_date')}"],
            [f"Party: {order_header.get('party_name')}", f"Agent: {order_header.get('agent_name', '-')}"],
            [f"Destination: {order_header.get('destination', '-')}", f"Status: {order_header.get('status', 'Pending')}"]
        ]
        t = Table(info_data, colWidths=[3.5 * inch, 3.5 * inch])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.2 * inch))

        # 3. Items Table
        data = [["Item Description", "Size", "Qty (Pcs)", "Rate", "Amount"]]
        for it in items:
            data.append([
                str(it.get("item_name") or ""),
                str(it.get("size_value") or ""),
                str(it.get("qty_pieces") or 0),
                f"{float(it.get('rate') or 0):.2f}",
                f"{float(it.get('amount') or 0):.2f}"
            ])

        # Totals Row
        data.append(["TOTAL", "", str(order_header.get("total_pcs") or 0), "", f"{float(order_header.get('total_amount') or 0):.2f}"])

        t = Table(data, colWidths=[2.5*inch, 1*inch, 1*inch, 1*inch, 1.5*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -2), 1, colors.grey),
            ('LINEBELOW', (0, -1), (-1, -1), 2, colors.black),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        elements.append(t)

        elements.append(Spacer(1, 0.5 * inch))
        elements.append(Paragraph(f"<b>Remarks:</b> {order_header.get('remarks', '-')}", self.styles['Normal']))
        
        doc.build(elements)
        return filepath

    def generate_cheque(self, payee_name, amount, date_str, ref_no=""):
        """
        Generate a cheque PDF on standard Indian bank cheque size (8 x 3.5 inches).
        Positions are calibrated for common Indian bank cheque formats.
        """
        cheque_width = 8 * inch
        cheque_height = 3.5 * inch
        safe_name = str(payee_name)[:15].replace(' ', '_').replace('/', '-')
        filename = f"Cheque_{safe_name}_{int(float(amount))}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        
        c = canvas.Canvas(filepath, pagesize=(cheque_width, cheque_height))
        
        # === A/C PAYEE crossing lines (top-left) ===
        c.setFont("Helvetica-Bold", 10)
        c.line(0.3 * inch, 3.15 * inch, 1.9 * inch, 3.15 * inch)
        c.drawString(0.5 * inch, 3.2 * inch, "A/C PAYEE ONLY")
        c.line(0.3 * inch, 3.35 * inch, 1.9 * inch, 3.35 * inch)
        
        # === Date (top-right) — spaced digits for DD MM YYYY boxes ===
        c.setFont("Helvetica-Bold", 12)
        try:
            parts = str(date_str).split('-')
            if len(parts) == 3:
                # ISO format YYYY-MM-DD
                yy, mm, dd = parts[0], parts[1], parts[2]
                date_display = f"{dd[0]}  {dd[1]}  {mm[0]}  {mm[1]}  {yy[0]}  {yy[1]}  {yy[2]}  {yy[3]}"
            else:
                date_display = str(date_str)
        except:
            date_display = str(date_str)
        c.drawString(5.5 * inch, 2.85 * inch, date_display)
        
        # === Pay / Payee Name (middle-left) ===
        c.setFont("Helvetica", 9)
        c.drawString(0.4 * inch, 2.3 * inch, "Pay")
        c.setFont("Helvetica-Bold", 13)
        c.drawString(0.8 * inch, 2.3 * inch, str(payee_name).upper())
        
        # === Amount in Words (below payee, two lines if needed) ===
        c.setFont("Helvetica", 9)
        c.drawString(0.4 * inch, 1.85 * inch, "Rupees")
        try:
            amt_float = float(amount)
            amt_words = num2words(int(amt_float), lang='en_IN').title()
            paise = int(round((amt_float - int(amt_float)) * 100))
            if paise > 0:
                amt_words += f" and {num2words(paise, lang='en_IN').title()} Paise"
            amt_words += " Only"
        except:
            amt_words = "Zero Only"
        
        c.setFont("Helvetica-Bold", 11)
        # Split long amount text across two lines if needed
        if len(amt_words) > 55:
            c.drawString(1.0 * inch, 1.85 * inch, amt_words[:55])
            c.drawString(0.4 * inch, 1.55 * inch, amt_words[55:])
        else:
            c.drawString(1.0 * inch, 1.85 * inch, amt_words)
        
        # === Amount in Figures (right side box) ===
        c.setFont("Helvetica-Bold", 14)
        c.drawString(6.0 * inch, 1.85 * inch, f"Rs. {float(amount):,.2f} /-")
        
        # === Reference/Voucher No (bottom-left, small) ===
        if ref_no:
            c.setFont("Helvetica", 8)
            c.drawString(0.4 * inch, 0.6 * inch, f"Ref: {ref_no}")
        
        c.showPage()
        c.save()
        return filepath

# Singleton instance
pdf_engine = PDFGenerator()
