"""
Text file parser.
"""
from typing import Dict, Any
import chardet
from .base_parser import BaseParser, ParserError


class TextParser(BaseParser):
    """Parser for text files."""
    
    def __init__(self):
        """Initialize text parser."""
        super().__init__()
        self.supported_extensions = [".txt", ".text", ".md", ".markdown", ".log", ".csv"]
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse text file and extract content.
        
        Args:
            file_path: Path to the text file
            
        Returns:
            Dictionary containing parsed content and metadata
        """
        if not self.validate_file(file_path):
            raise ParserError(f"Invalid or missing file: {file_path}")
        
        if not self.is_supported(file_path):
            raise ParserError(f"Unsupported file type for text parser: {file_path}")
        
        try:
            # Detect encoding
            encoding = self._detect_encoding(file_path)
            
            # Read file content
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
            
            # Get metadata
            metadata = self.extract_metadata(file_path)
            metadata.update({
                "encoding": encoding,
                "num_lines": content.count("\n") + 1,
                "num_characters": len(content)
            })
            
            return {
                "content": content,
                "metadata": metadata,
                "parser": "TextParser"
            }
        except Exception as e:
            raise ParserError(f"Failed to parse text file: {str(e)}")
    
    def _detect_encoding(self, file_path: str) -> str:
        """
        Detect file encoding using chardet.
        
        Args:
            file_path: Path to the text file
            
        Returns:
            Detected encoding name
        """
        try:
            with open(file_path, "rb") as f:
                raw_data = f.read()
            
            result = chardet.detect(raw_data)
            encoding = result["encoding"]
            
            # Default to utf-8 if detection fails
            return encoding if encoding else "utf-8"
        except Exception:
            return "utf-8"
