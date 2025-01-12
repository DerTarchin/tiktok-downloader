"""Module for handling TikTok API interactions."""

import requests
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

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
    'cookie': 'tt_csrf_token=oLYm7iAm-Sk-5Mqh9QPmlZmALT5f8BtUvgN8; ttwid=1%7CY0bPNKnk7H5_h1_Ae14weHqb9UUlsvx5tUzhMv5MRZM%7C1736602635%7Ca3401329d4e1544ba012dcc84f6d7b28936e94d8a86284fc875d1107894825b3; tt_chain_token=RV+6Ty1aLXvN+Yep6o+0Bw=='
}

# Common base parameters for all requests
BASE_PARAMS = {
    'WebIdLastTime': '1736602635',
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

def fetch_collection_items(collection_id: str, session: Optional[requests.Session] = None) -> List[str]:
    """
    Fetch all video IDs from a TikTok collection using their web API.
    
    Args:
        collection_id: ID of the TikTok collection
        session: Optional requests.Session to use for requests
        
    Returns:
        List of video IDs from the collection
    """
    if session is None:
        session = requests.Session()
    
    cursor = "0"
    has_more = True
    video_ids = []
    page = 1

    print(f"Fetching collection {collection_id}...")
    
    while has_more:
        params = get_collection_params(collection_id, cursor)
        
        try:
            # print(f"Fetching page {page} with cursor {cursor}...")
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
            
            print(f"Page {page}: {len(items):,} found, total collected: {len(video_ids):,} [next cursor: {cursor}]")
            
            # Check if there are more items
            has_more = data.get("hasMore", False)
            cursor = str(data.get("cursor", "0"))
            page += 1
            
            # Add a small delay to avoid rate limiting
            # import time
            # time.sleep(1)
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data on page {page}: {e}")
            if hasattr(e, 'response'):
                print(f"Response text: {e.response.text}")
            break
    
    print(f"\nTotal videos found: {len(video_ids):,}")
    return video_ids

def fetch_collections(username: str) -> List[Dict]:
    """Fetch all collections for a user."""
    # Create a session to maintain cookies
    session = requests.Session()
    
    # First get user's secUid
    user_info = get_user_info(username, session)
    if not user_info.get('secUid'):
        raise ValueError(f"Could not find user with username: {username}")
        
    collections = []
    cursor = 0
    has_more = True
    
    while has_more:
        params = get_collection_list_params(username, user_info['secUid'], cursor)
        
        try:
            response = session.get(
                ENDPOINTS['collection_list'],
                headers=DEFAULT_HEADERS,
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            items = data.get('collectionList', [])
            if not items:
                break
                
            for item in items:
                collection = {
                    'id': item.get('collectionId'),
                    'name': item.get('name'),
                    'total': item.get('total')
                }
                collections.append(collection)
            
            cursor = data.get('cursor', 0)
            has_more = data.get('hasMore', False)
            
            print(f"Found {len(items):,} collections")
                
        except Exception as e:
            print(f"Error fetching collections: {e}")
            if hasattr(e, 'response'):
                print(f"Response content: {e.response.content}")
            break
            
    return collections 