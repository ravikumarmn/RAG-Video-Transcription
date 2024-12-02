# RAG Video Transcription System

A system for processing, indexing, and searching video transcripts using Retrieval Augmented Generation (RAG) with Elasticsearch.

## Overview

This system processes video files along with their VTT transcripts, segments them, and indexes them in Elasticsearch for efficient retrieval. Each video segment is embedded using OpenAI's text embedding model for semantic search capabilities.

## Project Structure

```
.
├── config/
│   └── index_metadata.json    # Metadata configuration for videos and transcripts
├── data/
│   ├── videos/               # Video files (.mp4)
│   └── transcripts/          # Transcript files (.vtt)
└── src/
    ├── upsert_videos.py      # Main script for processing videos
    ├── vector_store.py       # Elasticsearch integration
    └── transcript_processor.py # VTT transcript processing
```

## Features

- Video and transcript processing
- Automatic segment extraction from VTT files
- Elasticsearch indexing with embeddings
- Configurable metadata support
- Batch processing with error handling
- Case-insensitive transcript matching

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure Elasticsearch:
   - Ensure Elasticsearch is running at http://localhost:9200
   - Default credentials: 
     - Username: elastic
     - Password: changeme

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your OpenAI API key and other settings
   ```

## Docker Setup

### Prerequisites
- Docker
- Docker Compose

### Quick Start with Docker

1. Start Elasticsearch using Docker:
   ```bash
   # Pull and run Elasticsearch
   docker run -d \
     --name elasticsearch \
     -p 9200:9200 \
     -p 9300:9300 \
     -e "discovery.type=single-node" \
     -e "xpack.security.enabled=true" \
     -e "ELASTIC_PASSWORD=changeme" \
     docker.elastic.co/elasticsearch/elasticsearch:8.11.1
   ```

2. Wait for Elasticsearch to start (usually takes about 30 seconds), then verify:
   ```bash
   # Check if Elasticsearch is running
   curl -u elastic:changeme http://localhost:9200
   ```

3. Build and run the application container:
   ```bash
   # Build the Docker image
   docker build -t rag-video-transcription .

   # Run the container
   docker run -d \
     --name rag-video-app \
     --link elasticsearch \
     -e ELASTICSEARCH_URL=http://elasticsearch:9200 \
     -e ELASTICSEARCH_USER=elastic \
     -e ELASTICSEARCH_PASSWORD=changeme \
     -e OPENAI_API_KEY=your_api_key_here \
     -v $(pwd)/data:/app/data \
     rag-video-transcription
   ```

### Using Docker Compose

1. Create a `.env` file with your configuration:
   ```bash
   ELASTICSEARCH_URL=http://elasticsearch:9200
   ELASTICSEARCH_USER=elastic
   ELASTICSEARCH_PASSWORD=changeme
   OPENAI_API_KEY=your_api_key_here
   ```

2. Start all services using Docker Compose:
   ```bash
   docker-compose up -d
   ```

3. Monitor the logs:
   ```bash
   # View all logs
   docker-compose logs -f

   # View only app logs
   docker-compose logs -f app
   ```

4. Stop all services:
   ```bash
   docker-compose down
   ```

### Docker Commands Reference

```bash
# List running containers
docker ps

# View container logs
docker logs elasticsearch
docker logs rag-video-app

# Stop containers
docker stop elasticsearch rag-video-app

# Remove containers
docker rm elasticsearch rag-video-app

# Remove all stopped containers and unused images
docker system prune
```

### Troubleshooting Docker Setup

1. If Elasticsearch fails to start:
   ```bash
   # Increase virtual memory for Elasticsearch
   sudo sysctl -w vm.max_map_count=262144
   ```

2. If you can't connect to Elasticsearch:
   ```bash
   # Check Elasticsearch logs
   docker logs elasticsearch

   # Verify network connectivity
   docker network inspect bridge
   ```

3. Reset everything and start fresh:
   ```bash
   # Stop and remove all containers
   docker-compose down
   docker system prune -f
   
   # Start fresh
   docker-compose up -d
   ```

## Usage

1. Place your video files in `data/videos/`
2. Place corresponding VTT transcripts in `data/transcripts/`
3. Update metadata in `config/index_metadata.json`:
   ```json
   {
     "transcript_metadata": [
       {
         "video_path": "example.mp4",
         "transcript_path": "example.vtt",
         "title": "Video Title",
         "description": "Video Description"
       }
     ]
   }
   ```

4. Run the indexing script:
   ```bash
   python src/upsert_videos.py
   ```

## Metadata Format

The system expects metadata in the following format in `config/index_metadata.json`:

```json
{
  "transcript_metadata": [
    {
      "video_path": "python_tutor.mp4",
      "transcript_path": "python_tutor.vtt",
      "title": "Python Tutorials",
      "description": "Python Tutorials along with macbook airpod no Desktop no cooler"
    },
    {
      "video_path": "GreatRedSpot.mp4",
      "transcript_path": "GreatRedSpot.vtt",
      "title": "Great Red Spot",
      "description": "Python Tutorials along with macbook airpod no Desktop no cooler"
    }
  ]
}
```

## Error Handling

The system includes robust error handling for:
- Missing video/transcript files
- Transcript matching issues
- Elasticsearch indexing failures
- Invalid segment data

Failed operations are logged with specific error messages for debugging.

## Performance

- Batch processing with configurable batch sizes
- Optimized index settings for fast retrieval
- Efficient transcript matching algorithms
- Parallel processing capabilities

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.