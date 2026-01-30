# Agentic AI Translator - Implementation Plan

## Project Overview

Enterprise-grade, local-first translation system focused on English ↔ Arabic with:
- Agentic LLM pipeline (Router → Translator → Reviewer → Post-Processor → Packager)
- Provider-agnostic LLM abstraction (OpenAI Phase 1, vLLM Phase 2)
- LDAP authentication with role-based authorization
- File translation (.txt, .docx, .pdf, .msg)
- Modern Next.js UI with RTL-first design

---

## Repository Structure

```
C:\TRJM\
├── apps/
│   └── web/                          # Next.js frontend
│       ├── src/
│       │   ├── app/                  # App router pages
│       │   │   ├── (auth)/
│       │   │   │   └── login/
│       │   │   ├── (dashboard)/
│       │   │   │   ├── translate/
│       │   │   │   ├── files/
│       │   │   │   ├── history/
│       │   │   │   ├── glossary/
│       │   │   │   └── admin/
│       │   │   ├── api/              # Next.js API routes (proxy)
│       │   │   └── layout.tsx
│       │   ├── components/
│       │   │   ├── ui/               # shadcn/ui components
│       │   │   ├── translation/
│       │   │   ├── files/
│       │   │   └── admin/
│       │   ├── lib/
│       │   │   ├── api-client.ts
│       │   │   ├── auth.ts
│       │   │   └── utils.ts
│       │   ├── hooks/
│       │   └── styles/
│       ├── public/
│       ├── next.config.js
│       ├── tailwind.config.ts
│       ├── package.json
│       └── Dockerfile
│
├── services/
│   └── gateway/                      # Python FastAPI backend
│       ├── src/
│       │   ├── api/
│       │   │   ├── routes/
│       │   │   │   ├── auth.py
│       │   │   │   ├── translation.py
│       │   │   │   ├── files.py
│       │   │   │   ├── glossary.py
│       │   │   │   ├── history.py
│       │   │   │   └── admin.py
│       │   │   ├── middleware/
│       │   │   │   ├── auth.py
│       │   │   │   ├── cors.py
│       │   │   │   ├── rate_limit.py
│       │   │   │   └── security.py
│       │   │   └── deps.py
│       │   ├── core/
│       │   │   ├── config.py
│       │   │   ├── security.py
│       │   │   └── logging.py
│       │   ├── db/
│       │   │   ├── models.py
│       │   │   ├── session.py
│       │   │   └── migrations/
│       │   ├── services/
│       │   │   ├── auth/
│       │   │   │   ├── ldap.py
│       │   │   │   └── jwt.py
│       │   │   ├── translation/
│       │   │   │   ├── pipeline.py
│       │   │   │   ├── agents/
│       │   │   │   │   ├── router.py
│       │   │   │   │   ├── translator.py
│       │   │   │   │   ├── reviewer.py
│       │   │   │   │   └── post_processor.py
│       │   │   │   └── packager.py
│       │   │   ├── files/
│       │   │   │   ├── parser.py
│       │   │   │   ├── txt.py
│       │   │   │   ├── docx.py
│       │   │   │   ├── pdf.py
│       │   │   │   └── msg.py
│       │   │   ├── glossary/
│       │   │   │   └── manager.py
│       │   │   └── jobs/
│       │   │       └── manager.py
│       │   ├── llm/
│       │   │   ├── provider.py       # Abstract interface
│       │   │   ├── openai.py         # OpenAI provider
│       │   │   ├── vllm.py           # vLLM provider
│       │   │   ├── mock.py           # Mock for testing
│       │   │   └── factory.py        # Provider factory
│       │   └── main.py
│       ├── eval/                     # Evaluation harness
│       │   ├── test_cases/
│       │   ├── runner.py
│       │   └── metrics.py
│       ├── tests/
│       ├── requirements.txt
│       ├── pyproject.toml
│       └── Dockerfile
│
├── packages/
│   └── shared/
│       ├── prompts/                  # LLM prompt templates
│       │   ├── router.yaml
│       │   ├── translator.yaml
│       │   ├── reviewer.yaml
│       │   └── post_processor.yaml
│       ├── schemas/                  # Shared JSON schemas
│       │   ├── translation.json
│       │   └── qa_report.json
│       └── types/                    # TypeScript types
│           └── index.ts
│
├── deploy/
│   ├── docker-compose.yml            # Phase 1 (OpenAI)
│   ├── docker-compose.vllm.yml       # Phase 2 (vLLM)
│   ├── nginx/
│   │   └── nginx.conf
│   └── postgres/
│       └── init.sql
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   ├── API.md
│   ├── SECURITY.md
│   └── EVALUATION.md
│
├── samples/
│   ├── glossary.csv
│   ├── test_document.docx
│   ├── test_document.pdf
│   ├── test_email.msg
│   └── test_text.txt
│
├── .env.example
├── .env.phase1.example
├── .env.phase2.example
├── models.yaml
├── .gitignore
└── README.md
```

