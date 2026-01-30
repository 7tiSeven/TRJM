# TRJM - Agentic AI Translator

Enterprise-grade, local-first translation system with focus on English-Arabic translation.

## Features

- **Agentic Translation Pipeline**: Multi-agent system with Router, Translator, Reviewer, and Post-Processor
- **Provider Agnostic**: Switch between OpenAI and local vLLM without code changes
- **LDAP Authentication**: Enterprise SSO with role-based access control
- **File Translation**: Support for .txt, .docx, .pdf, and .msg files
- **Quality Assurance**: Built-in QA scoring with confidence metrics
- **RTL Support**: First-class support for Arabic and other RTL languages
- **Glossary Enforcement**: Custom terminology management
- **Security Hardened**: TLS, CSRF, rate limiting, sandboxed file processing

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenAI API key (Phase 1) or NVIDIA GPU with vLLM (Phase 2)

### Phase 1: Development (OpenAI)

1. Copy environment configuration:
   ```bash
   cp .env.phase1.example .env
   ```

2. Add your OpenAI API key to `.env`:
   ```
   LLM_API_KEY=sk-your-api-key-here
   ```

3. Generate TLS certificates:
   ```bash
   ./deploy/scripts/generate-certs.sh
   ```

4. Start the application:
   ```bash
   docker compose up -d
   ```

5. Access the application at `https://localhost:3000`

### Default Mock Users (Development)

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Administrator |
| user | user123 | Normal User |
| translator | trans123 | Translator |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         NGINX                                │
│                    (TLS Termination)                         │
└──────────────┬──────────────────────────┬───────────────────┘
               │                          │
       ┌───────▼───────┐          ┌──────▼──────┐
       │   Next.js     │          │   FastAPI   │
       │   Frontend    │◄────────►│   Gateway   │
       │   (Web UI)    │          │   (API)     │
       └───────────────┘          └──────┬──────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
            ┌───────▼───────┐    ┌──────▼──────┐    ┌───────▼───────┐
            │  PostgreSQL   │    │ LLM Provider │    │ File Storage  │
            │  (Database)   │    │ (OpenAI/vLLM)│    │   (Uploads)   │
            └───────────────┘    └──────────────┘    └───────────────┘
```

### Translation Pipeline

```
Input Text
    │
    ▼
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│    Router    │────►│  Translator   │────►│   Reviewer   │
│    Agent     │     │    Agent      │     │    Agent     │
└──────────────┘     └───────────────┘     └──────┬───────┘
                                                  │
                                          Confidence < 75%?
                                                  │
                                    ┌─────────────┼─────────────┐
                                    │ Yes                   No  │
                                    ▼                       ▼   │
                              Retry (max 2)         ┌──────────────┐
                                                    │    Post-     │
                                                    │  Processor   │
                                                    └──────┬───────┘
                                                           │
                                                           ▼
                                                    ┌──────────────┐
                                                    │   Packager   │
                                                    │ (Final + QA) │
                                                    └──────────────┘
```

## Project Structure

```
TRJM/
├── apps/web/                 # Next.js frontend
├── services/gateway/         # FastAPI backend
├── packages/shared/          # Shared prompts, schemas, types
├── deploy/                   # Docker, nginx, postgres configs
├── docs/                     # Documentation
└── samples/                  # Sample files for testing
```

## Configuration

### Environment Variables

See `.env.example` for all available options. Key configurations:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider (openai/vllm) | openai |
| `LLM_MODEL` | Model identifier | gpt-4.1 |
| `LDAP_MOCK` | Use mock LDAP | true |
| `DEV_MODE` | Show dev warning banner | true |

### Phase 2: Production (vLLM)

1. Copy Phase 2 configuration:
   ```bash
   cp .env.phase2.example .env
   ```

2. Start vLLM with Qwen model:
   ```bash
   docker compose -f deploy/docker-compose.vllm.yml up -d
   ```

No code changes required - same application, different LLM backend.

## Security

- TLS encryption for all traffic
- LDAP/LDAPS authentication with certificate validation
- JWT tokens with configurable expiry
- CSRF protection
- Rate limiting per user and IP
- File upload validation (extension, MIME, magic bytes)
- Sandboxed file processing
- Audit logging

## API Documentation

Once running, access the API documentation at:
- Swagger UI: `https://localhost:8000/docs`
- ReDoc: `https://localhost:8000/redoc`

## Development

### Running Tests

```bash
# Backend tests
cd services/gateway
pytest

# Frontend tests
cd apps/web
npm test

# Evaluation harness
cd services/gateway
python -m eval.runner
```

### Code Style

- Backend: Black, isort, mypy
- Frontend: ESLint, Prettier

## License

Proprietary - Internal Use Only

## Support

For issues and feature requests, contact the development team.
