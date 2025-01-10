#!/usr/bin/env python3
"""Script to deduplicate links in text files within a directory."""

import os
import argparse
import sys
from typing import Set, List

def get_text_files(directory: str) -> List[str]:
    """Get all .txt files in the directory."""
    return [f for f in os.listdir(directory) 
            if f.endswith('.txt') and os.path.isfile(os.path.join(directory, f))]

def dedupe_file(file_path: str) -> int:
    """
    Remove duplicate links from a file.
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
            if line and line not in seen:
                seen.add(line)
                unique_lines.append(line)
            elif line:
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
    
    total_duplicates = 0
    processed_files = 0
    
    for filename in text_files:
        file_path = os.path.join(args.directory, filename)
        
        if args.dry_run:
            with open(file_path, 'r') as f:
                # Read all lines at once and calculate duplicates
                lines = [line.strip() for line in f if line.strip()]
                duplicates = len(lines) - len(set(lines))
            if duplicates > 0:
                print(f"{filename}: Would remove {duplicates:,} duplicate(s)")
        else:
            duplicates = dedupe_file(file_path)
            if duplicates > 0:
                print(f"{filename}: Removed {duplicates:,} duplicate(s)")
        
        total_duplicates += duplicates
        processed_files += 1
    
    print(f"\nProcessed {processed_files:,} files")
    print(f"Total duplicates {'found' if args.dry_run else 'removed'}: {total_duplicates:,}")

if __name__ == '__main__':
    main() 