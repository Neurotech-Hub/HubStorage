-- Backup Catalog Database Schema
-- This schema tracks backup files from S3 and local storage for easy searching and restoration

-- Create the main database tables
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For text search

-- Backup Sources table - tracks different backup sources (S3 buckets, local dirs, etc.)
CREATE TABLE backup_sources (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(255) NOT NULL UNIQUE,
    source_type VARCHAR(50) NOT NULL CHECK (source_type IN ('s3_bucket', 'local_dir', 'database', 'other')),
    source_path TEXT NOT NULL, -- S3 bucket name or local path
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Backup Sessions table - tracks individual backup runs/sessions
CREATE TABLE backup_sessions (
    id SERIAL PRIMARY KEY,
    session_uuid UUID DEFAULT uuid_generate_v4(),
    source_id INTEGER REFERENCES backup_sources(id) ON DELETE CASCADE,
    session_start TIMESTAMP WITH TIME ZONE NOT NULL,
    session_end TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'partial')),
    total_files INTEGER DEFAULT 0,
    total_size_bytes BIGINT DEFAULT 0,
    files_added INTEGER DEFAULT 0,
    files_updated INTEGER DEFAULT 0,
    files_deleted INTEGER DEFAULT 0,
    error_message TEXT,
    backup_command TEXT, -- The command used for backup
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- File catalog table - tracks individual files in backups
CREATE TABLE backup_files (
    id SERIAL PRIMARY KEY,
    file_uuid UUID DEFAULT uuid_generate_v4(),
    session_id INTEGER REFERENCES backup_sessions(id) ON DELETE CASCADE,
    source_id INTEGER REFERENCES backup_sources(id) ON DELETE CASCADE,
    
    -- File identification
    relative_path TEXT NOT NULL, -- Path relative to backup source
    full_local_path TEXT NOT NULL, -- Full path in local storage
    original_path TEXT, -- Original path in source system (e.g., S3 key)
    filename VARCHAR(255) NOT NULL,
    file_extension VARCHAR(20),
    
    -- File metadata
    file_size_bytes BIGINT,
    file_modified_time TIMESTAMP WITH TIME ZONE,
    file_checksum_md5 VARCHAR(32),
    file_checksum_sha256 VARCHAR(64),
    
    -- Backup metadata
    backup_date TIMESTAMP WITH TIME ZONE NOT NULL,
    is_latest_version BOOLEAN DEFAULT true,
    file_status VARCHAR(20) DEFAULT 'active' CHECK (file_status IN ('active', 'deleted', 'replaced', 'corrupted')),
    
    -- Content metadata
    mime_type VARCHAR(100),
    is_compressed BOOLEAN DEFAULT false,
    compression_type VARCHAR(20),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- File tags table - for categorizing and tagging files
CREATE TABLE file_tags (
    id SERIAL PRIMARY KEY,
    tag_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    color VARCHAR(7), -- Hex color for UI
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Many-to-many relationship between files and tags
CREATE TABLE backup_file_tags (
    file_id INTEGER REFERENCES backup_files(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES file_tags(id) ON DELETE CASCADE,
    PRIMARY KEY (file_id, tag_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Database backup metadata table - specific to database backups
CREATE TABLE database_backups (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES backup_files(id) ON DELETE CASCADE,
    database_type VARCHAR(50) NOT NULL, -- postgresql, mysql, sqlite, etc.
    database_name VARCHAR(255),
    database_version VARCHAR(50),
    backup_type VARCHAR(20) CHECK (backup_type IN ('full', 'incremental', 'differential')),
    is_compressed BOOLEAN DEFAULT false,
    compression_ratio DECIMAL(5,2),
    dump_command TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Search index table - for full text search optimization
CREATE TABLE search_index (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES backup_files(id) ON DELETE CASCADE,
    search_vector tsvector,
    keywords TEXT[], -- Array of searchable keywords
    content_preview TEXT, -- First few lines for preview
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Backup restoration tracking
CREATE TABLE restoration_requests (
    id SERIAL PRIMARY KEY,
    request_uuid UUID DEFAULT uuid_generate_v4(),
    file_id INTEGER REFERENCES backup_files(id) ON DELETE CASCADE,
    requested_by VARCHAR(255),
    restore_destination TEXT,
    restore_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    error_message TEXT,
    notes TEXT
);

-- Indexes for performance
CREATE INDEX idx_backup_files_session_id ON backup_files(session_id);
CREATE INDEX idx_backup_files_source_id ON backup_files(source_id);
CREATE INDEX idx_backup_files_filename ON backup_files(filename);
CREATE INDEX idx_backup_files_extension ON backup_files(file_extension);
CREATE INDEX idx_backup_files_backup_date ON backup_files(backup_date);
CREATE INDEX idx_backup_files_latest_version ON backup_files(is_latest_version);
CREATE INDEX idx_backup_files_relative_path ON backup_files(relative_path);
CREATE INDEX idx_backup_files_full_path ON backup_files(full_local_path);

-- Full text search indexes
CREATE INDEX idx_search_vector ON search_index USING GIN(search_vector);
CREATE INDEX idx_search_keywords ON search_index USING GIN(keywords);
CREATE INDEX idx_backup_files_filename_trgm ON backup_files USING GIN(filename gin_trgm_ops);
CREATE INDEX idx_backup_files_relative_path_trgm ON backup_files USING GIN(relative_path gin_trgm_ops);

-- Indexes for backup sessions
CREATE INDEX idx_backup_sessions_source_id ON backup_sessions(source_id);
CREATE INDEX idx_backup_sessions_status ON backup_sessions(status);
CREATE INDEX idx_backup_sessions_start_time ON backup_sessions(session_start);

-- Triggers for updating timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_backup_sources_updated_at BEFORE UPDATE ON backup_sources FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_backup_sessions_updated_at BEFORE UPDATE ON backup_sessions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_backup_files_updated_at BEFORE UPDATE ON backup_files FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to update search index when files are added/updated
CREATE OR REPLACE FUNCTION update_search_index()
RETURNS TRIGGER AS $$
BEGIN
    -- Create search vector from filename, relative path, and other searchable fields
    INSERT INTO search_index (file_id, search_vector, keywords) 
    VALUES (
        NEW.id,
        to_tsvector('english', 
            COALESCE(NEW.filename, '') || ' ' || 
            COALESCE(NEW.relative_path, '') || ' ' ||
            COALESCE(NEW.file_extension, '') || ' ' ||
            COALESCE(NEW.mime_type, '')
        ),
        ARRAY[
            NEW.filename,
            NEW.file_extension,
            CASE WHEN NEW.relative_path IS NOT NULL THEN split_part(NEW.relative_path, '/', 1) END
        ]
    ) ON CONFLICT (file_id) DO UPDATE SET
        search_vector = EXCLUDED.search_vector,
        keywords = EXCLUDED.keywords;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER trigger_update_search_index 
    AFTER INSERT OR UPDATE ON backup_files 
    FOR EACH ROW EXECUTE FUNCTION update_search_index();

-- Views for common queries
CREATE VIEW latest_backup_files AS
SELECT 
    bf.*,
    bs.session_start,
    bs.status as session_status,
    src.source_name,
    src.source_type
FROM backup_files bf
JOIN backup_sessions bs ON bf.session_id = bs.id
JOIN backup_sources src ON bf.source_id = src.id
WHERE bf.is_latest_version = true 
  AND bf.file_status = 'active';

CREATE VIEW backup_summary AS
SELECT 
    src.source_name,
    src.source_type,
    COUNT(bf.id) as total_files,
    SUM(bf.file_size_bytes) as total_size_bytes,
    MAX(bf.backup_date) as latest_backup,
    COUNT(DISTINCT bf.session_id) as total_sessions
FROM backup_sources src
LEFT JOIN backup_files bf ON src.id = bf.source_id
WHERE bf.file_status = 'active'
GROUP BY src.id, src.source_name, src.source_type;

-- Insert default file tags
INSERT INTO file_tags (tag_name, description, color) VALUES 
('database', 'Database backup files', '#2563eb'),
('config', 'Configuration files', '#dc2626'),
('logs', 'Log files', '#16a34a'),
('documents', 'Document files', '#ca8a04'),
('images', 'Image files', '#9333ea'),
('code', 'Source code files', '#ea580c'),
('archive', 'Archive/compressed files', '#64748b'),
('important', 'Important/critical files', '#dc2626'),
('temporary', 'Temporary files', '#6b7280'),
('media', 'Media files (audio/video)', '#ec4899');

-- Insert example backup source (using the config from the existing system)
INSERT INTO backup_sources (source_name, source_type, source_path, description) VALUES 
('S3 Primary Backup', 's3_bucket', 'F:/S3_Backup', 'Primary S3 bucket backup location from existing sync system');

COMMENT ON TABLE backup_sources IS 'Tracks different backup sources like S3 buckets, local directories, databases';
COMMENT ON TABLE backup_sessions IS 'Records individual backup sessions/runs with their metadata';
COMMENT ON TABLE backup_files IS 'Catalog of all backup files with metadata and search information';
COMMENT ON TABLE file_tags IS 'Tags for categorizing backup files';
COMMENT ON TABLE database_backups IS 'Additional metadata specific to database backup files';
COMMENT ON TABLE search_index IS 'Full-text search index for efficient file searching';
COMMENT ON TABLE restoration_requests IS 'Tracks file restoration requests and their status'; 