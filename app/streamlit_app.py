"""
Streamlit App for Video Search and Display
"""
import os
import sys
from pathlib import Path
import streamlit as st
from datetime import datetime
from collections import defaultdict

# Add src directory to path
src_dir = Path(__file__).parent.parent / "src"
sys.path.append(str(src_dir))

from generator import VideoResponseGenerator

# Configure page
st.set_page_config(
    page_title="Video Search & Display",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        background-color: #111827;
        color: #f3f4f6;
        max-width: 1200px;
        margin: 0 auto;
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #f3f4f6 !important;
        font-family: 'Inter', sans-serif;
    }
    
    p, span, div {
        color: #f3f4f6;
        font-family: 'Inter', sans-serif;
    }
    
    .chat-message {
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        max-width: 80%;
    }
    
    .user-message {
        background-color: #4f46e5;
        margin-left: auto;
        border-bottom-right-radius: 5px;
    }
    
    .bot-message {
        background-color: #1f2937;
        margin-right: auto;
        border-bottom-left-radius: 5px;
    }
    
    .search-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: #1f2937;
        padding: 1rem;
        box-shadow: 0 -4px 6px rgba(0,0,0,0.1);
        z-index: 1000;
        max-width: 1200px;
        margin: 0 auto;
    }
    
    .stTextInput > div > div {
        background-color: #374151;
        border: 2px solid #4b5563;
        color: white !important;
        border-radius: 25px;
        padding: 0.5rem 1.5rem;
    }
    
    .source-text {
        background-color: #374151;
        border-left: 4px solid #6366f1;
        color: #f3f4f6;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.5rem 0;
        font-size: 0.9rem;
    }
    
    .source-text .timestamp {
        color: #9ca3af;
        font-size: 0.8rem;
        margin-bottom: 0.5rem;
    }
    
    .source-text .content {
        line-height: 1.5;
    }
    
    .main .block-container {
        padding-bottom: 5rem;
        max-width: 1200px;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .chat-message {
        animation: slideIn 0.3s ease-out;
    }
    
    /* Improved video container styling */
    .stVideo {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

def parse_timestamp(timestamp):
    """Convert timestamp string to seconds."""
    try:
        parts = timestamp.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = map(float, parts)
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            minutes, seconds = map(float, parts)
            return minutes * 60 + seconds
        else:
            return float(timestamp)
    except:
        return 0

def merge_video_segments(videos):
    """
    Merge overlapping video segments and combine their texts.
    Now includes relevance scoring and smart merging.
    """
    if not videos:
        return []
        
    video_groups = defaultdict(list)
    
    # Group segments by video file and track scores
    for video in videos:
        start_time = parse_timestamp(video["start_time"])
        end_time = parse_timestamp(video.get("end_time", video["start_time"])) + 10
        score = video.get("score", 0)
        
        video_groups[video["path"]].append({
            "start": start_time,
            "end": end_time,
            "text": video["text"],
            "score": score
        })
    
    # Merge overlapping segments for each video
    merged_videos = []
    for video_path, segments in video_groups.items():
        # Sort segments by start time
        segments.sort(key=lambda x: x["start"])
        
        # Merge overlapping segments
        merged = []
        current = segments[0]
        
        for segment in segments[1:]:
            # If segments overlap
            if segment["start"] <= current["end"] + 5:  # 5 second buffer
                # Extend end time
                current["end"] = max(current["end"], segment["end"])
                # Combine texts if they're different
                if segment["text"].strip() not in current["text"]:
                    current["text"] = f"{current['text']} {segment['text']}"
                # Take max score
                current["score"] = max(current["score"], segment["score"])
            else:
                merged.append(current)
                current = segment
        
        merged.append(current)
        
        # Add merged segments to final list
        for segment in merged:
            merged_videos.append({
                "path": video_path,
                "start_time": segment["start"],
                "end_time": segment["end"],
                "text": segment["text"].strip(),
                "score": segment["score"]
            })
    
    # Sort by relevance score
    merged_videos.sort(key=lambda x: x["score"], reverse=True)
    
    # Take top N most relevant videos
    MAX_VIDEOS = 4
    return merged_videos[:MAX_VIDEOS]

def display_video_grid(videos, message_index):
    """Display videos in a responsive grid with improved error handling."""
    try:
        # Merge overlapping video segments
        merged_videos = merge_video_segments(videos)
        
        if not merged_videos:
            st.warning("No relevant video segments found.")
            return
            
        # Calculate optimal grid layout
        num_videos = len(merged_videos)
        if num_videos == 1:
            cols = st.columns([1])
        elif num_videos == 2:
            cols = st.columns([1, 1])
        else:
            cols = st.columns([1, 1])  # Max 2 columns
        
        # Display videos in columns
        for i, video in enumerate(merged_videos):
            try:
                col_idx = i % 2  # Alternate between columns
                with cols[col_idx]:
                    # Add video title/info
                    video_name = Path(video["path"]).stem
                    relevance = f"{video['score']*100:.1f}% relevant"
                    # st.markdown(f"##### {video_name} ({relevance})")
                    
                    # Display video with start time
                    start_time = int(video["start_time"])
                    try:
                        st.video(
                            video["path"],
                            start_time=start_time
                        )
                    except Exception as e:
                        st.error(f"Error loading video: {str(e)}")
                        continue
                    
                    # Display timestamp and text
                    timestamp = f"{int(start_time//60)}:{int(start_time%60):02d}"
                    st.markdown(f"""
                        <div class="source-text">
                            <div class="timestamp">{timestamp}</div>
                            <div class="content">{video["text"]}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
            except Exception as e:
                st.error(f"Error displaying video segment: {str(e)}")
                continue
                
    except Exception as e:
        st.error(f"Error in video grid display: {str(e)}")

def format_response(response_text, has_valid_sources=False):
    """Format the response text based on whether there are valid sources."""
    if not has_valid_sources:
        return f"Based on my knowledge: {response_text}"
    return response_text

def display_chat_message(message, message_index):
    """Display a chat message with appropriate styling."""
    if message["type"] == "user":
        st.markdown(f"""
            <div class="chat-message user-message">
                🧑‍💻 <b>You:</b><br>{message["content"]}
            </div>
        """, unsafe_allow_html=True)
    else:
        # Display assistant message
        st.markdown(f"""
            <div class="chat-message bot-message">
                🤖 <b>Assistant:</b><br>{message["content"]}
            </div>
        """, unsafe_allow_html=True)
        
        # Display videos only if they meet the threshold
        if "videos" in message and message["videos"] and any(v.get("score", 0) >= message.get("threshold", 0.5) for v in message["videos"]):
            # st.markdown("---")
            # st.markdown("📺 **Relevant Video Segments:**")
            
            # Filter videos by threshold
            valid_videos = [v for v in message["videos"] if v.get("score", 0) >= message.get("threshold", 0.5)]
            if valid_videos:
                display_video_grid(valid_videos, message_index)

def main():
    st.markdown("# 🎬 Video Search Assistant")
    
    # Initialize generator
    videos_dir = Path(__file__).parent.parent / "data/videos"
    transcripts_dir = Path(__file__).parent.parent / "data/transcripts"
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    try:
        generator = VideoResponseGenerator(
            str(videos_dir),
            str(transcripts_dir)
        )
    except Exception as e:
        st.error(f"⚠️ Error initializing generator: {e}")
        return
    
    # Display chat history
    for i, message in enumerate(st.session_state.chat_history):
        display_chat_message(message, i)
    
    # Search form
    with st.form("search_form", clear_on_submit=True):
        st.markdown("""
            <div class="search-container">
        """, unsafe_allow_html=True)
        
        cols = st.columns([4, 1])
        with cols[0]:
            query = st.chat_input(
                "",
                placeholder="Ask me anything about the videos...",
                label_visibility="collapsed"
            )
        
        with cols[1]:
            submitted = st.form_submit_button("🔍 Ask", use_container_width=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Handle search
    if submitted and query:
        # Add user message to chat
        st.session_state.chat_history.append({
            "type": "user",
            "content": query
        })
        
        with st.spinner("🤖 Thinking..."):
            try:
                # Set threshold for video display
                threshold = 0.5
                
                # Get response
                response = generator.generate_response(
                    query=query,
                    k=5,
                    score_threshold=0  # Get all results, we'll filter later
                )
                
                if response["answer"]:
                    # Check if we have any sources that meet the threshold
                    valid_sources = [s for s in response["sources"] if s["score"] >= threshold]
                    has_valid_sources = bool(valid_sources)
                    
                    # Format response based on whether we have valid sources
                    formatted_response = format_response(
                        response["answer"],
                        has_valid_sources=has_valid_sources
                    )
                    
                    # Create assistant message
                    assistant_message = {
                        "type": "assistant",
                        "content": formatted_response,
                        "threshold": threshold  # Store threshold for video filtering
                    }
                    
                    # Add video information for all sources (will be filtered in display)
                    if response["sources"]:
                        assistant_message["videos"] = [{
                            "path": str(videos_dir / source["video"]),
                            "start_time": source["timestamp"]["start"],
                            "end_time": source["timestamp"].get("end", None),
                            "text": source["text"],
                            "score": source["score"]  # Include score for filtering
                        } for source in response["sources"]]
                    
                    # Add to chat history
                    st.session_state.chat_history.append(assistant_message)
                else:
                    # Handle case where no answer was generated
                    st.session_state.chat_history.append({
                        "type": "assistant",
                        "content": "I couldn't generate a response for your query. Please try asking something else."
                    })
                
                # Rerun to update chat display
                st.experimental_rerun()
            
            except Exception as e:
                st.error(f"⚠️ Error processing your query: {e}")
                st.session_state.chat_history.append({
                    "type": "assistant",
                    "content": f"I encountered an error while processing your query: {str(e)}"
                })

if __name__ == "__main__":
    main()
