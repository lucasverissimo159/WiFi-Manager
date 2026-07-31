#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Geração de relatórios PDF e TXT para vouchers irregulares."""

from datetime import datetime
from models.cpf_validator import CPFValidationResult


def gerar_relatorio_pdf(vouchers: list[dict], filepath: str, ip_loja: str) -> str:
    """Gera relatório PDF. Faz fallback para TXT se reportlab não estiver instalado."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        return gerar_relatorio_txt(vouchers, filepath.replace('.pdf', '.txt'), ip_loja)

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        rightMargin=20 * mm, leftMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm
    )
    styles = getSampleStyleSheet()

    s_title = ParagraphStyle('T', parent=styles['Title'], fontSize=18, spaceAfter=6,
                              textColor=colors.HexColor('#1a1a2e'), fontName='Helvetica-Bold')
    s_sub = ParagraphStyle('S', parent=styles['Normal'], fontSize=11, spaceAfter=4,
                            textColor=colors.HexColor('#555555'))
    s_info = ParagraphStyle('I', parent=styles['Normal'], fontSize=10, spaceAfter=2,
                             textColor=colors.HexColor('#333333'))
    s_hdr = ParagraphStyle('H', parent=styles['Normal'], fontSize=9, textColor=colors.white,
                            fontName='Helvetica-Bold', alignment=TA_CENTER)
    s_cell = ParagraphStyle('C', parent=styles['Normal'], fontSize=8,
                             textColor=colors.HexColor('#333333'), alignment=TA_CENTER)
    s_cell_l = ParagraphStyle('CL', parent=s_cell, alignment=TA_LEFT)
    s_motivo = ParagraphStyle('M', parent=s_cell, textColor=colors.HexColor('#c0392b'),
                               fontName='Helvetica-Bold', alignment=TA_LEFT)

    elems = []
    elems.append(Paragraph("RELATÓRIO DE BLOQUEIO DE REDE WI-FI", s_title))
    elems.append(Paragraph("Gerenciador de WiFi UniFi — Setor de TI / Infraestrutura", s_sub))
    elems.append(Spacer(1, 4 * mm))
    elems.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1a1a2e'), spaceAfter=4 * mm))

    agora = datetime.now().strftime('%d/%m/%Y às %H:%M:%S')
    elems.append(Paragraph(f"<b>Data/Hora:</b> {agora}", s_info))
    elems.append(Paragraph(f"<b>Controller:</b> {ip_loja}", s_info))
    elems.append(Paragraph(f"<b>Vouchers irregulares:</b> {len(vouchers)}", s_info))
    elems.append(Spacer(1, 3 * mm))
    elems.append(Paragraph(
        "<b>Motivo:</b> Vouchers sem CPF válido no campo Notes. "
        "Rede bloqueada conforme política interna.", s_info))
    elems.append(Spacer(1, 6 * mm))

    headers = [Paragraph(h, s_hdr) for h in ["Nº", "Código", "Criação", "Notes", "CPF", "Nível", "Motivo"]]
    data = [headers]

    for i, v in enumerate(vouchers, 1):
        code = v.get('code', 'N/A')
        ct = v.get('create_time', 0)
        try:
            cs = datetime.fromtimestamp(ct).strftime('%d/%m/%Y %H:%M') if ct else 'N/A'
        except Exception:
            cs = str(ct)

        notes = v.get('note', v.get('notes', ''))
        val: CPFValidationResult | None = v.get('_validation')

        if val:
            cpf_d = val.cpf_formatted or "—"
            lv = {"invalid": "INVÁLIDO", "suspect": "SUSPEITO", "valid": "VÁLIDO"}.get(val.risk_level, "?")
            mt = "; ".join(val.risk_reasons) if val.risk_reasons else "OK"
        elif not notes or not notes.strip():
            cpf_d, lv, mt = "—", "INVÁLIDO", "Notes vazio"
        else:
            cpf_d, lv, mt = "—", "INVÁLIDO", "CPF não encontrado no Notes"

        data.append([
            Paragraph(str(i), s_cell), Paragraph(code, s_cell),
            Paragraph(cs, s_cell), Paragraph(str(notes) if notes else "—", s_cell_l),
            Paragraph(cpf_d, s_cell), Paragraph(lv, s_cell),
            Paragraph(mt, s_motivo),
        ])

    table = Table(data, colWidths=[22, 65, 75, 90, 80, 52, 130], repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor('#1a1a2e')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        *[('BACKGROUND', (0, i), (-1, i),
           colors.HexColor('#f8f9fa') if i % 2 == 0 else colors.white) for i in range(1, len(data))],
    ]))

    elems.append(table)
    elems.append(Spacer(1, 8 * mm))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc'), spaceAfter=3 * mm))
    elems.append(Paragraph(
        f"UniFi Wi-Fi Manager v2.0 — {agora}",
        ParagraphStyle('F', parent=styles['Normal'], fontSize=8,
                       textColor=colors.HexColor('#999999'), alignment=TA_CENTER)))
    doc.build(elems)
    return filepath


def gerar_relatorio_txt(vouchers: list[dict], filepath: str, ip_loja: str) -> str:
    """Gera relatório em TXT (fallback)."""
    agora = datetime.now().strftime('%d/%m/%Y às %H:%M:%S')
    lines = [
        "=" * 80, "  RELATÓRIO DE BLOQUEIO DE REDE WI-FI",
        "  Gerenciador de WiFi UniFi — TI / Infraestrutura", "=" * 80, "",
        f"  Data/Hora: {agora}", f"  Controller: {ip_loja}",
        f"  Vouchers irregulares: {len(vouchers)}", "",
        "-" * 80, "  VOUCHERS:", "-" * 80, "",
    ]

    for i, v in enumerate(vouchers, 1):
        code = v.get('code', 'N/A')
        ct = v.get('create_time', 0)
        try:
            cs = datetime.fromtimestamp(ct).strftime('%d/%m/%Y %H:%M') if ct else 'N/A'
        except Exception:
            cs = str(ct)
        notes = v.get('note', v.get('notes', ''))
        val: CPFValidationResult | None = v.get('_validation')

        if val:
            cpf_s = val.cpf_formatted or "(nenhum)"
            lv = val.risk_level.upper()
            mt = "; ".join(val.risk_reasons) if val.risk_reasons else "OK"
        elif not notes or not notes.strip():
            cpf_s, lv, mt = "(nenhum)", "INVÁLIDO", "Notes vazio"
        else:
            cpf_s, lv, mt = "(nenhum)", "INVÁLIDO", "CPF não encontrado"

        lines.extend([f"  [{i}] Código: {code}", f"      Criação: {cs}",
                       f"      Notes: {notes or '(vazio)'}", f"      CPF: {cpf_s}",
                       f"      Nível: {lv}", f"      Motivo: {mt}", ""])

    lines.extend(["-" * 80, f"  Gerado em: {agora}", "=" * 80])
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return filepath
