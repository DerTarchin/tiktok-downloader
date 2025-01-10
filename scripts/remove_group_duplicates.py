#!/usr/bin/env python3
"""
Script to remove duplicate links from uncategorized group files if they exist in any regular collection file.
This ensures links only exist in one place - either in regular collections or in uncategorized groups.
"""

import os
import sys

# Get the absolute path of the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the project root to the Python path if it's not already there
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from downloader.utils import remove_duplicates_from_groups

def main():
    if len(sys.argv) < 2:
        print("Usage: python remove_group_duplicates.py <input_directory> [--dry-run]")
        print("\nExample:")
        print("python remove_group_duplicates.py dertarchin")
        print("python remove_group_duplicates.py dertarchin --dry-run")
        sys.exit(1)

    input_dir = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    
    if dry_run:
        print("Dry run mode - no changes will be made")
    
    if not os.path.isdir(input_dir):
        print(f"Error: '{input_dir}' is not a directory.")
        sys.exit(1)
    
    print(f"Looking for files in: {input_dir}")
    
    try:
        # Get all text files that are regular collections (not error logs or uncategorized groups)
        text_files = [f for f in os.listdir(input_dir) 
                     if f.endswith(".txt") 
                     and not f.startswith("[error") 
                     and not f.startswith("All Uncategorized Favorites")
                     and f != "Favorite Videos (URLs).txt"]
        
        if not text_files:
            print("No regular collection files found in the directory.")
            sys.exit(1)
            
        print(f"\nFound {len(text_files)} regular collection files:")
        for file in text_files:
            print(f"- {file}")
            
        total_removed = 0
        for source_file in text_files:
            source_path = os.path.join(input_dir, source_file)
            removed = remove_duplicates_from_groups(source_path, input_dir, dry_run=dry_run)
            total_removed += removed
            
        if total_removed > 0:
            action = "would be" if dry_run else "have been"
            print(f"\nSuccess! {total_removed:,} total links {action} removed from group files.")
        else:
            print("\nNo duplicate links were found in group files.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 