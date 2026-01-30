# TRJM Architecture

## Overview

TRJM is an enterprise-grade translation system built with a microservices architecture. It uses an agentic AI pipeline for high-quality English-Arabic translation with quality assurance.

## System Components

### 1. Frontend (Next.js)

**Location:** `apps/web/`

- **Framework:** Next.js 14 with App Router
- **Styling:** Tailwind CSS + shadcn/ui
- **State Management:** Zustand
- **Key Features:**
  - RTL-first design for Arabic support
  - Split-pane translation editor
  - Real-time QA report display
  - File upload with drag-and-drop
  - Role-based UI rendering

### 2. Backend Gateway (FastAPI)

**Location:** `services/gateway/`

- **Framework:** FastAPI (async)
- **Database:** PostgreSQL with SQLAlchemy
- **Authentication:** LDAP + JWT
- **Key Features:**
  - RESTful API
  - Rate limiting
  - CSRF protection
  - Request correlation
  - Structured logging

### 3. LLM Provider Layer

**Location:** `services/gateway/src/llm/`

Provider-agnostic abstraction supporting:
- **OpenAI** (Phase 1): GPT-4.1 via API
- **vLLM** (Phase 2): Qwen2.5-32B self-hosted

Configuration-only switching via environment variables.

### 4. Translation Pipeline

**Location:** `services/gateway/src/services/translation/`

Multi-agent pipeline:

```
┌─────────┐    ┌────────────┐    ┌──────────┐    ┌───────────────┐    ┌──────────┐
│ Router  │───►│ Translator │───►│ Reviewer │───►│ Post-Processor│───►│ Packager │
│  Agent  │    │   Agent    │    │  Agent   │    │     Agent     │    │          │
└─────────┘    └────────────┘    └──────────┘    └───────────────┘    └──────────┘
```

**Router Agent:**
- Detects source language
- Identifies content type
- Selects translation strategy

**Translator Agent:**
- Performs initial translation
- Applies glossary terms
- Protects tokens (URLs, emails, placeholders)

**Reviewer Agent:**
- Quality assessment
- Confidence scoring
- Issue identification
- Triggers retry if confidence < 75%

**Post-Processor Agent:**
- RTL text corrections
- Arabic punctuation fixes
- Typography improvements

**Packager:**
- Combines translation with QA report
- Generates final output

### 5. File Processing

**Location:** `services/gateway/src/services/files/`

Supported formats:
- `.txt` - Plain text with encoding detection
- `.docx` - Microsoft Word documents
- `.pdf` - PDF text extraction (no OCR)
- `.msg` - Outlook email messages

Security measures:
- Extension whitelist
- MIME type validation
- Magic byte verification
- Size limits

## Data Flow

### Text Translation

```
1. User submits text via UI
2. Frontend sends POST to /translation/translate
3. Gateway validates request
4. Pipeline executes all agents sequentially
5. Each agent calls LLM provider
6. Results returned with QA report
7. Job stored in database
8. Response sent to frontend
```

### File Translation

```
1. User uploads file via UI
2. Frontend sends POST to /files/translate
3. Gateway validates file
4. Parser extracts text paragraphs
5. Each paragraph translated via pipeline
6. Output file generated
7. User downloads translated file
```

## Database Schema

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐
│    User     │───►│    Role     │◄───│ RoleFeature  │
└─────────────┘    └─────────────┘    └──────────────┘
       │
       ▼
┌─────────────┐    ┌─────────────┐
│    Job      │    │  Glossary   │
└─────────────┘    └──────┬──────┘
                          │
                          ▼
                   ┌──────────────┐
                   │GlossaryEntry │
                   └──────────────┘
```

**Key Tables:**
- `users` - User accounts from LDAP
- `roles` - Role definitions
- `role_features` - Feature flags per role
- `jobs` - Translation job records
- `glossaries` - User glossary collections
- `glossary_entries` - Individual terms
- `audit_logs` - Security audit trail

## Authentication Flow

```
1. User enters LDAP credentials
2. Gateway performs LDAP bind
3. On success, user created/updated in DB
4. JWT issued with httpOnly cookie
5. Subsequent requests include JWT
6. Gateway validates JWT, loads user
7. Role features checked for authorization
```

## Security Architecture

### Network Security
- All traffic over TLS
- Private Docker network
- No direct database access

### Application Security
- JWT with short expiry
- CSRF tokens for mutations
- Rate limiting per user
- Request correlation IDs

### Data Security
- File validation
- SQL injection prevention (ORM)
- XSS prevention (React)
- No PII in logs

## Deployment Architecture

### Phase 1 (Development)

```
┌─────────────────────────────────────┐
│              NGINX                   │
│         (TLS, Routing)              │
└──────────────┬──────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────┐         ┌──────▼──────┐
│ Web    │         │   Gateway    │
│ (3000) │         │    (8000)    │
└────────┘         └──────┬───────┘
                          │
              ┌───────────┼───────────┐
              │                       │
       ┌──────▼──────┐        ┌───────▼───────┐
       │ PostgreSQL  │        │  OpenAI API   │
       │   (5432)    │        │  (External)   │
       └─────────────┘        └───────────────┘
```

### Phase 2 (Production)

```
┌─────────────────────────────────────┐
│              NGINX                   │
│         (TLS, Routing)              │
└──────────────┬──────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────┐         ┌──────▼──────┐
│ Web    │         │   Gateway    │
│ (3000) │         │    (8000)    │
└────────┘         └──────┬───────┘
                          │
    ┌─────────────────────┼─────────────────────┐
    │                     │                     │
┌───▼───────┐     ┌───────▼───────┐    ┌────────▼────────┐
│PostgreSQL │     │     vLLM      │    │  File Storage   │
│  (5432)   │     │    (8001)     │    │   (Uploads)     │
└───────────┘     └───────────────┘    └─────────────────┘
                         │
                 ┌───────▼───────┐
                 │  GPU Server   │
                 │ (Qwen2.5-32B) │
                 └───────────────┘
```

## Scalability Considerations

### Horizontal Scaling
- Gateway is stateless (can run multiple instances)
- Database is the bottleneck
- Consider connection pooling (PgBouncer)

### Vertical Scaling
- vLLM benefits from more GPU memory
- Increase `tensor-parallel-size` for multi-GPU

### Caching
- LLM responses can be cached by content hash
- Consider Redis for session/rate limit storage

## Monitoring

### Health Endpoints
- `GET /health` - Gateway health
- `GET /api/health` - Frontend health
- vLLM: `GET /health`

### Metrics to Track
- Translation latency
- Confidence score distribution
- Error rates by type
- LLM token usage
- File processing times

### Logging
- Structured JSON logs
- Request correlation IDs
- Optional PII redaction
- Audit trail for security events
