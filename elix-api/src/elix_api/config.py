import os
from functools import lru_cache
from loguru import logger
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_default_mcp_server() -> str:
    """Get the default MCP server URL based on environment."""
    # Check if we're in Docker by looking for .dockerenv file
    in_docker = os.path.exists("/.dockerenv")
    
    if in_docker:
        return "http://elix-mcp:9090/mcp/"
    else:
        # Running locally, use localhost
        return "http://localhost:9090/mcp/"


def _is_in_docker() -> bool:
    """Check if we're running inside Docker."""
    return os.path.exists("/.dockerenv")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_file_encoding="utf-8")

    # --- GROQ Configuration ---
    GROQ_API_KEY: str 
    GROQ_ROUTING_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    GROQ_TOOL_USE_MODEL: str = "meta-llama/llama-4-maverick-17b-128e-instruct"
    GROQ_IMAGE_MODEL: str = "meta-llama/llama-4-maverick-17b-128e-instruct"
    GROQ_GENERAL_MODEL: str = "meta-llama/llama-4-maverick-17b-128e-instruct"

    # --- Comet ML & Opik Configuration ---
    OPIK_API_KEY: str | None = Field(default=None, description="API key for Comet ML and Opik services.")
    OPIK_WORKSPACE: str = "default"
    OPIK_PROJECT: str = Field(
        default="elix-api",
        description="Project name for Comet ML and Opik tracking.",
    )

    # --- Memory Configuration ---
    AGENT_MEMORY_SIZE: int = 20

    # --- MCP Configuration ---
    # Automatically detects Docker vs local environment, but can be overridden with environment variable
    MCP_SERVER: str = Field(
        default_factory=_get_default_mcp_server,
        description="MCP server URL. Auto-detects Docker vs local environment, or set MCP_SERVER env var to override."
    )
    
    @field_validator("MCP_SERVER", mode="before")
    @classmethod
    def validate_mcp_server(cls, v: str) -> str:
        """
        Validate and auto-correct MCP server URL based on environment.
        If MCP_SERVER is set to use Docker hostname (elix-mcp) but we're not in Docker,
        automatically switch to localhost.
        """
        if v is None:
            return v
        
        if isinstance(v, str) and "elix-mcp" in v:
            if not _is_in_docker():
                # Running locally but MCP_SERVER is set to Docker hostname
                # Auto-correct to localhost
                corrected = v.replace("elix-mcp", "localhost")
                logger.warning(
                    f"MCP_SERVER was set to '{v}' but running outside Docker. "
                    f"Auto-correcting to '{corrected}'. "
                    f"To suppress this warning, set MCP_SERVER={corrected} in your environment."
                )
                return corrected
        return v

    # --- Disable Nest Asyncio ---
    DISABLE_NEST_ASYNCIO: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get the application settings.

    Returns:
        Settings: The application settings.
    """
    return Settings()