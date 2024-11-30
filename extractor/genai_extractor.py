import os
import time
import json
import google.generativeai as genai
from datetime import datetime
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Constants
VIDEOS_DIR = "data/videos"
TRANSCRIPTS_DIR = "data"
SUPPORTED_VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv')


def get_video_files():
    """Get all video files from the videos directory."""
    video_files = []
    for filename in os.listdir(VIDEOS_DIR):
        if filename.lower().endswith(SUPPORTED_VIDEO_EXTENSIONS):
            video_files.append(os.path.join(VIDEOS_DIR, filename))
    return video_files


def get_transcript_status():
    """Load or create the transcript status file."""
    status_file = os.path.join(TRANSCRIPTS_DIR, "transcript_status.json")
    if os.path.exists(status_file):
        with open(status_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'last_update': None,
        'videos': {}
    }


def update_transcript_status(video_path, vtt_file, json_file):
    """Update the transcript status file with new video information."""
    status_file = os.path.join(TRANSCRIPTS_DIR, "transcript_status.json")
    status = get_transcript_status()
    
    video_name = os.path.basename(video_path)
    file_stat = os.stat(video_path)
    
    # Check if file already exists in status and hasn't been modified
    if video_name in status['videos']:
        existing = status['videos'][video_name]
        if os.path.exists(os.path.join(TRANSCRIPTS_DIR, existing['vtt_file'])):
            # If file exists and hasn't been modified, skip updating status
            if file_stat.st_mtime == datetime.fromisoformat(existing['modified_time']).timestamp():
                return
    
    status['last_update'] = datetime.now().isoformat()
    status['videos'][video_name] = {
        'last_processed': datetime.now().isoformat(),
        'file_size': file_stat.st_size,
        'modified_time': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
        'vtt_file': os.path.basename(vtt_file),
        'json_file': os.path.basename(json_file)
    }
    
    with open(status_file, 'w', encoding='utf-8') as f:
        json.dump(status, f, indent=2, ensure_ascii=False)


def should_process_video(video_path):
    """Check if a video needs to be processed based on modification time."""
    status = get_transcript_status()
    video_name = os.path.basename(video_path)
    file_stat = os.stat(video_path)
    
    # If video not in status, it needs processing
    if video_name not in status['videos']:
        return True
    
    video_status = status['videos'][video_name]
    
    # Check if VTT file exists
    vtt_file = os.path.join(TRANSCRIPTS_DIR, video_status['vtt_file'])
    if not os.path.exists(vtt_file):
        return True
    
    # Compare modification times
    last_modified = datetime.fromtimestamp(file_stat.st_mtime)
    last_processed = datetime.fromisoformat(video_status['last_processed'])
    
    # Only process if the video file is newer than the last processing time
    return last_modified > last_processed


def generate_filename(video_filename, extension):
    """Generate a filename based on the video filename and current timestamp."""
    base_name = os.path.splitext(os.path.basename(video_filename))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}.{extension}"


def format_timestamp(timestamp):
    """Format timestamp to ensure exactly 3 decimal places."""
    # Split into seconds and milliseconds
    parts = timestamp.split('.')
    seconds = parts[0]
    # Ensure exactly 3 decimal places
    msec = parts[1][:3] if len(parts) > 1 else "000"
    msec = msec.ljust(3, '0')
    return f"{seconds}.{msec}"


def extract_transcript_data(content):
    """Extract transcript data into a structured format."""
    lines = content.strip().split('\n')
    transcript_data = []
    current_entry = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if '-->' in line:
            if current_entry:
                transcript_data.append(current_entry)
            times = line.split(' --> ')
            current_entry = {
                'start_time': times[0].strip(),
                'end_time': times[1].strip(),
                'text': '',
                'speaker': ''
            }
        elif current_entry and '<v' in line:
            # Extract speaker and text from line like "<v Speaker>Text</v>"
            match = re.match(r'<v ([^>]+)>(.*)</v>', line)
            if match:
                current_entry['speaker'] = match.group(1)
                current_entry['text'] = match.group(2)
    
    if current_entry:
        transcript_data.append(current_entry)
    
    return transcript_data


