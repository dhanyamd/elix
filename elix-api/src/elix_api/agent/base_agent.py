from abc import ABC, abstractmethod 

from fastmcp import Client
from loguru import logger 

from elix_api.agent.memory import Memory
from elix_api.mcp_utils import retry_mcp_connection 

class BaseAgent(ABC): 
    """
    Base class for all agents. 
    """
    def __init__(
        self, name: str, mcp_server: str, memory: Memory = None, disable_tools: list = None
    ): 
        self.name = name 
        self.mcp_server = mcp_server
        self.mcp_client = Client(mcp_server) 
        self.memory = memory if memory else Memory(name) 
        self.disable_tools = disable_tools if disable_tools else [] 

        self.tools = None
        self.routing_system_prompt = None
        self.tool_use_system_prompt = None
        self.general_system_prompt = None
        self._is_setup = False
    
    async def setup(self): 
        """ Initialize async components of the agent (idempotent)""" 
        if self._is_setup:
            return
        
        # Use retry logic for initial setup
        async def _setup_with_retry():
            async with self.mcp_client as _: 
                self.tools = await self._get_tools()
                self.routing_system_prompt = await self._get_routing_system_prompt()
                self.tool_use_system_prompt = await self._get_tool_use_system_prompt()
                self.general_system_prompt = await self._get_general_system_prompt()
        
        await retry_mcp_connection(_setup_with_retry, mcp_server_url=self.mcp_server)
        self._is_setup = True

    async def _get_routing_system_prompt(self)-> str: 
        """Get the routing system prompt""" 
        async def _get_prompt():
            mcp_prompt = await self.mcp_client.get_prompt("routing_system_prompt") 
            return mcp_prompt.messages[0].content.text
        return await retry_mcp_connection(_get_prompt) 
    
    async def _get_tool_use_system_prompt(self) -> str:
        """Get the tool use system prompt."""
        logger.info("Getting tool use system prompt")
        async def _get_prompt():
            mcp_prompt = await self.mcp_client.get_prompt("tool_use_system_prompt")
            return mcp_prompt.messages[0].content.text
        return await retry_mcp_connection(_get_prompt)
    
    async def _get_general_system_prompt(self) -> str:
        """Get the general system prompt."""
        logger.info("Getting general system prompt")
        async def _get_prompt():
            mcp_prompt = await self.mcp_client.get_prompt("general_system_prompt")
            return mcp_prompt.messages[0].content.text
        return await retry_mcp_connection(_get_prompt)

    def reset_memory(self):
        self.memory.reset_memory()
        
    def filter_active_tools(self, tools: list) -> list:
        """
        Filter the list of tools to only include the active tools.
        """
        return [tool for tool in tools if tool.name not in self.disable_tools]

    async def discover_tools(self) -> list:
        """
        Discover and register available tools from the MCP server.

        This method connects to the MCP server and retrieves the list of available tools.
        Each tool contains metadata like name, description, and parameters.

        Returns:
            list: A list of Tool objects containing the discovered tools and their metadata

        Raises:
            ConnectionError: If unable to connect to the MCP server
            Exception: If tool discovery fails for any other reason
        """
        async def _discover_tools():
            async with self.mcp_client as client:
                tools = await client.list_tools()
                if not tools:
                    logger.info("No tools were discovered from the MCP server")
                    return []
                logger.info(f"Discovered {len(tools)} tools:")
                tools = self.filter_active_tools(tools)
                logger.info(f"Filtered tools to {len(tools)} active tools")
                for tool in tools:
                    logger.info(f"- {tool.name}: {tool.description}")
                return tools
        
        try:
            return await retry_mcp_connection(_discover_tools)
        except ConnectionError as e:
            logger.error(f"Failed to connect to MCP server after retries: {e}")
            raise
        except Exception as e:
            logger.error(f"Tool discovery failed: {e}")
            raise
        
    @abstractmethod
    async def _get_tools(self) -> list:
        raise NotImplementedError("Tools are not implemented in the base class.")
    
    async def call_tool(self, function_name: str, function_args: dict) -> str:
        async def _call_tool():
            async with self.mcp_client as _:
                mcp_response = await self.mcp_client.call_tool(function_name, function_args)
                response_text = mcp_response[0].text if mcp_response else ""
                # Check if the response indicates an error
                if response_text and ("error" in response_text.lower() or "not found" in response_text.lower() or "failed" in response_text.lower()):
                    logger.warning(f"MCP tool {function_name} returned potential error: {response_text}")
                return response_text
        
        try:
            return await retry_mcp_connection(_call_tool)
        except Exception as e:
            logger.error(f"MCP call_tool raised exception for {function_name}: {e}", exc_info=True)
            raise
    
    @abstractmethod
    async def chat(self, message: str) -> str:
        raise NotImplementedError("Chat is not implemented in the base class.")