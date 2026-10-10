"""Oracle AI service layer"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.oracle import OracleQuery as OracleQueryModel
from app.models.forum import Topic, Post
from app.oracle.ai_providers import get_ai_provider
from app.oracle.schemas import (
    OracleQuery,
    OracleResponse,
    OracleHistoryItem,
    ForumAnalysisResponse
)
from app.logging_config import logger
import json


class OracleService:
    """Service for Oracle AI operations"""
    
    @staticmethod
    async def ask_oracle(
        db: Session,
        query: OracleQuery,
        user_id: Optional[int] = None
    ) -> OracleResponse:
        """Ask a question to the Oracle"""
        try:
            # Get AI provider
            provider = get_ai_provider(query.ai_provider)
            
            # Query the AI
            result = await provider.query(
                question=query.question,
                context=query.context,
                temperature=query.temperature,
                max_tokens=query.max_tokens
            )
            
            # Save to database
            db_query = OracleQueryModel(
                user_id=user_id,
                question=query.question,
                answer=result["answer"],
                context=query.context,
                ai_provider=result["provider"],
                processing_time=result["processing_time"],
                tokens_used=result.get("tokens_used")
            )
            db.add(db_query)
            db.commit()
            db.refresh(db_query)
            
            return OracleResponse(
                id=db_query.id,
                question=db_query.question,
                answer=db_query.answer,
                ai_provider=db_query.ai_provider,
                context=db_query.context,
                created_at=db_query.created_at,
                user_id=db_query.user_id,
                processing_time=db_query.processing_time,
                tokens_used=db_query.tokens_used,
                sources=result.get("sources")
            )
            
        except Exception as e:
            logger.error(f"Oracle query failed: {str(e)}")
            raise
    
    @staticmethod
    async def ask_oracle_stream(
        db: Session,
        query: OracleQuery,
        user_id: Optional[UUID] = None
    ):
        """Ask a question to the Oracle with streaming response"""
        import time
        
        start_time = time.time()
        full_answer = ""
        
        try:
            # Get AI provider
            provider = get_ai_provider(query.ai_provider)
            
            # Query the AI and get full response
            result = await provider.query(
                question=query.question,
                context=query.context,
                temperature=query.temperature,
                max_tokens=query.max_tokens
            )
            
            full_answer = result["answer"]
            
            # Stream the answer word by word for better UX
            words = full_answer.split()
            for i, word in enumerate(words):
                yield {
                    'type': 'token',
                    'content': word + (' ' if i < len(words) - 1 else ''),
                    'index': i
                }
            
            processing_time = time.time() - start_time
            
            # Save to database
            db_query = OracleQueryModel(
                user_id=user_id,
                question=query.question,
                answer=full_answer,
                context=query.context,
                ai_provider=result["provider"],
                processing_time=processing_time,
                tokens_used=result.get("tokens_used")
            )
            db.add(db_query)
            db.commit()
            db.refresh(db_query)
            
            # Send completion event
            yield {
                'type': 'done',
                'id': db_query.id,
                'provider': result["provider"],
                'processing_time': processing_time,
                'tokens_used': result.get("tokens_used"),
                'sources': result.get("sources")
            }
            
        except Exception as e:
            logger.error(f"Oracle stream query failed: {str(e)}")
            yield {
                'type': 'error',
                'message': str(e)
            }
    
    @staticmethod
    def get_history(
        db: Session,
        user_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List[OracleHistoryItem]:
        """Get Oracle query history"""
        query = db.query(OracleQueryModel)
        
        if user_id:
            query = query.filter(OracleQueryModel.user_id == user_id)
        
        queries = query.order_by(desc(OracleQueryModel.created_at)).limit(limit).all()
        
        return [
            OracleHistoryItem(
                id=q.id,
                question=q.question,
                answer=q.answer,
                ai_provider=q.ai_provider,
                created_at=q.created_at,
                processing_time=q.processing_time
            )
            for q in queries
        ]
    
    @staticmethod
    async def analyze_forum(
        db: Session,
        ai_provider: str = "kiro"
    ) -> ForumAnalysisResponse:
        """Analyze forum messages and predict job loss"""
        try:
            # Get all forum topics and posts
            topics = db.query(Topic).all()
            posts = db.query(Post).all()
            
            # Build context from forum data
            forum_content = []
            for topic in topics:
                forum_content.append(f"Sujet: {topic.title}")
                topic_posts = [p for p in posts if p.topic_id == topic.id]
                for post in topic_posts:
                    forum_content.append(f"- {post.content[:200]}")
            
            context = "\n".join(forum_content[:100])  # Limit context size
            
            # Construct analysis question
            question = """
            Analyse tous les messages du forum et réponds aux questions suivantes:
            
            1. Fais un résumé des discussions principales
            2. Estime le pourcentage d'emplois qui seront supprimés à cause de l'IA dans:
               - 5 ans
               - 10 ans
               - 20 ans
            3. Identifie les sujets clés discutés
            4. Évalue le sentiment général (positif, neutre, négatif)
            5. Donne un niveau de confiance pour tes prédictions (0-1)
            
            Réponds au format JSON avec les clés: summary, job_loss_5y, job_loss_10y, job_loss_20y, 
            key_topics (liste), sentiment, confidence
            """
            
            # Query AI
            provider = get_ai_provider(ai_provider)
            result = await provider.query(
                question=question,
                context=context,
                temperature=0.3,  # Lower temperature for more factual analysis
                max_tokens=3000
            )
            
            # Parse JSON response
            try:
                # Try to extract JSON from response
                answer = result["answer"]
                if "```json" in answer:
                    answer = answer.split("```json")[1].split("```")[0]
                elif "```" in answer:
                    answer = answer.split("```")[1].split("```")[0]
                
                data = json.loads(answer.strip())
                
                return ForumAnalysisResponse(
                    summary=data.get("summary", "Analyse non disponible"),
                    job_loss_prediction_5y=float(data.get("job_loss_5y", 0)),
                    job_loss_prediction_10y=float(data.get("job_loss_10y", 0)),
                    job_loss_prediction_20y=float(data.get("job_loss_20y", 0)),
                    key_topics=data.get("key_topics", []),
                    sentiment=data.get("sentiment", "neutre"),
                    confidence=float(data.get("confidence", 0.5))
                )
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error(f"Failed to parse AI response: {str(e)}")
                # Return default response
                return ForumAnalysisResponse(
                    summary=result["answer"],
                    job_loss_prediction_5y=0.0,
                    job_loss_prediction_10y=0.0,
                    job_loss_prediction_20y=0.0,
                    key_topics=[],
                    sentiment="neutre",
                    confidence=0.0
                )
                
        except Exception as e:
            logger.error(f"Forum analysis failed: {str(e)}")
            raise
