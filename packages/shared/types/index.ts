/**
 * TRJM Shared TypeScript Types
 * ============================
 * Type definitions shared between frontend and API contracts
 */

// ============================================================================
// Language & Style Types
// ============================================================================

export type LanguageCode = 'en' | 'ar' | 'fr' | 'de' | 'es' | 'auto';

export type StylePreset = 'formal_msa' | 'neutral' | 'marketing' | 'government_memo';

export type ContentType =
  | 'general'
  | 'email'
  | 'legal'
  | 'technical'
  | 'marketing'
  | 'ui_strings'
  | 'government';

export type FormalityLevel = 'informal' | 'neutral' | 'formal' | 'highly_formal';

// ============================================================================
// Special Elements
// ============================================================================

export type SpecialElementType =
  | 'url'
  | 'email'
  | 'placeholder'
  | 'code'
  | 'html'
  | 'bracketed'
  | 'number'
  | 'date'
  | 'currency'
  | 'entity'
  | 'technical_term';

export interface Position {
  start: number;
  end: number;
}

export interface SpecialElement {
  type: SpecialElementType;
  value: string;
  position?: Position;
  protect: boolean;
}

// ============================================================================
// Glossary Types
// ============================================================================

export interface GlossaryEntry {
  source: string;
  target: string;
  case_sensitive?: boolean;
  context?: string;
}

export interface Glossary {
  id: string;
  name: string;
  description?: string;
  entries: GlossaryEntry[];
  version: number;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// Translation Request/Response
// ============================================================================

export interface TranslationRequest {
  text: string;
  source_language?: LanguageCode;
  target_language?: LanguageCode;
  style_preset?: StylePreset;
  glossary_id?: string;
  protected_patterns?: string[];
}

export interface TranslationResponse {
  job_id: string;
  translation: string;
  source_language: LanguageCode;
  target_language: LanguageCode;
  confidence: number;
  qa_report: QAReport;
  processing_time_ms: number;
  retries: number;
}

// ============================================================================
// QA Report Types
// ============================================================================

export type IssueSeverity = 'critical' | 'major' | 'minor' | 'suggestion';

export type IssueCategory =
  | 'meaning'
  | 'omission'
  | 'addition'
  | 'numbers'
  | 'entities'
  | 'glossary'
  | 'protected_tokens'
  | 'grammar'
  | 'punctuation'
  | 'formatting'
  | 'leftover_source'
  | 'cultural';

export interface QAIssue {
  id?: string;
  category: IssueCategory;
  severity: IssueSeverity;
  description: string;
  source_segment?: string;
  translation_segment?: string;
  suggested_fix?: string;
  auto_fixed?: boolean;
}

export interface RiskySpan {
  text: string;
  reason: string;
  risk_level?: 'low' | 'medium' | 'high';
  position?: Position;
  requires_human_review?: boolean;
}

export interface QAReport {
  confidence_score: number;
  confidence_level?: 'excellent' | 'good' | 'acceptable' | 'poor' | 'unacceptable';
  issues: QAIssue[];
  glossary_compliance: boolean;
  protected_tokens_intact: boolean;
  risky_spans?: RiskySpan[];
  reviewer_notes?: string;
  metrics?: QAMetrics;
}

export interface QAMetrics {
  total_issues: number;
  critical_issues: number;
  major_issues: number;
  minor_issues: number;
  suggestions: number;
  source_char_count: number;
  translation_char_count: number;
  length_ratio: number;
}

// ============================================================================
// Job Types
// ============================================================================

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'expired';

export type JobType = 'text' | 'file';

export interface Job {
  id: string;
  user_id: string;
  job_type: JobType;
  status: JobStatus;
  source_language: LanguageCode;
  target_language: LanguageCode;
  style_preset?: StylePreset;
  input_text?: string;
  output_text?: string;
  file_name?: string;
  file_path?: string;
  qa_report?: QAReport;
  confidence?: number;
  error_message?: string;
  created_at: string;
  completed_at?: string;
  expires_at: string;
}

// ============================================================================
// User & Auth Types
// ============================================================================

export type Feature =
  | 'TRANSLATE_TEXT'
  | 'UPLOAD_FILES'
  | 'TRANSLATE_DOCX'
  | 'TRANSLATE_PDF'
  | 'TRANSLATE_MSG'
  | 'USE_GLOSSARY'
  | 'MANAGE_GLOSSARY'
  | 'VIEW_HISTORY'
  | 'EXPORT_RESULTS'
  | 'ADMIN_PANEL';

export interface Role {
  id: string;
  name: string;
  description?: string;
  features: Feature[];
  is_default: boolean;
}

export interface User {
  id: string;
  username: string;
  email?: string;
  display_name?: string;
  role: Role;
  created_at: string;
  last_login?: string;
}

export interface AuthResponse {
  user: User;
  token?: string; // Only if not using httpOnly cookies
  expires_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

// ============================================================================
// File Translation Types
// ============================================================================

export type SupportedFileType = 'txt' | 'docx' | 'pdf' | 'msg';

export interface FileUploadResponse {
  job_id: string;
  file_name: string;
  file_type: SupportedFileType;
  file_size: number;
  status: JobStatus;
}

export interface FileTranslationResult {
  job_id: string;
  original_file_name: string;
  translated_file_name: string;
  download_url: string;
  translation_summary?: string;
  qa_report: QAReport;
}

// ============================================================================
// API Error Types
// ============================================================================

export interface APIError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  correlation_id?: string;
}

// ============================================================================
// Audit Log Types
// ============================================================================

export type AuditAction =
  | 'login'
  | 'logout'
  | 'translation_started'
  | 'translation_completed'
  | 'file_uploaded'
  | 'file_downloaded'
  | 'glossary_created'
  | 'glossary_updated'
  | 'glossary_deleted'
  | 'role_created'
  | 'role_updated'
  | 'role_deleted'
  | 'user_role_changed';

export interface AuditLog {
  id: string;
  user_id: string;
  action: AuditAction;
  resource?: string;
  details?: Record<string, unknown>;
  ip_address?: string;
  timestamp: string;
}
