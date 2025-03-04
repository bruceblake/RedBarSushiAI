# CLAUDE.md - RedBarSushiAI Reference Guide

## Build/Run Commands
- Run server: `python run.py` 
- Run with debug: `FLASK_DEBUG=1 FLASK_APP=run.py flask run`
- Run Celery worker: `celery -A celery_app worker --loglogs=INFO`
- Run tests: `pytest`
- Run single test: `pytest tests/test_file.py::test_function`

## Code Style Guidelines
- **Imports**: Group by standard lib, third-party, local modules; alphabetize within groups
- **Naming**: snake_case for variables/functions, CamelCase for classes
- **Formatting**: 4-space indentation, 100 character line limit, docstrings with """triple quotes"""
- **Type Hints**: Use when appropriate for function parameters and returns
- **Error Handling**: Use try/except blocks with specific exceptions, proper logging
- **Logging**: Use structlog with context, levels appropriate to message importance
- **Comments**: Add comments for complex logic, not for obvious code
- **Code Organization**: Group related functionality, use helper functions for reusable logic
- **Testing**: Write pytest tests for all new features, mock external services

This file serves as a reference for agentic coding assistants working in this codebase.