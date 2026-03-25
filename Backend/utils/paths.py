"""
Centralized path helper for data directories.
All runtime artifacts live in the top-level `data/` directory alongside `Backend/` and `Frontend/`.
"""
from pathlib import Path
from typing import Optional

# Backend directory (this file is under Backend/utils)
BACKEND_DIR = Path(__file__).resolve().parents[1]
# Project root
PROJECT_ROOT = BACKEND_DIR.parent
# Data directory at the same level as Backend/
DATA_DIR = PROJECT_ROOT / "data"

# Subdirectories
UPLOAD_DIR = DATA_DIR / "uploads"
UNZIP_DIR = DATA_DIR / "unzipped"
USER_DIR = DATA_DIR / "users"
LOG_DIR = DATA_DIR / "logs"
OUTPUT_DOC_DIR = DATA_DIR / "output_doc"
CHUNK_OUTPUT_DIR = DATA_DIR / "chunk_output"


def get_uuid_dir(base_dir: Path, uuid_str: str) -> Path:
    """Get UUID-specific subdirectory path."""
    return base_dir / uuid_str


def get_output_doc_dir(uuid_str: str) -> Path:
    """Get output document-specific directory path."""
    return get_uuid_dir(OUTPUT_DOC_DIR, uuid_str)


def get_chunk_output_dir(uuid_str: str) -> Path:
    """Get chunk output-specific directory path."""
    return get_uuid_dir(CHUNK_OUTPUT_DIR, uuid_str)


def get_unzip_dir(uuid_str: str) -> Path:
    """Get unzip-specific directory path."""
    return get_uuid_dir(UNZIP_DIR, uuid_str)


def ensure_directories() -> None:
    """Ensure that all required directories exist."""
    for p in [
        DATA_DIR,
        UPLOAD_DIR,
        UNZIP_DIR,
        USER_DIR,
        LOG_DIR,
        OUTPUT_DOC_DIR,
        CHUNK_OUTPUT_DIR,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def ensure_uuid_directories(uuid_str: str) -> None:
    """Ensure that all UUID-specific directories exist."""
    for p in [
        get_output_doc_dir(uuid_str),
        get_chunk_output_dir(uuid_str),
        get_unzip_dir(uuid_str),
    ]:
        p.mkdir(parents=True, exist_ok=True)


# Ensure on import
ensure_directories()