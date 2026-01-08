"""
Document processing service layer.
"""
from typing import Dict, Any
import os
import shutil
from pathlib import Path
from app.agents.document_agent import document_agent
from app.database.mysql_client import mysql_client, Document as DocumentModel
from app.database.milvus_client import milvus_client
from app.config import get_settings
from datetime import datetime

settings = get_settings()


class DocumentService:
    """Service for document processing."""
    
    def __init__(self):
        """Initialize service."""
        self.agent = document_agent
        self.db_client = mysql_client
        self.vector_client = milvus_client
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    async def upload_document(
        self,
        file_content: bytes,
        filename: str
    ) -> Dict[str, Any]:
        """
        Upload and save document file.
        
        Args:
            file_content: File content bytes
            file_content: Original filename
            
        Returns:
            Dictionary with upload result
        """
        try:
            # Generate unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            file_ext = Path(filename).suffix
            unique_filename = f"{timestamp}_{filename}"
            file_path = self.upload_dir / unique_filename
            
            # Save file
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            file_size = len(file_content)
            file_type = file_ext.lstrip(".")
            
            # Save to database
            session = self.db_client.get_session()
            try:
                doc_record = DocumentModel(
                    filename=filename,
                    file_type=file_type,
                    file_path=str(file_path),
                    file_size=file_size,
                    created_at=datetime.utcnow()
                )
                session.add(doc_record)
                session.commit()
                
                return {
                    "document_id": doc_record.id,
                    "filename": filename,
                    "file_type": file_type,
                    "file_size": file_size,
                    "file_path": str(file_path),
                    "status": "uploaded",
                    "success": True
                }
            except Exception as e:
                session.rollback()
                # Clean up file if database save fails
                if file_path.exists():
                    file_path.unlink()
                raise e
            finally:
                session.close()
        except Exception as e:
            return {
                "filename": filename,
                "error": str(e),
                "success": False
            }
    
    async def parse_document(self, document_id: int) -> Dict[str, Any]:
        """
        Parse uploaded document.
        
        Args:
            document_id: Document ID
            
        Returns:
            Dictionary with parsing result
        """
        # Get document from database
        session = self.db_client.get_session()
        try:
            doc_record = session.query(DocumentModel).filter(DocumentModel.id == document_id).first()
            
            if not doc_record:
                return {
                    "error": "Document not found",
                    "success": False
                }
            
            file_path = doc_record.file_path
            
            # Parse document
            result = await self.agent.parse_document(file_path)
            
            if result.get("success"):
                # Save parsed content to database
                doc_record.parsed_content = result.get("content", "")[:10000]  # Store first 10k chars
                doc_record.metadata = result.get("metadata", {})
                session.commit()
                
                result["document_id"] = document_id
                result["filename"] = doc_record.filename
            
            return result
        except Exception as e:
            session.rollback()
            return {
                "document_id": document_id,
                "error": str(e),
                "success": False
            }
        finally:
            session.close()
    
    async def process_and_embed_document(self, document_id: int) -> Dict[str, Any]:
        """
        Process document and generate embeddings for vector search.
        
        Args:
            document_id: Document ID
            
        Returns:
            Dictionary with processing result
        """
        # Get document from database
        session = self.db_client.get_session()
        try:
            doc_record = session.query(DocumentModel).filter(DocumentModel.id == document_id).first()
            
            if not doc_record:
                return {
                    "error": "Document not found",
                    "success": False
                }
            
            file_path = doc_record.file_path
            
            # Process document (parse, chunk, embed)
            result = await self.agent.process_document(file_path, generate_embeddings=True)
            
            if result.get("success") and result.get("embeddings"):
                # Store embeddings in Milvus
                document_ids = [document_id] * len(result["chunks"])
                chunks = result["chunks"]
                embeddings = result["embeddings"]
                
                self.vector_client.insert(document_ids, chunks, embeddings)
                
                result["document_id"] = document_id
                result["filename"] = doc_record.filename
                result["vector_stored"] = True
            
            return result
        except Exception as e:
            return {
                "document_id": document_id,
                "error": str(e),
                "success": False
            }
        finally:
            session.close()
    
    def delete_document(self, document_id: int) -> Dict[str, Any]:
        """
        Delete document and its associated data.
        
        Args:
            document_id: Document ID
            
        Returns:
            Dictionary with deletion result
        """
        session = self.db_client.get_session()
        try:
            doc_record = session.query(DocumentModel).filter(DocumentModel.id == document_id).first()
            
            if not doc_record:
                return {
                    "error": "Document not found",
                    "success": False
                }
            
            # Delete file
            file_path = Path(doc_record.file_path)
            if file_path.exists():
                file_path.unlink()
            
            # Delete from Milvus
            self.vector_client.delete(f"document_id == {document_id}")
            
            # Delete from database
            session.delete(doc_record)
            session.commit()
            
            return {
                "document_id": document_id,
                "message": "Document deleted successfully",
                "success": True
            }
        except Exception as e:
            session.rollback()
            return {
                "document_id": document_id,
                "error": str(e),
                "success": False
            }
        finally:
            session.close()


# Global service instance
document_service = DocumentService()
