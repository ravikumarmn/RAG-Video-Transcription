import streamlit as st
import json
import os

# Load the data
with open("misc/data.json", "r") as json_file:
    segments = json.load(json_file)

st.title("Video Segments")

# Group segments by video filename
video_segments = {}
for segment in segments:
    video_name = segment["video_filename"]
    if video_name not in video_segments:
        video_segments[video_name] = []
    video_segments[video_name].append(segment)

# Display segments for each video
for video_name, segments in video_segments.items():
    st.header(f"Video: {video_name}")
    
    # Read video file
    video_path = os.path.join("data/videos", video_name)
    if os.path.exists(video_path):
        with open(video_path, "rb") as file:
            video_bytes = file.read()
            
        # Display each segment with its timestamp
        for segment in segments:
            st.subheader(f"Segment at {segment['start_time']} - {segment['end_time']}")
            st.write(segment['text'])
            
            # Convert timestamp to seconds for the video player
            start_time = sum(float(x) * 60 ** i for i, x in enumerate(reversed(segment['start_time'].replace(",", ".").split(":"))))
            st.video(video_bytes, start_time=int(start_time))
    else:
        st.error(f"Video file not found: {video_name}")
