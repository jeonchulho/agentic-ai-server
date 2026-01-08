# Contributing to Agentic AI Server

Thank you for your interest in contributing to the Agentic AI Server project!

## Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/yourusername/agentic-ai-server.git
   cd agentic-ai-server
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Development Workflow

1. **Create a new branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed

3. **Run tests**
   ```bash
   pytest tests/ -v
   ```

4. **Format code** (optional but recommended)
   ```bash
   black app/ tests/
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add feature: your feature description"
   ```

6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request**
   - Go to the original repository on GitHub
   - Click "New Pull Request"
   - Select your branch
   - Fill out the PR template

## Code Style Guidelines

- Follow PEP 8 Python style guide
- Use type hints where possible
- Write docstrings for all functions and classes
- Keep functions small and focused
- Add comments for complex logic

## Adding New Features

### Adding a New Agent

1. Create a new file in `app/agents/`
2. Implement the agent using LangChain patterns
3. Add corresponding service in `app/services/`
4. Create API endpoints in `app/api/v1/`
5. Add tests in `tests/`

### Adding a New Parser

1. Create a new file in `app/parsers/`
2. Inherit from `BaseParser`
3. Implement the `parse()` method
4. Register in `ParserFactory`
5. Add tests for the parser

### Adding a New API Endpoint

1. Create or update file in `app/api/v1/`
2. Define Pydantic models in `app/models/schemas.py`
3. Implement the endpoint logic
4. Add to router in `app/main.py`
5. Test the endpoint

## Testing

- Write unit tests for new functionality
- Ensure all tests pass before submitting PR
- Aim for good test coverage
- Use fixtures for common test data

## Documentation

- Update README.md for major features
- Add docstrings to all public functions
- Update API documentation if needed
- Include examples in docstrings

## Questions?

Feel free to open an issue if you have questions or need help!
