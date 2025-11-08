import traceback
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
from elix_api.models import (
    AssistantMessageResponse,
    ProcessVideoRequest,
    ProcessVideoResponse,
    ResetMemoryResponse,
    UserMessageRequest,
    VideoUploadResponse,
)

settings = get_settings()

class TaskStatus(str, Enum): 
    PENDING = "pending" 
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed" 
    FAILED = "failed" 
    NOT_FOUND = "not_found"

# Store task errors for debugging
task_errors: dict[str, str] = {} 

@asynccontextmanager
async def lifespan(app: FastAPI): 
    logger.info("🚀 Starting Elix API server...")
    logger.info(f"🔗 MCP Server URL: {settings.MCP_SERVER}")
    app.state.agent = GroqAgent(
        name="elix",
        mcp_server=settings.MCP_SERVER,
        disable_tools=["process_video"], 
    )
    app.state.bg_task_states = dict()
    logger.info("✅ Elix API server started successfully")
    yield
    logger.info("🛑 Shutting down Elix API server...")
    app.state.agent.reset_memory()

app = FastAPI(
    title="Elix API",
    description="An AI-powered sports assistant API using OpenAI",
    docs_url="/docs",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Frontend URL
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
    logger.info("📥 Root endpoint accessed")
    return {"message": "Welcome to Elix API. Visit /docs for documentation"}

@app.get("/task-status/{task_id}") 
async def get_task_status(task_id: str, fastapi_request: Request): 
    status = fastapi_request.app.state.bg_task_states.get(task_id, TaskStatus.NOT_FOUND)
    error = task_errors.get(task_id, None)
    logger.info(f"📊 Task status check for {task_id}: {status}")
    response = {"task_id": task_id, "status": status}
    if error:
        response["error"] = error
    return response 

@app.post("/process-video")
async def process_video(request: ProcessVideoRequest, bg_tasks: BackgroundTasks, fastapi_request: Request):
    """
    Process a video and return the results
    """
    logger.info(f"📥 Received process-video request for: {request.video_path}")
    task_id = str(uuid4())
    bg_task_states = fastapi_request.app.state.bg_task_states
    logger.info(f"📝 Created task_id: {task_id}")
    
    # Initialize task status as PENDING before enqueuing
    bg_task_states[task_id] = TaskStatus.PENDING
    logger.info(f"📝 Task {task_id} initialized with status: PENDING")

    async def background_process_video(video_path: str, task_id: str): 
        """
        Background task to process the video
        """
        logger.info(f"🚀 Starting background video processing task {task_id} for video: {video_path}")
        bg_task_states[task_id] = TaskStatus.IN_PROGRESS
        logger.info(f"📝 Task {task_id} status updated to: IN_PROGRESS") 

        try:
            logger.info(f"📁 Checking if video file exists: {video_path}")
            if not Path(video_path).exists():
                error_msg = f"❌ Video file not found: {video_path}"
                logger.error(error_msg)
                bg_task_states[task_id] = TaskStatus.FAILED 
                return
            
            logger.info(f"🔗 Connecting to MCP server: {settings.MCP_SERVER}")
            mcp_client = Client(settings.MCP_SERVER) 
            
            logger.info(f"🛠️ Calling process_video tool with video_path: {video_path}")
            async with mcp_client: 
                logger.info(f"✅ MCP client connected, calling tool...")
                result = await mcp_client.call_tool("process_video", {"video_path": video_path})
                logger.info(f"✅ Video processing completed successfully. Result: {result}")
            
            bg_task_states[task_id] = TaskStatus.COMPLETED 
            logger.info(f"✅ Task {task_id} completed successfully")
        except Exception as e: 
            error_msg = f"❌ Error processing video {video_path}: {type(e).__name__}: {str(e)}"
            full_error = f"{error_msg}\n\nFull traceback:\n{traceback.format_exc()}"
            logger.error(error_msg, exc_info=True)
            logger.error(f"Full traceback: {traceback.format_exc()}")
            bg_task_states[task_id] = TaskStatus.FAILED
            task_errors[task_id] = full_error  # Store error for debugging
            logger.error(f"❌ Task {task_id} failed: {error_msg}") 
    logger.info(f"📋 Enqueuing background task {task_id} for video: {request.video_path}")
    bg_tasks.add_task(background_process_video, request.video_path, task_id) 
    logger.info(f"✅ Background task {task_id} enqueued successfully")
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
    logger.info(f"📤 Received upload-video request for file: {file.filename}")
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    try:
        shared_media_dir = Path("shared_media")
        shared_media_dir.mkdir(exist_ok=True)

        # Sanitize filename to prevent path traversal
        safe_filename = Path(file.filename).name
        video_path = shared_media_dir / safe_filename
        
        # Stream file content to disk to handle large files efficiently
        if not video_path.exists():
            # Read and write in chunks to avoid loading entire file into memory
            with open(video_path, "wb") as f:
                while chunk := await file.read(8192):  # Read in 8KB chunks
                    f.write(chunk)
            logger.info(f"Video uploaded successfully: {video_path}")
        else:
            logger.info(f"File {video_path} already exists, skipping upload")

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

    uvicorn.run(
        "api:app",
        host=host,
        port=port,
        loop="asyncio",
        timeout_keep_alive=120,  # Increase keep-alive timeout for large uploads
        limit_concurrency=100,  # Allow more concurrent connections
    )


if __name__ == "__main__":
    run_api()