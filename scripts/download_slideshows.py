#!/usr/bin/env python3
"""Download TikTok slideshows using selenium pipeline."""

import os
import sys
import argparse
from downloader.file_handler import FileHandler
from downloader.selenium_handler import SeleniumHandler
from downloader.worker_pool import WorkerPool

def precheck_downloads(input_path, file_handler):
    """Check all URLs upfront and return unprocessed ones."""
    unprocessed_urls = []
    
    if os.path.isfile(input_path):
        if not input_path.endswith('.txt'):
            print(f"Error: {input_path} is not a .txt file")
            return []
        files = [input_path]
        base_dir = os.path.dirname(input_path)
    else:
        files = [os.path.join(input_path, f) for f in os.listdir(input_path) 
                if f.endswith('.txt') and not f.startswith('error_')]
        base_dir = input_path
    
    for file_path in files:
        collection_name = os.path.basename(file_path).split('.txt')[0]
        output_folder = os.path.join(os.path.dirname(file_path), collection_name)
        
        with open(file_path, 'r') as f:
            urls = [url.strip() for url in f.readlines() if url.strip()]
        
        for url in urls:
            if not file_handler.is_url_downloaded(url, collection_name):
                unprocessed_urls.append((url, output_folder, collection_name))
    
    if unprocessed_urls:
        print(f"\nFound {len(unprocessed_urls):,} unprocessed URLs")
    else:
        print("\nNo unprocessed URLs found")
    
    return unprocessed_urls

def process_url(selenium_handler, url, output_folder, file_handler, collection_name):
    """Process a single URL using selenium."""
    try:
        selenium_handler.download_with_selenium(url, output_folder, file_handler, collection_name, photos_only=True)
        file_handler.log_successful_download(url, collection_name)
    except Exception as e:
        if str(e) == "Skipping non-photo content":
            print(f"\t-> Skipping non-photo content: {url}")
        else:
            raise

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
    
    # Create worker pool
    worker_pool = WorkerPool()

    try:
        # Start up all selenium handlers
        for handler in selenium_handlers:
            handler.startup()
            
        # Start worker threads
        worker_pool.start_selenium_threads(selenium_handlers, file_handler, None)
        
        # Queue all unprocessed URLs
        for url, output_folder, collection_name in unprocessed_urls:
            worker_pool.queue_selenium_download(url, collection_name, "known-photo", output_folder)
        
        # Wait for all downloads to complete
        print("\nWaiting for queued downloads to complete...")
        worker_pool.wait_for_selenium_queue()
    
    finally:
        # Stop worker threads and clean up
        worker_pool.shutdown()
        
        # Clean up selenium handlers
        for handler in selenium_handlers:
            handler.shutdown()

    print("\nProcessing complete.")

if __name__ == '__main__':
    main() 