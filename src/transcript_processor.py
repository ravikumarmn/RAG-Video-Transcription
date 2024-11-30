import os
import re
from typing import List, Dict, Optional
from datetime import datetime
import webvtt
from pathlib import Path


class TranscriptSegment:
    def __init__(self, text: str, start: str, end: str):
        self.text = text
        self.start = start
        self.end = end

    def to_dict(self) -> Dict:
        return {"text": self.text, "start_time": self.start, "end_time": self.end}


class TranscriptProcessor:
    def __init__(self, videos_dir: str, transcripts_dir: str):
        self.videos_dir = Path(videos_dir)
        self.transcripts_dir = Path(transcripts_dir)

    def parse_vtt(self, vtt_path: str) -> List[TranscriptSegment]:
        """Parse a VTT file into segments."""
        segments = []
        for caption in webvtt.read(vtt_path):
            # Clean the text: remove multiple spaces and newlines
            text = " ".join(caption.text.split())
            segments.append(
                TranscriptSegment(text=text, start=caption.start, end=caption.end)
            )
        return segments

    def extract_metadata(self, video_path: str, transcript_path: str) -> Dict:
        """Extract metadata from video and transcript files."""
        video_path = Path(video_path)
        transcript_path = Path(transcript_path)

        # Get video information
        video_stats = video_path.stat()

        # Extract timestamp from transcript filename if it exists
        # Format: filename_YYYYMMDD_HHMMSS.vtt
        timestamp_match = re.search(r"_(\d{8}_\d{6})\.vtt$", transcript_path.name)
        processed_date = None
        if timestamp_match:
            date_str = timestamp_match.group(1)
            try:
                processed_date = datetime.strptime(
                    date_str, "%Y%m%d_%H%M%S"
                ).isoformat()
            except ValueError:
                pass

        metadata = {
            "video_filename": video_path.name,
            "video_size_bytes": video_stats.st_size,
            "video_created_at": datetime.fromtimestamp(
                video_stats.st_ctime
            ).isoformat(),
            "video_modified_at": datetime.fromtimestamp(
                video_stats.st_mtime
            ).isoformat(),
            "transcript_filename": transcript_path.name,
            "transcript_processed_at": processed_date,
            "file_extension": video_path.suffix.lower(),
        }

        return metadata

    def find_matching_transcript(self, video_filename: str) -> Optional[Path]:
        """Find the matching transcript file for a video."""
        base_name = Path(video_filename).stem
        matching_transcripts = list(self.transcripts_dir.glob(f"{base_name}*.vtt"))

        if not matching_transcripts:
            return None

        # Return the most recent transcript if multiple exist
        return sorted(matching_transcripts, key=lambda x: x.stat().st_mtime)[-1]

    def process_video(self, video_filename: str) -> Optional[Dict]:
        """Process a single video and its transcript."""
        video_path = self.videos_dir / video_filename
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_filename}")

        transcript_path = self.find_matching_transcript(video_filename)
        if not transcript_path:
            raise FileNotFoundError(
                f"No matching transcript found for video: {video_filename}"
            )

        # Parse the transcript
        segments = self.parse_vtt(str(transcript_path))

        # Extract metadata
        metadata = self.extract_metadata(video_path, transcript_path)

        return {"segments": [seg.to_dict() for seg in segments], "metadata": metadata}

    def process_all_videos(self) -> List[Dict]:
        """Process all videos in the videos directory."""
        results = []
        for video_file in self.videos_dir.glob("*.mp4"):
            try:
                result = self.process_video(video_file.name)
                if result:
                    results.append(result)
            except Exception as e:
                print(f"Error processing {video_file.name}: {str(e)}")
        return results
