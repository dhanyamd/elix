from abc import ABC, abstractmethod

from fastmcp import Client
from loguru import logger

from elix_api.agent.memory import Memory

class BaseAgenr(ABC): 
    """Base class for all agents""" 
    def __init__(self, name: str, mcp_server: str, memory: Memory=None, disable_tools: list=None): 
        self.name = name
        self.mcp_client = Client(mcp_server) 
        self.memory = memory if memory else Memory(name) 
        self.disable_tools = disable_tools if disable_tools else None 

        self.tools = None
        self.routing_system_prompt = None 
        self.tool_use_system_prompt = None 
        self.general_system_prompt = None 

    async def setup(self):
        """Initialize async components of the agent."""
        async with self.mcp_client as _:
            self.tools = await self._get_tools()
            self.routing_system_prompt = await self._get_routing_system_prompt()
            self.tool_use_system_prompt = await self._get_tool_use_system_prompt()
            self.general_system_prompt = await self._get_general_system_prompt()
    async def _get_routing_system_prompt(self) -> str:
        """Get the routing system prompt."""
        logger.info("Getting routing system prompt")
        mcp_prompt = await self.mcp_client.get_prompt("routing_system_prompt")
        return mcp_prompt.messages[0].content.text
    
    async def _get_tool_use_system_prompt(self) -> str:
        """Get the tool use system prompt."""
        logger.info("Getting tool use system prompt")
        mcp_prompt = await self.mcp_client.get_prompt("tool_use_system_prompt")
        return mcp_prompt.messages[0].content.text
    
    async def _get_general_system_prompt(self) -> str:
        """Get the general system prompt."""
        logger.info("Getting general system prompt")
        mcp_prompt = await self.mcp_client.get_prompt("general_system_prompt")
        return mcp_prompt.messages[0].content.text
    def reset_memory(self):
        self.memory.reset_memory()
        
    def filter_active_tools(self, tools: list) -> list:
        """
        Filter the list of tools to only include the active tools.
        """
        return [tool for tool in tools if tool.name not in self.disable_tools]
