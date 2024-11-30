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
    """Merge overlapping video segments and combine their texts."""
    video_groups = defaultdict(list)
    
    # Group segments by video file
    for video in videos:
        start_time = parse_timestamp(video["start_time"])
        end_time = parse_timestamp(video.get("end_time", video["start_time"])) + 10  # Default 10 sec if no end time
        video_groups[video["path"]].append({
            "start": start_time,
            "end": end_time,
            "text": video["text"]
        })
    
    # Merge overlapping segments for each video
    merged_videos = []
    for video_path, segments in video_groups.items():
        # Sort segments by start time
        segments.sort(key=lambda x: x["start"])
        
        # Get unique segments and find min start and max end time
        unique_texts = []
        min_start = segments[0]["start"]
        max_end = segments[0]["end"]
        
        for segment in segments:
            text = segment["text"].strip()
            if text not in unique_texts:
                unique_texts.append(text)
            min_start = min(min_start, segment["start"])
            max_end = max(max_end, segment["end"])
        
        # Create a single merged segment
        merged_videos.append({
            "path": video_path,
            "start_time": min_start,  # Keep as seconds for st.video
            "end_time": max_end,  # Keep as seconds for st.video
            "text": " ".join(unique_texts)
        })
    
    return merged_videos

def display_video_grid(videos, message_index):
    """Display videos using st.video."""
    # Merge overlapping video segments
    merged_videos = merge_video_segments(videos)
    
    # Create columns for videos
    cols = st.columns(min(len(merged_videos), 2))  # Max 2 columns
    
    # Display videos in columns
    for i, video in enumerate(merged_videos):
        col_idx = i % 2  # Alternate between columns
        with cols[col_idx]:
            # Display video with start time
            st.video(video["path"], start_time=int(video["start_time"]))
            
            # Display text
            st.markdown(f"""
                <div class="source-text">
                    {video["text"]}
                </div>
            """, unsafe_allow_html=True)

def format_response(response_text):
    """Format the response text only."""
    return response_text

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
        if message["type"] == "user":
            st.markdown(f"""
                <div class="chat-message user-message">
                    🧑‍💻 <b>You:</b><br>{message["content"]}
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
                <div class="chat-message bot-message">
                    🤖 <b>Assistant:</b><br>{message["content"]}
                </div>
            """, unsafe_allow_html=True)
            
            # Display videos if present
            if "videos" in message:
                display_video_grid(message["videos"], i)
    
    # Search form
    with st.form("search_form", clear_on_submit=True):
        st.markdown("""
            <div class="search-container">
        """, unsafe_allow_html=True)
        
        cols = st.columns([4, 1])
        with cols[0]:
            query = st.text_input(
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
                response = generator.generate_response(query, k=3)
                
                if response["answer"]:
                    # Format response with just the answer
                    formatted_response = format_response(response["answer"])
                    
                    # Add assistant's response with video segments
                    st.session_state.chat_history.append({
                        "type": "assistant",
                        "content": formatted_response,
                        "videos": [{
                            "path": str(videos_dir / source["video"]),
                            "start_time": source["timestamp"]["start"],
                            "end_time": source["timestamp"].get("end", None),  # Get end time if available
                            "text": source["text"]
                        } for source in response["sources"]]
                    })
                else:
                    st.session_state.chat_history.append({
                        "type": "assistant",
                        "content": "I couldn't find any relevant video segments for your query. Please try asking something else."
                    })
                
                # Rerun to update chat display
                st.experimental_rerun()
            
            except Exception as e:
                st.error(f"⚠️ Error: {e}")

if __name__ == "__main__":
    main()
