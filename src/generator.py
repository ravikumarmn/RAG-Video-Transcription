from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import os
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv
from openai import OpenAI
from retriever import VideoRetriever
import time
from config_utils import config

load_dotenv()


@dataclass(frozen=True)
class VideoTimestamp:
    """Immutable data class for video timestamps."""

    start: str
    end: str

    def __str__(self) -> str:
        return f"{self.start} - {self.end}"


@dataclass(frozen=True)
class VideoSegment:
    """Immutable data class for video segments."""

    text: str
    video: str
    timestamp: VideoTimestamp
    score: float
    metadata: Dict = field(
        default_factory=dict, hash=False
    )  # Make metadata unhashable but keep the class hashable

    @classmethod
    def from_dict(cls, data: Dict) -> "VideoSegment":
        """Create a VideoSegment from a dictionary."""
        try:
            return cls(
                text=str(data["text"]).strip(),
                video=str(data["video"]),
                timestamp=VideoTimestamp(
                    start=str(data["timestamp"]["start"]),
                    end=str(data["timestamp"]["end"]),
                ),
                score=float(data["score"]),
                metadata=data.get("metadata", {}),
            )
        except (KeyError, ValueError, TypeError) as e:
            raise ValueError(f"Invalid segment data: {e}")

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "video": self.video,
            "timestamp": {"start": self.timestamp.start, "end": self.timestamp.end},
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass
class SearchResponse:
    """Data class for search responses."""

    answer: str
    sources: List[VideoSegment] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def has_error(self) -> bool:
        """Check if response contains an error."""
        return bool(self.error)


class VideoResponseError(Exception):
    """Custom exception for video response generation errors."""

    pass


class VideoResponseGenerator:
    """Production-grade generator for video-based question answering using semantic search."""

    # Class-level constants
    HIGH_CONFIDENCE_THRESHOLD = config.retrieval["similarity_threshold"]
    DEFAULT_MODEL = config.models["chat_model"]
    MAX_TOKENS = config.retrieval["max_tokens"]
    TEMPERATURE = 0.7
    MIN_QUERY_LENGTH = 3
    MAX_QUERY_LENGTH = 500
    DEFAULT_SEARCH_LIMIT = config.retrieval["max_sources"]

    def __init__(
        self,
        videos_dir: str = config.paths["videos"],
        transcripts_dir: str = config.paths["transcripts"],
        model: str = DEFAULT_MODEL,
        high_confidence_threshold: float = HIGH_CONFIDENCE_THRESHOLD,
    ):
        """Initialize the response generator with validation."""
        if not isinstance(videos_dir, str) or not isinstance(transcripts_dir, str):
            raise TypeError("Directory paths must be strings")
        if not isinstance(model, str):
            raise TypeError("Model name must be a string")
        if not isinstance(high_confidence_threshold, (int, float)):
            raise TypeError("Confidence threshold must be a number")
        if not 0 <= high_confidence_threshold <= 1:
            raise ValueError("Confidence threshold must be between 0 and 1")

        self.high_confidence_threshold = high_confidence_threshold
        self.model = model
        self._init_retriever(videos_dir, transcripts_dir)
        self._init_openai()

    def _init_retriever(self, videos_dir: str, transcripts_dir: str) -> None:
        """Initialize the video retriever with error handling."""
        try:
            self.retriever = VideoRetriever(videos_dir, transcripts_dir)
        except Exception as e:
            raise VideoResponseError(f"Failed to initialize VideoRetriever: {e}")

    def _init_openai(self) -> None:
        """Initialize OpenAI client with validation."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise VideoResponseError("OPENAI_API_KEY environment variable is required")
        try:
            self.client = OpenAI(api_key=api_key)
        except Exception as e:
            raise VideoResponseError(f"Failed to initialize OpenAI client: {e}")

    def _validate_query(self, query: str) -> None:
        """Validate the search query."""
        if not isinstance(query, str):
            raise TypeError("Query must be a string")
        if not self.MIN_QUERY_LENGTH <= len(query.strip()) <= self.MAX_QUERY_LENGTH:
            raise ValueError(
                f"Query length must be between {self.MIN_QUERY_LENGTH} and "
                f"{self.MAX_QUERY_LENGTH} characters"
            )

    def _validate_search_params(self, k: int, score_threshold: float) -> None:
        """Validate search parameters."""
        if not isinstance(k, int) or k < 1:
            raise ValueError("k must be a positive integer")
        if not isinstance(score_threshold, (int, float)):
            raise TypeError("score_threshold must be a number")
        if not 0 <= score_threshold <= 1:
            raise ValueError("score_threshold must be between 0 and 1")

    def _process_search_results(self, results: List[Dict]) -> List[VideoSegment]:
        """Convert raw search results to VideoSegment objects with validation."""
        processed_segments = []
        for result in results:
            try:
                segment = VideoSegment.from_dict(result)
                processed_segments.append(segment)
            except ValueError as e:
                print(f"Warning: Skipping invalid segment: {e}")
        return processed_segments

    @lru_cache(maxsize=100)
    def _format_context(self, segments: Tuple[VideoSegment, ...]) -> str:
        """Format search results into context."""
        if not segments:
            return ""

        # sorted_segments = sorted(segments, key=lambda x: x.score, reverse=True)
        return "\n\n".join([segment.text for segment in segments])

    def _create_prompt(self, query: str, context: str) -> List[Dict]:
        system_content = """You are an AI assistant that answers questions about video content.
