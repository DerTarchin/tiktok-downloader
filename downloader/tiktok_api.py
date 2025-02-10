"""Module for handling TikTok API interactions."""

import requests
import re
import time
import os
from typing import Dict, List, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get environment variables
cookies = os.getenv('COOKIES', '')
if not cookies:
    raise ValueError("COOKIES environment variable not found in .env file")
lastWebId = os.getenv('LAST_WEB_ID', '')
if not lastWebId:
    raise ValueError("LAST_WEB_ID environment variable not found in .env file")


# Common API endpoints
ENDPOINTS = {
    'collection_items': 'https://www.tiktok.com/api/collection/item_list/',
    'collection_list': 'https://www.tiktok.com/api/user/collection_list/',
    'user_detail': 'https://www.tiktok.com/api/user/detail/'
}

# Common headers for all requests
DEFAULT_HEADERS = {
    'authority': 'www.tiktok.com',
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'accept-encoding': 'gzip, deflate, br, zstd',
    'dnt': '1',
    'pragma': 'no-cache',
    'cache-control': 'no-cache',
    'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'cookie': cookies
}

# Common base parameters for all requests
BASE_PARAMS = {
    'WebIdLastTime': lastWebId,
    'aid': '1988',
    'app_language': 'en',
    'app_name': 'tiktok_web',
    'browser_language': 'en-US',
    'browser_name': 'Mozilla',
    'browser_online': 'true',
    'browser_platform': 'MacIntel',
    'browser_version': '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'channel': 'tiktok_web',
    'cookie_enabled': 'true',
    'device_platform': 'web_pc',
    'focus_state': 'true',
    'from_page': 'user',
    'history_len': '2',
    'is_fullscreen': 'false',
    'is_page_visible': 'true',
    'language': 'en',
    'os': 'mac',
    'priority_region': '',
    'referer': '',
    'region': 'US',
    'screen_height': '1329',
    'screen_width': '2056',
    'sourceType': '113',
    'tz_name': 'America/New_York',
    'user_is_login': 'false',
    'webcast_language': 'en'
}

# Add rate limit constants
MAX_RETRIES = 5
INITIAL_BACKOFF = 5  # Initial backoff time in seconds
MAX_BACKOFF = 60    # Maximum backoff time in seconds

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

def get_user_info(username: str, session: Optional[requests.Session] = None) -> Dict:
    """Get user info including secUid."""
    if session is None:
        session = requests.Session()
    
    try:
        # First get the user's page to extract secUid
        response = session.get(
            f'https://www.tiktok.com/@{username}',
            headers=DEFAULT_HEADERS,
            allow_redirects=True
        )
        response.raise_for_status()
        
        # Look for secUid in the page content
        content = response.text
        sec_uid_match = re.search(r'"secUid":"([^"]+)"', content)
        user_id_match = re.search(r'"id":"(\d+)"', content)
        
        if sec_uid_match and user_id_match:
            return {
                'secUid': sec_uid_match.group(1),
                'userId': user_id_match.group(1)
            }
        
        print("Could not find secUid in page content, trying API...")
        
        # If we couldn't find it in the page, try the API
        api_params = {
            **BASE_PARAMS,
            'uniqueId': username,
            'device_id': '7411354210934162987',
            'msToken': response.cookies.get('msToken', '')
        }
        
        api_response = session.get(
            ENDPOINTS['user_detail'],
            headers=DEFAULT_HEADERS,
            params=api_params,
            cookies=response.cookies
        )
        api_response.raise_for_status()
        
        data = api_response.json()
        user = data.get('userInfo', {}).get('user', {})
        
        if user:
            return {
                'secUid': user.get('secUid'),
                'userId': user.get('id')
            }
            
        raise ValueError(f"Could not find user info for @{username}")
        
    except Exception as e:
        print(f"Error fetching user info: {e}")
        if hasattr(e, 'response'):
            print(f"Response content: {e.response.content}")
        raise

