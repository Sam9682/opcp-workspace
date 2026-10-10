#!/usr/bin/env python3
"""
Script pour générer tous les PDFs des documents officiels de l'PSMC OPCP
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors


def create_common_styles():
    """Crée les styles communs pour tous les documents"""
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        alignment=TA_JUSTIFY,
        spaceAfter=12,
        leading=16
    )
    
    center_style = ParagraphStyle(
        'CustomCenter',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    return {
        'title': title_style,
        'heading': heading_style,
        'normal': normal_style,
        'center': center_style
    }


def generate_pv_pdf(output_filename="docs/PROCES_VERBAL_ASSEMBLEE_CONSTITUTIVE.pdf"):
    """Génère le PDF du procès-verbal de l'assemblée constitutive"""
    
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    styles = create_common_styles()
    story = []
    
    # En-tête
    story.append(Paragraph("PROCÈS-VERBAL", styles['title']))
    story.append(Spacer(1, 0.5*cm))
    
    # Introduction
    story.append(Paragraph(
        "Le 16 février 2026 à 20h, les membres fondateurs se sont réunis 2 square des coquelicots. "
        styles['normal']
    ))
    story.append(Spacer(1, 0.5*cm))
    
    # Ordre du jour
    story.append(Paragraph("Ordre du jour", styles['heading']))
    story.append(Paragraph("Création de PSMC", styles['normal']))
    story.append(Paragraph("Adoption des statuts", styles['normal']))
    story.append(Paragraph("Élection", styles['normal']))
    story.append(Paragraph("Pouvoirs pour déclaration", styles['normal']))
    story.append(Spacer(1, 0.5*cm))
        
    # Élection
    story.append(Paragraph("Team PSMC", styles['heading']))
    story.append(Paragraph("Cloud Architect : Samuel LEPETRE", styles['normal']))
    story.append(Spacer(1, 0.5*cm))

    # Clôture
    story.append(Paragraph("La séance est levée à 21h.", styles['normal']))
    story.append(Spacer(1, 1*cm))
    
    # Signatures
    story.append(Paragraph("Fait à OVH, le 16 février 2026", styles['center']))

    story.append(Spacer(1, 0.5*cm))
    
    signatures_data = [
        ['Cloud Architect'],
        ['Samuel LEPETRE'],
        ['Signature :']
    ]
    
    signatures_table = Table(signatures_data, colWidths=[5*cm, 5*cm, 5*cm])
    signatures_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTNAME', (0, 1), (-1, 2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, 1), 9),
        ('FONTSIZE', (0, 2), (-1, 2), 8),
        ('TOPPADDING', (0, 0), (-1, 2), 8),
    ]))
    
    story.append(signatures_table)
    
    doc.build(story)
    print(f"✅ PDF généré : {output_filename}")


def generate_statuts_pdf(output_filename="docs/STATUTS_PSMC_OPCP.pdf"):
    """Génère le PDF des statuts de l'PSMC"""
    
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    styles = create_common_styles()
    story = []
    
    # En-tête
    story.append(Paragraph("PSMC OPCP", styles['title']))
    story.append(Paragraph("OVH", styles['center']))
    story.append(Spacer(1, 0.5*cm))
    
    
    # Signatures
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("Fait à XXX, le XX XXXXXXXXXXX 2026", styles['center']))
    story.append(Spacer(1, 0.5*cm))
    
    signatures_data = [
        ['Le gestionnaire'],
        ['Signature :']
    ]
    
    signatures_table = Table(signatures_data, colWidths=[5*cm, 5*cm, 5*cm])
    signatures_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTNAME', (0, 1), (-1, 2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, 1), 9),
        ('FONTSIZE', (0, 2), (-1, 2), 8),
        ('TOPPADDING', (0, 0), (-1, 2), 8),
    ]))
    
    story.append(signatures_table)

    doc.build(story)
    print(f"✅ PDF généré : {output_filename}")


