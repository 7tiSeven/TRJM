-- =============================================================================
-- TRJM Database Initialization
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Roles Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- Role Features Table (Feature flags per role)
-- =============================================================================
CREATE TABLE IF NOT EXISTS role_features (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    feature_name VARCHAR(50) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(role_id, feature_name)
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_role_features_role_id ON role_features(role_id);

-- =============================================================================
-- Users Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255),
    display_name VARCHAR(255),
    role_id UUID NOT NULL REFERENCES roles(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);

-- =============================================================================
-- Jobs Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_type VARCHAR(20) NOT NULL CHECK (job_type IN ('text', 'file')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'expired')),
    source_language VARCHAR(10) NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    style_preset VARCHAR(50),
    input_text TEXT,
    output_text TEXT,
    file_name VARCHAR(255),
    file_path VARCHAR(500),
    output_file_path VARCHAR(500),
    glossary_id UUID,
    qa_report JSONB,
    confidence DECIMAL(3, 2),
    error_message TEXT,
    retries INTEGER DEFAULT 0,
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_expires_at ON jobs(expires_at);

-- =============================================================================
-- Glossaries Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS glossaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    source_language VARCHAR(10) NOT NULL DEFAULT 'en',
    target_language VARCHAR(10) NOT NULL DEFAULT 'ar',
    is_global BOOLEAN DEFAULT FALSE,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_glossaries_user_id ON glossaries(user_id);

-- =============================================================================
-- Glossary Entries Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS glossary_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    glossary_id UUID NOT NULL REFERENCES glossaries(id) ON DELETE CASCADE,
    source_term VARCHAR(500) NOT NULL,
    target_term VARCHAR(500) NOT NULL,
    case_sensitive BOOLEAN DEFAULT FALSE,
    context TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_glossary_entries_glossary_id ON glossary_entries(glossary_id);
CREATE INDEX IF NOT EXISTS idx_glossary_entries_source_term ON glossary_entries(source_term);

-- =============================================================================
-- Audit Logs Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(255),
    resource_id UUID,
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    correlation_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_correlation_id ON audit_logs(correlation_id);

-- =============================================================================
-- Insert Default Roles
-- =============================================================================
INSERT INTO roles (id, name, description, is_default) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Administrator', 'Full system access', FALSE),
    ('00000000-0000-0000-0000-000000000002', 'Translator', 'Translation and glossary access', FALSE),
    ('00000000-0000-0000-0000-000000000003', 'Normal User', 'Basic translation access', TRUE)
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- Insert Default Role Features
-- =============================================================================

-- Administrator features (all enabled)
INSERT INTO role_features (role_id, feature_name, enabled) VALUES
    ('00000000-0000-0000-0000-000000000001', 'TRANSLATE_TEXT', TRUE),
    ('00000000-0000-0000-0000-000000000001', 'UPLOAD_FILES', TRUE),
    ('00000000-0000-0000-0000-000000000001', 'TRANSLATE_DOCX', TRUE),
    ('00000000-0000-0000-0000-000000000001', 'TRANSLATE_PDF', TRUE),
    ('00000000-0000-0000-0000-000000000001', 'TRANSLATE_MSG', TRUE),
    ('00000000-0000-0000-0000-000000000001', 'USE_GLOSSARY', TRUE),
    ('00000000-0000-0000-0000-000000000001', 'MANAGE_GLOSSARY', TRUE),
    ('00000000-0000-0000-0000-000000000001', 'VIEW_HISTORY', TRUE),
    ('00000000-0000-0000-0000-000000000001', 'EXPORT_RESULTS', TRUE),
    ('00000000-0000-0000-0000-000000000001', 'ADMIN_PANEL', TRUE)
ON CONFLICT (role_id, feature_name) DO NOTHING;

-- Translator features
INSERT INTO role_features (role_id, feature_name, enabled) VALUES
    ('00000000-0000-0000-0000-000000000002', 'TRANSLATE_TEXT', TRUE),
    ('00000000-0000-0000-0000-000000000002', 'UPLOAD_FILES', TRUE),
    ('00000000-0000-0000-0000-000000000002', 'TRANSLATE_DOCX', TRUE),
    ('00000000-0000-0000-0000-000000000002', 'TRANSLATE_PDF', TRUE),
    ('00000000-0000-0000-0000-000000000002', 'TRANSLATE_MSG', TRUE),
    ('00000000-0000-0000-0000-000000000002', 'USE_GLOSSARY', TRUE),
    ('00000000-0000-0000-0000-000000000002', 'MANAGE_GLOSSARY', TRUE),
    ('00000000-0000-0000-0000-000000000002', 'VIEW_HISTORY', TRUE),
    ('00000000-0000-0000-0000-000000000002', 'EXPORT_RESULTS', TRUE),
    ('00000000-0000-0000-0000-000000000002', 'ADMIN_PANEL', FALSE)
ON CONFLICT (role_id, feature_name) DO NOTHING;

-- Normal User features (limited)
INSERT INTO role_features (role_id, feature_name, enabled) VALUES
    ('00000000-0000-0000-0000-000000000003', 'TRANSLATE_TEXT', TRUE),
    ('00000000-0000-0000-0000-000000000003', 'UPLOAD_FILES', FALSE),
    ('00000000-0000-0000-0000-000000000003', 'TRANSLATE_DOCX', FALSE),
    ('00000000-0000-0000-0000-000000000003', 'TRANSLATE_PDF', FALSE),
    ('00000000-0000-0000-0000-000000000003', 'TRANSLATE_MSG', FALSE),
    ('00000000-0000-0000-0000-000000000003', 'USE_GLOSSARY', TRUE),
    ('00000000-0000-0000-0000-000000000003', 'MANAGE_GLOSSARY', FALSE),
    ('00000000-0000-0000-0000-000000000003', 'VIEW_HISTORY', TRUE),
    ('00000000-0000-0000-0000-000000000003', 'EXPORT_RESULTS', FALSE),
    ('00000000-0000-0000-0000-000000000003', 'ADMIN_PANEL', FALSE)
ON CONFLICT (role_id, feature_name) DO NOTHING;

-- =============================================================================
-- Function to auto-update updated_at timestamp
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to relevant tables
DROP TRIGGER IF EXISTS update_roles_updated_at ON roles;
CREATE TRIGGER update_roles_updated_at
    BEFORE UPDATE ON roles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_glossaries_updated_at ON glossaries;
CREATE TRIGGER update_glossaries_updated_at
    BEFORE UPDATE ON glossaries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_glossary_entries_updated_at ON glossary_entries;
CREATE TRIGGER update_glossary_entries_updated_at
    BEFORE UPDATE ON glossary_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Function to clean up expired jobs
-- =============================================================================
CREATE OR REPLACE FUNCTION cleanup_expired_jobs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM jobs WHERE expires_at < NOW() AND status != 'processing';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Grant permissions (if running as superuser)
-- =============================================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trjm;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO trjm;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO trjm;
