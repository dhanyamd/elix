from abc import ABC, abstractmethod 

from fastmcp import Client
from loguru import logger 

from kubrick_api.agent.memory import Memory 

class BaseAgent(ABC): 
    """
    Base class for all agents. 
    """
    def __init__(
        self, name: str, mcp_server: str, memory: Memory = None, disable_tools: list = None
    ): 
        self.name = name 
        self.mcp_client = Client(mcp_server) 
        self.memory = memory if memory else Memory(name) 
        self.disable_tools = disable_tools if disable_tools else [] 

        self.tools = None
        self.routing_system_prompt = None
        self.tool_use_system_prompt = None
        self.general_system_prompt = None 
    
    async def setup(self): 
        """ Intialize async components of the agent""" 
        async with self.mcp_client as _: 
            self.tools = await self._get_tools()
            self.routing_system_prompt = await self._get_routing_system_prompt()
            self.tool_use_system_prompt = await self._get_tool_use_system_prompt()
            self.general_system_prompt = await self._get_general_system_prompt()

