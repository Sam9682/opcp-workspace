"""Oracle AI router"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import json
import asyncio
from app.database import get_db
from app.auth.dependencies import get_current_user, get_current_user_optional
from app.events.dependencies import require_admin
from app.models.user import User
from app.oracle.schemas import (
    OracleQuery,
    OracleResponse,
    OracleHistoryItem,
    OracleAnalysisRequest,
    ForumAnalysisResponse
)
from app.oracle.service import OracleService
from app.oracle.provider_config import get_enabled_map, is_provider_enabled
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.middleware.rate_limit import limiter
from app.logging_config import logger

router = APIRouter(prefix="/api/oracle", tags=["oracle"])


@router.post("/ask", response_model=OracleResponse)
@limiter.limit("10/minute")
async def ask_oracle(
    request: Request,
    query: OracleQuery,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Poser une question à l'Oracle AI
    
    - Supporte plusieurs fournisseurs d'IA: kiro (défaut), shai, openai
    - Historique sauvegardé pour les utilisateurs connectés
    - Rate limited à 10 requêtes par minute
    """
    if not is_provider_enabled(db, query.ai_provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le fournisseur d'IA '{query.ai_provider}' n'est pas activé"
        )
    try:
        user_id = current_user.id if current_user else None
        response = await OracleService.ask_oracle(db, query, user_id)
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la consultation de l'Oracle: {str(e)}"
        )


@router.post("/ask/stream")
@limiter.limit("10/minute")
async def ask_oracle_stream(
    request: Request,
    query: OracleQuery,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Poser une question à l'Oracle AI avec streaming SSE
    
    - Retourne les réponses en temps réel via Server-Sent Events
    - Supporte plusieurs fournisseurs d'IA: kiro (défaut), shai, openai
    - Historique sauvegardé pour les utilisateurs connectés
    - Rate limited à 10 requêtes par minute
    """
    if not is_provider_enabled(db, query.ai_provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le fournisseur d'IA '{query.ai_provider}' n'est pas activé"
        )

    async def event_generator():
        try:
            user_id = current_user.id if current_user else None
            
            # Send start event
            yield f"data: {json.dumps({'type': 'start', 'provider': query.ai_provider})}\n\n"
            
            # Stream the response
            async for chunk in OracleService.ask_oracle_stream(db, query, user_id):
                if chunk['type'] == 'token':
                    yield f"data: {json.dumps(chunk)}\n\n"
                elif chunk['type'] == 'done':
                    yield f"data: {json.dumps(chunk)}\n\n"
                elif chunk['type'] == 'error':
                    yield f"data: {json.dumps(chunk)}\n\n"
                    break
                
                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.01)
            
        except Exception as e:
            logger.error(f"SSE stream error: {str(e)}")
            error_data = {
                'type': 'error',
                'message': f"Erreur: {str(e)}"
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/history", response_model=List[OracleHistoryItem])
async def get_oracle_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupérer l'historique des questions posées à l'Oracle
    
    - Limité aux questions de l'utilisateur connecté
    - Maximum 50 résultats par défaut
    """
    try:
        history = OracleService.get_history(db, current_user.id, limit)
        return history
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de l'historique: {str(e)}"
        )


@router.get("/history/all", response_model=List[OracleHistoryItem])
async def get_all_oracle_history(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Récupérer tout l'historique des questions (admin uniquement)
    
    - Accessible uniquement aux administrateurs
    - Maximum 100 résultats par défaut
    """
    try:
        history = OracleService.get_history(db, None, limit)
        return history
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de l'historique: {str(e)}"
        )


@router.post("/analyze/forum", response_model=ForumAnalysisResponse)
@limiter.limit("5/hour")
async def analyze_forum(
    request: Request,
    analysis_request: OracleAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyser les messages du forum avec l'Oracle AI
    
    - Résumé des discussions
    - Prédiction de perte d'emplois à 5, 10 et 20 ans
    - Identification des sujets clés
    - Analyse de sentiment
    - Rate limited à 5 requêtes par heure (analyse coûteuse)
    """
    try:
        analysis = await OracleService.analyze_forum(db, analysis_request.ai_provider)
        return analysis
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'analyse du forum: {str(e)}"
        )


@router.get("/providers")
async def get_available_providers(db: Session = Depends(get_db)):
    """
    Liste des fournisseurs d'IA disponibles

    Chaque fournisseur porte un indicateur ``enabled`` reflétant la
    configuration administrateur (table ``ai_provider_config``). Le front
    n'affiche dans le menu déroulant que les fournisseurs activés. Le
    fournisseur ``shai`` est toujours activé.
    """
    enabled_map = get_enabled_map(db)

    provider_meta = [
        {
            "id": "shai",
            "name": "Shai AI",
            "description": "IA d'OVH Cloud (recommandé)",
            "default": True,
        },
        {
            "id": "kiro",
            "name": "Kiro AI",
            "description": "IA locale via kiro-cli (inclus dans le container)",
            "default": False,
        },
        {
            "id": "openai",
            "name": "OpenAI",
            "description": "GPT-4 d'OpenAI",
            "default": False,
        },
        {
            "id": "opcp_companion",
            "name": "OPCP Companion",
            "description": "Assistant RAG basé sur la base documentaire OPCP (pgvector + OVH)",
            "default": False,
        },
    ]

    providers = [
        {**meta, "enabled": enabled_map.get(meta["id"], False)}
        for meta in provider_meta
    ]

    return {"providers": providers}