def get_collection_list_params(username: str, sec_uid: str, cursor: int = 0) -> Dict:
    """Get parameters for collection list request."""
    return {
        **BASE_PARAMS,
        'WebIdLastTime': '1736604666',
        'device_id': '7458660215698966062',
        'odinId': '7458660231299171374',
        'count': '30',
        'coverFormat': '2',
        'cursor': str(cursor),
        'secUid': sec_uid,
        'needPinnedItemIds': 'true',
        'publicOnly': 'true',
        'post_item_list_request_type': '0'
    }

def get_collection_params(collection_id: str, cursor: str = "0") -> Dict:
    """Get parameters for collection items request."""
    return {
        **BASE_PARAMS,
        'WebIdLastTime': '1736602635',
        'clientABVersions': '70508271,72923695,73038832,73067877,73167671,73184710,73216053,73234258,73240211,73242625,73242628,73242629,73262085,73273316,73289689,70405643,71057832,71200802,72267504,72361743,73171280,73208420',
        'collectionId': collection_id,
        'count': '30',
        'cursor': cursor,
        'data_collection_enabled': 'false',
        'device_id': '7458651491272918570',
        'odinId': '7458651507845121067'
    }

def format_video_url(video_id: str) -> str:
    """Format a video ID into a TikTok URL."""
    return f'https://www.tiktok.com/@/video/{video_id}'

