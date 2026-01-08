"""
Excel document parser.
"""
from typing import Dict, Any
import openpyxl
from .base_parser import BaseParser, ParserError


class ExcelParser(BaseParser):
    """Parser for Excel documents."""
    
    def __init__(self):
        """Initialize Excel parser."""
        super().__init__()
        self.supported_extensions = [".xls", ".xlsx"]
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse Excel document and extract content.
        
        Args:
            file_path: Path to the Excel file
            
        Returns:
            Dictionary containing parsed content and metadata
        """
        if not self.validate_file(file_path):
            raise ParserError(f"Invalid or missing file: {file_path}")
        
        if not self.is_supported(file_path):
            raise ParserError(f"Unsupported file type for Excel parser: {file_path}")
        
        try:
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            
            # Extract text from all sheets
            sheet_texts = []
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                sheet_content = [f"--- Sheet: {sheet_name} ---"]
                
                for row in sheet.iter_rows(values_only=True):
                    # Filter out empty rows
                    row_values = [str(cell) if cell is not None else "" for cell in row]
                    if any(val.strip() for val in row_values):
                        sheet_content.append(" | ".join(row_values))
                
                if len(sheet_content) > 1:  # More than just the sheet header
                    sheet_texts.append("\n".join(sheet_content))
            
            content = "\n\n".join(sheet_texts)
            
            # Get metadata
            metadata = self.extract_metadata(file_path)
            metadata.update({
                "num_sheets": len(workbook.sheetnames),
                "sheet_names": workbook.sheetnames,
                "properties": self._extract_properties(workbook)
            })
            
            return {
                "content": content,
                "metadata": metadata,
                "parser": "ExcelParser"
            }
        except Exception as e:
            raise ParserError(f"Failed to parse Excel document: {str(e)}")
    
    def _extract_properties(self, workbook) -> Dict[str, Any]:
        """Extract properties from Excel workbook."""
        try:
            props = workbook.properties
            return {
                "creator": props.creator or "",
                "title": props.title or "",
                "subject": props.subject or "",
                "created": str(props.created) if props.created else "",
                "modified": str(props.modified) if props.modified else ""
            }
        except Exception:
            return {}