Instructions:
1. Use ONLY the provided video segments to answer - do not add external information
2. Keep responses brief and focused (2-3 sentences)
3. Be direct and specific
4. If segments don't contain the answer, say "I don't have enough information"
"""

        user_content = f"""Question: {query}

Context from video segments:
{context}

Provide a brief, focused answer using only the information from these segments."""

        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

    def _display_segments(self, segments: List[VideoSegment]) -> None:
        """Display relevant segments."""
        if segments:
            print("\nRetrieved segments:")
            for segment in sorted(segments, key=lambda x: x.score, reverse=True)[
                : self.DEFAULT_SEARCH_LIMIT
            ]:
                print(f"- {segment.text.strip()} (Score: {segment.score:.2f})")
        else:
            print("\nNo relevant segments found.")

    def generate_response(
        self,
        query: str,
        k: int = DEFAULT_SEARCH_LIMIT,
        score_threshold: float = 0.5,
        max_retries: int = 3,
        retry_delay: int = 5,
    ) -> SearchResponse:
        """Generate a response with rate limit handling."""
        try:
            # Validate inputs
            self._validate_query(query)
            self._validate_search_params(k, score_threshold)

            # Perform search
            raw_results = self.retriever.search(
                query=query, k=k, score_threshold=score_threshold
            )

            # Process results
            segments = self._process_search_results(raw_results)

            if not segments:
                return SearchResponse(
                    answer="I don't have enough information.", sources=[]
                )

            self._display_segments(segments)
            context = self._format_context(tuple(segments))
            messages = self._create_prompt(query, context)

            # Generate response with retry logic for rate limits
            for attempt in range(max_retries):
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=self.TEMPERATURE,
                        max_tokens=self.MAX_TOKENS,
                    )

                    return SearchResponse(
                        answer=response.choices[0].message.content,
                        sources=sorted(segments, key=lambda x: x.score, reverse=True)[
                            : self.DEFAULT_SEARCH_LIMIT
                        ],
                    )
                except Exception as e:
                    if "rate limit" in str(e).lower() and attempt < max_retries - 1:
                        print(
                            f"\nRate limit reached. Retrying in {retry_delay} seconds..."
                        )
                        time.sleep(retry_delay)
                        continue
                    raise

        except (ValueError, TypeError) as e:
            return SearchResponse(
                answer="I don't have enough information",
                error=f"Invalid input: {str(e)}",
            )
        except Exception as e:
            if "rate limit" in str(e).lower():
                return SearchResponse(
                    answer="I don't have enough information",
                    error="Rate limit exceeded. Please try again later.",
                )
            return SearchResponse(
                answer="I don't have enough information", error=f"Error: {str(e)}"
            )


def display_response(response: SearchResponse) -> None:
    """Display the response in a formatted way."""
    # Display any errors if present
    if response.has_error:
        print(f"\nWarning: {response.error}")

    # Display the answer
    print(f"\nAnswer: {response.answer}")

    # Display sources if available
    if response.sources:
        print("\nSources:")
        for source in sorted(response.sources, key=lambda x: x.score, reverse=True):
            print(f"- {source.video} at {source.timestamp}")


def main():
    """Run test queries with proper error handling."""
    try:
        # Initialize generator with custom settings
        generator = VideoResponseGenerator(
            high_confidence_threshold=0.7  # Adjust based on your needs
        )

        # Test query
        query = "what is great red spot?"
        print(f"\nQuery: '{query}'")

        # Generate and display response
        response = generator.generate_response(query=query, k=3, score_threshold=0.7)
        display_response(response)

    except Exception as e:
        print(f"An error occurred while processing your request: {e}")


if __name__ == "__main__":
    main()
