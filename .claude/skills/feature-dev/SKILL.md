---
name: feature-dev
description: Guided feature development with codebase understanding and architecture focus
user-invocable: true
disable-model-invocation: false
context: fork
---

# Feature Development Skill

This skill helps with guided feature development by analyzing the codebase structure and providing architecture-focused implementation guidance.

## Usage

Invoke with: `/feature-dev <feature-description>`

## What It Does

1. **Codebase Analysis**: Examines existing patterns, conventions, and architecture
2. **Implementation Planning**: Creates step-by-step development plans
3. **File Mapping**: Identifies which files need to be created or modified
4. **Architecture Review**: Ensures new features align with existing patterns

## Project-Specific Patterns

For this Ge Wu Jian Lu project, the skill will:

- Analyze FastAPI backend patterns in `backend/app/`
- Study Next.js 15 + React 19 frontend patterns in `web-ui/src/`
- Review微信小程序 patterns in `miniapp/`
- Follow existing API layer conventions
- Preserve authentication and notification flows
- Maintain consistent state management patterns

## Example Workflows

### Backend Feature
- Analyzes existing routers, services, and models
- Follows FastAPI dependency injection patterns
- Maintains security and audit logging

### Frontend Feature
- Uses existing API wrappers and hooks
- Follows Zustand + React Query patterns
- Preserves motion/animation conventions

### Miniapp Feature
- Aligns with WeChat authentication flow
- Uses existing API utility patterns
- Maintains consistent navigation structure