# Async Task Queue and Performance Enhancements

This document describes the async task queue implementation and performance optimizations added to the Agentic AI Server.

## Overview

The server now includes **Celery** for asynchronous task processing, enabling scalable handling of large-scale document processing, batch operations, and long-running AI tasks.

## Features Added

### 1. Async Task Queue (Celery)

#### Architecture
```
FastAPI (API Layer)
    ↓
Celery Tasks (Async Processing)
    ↓
Redis (Message Broker)
    ↓
Worker Processes (Parallel Execution)
```

#### Task Queues
- **documents**: Document parsing, processing, embedding generation
- **summarize**: Text and document summarization
- **translate**: Multi-language translation
- **analysis**: Legacy data analysis

#### Configuration
```python
# Task routing
task_routes = {
    "app.tasks.document_tasks.*": {"queue": "documents"},
    "app.tasks.summarize_tasks.*": {"queue": "summarize"},
    "app.tasks.translate_tasks.*": {"queue": "translate"},
    "app.tasks.analysis_tasks.*": {"queue": "analysis"},
}
```

### 2. Korean Language Optimization (HWP Files)

#### Enhanced HWP Parser
- **Multiple Encoding Support**: UTF-16, UTF-8, CP949, EUC-KR
- **Korean Character Detection**: Automatic detection of Hangul (한글) characters
- **Text Optimization**: Removes excessive whitespace and control characters
- **Fallback Strategy**: Tries multiple encodings if initial attempt fails

#### Configuration
```python
# In settings.py
ENABLE_KOREAN_OPTIMIZATION: bool = True
KOREAN_ENCODING: str = "utf-8"
HWP_FALLBACK_ENCODING: str = "cp949"
```

### 3. Smart Chunking for Large Files

#### Features
- **Sentence Boundary Awareness**: Preserves semantic coherence
- **Configurable Chunk Sizes**: Adjustable chunk size and overlap
- **Korean & English Support**: Handles both languages effectively
- **Automatic Splitting**: Handles sentences exceeding max chunk size

#### Configuration
```python
# In settings.py
CHUNK_SIZE: int = 1000          # Characters per chunk
CHUNK_OVERLAP: int = 100         # Overlap between chunks
MAX_CHUNK_SIZE: int = 2000       # Maximum chunk size
```

#### Chunking Strategy
```python
# Smart chunking process
1. Split text into sentences (Korean + English aware)
2. Group sentences into chunks maintaining size limits
3. Add overlap between chunks for context preservation
4. Handle extra-long sentences by splitting further
```

### 4. Query Optimization for Legacy DB

#### Features
- **Query Result Caching**: Redis-based caching of query results
- **Connection Pooling**: Optimized database connection management
- **Cache Key Generation**: MD5-based cache keys for queries
- **Configurable TTL**: Adjustable cache expiration

#### Configuration
```python
# In settings.py
ENABLE_QUERY_CACHE: bool = True
QUERY_CACHE_TTL: int = 300  # 5 minutes
```

#### Usage
```python
# Automatic caching
results = legacy_db_connector.execute_query(
    query="SELECT * FROM messages WHERE id > :id",
    params={"id": 1000},
    use_cache=True  # Enable caching
)
```

### 5. Enhanced Logging

#### Features
- **Structured Logging**: Using loguru for better log formatting
- **Multiple Log Levels**: DEBUG, INFO, WARNING, ERROR
- **File Rotation**: Daily log rotation with compression
- **Separate Error Logs**: Dedicated error log files
- **Request Logging**: Automatic logging of all HTTP requests with timing

#### Log Files
```
logs/
├── app_2024-01-08.log         # Daily application logs
├── app_2024-01-08.log.zip     # Compressed old logs
├── error_2024-01-08.log       # Error logs
└── error_2024-01-08.log.zip   # Compressed error logs
```

### 6. Performance Optimizations

#### Database Connection Pooling
```python
# MySQL with QueuePool
pool_size=10
max_overflow=20
pool_pre_ping=True
pool_recycle=3600
```

#### Batch Processing
- Parallel document processing
- Batch summarization
- Batch translation
- Configurable batch size

#### Configuration
```python
BATCH_SIZE: int = 100
MAX_CONCURRENT_TASKS: int = 10
MAX_WORKERS: int = 4
ASYNC_QUEUE_SIZE: int = 100
```

## Usage Examples

### Starting Celery Workers

```bash
# Start all workers
celery -A app.celery_config:celery_app worker --loglevel=info

# Start specific queue workers
celery -A app.celery_config:celery_app worker -Q documents --loglevel=info
celery -A app.celery_config:celery_app worker -Q summarize --loglevel=info
celery -A app.celery_config:celery_app worker -Q translate --loglevel=info
celery -A app.celery_config:celery_app worker -Q analysis --loglevel=info

# Start with concurrency
celery -A app.celery_config:celery_app worker --concurrency=4
```

