"""
Test parser functionality.
"""
import pytest
from pathlib import Path
from app.parsers.text_parser import TextParser
from app.parsers.base_parser import ParserError


def test_text_parser_initialization():
    """Test TextParser initialization."""
    parser = TextParser()
    assert parser is not None
    assert ".txt" in parser.supported_extensions


def test_text_parser_is_supported():
    """Test file type support checking."""
    parser = TextParser()
    assert parser.is_supported("test.txt")
    assert parser.is_supported("test.md")
    assert not parser.is_supported("test.pdf")


def test_text_parser_parse(tmp_path):
    """Test text file parsing."""
    parser = TextParser()
    
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_content = "Hello, this is a test file.\nIt has multiple lines."
    test_file.write_text(test_content)
    
    # Parse the file
    result = parser.parse(str(test_file))
    
    assert result["success"] is True
    assert result["content"] == test_content
    assert result["parser"] == "TextParser"
    assert "metadata" in result
    assert result["metadata"]["filename"] == "test.txt"


def test_text_parser_invalid_file():
    """Test parsing non-existent file."""
    parser = TextParser()
    
    with pytest.raises(ParserError):
        parser.parse("nonexistent_file.txt")