---

## Implementation Steps

### Step 0: Repository Scaffold & Configuration
**Files to create:**
- All directory structure
- `.env.example`, `.env.phase1.example`, `.env.phase2.example`
- `models.yaml` (model configurations)
- `README.md`
- `.gitignore`
- `docker-compose.yml` (skeleton)
- `packages/shared/prompts/*.yaml`
- Sample files in `samples/`

### Step 1: Backend Skeleton + LDAP Auth + Role System
**Files:**
- `services/gateway/src/main.py` - FastAPI app
- `services/gateway/src/core/config.py` - Pydantic settings
- `services/gateway/src/core/security.py` - JWT, CSRF tokens
- `services/gateway/src/db/models.py` - SQLAlchemy models
- `services/gateway/src/db/session.py` - DB connection
- `services/gateway/src/services/auth/ldap.py` - LDAP bind
- `services/gateway/src/services/auth/jwt.py` - Token management
- `services/gateway/src/api/routes/auth.py` - Login/logout
- `services/gateway/src/api/routes/admin.py` - Role management
- `services/gateway/src/api/middleware/auth.py` - Auth middleware
- `services/gateway/src/api/middleware/security.py` - Security headers

**Database Models:**
```python
User: id, username, email, display_name, role_id, created_at, last_login
Role: id, name, description, is_default, created_at
RoleFeature: id, role_id, feature_name, enabled
AuditLog: id, user_id, action, resource, details, ip_address, timestamp
```

**Feature Registry (Enum):**
```python
TRANSLATE_TEXT, UPLOAD_FILES, TRANSLATE_DOCX, TRANSLATE_PDF,
TRANSLATE_MSG, USE_GLOSSARY, MANAGE_GLOSSARY, VIEW_HISTORY,
EXPORT_RESULTS, ADMIN_PANEL
```

### Step 2: Provider Abstraction + OpenAI Provider
**Files:**
- `services/gateway/src/llm/provider.py` - Abstract base
- `services/gateway/src/llm/openai.py` - OpenAI implementation
- `services/gateway/src/llm/vllm.py` - vLLM implementation
- `services/gateway/src/llm/mock.py` - Mock for tests
- `services/gateway/src/llm/factory.py` - Factory pattern

**Provider Interface:**
```python
class LLMProvider(ABC):
    async def chat_completion(
        self,
        messages: List[Message],
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[ResponseFormat] = None
    ) -> CompletionResponse
```

