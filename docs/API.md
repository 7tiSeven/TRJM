# TRJM API Documentation

## Base URL

- Development: `https://localhost:8000`
- Production: Configure based on deployment

## Authentication

All API endpoints (except `/auth/login` and `/health`) require authentication via JWT cookie.

### Login

```http
POST /auth/login
Content-Type: application/json

{
  "username": "user",
  "password": "password"
}
```

**Response:**
```json
{
  "user": {
    "id": "uuid",
    "username": "user",
    "email": "user@example.com",
    "display_name": "User Name",
    "role": {
      "id": "uuid",
      "name": "User"
    },
    "features": ["translate_text", "upload_files"]
  },
  "message": "Login successful"
}
```

### Logout

```http
POST /auth/logout
```

### Refresh Token

```http
POST /auth/refresh
```

### Get Current User

```http
GET /auth/me
```

---

## Translation

### Translate Text

```http
POST /translation/translate
Content-Type: application/json

{
  "text": "Hello, how are you?",
  "source_language": "auto",
  "target_language": "ar",
  "style_preset": "neutral",
  "glossary_id": "optional-uuid"
}
```

**Parameters:**
- `text` (required): Text to translate (max 10,000 characters)
- `source_language`: Source language code or "auto" (default: "auto")
- `target_language` (required): Target language code ("ar" or "en")
- `style_preset`: Translation style ("neutral", "formal", "casual", "technical", "literary")
- `glossary_id`: Optional glossary UUID

**Response:**
```json
{
  "job_id": "uuid",
  "source_text": "Hello, how are you?",
  "translation": "مرحباً، كيف حالك؟",
  "source_language": "en",
  "target_language": "ar",
  "confidence": 0.92,
  "qa_report": {
    "issues": [],
    "glossary_compliance": 1.0,
    "overall_quality": "excellent"
  },
  "style_preset": "neutral",
  "processing_time_ms": 1250
}
```

### Get Available Styles

```http
GET /translation/styles
```

**Response:**
```json
{
  "presets": [
    {
      "value": "neutral",
      "label": "Neutral",
      "description": "Balanced, standard translation"
    }
  ]
}
```

### Get Supported Languages

```http
GET /translation/languages
```

---

## Files

### Upload and Translate File

```http
POST /files/translate
Content-Type: multipart/form-data

file: <binary>
target_language: ar
style_preset: neutral
glossary_id: optional-uuid
```

**Supported Formats:**
- `.txt` (Plain text)
- `.docx` (Microsoft Word)
- `.pdf` (PDF - text only)
- `.msg` (Outlook email)

**Response:**
```json
{
  "job_id": "uuid",
  "file_name": "document.docx",
  "file_type": "docx",
  "file_size": 12345,
  "status": "completed",
  "translated_file_name": "document_ar.docx",
  "confidence": 0.88,
  "download_ready": true
}
```

### Check File Translation Status

```http
GET /files/{job_id}/status
```

### Download Translated File

```http
GET /files/{job_id}/download
```

Returns binary file with `Content-Disposition` header.

### Get Supported Formats

```http
GET /files/supported-formats
```

---

## Glossary

### List Glossaries

```http
GET /glossary
```

**Response:**
```json
{
  "glossaries": [
    {
      "id": "uuid",
      "name": "Technical Terms",
      "description": "IT terminology",
      "entry_count": 150,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-15T00:00:00Z"
    }
  ]
}
```

### Create Glossary

```http
POST /glossary
Content-Type: application/json

{
  "name": "Medical Terms",
  "description": "Healthcare terminology"
}
```

### Get Glossary

```http
GET /glossary/{glossary_id}
```

### Update Glossary

```http
PUT /glossary/{glossary_id}
Content-Type: application/json

{
  "name": "Updated Name",
  "description": "Updated description"
}
```

### Delete Glossary

```http
DELETE /glossary/{glossary_id}
```

### Get Glossary Entries

```http
GET /glossary/{glossary_id}/entries
```

### Add Entry

```http
POST /glossary/{glossary_id}/entries
Content-Type: application/json

{
  "source_term": "machine learning",
  "target_term": "التعلم الآلي",
  "context": "AI/ML domain"
}
```

