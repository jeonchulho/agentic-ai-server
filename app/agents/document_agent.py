"""
Document processing agent.
"""
from typing import Dict, Any
from app.parsers import parser_factory
from sentence_transformers import SentenceTransformer
from app.config import get_settings

settings = get_settings()


class DocumentAgent:
    """Agent for document processing and embedding generation."""
    
    def __init__(self):
        """Initialize document agent."""
        self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
    
    async def parse_document(self, file_path: str) -> Dict[str, Any]:
        """
        Parse document and extract content.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary with parsed content and metadata
        """
        try:
            result = parser_factory.parse_document(file_path)
            return {
                "content": result.get("content", ""),
                "metadata": result.get("metadata", {}),
                "parser": result.get("parser", ""),
                "success": True
            }
        except Exception as e:
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
            print(f"Embedding generation error: {e}")
            return []
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """
        Split text into chunks for processing.
        
        Args:
            text: Text to chunk
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            chunk = text[start:end]
            
            if chunk.strip():
                chunks.append(chunk)
            
            start += (chunk_size - overlap)
        
        return chunks
    
    async def process_document(
        self,
        file_path: str,
        generate_embeddings: bool = True
    ) -> Dict[str, Any]:
        """
        Process document: parse, chunk, and generate embeddings.
        
        Args:
            file_path: Path to the document file
            generate_embeddings: Whether to generate embeddings
            
        Returns:
            Dictionary with processed document data
        """
        # Parse document
        parse_result = await self.parse_document(file_path)
        
        if not parse_result.get("success"):
            return parse_result
        
        content = parse_result.get("content", "")
        
        # Chunk text for better processing
        chunks = self.chunk_text(content)
        
        # Generate embeddings if requested
        embeddings = []
        if generate_embeddings and chunks:
            for chunk in chunks:
                embedding = self.generate_embeddings(chunk)
                if embedding:
                    embeddings.append(embedding)
        
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
