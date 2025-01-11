#!/usr/bin/env python3
"""Script to count unique videos across text files in a directory."""

import os
import sys
from typing import Set

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from downloader.utils import extract_video_id

def count_unique_videos(directory: str) -> Set[str]:
    """Count unique video IDs across all non-log text files."""
    unique_ids = set()
    
    # Get all .txt files that aren't error logs
    txt_files = [f for f in os.listdir(directory) 
                if f.endswith('.txt') 
                and not f.startswith('[error log]')]
    
    # Sort files for consistent output
    txt_files.sort()
    
    for filename in txt_files:
        file_ids = set()
        filepath = os.path.join(directory, filename)
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    url = line.strip()
                    if url:
                        video_id = extract_video_id(url)
                        if video_id:
                            file_ids.add(video_id)
                            unique_ids.add(video_id)
            print(f"{filename}: {len(file_ids):,} unique videos")
        except Exception as e:
            print(f"Error reading {filename}: {e}", file=sys.stderr)
            continue
    
    return unique_ids

def main():
    if len(sys.argv) != 2:
        print("Usage: python count_unique_videos.py <directory>")
        sys.exit(1)
    
    directory = sys.argv[1]
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)
    
    unique_ids = count_unique_videos(directory)
    print(f"\nTotal unique videos to download: {len(unique_ids):,}")

if __name__ == "__main__":
    main() 