### Async Task Submission

```python
from app.tasks import process_document_async, batch_process_documents

# Process single document asynchronously
task = process_document_async.delay(document_id=123)
result = task.get()  # Wait for result

# Batch process multiple documents
task = batch_process_documents.delay([1, 2, 3, 4, 5])
results = task.get()
```

### API Endpoints (Future Addition)

```bash
# Submit async task
POST /api/v1/documents/process-async/{document_id}
Response: {"task_id": "abc-123", "status": "pending"}

# Check task status
GET /api/v1/tasks/{task_id}
Response: {"task_id": "abc-123", "status": "completed", "result": {...}}

# Batch processing
POST /api/v1/documents/batch-process
Body: {"document_ids": [1, 2, 3, 4, 5]}
Response: {"task_id": "xyz-789", "status": "pending", "total": 5}
```

## Monitoring

### Celery Flower (Task Monitor)

```bash
# Install Flower
pip install flower

# Start Flower
celery -A app.celery_config:celery_app flower --port=5555

# Access dashboard
http://localhost:5555
```

### Redis Queue Monitoring

```bash
# Check queue length
redis-cli LLEN celery

# Monitor in real-time
redis-cli MONITOR
```

### Application Logs

```bash
# Tail application logs
tail -f logs/app_$(date +%Y-%m-%d).log

# Watch error logs
tail -f logs/error_$(date +%Y-%m-% d).log

# Search logs
grep "ERROR" logs/app_*.log
```

## Performance Metrics

### Before Optimizations
- Single document processing: ~5-10s
- Query response time: ~200-500ms
- Chunk quality: Fixed-size, context breaks
- Korean HWP parsing: Basic, single encoding

### After Optimizations
- Async document processing: Non-blocking API
- Cached query response: ~10-50ms
- Smart chunking: Semantic boundaries preserved
- Korean HWP parsing: Multi-encoding, optimized
- Batch processing: Parallel execution
- Query optimization: Connection pooling + caching

## Best Practices

### 1. Task Design
- Keep tasks idempotent
- Use task retries with exponential backoff
- Set appropriate time limits
- Handle errors gracefully

### 2. Caching Strategy
- Cache frequently accessed queries
- Set appropriate TTL
- Invalidate cache on updates
- Monitor cache hit rates

### 3. Chunking
- Use smart chunking for better semantic preservation
- Adjust chunk size based on use case
- Maintain overlap for context
- Consider language-specific boundaries

### 4. Logging
- Use appropriate log levels
- Include context in log messages
- Monitor error logs regularly
- Set up alerts for critical errors

### 5. Monitoring
- Monitor task queue lengths
- Track task success/failure rates
- Monitor resource usage
- Set up alerts for anomalies

## Configuration Reference

```python
# Celery
CELERY_BROKER_URL: str = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
CELERY_TASK_ALWAYS_EAGER: bool = False

# Chunking
CHUNK_SIZE: int = 1000
CHUNK_OVERLAP: int = 100
MAX_CHUNK_SIZE: int = 2000

# Korean Optimization
ENABLE_KOREAN_OPTIMIZATION: bool = True
KOREAN_ENCODING: str = "utf-8"
HWP_FALLBACK_ENCODING: str = "cp949"

# Query Caching
ENABLE_QUERY_CACHE: bool = True
QUERY_CACHE_TTL: int = 300

# Performance
BATCH_SIZE: int = 100
MAX_CONCURRENT_TASKS: int = 10
MAX_WORKERS: int = 4
```

## Troubleshooting

### Task Not Processing
- Check Celery worker status
- Verify Redis connection
- Check task queue length
- Review worker logs

### High Memory Usage
- Reduce batch size
- Adjust worker concurrency
- Implement task result expiration
- Monitor large document processing

### Cache Issues
- Verify Redis connectivity
- Check cache TTL settings
- Monitor cache memory usage
- Implement cache eviction policy

### Korean Text Issues
- Verify encoding settings
- Check HWP file format
- Enable Korean optimization
- Review parser logs

## Future Enhancements

- [ ] Priority queues for urgent tasks
- [ ] Task result persistence
- [ ] Advanced monitoring dashboard
- [ ] Auto-scaling workers
- [ ] Task scheduling (periodic tasks)
- [ ] Dead letter queue handling
- [ ] Circuit breaker pattern
- [ ] Rate limiting per user

---

**Last Updated**: 2024-01-08
