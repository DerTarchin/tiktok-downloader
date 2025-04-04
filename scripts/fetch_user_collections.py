#!/usr/bin/env python3
"""Script to fetch all collections for a TikTok user."""

import argparse
import os
import sys

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from downloader.tiktok_api import fetch_collections, format_video_url, fetch_collection_items
from scripts.count_videos_to_download import process_directory

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Fetch all collections for a TikTok user')
    parser.add_argument('output_dir', help='Directory to save the collection files into')
    parser.add_argument('--delay', type=float, default=0, help='Delay between requests in seconds (default: 0)')
    parser.add_argument('--directory', help='Path to directory.log file to use instead of fetching collections')
    args = parser.parse_args()
    
    # Extract username from the final directory of the output path
    username = os.path.basename(os.path.normpath(args.output_dir))
    
    try:
        # Create output directory if it doesn't exist
        os.makedirs(args.output_dir, exist_ok=True)
        
        if args.directory:
            print(f"\nUsing collections from {args.directory}...")
            collections = fetch_collections(username, delay=args.delay, directory_path=args.directory)
        else:
            print(f"\nFetching collections for user @{username}...")
            # Pass output directory for saving directory.log
            directory_path = os.path.join(args.output_dir, "directory.log")
            collections = fetch_collections(username, delay=args.delay, save_to=directory_path)
        
        if not collections:
            print("No collections found for this user")
            return 1
                    
        # Track total videos while processing collections
        total_videos = 0
        
        # Process each collection
        for collection in collections:
            collection_name = collection['name']
            collection_id = collection['id']
            safe_name = collection_name
            while safe_name.endswith('.'):
                safe_name = safe_name[:-1]
            
            print(f"\nProcessing collection: {collection_name} ({collection_id}) ({collections.index(collection) + 1:,} of {len(collections):,})")
            if collection.get('total'):  # Only print total if available
                print(f"Total expected videos in collection: {collection['total']:,}")
            
            # Use fetch_collection_items from tiktok_api with delay
            video_ids = fetch_collection_items(collection_id, delay=args.delay)
            total_videos += len(video_ids)
            
            # First try with just the collection name
            output_file = os.path.join(args.output_dir, f"{safe_name}.txt")
            
            # If file exists, use name with ID to avoid overwriting
            if os.path.exists(output_file):
                output_file = os.path.join(args.output_dir, f"{safe_name} ({collection_id}).txt")
            
            with open(output_file, 'w') as f:
                for vid_id in video_ids:
                    f.write(format_video_url(vid_id) + '\n')
            print(f"Saved {len(video_ids):,} video URLs to {output_file}")
                
        # Call process_directory instead of count_unique_videos
        process_directory(args.output_dir, collections)
        return 0
            
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 