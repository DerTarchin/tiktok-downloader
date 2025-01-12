#!/usr/bin/env python3
"""Script to deduplicate links in text files within a directory."""

import os
import argparse
import sys
from typing import Set, List, Dict
from downloader.utils import extract_video_id

def get_text_files(directory: str) -> List[str]:
    """Get all .txt files in the directory."""
    return [f for f in os.listdir(directory) 
            if f.endswith('.txt') and os.path.isfile(os.path.join(directory, f))]

def dedupe_file(file_path: str, collection_video_ids: Set[str] = None) -> int:
    """
    Remove duplicate links from a file.
    If collection_video_ids is provided, also remove any videos that appear in those IDs.
    Returns the number of duplicates removed.
    """
    try:
        with open(file_path, 'r') as f:
            # Read all lines and strip whitespace
            lines = [line.strip() for line in f.readlines()]
            
        # Get unique lines while preserving order
        seen: Set[str] = set()
        unique_lines = []
        duplicates = 0
        
        for line in lines:
            if not line:
                continue
                
            video_id = extract_video_id(line)
            
            # For uncategorized files, check against collection videos
            if collection_video_ids is not None and video_id in collection_video_ids:
                duplicates += 1
                continue
            
            # For all files, remove duplicates within the same file
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)
            else:
                duplicates += 1
        
        # Only write back if we found duplicates
        if duplicates > 0:
            with open(file_path, 'w') as f:
                f.write('\n'.join(unique_lines))
                if unique_lines:  # Add final newline if file is not empty
                    f.write('\n')
                    
        return duplicates
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}", file=sys.stderr)
        return 0

def main():
    parser = argparse.ArgumentParser(description='Deduplicate links in text files.')
    parser.add_argument('directory', help='Directory containing text files to deduplicate')
    parser.add_argument('--dry-run', action='store_true', 
                        help='Show what would be done without making changes')
    args = parser.parse_args()
    
    if not os.path.isdir(args.directory):
        print(f"Error: {args.directory} is not a directory", file=sys.stderr)
        sys.exit(1)
    
    text_files = get_text_files(args.directory)
    if not text_files:
        print("No text files found in directory.")
        return
    
    # Sort files to process collections first, then uncategorized files
    def is_uncategorized(filename: str) -> bool:
        return filename.startswith("all_saves") or filename.startswith("All Saves")
    
    text_files.sort(key=lambda x: (is_uncategorized(x), x.lower()))
    
    # First pass: collect video IDs from regular collections
    collection_video_ids: Set[str] = set()
    for filename in text_files:
        if not is_uncategorized(filename):
            file_path = os.path.join(args.directory, filename)
            try:
                with open(file_path, 'r') as f:
                    for line in f:
                        if line.strip():
                            video_id = extract_video_id(line.strip())
                            if video_id:
                                collection_video_ids.add(video_id)
            except Exception as e:
                print(f"Error reading {file_path}: {str(e)}", file=sys.stderr)
                continue
    
    # Second pass: process all files
    total_duplicates = 0
    processed_files = 0
    
    for filename in text_files:
        file_path = os.path.join(args.directory, filename)
        is_uncategorized_file = is_uncategorized(filename)
        
        if args.dry_run:
            with open(file_path, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
                # For uncategorized files, count videos that appear in collections
                if is_uncategorized_file:
                    duplicates = sum(1 for line in lines 
                                   if extract_video_id(line) in collection_video_ids)
                    # Add internal duplicates
                    seen = set()
                    duplicates += sum(1 for line in lines 
                                    if line in seen or seen.add(line))
                else:
                    # For collections, only count internal duplicates
                    seen = set()
                    duplicates = sum(1 for line in lines 
                                   if line in seen or seen.add(line))
                
            if duplicates > 0:
                print(f"{filename}: Would remove {duplicates:,} duplicate(s)")
        else:
            # Pass collection_video_ids only for uncategorized files
            duplicates = dedupe_file(file_path, 
                                   collection_video_ids if is_uncategorized_file else None)
            if duplicates > 0:
                print(f"{filename}: Removed {duplicates:,} duplicate(s)")
        
        total_duplicates += duplicates
        processed_files += 1
    
    print(f"\nProcessed {processed_files:,} files")
    print(f"Total duplicates {'found' if args.dry_run else 'removed'}: {total_duplicates:,}")

if __name__ == '__main__':
    main() 