def generate_reglement_pdf(output_filename="docs/REGLEMENT_INTERIEUR.pdf"):
    """Génère le PDF du règlement intérieur"""
    
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    styles = create_common_styles()
    story = []
    
    # En-tête
    story.append(Paragraph("PSMC OPCP", styles['title']))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("RÈGLEMENT INTÉRIEUR", styles['title']))
    story.append(Spacer(1, 0.5*cm))
    
    # Article 1
    story.append(Paragraph("Article 1 — Objet", styles['heading']))
    story.append(Paragraph(
        "Le présent règlement intérieur complète les statuts de PSMC. Il précise les modalités "
        "pratiques de fonctionnement, notamment l'organisation des pôles thématiques et les conditions "
        "d'usage des outils numériques.",
        styles['normal']
    ))
    
    
    # Article 10
    story.append(Paragraph("Article 10 — Modification du règlement intérieur", styles['heading']))
    story.append(Paragraph(
        "Le règlement intérieur est modifiable par décision et soumis pour information ou "
        "validation à la plus proche Assemblée Générale.",
        styles['normal']
    ))
    
    # Signatures
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("Fait à VERRIERES LE BUISSON, le 30 septembre 2026.", styles['center']))
    story.append(Spacer(1, 0.5*cm))
    
    signatures_data = [
        ['Cloud Architect'],
        ['Signature :']
    ]
    
    signatures_table = Table(signatures_data, colWidths=[5*cm, 5*cm, 5*cm])
    signatures_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTNAME', (0, 1), (-1, 2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, 1), 9),
        ('FONTSIZE', (0, 2), (-1, 2), 8),
        ('TOPPADDING', (0, 0), (-1, 2), 8),
    ]))
    
    story.append(signatures_table)
    
    doc.build(story)
    print(f"✅ PDF généré : {output_filename}")


def generate_dirigeants_pdf(output_filename="docs/LISTE_DES_DIRIGEANTS.pdf"):
    """Génère le PDF de la liste des dirigeants"""
    
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    styles = create_common_styles()
    story = []
    
    # En-tête
    story.append(Paragraph("PSMC OPCP", styles['title']))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("LISTE DES DIRIGEANTS", styles['title']))
    story.append(Spacer(1, 1*cm))
    
    # Informations PSMC
    story.append(Paragraph("<b>PSMC :</b> OPCP", styles['normal']))
    story.append(Paragraph(
        "<b>Siège :</b> 2 square des coquelicots 91370 VERRIERES LE BUISSON",
        styles['normal']
    ))
    story.append(Spacer(1, 1*cm))
    
    # Tableau des dirigeants
    story.append(Paragraph("COMPOSITION", styles['heading']))
    story.append(Spacer(1, 0.5*cm))
    
    dirigeants_data = [
        ['Fonction', 'Identité'],
        [
            'Président',
            'Samuel LEPETRE\nNé le 2 Aout 1969\nNationalité française\nDomicilié au 2 square des coquelicots\n91370 VERRIERES LE BUISSON'
        ]
    ]
    
    dirigeants_table = Table(dirigeants_data, colWidths=[4*cm, 11*cm])
    dirigeants_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 12),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    story.append(dirigeants_table)
    story.append(Spacer(1, 1*cm))
    
    # Note
    story.append(Paragraph(
        "<i>Document établi conformément aux exigences de la loi du 1er juillet 1901 "
        "relative au contrat d'PSMC.</i>",
        ParagraphStyle(
            'Note',
            parent=styles['normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_JUSTIFY
        )
    ))
    
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("Fait à VERRIERES LE BUISSON, le 16 février 2026", styles['center']))
    
    doc.build(story)
    print(f"✅ PDF généré : {output_filename}")


if __name__ == "__main__":
    print("Génération des PDFs des documents officiels OPCP...\n")
    generate_pv_pdf()
    generate_statuts_pdf()
    generate_reglement_pdf()
    generate_dirigeants_pdf()
    print("\n✅ Tous les PDFs ont été générés avec succès !")
