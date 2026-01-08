"""
HWP (한글) document parser.
"""
from typing import Dict, Any
import olefile
from .base_parser import BaseParser, ParserError


class HWPParser(BaseParser):
    """Parser for HWP (Hancom Office) documents."""
    
    def __init__(self):
        """Initialize HWP parser."""
        super().__init__()
        self.supported_extensions = [".hwp"]
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse HWP document and extract content.
        
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
            # Try to parse HWP file using olefile
            content = self._extract_with_olefile(file_path)
            
            # Get metadata
            metadata = self.extract_metadata(file_path)
            metadata.update({
                "format": "HWP",
                "encoding": "utf-8"
            })
            
            return {
                "content": content,
                "metadata": metadata,
                "parser": "HWPParser"
            }
        except Exception as e:
            raise ParserError(f"Failed to parse HWP document: {str(e)}")
    
    def _extract_with_olefile(self, file_path: str) -> str:
        """
        Extract text from HWP file using olefile.
        
        Note: This is a basic implementation. HWP format is complex,
        and full parsing would require the hwp5 library or more sophisticated parsing.
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
                if "BodyText" in stream_name or "PrvText" in stream_name:
                    try:
                        data = ole.openstream(stream).read()
                        # Try to decode as UTF-16 (common in HWP files)
                        try:
                            text = data.decode("utf-16")
                            text_parts.append(text)
                        except:
                            # Try UTF-8 if UTF-16 fails
                            try:
                                text = data.decode("utf-8", errors="ignore")
                                text_parts.append(text)
                            except:
                                pass
                    except:
                        pass
            
            ole.close()
            
            if text_parts:
                return "\n\n".join(text_parts)
            else:
                return "[HWP content - requires advanced parsing]"
        except Exception as e:
            raise ParserError(f"Failed to extract HWP content: {str(e)}")