def fetch_collection_items(collection_id: str, session: Optional[requests.Session] = None, cursor: str = "0", existing_count: int = 0, delay: float = 0) -> List[str]:
    """
    Fetch all video IDs from a TikTok collection using their web API.
    
    Args:
        collection_id: ID of the TikTok collection
        session: Optional requests.Session to use for requests
        cursor: Optional cursor to start fetching from
        existing_count: Number of existing items when resuming from a cursor
        delay: Optional delay between requests in seconds (default: 0)
        
    Returns:
        List of video IDs from the collection
    """
    if session is None:
        session = requests.Session()
    
    has_more = True
    video_ids = []
    # Calculate starting page number based on cursor (assuming increments of 30)
    page = (int(cursor) // 30) + 1

    print(f"Fetching collection {collection_id} starting from cursor {cursor}...")
    
    while has_more:
        params = get_collection_params(collection_id, cursor)
        
        try:
            # Add delay if specified
            if delay > 0 and len(video_ids) > 0:  # Don't delay on first request
                import time
                time.sleep(delay)
            
            response = session.get(
                ENDPOINTS['collection_items'],
                params=params,
                headers=DEFAULT_HEADERS
            )
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
                    video_ids.append(video_id)
            
            # Get next cursor before printing progress
            next_cursor = str(data.get("cursor", "0"))
            print(f"Page {page}: {len(items):,} found, total collected: {len(video_ids) + existing_count:,} [next cursor: {next_cursor}]")
            
            # Check if there are more items and update cursor
            has_more = data.get("hasMore", False)
            cursor = next_cursor
            page += 1
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data on page {page}: {e}")
            if hasattr(e, 'response'):
                print(f"Response text: {e.response.text}")
            break
    
    print(f"\nTotal videos found: {len(video_ids) + existing_count:,}")
    return video_ids

def sanitize_filename(name: str) -> str:
    """Sanitize a string to be used as a filename."""
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def save_collections_directory(collections: List[Dict], output_path: str = "directory.log"):
    """Save collections list to a directory file."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for collection in collections:
                f.write(f"[{collection['id']}] {collection['name']}\n")
        print(f"\nSaved {len(collections)} collections to {output_path}")
    except Exception as e:
        print(f"Error saving directory: {e}")

def read_collections_directory(directory_path: str) -> List[Dict]:
    """Read collections from a directory file."""
    collections = []
    try:
        with open(directory_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Parse [id] name format
                if match := re.match(r'\[(\d+)\]\s+(.+)$', line.strip()):
                    collection_id, name = match.groups()
                    collections.append({
                        'id': collection_id,
                        'name': name,
                        'total': 0  # We don't have this info from the file
                    })
        print(f"\nLoaded {len(collections)} collections from {directory_path}")
        return collections
    except Exception as e:
        print(f"Error reading directory: {e}")
        raise

def fetch_collections(username: str, delay: float = 0, directory_path: Optional[str] = None, save_to: Optional[str] = None) -> List[Dict]:
    """
    Fetch all collections for a TikTok user with retry logic.
    
    Args:
        username: TikTok username to fetch collections for
        delay: Optional delay between requests in seconds (default: 0)
        directory_path: Optional path to read collections from instead of fetching
        save_to: Optional path to save directory.log to (default: directory.log in current dir)
        
    Returns:
        List of collection dictionaries containing id and name
    """
    # If directory path is provided, read from it instead of fetching
    if directory_path and os.path.exists(directory_path):
        return read_collections_directory(directory_path)
    
    session = requests.Session()
    
    try:
        # Get user info first
        user_info = get_user_info(username, session)
        if not user_info or not user_info.get('secUid'):
            raise ValueError(f"Could not get secUid for user @{username}")
        collections = []
        cursor = 0
        has_more = True
        page = 1
        retry_count = 0
        current_backoff = INITIAL_BACKOFF
        
        while has_more:
            try:
                # Add delay if specified
                if delay > 0 and cursor > 0:  # Don't delay on first request
                    time.sleep(delay)
                    
                params = get_collection_list_params(username, user_info['secUid'], cursor)
                response = session.get(
                    ENDPOINTS['collection_list'],
                    params=params,
                    headers=DEFAULT_HEADERS
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Check for rate limit or error response
                if data.get('statusCode') == 10101 or response.status_code == 500:
                    if retry_count >= MAX_RETRIES:
                        raise Exception(f"Max retries ({MAX_RETRIES}) exceeded. Last error: {data.get('statusMsg', 'Rate limited')}")
                    
                    print(f"\nRate limited, waiting {current_backoff} seconds before retry {retry_count + 1}/{MAX_RETRIES}...")
                    time.sleep(current_backoff)
                    
                    # Exponential backoff with jitter
                    current_backoff = min(current_backoff * 2 + (time.time() % 1), MAX_BACKOFF)
                    retry_count += 1
                    continue
                
                # Reset retry count and backoff on successful request
                retry_count = 0
                current_backoff = INITIAL_BACKOFF
                
                items = data.get('collectionList', [])
                
                for item in items:
                    collection = {
                        'id': item.get('collectionId'),
                        'name': sanitize_filename(item.get('name', '')),
                        'total': int(item.get('total', '0'))
                    }
                    if collection['id'] and collection['name']:
                        collections.append(collection)
                
                print(f"Page {page}: {len(items)} collections found, total collected: {len(collections):,}")
                
                has_more = data.get('hasMore', False)
                cursor = int(data.get('cursor', '0'))  # Convert cursor to int
                page += 1
                
            except requests.exceptions.RequestException as e:
                if retry_count >= MAX_RETRIES:
                    print(f"\nFailed after {MAX_RETRIES} retries")
                    raise
                
                print(f"\nRequest error, waiting {current_backoff} seconds before retry {retry_count + 1}/{MAX_RETRIES}...")
                if hasattr(e, 'response'):
                    print(f"Response content: {e.response.content}")
                
                time.sleep(current_backoff)
                current_backoff = min(current_backoff * 2 + (time.time() % 1), MAX_BACKOFF)
                retry_count += 1
                continue
        
        # Save collections to directory file after successful fetch
        if save_to:
            save_collections_directory(collections, save_to)
        else:
            save_collections_directory(collections)  # Use default path
        return collections
        
    except Exception as e:
        print(f"Error fetching collections: {e}")
        if hasattr(e, 'response'):
            print(f"Response content: {e.response.content}")
        raise 