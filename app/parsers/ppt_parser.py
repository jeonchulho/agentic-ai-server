"""
PowerPoint document parser.
"""
from typing import Dict, Any
from pptx import Presentation
from .base_parser import BaseParser, ParserError


class PPTParser(BaseParser):
    """Parser for PowerPoint documents."""
    
    def __init__(self):
        """Initialize PowerPoint parser."""
        super().__init__()
        self.supported_extensions = [".ppt", ".pptx"]
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse PowerPoint document and extract content.
        
        Args:
            file_path: Path to the PowerPoint file
            
        Returns:
            Dictionary containing parsed content and metadata
        """
        if not self.validate_file(file_path):
            raise ParserError(f"Invalid or missing file: {file_path}")
        
        if not self.is_supported(file_path):
            raise ParserError(f"Unsupported file type for PowerPoint parser: {file_path}")
        
        try:
            prs = Presentation(file_path)
            
            # Extract text from slides
            slide_texts = []
            for slide_num, slide in enumerate(prs.slides, 1):
                slide_content = []
                slide_content.append(f"--- Slide {slide_num} ---")
                
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_content.append(shape.text)
                    
                    # Extract text from tables
                    if hasattr(shape, "table"):
                        table = shape.table
                        for row in table.rows:
                            row_text = " | ".join(cell.text for cell in row.cells)
                            if row_text.strip():
                                slide_content.append(row_text)
                
                if len(slide_content) > 1:  # More than just the slide header
                    slide_texts.append("\n".join(slide_content))
            
            content = "\n\n".join(slide_texts)
            
            # Get metadata
            metadata = self.extract_metadata(file_path)
            metadata.update({
                "num_slides": len(prs.slides),
                "slide_width": prs.slide_width,
                "slide_height": prs.slide_height
            })
            
            return {
                "content": content,
                "metadata": metadata,
                "parser": "PPTParser"
            }
        except Exception as e:
            raise ParserError(f"Failed to parse PowerPoint document: {str(e)}")
