#!/usr/bin/env python3
"""Script to download TikTok slideshows using the selenium pipeline."""

import os
import sys
import argparse
import threading
from queue import Queue

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from downloader.selenium_handler import SeleniumHandler
from downloader.file_handler import FileHandler
from downloader.utils import extract_video_id

# Global variables for progress tracking
slideshow_queue = Queue()
slideshow_thread_stop = threading.Event()
slideshow_total_items = 0
slideshow_processed_items = 0
slideshow_counter_lock = threading.Lock()
slideshow_threads = []

def process_url(selenium_handler, url, output_folder, file_handler, collection_name=None):
    """Process a single URL, only continuing if it's a slideshow."""
    try:
        # Try downloading with selenium, only allowing photos
        selenium_handler.download_with_selenium(url, output_folder, file_handler, collection_name, photos_only=True)
        return True
    except Exception as e:
        if "private" in str(e).lower():
            print(f"\t-> Skipping private video: {url}")
        elif "skipping non-photo content" in str(e).lower():
            print(f"\t-> Skipping non-photo content: {url}")
        else:
            print(f"\t-> Failed to download: {url}")
            print(f"\t-> Error: {str(e)}")
        return False

def slideshow_worker(selenium_handler, file_handler, worker_num):
    """Worker thread that processes slideshow downloads."""
    global slideshow_processed_items, slideshow_total_items
    
    while not slideshow_thread_stop.is_set():
        try:
            # Get next item from queue with timeout to allow checking stop flag
            try:
                url, output_folder, collection_name = slideshow_queue.get(timeout=1)
            except:
                # Reset counters if queue is empty
                if slideshow_queue.empty():
                    with slideshow_counter_lock:
                        slideshow_processed_items = 0
                        slideshow_total_items = 0
                continue
                
            try:
                # Update progress counter
                with slideshow_counter_lock:
                    slideshow_processed_items += 1
                    current = slideshow_processed_items
                    total = slideshow_total_items
                    print(f"\n[Worker {worker_num}] [Progress: {current:,} of {total:,}]")
                
                process_url(selenium_handler, url, output_folder, file_handler, collection_name)
                
            except Exception as e:
                print(f"[Worker {worker_num}] \t  ❌\tError processing {url}: {str(e)}")
            finally:
                slideshow_queue.task_done()
                
        except Exception as e:
            print(f"[Worker {worker_num}] \t  ❌\tWorker error: {str(e)}")

def start_slideshow_threads(selenium_handlers, file_handler):
    """Start multiple slideshow worker threads."""
    global slideshow_threads, slideshow_processed_items, slideshow_total_items
    slideshow_thread_stop.clear()
    slideshow_processed_items = 0
    slideshow_total_items = 0
    
    # Create and start a thread for each selenium handler
    for i, handler in enumerate(selenium_handlers, 1):
        thread = threading.Thread(
            target=slideshow_worker,
            args=(handler, file_handler, i),
            daemon=True
        )
        thread.start()
        slideshow_threads.append(thread)

def stop_slideshow_threads():
    """Stop all slideshow worker threads and wait for them to finish."""
    slideshow_thread_stop.set()
    for thread in slideshow_threads:
        thread.join()
    slideshow_threads.clear()

def queue_slideshow_download(url, output_folder, collection_name):
    """Queue a URL for slideshow download and update counter."""
    global slideshow_total_items
    with slideshow_counter_lock:
        slideshow_total_items += 1
    slideshow_queue.put((url, output_folder, collection_name))

def wait_for_slideshow_queue():
    """Wait for all queued slideshow downloads to complete."""
    slideshow_queue.join()

def collect_urls_from_file(file_path):
    """Read URLs from a file and return them with collection info."""
    collection_name = os.path.splitext(os.path.basename(file_path))[0]
    output_folder = os.path.join(os.path.dirname(file_path), collection_name)
    
    # Use set to deduplicate URLs within the same file
    unique_urls = set()
    with open(file_path, 'r') as f:
        for line in f:
            url = line.strip()
            if url and extract_video_id(url):  # Only add if we can extract a valid ID
                unique_urls.add(url)
    
    return [(url, output_folder, collection_name) for url in unique_urls]

