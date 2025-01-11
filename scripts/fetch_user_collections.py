#!/usr/bin/env python3
"""Script to fetch all collections for a TikTok user."""

import argparse
import os
import sys

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from downloader.tiktok_api import fetch_collections, format_video_url, fetch_collection_items

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Fetch all collections for a TikTok user')
    parser.add_argument('username', help='TikTok username to fetch collections from')
    parser.add_argument('output_dir', help='Directory to save the collection files into')
    args = parser.parse_args()
    
    try:
        print(f"\nFetching collections for user @{args.username}...")
        collections = fetch_collections(args.username)
        
        if not collections:
            print("No collections found for this user")
            return 1
                    
        # Create output directory if it doesn't exist
        os.makedirs(args.output_dir, exist_ok=True)
        
        # Process each collection
        for collection in collections:
            collection_name = collection['name']
            collection_id = collection['id']
            safe_name = collection_name
            
            print(f"\nProcessing collection: {collection_name} ({collection_id})")
            
            # Use fetch_collection_items from tiktok_api
            video_ids = fetch_collection_items(collection_id)
            
            if video_ids:
                output_file = os.path.join(args.output_dir, f"{safe_name}.txt")
                with open(output_file, 'w') as f:
                    for vid_id in video_ids:
                        f.write(format_video_url(vid_id) + '\n')
                print(f"Saved {len(video_ids):,} video URLs to {output_file}")
            else:
                print("No videos found in this collection")
                
        # Print summary
        total_videos = sum(len(fetch_collection_items(c['id'])) for c in collections)
        print(f"\nSummary:")
        print(f"Total collections: {len(collections):,}")
        print(f"Total videos: {total_videos:,}")
        return 0
            
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 