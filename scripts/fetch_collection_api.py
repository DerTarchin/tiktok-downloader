#!/usr/bin/env python3
"""Script to fetch TikTok collection data using their web API."""

import argparse
import json
import re
import requests
import sys
import time
from typing import List, Optional
from urllib.parse import urlparse, parse_qs

def extract_collection_id(url: str) -> Optional[str]:
    """Extract collection ID from TikTok collection URL."""
    # Try direct regex match first
    match = re.search(r'collection/[^-]+-(\d+)', url)
    if match:
        return match.group(1)
    
    # If no match, try parsing URL and query params
    parsed = urlparse(url)
    path_parts = parsed.path.split('/')
    
    # Look for the collection ID in the path
    for part in path_parts:
        if part.isdigit() and len(part) > 10:  # TikTok collection IDs are long numbers
            return part
    
    return None

def get_api_params(collection_id: str, cursor: str = "0") -> dict:
    """Generate API parameters for the request."""
    return {
        "WebIdLastTime": "1736602635",
        "aid": "1988",
        "app_language": "en",
        "app_name": "tiktok_web",
        "browser_language": "en-US",
        "browser_name": "Mozilla",
        "browser_online": "true",
        "browser_platform": "MacIntel",
        "browser_version": "5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "channel": "tiktok_web",
        "clientABVersions": "70508271,72923695,73038832,73067877,73167671,73184710,73216053,73234258,73240211,73242625,73242628,73242629,73262085,73273316,73289689,70405643,71057832,71200802,72267504,72361743,73171280,73208420",
        "collectionId": collection_id,
        "cookie_enabled": "true",
        "count": "30",
        "cursor": cursor,
        "data_collection_enabled": "false",
        "device_id": "7458651491272918570",
        "device_platform": "web_pc",
        "focus_state": "true",
        "from_page": "user",
        "history_len": "2",
        "is_fullscreen": "false",
        "is_page_visible": "true",
        "language": "en",
        "odinId": "7458651507845121067",
        "os": "mac",
        "priority_region": "",
        "referer": "",
        "region": "US",
        "screen_height": "1329",
        "screen_width": "2056",
        "sourceType": "113",
        "tz_name": "America/New_York",
        "user_is_login": "false",
        "webcast_language": "en"
    }

def get_headers() -> dict:
    """Generate headers for the request."""
    return {
        "authority": "www.tiktok.com",
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "cookie": "tt_csrf_token=oLYm7iAm-Sk-5Mqh9QPmlZmALT5f8BtUvgN8; ttwid=1%7CY0bPNKnk7H5_h1_Ae14weHqb9UUlsvx5tUzhMv5MRZM%7C1736602635%7Ca3401329d4e1544ba012dcc84f6d7b28936e94d8a86284fc875d1107894825b3; tt_chain_token=RV+6Ty1aLXvN+Yep6o+0Bw==",
        "dnt": "1",
        "pragma": "no-cache",
        "referer": "https://www.tiktok.com",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }

def fetch_collection_items(collection_url: str, output_file: str = None) -> List[str]:
    """
    Fetch all items from a TikTok collection using their web API.
    
    Args:
        collection_url: URL of the TikTok collection
        output_file: Optional file to save the video URLs to
        
    Returns:
        List of video URLs from the collection
    """
    collection_id = extract_collection_id(collection_url)
    if not collection_id:
        raise ValueError(f"Could not extract collection ID from URL: {collection_url}")
    
    print(f"Fetching collection ID: {collection_id}")
    
    base_url = "https://www.tiktok.com/api/collection/item_list/"
    cursor = "0"
    has_more = True
    video_urls = []
    page = 1
    
    while has_more:
        params = get_api_params(collection_id, cursor)
        headers = get_headers()
        
        try:
            print(f"\nFetching page {page}...")
            response = requests.get(base_url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Extract items from response
            items = data.get("itemList", [])
            if not items:
                print("No more items found")
                break
            
            # Process items
            for item in items:
                video_id = item.get("video", {}).get("id")
                if video_id:
                    video_url = f"https://www.tiktok.com/video/{video_id}"
                    video_urls.append(video_url)
                    print(f"Found video: {video_url}")
            
            # Check if there are more items
            has_more = data.get("hasMore", False)
            cursor = str(data.get("cursor", "0"))
            page += 1
            
            # Add a small delay to avoid rate limiting
            time.sleep(1)
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response text: {e.response.text}")
            break
    
    print(f"\nTotal videos found: {len(video_urls)}")
    
    # Save to file if specified
    if output_file:
        with open(output_file, 'w') as f:
            for url in video_urls:
                f.write(f"{url}\n")
        print(f"Saved URLs to: {output_file}")
    
    return video_urls

def main():
    parser = argparse.ArgumentParser(description='Fetch TikTok collection videos using web API')
    parser.add_argument('collection_url', help='URL of the TikTok collection')
    parser.add_argument('-o', '--output', help='Output file to save URLs to')
    
    args = parser.parse_args()
    
    try:
        fetch_collection_items(args.collection_url, args.output)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 