def clean_vtt_content(content):
    """Clean and format the VTT content."""
    # Remove any markdown code block markers and extra text
    content = re.sub(r'```.*?\n', '', content)
    content = re.sub(r'```', '', content)
    content = re.sub(r'WEBVTT file:', 'WEBVTT', content)
    
    # Start with WEBVTT header
    formatted_lines = ['WEBVTT', '']
    
    # Split content into lines and process
    lines = content.strip().split('\n')
    
    # Skip any existing WEBVTT header
    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith('WEBVTT')):
        i += 1
    
    # Process remaining lines
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
            
        # Process timestamp lines
        if '-->' in line:
            # Format timestamps
            times = line.split(' --> ')
            if len(times) == 2:
                # Ensure HH:MM:SS format for timestamps
                start_time = format_timestamp(times[0].strip())
                end_time = format_timestamp(times[1].strip())
                if ':' not in start_time:
                    start_time = f"00:{start_time}"
                if ':' not in end_time:
                    end_time = f"00:{end_time}"
                formatted_lines.append(f"{start_time} --> {end_time}")
                
                # Process speaker line
                if i + 1 < len(lines):
                    speaker_line = lines[i + 1].strip()
                    if speaker_line:
                        formatted_lines.append(speaker_line)
                        formatted_lines.append('')  # Single blank line between entries
                    i += 2
                    continue
        i += 1
    
    # Remove trailing empty lines and ensure single newline at end
    while formatted_lines and not formatted_lines[-1]:
        formatted_lines.pop()
    
    return '\n'.join(formatted_lines) + '\n'


def save_vtt_content(content, output_path):
    """Save the VTT content to a file."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Saved VTT transcript to: {output_path}")


def save_json_content(transcript_data, output_path):
    """Save the transcript data as JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'format_version': '1.0'
            },
            'transcript': transcript_data
        }, f, indent=2, ensure_ascii=False)
    print(f"Saved JSON transcript to: {output_path}")


def transcribe_video(video_file_path, output_dir="data/transcripts"):
    """Transcribe video using Gemini and save as VTT and JSON files."""
    # Configure Gemini
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

    # Upload video file
    print(f"Uploading file: {video_file_path}")
    video_file = genai.upload_file(path=video_file_path)
    print(f"Completed upload: {video_file.uri}")

    # Check whether the file is ready to be used.
    while video_file.state.name == "PROCESSING":
        print(".", end="")
        time.sleep(10)
        video_file = genai.get_file(video_file.name)

    if video_file.state.name == "FAILED":
        raise ValueError(video_file.state.name)

    # Initialize model
    model = genai.GenerativeModel(model_name="gemini-1.5-pro")

    # Define transcription prompt
    TRANSCRIBE_VIDEO_PROMPT = """
    Transcribe the video audio into WebVTT format following these exact rules:
    1. Start with only "WEBVTT" on the first line (no extra text)
    2. Add exactly one blank line after WEBVTT
    3. For each segment:
       - Use timestamps in format HH:MM:SS.mmm (exactly 3 decimal places)
       - Format: XX:XX:XX.XXX --> XX:XX:XX.XXX
       - Use speaker tags: <v Speaker>text</v>
       - Add exactly one blank line between segments
    4. Keep segments short (around 5-10 seconds each)
    5. Do not add any extra text or formatting

    Example format:
    WEBVTT

    00:00:46.000 --> 00:00:50.020
    <v Speaker>Text content goes here.</v>

    00:00:50.440 --> 00:00:51.050
    <v Speaker>Next segment text.</v>
    """

    try:
        # Generate transcription
        print("Generating transcription...")
        response = model.generate_content(
            [video_file, TRANSCRIBE_VIDEO_PROMPT], request_options={"timeout": 1200}
        )

        # Clean and format the response
        formatted_content = clean_vtt_content(response.text)

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Generate filenames
        vtt_file = os.path.join(output_dir, generate_filename(video_file_path, "vtt"))
        json_file = os.path.join(output_dir, generate_filename(video_file_path, "json"))

        # Extract and save transcript data in both formats
        transcript_data = extract_transcript_data(formatted_content)
        save_vtt_content(formatted_content, vtt_file)
        # save_json_content(transcript_data, json_file)

        return vtt_file, json_file
    except Exception as e:
        print(f"Error during transcription: {str(e)}")
        raise


def transcribe_videos():
    """Process all videos in the videos directory."""
    # Create output directory if it doesn't exist
    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
    
    # Get all video files
    video_files = get_video_files()
    if not video_files:
        print("No video files found in", VIDEOS_DIR)
        return
    
    print(f"Found {len(video_files)} video files")
    
    # Get current status
    status = get_transcript_status()
    
    # Process each video
    for video_path in video_files:
        video_name = os.path.basename(video_path)
        
        # Check if video needs processing
        if not should_process_video(video_path):
            print(f"Skipping {video_name} - transcript already exists and up to date")
            continue
        
        print(f"\nProcessing {video_name}...")
        try:
            vtt_file, json_file = transcribe_video(video_path, TRANSCRIPTS_DIR)
            update_transcript_status(video_path, vtt_file, json_file)
            print(f"Successfully processed {video_name}")
        except Exception as e:
            print(f"Error processing {video_name}: {str(e)}")


if __name__ == "__main__":
    transcribe_videos()
