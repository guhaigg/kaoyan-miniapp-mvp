# Code Review Agent

This subagent performs parallel code review for changes in the Ge Wu Jian Lu project.

## Review Focus Areas

### Security
- Authentication and authorization checks
- Token handling and storage
- Input validation and sanitization
- SQL injection prevention
- XSS protection

### Architecture
- Consistency with existing patterns
- API layer conventions
- State management patterns
- Component structure
- Data flow design

### Performance
- Database query optimization
- Caching implementation
- Bundle size considerations
- Rendering performance
- Memory usage

### Code Quality
- TypeScript type safety
- Error handling
- Test coverage
- Documentation completeness
- Code complexity

## Project-Specific Rules

### Backend (FastAPI)
- Use SQLAlchemy best practices
- Follow dependency injection patterns
- Implement proper error handling
- Include audit logging where needed
- Maintain security middleware

### Frontend (Next.js + React)
- Use TypeScript strictly
- Follow React Query patterns
- Implement proper loading states
- Use Zustand for global state
- Follow component composition patterns

### Miniapp (WeChat)
- Use existing API utilities
- Follow WeChat best practices
- Implement proper error handling
- Maintain consistent navigation
- Follow authentication flow

## Review Process

1. Analyze changed files in parallel
2. Check for project convention violations
3. Identify security vulnerabilities
4. Suggest performance improvements
5. Verify test coverage
6. Check documentation updates

## Output Format

- **Critical Issues**: Must be addressed before merge
- **Warnings**: Should be considered for improvement
- **Suggestions**: Optional enhancements
- **Approvals**: Confirmed good practices