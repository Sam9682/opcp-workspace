"""AI Provider implementations for Oracle"""
import asyncio
import time
import json
import re
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import httpx
from app.config import settings
from app.logging_config import logger


# Instruction système du pipeline RAG OPCP Companion. Le placeholder {context}
# reçoit les fragments récupérés dans pgvector, assemblés par _build_context.
SYSTEM_PROMPT = """Tu es OPCP Companion, un assistant documentaire qui répond aux questions en t'appuyant exclusivement sur le contexte fourni ci-dessous.

Consignes :
- Réponds en français, de manière claire et concise.
- Fonde ta réponse uniquement sur le contexte fourni. N'invente rien.
- Si le contexte ne contient pas l'information nécessaire, indique-le honnêtement.
- Cite les éléments pertinents du contexte lorsque c'est utile.

Contexte :
{context}"""


# Chemin du fichier de contexte métier injecté dans le fournisseur Shai,
# relatif à la racine du projet (même convention que app.config, ex. DOCS_SEED_DIR).
SHAI_SKILL_CONTEXT_PATH = "conf/shai_context.md"


def _load_shai_skill_context() -> Optional[str]:
    """Lit le contexte métier Shai depuis SHAI_SKILL_CONTEXT_PATH.

    Retourne le contenu (sans espaces superflus) en cas de succès, sinon None.
    Un fichier manquant ou illisible n'interrompt pas la requête : un
    avertissement est journalisé et None est retourné.
    """
    try:
        with open(SHAI_SKILL_CONTEXT_PATH, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return content or None
    except OSError as e:
        logger.warning(
            f"Contexte métier Shai indisponible ({SHAI_SKILL_CONTEXT_PATH}) : "
            f"{str(e)}. Poursuite sans le contexte métier."
        )
        return None


def _build_shai_prompt(
    skill_context: Optional[str],
    context: Optional[str],
    question: str,
) -> str:
    """Assemble le prompt Shai : contexte métier (optionnel) + contexte existant
    (optionnel) + question. Combine sans remplacer le contexte existant."""
    parts = []
    if skill_context:
        parts.append(skill_context)
    if context:
        parts.append(f"Contexte: {context}")
    parts.append(f"Question: {question}")
    return "\n\n".join(parts)


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape codes from text"""
    # Pattern to match ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


class AIProvider(ABC):
    """Base class for AI providers"""
    
    @abstractmethod
    async def query(
        self,
        question: str,
        context: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """Query the AI provider"""
        pass


class KiroAIProvider(AIProvider):
    """Kiro CLI AI Provider - Uses local Ubuntu session with kiro-cli"""
    
    async def query(
        self,
        question: str,
        context: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """Query Kiro AI via CLI"""
        start_time = time.time()

        try:
            # Construct the prompt
            prompt = question
            if context:
                prompt = f"Contexte: {context}\n\nQuestion: {question}"

            # Set up environment with proper PATH
            import os
            env = os.environ.copy()
            # Ensure PATH includes Kiro CLI installation locations
            kiro_paths = [
                "/root/.local/bin",
                "/home/ubuntu/.local/bin",
                os.path.expanduser("~/.local/bin")
            ]
            current_path = env.get('PATH', '')
            env['PATH'] = ':'.join(kiro_paths + [current_path])

            # Check if kiro-cli is authenticated, if not skip authentication for now
            # The CLI should work without authentication for basic queries
            
            # Execute kiro-cli chat command with timeout
            process = await asyncio.create_subprocess_exec(
                'kiro-cli', 'chat', '--no-interactive', '--trust-all-tools', prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
            except asyncio.TimeoutError:
                process.kill()
                logger.error("Kiro CLI timeout after 60 seconds")
                raise Exception("Kiro CLI timeout - la requête a pris trop de temps")

            output = stdout.decode().strip()
            error_output = stderr.decode().strip() if stderr else ""

            # Check for authentication errors and provide helpful message
            if "Failed to open browser" in output or "Failed to open browser" in error_output:
                logger.warning("Kiro CLI authentication issue - service may require manual authentication")
                raise Exception("Kiro CLI nécessite une authentification. Veuillez utiliser un autre fournisseur d'IA (OpenAI ou Shai) ou configurer l'authentification manuellement.")

            if process.returncode != 0:
                error_msg = error_output or output or "Unknown error"
                logger.error(f"Kiro CLI error: {error_msg}")

                # Check if kiro-cli is not installed
                if "not found" in error_msg or "command not found" in error_msg or "No such file or directory" in error_msg:
                    raise Exception("Kiro CLI n'est pas installé. Veuillez reconstruire le container Docker ou utiliser un autre fournisseur d'IA.")

                raise Exception(f"Kiro CLI a échoué: {error_msg}")

            # Strip ANSI escape codes only
            answer = strip_ansi_codes(output)

            if not answer:
                raise Exception("Kiro CLI n'a pas retourné de réponse")

            processing_time = time.time() - start_time

            return {
                "answer": answer,
                "processing_time": processing_time,
                "tokens_used": len(answer.split()),  # Approximation
                "provider": "kiro"
            }

        except Exception as e:
            logger.error(f"Kiro AI query failed: {str(e)}")
            raise


class ShaiAIProvider(AIProvider):
    """Shai CLI AI Provider - Uses local Ubuntu session with shai CLI"""
    
    async def query(
        self,
        question: str,
        context: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """Query Shai AI via CLI"""
        start_time = time.time()

        try:
            skill_context = _load_shai_skill_context()
            prompt = _build_shai_prompt(skill_context, context, question)

            import os
            env = os.environ.copy()
            shai_paths = [
                "/root/.local/bin",
                "/home/ubuntu/.local/bin",
                os.path.expanduser("~/.local/bin")
            ]
            current_path = env.get('PATH', '')
            env['PATH'] = ':'.join(shai_paths + [current_path])

            process = await asyncio.create_subprocess_exec(
                'shai', prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
            except asyncio.TimeoutError:
                process.kill()
                logger.error("Shai CLI timeout after 60 seconds")
                raise Exception("Shai CLI timeout - la requête a pris trop de temps")

            output = stdout.decode().strip()
            error_output = stderr.decode().strip() if stderr else ""

            if process.returncode != 0:
                error_msg = error_output or output or "Unknown error"
                logger.error(f"Shai CLI error: {error_msg}")

                if "not found" in error_msg or "command not found" in error_msg or "No such file or directory" in error_msg:
                    raise Exception("Shai CLI n'est pas installé. Veuillez reconstruire le container Docker ou utiliser un autre fournisseur d'IA.")

                raise Exception(f"Shai CLI a échoué: {error_msg}")

            answer = strip_ansi_codes(output)
            answer = answer.strip()
            
            lines = answer.split('\n')
            cleaned_lines = []
            skip_box = False
            
            for line in lines:
                if '╭' in line or '╰' in line or '│' in line:
                    skip_box = True
                    continue
                if skip_box and ('─' in line or not line.strip()):
                    continue
                skip_box = False
                
                if '▸ Time:' in line or line.strip().startswith('Time:'):
                    continue
                    
                cleaned_lines.append(line)
            
            answer = '\n'.join(cleaned_lines).strip()

            if not answer:
                raise Exception("Shai CLI n'a pas retourné de réponse")

            processing_time = time.time() - start_time

            return {
                "answer": answer,
                "processing_time": processing_time,
                "tokens_used": len(answer.split()),
                "provider": "shai"
            }

        except Exception as e:
            logger.error(f"Shai AI query failed: {str(e)}")
            raise


class OpenAIProvider(AIProvider):
    """OpenAI Provider - Fallback option"""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.model = settings.OPENAI_MODEL
    
    async def query(
        self,
        question: str,
        context: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """Query OpenAI API"""
        start_time = time.time()
        
        if not self.api_key:
            raise Exception("OPENAI_API_KEY n'est pas configurée. Veuillez ajouter OPENAI_API_KEY dans le fichier .env")
        
        try:
            messages = []
            if context:
                messages.append({"role": "system", "content": context})
            messages.append({"role": "user", "content": question})
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    },
                    timeout=60.0
                )
                
                response.raise_for_status()
                data = response.json()
                
                answer = data["choices"][0]["message"]["content"]
                tokens_used = data["usage"]["total_tokens"]
                
                processing_time = time.time() - start_time
                
                return {
                    "answer": answer,
                    "processing_time": processing_time,
                    "tokens_used": tokens_used,
                    "provider": "openai"
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI HTTP error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Erreur OpenAI: {e.response.status_code} - Vérifiez votre clé API")
        except Exception as e:
            logger.error(f"OpenAI query failed: {str(e)}")
            raise


class OpcpCompanionProvider(AIProvider):
    """Fournisseur RAG : embedding OVH + recherche pgvector + génération LLM OVH.

    Pipeline autonome porté depuis rag_query.py (dépôt opcp-ai-chatbot), réécrit
    en classe conforme à l'interface AIProvider. Aucune importation d'exécution du
    dépôt opcp-ai-chatbot : toute la configuration provient de app.config.settings.
    """

    def __init__(self):
        # Embedding (OVH AI Endpoints)
        self.embed_endpoint = settings.OVH_AI_ENDPOINT
        self.embed_token = settings.OVH_AI_TOKEN
        self.embedding_model = settings.EMBEDDING_MODEL
        self.embedding_dim = settings.EMBEDDING_DIM
        # Génération (LLM OVH) — retombe sur les endpoints/token d'embedding si vides
        self.llm_endpoint = settings.LLM_ENDPOINT or settings.OVH_AI_ENDPOINT
        self.llm_token = settings.LLM_TOKEN or settings.OVH_AI_TOKEN
        self.llm_model = settings.LLM_MODEL
        # Recherche pgvector
        self.table_name = settings.TABLE_NAME
        self.top_k = 3

    # --- Clients ---
    def _get_embed_client(self):
        """Client OpenAI pointant vers les OVH AI Endpoints (embeddings)."""
        from openai import OpenAI
        return OpenAI(base_url=self.embed_endpoint, api_key=self.embed_token)

    def _get_llm_client(self):
        """Client OpenAI pointant vers l'endpoint LLM (génération)."""
        from openai import OpenAI
        return OpenAI(base_url=self.llm_endpoint, api_key=self.llm_token)

    def _get_pg_connection(self):
        """Connexion Postgres pgvector via les variables PG_* de la configuration."""
        import psycopg2
        return psycopg2.connect(
            host=settings.PG_HOST,
            port=settings.PG_PORT,
            dbname=settings.PG_DB,
            user=settings.PG_USER,
            password=settings.PG_PASSWORD,
        )

    def ensure_vector_store(self, conn) -> None:
        """Provisionne le magasin vectoriel de façon idempotente.

        Sur une connexion psycopg2 déjà ouverte vers la base vectorielle, crée
        l'extension pgvector et la table de recherche si elles sont absentes,
        puis valide (commit) afin que le DDL soit durable avant la recherche.
        L'opération est sans effet lorsque l'extension et la table existent déjà.

        Le nom de table (self.table_name) et la dimension (self.embedding_dim)
        proviennent exclusivement de la configuration (jamais d'une entrée
        utilisateur), donc leur interpolation dans le SQL est sûre — même motif
        que celui déjà employé par _search.
        """
        create_table_sql = (
            f"CREATE TABLE IF NOT EXISTS {self.table_name} ("
            "title text, "
            "file_path text, "
            "chunk_index integer, "
            "content text, "
            f"embedding vector({self.embedding_dim})"
            ")"
        )

        cursor = conn.cursor()
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cursor.execute(create_table_sql)
        finally:
            cursor.close()

        conn.commit()

    def _embed_query(self, client, query: str) -> list:
        """Calcule le vecteur d'embedding de la question via les OVH AI Endpoints.

        `dimensions` n'est transmis que si embedding_dim < 4096 (certains modèles
        rejettent le paramètre à la dimension native maximale). La longueur du
        vecteur retourné est validée contre embedding_dim.
        """
        kwargs = {"model": self.embedding_model, "input": [query]}
        if self.embedding_dim < 4096:
            kwargs["dimensions"] = self.embedding_dim
        response = client.embeddings.create(**kwargs)
        vector = response.data[0].embedding
        if len(vector) != self.embedding_dim:
            raise Exception(
                f"Dimension d'embedding inattendue : {len(vector)} "
                f"(attendu {self.embedding_dim})"
            )
        return vector

    # --- Étapes pures / semi-pures ---
    def _search(self, conn, query_vector: list, top_k: int) -> list:
        """Recherche cosinus des top_k fragments dans pgvector.

        Le nom de table provient de la configuration (self.table_name, jamais
        d'une entrée utilisateur), donc son interpolation dans le SQL est sûre.
        Les valeurs (vecteur, vecteur, top_k) restent paramétrées via %s.
        """
        # Sérialisation du vecteur au format attendu par pgvector : "[v1,v2,...]"
        vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

        sql = (
            "SELECT title, file_path, chunk_index, content, "
            "1 - (embedding <=> %s::vector) AS similarity "
            f"FROM {self.table_name} "
            "ORDER BY embedding <=> %s::vector "
            "LIMIT %s;"
        )

        cursor = conn.cursor()
        try:
            cursor.execute(sql, (vector_str, vector_str, top_k))
            rows = cursor.fetchall()
        finally:
            cursor.close()

        chunks = []
        for row in rows:
            title, file_path, chunk_index, content, similarity = row
            chunks.append({
                "title": title,
                "file_path": file_path,
                "chunk_index": chunk_index,
                "content": content,
                "similarity": round(float(similarity), 4),
            })
        return chunks

    def _chunks_to_sources(self, chunks: list) -> list:
        """Dérive la liste des sources (title, file_path, similarity) des chunks."""
        return [
            {
                "title": chunk["title"],
                "file_path": chunk["file_path"],
                "similarity": chunk["similarity"],
            }
            for chunk in chunks
        ]

    def _build_context(self, chunks: list) -> str:
        """Assemble la chaîne de contexte injectée dans le SYSTEM_PROMPT.

        Chaque chunk est formaté `[{title} — chunk {chunk_index}]\n{content}` et
        les fragments sont joints par un séparateur `\n\n---\n\n`.
        """
        return "\n\n---\n\n".join(
            f"[{chunk['title']} — chunk {chunk['chunk_index']}]\n{chunk['content']}"
            for chunk in chunks
        )

    async def query(
        self,
        question: str,
        context: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """Exécute le pipeline RAG : embedding OVH → recherche pgvector → génération LLM OVH.

        Les appels bloquants (client OpenAI synchrone, psycopg2) sont déportés
        hors de la boucle événementielle via asyncio.to_thread. Les erreurs sont
        journalisées (logger.error) puis relancées avec un message français ne
        divulguant aucun secret.
        """
        start_time = time.time()

        # Garde de token : refuser tôt si une clé requise est absente (Req 5.3).
        if not self.embed_token:
            raise Exception(
                "Configuration manquante : OVH_AI_TOKEN est requis pour l'embedding OPCP Companion."
            )
        if not self.llm_token:
            raise Exception(
                "Configuration manquante : LLM_TOKEN (ou OVH_AI_TOKEN de repli) est requis pour la génération OPCP Companion."
            )

        # 1. Embedding de la question (appel OVH) — Req 5.2
        try:
            embed_client = self._get_embed_client()
            query_vector = await asyncio.to_thread(
                self._embed_query, embed_client, question
            )
        except Exception as e:
            logger.error(f"OPCP Companion embedding failed: {str(e)}")
            raise Exception(
                f"Échec de l'appel OVH (embedding) : impossible de calculer le vecteur de la question ({str(e)})"
            )

        # 2. Récupération des fragments dans pgvector — Req 5.1
        conn = None
        try:
            conn = await asyncio.to_thread(self._get_pg_connection)
            # Provisionnement idempotent du magasin vectoriel avant la recherche
            # (extension pgvector + table de recherche). Sans effet si déjà en
            # place. En cas d'échec, on lève un message clair nommant la table
            # cible et la base vectorielle, sans divulguer PG_PASSWORD. Req 2.1-2.3
            try:
                await asyncio.to_thread(self.ensure_vector_store, conn)
            except Exception as provisioning_error:
                logger.error(
                    f"OPCP Companion vector store provisioning failed: {str(provisioning_error)}"
                )
                raise Exception(
                    f"Impossible de provisionner la table « {self.table_name} » "
                    f"dans la base de données vectorielle "
                    f"« {settings.PG_DB} » sur {settings.PG_HOST}:{settings.PG_PORT} "
                    f"({str(provisioning_error)})"
                )
            chunks = await asyncio.to_thread(
                self._search, conn, query_vector, self.top_k
            )
        except Exception as e:
            logger.error(f"OPCP Companion pgvector search failed: {str(e)}")
            raise Exception(
                f"Échec de la connexion ou de la recherche dans la base de données vectorielle ({str(e)})"
            )
        finally:
            if conn is not None:
                try:
                    await asyncio.to_thread(conn.close)
                except Exception:
                    pass

        # 3. Assemblage du contexte et génération de la réponse (appel OVH) — Req 5.2
        context_str = self._build_context(chunks)
        try:
            llm_client = self._get_llm_client()
            response = await asyncio.to_thread(
                lambda: llm_client.responses.create(
                    model=self.llm_model,
                    instructions=SYSTEM_PROMPT.format(context=context_str),
                    input=question,
                    store=False,
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )
            )
        except Exception as e:
            logger.error(f"OPCP Companion generation failed: {str(e)}")
            raise Exception(
                f"Échec de l'appel OVH (génération) : impossible de produire la réponse ({str(e)})"
            )

        answer = response.output_text.strip()

        # tokens_used depuis l'usage rapporté, sinon approximation par mots.
        tokens_used = len(answer.split())
        usage = getattr(response, "usage", None)
        if usage is not None:
            total = getattr(usage, "total_tokens", None)
            if total is not None:
                tokens_used = total

        return {
            "answer": answer,
            "processing_time": max(0.0, time.time() - start_time),
            "tokens_used": tokens_used,
            "provider": "opcp_companion",
            "sources": self._chunks_to_sources(chunks),
        }


def get_ai_provider(provider_name: str) -> AIProvider:
    """Factory function to get AI provider instance"""
    providers = {
        "kiro": KiroAIProvider,
        "shai": ShaiAIProvider,
        "openai": OpenAIProvider,
        "opcp_companion": OpcpCompanionProvider
    }
    
    provider_class = providers.get(provider_name)
    if not provider_class:
        raise ValueError(f"Unknown AI provider: {provider_name}")
    
    return provider_class()
