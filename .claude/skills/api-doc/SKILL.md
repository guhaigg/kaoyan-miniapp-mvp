---
name: api-doc
description: Generate API documentation based on FastAPI code and existing patterns
user-invocable: true
disable-model-invocation: false
---

# API Documentation Skill

Generates API documentation following the project's OpenAPI/Swagger patterns and FastAPI conventions.

## Usage

`/api-doc <endpoint-file>`

## Features

- Analyzes FastAPI router patterns
- Extracts Pydantic schemas
- Documents authentication requirements
- Includes response models and error codes
- Follows existing API documentation style from `docs/` directory

## Project Context

This project uses:
- FastAPI with automatic OpenAPI generation
- JWT-based authentication
- Role-based access control
- Standardized error responses
- SSE for real-time notifications

## Output Format

Generates markdown documentation compatible with the `docs/` structure, including:
- Endpoint descriptions
- Request/response schemas
- Authentication requirements
- Example requests
- Error handling guidelines