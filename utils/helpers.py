"""Utility helper functions"""

import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

def generate_secret_key() -> str:
    """Generate a secure secret key"""
    return secrets.token_hex(32)

def clean_filename(filename: str) -> str:
    """Clean filename for safe filesystem usage"""
    # Remove or replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:190] + ext
    
    return filename.strip()

def ensure_directory(path: str) -> str:
    """Ensure directory exists and return the path"""
    Path(path).mkdir(parents=True, exist_ok=True)
    return path

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

def normalize_title_for_matching(title: str) -> str:
    """Normalize title for matching purposes"""
    import re
    if not title:
        return ''
    
    # Convert to lowercase
    normalized = title.lower()
    
    # Remove special characters and extra whitespace
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized
