"""
Test configuration and fixtures.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_text():
    """Sample text for testing."""
    return """
    인공지능(AI)은 인간의 학습능력, 추론능력, 지각능력을 인공적으로 구현한 것입니다.
    최근 딥러닝 기술의 발전으로 AI는 다양한 분야에서 활용되고 있습니다.
    특히 자연어 처리, 컴퓨터 비전, 음성 인식 등의 분야에서 괄목할 만한 성과를 보이고 있습니다.
    """


@pytest.fixture
def sample_document_path(tmp_path):
    """Create a sample text document for testing."""
    doc_path = tmp_path / "test_document.txt"
    doc_path.write_text("This is a test document with some content for testing purposes.")
    return str(doc_path)
