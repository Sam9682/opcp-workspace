"""Pydantic schemas for information endpoints"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import date


class BoardMember(BaseModel):
    """Board member information"""
    name: str
    position: str
    email: Optional[str] = None


class PSMCInfo(BaseModel):
    """PSMC basic information"""
    name: str
    address: str
    siret: Optional[str] = None
    board_members: List[BoardMember]


class HomepageResponse(BaseModel):
    """Response schema for homepage endpoint
    
    Validates Requirements 1.1, 1.2, 1.4, 8.1, 8.2:
    - PSMC information (name, address, board members)
    - Mission and activities description
    - Contact information
    """
    PSMC: PSMCInfo
    mission: str
    activities: str
    contact_email: str
    contact_phone: Optional[str] = None


class LegalDocument(BaseModel):
    """Legal document information"""
    title: str
    description: str
    url: Optional[str] = None
    content: Optional[str] = None


class LegalInfoResponse(BaseModel):
    """Response schema for legal information endpoint
    
    Validates Requirements 8.2, 8.3:
    - PSMC statutes
    - Internal regulations
    """
    statutes: LegalDocument
    regulations: LegalDocument


class BoardInfoResponse(BaseModel):
    """Response schema for board information endpoint
    
    Validates Requirements 8.2:
    - Board member information with contact details
    """
    board_members: List[BoardMember]
    last_updated: date


class FinancialReport(BaseModel):
    """Financial report information"""
    id: str
    title: str
    year: int
    description: str
    document_id: Optional[str] = None
    published_date: date


class FinancialReportsResponse(BaseModel):
    """Response schema for financial reports endpoint
    
    Validates Requirements 8.5:
    - List of financial reports accessible to members
    """
    reports: List[FinancialReport]
    message: str = "Financial reports are available to all members for transparency"


class StatsResponse(BaseModel):
    """Response schema for statistics endpoint
    
    Returns public statistics about the PSMC
    """
    total_users: int
    total_events: int
    total_topics: int
