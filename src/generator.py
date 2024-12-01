"""
Response Generator for Video Transcripts
"""

from typing import List, Dict
import os
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from retriever import VideoRetriever

load_dotenv()


class VideoResponseGenerator:

    def __init__(
        self, videos_dir: str = "videos", transcripts_dir: str = "transcripts"
    ):
        """Initialize the response generator."""
        # Initialize retriever
        self.retriever = VideoRetriever(videos_dir, transcripts_dir)

        # Initialize Gemini
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-flash-002")

    def _format_context(self, results: List[Dict]) -> str:
        """Format search results into context for the model."""
        if not results:
            return ""

        # Sort by score in descending order
        sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
        context_parts = []

        for i, result in enumerate(sorted_results, 1):
            text = result["text"].strip()
            video = result["video"]
            time_range = (
                f"{result['timestamp']['start']} - {result['timestamp']['end']}"
            )
            score = result["score"]

            context_parts.append(
                f"[Segment {i} (Relevance: {score:.2f})] From video '{video}' at {time_range}:\n{text}"
            )

        return "\n\n".join(context_parts)

    def generate_response(
        self, query: str, k: int = 3, score_threshold: float = 0.70
    ) -> Dict:
        """
        Generate a response based on video transcripts.

        Args:
            query: User's question
            k: Number of relevant segments to retrieve
            score_threshold: Minimum similarity score threshold (default: 0.70)

        Returns:
            Dict with generated answer and source segments
        """
        try:
            # Get relevant segments
            results = self.retriever.search(
                query=query, k=k, score_threshold=score_threshold
            )

            if not results:
                return {
                    "answer": f"No relevant information found in the video transcripts (similarity threshold: {score_threshold}).",
                    "sources": [],
                }

            # Format context
            context = self._format_context(results)

            # Create prompt
            prompt = f"""Based on these video transcript segments, answer the question. Only use information from the provided segments:

Transcript segments:
{context}

Question: {query}

Instructions:
1. Answer directly and naturally without mentioning segments or sources
2. If the answer is not evident or information is insufficient, respond with: "I don't know."
3.Avoid speculating or adding information not present in the excerpts.
4. Be concise but informative
5. Don't make up information - only use what's in the transcripts
6. If there are contradictions, explain them naturally

Answer:"""

            # Generate response
            response = self.model.generate_content(prompt)

            return {
                "answer": response.text,
                "sources": results,
                # "context_used": context
            }

        except Exception as e:
            error_msg = str(e)
            print(f"Error generating response: {error_msg}")
            return {
                "answer": f"An error occurred while generating the response: {error_msg}",
                "sources": [],
                # "context_used": None
            }


def main():
    """Example usage."""
    # Initialize generator
    generator = VideoResponseGenerator()

    # Test queries
    test_queries = [
        "what is great gold spot?",
    ]

    # Test different thresholds
    thresholds = [0.70, 0.50]

    for threshold in thresholds:
        print(f"\n{'='*80}")
        print(f"Testing with similarity threshold: {threshold}")
        print("=" * 80)

        for query in test_queries:
            print(f"\n\n--- Query: '{query}' ---")

            # Generate response
            response = generator.generate_response(
                query=query, k=3, score_threshold=threshold
            )

            # Print results
            print("\nAnswer:")
            print(response["answer"])

            print("\nSources Used:")
            if response["sources"]:
                for i, source in enumerate(response["sources"], 1):
                    print(f"\n{i}. Video: {source['video']}")
                    print(
                        f"   Time: {source['timestamp']['start']} - {source['timestamp']['end']}"
                    )
                    print(f"   Score: {source['score']:.3f}")
                    print(f"   Text: {source['text'][:100]}...")
            else:
                print("No sources found.")

            print("\n" + "-" * 80)


if __name__ == "__main__":
    main()
