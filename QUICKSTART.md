# Quick Start Guide

Get up and running with Agentic AI Server in 5 minutes!

## Prerequisites

- Docker & Docker Compose installed
- OpenAI API Key (get one at https://platform.openai.com/)

## 5-Minute Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/jeonchulho/agentic-ai-server.git
cd agentic-ai-server
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-key-here
nano .env  # or use your favorite editor
```

### 3. Start the Server

**Option A: Using the start script (recommended)**

```bash
chmod +x start.sh
./start.sh
```

**Option B: Using Docker Compose directly**

```bash
docker-compose up -d
```

### 4. Verify Installation

```bash
# Check health status
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"v1","services":{"mysql":true,"redis":true,"milvus":true}}
```

### 5. Try Your First Request

**Summarize text:**

```bash
curl -X POST "http://localhost:8000/api/v1/summarize/text" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Artificial intelligence is transforming every industry. From healthcare to finance, AI is enabling new capabilities and improving efficiency. Machine learning models can now understand natural language, recognize images, and make complex decisions.",
    "max_length": 50
  }'
```

## Next Steps

### Explore the API

- **Interactive Documentation**: http://localhost:8000/docs
- **API Examples**: See [API_EXAMPLES.md](API_EXAMPLES.md)

### Upload and Process Documents

```bash
# Upload a document
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@your-document.pdf"

# Response will include document_id
# {"document_id": 1, "filename": "your-document.pdf", ...}

# Parse the document
curl -X POST "http://localhost:8000/api/v1/documents/parse/1"

# Summarize the document
curl -X POST "http://localhost:8000/api/v1/summarize/document" \
  -H "Content-Type: application/json" \
  -d '{"document_id": 1}'
```

### Translate Text

```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, world!",
    "source_language": "en",
    "target_language": "ko"
  }'
```

## Development Mode

For local development with hot reload:

```bash
# Start in development mode
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Or using Make
make docker-dev-up

# View logs
docker-compose logs -f app
```

## Supported Document Formats

- **PDF**: .pdf
- **Word**: .doc, .docx
- **PowerPoint**: .ppt, .pptx
- **Excel**: .xls, .xlsx
- **HWP**: .hwp (Korean Hancom Office)
- **Text**: .txt, .md, .log, .csv

## Common Issues

### Issue: Services not starting

```bash
# Check logs
docker-compose logs

# Restart services
docker-compose down
docker-compose up -d
```

### Issue: "Connection refused" errors

Wait a bit longer for services to initialize (can take 30-60 seconds on first run).

### Issue: Missing OpenAI API key

Make sure you've set `OPENAI_API_KEY` in your `.env` file.

## Useful Commands

```bash
# View all services status
docker-compose ps

# View logs
docker-compose logs -f app

# Stop all services
docker-compose down

# Rebuild and restart
docker-compose up -d --build

# Run tests
make test
```

## Architecture Overview

```
User Request → FastAPI → Service Layer → Agent Layer → AI Model
                ↓            ↓              ↓
            MySQL        Redis Cache    Milvus (Vector DB)
```

## Performance Tips

1. **Caching**: Results are automatically cached in Redis
2. **Batch Processing**: Process multiple documents in parallel
3. **Vector Search**: Use Milvus for semantic document search
4. **Resource Limits**: Adjust Docker resource limits for production

## Production Deployment

For production deployment:

1. **Use environment-specific .env files**
2. **Set strong passwords** for MySQL and Redis
3. **Enable authentication** and rate limiting
4. **Use reverse proxy** (nginx) with SSL
5. **Set up monitoring** and logging
6. **Configure backups** for MySQL and Milvus

See [README.md](README.md) for detailed production setup.

## Support

- **Documentation**: See [README.md](README.md)
- **API Examples**: See [API_EXAMPLES.md](API_EXAMPLES.md)
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md)
- **Issues**: https://github.com/jeonchulho/agentic-ai-server/issues

## What's Next?

- Explore advanced features in the [API documentation](http://localhost:8000/docs)
- Connect your legacy database for data analysis
- Build custom agents for your specific use cases
- Scale horizontally with Kubernetes

Happy coding! 🚀
