"""
Application settings using Pydantic Settings.
All values can be overridden via environment variables or .env file.
"""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

DEFAULT_JWT_SECRET = "change-me-in-production-use-a-real-secret-key"
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    # ── Environment ──────────────────────────────────────────────────────────
    ENV: str = Field(default="development", description="development or production")

    # ── Auth ─────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(default=DEFAULT_JWT_SECRET)
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRE_MINUTES: int = Field(default=480)  # 8 hours

    # ── Database ──────────────────────────────────────────────────────────────
    DB_TYPE: str = Field(default="sqlite", description="sqlite or mysql")
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=3306)
    DB_USER: str = Field(default="root")
    DB_PASSWORD: str = Field(default="")
    DB_NAME: str = Field(default="reporting_agent")
    SQLITE_PATH: str = Field(default="data/reporting_agent.db")

    # ── OpenAI ────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = Field(default="gpt-4o")
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = Field(default="data/chroma")

    # ── RAG ───────────────────────────────────────────────────────────────────
    CHUNK_SIZE: int = Field(default=500)
    CHUNK_OVERLAP: int = Field(default=100)
    TOP_K_RESULTS: int = Field(default=5)

    # ── Report generation ─────────────────────────────────────────────────────
    MAX_EVALUATOR_ITERATIONS: int = Field(default=3)
    WRITER_STRATEGY: str = Field(default="few_shot", description="zero_shot | few_shot | cot")

    # ── Email delivery ────────────────────────────────────────────────────────
    SMTP_HOST: str = Field(default="")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(default="")
    SMTP_PASSWORD: str = Field(default="")
    REPORT_RECIPIENTS: str = Field(default="", description="Comma-separated email list")

    # ── WhatsApp / Twilio ──────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = Field(default="")
    TWILIO_AUTH_TOKEN: str = Field(default="")
    WHATSAPP_FROM: str = Field(default="", description="Twilio WhatsApp sender, e.g. whatsapp:+14155238886")
    WHATSAPP_RECIPIENTS: str = Field(default="", description="Comma-separated whatsapp:+... numbers")

    # ── Scheduler ────────────────────────────────────────────────────────────
    SCHEDULER_ENABLED: bool = Field(default=False, description="Enable monthly APScheduler")
    SCHEDULER_HOUR: int = Field(default=8, description="Hour to run monthly job (0-23)")
    SCHEDULER_MINUTE: int = Field(default=0, description="Minute to run monthly job (0-59)")

    # ── LangSmith observability ───────────────────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = Field(default=False)
    LANGCHAIN_API_KEY: str = Field(default="")
    LANGCHAIN_PROJECT: str = Field(default="proactive-reporting-agent")

    @model_validator(mode="after")
    def _require_real_jwt_secret_in_production(self) -> "Settings":
        """Refuse to start in production with the shipped placeholder secret.

        The default lives in a public repo, so anyone could forge tokens for a
        deployment that never overrode it.
        """
        if self.ENV.strip().lower() not in ("production", "prod"):
            return self
        if self.JWT_SECRET_KEY == DEFAULT_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET_KEY is still the default placeholder. Set it to a real "
                "secret before running with ENV=production, e.g. "
                "`python -c \"import secrets; print(secrets.token_urlsafe(32))\"`."
            )
        if len(self.JWT_SECRET_KEY) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_LENGTH} characters "
                f"when ENV=production (got {len(self.JWT_SECRET_KEY)})."
            )
        return self

    @property
    def database_url(self) -> str:
        """Build SQLAlchemy database URL from settings."""
        if self.DB_TYPE == "sqlite":
            return f"sqlite:///{self.SQLITE_PATH}"
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def recipients_list(self) -> list[str]:
        """Parse comma-separated recipients into a list."""
        if not self.REPORT_RECIPIENTS:
            return []
        return [r.strip() for r in self.REPORT_RECIPIENTS.split(",") if r.strip()]

    @property
    def whatsapp_recipients_list(self) -> list[str]:
        """Parse comma-separated WhatsApp recipients into a list."""
        if not self.WHATSAPP_RECIPIENTS:
            return []
        return [r.strip() for r in self.WHATSAPP_RECIPIENTS.split(",") if r.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Module-level singleton — import this everywhere
settings = Settings()
