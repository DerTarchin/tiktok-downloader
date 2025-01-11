#!/usr/bin/env python3
"""Script to fetch TikTok collection data using their web API."""

import argparse
import os
import sys

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from downloader.tiktok_api import fetch_collection_items

def main():
    parser = argparse.ArgumentParser(description='Fetch TikTok collection videos using web API')
    parser.add_argument('collection_id', help='ID of the TikTok collection')
    
    args = parser.parse_args()
    
    try:
        video_ids = fetch_collection_items(args.collection_id)
        print(f"Found {len(video_ids)} video IDs")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 