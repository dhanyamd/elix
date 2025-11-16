import shutil
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path
from uuid import uuid4

import click
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastmcp.client import Client
from loguru import logger

from elix_api.agent import GroqAgent
from elix_api.config import get_settings
from elix_api.mcp_utils import retry_mcp_connection
from elix_api.models import AssistantMessageResponse, ProcessVideoRequest, ProcessVideoResponse, ResetMemoryResponse, UserMessageRequest, VideoUploadResponse

settings = get_settings()


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_FOUND = "not_found"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.agent = GroqAgent(
        name="elix-api",
        mcp_server=settings.MCP_SERVER,
        disable_tools=["process_video"],
    )
    app.state.bg_task_states = dict()
    yield
    app.state.agent.reset_memory()


app = FastAPI(
    title="Elix API",
    description="An AI-powered sports assistant API using OpenAI",
    docs_url="/docs",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = [
    "*", # Wildcard for simple requests (but better to be specific)
    "http://localhost",
    "http://localhost:3000", # Frontend port
    "http://127.0.0.1:3000", # Fallback for frontend port
    settings.FRONTEND_URL, # Assuming this is defined in your settings
]
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
     
)

# Mount static files for media serving
app.mount("/media", StaticFiles(directory="shared_media"), name="media")


@app.get("/")
async def root():
    """
    Root endpoint that redirects to API documentation
    """
    return {"message": "Welcome to Elix API. Visit /docs for documentation"}


@app.get("/task-status/{task_id}")
async def get_task_status(task_id: str, fastapi_request: Request):
    status = fastapi_request.app.state.bg_task_states.get(task_id, TaskStatus.NOT_FOUND)
    error = fastapi_request.app.state.bg_task_states.get(f"{task_id}_error")
    response = {"task_id": task_id, "status": status}
    if error:
        response["error"] = error
    return response


@app.post("/process-video")
async def process_video(request: ProcessVideoRequest, bg_tasks: BackgroundTasks, fastapi_request: Request):
    """
    Process a video and return the results
    """
    task_id = str(uuid4())
    bg_task_states = fastapi_request.app.state.bg_task_states

    async def background_process_video(video_path: str, task_id: str):
        """
        Background task to process the video
        """
        bg_task_states[task_id] = TaskStatus.IN_PROGRESS

        try:
            if not Path(video_path).exists():
                error_msg = f"Video file not found at {video_path}"
                logger.error(error_msg)
                bg_task_states[task_id] = TaskStatus.FAILED
                bg_task_states[f"{task_id}_error"] = error_msg
                return

            logger.info(f"Starting video processing for {video_path}")
            logger.info(f"Connecting to MCP server at: {settings.MCP_SERVER}")
            
            try:
                mcp_client = Client(settings.MCP_SERVER)
                
                async def _process_video():
                    async with mcp_client:
                        result = await mcp_client.call_tool("process_video", {"video_path": video_path})
                        return result
                
                result = await retry_mcp_connection(_process_video, mcp_server_url=settings.MCP_SERVER)
                logger.info(f"Video processing result: {result}")
            except Exception as mcp_error:
                # Provide more helpful error message for connection issues
                error_str = str(mcp_error)
                error_lower = error_str.lower()
                
                # Check for various connection error patterns
                is_connection_error = (
                    "name or service not known" in error_lower
                    or "failed to connect" in error_lower
                    or "connection" in error_lower and ("refused" in error_lower or "failed" in error_lower or "error" in error_lower)
                    or "all connection attempts failed" in error_lower
                    or isinstance(mcp_error, (ConnectionError, OSError))
                )
                
                if is_connection_error:
                    # Check if we're trying to use Docker hostname but might be running locally
                    troubleshooting = ""
                    if "elix-mcp" in settings.MCP_SERVER:
                        troubleshooting = (
                            f"\n\nTroubleshooting:\n"
                            f"1. If running locally (outside Docker), set MCP_SERVER=http://localhost:9090/mcp/\n"
                            f"2. If running in Docker, ensure elix-mcp container is running: docker ps | grep elix-mcp\n"
                            f"3. Check MCP server is accessible: curl {settings.MCP_SERVER.replace('elix-mcp', 'localhost')}\n"
                        )
                    
                    error_msg = (
                        f"Failed to connect to MCP server at {settings.MCP_SERVER}. "
                        f"Please ensure the MCP server is running and accessible.{troubleshooting}"
                        f"\nOriginal error: {error_str}"
                    )
                    logger.error(error_msg)
                    bg_task_states[task_id] = TaskStatus.FAILED
                    bg_task_states[f"{task_id}_error"] = error_msg
                    return
                raise
            
            bg_task_states[task_id] = TaskStatus.COMPLETED
            logger.info(f"Video processing completed successfully for {video_path}")
        except Exception as e:
            error_str = str(e)
            error_lower = error_str.lower()
            
            # Check if this is a connection error that wasn't caught earlier
            is_connection_error = (
                "name or service not known" in error_lower
                or "failed to connect" in error_lower
                or "all connection attempts failed" in error_lower
                or ("connection" in error_lower and ("refused" in error_lower or "failed" in error_lower or "error" in error_lower))
                or isinstance(e, (ConnectionError, OSError))
            )
            
            if is_connection_error:
                # Provide troubleshooting help for connection errors
                troubleshooting = ""
                if "elix-mcp" in settings.MCP_SERVER:
                    troubleshooting = (
                        f"\n\nTroubleshooting:\n"
                        f"1. If running locally (outside Docker), set MCP_SERVER=http://localhost:9090/mcp/\n"
                        f"2. If running in Docker, ensure elix-mcp container is running: docker ps | grep elix-mcp\n"
                        f"3. Check MCP server is accessible: curl {settings.MCP_SERVER.replace('elix-mcp', 'localhost')}\n"
                    )
                
                error_msg = (
                    f"Error processing video {video_path}: Failed to connect to MCP server at {settings.MCP_SERVER}. "
                    f"Please ensure the MCP server is running and accessible.{troubleshooting}"
                    f"\nOriginal error: {error_str}"
                )
            else:
                error_msg = f"Error processing video {video_path}: {error_str}"
            
            logger.error(error_msg, exc_info=True)
            bg_task_states[task_id] = TaskStatus.FAILED
            bg_task_states[f"{task_id}_error"] = error_msg

    bg_tasks.add_task(background_process_video, request.video_path, task_id)
    return ProcessVideoResponse(message="Task enqueued for processing", task_id=task_id)


