from typing import Dict
from uuid import uuid4

from loguru import logger      

from elix_mcp.config import get_settings
from elix_mcp.video.ingestion.tools import extract_video_clip
from elix_mcp.video.ingestion.video_processor import VideoProcessor
from elix_mcp.video.video_search_engine import VideoSearchEngine

logger = logger.bind(name="MCPVideoTools")
video_processor = VideoProcessor()
settings = get_settings()


def process_video(video_path: str) -> str:
    """Process a video file and prepare it for searching.

    Args:
        video_path (str): Path to the video file to process.

    Returns:
        str: Success message indicating the video was processed.

    Raises:
        ValueError: If the video file cannot be found or processed.
    """
    try:
        exists = video_processor._check_if_exists(video_path)
        if exists:
            logger.info(f"Video index for '{video_path}' already exists and is ready for use.")
            return "Video already processed and ready for use."
        
        logger.info(f"Starting to process video: {video_path}")
        video_processor.setup_table(video_name=video_path)
        is_done = video_processor.add_video(video_path=video_path)
        
        if is_done:
            logger.info(f"Successfully processed video: {video_path}")
            return "Video processed successfully."
        else:
            raise ValueError(f"Video processing failed for {video_path}")
    except Exception as e:
        logger.error(f"Error processing video {video_path}: {e}", exc_info=True)
        raise ValueError(f"Failed to process video {video_path}: {str(e)}")


def get_video_clip_from_user_query(video_path: str, user_query: str) -> str:
    """Get a video clip based on the user query using speech and caption similarity.

    Args:
        video_path (str): The path to the video file.
        user_query (str): The user query to search for.

    Returns:
        str: Path to the extracted video clip.
    
    Raises:
        ValueError: If no matching clips are found or video index doesn't exist.
    """
    try:
        search_engine = VideoSearchEngine(video_path)
    except ValueError as e:
        logger.error(f"Failed to initialize VideoSearchEngine for {video_path}: {e}")
        raise ValueError(f"Video index not found for {video_path}. Please process the video first using process_video tool.")

    speech_clips = search_engine.search_by_speech(user_query, settings.VIDEO_CLIP_SPEECH_SEARCH_TOP_K)
    caption_clips = search_engine.search_by_caption(user_query, settings.VIDEO_CLIP_CAPTION_SEARCH_TOP_K)

    speech_sim = speech_clips[0]["similarity"] if speech_clips else 0
    caption_sim = caption_clips[0]["similarity"] if caption_clips else 0

    # Check if we have any results
    if not speech_clips and not caption_clips:
        raise ValueError(f"No matching clips found for query: '{user_query}'. The video may not contain content matching your search.")

    # Select the best match
    video_clip_info = speech_clips[0] if speech_sim > caption_sim else caption_clips[0]

    video_clip = extract_video_clip(
        video_path=video_path,
        start_time=video_clip_info["start_time"],
        end_time=video_clip_info["end_time"],
        output_path=f"./shared_media/{str(uuid4())}.mp4",
    )

    return video_clip.filename


def get_video_clip_from_image(video_path: str, user_image: str) -> str:
    """Get a video clip based on similarity to a provided image.

    Args:
        video_path (str): The path to the video file.
        user_image (str): The query image encoded in base64 format.

    Returns:
        str: Path to the extracted video clip.
    
    Raises:
        ValueError: If no matching clips are found or video index doesn't exist.
    """
    try:
        search_engine = VideoSearchEngine(video_path)
    except ValueError as e:
        logger.error(f"Failed to initialize VideoSearchEngine for {video_path}: {e}")
        raise ValueError(f"Video index not found for {video_path}. Please process the video first using process_video tool.")
    
    image_clips = search_engine.search_by_image(user_image, settings.VIDEO_CLIP_IMAGE_SEARCH_TOP_K)

    if not image_clips:
        raise ValueError(f"No matching image clips found in video {video_path}. The video may not contain frames similar to the provided image.")

    video_clip = extract_video_clip(
        video_path=video_path,
        start_time=image_clips[0]["start_time"],
        end_time=image_clips[0]["end_time"],
        output_path=f"./shared_media/{str(uuid4())}.mp4",
    )

    return video_clip.filename


def ask_question_about_video(video_path: str, user_query: str) -> str:
    """Get relevant captions from the video based on the user's question.

    Args:
        video_path (str): The path to the video file.
        user_query (str): The question to search for relevant captions.

    Returns:
        str: Concatenated relevant captions from the video.
    """
    search_engine = VideoSearchEngine(video_path)
    caption_info = search_engine.get_caption_info(user_query, settings.QUESTION_ANSWER_TOP_K)

    answer = "\n".join(entry["caption"] for entry in caption_info)
    return answer