"""Application configuration using Pydantic settings"""
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database
    DATABASE_URL: str = "postgresql://shai_user:shai_password@postgres:5432/shai_db"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database field encryption (optional, off by default).
    # When set, this is a ready-to-use Fernet key (as produced by
    # app.security.encryption.derive_key from the admin password key) that
    # seeds the in-memory KeyProvider at startup so encrypted columns can be
    # decrypted without an admin re-entering the key after a restart. Empty
    # means the key must be supplied at runtime via the admin API.
    DB_ENCRYPTION_KEY: str = ""
    
    # Email (optional for development)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@opcp-psmc.com"
    
    # Payment (optional for development)
    STRIPE_API_KEY: str = "sk_test_dummy_key"
    STRIPE_WEBHOOK_SECRET: str = "whsec_dummy_secret"
    PAYPAL_CLIENT_ID: str = "dummy_client_id"
    PAYPAL_CLIENT_SECRET: str = "dummy_client_secret"
    PAYPAL_MODE: str = "sandbox"
    
    # Application
    APP_NAME: str = "AI-SHAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "https://opcp-psmc.com"
    
    # File Storage
    UPLOAD_DIR: str = "./storage/uploads"
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    DOCS_SEED_DIR: str = "./docs/to_publish"  # repository docs/ folder, baked into the image (resolves to /app/docs in the container)
    
    # Membership
    ANNUAL_MEMBERSHIP_FEE: float = 50.00
    
    # Oracle AI Configuration (optional)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4"
    SHAI_API_KEY: str = ""
    SHAI_API_URL: str = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1"  # Use EU endpoint to avoid redirect
    SHAI_MODEL: str = "Qwen2.5-Coder-32B-Instruct"  # OpenAI-compatible model served by the OVH endpoint
    
    # OPCP Companion (RAG) Configuration
    # OVH AI Endpoints for embeddings (LLM falls back to these when LLM_* is empty)
    OVH_AI_ENDPOINT: str = ""
    OVH_AI_TOKEN: str = ""
    EMBEDDING_MODEL: str = "Qwen3-Embedding-8B"
    EMBEDDING_DIM: int = 4096
    # LLM generation endpoint (falls back to OVH_AI_ENDPOINT/OVH_AI_TOKEN when empty)
    LLM_ENDPOINT: str = ""
    LLM_TOKEN: str = ""
    LLM_MODEL: str = "Qwen3-Embedding-8B"
    # pgvector Postgres connection (explicit PG_* vars, aligned with DATABASE_URL: shai_db @ postgres)
    PG_HOST: str = "postgres"
    PG_PORT: int = 5432
    PG_DB: str = "shai_db"
    PG_USER: str = "shai_user"
    PG_PASSWORD: str = "shai_password"
    TABLE_NAME: str = "md_embeddings"
    
    # OpenStack forward proxy (empty means no proxy configured -> direct connection)
    # Accepts the explicit app var plus the standard lowercase/uppercase proxy env vars
    OPENSTACK_HTTPS_PROXY: str = Field(
        default="",
        validation_alias=AliasChoices(
            "OPENSTACK_HTTPS_PROXY",
            "https_proxy",
            "http_proxy",
            "HTTPS_PROXY",
            "HTTP_PROXY",
        ),
    )
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"  # Ignore extra environment variables not defined in the model
    }
    
    @property
    def cors_origins(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]


# Global settings instance
settings = Settings()
