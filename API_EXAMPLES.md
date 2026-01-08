# API Usage Examples

Complete examples for using the Agentic AI Server API.

## Base URL

```
http://localhost:8000/api/v1
```

## 1. Text Summarization

### Summarize Text

**Endpoint:** `POST /summarize/text`

```bash
curl -X POST "http://localhost:8000/api/v1/summarize/text" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "인공지능은 인간의 학습능력과 추론능력을 인공적으로 구현한 컴퓨터 시스템입니다. 최근 딥러닝 기술의 발전으로 이미지 인식, 자연어 처리, 음성 인식 등 다양한 분야에서 인간 수준의 성능을 보이고 있습니다.",
    "max_length": 50,
    "language": "ko"
  }'
```

**Response:**
```json
{
  "original_text": "인공지능은...",
  "summary": "인공지능은 인간의 능력을 구현한 시스템으로, 딥러닝 발전으로 다양한 분야에서 활용되고 있습니다.",
  "language": "ko",
  "created_at": "2024-01-08T12:00:00Z"
}
```

## 2. Translation

### Translate Text

**Endpoint:** `POST /translate`

```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "안녕하세요, 세계!",
    "source_language": "ko",
    "target_language": "en"
  }'
```

**Response:**
```json
{
  "source_text": "안녕하세요, 세계!",
  "translated_text": "Hello, world!",
  "source_language": "ko",
  "target_language": "en",
  "created_at": "2024-01-08T12:00:00Z"
}
```

### Supported Language Codes

- `en`: English
- `ko`: Korean
- `ja`: Japanese
- `zh`: Chinese
- `es`: Spanish
- `fr`: French
- `de`: German
- `ru`: Russian

## 3. Document Processing

### Upload Document

**Endpoint:** `POST /documents/upload`

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@document.pdf"
```

**Response:**
```json
{
  "document_id": 1,
  "filename": "document.pdf",
  "file_type": "pdf",
  "file_size": 152432,
  "status": "uploaded",
  "created_at": "2024-01-08T12:00:00Z"
}
```

### Parse Document

**Endpoint:** `POST /documents/parse/{document_id}`

```bash
curl -X POST "http://localhost:8000/api/v1/documents/parse/1"
```

**Response:**
```json
{
  "document_id": 1,
  "filename": "document.pdf",
  "content": "Extracted text content from the document...",
  "metadata": {
    "num_pages": 10,
    "size": 152432
  },
  "parser": "PDFParser"
}
```

### Process Document (Parse + Embed)

**Endpoint:** `POST /documents/process/{document_id}`

```bash
curl -X POST "http://localhost:8000/api/v1/documents/process/1"
```

**Response:**
```json
{
  "document_id": 1,
  "filename": "document.pdf",
  "num_chunks": 15,
  "num_embeddings": 15,
  "vector_stored": true,
  "message": "Document processed successfully"
}
```

### Summarize Document

**Endpoint:** `POST /summarize/document`

```bash
curl -X POST "http://localhost:8000/api/v1/summarize/document" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": 1,
    "max_length": 200
  }'
```

**Response:**
```json
{
  "document_id": 1,
  "filename": "document.pdf",
  "summary": "This document discusses...",
  "created_at": "2024-01-08T12:00:00Z"
}
```

### Delete Document

**Endpoint:** `DELETE /documents/{document_id}`

```bash
curl -X DELETE "http://localhost:8000/api/v1/documents/1"
```

**Response:**
```json
{
  "document_id": 1,
  "message": "Document deleted successfully"
}
```

## 4. Legacy Data Operations

### Get Legacy Data

**Endpoint:** `POST /legacy/data`

```bash
curl -X POST "http://localhost:8000/api/v1/legacy/data" \
  -H "Content-Type: application/json" \
  -d '{
    "data_type": "messages",
    "limit": 10,
    "offset": 0
  }'
```

**Response:**
```json
{
  "data_type": "messages",
  "records": [
    {
      "id": 1,
      "sender_id": 123,
      "receiver_id": 456,
      "content": "Hello!",
      "created_at": "2024-01-01T10:00:00"
    }
  ],
  "count": 10
}
```

### Get Legacy Data Summary

**Endpoint:** `GET /legacy/summary/{data_type}`

```bash
curl -X GET "http://localhost:8000/api/v1/legacy/summary/messages?use_cache=true"
```

**Response:**
```json
{
  "data_type": "messages",
  "summary": "The messages dataset contains communication between users...",
  "record_count": 1520,
  "created_at": "2024-01-08T12:00:00Z"
}
```

### Analyze Legacy Data

**Endpoint:** `POST /legacy/analyze`

```bash
curl -X POST "http://localhost:8000/api/v1/legacy/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "data_type": "projects",
    "limit": 50
  }'
```

**Response:**
```json
{
  "data_type": "projects",
  "record_count": 50,
  "analysis": "Key insights from the projects data..."
}
```

### Get Legacy Statistics

**Endpoint:** `GET /legacy/statistics`

```bash
curl -X GET "http://localhost:8000/api/v1/legacy/statistics"
```

**Response:**
```json
{
  "statistics": {
    "messages": 1520,
    "chats": 3240,
    "schedules": 890,
    "emails": 4560,
    "projects": 125
  },
  "total_records": 10335
}
```

## 5. System Endpoints

### Health Check

**Endpoint:** `GET /health`

```bash
curl -X GET "http://localhost:8000/health"
```

**Response:**
```json
{
  "status": "healthy",
  "version": "v1",
  "services": {
    "mysql": true,
    "redis": true,
    "milvus": true
  }
}
```

### Root Endpoint

**Endpoint:** `GET /`

```bash
curl -X GET "http://localhost:8000/"
```

**Response:**
```json
{
  "name": "Agentic AI Server",
  "version": "v1",
  "status": "running",
  "docs": "/docs",
  "health": "/health"
}
```

## Python SDK Example

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# Summarize text
response = requests.post(
    f"{BASE_URL}/summarize/text",
    json={
        "text": "Your long text here...",
        "max_length": 100
    }
)
result = response.json()
print(result["summary"])

# Translate text
response = requests.post(
    f"{BASE_URL}/translate",
    json={
        "text": "Hello, world!",
        "source_language": "en",
        "target_language": "ko"
    }
)
result = response.json()
print(result["translated_text"])

# Upload and process document
with open("document.pdf", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/documents/upload",
        files={"file": f}
    )
doc_id = response.json()["document_id"]

# Parse document
response = requests.post(f"{BASE_URL}/documents/parse/{doc_id}")
content = response.json()["content"]
print(content)
```

## Error Handling

All endpoints return standard HTTP status codes:

- `200`: Success
- `400`: Bad Request (invalid input)
- `404`: Not Found
- `422`: Validation Error
- `500`: Internal Server Error

**Error Response Format:**
```json
{
  "detail": "Error message describing what went wrong"
}
```
