#!/usr/bin/env python3
"""Script to count unique videos across text files in a directory."""

import os
import sys
from typing import Set

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from downloader.utils import extract_video_id

def count_unique_videos(directory: str, collections=None) -> tuple[Set[str], list[str], dict[str, int]]:
    """Count unique video IDs across all non-log text files."""
    unique_ids = set()
    collection_totals = {}

    print(f"Counting unique videos in {directory}...\n")
    
    # Get all .txt files that aren't error logs
    txt_files = [f for f in os.listdir(directory) 
                if f.endswith('.txt') 
                and not f.startswith('[error log]')]
    
    # Sort files for consistent output
    txt_files.sort()
    
    # Build a map of collection names to their expected totals
    if collections:
        collection_totals = {
            collection['name']: collection['total']
            for collection in collections
        }
        # Handle potential duplicate collection names with IDs
        for collection in collections:
            alt_name = f"{collection['name']}_{collection['id']}"
            collection_totals[alt_name] = collection['total']
    
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
            
            # Get collection name without .txt extension
            collection_name = filename.replace('.txt', '')
            actual_count = len(file_ids)
            expected_count = collection_totals.get(collection_name, actual_count)
            
            # Calculate private videos
            private_count = expected_count - actual_count if expected_count > actual_count else 0
            
            # Print count with private videos if any
            if private_count > 0:
                print(f"{collection_name}: {actual_count:,} (+ {private_count:,} private video{'s' if private_count != 1 else ''})")
            else:
                print(f"{collection_name}: {actual_count:,}")
                
        except Exception as e:
            print(f"Error reading {filename}: {e}", file=sys.stderr)
            continue
    
    return unique_ids, txt_files, collection_totals

def process_directory(directory: str, collections=None) -> tuple[Set[str], int]:
    """Process the directory to count unique video IDs and collections."""
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)
    
    unique_ids, txt_files, _ = count_unique_videos(directory, collections)
    print(f"\nTotal unique videos to download: {len(unique_ids):,}")
    
    # Count total collections (excluding uncategorized)
    regular_collections = sum(1 for f in txt_files if not f.startswith('uncategorized'))
    
    # Add 1 if there's an uncategorized collection
    has_uncategorized = any(f.startswith('uncategorized') for f in txt_files)
    total_collections = regular_collections + (1 if has_uncategorized else 0)
    
    print(f"Total collections: {total_collections:,}")
    
    return unique_ids, total_collections

def main():
    if len(sys.argv) != 2:
        print("Usage: python count_unique_videos.py <directory>")
        sys.exit(1)
    
    directory = sys.argv[1]
    process_directory(directory)

if __name__ == "__main__":
    main() 