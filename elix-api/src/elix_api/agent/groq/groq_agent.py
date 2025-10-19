import json
import uuid
from datetime import datetime 
from typing import Any, Dict, List, Optional 
import instructor 
import opik
from groq import Groq
from loguru import logger
from opik import Attachment, opik_context

from elix_api import tools
from elix_api.agent.base_agent import BaseAgent
from elix_api.agent.groq.groq_tool import transform_tool_definition
from elix_api.agent.memory import Memory, MemoryRecord
from elix_api.config import get_settings
from elix_api.models import (
    AssistantMessageResponse,
    GeneralResponseModel,
    RoutingResponseModel,
    VideoClipResponseModel,
)

logger.bind(name="GroqAgent")

settings = get_settings()

class GroqAgent(BaseAgent): 
    def __init__(self, name: str, mcp_server: str, memory: Memory = None, disable_tools: list = None):
        super().__init__(name, mcp_server, memory, disable_tools) 
        self.client = Groq(api_key=settings.GROQ_API_KEY) 
        self.instructor_client = instructor.from_groq(self.client, mode=instructor.Mode.JSON) 
        self.thread_id = str(uuid.uuid4()) 

    async def _get_tools(self) -> List[Dict[str, Any]]: 
        tools = await self.discover_tools()
        return [transform_tool_definition(tool) for tool in tools] 
    
    @opik.track(name="build_-chat-history") 
    def _build_chat_history(self, system_prompt: str, user_message: str, 
    image_base64: Optional[str]=None, n: int = settings.AGENT_MEMORY_SIZE
    ) -> List[Dict[str, Any]]:
       history = [{"role": "system", "content": system_prompt}] 