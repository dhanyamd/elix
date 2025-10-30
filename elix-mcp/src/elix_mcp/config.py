from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        default="elix-mcp",
        description="Project name for Comet ML and Opik tracking.",
    )

    # --- Memory Configuration ---
    AGENT_MEMORY_SIZE: int = 20

    # --- MCP Configuration ---
    MCP_SERVER: str = "http://elix-mcp:9090/mcp"

    # --- Disable Nest Asyncio ---
    DISABLE_NEST_ASYNCIO: bool = True

    # --- Video Processing Configuration ---
    SPLIT_FRAMES_COUNT: int = 10
    AUDIO_CHUNK_LENGTH: int = 10
    AUDIO_OVERLAP_SECONDS: float = 2.0
    AUDIO_MIN_CHUNK_DURATION_SECONDS: float = 1.0
    AUDIO_TRANSCRIPT_MODEL: str = "whisper-1"
    TRANSCRIPT_SIMILARITY_EMBD_MODEL: str = "text-embedding-3-small"
    IMAGE_RESIZE_WIDTH: int = 224
    IMAGE_RESIZE_HEIGHT: int = 224
    IMAGE_SIMILARITY_EMBD_MODEL: str = "ViT-B/32"
    CAPTION_MODEL_PROMPT: str = "Describe this image in detail."
    IMAGE_CAPTION_MODEL: str = "blip2-image-captioning-large"
    CAPTION_SIMILARITY_EMBD_MODEL: str = "text-embedding-3-small"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get the application settings.

    Returns:
        Settings: The application settings.
    """
    return Settings()