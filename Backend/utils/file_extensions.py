"""
Centralized file extension configuration for the Digital Kuroshio project.
This module contains all file extension definitions used throughout the codebase.
"""

# Delphi/Pascal source file extensions
PASCAL_SOURCE_EXTENSIONS = (".pas", ".dpr")

# Delphi form definition file extensions
FORM_EXTENSIONS = (".dfm",)

# All Delphi-related file extensions
DELPHI_EXTENSIONS = PASCAL_SOURCE_EXTENSIONS + FORM_EXTENSIONS

# File extensions to exclude from processing
EXCLUDED_EXTENSIONS = (
    "DS_Store",  # macOS system files
    "~pas",  # Delphi backup files
    "~dfm",  # Delphi backup files
    "~ddp",  # Delphi backup files
    "exe",  # Executable files
    "rar",  # Archive files
    "doc",  # Microsoft Word
    "docx",  # Microsoft Word
    "pdf",  # PDF files
    "xlsx",  # Microsoft Excel
    "xls",  # Microsoft Excel
    "zip",  # Archive files
    "log",  # Log files
    "bmp",  # Image files
    "dll",  # Dynamic link libraries
    "dcu",  # Delphi compiled units
    "cfg",  # Configuration files
    "~pa",  # Delphi backup files
    "MB",  # Unknown extension
    "~df",  # Delphi backup files
    "~dpr",  # Delphi backup files
    "~dp",  # Delphi backup files
    "bak",  # Backup files
    "txt",  # Text files
    "bkm",  # Bookmark files
    "dfm",  # Form files (processed separately)
    "dcu",  # Delphi compiled units
)

# File extensions that should be processed
PROCESSABLE_EXTENSIONS = (".pas", ".dpr", ".dfm")


def is_pascal_source(filename: str) -> bool:
    """Check if a filename represents a Pascal source file."""
    return filename.lower().endswith(PASCAL_SOURCE_EXTENSIONS)


def is_form_file(filename: str) -> bool:
    """Check if a filename represents a Delphi form file."""
    return filename.lower().endswith(FORM_EXTENSIONS)


def is_delphi_file(filename: str) -> bool:
    """Check if a filename represents any Delphi-related file."""
    return filename.lower().endswith(DELPHI_EXTENSIONS)


def is_excluded_file(filename: str) -> bool:
    """Check if a filename should be excluded from processing."""
    return any(filename.lower().endswith(f".{ext}") for ext in EXCLUDED_EXTENSIONS)


def is_processable_file(filename: str) -> bool:
    """Check if a filename should be processed."""
    return filename.lower().endswith(PROCESSABLE_EXTENSIONS)
