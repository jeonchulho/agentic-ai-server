"""
Base parser class for document parsing.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path


class BaseParser(ABC):
    """Abstract base class for document parsers."""
    
    def __init__(self):
        """Initialize parser."""
        self.supported_extensions = []
    
    @abstractmethod
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse document and extract content.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary containing parsed content and metadata
        """
        pass
    
    def is_supported(self, file_path: str) -> bool:
        """
        Check if file type is supported by this parser.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            True if supported, False otherwise
        """
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_extensions
    
    def validate_file(self, file_path: str) -> bool:
        """
        Validate that file exists and is readable.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            True if valid, False otherwise
        """
        path = Path(file_path)
        return path.exists() and path.is_file()
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract basic file metadata.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary containing metadata
        """
        path = Path(file_path)
        return {
            "filename": path.name,
            "extension": path.suffix,
            "size": path.stat().st_size if path.exists() else 0,
            "path": str(path.absolute())
        }


class ParserError(Exception):
    """Custom exception for parser errors."""
    pass
