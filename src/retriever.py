"""
Video Retrieval Interface using VideoTranscriptionStore
"""
from typing import List, Dict, Optional
from datetime import datetime
import os
from pathlib import Path
from dotenv import load_dotenv
from vector_store import VideoTranscriptionStore

load_dotenv()


class VideoRetriever:
    def __init__(self, videos_dir: str = "videos", transcripts_dir: str = "transcripts"):
        """Initialize video retriever with directories."""
        # Convert to absolute paths
        self.videos_dir = str(Path(videos_dir).absolute())
        self.transcripts_dir = str(Path(transcripts_dir).absolute())
        
        # Ensure directories exist
        os.makedirs(self.videos_dir, exist_ok=True)
        os.makedirs(self.transcripts_dir, exist_ok=True)
        
        # Initialize store
        self.store = VideoTranscriptionStore(
            videos_dir=self.videos_dir,
            transcripts_dir=self.transcripts_dir
        )
        
        # Setup transcriber if API key exists
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            self.store.init_transcriber(api_key)

    def format_timestamp(self, time_str: str) -> str:
        """Convert timestamp to HH:MM:SS.mmm format."""
        try:
            # Convert string to float if needed
            if isinstance(time_str, str):
                seconds = float(time_str)
            else:
                seconds = float(time_str)
                
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"
        except (ValueError, TypeError):
            return str(time_str)

    def format_result(self, result: Dict) -> Dict:
        """Format search result for display."""
        try:
            # Extract metadata
            metadata = result.get("metadata", {})
            
            # Format result
            formatted = {
                "text": result.get("text", ""),
                "video": result.get("video_filename", ""),
                "timestamp": {
                    "start": self.format_timestamp(result.get("start_time", 0)),
                    "end": self.format_timestamp(result.get("end_time", 0))
                },
                "score": result.get("relevance_score", 0),
                "metadata": metadata
            }
            return formatted
        except Exception as e:
            print(f"Error formatting result: {e}")
            return {}

    def search(self, query: str, k: int = 5) -> List[Dict]:
        """Search for video segments matching query."""
        try:
            # Get results from vector store
            results = self.store.search_transcriptions(query, k=k)
            
            # Format results, filtering out empty ones
            formatted = []
            for r in results:
                result = self.format_result(r)
                if result and result.get("text"):
                    formatted.append(result)
            
            return formatted
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def process_video(self, video_filename: str) -> None:
        """Process and index a single video."""
        try:
            self.store.upsert_video(video_filename)
        except Exception as e:
            print(f"Error processing video {video_filename}: {e}")

    def process_all_videos(self) -> None:
        """Process all videos in the videos directory."""
        try:
            self.store.upsert_all_videos()
        except Exception as e:
            print(f"Error processing videos: {e}")


def main():
    """Example usage."""
    # Initialize retriever
    retriever = VideoRetriever()

    # Process videos
    print("\nProcessing videos...")
    retriever.process_all_videos()

    # Search example
    query = "llamaindex"
    print(f"\nSearching: {query}")

    results = retriever.search(query, k=5)

    # Display results
    print("\nResults:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['text']}")
        print(f"   Video: {result['video']}")
        print(f"   Time: {result['timestamp']['start']} - {result['timestamp']['end']}")
        print(f"   Score: {result['score']:.4f}")


if __name__ == "__main__":
    main()
