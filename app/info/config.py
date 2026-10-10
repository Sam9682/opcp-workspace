"""Configuration for PSMC information
This file contains static information about the OPCP PSMC.
In a production environment, this could be stored in a database or CMS.
"""
from datetime import date
from app.info.schemas import (
    PSMCInfo, 
    BoardMember, 
    LegalDocument,
    FinancialReport
)


# PSMC basic information (Requirements 1.1, 8.1, 8.2)
PSMC_INFO = PSMCInfo(
    name="OPCP",
    address="123 Rue de l'PSMC, 75001 Paris, France",
    siret="12345678900012",  # Example SIRET number
    board_members=[
        BoardMember(
            name="Jean Dupont",
            position="Président",
            email="president@opcp-psmc.com"
        ),
        BoardMember(
            name="Marie Martin",
            position="Trésorière",
            email="tresorier@opcp-psmc.com"
        ),
        BoardMember(
            name="Pierre Durand",
            position="Secrétaire",
            email="secretaire@opcp-psmc.com"
        )
    ]
)

# Mission and activities (Requirements 1.2)
MISSION = """OPCP est produit OVH dédiée à la promotion et au développement 
des technologies de l'information et de la communication. Notre mission est de créer un espace 
d'échange et de partage de connaissances pour tous les passionnés de technologie."""

ACTIVITIES = """Nos activités incluent :
- Organisation de conférences et d'ateliers techniques
- Mise en place de groupes de travail thématiques
- Développement de projets collaboratifs open source
- Événements de networking pour les membres
- Formation continue et partage de compétences
- Participation à des événements communautaires"""

# Contact information (Requirement 1.4)
CONTACT_EMAIL = "contact@opcp-psmc.com"
CONTACT_PHONE = "+33 1 23 45 67 89"

# Legal documents (Requirements 8.2, 8.3)
STATUTES = LegalDocument(
    title="Statuts de l'OPCP",
    description="Les statuts définissent l'objet, le fonctionnement et les règles de la plateforme OPCP.",
    content="""STATUTS DE L'OPCP

Article 1 - Constitution et dénomination

Article 2 - Objet

Article 3 - Durée
"""
)

REGULATIONS = LegalDocument(
    title="Règlement Intérieur de l'OPCP",
    description="Le règlement intérieur précise les modalités d'application des statuts et les règles de fonctionnement quotidien.",
    content="""RÈGLEMENT INTÉRIEUR DE L'OPCP
"""
)

# Financial reports (Requirement 8.5)
# In a real application, these would be fetched from the database
FINANCIAL_REPORTS = [
    FinancialReport(
        id="report-2024",
        title="Rapport Financier 2024",
        year=2024,
        description="Rapport financier annuel incluant le bilan et les notes explicatives.",
        published_date=date(2024, 12, 31)
    ),
    FinancialReport(
        id="report-2023",
        title="Rapport Financier 2023",
        year=2023,
        description="Rapport financier annuel incluant le bilan et les notes explicatives.",
        published_date=date(2023, 12, 31)
    ),
    FinancialReport(
        id="report-2022",
        title="Rapport Financier 2022",
        year=2022,
        description="Rapport financier annuel incluant le bilan et les notes explicatives.",
        published_date=date(2022, 12, 31)
    )
]

# Board information last updated date
BOARD_LAST_UPDATED = date(2024, 1, 15)
