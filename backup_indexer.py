#!/usr/bin/env python3
"""
Backup File Indexer

This script scans backup directories and indexes all files into the PostgreSQL database
for easy searching and retrieval. It integrates with the existing S3 backup system.
"""

import os
import sys
import json
import hashlib
import mimetypes
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import psycopg2
import psycopg2.extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


class BackupIndexer:
    def __init__(self, db_config: Dict, config_file: Optional[str] = None):
        """Initialize the backup indexer."""
        self.db_config = db_config
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.conn = None
        
        # File type detection
        mimetypes.init()
        
        # Statistics tracking
        self.stats = {
            'files_processed': 0,
            'files_added': 0,
            'files_updated': 0,
            'files_skipped': 0,
            'errors': 0,
            'total_size': 0
        }
    
    def load_config(self, config_file: Optional[str]) -> Dict:
        """Load configuration from S3 backup config or defaults."""
        default_config = {
            "backup_sources": [],
            "indexing": {
                "compute_checksums": True,
                "checksum_algorithms": ["md5", "sha256"],
                "skip_hidden_files": True,
                "skip_temp_files": True,
                "max_file_size_for_checksum": 1024 * 1024 * 1024,  # 1GB
                "excluded_extensions": [".tmp", ".log", ".cache"],
                "batch_size": 1000
            },
            "database": {
                "auto_tag": True,
                "content_preview_length": 500
            }
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                    
                # Convert S3 backup config format to indexer format
                if "s3_buckets" in file_config and "local_base_path" in file_config:
                    backup_sources = []
                    for bucket in file_config["s3_buckets"]:
                        bucket_name = bucket if isinstance(bucket, str) else bucket.get("name")
                        if bucket_name:
                            backup_sources.append({
                                "name": f"S3 Bucket: {bucket_name}",
                                "type": "s3_bucket",
                                "path": os.path.join(file_config["local_base_path"], bucket_name),
                                "description": f"S3 bucket {bucket_name} synced locally"
                            })
                    default_config["backup_sources"] = backup_sources
                
                # Update with any specific indexer config
                if "indexing" in file_config:
                    default_config["indexing"].update(file_config["indexing"])
                    
                logging.info(f"Loaded configuration from {config_file}")
            except Exception as e:
                logging.error(f"Error loading config file: {e}")
        
        return default_config
    
    def setup_logging(self):
        """Configure logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('backup_indexer.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    def connect_database(self):
        """Connect to PostgreSQL database."""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            logging.info("Connected to database successfully")
        except Exception as e:
            logging.error(f"Failed to connect to database: {e}")
            raise
    
    def close_database(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logging.info("Database connection closed")
    
    def get_or_create_backup_source(self, name: str, source_type: str, path: str, description: str = "") -> int:
        """Get or create a backup source and return its ID."""
        with self.conn.cursor() as cur:
            # Check if source exists
            cur.execute(
                "SELECT id FROM backup_sources WHERE source_name = %s",
                (name,)
            )
            result = cur.fetchone()
            
            if result:
                return result[0]
            
            # Create new source
            cur.execute(
                """INSERT INTO backup_sources (source_name, source_type, source_path, description)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (name, source_type, path, description)
            )
            source_id = cur.fetchone()[0]
            logging.info(f"Created backup source: {name} (ID: {source_id})")
            return source_id
    
    def create_backup_session(self, source_id: int, command: str = "") -> int:
        """Create a new backup session and return its ID."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO backup_sessions (source_id, session_start, backup_command, status)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (source_id, datetime.now(timezone.utc), command or "Manual indexing", "running")
            )
            session_id = cur.fetchone()[0]
            logging.info(f"Created backup session: {session_id}")
            return session_id
    
    def complete_backup_session(self, session_id: int, status: str = "completed"):
        """Complete a backup session with statistics."""
        with self.conn.cursor() as cur:
            cur.execute(
                """UPDATE backup_sessions 
                   SET session_end = %s, status = %s, total_files = %s, 
                       total_size_bytes = %s, files_added = %s
                   WHERE id = %s""",
                (
                    datetime.now(timezone.utc), status, self.stats['files_processed'],
                    self.stats['total_size'], self.stats['files_added'], session_id
                )
            )
    
    def compute_file_checksum(self, file_path: str, algorithm: str = "md5") -> Optional[str]:
        """Compute file checksum."""
        try:
            if algorithm == "md5":
                hash_func = hashlib.md5()
            elif algorithm == "sha256":
                hash_func = hashlib.sha256()
            else:
                return None
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_func.update(chunk)
            
            return hash_func.hexdigest()
        except Exception as e:
            logging.warning(f"Failed to compute {algorithm} checksum for {file_path}: {e}")
            return None
    
    def get_file_metadata(self, file_path: str, relative_path: str) -> Dict:
        """Extract file metadata."""
        try:
            stat = os.stat(file_path)
            file_size = stat.st_size
            modified_time = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
            
            # Basic file info
            filename = os.path.basename(file_path)
            file_extension = os.path.splitext(filename)[1].lower()
            
            # MIME type detection
            mime_type, _ = mimetypes.guess_type(file_path)
            
            # Checksums (only for files under size limit)
            md5_checksum = None
            sha256_checksum = None
            
            if (self.config["indexing"]["compute_checksums"] and 
                file_size <= self.config["indexing"]["max_file_size_for_checksum"]):
                
                if "md5" in self.config["indexing"]["checksum_algorithms"]:
                    md5_checksum = self.compute_file_checksum(file_path, "md5")
                if "sha256" in self.config["indexing"]["checksum_algorithms"]:
                    sha256_checksum = self.compute_file_checksum(file_path, "sha256")
            
            # Compression detection
            is_compressed = file_extension in ['.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar']
            compression_type = file_extension[1:] if is_compressed else None
            
            return {
                'filename': filename,
                'file_extension': file_extension,
                'file_size_bytes': file_size,
                'file_modified_time': modified_time,
                'mime_type': mime_type,
                'md5_checksum': md5_checksum,
                'sha256_checksum': sha256_checksum,
                'is_compressed': is_compressed,
                'compression_type': compression_type,
                'relative_path': relative_path,
                'full_local_path': file_path
            }
            
        except Exception as e:
            logging.error(f"Failed to get metadata for {file_path}: {e}")
            return None
    
    def should_skip_file(self, file_path: str) -> bool:
        """Determine if file should be skipped during indexing."""
        filename = os.path.basename(file_path)
        file_extension = os.path.splitext(filename)[1].lower()
        
        # Skip hidden files if configured
        if self.config["indexing"]["skip_hidden_files"] and filename.startswith('.'):
            return True
        
        # Skip temp files if configured
        if self.config["indexing"]["skip_temp_files"] and any(
            temp in filename.lower() for temp in ['temp', 'tmp', '~']
        ):
            return True
        
        # Skip excluded extensions
        if file_extension in self.config["indexing"]["excluded_extensions"]:
            return True
        
        return False
    
    def auto_tag_file(self, metadata: Dict) -> List[str]:
        """Automatically tag files based on their characteristics."""
        if not self.config["database"]["auto_tag"]:
            return []
        
        tags = []
        extension = metadata.get('file_extension', '').lower()
        mime_type = metadata.get('mime_type', '') or ''
        filename = metadata.get('filename', '').lower()
        
        # Database files
        if extension in ['.sql', '.db', '.sqlite', '.dump', '.backup'] or 'database' in filename:
            tags.append('database')
        
        # Configuration files
        if extension in ['.conf', '.config', '.ini', '.yaml', '.yml', '.json', '.xml'] or 'config' in filename:
            tags.append('config')
        
        # Log files
        if extension in ['.log', '.out'] or 'log' in filename:
            tags.append('logs')
        
        # Documents
        if mime_type.startswith('text/') or extension in ['.pdf', '.doc', '.docx', '.txt', '.md']:
            tags.append('documents')
        
        # Images
        if mime_type.startswith('image/') or extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            tags.append('images')
        
        # Code files
        if extension in ['.py', '.js', '.java', '.cpp', '.c', '.h', '.php', '.rb', '.go', '.rs']:
            tags.append('code')
        
        # Archives
        if metadata.get('is_compressed'):
            tags.append('archive')
        
        # Media files
        if mime_type.startswith('video/') or mime_type.startswith('audio/'):
            tags.append('media')
        
        # Important files (based on keywords)
        if any(keyword in filename for keyword in ['important', 'critical', 'backup', 'master']):
            tags.append('important')
        
        return tags
    
    def get_tag_ids(self, tag_names: List[str]) -> List[int]:
        """Get tag IDs for given tag names."""
        if not tag_names:
            return []
        
        tag_ids = []
        with self.conn.cursor() as cur:
            for tag_name in tag_names:
                cur.execute("SELECT id FROM file_tags WHERE tag_name = %s", (tag_name,))
                result = cur.fetchone()
                if result:
                    tag_ids.append(result[0])
        
        return tag_ids
    
    def index_file(self, file_path: str, relative_path: str, source_id: int, session_id: int) -> bool:
        """Index a single file into the database."""
        try:
            # Get file metadata
            metadata = self.get_file_metadata(file_path, relative_path)
            if not metadata:
                self.stats['errors'] += 1
                return False
            
            # Check if file already exists
            with self.conn.cursor() as cur:
                cur.execute(
                    """SELECT id FROM backup_files 
                       WHERE source_id = %s AND relative_path = %s AND filename = %s""",
                    (source_id, relative_path, metadata['filename'])
                )
                existing_file = cur.fetchone()
                
                if existing_file:
                    # Update existing file
                    cur.execute(
                        """UPDATE backup_files SET
                           session_id = %s, full_local_path = %s, file_size_bytes = %s,
                           file_modified_time = %s, file_checksum_md5 = %s, file_checksum_sha256 = %s,
                           backup_date = %s, mime_type = %s, is_compressed = %s, compression_type = %s,
                           updated_at = CURRENT_TIMESTAMP
                           WHERE id = %s""",
                        (
                            session_id, metadata['full_local_path'], metadata['file_size_bytes'],
                            metadata['file_modified_time'], metadata['md5_checksum'], metadata['sha256_checksum'],
                            datetime.now(timezone.utc), metadata['mime_type'], metadata['is_compressed'],
                            metadata['compression_type'], existing_file[0]
                        )
                    )
                    file_id = existing_file[0]
                    self.stats['files_updated'] += 1
                    logging.debug(f"Updated file: {relative_path}")
                else:
                    # Insert new file
                    cur.execute(
                        """INSERT INTO backup_files (
                           session_id, source_id, relative_path, full_local_path, filename, file_extension,
                           file_size_bytes, file_modified_time, file_checksum_md5, file_checksum_sha256,
                           backup_date, mime_type, is_compressed, compression_type
                           ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           RETURNING id""",
                        (
                            session_id, source_id, relative_path, metadata['full_local_path'],
                            metadata['filename'], metadata['file_extension'], metadata['file_size_bytes'],
                            metadata['file_modified_time'], metadata['md5_checksum'], metadata['sha256_checksum'],
                            datetime.now(timezone.utc), metadata['mime_type'], metadata['is_compressed'],
                            metadata['compression_type']
                        )
                    )
                    file_id = cur.fetchone()[0]
                    self.stats['files_added'] += 1
                    logging.debug(f"Added file: {relative_path}")
                
                # Auto-tag the file
                tag_names = self.auto_tag_file(metadata)
                tag_ids = self.get_tag_ids(tag_names)
                
                # Remove existing tags and add new ones
                cur.execute("DELETE FROM backup_file_tags WHERE file_id = %s", (file_id,))
                for tag_id in tag_ids:
                    cur.execute(
                        "INSERT INTO backup_file_tags (file_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (file_id, tag_id)
                    )
            
            self.stats['files_processed'] += 1
            self.stats['total_size'] += metadata['file_size_bytes']
            
            # Log progress
            if self.stats['files_processed'] % 100 == 0:
                logging.info(f"Processed {self.stats['files_processed']} files...")
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to index file {file_path}: {e}")
            self.stats['errors'] += 1
            return False
    
    def scan_directory(self, source_config: Dict) -> bool:
        """Scan a directory and index all files."""
        base_path = source_config["path"]
        
        if not os.path.exists(base_path):
            logging.error(f"Backup path does not exist: {base_path}")
            return False
        
        logging.info(f"Scanning directory: {base_path}")
        
        # Create or get backup source
        source_id = self.get_or_create_backup_source(
            source_config["name"],
            source_config["type"],
            base_path,
            source_config.get("description", "")
        )
        
        # Create backup session
        session_id = self.create_backup_session(source_id, f"Directory scan: {base_path}")
        
        try:
            # Walk through all files
            for root, dirs, files in os.walk(base_path):
                # Skip hidden directories if configured
                if self.config["indexing"]["skip_hidden_files"]:
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for filename in files:
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, base_path)
                    
                    # Skip files based on rules
                    if self.should_skip_file(file_path):
                        self.stats['files_skipped'] += 1
                        continue
                    
                    # Index the file
                    self.index_file(file_path, relative_path, source_id, session_id)
            
            # Complete the session
            self.complete_backup_session(session_id, "completed")
            logging.info(f"Completed scanning directory: {base_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error scanning directory {base_path}: {e}")
            self.complete_backup_session(session_id, "failed")
            return False
    
    def index_all_sources(self):
        """Index all configured backup sources."""
        logging.info("Starting backup indexing process")
        
        if not self.config["backup_sources"]:
            logging.warning("No backup sources configured")
            return
        
        for source_config in self.config["backup_sources"]:
            try:
                logging.info(f"Indexing source: {source_config['name']}")
                self.scan_directory(source_config)
            except Exception as e:
                logging.error(f"Failed to index source {source_config['name']}: {e}")
                self.stats['errors'] += 1
        
        # Print final statistics
        logging.info("Indexing completed!")
        logging.info(f"Files processed: {self.stats['files_processed']}")
        logging.info(f"Files added: {self.stats['files_added']}")
        logging.info(f"Files updated: {self.stats['files_updated']}")
        logging.info(f"Files skipped: {self.stats['files_skipped']}")
        logging.info(f"Errors: {self.stats['errors']}")
        logging.info(f"Total size indexed: {self.stats['total_size'] / (1024**3):.2f} GB")
    
    def create_database_backup_entry(self, file_id: int, db_type: str, db_name: str = None, 
                                   backup_type: str = "full", dump_command: str = None):
        """Create a database backup entry for database files."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO database_backups (file_id, database_type, database_name, backup_type, dump_command)
                   VALUES (%s, %s, %s, %s, %s)""",
                (file_id, db_type, db_name, backup_type, dump_command)
            )


def main():
    parser = argparse.ArgumentParser(description="Index backup files into PostgreSQL database")
    parser.add_argument("--config", "-c", help="Path to configuration file")
    parser.add_argument("--db-host", default="localhost", help="Database host")
    parser.add_argument("--db-port", default="5432", help="Database port")
    parser.add_argument("--db-name", default="backup_catalog", help="Database name")
    parser.add_argument("--db-user", default="postgres", help="Database user")
    parser.add_argument("--db-password", help="Database password")
    parser.add_argument("--source-path", help="Single source path to index")
    parser.add_argument("--source-name", help="Name for single source")
    parser.add_argument("--source-type", default="local_dir", help="Type for single source")
    parser.add_argument("--dry-run", action="store_true", help="Dry run - don't actually index")
    
    args = parser.parse_args()
    
    # Database configuration
    db_config = {
        "host": args.db_host,
        "port": args.db_port,
        "database": args.db_name,
        "user": args.db_user,
        "password": args.db_password or os.getenv("DB_PASSWORD")
    }
    
    if not db_config["password"]:
        db_config["password"] = input("Database password: ")
    
    try:
        # Initialize indexer
        indexer = BackupIndexer(db_config, args.config)
        
        if args.dry_run:
            logging.info("DRY RUN MODE - No files will be indexed")
            return
        
        # Connect to database
        indexer.connect_database()
        
        # Handle single source indexing
        if args.source_path:
            source_config = {
                "name": args.source_name or f"Manual: {args.source_path}",
                "type": args.source_type,
                "path": args.source_path,
                "description": f"Manually added source: {args.source_path}"
            }
            indexer.config["backup_sources"] = [source_config]
        
        # Index all sources
        indexer.index_all_sources()
        
    except KeyboardInterrupt:
        logging.info("Indexing interrupted by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        if 'indexer' in locals():
            indexer.close_database()


if __name__ == "__main__":
    main() 