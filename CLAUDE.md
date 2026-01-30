# Claude Code Project Context

This file provides context for Claude Code when working on this project.

## Project Overview

TRJM is an enterprise-grade, local-first translation system focused on English ↔ Arabic with:
- Agentic LLM pipeline (Router → Translator → Reviewer → Post-Processor → Packager)
- Provider-agnostic LLM abstraction (OpenAI Phase 1, vLLM Phase 2)
- LDAP authentication with role-based authorization (Mock LDAP for development)
- File translation (.txt, .docx, .pdf, .msg)
- Modern Next.js UI with RTL-first design

## Repository Structure

```
C:\TRJM\
├── apps/web/                    # Next.js 14 frontend
├── services/gateway/            # FastAPI backend
├── packages/shared/             # Shared prompts, schemas, types
├── deploy/                      # Docker Compose, nginx, postgres
├── docs/                        # Documentation
└── samples/                     # Test files
```

## Development Setup

1. Copy `.env.example` to `.env` in `deploy/` directory
2. Generate TLS certificates: `bash deploy/scripts/generate-certs.sh`
3. Start services: `docker compose -f deploy/docker-compose.yml up -d`
4. Access at: https://localhost/

## Mock Users (Development)

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Administrator (all features) |
| user | user123 | User (basic translation) |
| translator | trans123 | Translator (translation + glossary) |

## Key Technologies

- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS, shadcn/ui, Zustand
- **Backend**: FastAPI, SQLAlchemy (async), Pydantic, Python 3.11+
- **Database**: PostgreSQL 16
- **LLM**: OpenAI API (Phase 1), vLLM (Phase 2)
- **Deployment**: Docker Compose, nginx (TLS termination)

## Implementation Status

### Completed (Phase 1)
- [x] Repository scaffold and configuration
- [x] Backend skeleton with FastAPI
- [x] Mock LDAP authentication
- [x] Role-based authorization system
- [x] LLM provider abstraction (OpenAI, vLLM, Mock)
- [x] Translation pipeline with agents
- [x] Database models and job system
- [x] File parsing (txt, docx, pdf, msg)
- [x] Complete Next.js UI with all pages
- [x] Docker Compose deployment
- [x] Evaluation harness

### Future Work (Phase 2)
- [ ] Real LDAP integration
- [ ] vLLM local deployment
- [ ] OCR for scanned PDFs
- [ ] Advanced glossary features
- [ ] Translation memory
- [ ] Batch processing improvements

## Important Files

- `apps/web/src/lib/auth.ts` - Frontend auth store (Zustand)
- `apps/web/src/lib/api-client.ts` - API client
- `services/gateway/src/main.py` - FastAPI entry point
- `services/gateway/src/services/translation/pipeline.py` - Translation pipeline
- `services/gateway/src/services/auth/ldap.py` - LDAP/Mock auth
- `deploy/docker-compose.yml` - Docker services configuration

## Known Issues & Fixes Applied

1. **Zustand hydration**: Added `_hasHydrated` state to prevent SSR/client mismatch
2. **JWT timestamps**: Use Unix timestamps (not ISO strings) for exp/iat
3. **Cookie SameSite**: Use "lax" instead of "strict" for cross-origin
4. **CSP headers**: Include 'unsafe-inline' 'unsafe-eval' for Next.js
5. **Feature case**: Backend uses UPPERCASE feature names

## Environment Variables

See `.env.example` for all required variables. Key ones:
- `LLM_API_KEY` - OpenAI API key
- `JWT_SECRET` - Secret for JWT signing
- `CSRF_SECRET` - Secret for CSRF tokens
- `DATABASE_URL` - PostgreSQL connection string
