#!/usr/bin/env python3
"""Script to fetch TikTok collection data using their web API."""

import argparse
import os
import sys

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from downloader.tiktok_api import fetch_collection_items, format_video_url

def main():
    parser = argparse.ArgumentParser(description='Fetch TikTok collection videos using web API')
    parser.add_argument('collection_id', help='ID of the TikTok collection')
    parser.add_argument('--output-file', '-o', help='Output file to write URLs to. If not specified, will use collection_[ID].txt')
    parser.add_argument('--cursor', help='Cursor to start fetching from', default="0")
    parser.add_argument('--delay', '-d', type=float, default=0, help='Delay between requests in seconds (default: 0)')
    
    args = parser.parse_args()
    
    try:
        # Determine output file path
        output_file = args.output_file or os.path.join(os.getcwd(), f'collection_{args.collection_id}.txt')
        
        # Read existing URLs if file exists
        existing_urls = set()
        if os.path.exists(output_file):
            print(f"Reading existing URLs from {output_file}")
            with open(output_file, 'r') as f:
                existing_urls = {url.strip() for url in f if url.strip()}
            print(f"Found {len(existing_urls):,} existing URLs")
        
        # Fetch new video IDs starting from cursor
        video_ids = fetch_collection_items(
            args.collection_id, 
            cursor=args.cursor, 
            existing_count=len(existing_urls),
            delay=args.delay
        )
        
        if not video_ids:
            print("No new videos found")
            return 0
            
        print(f"Found {len(video_ids):,} new video IDs")
        
        # Convert to URLs while preserving order
        new_urls = [format_video_url(video_id) for video_id in video_ids]
        
        # Always check for duplicates to avoid writing existing URLs
        existing_set = existing_urls
        urls_to_write = [url for url in new_urls if url not in existing_set]
        
        if urls_to_write:
            print(f"Adding {len(urls_to_write):,} {'new ' if args.cursor != '0' else ''}unique URLs")
            # Append new URLs to file
            mode = 'a' if existing_urls else 'w'
            with open(output_file, mode) as f:
                for url in urls_to_write:
                    f.write(url + '\n')
            print(f"URLs saved to {output_file}")
            print(f"Total URLs in file: {len(existing_urls) + len(urls_to_write):,}")
        else:
            print("No new unique URLs found")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 