def precheck_downloads(input_path, file_handler):
    """Check all URLs upfront and return unprocessed ones."""
    all_urls = set()  # Store tuples of (url, output_folder, collection_name)
    already_downloaded = set()  # Store tuples of (video_id, collection_name)
    
    # First collect URLs from regular collections to track their video IDs
    regular_collection_ids = set()  # Track video IDs in regular collections
    all_saves_urls = []  # Store all_saves URLs for later processing
    
    if os.path.isfile(input_path):
        file_urls = collect_urls_from_file(input_path)
        if os.path.basename(input_path).startswith(file_handler.all_saves_name):
            all_saves_urls.extend(file_urls)
        else:
            for url, output_folder, collection_name in file_urls:
                all_urls.add((url, output_folder, collection_name))
                # Track video IDs from regular collections
                video_id = extract_video_id(url)
                if video_id:
                    regular_collection_ids.add(video_id)
    else:
        for file in os.listdir(input_path):
            if file.endswith('.txt'):
                print(file)
                file_path = os.path.join(input_path, file)
                file_urls = collect_urls_from_file(file_path)
                if file.startswith(file_handler.all_saves_name):
                    all_saves_urls.extend(file_urls)
                else:
                    for url, output_folder, collection_name in file_urls:
                        all_urls.add((url, output_folder, collection_name))
                        # Track video IDs from regular collections
                        video_id = extract_video_id(url)
                        if video_id:
                            regular_collection_ids.add(video_id)
    # Now process all_saves URLs, skipping those that exist in regular collections
    for url, output_folder, collection_name in all_saves_urls:
        video_id = extract_video_id(url)
        if video_id and video_id not in regular_collection_ids:
            all_urls.add((url, output_folder, collection_name))
    
    # Check which URLs are already downloaded using video IDs
    unprocessed_urls = []
    for url, output_folder, collection_name in all_urls:
        video_id = extract_video_id(url)
        if video_id:
            # Check if this video ID is downloaded in this collection
            id_with_collection = f"{video_id}:::{collection_name}"
            if file_handler.is_url_downloaded(url, collection_name):
                already_downloaded.add((video_id, collection_name))
            else:
                unprocessed_urls.append((url, output_folder, collection_name))
            
    # Print summary
    print(f"\nFound {len(all_urls):,} unique URLs to process")
    print(f"✓ {len(already_downloaded):,} already downloaded")
    if already_downloaded:
        by_collection = {}
        for video_id, collection in already_downloaded:
            by_collection[collection] = by_collection.get(collection, 0) + 1
        print("\nAlready downloaded by collection:")
        for collection, count in sorted(by_collection.items()):
            print(f"  • {collection}: {count:,}")
            
    remaining = len(unprocessed_urls)
    if remaining:
        print(f"\n→ Processing remaining {remaining:,} URLs")
    else:
        print("\nNo new URLs to process!")
        
    return unprocessed_urls

def process_file(file_path, selenium_handlers, file_handler):
    """Process a single file containing URLs."""
    # Get collection name and create output folder
    collection_name = os.path.splitext(os.path.basename(file_path))[0]
    output_folder = os.path.join(os.path.dirname(file_path), collection_name)
    os.makedirs(output_folder, exist_ok=True)
    
    # Read URLs
    with open(file_path, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    # Queue unprocessed URLs
    for url in urls:
        if not file_handler.is_url_downloaded(url, collection_name):
            queue_slideshow_download(url, output_folder, collection_name)

def main():
    parser = argparse.ArgumentParser(description='Download TikTok slideshows using selenium pipeline')
    parser.add_argument('input_path', help='Path to directory containing text files with TikTok URLs or a single text file')
    parser.add_argument('--disable-headless', action='store_true', help='Disable headless mode (show browser)')
    parser.add_argument('--concurrent', type=int, default=5, help='Number of concurrent downloads (default: 5)')
    
    args = parser.parse_args()

    if not os.path.exists(args.input_path):
        print(f"Error: {args.input_path} does not exist")
        sys.exit(1)

    # Initialize handlers
    file_handler = FileHandler(args.input_path)
    
    # Create base temp download directory
    if os.path.isfile(args.input_path):
        base_dir = os.path.dirname(args.input_path)
    else:
        base_dir = args.input_path
        
    # Check all URLs upfront
    unprocessed_urls = precheck_downloads(args.input_path, file_handler)
    if not unprocessed_urls:
        return
        
    # Create multiple selenium handlers with unique temp directories
    selenium_handlers = []
    for i in range(args.concurrent):
        temp_download_dir = os.path.join(base_dir, f"_tmp_{i+1}")
        os.makedirs(temp_download_dir, exist_ok=True)
        selenium_handlers.append(SeleniumHandler(temp_download_dir, headless=not args.disable_headless, worker_num=i+1))

    try:
        # Start up all selenium handlers
        for handler in selenium_handlers:
            handler.startup()
            
        # Start worker threads
        start_slideshow_threads(selenium_handlers, file_handler)
        
        # Queue all unprocessed URLs
        for url, output_folder, collection_name in unprocessed_urls:
            queue_slideshow_download(url, output_folder, collection_name)
        
        # Wait for all downloads to complete
        print("\nWaiting for queued downloads to complete...")
        wait_for_slideshow_queue()
    
    finally:
        # Stop worker threads
        stop_slideshow_threads()
        
        # Clean up selenium handlers
        for handler in selenium_handlers:
            handler.shutdown()
        
        # Clean up temp directories
        for i in range(args.concurrent):
            temp_download_dir = os.path.join(base_dir, f"_tmp_{i+1}")
            if os.path.exists(temp_download_dir):
                for file in os.listdir(temp_download_dir):
                    try:
                        os.remove(os.path.join(temp_download_dir, file))
                    except:
                        pass
                try:
                    os.rmdir(temp_download_dir)
                except:
                    pass

    print("\nProcessing complete.")

if __name__ == '__main__':
    main() 