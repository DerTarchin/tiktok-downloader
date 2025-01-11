import requests
import re
import json
from typing import List, Optional, Dict
from urllib.parse import urlparse, parse_qs
import os
from fetch_collection_api import fetch_collection_items
import argparse
import sys

def get_default_headers():
    """Get default headers for TikTok API requests."""
    return {
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
        'cookie': 'tt_csrf_token=AnMM1FNw-NWuuVSCNMn33crRmGiykBEB1q9Y; tiktok_webapp_theme=dark'
    }

def get_user_info(username: str) -> Dict:
    """Get user info including secUid."""
    headers = {
        'authority': 'www.tiktok.com',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'dnt': '1',
        'pragma': 'no-cache',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'cookie': 'tiktok_webapp_theme=dark; tt_csrf_token=AnMM1FNw-NWuuVSCNMn33crRmGiykBEB1q9Y; ttwid=1%7CE3U00nOnYoyY3hjztFNnX2h09uuwhDvc-Lqfx4tuzk4%7C1725590380%7Cf62ad4d2783460974e20aceb7aae8879511907034effbd7342dd37259a86bfab; tt_chain_token=SQyuTXOfr81sSY4wLi8ntA=='
    }
    
    try:
        print(f"\nFetching user info for @{username}...")
        
        # First get the user's page to extract secUid
        response = requests.get(
            f'https://www.tiktok.com/@{username}',
            headers=headers,
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
        else:
            print("Could not find secUid in page content, trying API...")
            
            # If we couldn't find it in the page, try the API
            api_params = {
                'aid': '1988',
                'app_language': 'en',
                'app_name': 'tiktok_web',
                'device_platform': 'web_pc',
                'uniqueId': username,
                'device_id': '7411354210934162987',
                'channel': 'tiktok_web',
                'msToken': response.cookies.get('msToken', '')
            }
            
            api_response = requests.get(
                'https://www.tiktok.com/api/user/detail/',
                headers=headers,
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
            
        print("Could not find user info")
        return {}
        
    except Exception as e:
        print(f"Error fetching user info: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response headers: {dict(e.response.headers)}")
            print(f"Response content: {e.response.content}")
        return {}

def get_collection_list_params(username: str, sec_uid: str, cursor: int = 0):
    """Get parameters for collection list request."""
    return {
        'WebIdLastTime': '0',
        'aid': '1988',
        'appId': '1988',
        'app_language': 'en',
        'app_name': 'tiktok_web',
        'browser_language': 'en-US',
        'browser_name': 'Mozilla',
        'browser_online': 'true',
        'browser_platform': 'MacIntel',
        'browser_version': '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'channel': 'tiktok_web',
        'cookie_enabled': 'true',
        'count': '30',
        'coverFormat': '2',
        'cursor': str(cursor),
        'data_collection_enabled': 'true',
        'device_platform': 'web_pc',
        'focus_state': 'true',
        'from_page': 'user',
        'history_len': '1',
        'is_fullscreen': 'false',
        'is_page_visible': 'true',
        'language': 'en',
        'os': 'mac',
        'priority_region': 'US',
        'region': 'US',
        'screen_height': '1329',
        'screen_width': '2056',
        'secUid': sec_uid,
        'tz_name': 'America/New_York',
        'webcast_language': 'en'
    }

def get_collection_params(collection_id: str, cursor: int = 0):
    """Get parameters for collection items request."""
    return {
        'WebIdLastTime': '1736602635',
        'aid': '1988',
        'appId': '1988',
        'app_language': 'en',
        'app_name': 'tiktok_web',
        'browser_language': 'en-US',
        'browser_name': 'Mozilla',
        'browser_online': 'true',
        'browser_platform': 'MacIntel',
        'browser_version': '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'channel': 'tiktok_web',
        'collectionId': collection_id,
        'cookie_enabled': 'true',
        'count': '30',
        'cursor': str(cursor),
        'data_collection_enabled': 'true',
        'device_platform': 'web_pc',
        'focus_state': 'true',
        'from_page': 'user',
        'history_len': '1',
        'is_fullscreen': 'false',
        'is_page_visible': 'true',
        'language': 'en',
        'os': 'mac',
        'priority_region': 'US',
        'region': 'US',
        'screen_height': '1329',
        'screen_width': '2056',
        'tz_name': 'America/New_York',
        'webcast_language': 'en'
    }

def fetch_collections(username: str) -> List[Dict]:
    """Fetch all collections for a user."""
    # First get user's secUid
    user_info = get_user_info(username)
    if not user_info.get('secUid'):
        raise ValueError(f"Could not find user with username: {username}")
        
    collections = []
    cursor = 0
    has_more = True
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    # Headers from incognito browser that worked
    headers = {
        'authority': 'www.tiktok.com',
        'accept': '*/*',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'dnt': '1',
        'pragma': 'no-cache',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }
    
    while has_more:
        # Parameters that worked from incognito browser
        params = {
            'WebIdLastTime': '1736604666',
            'aid': '1988',
            'appId': '1988',
            'app_language': 'en',
            'app_name': 'tiktok_web',
            'browser_language': 'en-US',
            'browser_name': 'Mozilla',
            'browser_online': 'true',
            'browser_platform': 'MacIntel',
            'browser_version': '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'channel': 'tiktok_web',
            'cookie_enabled': 'true',
            'count': '30',
            'coverFormat': '2',
            'cursor': str(cursor),
            'data_collection_enabled': 'false',
            'device_id': '7458660215698966062',
            'device_platform': 'web_pc',
            'focus_state': 'true',
            'from_page': 'user',
            'history_len': '2',
            'is_fullscreen': 'false',
            'is_page_visible': 'true',
            'language': 'en',
            'needPinnedItemIds': 'true',
            'odinId': '7458660231299171374',
            'os': 'mac',
            'post_item_list_request_type': '0',
            'priority_region': '',
            'publicOnly': 'true',
            'referer': '',
            'region': 'US',
            'screen_height': '1329',
            'screen_width': '2056',
            'secUid': user_info['secUid'],
            'tz_name': 'America/New_York',
            'user_is_login': 'false',
            'webcast_language': 'en'
        }
        
        try:
            response = session.get(
                'https://www.tiktok.com/api/user/collection_list/',
                headers=headers,
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
            
            print(f"Found {len(items):,} collections on this page")
            print(f"Next cursor: {cursor:,}")
            print(f"Has more: {has_more}")
                
        except Exception as e:
            print(f"Error fetching collections: {e}")
            if hasattr(e, 'response'):
                print(f"Response content: {e.response.content}")
            break
            
    return collections

def format_video_url(video_id: str) -> str:
    """Format video ID into shareable URL."""
    return f"https://tiktokv.com/share/video/{video_id}"

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Fetch all collections for a TikTok user')
    parser.add_argument('username', help='TikTok username to fetch collections from')
    args = parser.parse_args()
    
    try:
        print(f"\nFetching collections for user @{args.username}...")
        collections = fetch_collections(args.username)
        
        if not collections:
            print("No collections found for this user")
            return 1
            
        print(f"\nFound {len(collections):,} collections")
        
        # Create output directory if it doesn't exist
        output_dir = f"collections_{args.username}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Process each collection
        for collection in collections:
            collection_name = collection['name']
            collection_id = collection['id']
            safe_name = collection_name
            
            print(f"\nProcessing collection: {collection_name} ({collection_id})")
            
            # Use fetch_collection_items from fetch_collection_api.py
            video_ids = fetch_collection_items(collection_id)
            
            if video_ids:
                output_file = os.path.join(output_dir, f"{safe_name}.txt")
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