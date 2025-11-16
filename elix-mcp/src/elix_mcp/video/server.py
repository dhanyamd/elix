import click 
from fastmcp import FastMCP

from elix_mcp.video.prompts import general_system_prompt, routing_system_prompt, tool_use_system_prompt
from elix_mcp.video.resources import list_tables
from elix_mcp.video.tools import (
    ask_question_about_video,
    get_video_clip_from_image,
    get_video_clip_from_user_query,     
    process_video,
)

def add_mcp_tools(mcp: FastMCP): 
    # FastMCP.add_tool() only accepts a Tool instance, not a name and function.
    # Use mcp.tool() to register functions - it converts them to Tool instances automatically.
    # The tool name will be inferred from the function name, or you can specify it with name="...".
    
    mcp.tool(process_video)

    mcp.tool(get_video_clip_from_user_query)

    mcp.tool(get_video_clip_from_image)

    mcp.tool(ask_question_about_video)

def add_mcp_resources(mcp: FastMCP):
    # NOTE: add_resource_fn still uses keyword arguments.
    mcp.add_resource_fn(
        fn=list_tables,
        uri="file:///app/.records/records.json",
        name="list_tables",
        description="List all video indexes currently available.",
        tags={"resource", "all"},
    )
    
def add_mcp_prompts(mcp: FastMCP):
    # NOTE: add_prompt still uses keyword arguments.
    mcp.add_prompt(
        fn=routing_system_prompt,
        name="routing_system_prompt",
        description="Latest version of the routing prompt from Opik.",
        tags={"prompt", "routing"},
    )

    mcp.add_prompt(
        fn=tool_use_system_prompt,
        name="tool_use_system_prompt",
        description="Latest version of the tool use prompt from Opik.",
        tags={"prompt", "tool_use"},
    )

    mcp.add_prompt(
        fn=general_system_prompt,
        name="general_system_prompt",
        description="Latest version of the general prompt from Opik.",
        tags={"prompt", "general"},
    )
 
mcp = FastMCP("VideoProcessor")

# Since the previous error didn't involve prompts, we'll assume the TODO line
# is still valid and keep it commented out until you confirm the prompt API is stable.
add_mcp_prompts(mcp)
add_mcp_tools(mcp)
add_mcp_resources(mcp) 

@click.command()
@click.option("--port", default=9090, help="FastMCP server port")
@click.option("--host", default="0.0.0.0", help="FastMCP server host")
@click.option("--transport", default="streamable-http", help="MCP Transport protocol type")
def run_mcp(port, host, transport):
    """
    Run the FastMCP server with the specified port, host, and transport protocol.
    """
    # Use FastMCP's built-in run method which properly initializes everything
    # This ensures all MCP protocol handlers are set up correctly
    mcp.run(host=host, port=port, transport=transport)


if __name__ == "__main__":
    run_mcp()