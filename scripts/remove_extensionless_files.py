#!/usr/bin/env python3
"""Script to find and delete files without extensions in remote TikTok Archives."""

import argparse
import subprocess
import sys
from typing import List, Tuple

def list_files_without_extension(username: str) -> List[Tuple[str, str]]:
    """
    Find all files without extensions in the remote directory.
    Returns a list of tuples (full_path, filename).
    """
        
    remote_base = f"gdrive:/TikTok Archives/{username}"
    print(f"Searching for files without extensions in: {remote_base}")
    
    try:
        # Use rclone to recursively list all files
        cmd = ["rclone", "lsf", "--recursive", "--format", "p", remote_base]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        files_without_ext = []
        for line in result.stdout.splitlines():
            # Skip empty lines
            if not line.strip():
                continue
                
            # Get the full filename from the path
            filename = line.strip().split('/')[-1]
            
            # Check if file has no extension (no dot in filename)
            # Also check it's not a directory (which ends with / in rclone lsf output)
            if '.' not in filename and not line.endswith('/'):
                files_without_ext.append((line.strip(), filename))
        
        return files_without_ext
        
    except subprocess.CalledProcessError as e:
        print(f"Error running rclone: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

def delete_file(full_path: str, username: str) -> bool:
    """Delete a file from the remote using rclone."""
    try:
        # Construct the full rclone path with username included
        rclone_path = f"gdrive:/TikTok Archives/{username}/{full_path}"
        cmd = ["rclone", "deletefile", rclone_path]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error deleting {full_path}: {e.stderr}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description='Find and delete files without extensions in TikTok Archives')
    parser.add_argument('username', help='Username whose archives to search')
    parser.add_argument('--dry-run', action='store_true', help='Only list files, do not delete')
    args = parser.parse_args()

    username = args.username
    # Extract username if a full path is provided
    if '/' in username:
        username = username.rstrip('/').split('/')[-1]
    
    print(f"Searching for files without extensions in archives for user: {username}")
    files = list_files_without_extension(username)
    
    if not files:
        print("No files without extensions found.")
        return
    
    print(f"\nFound {len(files)} files without extensions:")
    for full_path, filename in files:
        print(f"\t{full_path}")
    
    if args.dry_run:
        print("\nDry run - no files were deleted.")
        return
        
    print("\nProceeding with deletion...")
    deleted_count = 0
    for full_path, _ in files:
        if delete_file(full_path, username):
            print(f"Deleted: {full_path}")
            deleted_count += 1
        
    print(f"\nOperation complete. Deleted {deleted_count:,} of {len(files):,} files.")

if __name__ == '__main__':
    main() 