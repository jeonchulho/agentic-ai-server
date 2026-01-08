"""
HWP (한글) document parser with Korean language optimization.
"""
from typing import Dict, Any, List
import olefile
from .base_parser import BaseParser, ParserError
from app.config import get_settings

settings = get_settings()


class HWPParser(BaseParser):
    """Parser for HWP (Hancom Office) documents with Korean optimization."""
    
    def __init__(self):
        """Initialize HWP parser."""
        super().__init__()
        self.supported_extensions = [".hwp"]
        self.korean_encodings = ["utf-16", "utf-8", "cp949", "euc-kr"]
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse HWP document and extract content with Korean optimization.
        
        Args:
            file_path: Path to the HWP file
            
        Returns:
            Dictionary containing parsed content and metadata
        """
        if not self.validate_file(file_path):
            raise ParserError(f"Invalid or missing file: {file_path}")
        
        if not self.is_supported(file_path):
            raise ParserError(f"Unsupported file type for HWP parser: {file_path}")
        
        try:
            # Try to parse HWP file using olefile with Korean optimization
            content = self._extract_with_olefile(file_path)
            
            # Post-process Korean text
            if settings.ENABLE_KOREAN_OPTIMIZATION:
                content = self._optimize_korean_text(content)
            
            # Get metadata
            metadata = self.extract_metadata(file_path)
            metadata.update({
                "format": "HWP",
                "encoding": "utf-8",
                "korean_optimized": settings.ENABLE_KOREAN_OPTIMIZATION
            })
            
            return {
                "content": content,
                "metadata": metadata,
                "parser": "HWPParser",
                "success": True
            }
        except Exception as e:
            raise ParserError(f"Failed to parse HWP document: {str(e)}")
    
    def _extract_with_olefile(self, file_path: str) -> str:
        """
        Extract text from HWP file using olefile with multiple encoding attempts.
        
        Optimized for Korean text extraction.
        """
        try:
            if not olefile.isOleFile(file_path):
                raise ParserError("File is not a valid OLE file")
            
            ole = olefile.OleFileIO(file_path)
            
            # Try to extract text from common HWP streams
            text_parts = []
            
            # List all streams in the file
            for stream in ole.listdir():
                stream_name = "/".join(stream)
                
                # Look for text content streams
                if "BodyText" in stream_name or "PrvText" in stream_name or "Section" in stream_name:
                    try:
                        data = ole.openstream(stream).read()
                        
                        # Try multiple Korean-compatible encodings
                        decoded_text = self._try_decode_korean(data)
                        if decoded_text:
                            text_parts.append(decoded_text)
                    except Exception as e:
                        # Continue with other streams even if one fails
                        continue
            
            ole.close()
            
            if text_parts:
                return "\n\n".join(text_parts)
            else:
                return "[HWP content - requires advanced parsing or hwp5 library]"
        except Exception as e:
            raise ParserError(f"Failed to extract HWP content: {str(e)}")
    
    def _try_decode_korean(self, data: bytes) -> str:
        """
        Try to decode bytes using multiple Korean-compatible encodings.
        
        Args:
            data: Raw bytes from HWP file
            
        Returns:
            Decoded text or empty string if all attempts fail
        """
        for encoding in self.korean_encodings:
            try:
                text = data.decode(encoding, errors="ignore")
                # Check if decoded text contains Korean characters or is meaningful
                if text and (self._contains_korean(text) or len(text.strip()) > 10):
                    return text
            except:
                continue
        
        return ""
    
    def _contains_korean(self, text: str) -> bool:
        """
        Check if text contains Korean characters (Hangul).
        
        Args:
            text: Text to check
            
        Returns:
            True if text contains Korean characters
        """
        for char in text:
            if '\uac00' <= char <= '\ud7a3':  # Hangul syllables range
                return True
        return False
    
    def _optimize_korean_text(self, text: str) -> str:
        """
        Optimize Korean text by removing unnecessary characters and normalizing.
        
        Args:
            text: Text to optimize
            
        Returns:
            Optimized text
        """
        import re
        
        # Remove excessive whitespace while preserving Korean spacing
        text = re.sub(r'\s+', ' ', text)
        
        # Remove null characters and control characters
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', text)
        
        # Normalize Korean text (optional: requires additional library like unicode-kr)
        # For now, just clean up
        text = text.strip()
        
        return text
