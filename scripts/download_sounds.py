#!/usr/bin/env python3
"""Script to download TikTok audio files from a text file containing sound links."""

import os
import re
import sys
import time
import argparse
import requests
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import threading

def setup_driver():
    """Set up and return a Firefox webdriver instance."""
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service
    
    options = Options()
    options.add_argument('--headless')
    
    # Create driver
    driver = webdriver.Firefox(options=options)
    return driver

def get_audio_download_link(driver, tiktok_url, max_retries=3):
    """Get the audio download link from musicaldown.com."""
    for attempt in range(max_retries):
        try:
            # Go to musicaldown.com
            driver.get('https://musicaldown.com')
            
            # Find and fill the input field
            input_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
            )
            input_field.clear()
            input_field.send_keys(tiktok_url)
            
            # Click the submit button
            submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            submit_btn.click()
            
            # Wait for the MP3 download button
            download_link = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.btn.waves-effect.waves-light.orange.download[data-event='mp3_download_click']"))
            )
            
            return download_link.get_attribute('href')
            
        except TimeoutException:
            print(f"Timeout while processing {tiktok_url}")
            if attempt < max_retries - 1:
                print(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                time.sleep(1)
            continue
        except Exception as e:
            print(f"Error processing {tiktok_url}: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                time.sleep(1)
            continue
    
    print(f"Failed to get download link after {max_retries} attempts")
    return None

def extract_music_id(url):
    """Extract the music ID from a TikTok music URL."""
    match = re.search(r'/music/(\d+)', url)
    return match.group(1) if match else None

def format_filename(original_filename, music_id):
    """Format filename according to specified pattern."""
    # Split on _musicaldown.com_ and take first part
    name_parts = original_filename.split('_musicaldown.com_')
    base_name = name_parts[0]
    
    # Get extension from original filename
    ext = os.path.splitext(original_filename)[1]
    if not ext:
        ext = '.mp3'  # Default extension
    
    # Limit base name to 70 chars
    base_name = base_name[:70].rstrip()
    
    # Prefix with underscore if base name starts with a period
    if base_name.startswith('.'):
        base_name = f"_{base_name}"
    
    # Create new filename
    return f"{base_name} {music_id}{ext}"

def find_file_by_id(directory, music_id):
    """Find a file in directory that ends with the music ID."""
    if not os.path.exists(directory):
        return None
    for filename in os.listdir(directory):
        name_without_ext, ext = os.path.splitext(filename)
        if name_without_ext.endswith(str(music_id)):
            return os.path.join(directory, filename)
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
        music_id = extract_music_id(link)
        if not music_id:
            continue
            
        file_exists = find_file_by_id(output_dir, music_id) is not None
        
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

def download_audio(url, output_dir, index, link, max_retries=3):
    """Download the audio file from the given URL."""
    music_id = extract_music_id(link)
    if not music_id:
        raise Exception("Could not extract music ID from URL")
        
    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Try to get filename from content-disposition header
            cd = response.headers.get('content-disposition')
            filename = None
            if cd:
                filename = re.findall("filename=(.+)", cd)
                if filename:
                    filename = filename[0].strip('"')
            
            # If no filename found, create one
            if not filename:
                filename = f'audio_{index}.mp3'
            
            # Format filename with music ID
            filename = format_filename(filename, music_id)
            filepath = os.path.join(output_dir, filename)
            
            # Download the file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Verify file exists and has minimum size
            if not os.path.exists(filepath):
                raise Exception("Downloaded file is missing")
            
            file_size = os.path.getsize(filepath)
            if file_size < 1024:  # Minimum 1KB
                os.remove(filepath)
                raise Exception(f"Downloaded file is too small ({file_size} bytes)")
                    
            return filepath
            
        except Exception as e:
            print(f"Error downloading audio: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                time.sleep(2)
            continue
    
    print(f"Failed to download audio after {max_retries} attempts")
    return None

def process_link(driver, link, output_dir, index, success_file, failed_file, worker_number, verbose):
    """Process a single link with the given driver."""
    print(f"\n[Worker {worker_number}] Downloading link {index:,}: {link}")
    
    # Get download link
    download_link = get_audio_download_link(driver, link)
    if download_link:
        # Download the file
        filepath = download_audio(download_link, output_dir, index, link)
        if filepath:
            if verbose:
                print(f"[Worker {worker_number}] Downloaded as: {os.path.basename(filepath)}")
            
            # Verify file exists with correct ID before logging success
            music_id = extract_music_id(link)
            if music_id and find_file_by_id(output_dir, music_id):
                # Check if link is not already in success file before appending
                with open(success_file, 'r', encoding='utf-8') as f:
                    existing_successes = {line.strip() for line in f}
                if link not in existing_successes:
                    with open(success_file, 'a', encoding='utf-8') as f:
                        f.write(f"{link}\n")
                
                # Remove from failed file if present
                if os.path.exists(failed_file):
                    with open(failed_file, 'r', encoding='utf-8') as f:
                        failed_links = [l.strip() for l in f if l.strip() != link]
                    with open(failed_file, 'w', encoding='utf-8') as f:
                        for l in failed_links:
                            f.write(f"{l}\n")
                
                return True, link
            else:
                print(f"[Worker {worker_number}] File verification failed - file not found with correct ID")
                return False, link
        else:
            print(f"[Worker {worker_number}] Failed to download audio")
            return False, link
    else:
        print(f"[Worker {worker_number}] Failed to get download link")
        return False, link

def find_input_file(directory):
    """Recursively search for 'All Saved Sounds.txt' in the given directory and its subdirectories."""
    for root, _, files in os.walk(directory):
        if 'All Saved Sounds.txt' in files:
            return os.path.join(root, 'All Saved Sounds.txt')
    return None

def read_links(file_path):
    """Read links from a file, one per line."""
    links = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            link = line.strip()
            if link:
                links.append(link)
    return links

def main():
    parser = argparse.ArgumentParser(description='Download TikTok audio files.')
    parser.add_argument('input_path', help='Input file containing TikTok sound links or directory containing All Saved Sounds.txt')
    parser.add_argument('--concurrent', type=int, default=5, help='Number of concurrent downloads (default: 5)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    verbose = args.verbose
    
    # Determine if input is a directory or file
    input_path = os.path.abspath(args.input_path)
    if os.path.isdir(input_path):
        # Search for Sound Links.txt in the directory and subdirectories
        source_path = find_input_file(input_path)
        if not source_path:
            print(f"Error: Could not find Sound Links.txt in {input_path} or its subdirectories")
            sys.exit(1)
        base_dir = input_path
    else:
        source_path = input_path
        base_dir = os.path.dirname(input_path)
    
    source_dir = os.path.dirname(source_path)
    
    # Read links
    links = read_links(source_path)
    print(f"Found {len(links):,} sound links")
    
    if not links:
        print("No links found in input file")
        sys.exit(1)
    
    # Create output directory
    output_dir = os.path.join(base_dir, 'All Saved Sounds')
    os.makedirs(output_dir, exist_ok=True)
    if verbose:
        print(f"Created output directory: {output_dir}")
    
    # Set up log files in the source directory
    success_file = os.path.join(source_dir, 'sounds_success.log')
    failed_file = os.path.join(source_dir, 'sounds_failed.log')
    
    # Ensure log files exist
    for log_file in [success_file, failed_file]:
        if not os.path.exists(log_file):
            with open(log_file, 'w', encoding='utf-8') as f:
                pass
    
    # Load existing logs into memory
    successful_links = set()
    failed_links = set()
    
    try:
        if os.path.exists(success_file):
            with open(success_file, 'r', encoding='utf-8') as f:
                successful_links = {line.strip() for line in f if line.strip()}
    except Exception as e:
        print(f"Warning: Error reading success log: {str(e)}")
    
    try:
        if os.path.exists(failed_file):
            with open(failed_file, 'r', encoding='utf-8') as f:
                failed_links = {line.strip() for line in f if line.strip()}
    except Exception as e:
        print(f"Warning: Error reading failed log: {str(e)}")
    
    # Create locks for thread-safe file writing
    success_lock = threading.Lock()
    failed_lock = threading.Lock()
    
    def log_success(link):
        """Thread-safe success logging"""
        try:
            with success_lock:
                if link not in successful_links:
                    successful_links.add(link)
                    with open(success_file, 'a', encoding='utf-8') as f:
                        f.write(f"{link}\n")
                        f.flush()
                        os.fsync(f.fileno())
        except Exception as e:
            print(f"Warning: Error logging success: {str(e)}")
    
    def log_failure(link):
        """Thread-safe failure logging"""
        try:
            with failed_lock:
                if link not in failed_links:
                    failed_links.add(link)
                    with open(failed_file, 'a', encoding='utf-8') as f:
                        f.write(f"{link}\n")
                        f.flush()
                        os.fsync(f.fileno())
        except Exception as e:
            print(f"Warning: Error logging failure: {str(e)}")
    
    def remove_from_failed(link):
        """Thread-safe removal from failed log"""
        try:
            with failed_lock:
                if link in failed_links:
                    failed_links.remove(link)
                    with open(failed_file, 'w', encoding='utf-8') as f:
                        for l in failed_links:
                            f.write(f"{l}\n")
                        f.flush()
                        os.fsync(f.fileno())
        except Exception as e:
            print(f"Warning: Error removing from failed log: {str(e)}")
    
    # Filter out already downloaded links
    links_to_process = [link for link in links if link not in successful_links]
    if len(links) != len(links_to_process):
        print(f"Skipping {len(links) - len(links_to_process):,} already downloaded files")
        links = links_to_process
    
    # Track failures and successes for this session
    session_failed_links = []
    session_successful_downloads = []
    
    if links:
        # Create a pool of webdrivers
        drivers = []
        try:
            # Create webdriver pool
            print(f"\nInitializing {args.concurrent} concurrent downloaders...")
            for _ in range(min(args.concurrent, len(links))):
                drivers.append(setup_driver())
            
            # Process links concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(drivers)) as executor:
                future_to_link = {
                    executor.submit(
                        process_link,
                        drivers[i % len(drivers)],
                        link,
                        output_dir,
                        i + 1,
                        success_file,
                        failed_file,
                        i % len(drivers) + 1,  # Pass worker number
                        verbose
                    ): link
                    for i, link in enumerate(links)
                }
                
                # Process completed tasks
                for future in concurrent.futures.as_completed(future_to_link):
                    try:
                        success, link = future.result()
                        if success:
                            session_successful_downloads.append(link)
                            if verbose:
                                print(f"[Worker {i % len(drivers) + 1}] Successfully downloaded: {link}")
                            log_success(link)
                            remove_from_failed(link)
                        else:
                            session_failed_links.append(link)
                            print(f"[Worker {i % len(drivers) + 1}] Failed to download: {link}")
                            log_failure(link)
                    except Exception as e:
                        link = future_to_link[future]
                        session_failed_links.append(link)
                        print(f"[Worker {i % len(drivers) + 1}] Exception occurred while processing {link}: {str(e)}")
                        log_failure(link)
        
        finally:
            # Clean up drivers
            for driver in drivers:
                try:
                    driver.quit()
                except:
                    pass
            
            # Validate downloads and logs
            removed_success, removed_failed, added_failed = validate_download_logs(
                output_dir, success_file, failed_file, links
            )
            
            # Verify actual files in directory
            actual_files = [f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f)) 
                          and f.lower().endswith(('.mp3', '.m4a', '.wav'))]
            
            # Print summary
            print("\nDownload Summary:")
            print(f"Files reported as successfully downloaded this session: {len(session_successful_downloads):,}")
            print(f"Total successful downloads in log: {len(successful_links):,}")
            print(f"Actual audio files in directory: {len(actual_files):,}")
            print(f"Total attempted downloads this session: {len(links):,}")
            print(f"Failed downloads this session: {len(session_failed_links):,}")
            print(f"Total failed downloads in log: {len(failed_links):,}")
            
            if removed_success or removed_failed or added_failed:
                print("\nLog Validation Results:")
                print(f"Removed from success log: {removed_success}")
                print(f"Removed from failed log: {removed_failed}")
                print(f"Added to failed log: {added_failed}")
            
            # Print failed links from this session
            if session_failed_links:
                print("\nFailed downloads this session:")
                for link in session_failed_links:
                    print(link)
                print(f"\nFailed download links have been saved to: {failed_file}")
            
            # Print warning if counts don't match
            if len(actual_files) != len(successful_links):
                print(f"\nWARNING: Mismatch between logged successes ({len(successful_links)}) "
                      f"and actual files ({len(actual_files)})")
                print("This could indicate some files were not properly saved or were removed.")

if __name__ == '__main__':
    main() 