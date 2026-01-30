# TRJM Deployment Guide

## Prerequisites

### Phase 1 (OpenAI)
- Docker 24.0+
- Docker Compose 2.20+
- OpenAI API key with GPT-4.1 access
- 4GB RAM minimum

### Phase 2 (vLLM)
- All Phase 1 requirements
- NVIDIA GPU with 48GB+ VRAM (for Qwen2.5-32B)
- NVIDIA Docker runtime
- CUDA 12.0+

## Quick Start

### 1. Clone and Configure

```bash
# Clone repository
git clone <repository-url> TRJM
cd TRJM

# Copy environment template
cp .env.phase1.example .env

# Edit configuration
nano .env
```

### 2. Generate TLS Certificates

```bash
# Make script executable (Unix)
chmod +x deploy/scripts/generate-certs.sh

# Generate certificates
./deploy/scripts/generate-certs.sh

# On Windows, use Git Bash or WSL
```

### 3. Start Services

```bash
# Phase 1 (OpenAI)
cd deploy
docker compose up -d

# Phase 2 (vLLM)
docker compose -f docker-compose.yml -f docker-compose.vllm.yml up -d
```

### 4. Verify Deployment

```bash
# Check all services are running
docker compose ps

# Check logs
docker compose logs -f

# Test health endpoint
curl -k https://localhost/health
```

### 5. Access Application

- Web UI: https://localhost
- API Docs: https://localhost:8000/docs (dev mode only)

## Configuration Reference

### Essential Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://trjm:password@postgres:5432/trjm
POSTGRES_PASSWORD=your-secure-password

# Authentication
JWT_SECRET=generate-64-char-random-string
CSRF_SECRET=generate-32-char-random-string
LDAP_MOCK=true  # Set to false for real LDAP

# LLM Provider
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-openai-key
LLM_MODEL=gpt-4.1
```

### LDAP Configuration (Production)

```bash
LDAP_MOCK=false
LDAP_URL=ldaps://ldap.example.com:636
LDAP_BASE_DN=dc=example,dc=com
LDAP_BIND_DN=cn=service,dc=example,dc=com
LDAP_BIND_PASSWORD=service-password
LDAP_USER_DN_TEMPLATE=uid={username},ou=users,dc=example,dc=com
LDAP_SEARCH_FILTER=(uid={username})
LDAP_STARTTLS=false
LDAP_CA_CERT_PATH=/certs/ldap-ca.crt
```

### vLLM Configuration (Phase 2)

```bash
LLM_PROVIDER=vllm
LLM_BASE_URL=http://vllm:8001/v1
LLM_API_KEY=dummy
LLM_MODEL=qwen2.5-32b

# vLLM specific
VLLM_TENSOR_PARALLEL=1
VLLM_GPU_MEMORY=0.90
VLLM_MAX_MODEL_LEN=8192
HUGGING_FACE_HUB_TOKEN=hf_your_token
```

## Production Checklist

### Security

- [ ] Generate strong JWT_SECRET (64+ chars)
- [ ] Generate strong CSRF_SECRET (32+ chars)
- [ ] Generate strong POSTGRES_PASSWORD
- [ ] Use real LDAP (LDAP_MOCK=false)
- [ ] Use trusted TLS certificates
- [ ] Set DEV_MODE=false
- [ ] Review rate limits

### Performance

- [ ] Tune PostgreSQL (shared_buffers, work_mem)
- [ ] Set appropriate worker counts
- [ ] Configure connection pooling
- [ ] Enable compression in nginx

### Monitoring

- [ ] Set up log aggregation
- [ ] Configure alerting on health endpoints
- [ ] Monitor GPU utilization (Phase 2)
- [ ] Track translation latency

### Backup

- [ ] Configure PostgreSQL backup
- [ ] Backup glossaries
- [ ] Document recovery procedures

## Service Management

### Start/Stop Services

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart single service
docker compose restart gateway

# View logs
docker compose logs -f gateway
```

### Update Services

```bash
# Pull latest images
docker compose pull

# Rebuild custom images
docker compose build --no-cache

# Update with zero downtime
docker compose up -d --no-deps gateway
```

### Database Operations

```bash
# Access database
docker compose exec postgres psql -U trjm -d trjm

# Backup database
docker compose exec postgres pg_dump -U trjm trjm > backup.sql

# Restore database
cat backup.sql | docker compose exec -T postgres psql -U trjm -d trjm
```

## Troubleshooting

### Services Not Starting

```bash
# Check logs
docker compose logs gateway
docker compose logs web

# Check resource usage
docker stats

# Verify network
docker network ls
docker network inspect deploy_trjm-network
```

### Authentication Issues

```bash
# Test LDAP connection
docker compose exec gateway python -c "
from src.services.auth.ldap import get_ldap_provider
import asyncio
provider = get_ldap_provider()
result = asyncio.run(provider.authenticate('testuser', 'testpass'))
print(result)
"

# Check JWT configuration
docker compose exec gateway python -c "
from src.core.config import settings
print(f'JWT configured: {bool(settings.jwt_secret)}')
"
```

### Translation Failures

```bash
# Test LLM connection
docker compose exec gateway python -c "
from src.llm.factory import get_llm_provider
import asyncio
provider = get_llm_provider()
# Test simple completion
"

# Check model availability
curl http://localhost:8001/v1/models  # vLLM only
```

### vLLM Issues

```bash
# Check GPU availability
nvidia-smi

# Check vLLM logs
docker compose logs vllm

# Verify model loading
docker compose exec vllm curl http://localhost:8001/health
```

## Scaling

### Horizontal Scaling (Gateway)

```yaml
# docker-compose.override.yml
services:
  gateway:
    deploy:
      replicas: 3
```

### Load Balancing

Update nginx.conf for multiple gateway instances:

```nginx
upstream gateway {
    least_conn;
    server gateway1:8000;
    server gateway2:8000;
    server gateway3:8000;
}
```

### Database Connection Pooling

Add PgBouncer for high-concurrency scenarios:

```yaml
services:
  pgbouncer:
    image: edoburu/pgbouncer
    environment:
      DATABASE_URL: postgresql://trjm:pass@postgres:5432/trjm
      POOL_MODE: transaction
      MAX_CLIENT_CONN: 1000
      DEFAULT_POOL_SIZE: 20
```

## Maintenance

### Regular Tasks

- Weekly: Review audit logs
- Monthly: Rotate logs
- Quarterly: Update dependencies
- Annually: Rotate certificates

### Certificate Renewal

```bash
# Regenerate certificates
./deploy/scripts/generate-certs.sh

# Reload nginx
docker compose exec nginx nginx -s reload
```

### Log Rotation

Configure Docker log rotation:

```json
// /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```