### Update Entry

```http
PUT /glossary/{glossary_id}/entries/{entry_id}
Content-Type: application/json

{
  "target_term": "تعلم الآلة"
}
```

### Delete Entry

```http
DELETE /glossary/{glossary_id}/entries/{entry_id}
```

### Import CSV

```http
POST /glossary/{glossary_id}/import
Content-Type: multipart/form-data

file: <csv file>
```

CSV format:
```csv
source_term,target_term,context
machine learning,التعلم الآلي,AI domain
```

### Export CSV

```http
GET /glossary/{glossary_id}/export
```

---

## History

### List Jobs

```http
GET /history?page=1&limit=10&job_type=text&status=completed&search=hello
```

**Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 10, max: 100)
- `job_type`: Filter by type ("text" or "file")
- `status`: Filter by status ("pending", "processing", "completed", "failed")
- `search`: Search in input/output text

**Response:**
```json
{
  "jobs": [...],
  "total": 150,
  "page": 1,
  "limit": 10,
  "pages": 15
}
```

### Get Job Details

```http
GET /history/{job_id}
```

### Delete Job

```http
DELETE /history/{job_id}
```

### Get Statistics

```http
GET /history/stats
```

**Response:**
```json
{
  "total_jobs": 1500,
  "completed_jobs": 1450,
  "failed_jobs": 50,
  "avg_confidence": 0.89,
  "jobs_by_type": {
    "text": 1200,
    "file": 300
  },
  "jobs_by_status": {
    "completed": 1450,
    "failed": 50
  }
}
```

---

## Admin

### List Roles

```http
GET /admin/roles
```

### Create Role

```http
POST /admin/roles
Content-Type: application/json

{
  "name": "Editor",
  "description": "Can edit glossaries",
  "features": ["translate_text", "use_glossary", "manage_glossary"]
}
```

### Update Role

```http
PUT /admin/roles/{role_id}
Content-Type: application/json

{
  "features": ["translate_text", "use_glossary"]
}
```

### Delete Role

```http
DELETE /admin/roles/{role_id}
```

### List Users

```http
GET /admin/users?page=1&limit=10&search=john
```

### Update User Role

```http
PUT /admin/users/{user_id}/role
Content-Type: application/json

{
  "role_id": "uuid"
}
```

### Get Available Features

```http
GET /admin/features
```

**Response:**
```json
{
  "features": [
    {"name": "translate_text", "description": "Translate text content"},
    {"name": "upload_files", "description": "Upload files for translation"},
    {"name": "admin_panel", "description": "Access admin panel"}
  ]
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message",
  "correlation_id": "uuid"
}
```

### Status Codes

- `400` - Bad Request (invalid input)
- `401` - Unauthorized (not logged in)
- `403` - Forbidden (missing feature)
- `404` - Not Found
- `413` - Request Entity Too Large (file too big)
- `422` - Validation Error
- `429` - Too Many Requests (rate limited)
- `500` - Internal Server Error

---

## Rate Limiting

Default limits:
- 60 requests per minute per user
- 10 request burst allowed

Headers returned:
- `X-RateLimit-Limit`: Maximum requests
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Reset timestamp

---

## Webhooks (Future)

Planned webhook support for:
- Translation completed
- File processing completed
- Job failed

---

## SDKs

### Python

```python
import httpx

class TRJMClient:
    def __init__(self, base_url):
        self.client = httpx.Client(base_url=base_url)

    def login(self, username, password):
        resp = self.client.post("/auth/login", json={
            "username": username,
            "password": password
        })
        return resp.json()

    def translate(self, text, target_language="ar"):
        resp = self.client.post("/translation/translate", json={
            "text": text,
            "target_language": target_language
        })
        return resp.json()
```

### JavaScript

```javascript
class TRJMClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
  }

  async login(username, password) {
    const resp = await fetch(`${this.baseUrl}/auth/login`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    return resp.json();
  }

  async translate(text, targetLanguage = 'ar') {
    const resp = await fetch(`${this.baseUrl}/translation/translate`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, target_language: targetLanguage })
    });
    return resp.json();
  }
}
```
