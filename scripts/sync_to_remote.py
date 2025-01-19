#!/usr/bin/env python3
"""Script to sync current directory to remote using the same logic as the main script's final sync."""

import os
import sys
import argparse

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from downloader.sync_handler import SyncHandler

def main():
    parser = argparse.ArgumentParser(description='Sync directory to remote Google Drive using sync_handler\'s final sync logic.')
    parser.add_argument('path', help='Path to sync')
    parser.add_argument('--gdrive-base', default="gdrive:/TikTok Archives",
                       help='Base Google Drive path (defaults to "gdrive:/TikTok Archives")')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be synced without actually syncing')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.path):
        print(f"Error: {args.path} is not a valid directory")
        sys.exit(1)
    
    # Initialize sync handler
    sync_handler = SyncHandler()
    if args.dry_run:
        sync_handler.rclone_modifiers.append("--dry-run")
    
    # Set custom gdrive base path if provided
    if args.gdrive_base != "gdrive:/TikTok Archives":
        sync_handler.gdrive_base_path = args.gdrive_base
    
    # Run final sync
    print(f"\n>> {'[DRY RUN] ' if args.dry_run else ''}Performing final sync...")
    sync_handler.sync_remaining_files(args.path)

if __name__ == "__main__":
    main() 