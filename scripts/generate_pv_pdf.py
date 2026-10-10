#!/usr/bin/env python3
"""
Script pour générer un PDF du Procès-Verbal d'Assemblée Constitutive
PSMC OPCP - OVH
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from datetime import datetime

def generate_pv_pdf(output_filename="docs/PROCES_VERBAL_ASSEMBLEE_CONSTITUTIVE.pdf"):
    """Génère le PDF du procès-verbal"""
    
    # Créer le document
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Style pour le titre principal
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Style pour les sous-titres
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold'
    )
    
    # Style pour le texte normal
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        alignment=TA_JUSTIFY,
        spaceAfter=12,
        leading=16
    )
    
    # Style pour le texte centré
    center_style = ParagraphStyle(
        'CustomCenter',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    # Contenu du document
    story = []
    
    # En-tête avec logo/nom PSMC
    story.append(Paragraph("PSMC OPCP", title_style))
    story.append(Paragraph("OVH", center_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Titre du document
    story.append(Paragraph("PROCÈS-VERBAL D'ASSEMBLÉE CONSTITUTIVE", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Introduction
    intro_text = """
    Le <b>20 sept. 2026</b> à <b>20h</b>, les membres fondateurs se sont réunis. 
    """
    story.append(Paragraph(intro_text, normal_style))
    story.append(Spacer(1, 0.5*cm))
    
    
    # Générer le PDF
    doc.build(story)
    print(f"✅ PDF généré avec succès : {output_filename}")
    return output_filename


if __name__ == "__main__":
    generate_pv_pdf()
