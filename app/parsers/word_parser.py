"""
Word document parser.
"""
from typing import Dict, Any
from docx import Document
from .base_parser import BaseParser, ParserError


class WordParser(BaseParser):
    """Parser for Word documents."""
    
    def __init__(self):
        """Initialize Word parser."""
        super().__init__()
        self.supported_extensions = [".doc", ".docx"]
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse Word document and extract content.
        
        Args:
            file_path: Path to the Word file
            
        Returns:
            Dictionary containing parsed content and metadata
        """
        if not self.validate_file(file_path):
            raise ParserError(f"Invalid or missing file: {file_path}")
        
        if not self.is_supported(file_path):
            raise ParserError(f"Unsupported file type for Word parser: {file_path}")
        
        try:
            doc = Document(file_path)
            
            # Extract text from paragraphs
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            
            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text for cell in row.cells)
                    if row_text.strip():
                        text_parts.append(row_text)
            
            content = "\n\n".join(text_parts)
            
            # Get metadata
            metadata = self.extract_metadata(file_path)
            metadata.update({
                "num_paragraphs": len(doc.paragraphs),
                "num_tables": len(doc.tables),
                "core_properties": self._extract_core_properties(doc)
            })
            
            return {
                "content": content,
                "metadata": metadata,
                "parser": "WordParser"
            }
        except Exception as e:
            raise ParserError(f"Failed to parse Word document: {str(e)}")
    
    def _extract_core_properties(self, doc: Document) -> Dict[str, Any]:
        """Extract core properties from Word document."""
        try:
            props = doc.core_properties
            return {
                "author": props.author or "",
                "title": props.title or "",
                "subject": props.subject or "",
                "created": str(props.created) if props.created else "",
                "modified": str(props.modified) if props.modified else ""
            }
        except Exception:
            return {}
