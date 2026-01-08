"""
Document processing agent with improved chunking for large files.
"""
from typing import Dict, Any, List
from app.parsers import parser_factory
from sentence_transformers import SentenceTransformer
from app.config import get_settings
from loguru import logger
import re

settings = get_settings()


class DocumentAgent:
    """Agent for document processing and embedding generation."""
    
    def __init__(self):
        """Initialize document agent."""
        self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info(f"Initialized DocumentAgent with embedding model: {settings.EMBEDDING_MODEL}")
    
    async def parse_document(self, file_path: str) -> Dict[str, Any]:
        """
        Parse document and extract content.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary with parsed content and metadata
        """
        try:
            logger.info(f"Parsing document: {file_path}")
            result = parser_factory.parse_document(file_path)
            logger.info(f"Successfully parsed document: {file_path}")
            return {
                "content": result.get("content", ""),
                "metadata": result.get("metadata", {}),
                "parser": result.get("parser", ""),
                "success": True
            }
        except Exception as e:
            logger.error(f"Failed to parse document {file_path}: {str(e)}")
            return {
                "content": "",
                "metadata": {},
                "parser": "",
                "error": str(e),
                "success": False
            }
    
    def generate_embeddings(self, text: str) -> list[float]:
        """
        Generate embeddings for text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of embedding values
        """
        try:
            embedding = self.embedding_model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return []
    
    def chunk_text_smart(
        self,
        text: str,
        chunk_size: int = None,
        overlap: int = None,
        max_chunk_size: int = None
    ) -> List[str]:
        """
        Smart text chunking with sentence boundary awareness for large files.
        
        This method prioritizes sentence boundaries to maintain semantic coherence.
        Optimized for Korean and English text.
        
        Args:
            text: Text to chunk
            chunk_size: Target size of each chunk in characters
            overlap: Overlap between chunks
            max_chunk_size: Maximum allowed chunk size
            
        Returns:
            List of text chunks
        """
        chunk_size = chunk_size or settings.CHUNK_SIZE
        overlap = overlap or settings.CHUNK_OVERLAP
        max_chunk_size = max_chunk_size or settings.MAX_CHUNK_SIZE
        
        # Split text into sentences (supports Korean and English)
        sentences = self._split_sentences(text)
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # If single sentence exceeds max_chunk_size, split it
            if sentence_length > max_chunk_size:
                # Save current chunk if exists
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                # Split long sentence into smaller pieces
                for i in range(0, len(sentence), max_chunk_size - overlap):
                    chunks.append(sentence[i:i + max_chunk_size])
                continue
            
            # Check if adding this sentence would exceed chunk_size
            if current_length + sentence_length > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                
                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(current_chunk, overlap)
                current_chunk = overlap_sentences
                current_length = sum(len(s) for s in current_chunk)
            
            current_chunk.append(sentence)
            current_length += sentence_length
        
        # Add remaining chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        logger.info(f"Chunked text into {len(chunks)} chunks (avg size: {sum(len(c) for c in chunks) / len(chunks):.0f} chars)")
        return chunks
    
    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences, supporting both Korean and English.
        
        Args:
            text: Text to split
            
        Returns:
            List of sentences
        """
        # Pattern for sentence boundaries (supports Korean and English)
        # Korean: ., !, ?, 。
        # English: ., !, ?
        sentence_pattern = r'[^.!?。]+[.!?。]+'
        
        sentences = re.findall(sentence_pattern, text)
        
        # If no sentences found, split by newlines
        if not sentences:
            sentences = [s.strip() for s in text.split('\n') if s.strip()]
        
        # If still no sentences, use fixed-size chunks
        if not sentences:
            sentences = [text[i:i+500] for i in range(0, len(text), 500)]
        
        return sentences
    
    def _get_overlap_sentences(self, sentences: List[str], overlap: int) -> List[str]:
        """
        Get last few sentences for overlap based on character count.
        
        Args:
            sentences: List of sentences
            overlap: Target overlap in characters
            
        Returns:
            List of sentences for overlap
        """
        overlap_sentences = []
        char_count = 0
        
        for sentence in reversed(sentences):
            if char_count >= overlap:
                break
            overlap_sentences.insert(0, sentence)
            char_count += len(sentence)
        
        return overlap_sentences
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """
        Simple text chunking (kept for backward compatibility).
        
        Args:
            text: Text to chunk
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        # Use smart chunking by default
        return self.chunk_text_smart(text, chunk_size, overlap)
    
    async def process_document(
        self,
        file_path: str,
        generate_embeddings: bool = True
    ) -> Dict[str, Any]:
        """
        Process document: parse, chunk, and generate embeddings.
        Optimized for large files with smart chunking.
        
        Args:
            file_path: Path to the document file
            generate_embeddings: Whether to generate embeddings
            
        Returns:
            Dictionary with processed document data
        """
        logger.info(f"Processing document: {file_path}")
        
        # Parse document
        parse_result = await self.parse_document(file_path)
        
        if not parse_result.get("success"):
            return parse_result
        
        content = parse_result.get("content", "")
        
        # Smart chunking for better semantic preservation
        chunks = self.chunk_text_smart(content)
        
        # Generate embeddings if requested
        embeddings = []
        if generate_embeddings and chunks:
            logger.info(f"Generating embeddings for {len(chunks)} chunks")
            for i, chunk in enumerate(chunks):
                embedding = self.generate_embeddings(chunk)
                if embedding:
                    embeddings.append(embedding)
                
                # Log progress for large documents
                if (i + 1) % 10 == 0:
                    logger.debug(f"Generated {i + 1}/{len(chunks)} embeddings")
        
        logger.info(f"Document processing complete: {len(chunks)} chunks, {len(embeddings)} embeddings")
        
        return {
            "content": content,
            "chunks": chunks,
            "embeddings": embeddings,
            "metadata": parse_result.get("metadata", {}),
            "parser": parse_result.get("parser", ""),
            "num_chunks": len(chunks),
            "num_embeddings": len(embeddings),
            "success": True
        }


# Global agent instance
document_agent = DocumentAgent()
