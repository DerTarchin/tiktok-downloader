#!/usr/bin/env python3
"""Script to count unique videos across text files in a directory."""

import os
import sys
from typing import Set

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from downloader.utils import extract_video_id

def count_unique_videos(directory: str) -> tuple[Set[str], list[str]]:
    """Count unique video IDs across all non-log text files."""
    unique_ids = set()

    print(f"Counting unique videos in {directory}...\n")
    
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
            print(f"{filename.replace('.txt', '')}: {len(file_ids):,}")
        except Exception as e:
            print(f"Error reading {filename}: {e}", file=sys.stderr)
            continue
    
    return unique_ids, txt_files

def main():
    if len(sys.argv) != 2:
        print("Usage: python count_unique_videos.py <directory>")
        sys.exit(1)
    
    directory = sys.argv[1]
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)
    
    unique_ids, txt_files = count_unique_videos(directory)
    print(f"\nTotal unique videos to download: {len(unique_ids):,}")
    # Count total collections (excluding uncategorized)
    regular_collections = sum(1 for f in txt_files if not f.startswith('uncategorized'))
    
    # Add 1 if there's an uncategorized collection
    has_uncategorized = any(f.startswith('uncategorized') for f in txt_files)
    total_collections = regular_collections + (1 if has_uncategorized else 0)
    
    print(f"Total collections: {total_collections:,}")

if __name__ == "__main__":
    main() 