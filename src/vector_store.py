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
            index_name="video_transcriptions",
            embedding=embeddings,
            es_user="elastic",
            es_password="changeme",
        )

    def upsert_video(self, video_filename: str) -> None:
        """
        Process and upsert a single video's transcription.

        Args:
            video_filename: Name of the video file
        """
        try:
            # Check if video is already processed by searching for its segments
            existing_results = self.vector_store.similarity_search(
                "", filter={"video_filename": video_filename}, k=1
            )
            
            if existing_results:
                print(f"Video {video_filename} is already loaded in the vector store.")
                return

            # Process the video and its transcript
            result = self.processor.process_video(video_filename)

            documents = []
            for segment in result["segments"]:
                # Create a Document object with the segment text and all metadata
                doc = Document(
                    page_content=segment["text"],
                    metadata={
                        # Include all video/transcript metadata #TODO: Metadata in json dynamic.
                        **result["metadata"],
                        "start_time": segment["start_time"],
                        "end_time": segment["end_time"],
                        
                    },
                )
                documents.append(doc)

            # Add documents to the vector store
            self.vector_store.add_documents(documents)
            print(f"Added {len(documents)} segments from video: {video_filename}")

        except Exception as e:
            print(f"Error processing video {video_filename}: {str(e)}")

    def upsert_all_videos(self) -> None:
        """Process and upsert all videos in the videos directory."""
        videos_dir = Path(self.processor.videos_dir)
        for video_file in videos_dir.glob("*.mp4"):
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
        # Perform the search
        results = self.vector_store.similarity_search_with_score(
            query, k=k, filter=filter_metadata
        )

        # Format the results
        formatted_results = []
        for doc, score in results:
            result = {
                "text": doc.page_content,
                "start_time": doc.metadata["start_time"],
                "end_time": doc.metadata["end_time"],
                "video_filename": doc.metadata["video_filename"],
                "relevance_score": score,
            }

            # Add all other metadata
            result["metadata"] = {
                k: v
                for k, v in doc.metadata.items()
                if k not in ["start_time", "end_time", "video_filename"]
            }

            formatted_results.append(result)

        return formatted_results


def main():
    # Initialize the store with your video and transcript directories
    store = VideoTranscriptionStore(
        videos_dir="/Users/ravikumar/Developer/upwork/RAG-Video-Transcription/data/videos",
        transcripts_dir="/Users/ravikumar/Developer/upwork/RAG-Video-Transcription/data/transcripts",
    )

    # Upsert all videos
    store.upsert_all_videos()

    # Example search
    results = store.search_transcriptions(
        query="What is great red spot?", k=3
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
