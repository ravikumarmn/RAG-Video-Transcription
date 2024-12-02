import streamlit as st
from dataclasses import dataclass
from typing import List, Dict, Optional
import os
from pathlib import Path
from dotenv import load_dotenv
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial, lru_cache
import logging
from generator import (
    VideoResponseGenerator,
    SearchResponse,
    VideoSegment,
    VideoTimestamp,
)
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure Streamlit
st.set_page_config(
    page_title="Video Q&A Assistant",
    page_icon="",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Apply custom CSS for better UI
st.markdown(
    """
<style>
    /* Increase dialog width */
    .stDialog > div {
        max-width: 99.5% !important;
        max-height: 98vh !important;
    }
    
    /* Improve chat container */
    .stChatMessage {
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    
    /* Enhance video display */
    .stVideo {
        width: 100%;
        border-radius: 8px;
    }
    
    /* Better button styling */
    .stButton button {
        width: 100%;
        border-radius: 20px;
        transition: all 0.3s ease;
    }
    
    /* Loading spinner */
    .stSpinner > div {
        border-color: #FF4B4B !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Cache configurations
VIDEO_CACHE_TTL = 3600  # 1 hour
GENERATOR_CACHE_TTL = 3600  # 1 hour


@st.cache_resource(ttl=GENERATOR_CACHE_TTL)
def get_generator() -> Optional[VideoResponseGenerator]:
    """Initialize and cache the VideoResponseGenerator."""
    try:
        return VideoResponseGenerator(
            videos_dir="videos",
            transcripts_dir="data/transcripts",
            model="gpt-4o-mini",  # Using GPT-4 for better response quality
        )
    except Exception as e:
        logger.error(f"Failed to initialize VideoResponseGenerator: {e}")
        return None


@lru_cache(maxsize=32)
def get_video_title(video_filename: str) -> str:
    """Get formatted video title from filename."""
    return os.path.splitext(video_filename)[0].replace("_", " ").title()


def parse_timestamp(timestamp: str) -> int:
    """Parse timestamp string to seconds."""
    try:
        if ":" in timestamp:
            parts = timestamp.split(":")
            if len(parts) == 2:
                minutes, seconds = map(float, parts)
                return int(minutes * 60 + seconds)
            elif len(parts) == 3:
                hours, minutes, seconds = map(float, parts)
                return int(hours * 3600 + minutes * 60 + seconds)
        return int(float(timestamp))
    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing timestamp {timestamp}: {e}")
        return 0


def filter_top_k_per_video(sources, display_k: int = 3) -> List[VideoSegment]:
    video_groups = defaultdict(list)
    for source in sources:
        video_groups[source.video].append(source)

    filtered_sources = []
    for video, segments in video_groups.items():
        top_k = sorted(segments, key=lambda x: x.score, reverse=True)[:display_k]
        filtered_sources.extend(top_k)

    return filtered_sources


# Filter top k sources per video
@st.dialog("Video Sources", width="large")
def show_sources(sources: List[VideoSegment]):
    """Display video sources in an optimized dialog."""
    # Filter sources to be taken from one file only with high score
    sources = sorted(sources, key=lambda x: (x.video, x.score), reverse=True)
    # sources = [max(sources, key=lambda x: x.score)]
    top_k_sources = filter_top_k_per_video(sources, display_k=3)

    # Display videos in grid
    cols_per_row = min(2, len(top_k_sources))

    for i in range(0, len(top_k_sources), cols_per_row):
        cols = st.columns(cols_per_row)

        for col_idx, source in enumerate(top_k_sources[i : i + cols_per_row]):
            with cols[col_idx]:
                with st.container():
                    video_path = os.path.join("data/videos", source.video)
                    if os.path.exists(video_path):
                        try:
                            # Read and display video
                            with open(video_path, "rb") as video_file:
                                video_bytes = video_file.read()
                                start_time = parse_timestamp(source.timestamp.start)
                                st.video(video_bytes, start_time=start_time)

                                # Display video title
                                video_title = get_video_title(source.video)
                                st.caption(
                                    f"<p style='text-align: center'>{video_title}</p>",
                                    unsafe_allow_html=True,
                                )
                        except Exception as e:
                            logger.error(f"Error displaying video {video_path}: {e}")
                            st.error(f"Error displaying video: {source.video}")

    if st.button("Close", key="close_sources"):
        st.session_state.show_sources = None
        st.rerun()


def init_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "max_messages" not in st.session_state:
        st.session_state.max_messages = 50  # Increased from 20
    if "show_sources" not in st.session_state:
        st.session_state.show_sources = None
    if "show_about" not in st.session_state:
        st.session_state.show_about = False
    if "last_response_time" not in st.session_state:
        st.session_state.last_response_time = 0


def main():
    """Main application function."""
    init_session_state()
    st.title("Video Q&A Assistant")

    # Display chat history
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):

            st.markdown(message["content"])

            if (
                "sources" in message
                and message["sources"]
                and message["content"] != "I don't have enough information."
            ):
                if st.button("Show Sources", key=f"source_btn_{idx}"):
                    st.session_state.show_sources = message["sources"]
                    st.rerun()

    # Show sources dialog if needed
    if st.session_state.show_sources is not None:
        show_sources(st.session_state.show_sources)

    # Check message limit
    if len(st.session_state.messages) >= st.session_state.max_messages:
        st.warning("🚨 Maximum message limit reached. Please start a new conversation.")
        return

    # Initialize generator
    generator = get_generator()
    if generator is None:
        st.error("⚠️ System initialization failed. Please check configuration.")
        return

    # Handle user input
    if prompt := st.chat_input("Ask a detailed question about the videos..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            try:
                # Track response time
                start_time = time.time()

                with st.spinner("🔍 Searching through videos..."):

                    response = generator.generate_response(
                        query=prompt,
                        k=5,  # Increased number of segments
                        score_threshold=0.5,  # Lower threshold for broader coverage
                    )

                # Calculate response time
                response_time = time.time() - start_time
                st.session_state.last_response_time = response_time

                if response.has_error:
                    st.error(f"😔 {response.error}")
                    message_content = (
                        "I apologize, but I encountered an error while processing your question. "
                        "Please try rephrasing or asking a different question."
                    )
                else:
                    message_content = response.answer
                    # Add response time info
                    # message_content += f"\n\n*Response generated in {response_time:.2f} seconds*"

                st.markdown(message_content)

                # Save message to history
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": message_content,
                        "sources": response.sources if not response.has_error else [],
                        # "response_time": response_time
                    }
                )

                # Show sources button
                if (
                    response.sources
                    and message_content != "I don't have enough information."
                ):
                    if st.button("Show Sources", key="source_btn_current"):
                        st.session_state.show_sources = response.sources
                        st.rerun()

            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                st.error("🚨 An unexpected error occurred. Please try again.")
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": "I apologize, but I encountered an unexpected error.",
                        "sources": [],
                    }
                )


if __name__ == "__main__":
    main()