@app.post("/chat", response_model=AssistantMessageResponse)
async def chat(request: UserMessageRequest, fastapi_request: Request):
    """
    Chat with the AI assistant

    Args:
        request: ChatRequest containing the message and optional image URL

    Returns:
        ChatResponse containing the assistant's response
    """
    agent = fastapi_request.app.state.agent
    await agent.setup()

    try:
        response = await agent.chat(request.message, request.video_path, request.image_base64)
        return response
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset-memory")
async def reset_memory(fastapi_request: Request):
    """
    Reset the memory of the agent
    """
    agent = fastapi_request.app.state.agent
    agent.reset_memory()
    return ResetMemoryResponse(message="Memory reset successfully")


@app.post("/upload-video", response_model=VideoUploadResponse)
async def upload_video(file: UploadFile = File(...)):
    """
    Upload a video and return the path
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    try:
        shared_media_dir = Path("shared_media")
        shared_media_dir.mkdir(exist_ok=True)

        video_path = Path(shared_media_dir / file.filename)
        if not video_path.exists():
            with open(video_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

        return VideoUploadResponse(message="Video uploaded successfully", video_path=str(video_path))
    except Exception as e:
        logger.error(f"Error uploading video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/media/{file_path:path}")
async def serve_media(file_path: str):
    """
    Serve media files from the shared_media directory
    """
    try:
        clean_path = Path(file_path).name
        media_file = Path("shared_media") / clean_path

        if not media_file.exists():
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(str(media_file))
    except Exception as e:
        logger.error(f"Error serving media file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@click.command()
@click.option("--port", default=8080, help="FastAPI server port")
@click.option("--host", default="0.0.0.0", help="FastAPI server host")
def run_api(port, host):
    import uvicorn

    uvicorn.run("elix_api.api:app", host=host, port=port, loop="asyncio")


if __name__ == "__main__":
    run_api()
