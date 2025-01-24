#!/usr/bin/env python3
"""Script to count the total number of videos to be downloaded across text files in a directory."""

import os
import re
import sys
from typing import Set

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from downloader.utils import extract_video_id

def count_unique_videos(directory: str, collections=None) -> tuple[Set[str], list[str], dict[str, int]]:
    """Count unique video IDs across all non-log text files."""
    should_not_duplicate_ids = set()
    existing_collection_totals = {}
    expected_collection_totals = {} # with id as key and total collections as value

    print(f"Counting unique videos in {directory}...\n")
    
    # Get all .txt files that aren't error logs
    txt_files = [f for f in os.listdir(directory) 
                if f.endswith('.txt') 
                and not f.startswith('[error log]')]
    
    # Sort files for consistent output
    txt_files.sort(key=lambda f: [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', f)])
    
    # Build a map of collection names to their expected totals
    if collections:
        existing_collection_totals = {
            collection['name']: collection['total']
            for collection in collections
        }
        # Handle potential duplicate collection names with IDs
        for collection in collections:
            alt_name = f"{collection['name']}_{collection['id']}"
            existing_collection_totals[alt_name] = collection['total']
    
    for filename in txt_files:
        collection_name = filename.replace('.txt', '')

        if collection_name == 'Favorite Videos (URLs)':
            continue

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
            
            # Get collection name without .txt extension
            actual_count = len(file_ids)
            expected_count = existing_collection_totals.get(collection_name, actual_count)
            
            # Calculate private videos
            private_count = expected_count - actual_count if expected_count > actual_count else 0
            
            # Print count with private videos if any
            if private_count > 0:
                print(f"{collection_name}: {actual_count:,} (+{private_count:,} unavailable video{'s' if private_count != 1 else ''})")
            else:
                print(f"{collection_name}: {actual_count:,}")
            
            # Update unique_ids and collection ids based on collection type
            if collection_name.startswith('uncategorized'):
                should_not_duplicate_ids.update(file_ids)
            else:
                # Increment count for each video ID
                for vid_id in file_ids:
                    if vid_id in expected_collection_totals:
                        expected_collection_totals[vid_id] += 1
                    else:
                        expected_collection_totals[vid_id] = 1
                
        except Exception as e:
            print(f"Error reading {filename}: {e}", file=sys.stderr)
            continue
    
    # Add uncategorized videos to expected totals if not already present
    for vid_id in should_not_duplicate_ids:
        if vid_id not in expected_collection_totals:
            expected_collection_totals[vid_id] = 1

    total_videos_to_download = sum(expected_collection_totals.values())  
    
    return total_videos_to_download, txt_files, existing_collection_totals

def process_directory(directory: str, collections=None) -> tuple[Set[str], int]:
    """Process the directory to count unique video IDs and collections."""
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)
    
    total_videos_to_download, txt_files, _ = count_unique_videos(directory, collections)
    print(f"\nTotal videos expected to download: {total_videos_to_download:,}")
    
    # Count total collections (excluding uncategorized)
    regular_collections = sum(1 for f in txt_files if not f.startswith('uncategorized'))
    
    print(f"Total user collections: {regular_collections:,}")
    
    return total_videos_to_download, regular_collections

def main():
    if len(sys.argv) != 2:
        print("Usage: python count_videos_to_download.py <directory>")
        sys.exit(1)
    
    directory = sys.argv[1]
    process_directory(directory)

if __name__ == "__main__":
    main() 