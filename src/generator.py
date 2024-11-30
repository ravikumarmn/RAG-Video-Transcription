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
    def __init__(self, videos_dir: str = "videos", transcripts_dir: str = "transcripts"):
        """Initialize the response generator."""
        # Initialize retriever
        self.retriever = VideoRetriever(videos_dir, transcripts_dir)
        
        # Initialize Gemini
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
            
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')

    def _format_context(self, results: List[Dict]) -> str:
        """Format search results into context for the model."""
        context_parts = []
        
        for result in results:
            text = result["text"]
            video = result["video"]
            time_range = f"{result['timestamp']['start']} - {result['timestamp']['end']}"
            
            context_parts.append(
                f"From video '{video}' at {time_range}:\n{text}"
            )
        
        return "\n\n".join(context_parts)

    def generate_response(self, query: str, k: int = 3) -> Dict:
        """
        Generate a response based on video transcripts.
        
        Args:
            query: User's question
            k: Number of relevant segments to retrieve
            
        Returns:
            Dict with generated answer and source segments
        """
        try:
            # Get relevant segments
            results = self.retriever.search(query, k=k)
            if not results:
                return {
                    "answer": "No relevant information found in the video transcripts.",
                    "sources": []
                }

            # Format context
            context = self._format_context(results)
            
            # Create prompt
            prompt = f"""Based on these video transcript segments, answer the question. Only use information from the provided segments:

Transcript segments:
{context}

Question: {query}

Instructions:
1. Use only information from the transcript segments
2. If the segments don't fully answer the question, acknowledge this
3. Be concise but informative

Answer:"""

            # Generate response
            response = self.model.generate_content(prompt)
            
            return {
                "answer": response.text,
                "sources": results
            }

        except Exception as e:
            print(f"Error generating response: {e}")
            return {
                "answer": "An error occurred while generating the response.",
                "sources": []
            }


def main():
    """Example usage."""
    # Initialize generator
    generator = VideoResponseGenerator()
    
    # Example query
    query = "llamaindex"
    print(f"\nQuestion: {query}")
    
    # Generate response
    response = generator.generate_response(query)
    
    # Display results
    print("\nAnswer:")
    print(response["answer"])
    
    print("\nSources:")
    for source in response["sources"]:
        print(f"\nFrom {source['video']} ({source['timestamp']['start']} - {source['timestamp']['end']}):")
        print(source["text"])


if __name__ == "__main__":
    main()
