"""Invoice generation service for payment receipts
Feature: OPCP-website
Validates Requirements 4.3, 4.4
"""
import os
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

from app.config import settings

logger = logging.getLogger(__name__)


class InvoiceGenerator:
    """Service for generating PDF invoices
    
    Validates Requirements 4.3:
    - Generates PDF invoices with payment details
    - Includes PSMC information
    - Assigns unique invoice numbers
    """
    
    def __init__(self, storage_dir: str = None):
        """Initialize invoice generator
        
        Args:
            storage_dir: Directory to store generated invoices
        """
        self.storage_dir = storage_dir or os.path.join(settings.UPLOAD_DIR, "invoices")
        Path(self.storage_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"Invoice generator initialized with storage: {self.storage_dir}")
    
    def generate_invoice_number(self, payment_id: str, created_at: datetime) -> str:
        """Generate unique invoice number
        
        Format: INV-YYYY-XXXXXXXX (where X is first 8 chars of payment ID)
        
        Args:
            payment_id: Payment UUID
            created_at: Payment creation timestamp
        
        Returns:
            Invoice number string
        """
        year = created_at.year
        payment_short = str(payment_id).replace("-", "")[:8].upper()
        return f"INV-{year}-{payment_short}"
    
    def generate_invoice(
        self,
        payment_id: str,
        user_email: str,
        user_name: str,
        amount: Decimal,
        currency: str,
        payment_method: str,
        transaction_id: str,
        created_at: datetime
    ) -> str:
        """Generate PDF invoice for a completed payment
        
        Args:
            payment_id: Payment UUID
            user_email: User's email address
            user_name: User's full name
            amount: Payment amount
            currency: Currency code (EUR, USD, etc.)
            payment_method: Payment method used
            transaction_id: Transaction ID from payment provider
            created_at: Payment creation timestamp
        
        Returns:
            Path to generated PDF file
        
        Raises:
            Exception: If PDF generation fails
        """
        try:
            # Generate invoice number
            invoice_number = self.generate_invoice_number(payment_id, created_at)
            
            # Create filename
            filename = f"{invoice_number}.pdf"
            filepath = os.path.join(self.storage_dir, filename)
            
            # Create PDF document
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=20*mm,
                leftMargin=20*mm,
                topMargin=20*mm,
                bottomMargin=20*mm
            )
            
            # Build document content
            story = []
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1a1a1a'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#333333'),
                spaceAfter=12,
                spaceBefore=12
            )
            
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#555555')
            )
            
            # Title
            story.append(Paragraph("FACTURE / INVOICE", title_style))
            story.append(Spacer(1, 10*mm))
            
            # PSMC information
            story.append(Paragraph("PSMC OPCP", heading_style))
            PSMC_info = """
            OVH PSMC Team <br/>
            Email: contact@opcp-psmc.com
            """
            story.append(Paragraph(PSMC_info, normal_style))
            story.append(Spacer(1, 10*mm))
            
            # Invoice details
            invoice_date = created_at.strftime("%d/%m/%Y")
            invoice_data = [
                ["Numéro de facture / Invoice Number:", invoice_number],
                ["Date / Date:", invoice_date],
                ["Client / Customer:", user_name],
                ["Email:", user_email]
            ]
            
            invoice_table = Table(invoice_data, colWidths=[80*mm, 90*mm])
            invoice_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(invoice_table)
            story.append(Spacer(1, 10*mm))
            
            # Payment details
            story.append(Paragraph("Détails du paiement / Payment Details", heading_style))
            
            payment_data = [
                ["Description", "Quantité / Qty", "Prix unitaire / Unit Price", "Total"],
                [
                    "Cotisation annuelle OPCP\nAnnual Membership Fee",
                    "1",
                    f"{float(amount):.2f} {currency}",
                    f"{float(amount):.2f} {currency}"
                ]
            ]
            
            payment_table = Table(payment_data, colWidths=[80*mm, 30*mm, 40*mm, 40*mm])
            payment_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
            ]))
            story.append(payment_table)
            story.append(Spacer(1, 5*mm))
            
            # Total
            total_data = [
                ["Total TTC / Total:", f"{float(amount):.2f} {currency}"]
            ]
            total_table = Table(total_data, colWidths=[130*mm, 40*mm])
            total_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a1a1a')),
                ('ALIGN', (1, 0), (1, 0), 'CENTER'),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9f9f9')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
            ]))
            story.append(total_table)
            story.append(Spacer(1, 10*mm))
            
            # Transaction information
            story.append(Paragraph("Informations de transaction / Transaction Information", heading_style))
            transaction_info = f"""
            Méthode de paiement / Payment Method: {payment_method}<br/>
            ID de transaction / Transaction ID: {transaction_id}<br/>
            Statut / Status: Payé / Paid
            """
            story.append(Paragraph(transaction_info, normal_style))
            story.append(Spacer(1, 15*mm))
            
            # Footer
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor('#888888'),
                alignment=TA_CENTER
            )
            footer_text = """
            Merci pour votre paiement / Thank you for your payment<br/>
            Cette facture est générée automatiquement / This invoice is automatically generated<br/>
            PSMC OPCP - OVH
            """
            story.append(Paragraph(footer_text, footer_style))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"Generated invoice {invoice_number} at {filepath}")
            return filepath
        
        except Exception as e:
            logger.error(f"Failed to generate invoice: {str(e)}", exc_info=True)
            raise


# Global invoice generator instance
invoice_generator = InvoiceGenerator()
