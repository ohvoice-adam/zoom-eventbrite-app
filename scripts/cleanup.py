#!/usr/bin/env python3
"""Cleanup script for old files and database records"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def cleanup_old_files(download_folder, days=7):
    """Clean up old downloaded files"""
    download_path = Path(download_folder)
    
    if not download_path.exists():
        return 0
    
    cutoff_date = datetime.now() - timedelta(days=days)
    cleaned_count = 0
    
    for file_path in download_path.glob('*.mp4'):
        if file_path.stat().st_mtime < cutoff_date.timestamp():
            try:
                file_path.unlink()
                cleaned_count += 1
                print(f"Deleted: {file_path.name}")
            except Exception as e:
                print(f"Error deleting {file_path.name}: {e}")
    
    return cleaned_count

def main():
    """Run cleanup tasks"""
    # Simple cleanup without database dependencies for now
    print("Starting cleanup...")
    
    download_folder = os.environ.get('DOWNLOAD_FOLDER', './downloads')
    files_cleaned = cleanup_old_files(download_folder)
    print(f"Cleaned up {files_cleaned} old video files")
    
    print("Cleanup complete!")

if __name__ == '__main__':
    main()