**Environment-driven selection:**
- `LLM_PROVIDER=openai|vllm`
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`

### Step 3: Text Translation Pipeline + QA
**Files:**
- `services/gateway/src/services/translation/pipeline.py`
- `services/gateway/src/services/translation/agents/router.py`
- `services/gateway/src/services/translation/agents/translator.py`
- `services/gateway/src/services/translation/agents/reviewer.py`
- `services/gateway/src/services/translation/agents/post_processor.py`
- `services/gateway/src/services/translation/packager.py`
- `services/gateway/src/api/routes/translation.py`
- `packages/shared/prompts/*.yaml`

**Pipeline Flow:**
1. Router Agent → Detect language, content type, select strategy
2. Translator Agent → Draft translation with glossary/token protection
3. Reviewer Agent → QA validation, confidence scoring
4. Post-Processor → RTL fixes, typography
5. Packager → Final output with QA report

**Pydantic Schemas (validated outputs):**
```python
RouterOutput: source_lang, target_lang, content_type, strategy, prompt_template
TranslationOutput: draft, protected_tokens, glossary_applied
ReviewOutput: corrected_translation, confidence, issues[], glossary_compliance
FinalOutput: translation, qa_report, confidence, risky_spans[]
```

### Step 4: Database + Job System + Storage
**Files:**
- `services/gateway/src/db/models.py` (extend)
- `services/gateway/src/services/jobs/manager.py`
- `services/gateway/src/api/routes/history.py`
- `deploy/postgres/init.sql`

**Additional Models:**
```python
Job: id, user_id, job_type, status, source_lang, target_lang,
     input_text, output_text, file_path, qa_report, confidence,
     created_at, completed_at, expires_at
Glossary: id, user_id, name, version, created_at
GlossaryEntry: id, glossary_id, source_term, target_term
```

**Retention Policy:**
- Default: 24h auto-delete
- Configurable via `RETENTION_HOURS` env var

### Step 5: File Translation
**Files:**
- `services/gateway/src/services/files/parser.py` - Base parser
- `services/gateway/src/services/files/txt.py`
- `services/gateway/src/services/files/docx.py`
- `services/gateway/src/services/files/pdf.py`
- `services/gateway/src/services/files/msg.py`
- `services/gateway/src/api/routes/files.py`

**File Validation:**
- Extension whitelist: .txt, .docx, .pdf, .msg
- MIME type validation
- Magic byte verification
- Max file size: 10MB (configurable)

**Parser Output:**
```python
ParsedDocument: content, metadata, paragraphs[], format_hints
```

**OCR:**
- Stub interface only
- `OCR_ENABLED=false` by default

### Step 6: Web UI Implementation
**Files:**
- `apps/web/src/app/layout.tsx` - Root layout
- `apps/web/src/app/(auth)/login/page.tsx`
- `apps/web/src/app/(dashboard)/translate/page.tsx`
- `apps/web/src/app/(dashboard)/files/page.tsx`
- `apps/web/src/app/(dashboard)/history/page.tsx`
- `apps/web/src/app/(dashboard)/glossary/page.tsx`
- `apps/web/src/app/(dashboard)/admin/page.tsx`
- `apps/web/src/components/translation/split-editor.tsx`
- `apps/web/src/components/translation/qa-panel.tsx`
- `apps/web/src/components/files/upload-zone.tsx`
- `apps/web/src/components/ui/*` (shadcn components)

**UI Features:**
- RTL-first design with `dir="rtl"` support
- Split-pane editor (Source | Target)
- Style presets dropdown
- Glossary selector
- QA report panel with confidence meter
- DEV MODE banner (Phase 1)
- Role-based feature visibility

### Step 7: Docker Compose (Phase 1)
**Files:**
- `deploy/docker-compose.yml`
- `deploy/nginx/nginx.conf`
- `services/gateway/Dockerfile`
- `apps/web/Dockerfile`

**Services:**
```yaml
services:
  web:        # Next.js frontend
  gateway:    # FastAPI backend
  postgres:   # Database
  nginx:      # Reverse proxy with TLS
```

**Security:**
- Non-root containers
- Read-only filesystems where possible
- Network isolation
- Health checks

### Step 8: Evaluation Harness
**Files:**
- `services/gateway/eval/runner.py`
- `services/gateway/eval/metrics.py`
- `services/gateway/eval/test_cases/*.json`

**Test Categories:**
- Glossary enforcement
- Token protection (URLs, emails, placeholders)
- RTL/Arabic punctuation
- Meaning preservation
- Number/date accuracy

### Step 9: Phase 2 vLLM Profile
**Files:**
- `deploy/docker-compose.vllm.yml`
- `.env.phase2.example`
- `docs/DEPLOYMENT.md` (update)

**Config-only switch:**
```bash
LLM_PROVIDER=vllm
LLM_BASE_URL=http://vllm:8000/v1
LLM_API_KEY=dummy
LLM_MODEL=Qwen/Qwen2.5-32B-Instruct
```

### Step 10: Documentation
**Files:**
- `docs/ARCHITECTURE.md`
- `docs/DEPLOYMENT.md`
- `docs/API.md`
- `docs/SECURITY.md`
- `docs/EVALUATION.md`
- `README.md`

---

## Key Technical Decisions

### 1. Backend Framework: FastAPI
- Async support for concurrent LLM calls
- Pydantic for schema validation
- OpenAPI documentation
- Easy middleware integration

### 2. Database: PostgreSQL + SQLAlchemy
- Robust, production-ready
- Async support via asyncpg
- Alembic for migrations

### 3. Authentication Flow
```
User → Login Form → Gateway → LDAP Bind
                         ↓ Success
                    Create/Update User in DB
                         ↓
                    Issue JWT (httpOnly cookie)
                         ↓
                    Return user + role + features
```

### 4. Feature Enforcement
```
Request → Auth Middleware → Extract JWT
                              ↓
                         Load User + Role
                              ↓
                         Check required feature
                              ↓ Denied
                         Return 403 Forbidden
                              ↓ Allowed
                         Continue to handler
```

### 5. Translation Pipeline Architecture
```
Input → Router Agent (detect language, type)
             ↓
      Select prompt template
             ↓
      Translator Agent (draft + glossary)
             ↓
      Reviewer Agent (QA + score)
             ↓ Confidence < threshold?
      Retry (max 2x)
             ↓
      Post-Processor (RTL fixes)
             ↓
      Result Packager (final output + report)
```

### 6. File Processing Security
- Sandboxed container for parsing
- No network access
- Dropped capabilities
- Extension + MIME + magic byte validation

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/trjm

# LDAP
LDAP_URL=ldaps://ldap.example.com:636
LDAP_BASE_DN=dc=example,dc=com
LDAP_BIND_DN=cn=service,dc=example,dc=com
LDAP_BIND_PASSWORD=secret
LDAP_USER_DN_TEMPLATE=uid={username},ou=users,dc=example,dc=com
LDAP_STARTTLS=false
LDAP_CA_CERT_PATH=/certs/ca.crt

# LLM (Phase 1)
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-4.1

# Security
JWT_SECRET=generate-secure-random-string
CORS_ORIGINS=https://localhost:3000
CSRF_SECRET=generate-secure-random-string
RATE_LIMIT_PER_MINUTE=60
MAX_CONCURRENT_JOBS=3

# Storage
UPLOAD_DIR=/data/uploads
RETENTION_HOURS=24

# Mode
DEV_MODE=true
```

---

## Verification Plan

### Phase 1 Testing
1. `docker compose up -d` - All services start
2. Visit `https://localhost:3000` - See login page + DEV MODE banner
3. Login with LDAP credentials - Authenticated, redirected to dashboard
4. Translate text - Pipeline executes, QA report displayed
5. Upload .docx file - Parsed and translated
6. Check history - Jobs visible with search
7. Admin panel - Role management works
8. Eval harness - `python -m eval.runner` passes

### Phase 2 Testing
1. Update `.env` with vLLM settings
2. `docker compose down && docker compose up -d`
3. Same test sequence - All pass without code changes

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| LDAP unavailable | Graceful error, clear message |
| LLM timeout | Configurable timeout, retry logic |
| Large file DoS | Max file size, rate limiting |
| Prompt injection | Structured JSON outputs, validation |
| PII in logs | Configurable redaction, default off |

---

## User Preferences (Confirmed)

| Setting | Choice |
|---------|--------|
| LDAP Type | Mock LDAP for development (configure real LDAP later) |
| OpenAI API | Ready - GPT-4.1 access confirmed |
| TLS Setup | Self-signed certificates for development |
| UI Theme | Light mode primary with dark mode option |

---

## Implementation Adjustments Based on Preferences

### Mock LDAP Provider
- Implement `MockLDAPProvider` alongside real LDAP
- Enable via `LDAP_MOCK=true` environment variable
- Mock users: `admin/admin123`, `user/user123`, `translator/trans123`
- Mock validates credentials locally without network
- Easy switch to real LDAP by changing env vars

### Self-Signed TLS
- Generate self-signed certs during `docker compose up`
- Store in `deploy/certs/` (gitignored)
- Script: `deploy/scripts/generate-certs.sh`
- CN=localhost, SANs: localhost, 127.0.0.1

### Light Mode Primary UI
- Default theme: Light
- Dark mode toggle in header
- Persist preference in localStorage
- System preference option available
- shadcn/ui light theme customization

---

## Next Steps

Ready to begin implementation starting with Step 0 (Repository Scaffold).
