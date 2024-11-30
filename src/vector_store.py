from langchain.schema import Document
from langchain_elasticsearch import ElasticsearchStore
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
import os
import time
from elasticsearch import Elasticsearch
from typing import List, Dict, Optional
import json
from datetime import datetime
from transcript_processor import TranscriptProcessor
from pathlib import Path

load_dotenv()


class VideoTranscriptionStore:
    def __init__(self, videos_dir: str, transcripts_dir: str):
        self.vector_store = self.init_vector_store()
        self.processor = TranscriptProcessor(videos_dir, transcripts_dir)
        self.transcriber = None  # Will be initialized when needed

    def init_vector_store(self) -> ElasticsearchStore:
        # Initialize OpenAI embeddings
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

        # Wait for Elasticsearch to be ready
        es_client = Elasticsearch(
            "http://localhost:9200", basic_auth=("elastic", "changeme")
        )

        # Wait for up to 30 seconds for Elasticsearch to be ready
        start_time = time.time()
        while time.time() - start_time < 30:
            try:
                if es_client.ping():
                    print("Successfully connected to Elasticsearch")
                    break
            except Exception as e:
                print(f"Waiting for Elasticsearch to be ready... {str(e)}")
                time.sleep(2)
        else:
            raise Exception("Could not connect to Elasticsearch after 30 seconds")

        # Initialize vector store
        return ElasticsearchStore(
            es_url="http://localhost:9200",
            index_name="video-transcriptions",
            embedding=embeddings,
            es_user="elastic",
            es_password="changeme",
        )

    def init_transcriber(self, api_key: str):
        """Initialize the video transcriber with API key."""
        from video_transcriber import VideoTranscriber

        self.transcriber = VideoTranscriber(api_key)

    def is_video_upserted(self, video_filename: str) -> bool:
        """Check if a video is already upserted in the vector store."""
        try:
            # Use a direct Elasticsearch query to check for any documents with this video filename
            es_client = self.vector_store.client

            # First check if index exists
            if not es_client.indices.exists(index="video-transcriptions"):
                return False

            response = es_client.search(
                index="video-transcriptions",  # Use the hardcoded index name
                body={
                    "query": {
                        "term": {"metadata.video_filename.keyword": video_filename}
                    },
                    "size": 1,
                },
            )

            return response["hits"]["total"]["value"] > 0
        except Exception as e:
            print(f"Error checking video status: {str(e)}")
            # If check fails, assume not upserted to be safe
            return False

    def upsert_video(self, video_filename: str) -> None:
        """
        Process and upsert a single video's transcription.

        Args:
            video_filename: Name of the video file
        """
        try:
            # Check if video exists
            video_path = Path(self.processor.videos_dir) / video_filename
            if not video_path.exists():
                print(f"Video file {video_filename} not found.")
                return

            # Check if video is already upserted
            if self.is_video_upserted(video_filename):
                print(
                    f"Video {video_filename} is already in the vector store. Skipping."
                )
                return

            # Try to find existing transcript
            transcript_path = self.processor.find_matching_transcript(video_filename)

            # If no transcript exists and transcriber is available, generate one
            if not transcript_path and self.transcriber:
                print(f"Generating transcript for {video_filename}...")
                transcript_path = self.transcriber.transcribe_video(
                    str(video_path), str(self.processor.transcripts_dir)
                )
            elif not transcript_path:
                print(
                    f"No transcript found for {video_filename} and no transcriber configured."
                )
                return

            # Process the video and its transcript
            result = self.processor.process_video(video_filename)

            # Track unique segments to prevent duplicates
            seen_segments = set()
            documents = []

            for segment in result["segments"]:
                # Create a unique key for this segment
                segment_key = (
                    segment["text"],
                    segment["start_time"],
                    segment["end_time"],
                )

                # Skip if we've seen this segment before
                if segment_key in seen_segments:
                    continue

                seen_segments.add(segment_key)

                # Create a Document object with the segment text and metadata
                metadata = result["metadata"].copy()
                if "segment_id" in metadata:
                    del metadata["segment_id"]

                doc = Document(
                    page_content=segment["text"],
                    metadata={
                        **metadata,
                        "start_time": segment["start_time"],
                        "end_time": segment["end_time"],
                    },
                )
                documents.append(doc)

            # Add documents to the vector store
            if documents:
                self.vector_store.add_documents(documents)
                print(
                    f"Successfully upserted {len(documents)} unique segments from video: {video_filename}"
                )
            else:
                print(f"No unique segments found in video: {video_filename}")

        except Exception as e:
            print(f"Error processing video {video_filename}: {str(e)}")

    def upsert_all_videos(self) -> None:
        """Process and upsert all videos in the videos directory."""
        videos_dir = Path(self.processor.videos_dir)
        for video_file in videos_dir.glob("*.mp4"):
            print(f"\nProcessing {video_file.name}...")
            self.upsert_video(video_file.name)

    def search_transcriptions(
        self, query: str, filter_metadata: Optional[Dict] = None, k: int = 5
    ) -> List[Dict]:
        """
        Search transcriptions using a natural language query.

        Args:
            query: Search query
            filter_metadata: Optional metadata filters (e.g., {"video_filename": "example.mp4"})
            k: Number of results to return

        Returns:
            List of relevant transcription segments with metadata
        """
        # Perform the search with more results to account for duplicates
        results = self.vector_store.similarity_search_with_score(
            query, k=k * 2, filter=filter_metadata
        )

        # Format and deduplicate the results
        seen_segments = set()  # Track unique segments
        formatted_results = []

        for doc, score in results:
            # Create a unique key for each segment using content and timing
            segment_key = (
                doc.page_content,
                doc.metadata["start_time"],
                doc.metadata["end_time"],
                doc.metadata["video_filename"],
            )

            if segment_key not in seen_segments:
                seen_segments.add(segment_key)

                metadata = {
                    k: v
                    for k, v in doc.metadata.items()
                    if k
                    not in ["start_time", "end_time", "video_filename", "segment_id"]
                }

                result = {
                    "text": doc.page_content,
                    "start_time": doc.metadata["start_time"],
                    "end_time": doc.metadata["end_time"],
                    "video_filename": doc.metadata["video_filename"],
                    "relevance_score": score,
                    "metadata": metadata,
                }
                formatted_results.append(result)

                # Break if we have enough unique results
                if len(formatted_results) >= k:
                    break

        return formatted_results


def main():
    # Initialize the store with your video and transcript directories
    store = VideoTranscriptionStore(
        videos_dir="/Users/ravikumar/Developer/upwork/RAG-Video-Transcription/data/videos",
        transcripts_dir="/Users/ravikumar/Developer/upwork/RAG-Video-Transcription/data/transcripts",
    )

    # Initialize the transcriber if GEMINI_API_KEY is available
    gemini_api_key = os.getenv("GOOGLE_API_KEY")
    if gemini_api_key:
        store.init_transcriber(gemini_api_key)
    else:
        print(
            "Warning: GOOGLE_API_KEY not found in environment variables. Transcription will be skipped."
        )

    # Upsert all videos
    store.upsert_all_videos()

    # Example search
    results = store.search_transcriptions(
        query="What is great red spot? and how to install python?", k=5
    )

    # Print results
    print("\nSearch Results:")
    for result in results:
        print(f"\nSegment: {result['text']}")
        print(f"Video: {result['video_filename']}")
        print(f"Timestamp: {result['start_time']} - {result['end_time']}")
        print(f"Relevance Score: {result['relevance_score']}")
        print("Additional Metadata:", json.dumps(result["metadata"], indent=2))


if __name__ == "__main__":
    main()
