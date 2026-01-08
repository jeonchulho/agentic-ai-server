"""
Document parser factory and utilities.
"""
from typing import Dict, Any, Optional
from pathlib import Path
from .base_parser import BaseParser, ParserError
from .pdf_parser import PDFParser
from .word_parser import WordParser
from .ppt_parser import PPTParser
from .excel_parser import ExcelParser
from .hwp_parser import HWPParser
from .text_parser import TextParser


class ParserFactory:
    """Factory class for creating appropriate document parsers."""
    
    def __init__(self):
        """Initialize parser factory with available parsers."""
        self.parsers = [
            PDFParser(),
            WordParser(),
            PPTParser(),
            ExcelParser(),
            HWPParser(),
            TextParser()
        ]
    
    def get_parser(self, file_path: str) -> Optional[BaseParser]:
        """
        Get appropriate parser for the given file.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Parser instance or None if no suitable parser found
        """
        for parser in self.parsers:
            if parser.is_supported(file_path):
                return parser
        return None
    
    def parse_document(self, file_path: str) -> Dict[str, Any]:
        """
        Parse document using appropriate parser.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary containing parsed content and metadata
            
        Raises:
            ParserError: If no suitable parser found or parsing fails
        """
        parser = self.get_parser(file_path)
        
        if not parser:
            file_ext = Path(file_path).suffix
            raise ParserError(f"No parser available for file type: {file_ext}")
        
        return parser.parse(file_path)


# Global factory instance
parser_factory = ParserFactory()


__all__ = [
    "BaseParser",
    "PDFParser",
    "WordParser",
    "PPTParser",
    "ExcelParser",
    "HWPParser",
    "TextParser",
    "ParserFactory",
    "ParserError",
    "parser_factory"
]
