"""
PDF document parser.
"""
from typing import Dict, Any
import PyPDF2
import pdfplumber
from .base_parser import BaseParser, ParserError


class PDFParser(BaseParser):
    """Parser for PDF documents."""
    
    def __init__(self):
        """Initialize PDF parser."""
        super().__init__()
        self.supported_extensions = [".pdf"]
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse PDF document and extract content.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dictionary containing parsed content and metadata
        """
        if not self.validate_file(file_path):
            raise ParserError(f"Invalid or missing file: {file_path}")
        
        if not self.is_supported(file_path):
            raise ParserError(f"Unsupported file type for PDF parser: {file_path}")
        
        try:
            # Extract text using pdfplumber (better for complex layouts)
            text_content = self._extract_with_pdfplumber(file_path)
            
            # Get metadata
            metadata = self._extract_pdf_metadata(file_path)
            
            return {
                "content": text_content,
                "metadata": metadata,
                "parser": "PDFParser"
            }
        except Exception as e:
            raise ParserError(f"Failed to parse PDF: {str(e)}")
    
    def _extract_with_pdfplumber(self, file_path: str) -> str:
        """Extract text using pdfplumber."""
        text_parts = []
        
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    def _extract_pdf_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract PDF metadata."""
        metadata = self.extract_metadata(file_path)
        
        try:
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                metadata.update({
                    "num_pages": len(pdf_reader.pages),
                    "pdf_metadata": pdf_reader.metadata or {}
                })
        except Exception as e:
            metadata["pdf_metadata"] = {}
            metadata["num_pages"] = 0
        
        return metadata
