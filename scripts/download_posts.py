#!/usr/bin/env python3
"""Script to download TikTok posts from a text file containing post links."""

import os
import re
import sys
import time
import argparse
import subprocess
import concurrent.futures
from pathlib import Path
import threading
import hashlib

# Minimum expected file size for a valid video (500KB)
MIN_FILE_SIZE = 500 * 1024

def format_filename(url, index):
    """Format filename according to specified pattern."""
    # Create a short hash of the URL to ensure unique filenames
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"Post {index} {url_hash}.mp4"

def find_file_by_hash(directory, url):
    """Find a file in directory that matches the URL hash."""
    if not os.path.exists(directory):
        return None
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    for filename in os.listdir(directory):
        if url_hash in filename and filename.endswith('.mp4'):
            return os.path.join(directory, filename)
    return None

def download_video(url, output_path, index, max_retries=3):
    """Download video using curl."""
    output_file = os.path.join(output_path, format_filename(url, index))
    
    for attempt in range(max_retries):
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_path, exist_ok=True)
            
            # Remove file if it exists from previous attempt
            if os.path.exists(output_file):
                os.remove(output_file)
            
            # Download using curl with progress bar
            cmd = ["curl", "-L", "--retry", "3", "--retry-delay", "2", 
                   "--connect-timeout", "10", "--max-time", "60",
                   "--progress-bar",  # Show progress bar
                   url, "-o", output_file]
            
            result = subprocess.run(cmd)
            
            if result.returncode != 0:
                raise Exception(f"curl returned error code {result.returncode}")
                
            # Verify file exists and has minimum size
            if not os.path.exists(output_file):
                raise Exception("Downloaded file is missing")
                
            file_size = os.path.getsize(output_file)
            if file_size < MIN_FILE_SIZE:
                os.remove(output_file)
                raise Exception(f"Downloaded file is too small ({file_size} bytes)")
                
            return output_file
            
        except Exception as e:
            print(f"Error downloading post: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                time.sleep(2)
            continue
    
    print(f"Failed to download post after {max_retries} attempts")
    return None

def validate_download_logs(output_dir, success_file, failed_file, links):
    """Validate downloaded files against logs and fix any inconsistencies."""
    print("\nValidating downloads and logs...")
    
    # Ensure log files exist
    for log_file in [success_file, failed_file]:
        if not os.path.exists(log_file):
            with open(log_file, 'w', encoding='utf-8') as f:
                pass
    
    # Read current logs
    success_links = set()
    failed_links = set()
    
    try:
        with open(success_file, 'r', encoding='utf-8') as f:
            success_links = {line.strip() for line in f if line.strip()}
    except Exception as e:
        print(f"Warning: Error reading success log: {str(e)}")
    
    try:
        with open(failed_file, 'r', encoding='utf-8') as f:
            failed_links = {line.strip() for line in f if line.strip()}
    except Exception as e:
        print(f"Warning: Error reading failed log: {str(e)}")
    
    # Track changes needed
    to_remove_from_success = set()
    to_add_to_failed = set()
    to_remove_from_failed = set()
    
    # Validate each link
    for link in links:
        file_exists = find_file_by_hash(output_dir, link) is not None
        
        if file_exists:
            # File exists - should be in success, not in failed
            if link in failed_links:
                to_remove_from_failed.add(link)
            if link not in success_links:
                with open(success_file, 'a', encoding='utf-8') as f:
                    f.write(f"{link}\n")
        else:
            # File doesn't exist - should be in failed, not in success
            if link in success_links:
                to_remove_from_success.add(link)
            if link not in failed_links:
                to_add_to_failed.add(link)
    
    # Apply changes safely
    try:
        if to_remove_from_success:
            success_links -= to_remove_from_success
            with open(success_file, 'w', encoding='utf-8') as f:
                for link in success_links:
                    f.write(f"{link}\n")
    except Exception as e:
        print(f"Warning: Error updating success log: {str(e)}")
    
    try:
        if to_remove_from_failed:
            failed_links -= to_remove_from_failed
            with open(failed_file, 'w', encoding='utf-8') as f:
                for link in failed_links:
                    f.write(f"{link}\n")
    except Exception as e:
        print(f"Warning: Error updating failed log: {str(e)}")
    
    try:
        if to_add_to_failed:
            with open(failed_file, 'a', encoding='utf-8') as f:
                for link in to_add_to_failed:
                    f.write(f"{link}\n")
    except Exception as e:
        print(f"Warning: Error adding to failed log: {str(e)}")
    
    return len(to_remove_from_success), len(to_remove_from_failed), len(to_add_to_failed)

def process_link(link, output_dir, index, success_file, failed_file, worker_number, verbose):
    """Process a single link."""
    print(f"\n[Worker {worker_number}] Downloading post {index:,}")
    if verbose:
        print(f"URL: {link}")
    
    try:
        filepath = download_video(link, output_dir, index)
        if filepath:
            file_size = os.path.getsize(filepath)
            print(f"Successfully downloaded: {os.path.basename(filepath)} ({file_size/1024/1024:.2f} MB)")
            return True
    except Exception as e:
        print(f"Error processing post {index}: {str(e)}")
    
    return False

def find_input_file(directory):
    """Find the All Personal Posts.txt file in the given directory."""
    target_file = 'All Personal Posts.txt'
    for root, _, files in os.walk(directory):
        if target_file in files:
            return os.path.join(root, target_file)
    return None

def read_links(file_path):
    """Read links from the input file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def main():
    parser = argparse.ArgumentParser(description='Download TikTok posts from a text file.')
    parser.add_argument('input_path', help='Input file containing TikTok post links or directory containing All Personal Posts.txt')
    parser.add_argument('--concurrent', type=int, default=3, help='Number of concurrent downloads (default: 3)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed progress')
    args = parser.parse_args()
    
    # Determine if input is a directory or file
    input_path = os.path.abspath(args.input_path)
    if os.path.isdir(input_path):
        source_path = find_input_file(input_path)
        if not source_path:
            print(f"Error: Could not find All Personal Posts.txt in {input_path} or its subdirectories")
            sys.exit(1)
        base_dir = input_path
    else:
        source_path = input_path
        base_dir = os.path.dirname(input_path)
    
    # Read links
    links = read_links(source_path)
    if not links:
        print("No links found in input file")
        sys.exit(1)
    
    print(f"Found {len(links):,} links to process")
    
    # Set up output directory and log files
    output_dir = os.path.join(base_dir, 'All Personal Posts')
    os.makedirs(output_dir, exist_ok=True)
    
    # Put log files in same directory as input file
    log_dir = os.path.dirname(source_path)
    success_file = os.path.join(log_dir, 'download_success.log')
    failed_file = os.path.join(log_dir, 'download_failed.log')
    
    # Thread-safe logging functions
    log_lock = threading.Lock()
    
    def log_success(link):
        with log_lock:
            try:
                with open(success_file, 'a', encoding='utf-8') as f:
                    f.write(f"{link}\n")
            except Exception as e:
                print(f"Warning: Error logging success: {str(e)}")
    
    def log_failure(link):
        with log_lock:
            try:
                with open(failed_file, 'a', encoding='utf-8') as f:
                    f.write(f"{link}\n")
            except Exception as e:
                print(f"Warning: Error logging failure: {str(e)}")
    
    def remove_from_failed(link):
        with log_lock:
            try:
                with open(failed_file, 'r', encoding='utf-8') as f:
                    failed_links = [l.strip() for l in f if l.strip() != link]
                with open(failed_file, 'w', encoding='utf-8') as f:
                    for l in failed_links:
                        f.write(f"{l}\n")
            except Exception as e:
                print(f"Warning: Error removing from failed log: {str(e)}")
    
    # Read current success/failed logs
    try:
        with open(success_file, 'r', encoding='utf-8') as f:
            success_links = {line.strip() for line in f if line.strip()}
    except:
        success_links = set()
    
    try:
        with open(failed_file, 'r', encoding='utf-8') as f:
            failed_links = {line.strip() for line in f if line.strip()}
    except:
        failed_links = set()
    
    # Filter out already successful downloads
    links_to_process = []
    skipped = 0
    for link in links:
        if link in success_links:
            if find_file_by_hash(output_dir, link):
                skipped += 1
                continue
            else:
                # File was in success log but not found - remove from success and retry
                success_links.remove(link)
                with open(success_file, 'w', encoding='utf-8') as f:
                    for l in success_links:
                        f.write(f"{l}\n")
        links_to_process.append(link)
    
    if skipped > 0:
        print(f"\nSkipped {skipped:,} previously downloaded posts")
    
    if not links_to_process:
        print("\nAll links have been successfully downloaded!")
        sys.exit(0)
    
    print(f"\nProcessing {len(links_to_process):,} remaining posts...")
    
    # Process links with thread pool
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrent) as executor:
        futures = []
        for i, link in enumerate(links_to_process, 1):
            worker_number = (i % args.concurrent) + 1
            future = executor.submit(
                process_link, link, output_dir, i, 
                success_file, failed_file, worker_number, args.verbose
            )
            futures.append((future, link))
        
        # Process results as they complete
        successful = 0
        failed = 0
        for future, link in futures:
            try:
                if future.result():
                    successful += 1
                    log_success(link)
                    if link in failed_links:
                        remove_from_failed(link)
                else:
                    failed += 1
                    log_failure(link)
            except Exception as e:
                print(f"Error processing post {i}: {str(e)}")
                failed += 1
                log_failure(link)
    
    print(f"\nDownload Summary:")
    if skipped > 0:
        print(f"- Previously downloaded: {skipped:,} posts")
    print(f"- Successfully downloaded: {successful:,} posts")
    print(f"- Failed downloads: {failed:,} posts")
    print(f"- Total processed: {successful + failed:,} posts")
    print(f"\nOutput directory: {output_dir}")
    if failed > 0:
        print(f"Failed downloads are logged in: {failed_file}")

if __name__ == '__main__':
    main() 