#!/usr/bin/env python3
"""Script to extract and optionally download TikTok audio files from a text file containing sound links."""

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

def extract_links(input_file):
    """Extract TikTok sound links from the input file."""
    links = []
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Find all sound links using regex
    pattern = r'Sound Link: (https://[^\s]+)'
    matches = re.finditer(pattern, content)
    
    for match in matches:
        links.append(match.group(1))
        
    return links

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

def download_audio(url, output_dir, index, max_retries=3):
    """Download the audio file from the given URL."""
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
                
            # Ensure filename has proper extension
            if not filename.lower().endswith(('.mp3', '.m4a', '.wav')):
                filename += '.mp3'
                
            filepath = os.path.join(output_dir, filename)
            
            # Remove file if it exists from previous attempt
            if os.path.exists(filepath):
                os.remove(filepath)
            
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

def process_link(driver, link, output_dir, index):
    """Process a single link with the given driver."""
    print(f"\nProcessing link {index:,}: {link}")
    
    # Get download link
    download_link = get_audio_download_link(driver, link)
    if download_link:
        # Download the file
        filepath = download_audio(download_link, output_dir, index)
        if filepath:
            print(f"Downloaded to: {filepath}")
            return True, link
        else:
            print("Failed to download audio")
            return False, link
    else:
        print("Failed to get download link")
        return False, link

def main():
    parser = argparse.ArgumentParser(description='Extract and download TikTok audio files.')
    parser.add_argument('input_file', help='Input file containing TikTok sound links')
    parser.add_argument('--download', action='store_true', help='Download the audio files')
    parser.add_argument('--concurrent', type=int, default=5, help='Number of concurrent downloads (default: 5)')
    args = parser.parse_args()
    
    # Extract links
    links = extract_links(args.input_file)
    print(f"Found {len(links):,} sound links")
    
    if not links:
        print("No links found in input file")
        sys.exit(1)
    
    # Get input file directory
    input_dir = os.path.dirname(os.path.abspath(args.input_file))
    
    # Save links to file
    links_file = os.path.join(input_dir, 'links.txt')
    with open(links_file, 'w', encoding='utf-8') as f:
        for link in links:
            f.write(f"{link}\n")
    print(f"\nSaved {len(links):,} links to: {links_file}")
    
    # Create Sounds directory if downloading
    if args.download:
        output_dir = os.path.join(input_dir, 'Sounds')
        os.makedirs(output_dir, exist_ok=True)
        print(f"Created output directory: {output_dir}")
        
        # Set up log files
        success_file = os.path.join(input_dir, 'download_success.log')
        failed_file = os.path.join(input_dir, 'failed_downloads.log')
        
        # Load previously successful downloads
        successful_links = set()
        if os.path.exists(success_file):
            with open(success_file, 'r', encoding='utf-8') as f:
                successful_links = {line.strip() for line in f if line.strip()}
        
        # Filter out already downloaded links
        links_to_process = [link for link in links if link not in successful_links]
        if len(links) != len(links_to_process):
            print(f"Skipping {len(links) - len(links_to_process):,} already downloaded files")
            links = links_to_process
    
    # Track failures and successes
    failed_links = []
    successful_downloads = []
    
    if args.download and links:
        # Create a pool of webdrivers
        drivers = []
        try:
            # Create webdriver pool
            print(f"\nInitializing {args.concurrent} concurrent downloaders...")
            for _ in range(min(args.concurrent, len(links))):
                drivers.append(setup_driver())
            
            # Process links concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(drivers)) as executor:
                # Create tasks for each link
                future_to_link = {
                    executor.submit(
                        process_link,
                        drivers[i % len(drivers)],
                        link,
                        output_dir,
                        i + 1
                    ): link
                    for i, link in enumerate(links)
                }
                
                # Process completed tasks
                for future in concurrent.futures.as_completed(future_to_link):
                    try:
                        success, link = future.result()
                        if success:
                            successful_downloads.append(link)
                            print(f"Successfully downloaded: {link}")
                            # Save success immediately
                            with open(success_file, 'a', encoding='utf-8') as f:
                                f.write(f"{link}\n")
                        else:
                            failed_links.append(link)
                            print(f"Failed to download: {link}")
                            # Save failure immediately
                            with open(failed_file, 'a', encoding='utf-8') as f:
                                f.write(f"{link}\n")
                    except Exception as e:
                        link = future_to_link[future]
                        failed_links.append(link)
                        print(f"Exception occurred while processing {link}: {str(e)}")
                        # Save failure immediately
                        with open(failed_file, 'a', encoding='utf-8') as f:
                            f.write(f"{link}\n")
        
        finally:
            # Clean up drivers
            for driver in drivers:
                try:
                    driver.quit()
                except:
                    pass
            
            # Print summary
            print("\nDownload Summary:")
            print(f"Successfully downloaded: {len(successful_downloads):,} of {len(links):,} audio files")
            print(f"Failed downloads: {len(failed_links):,}")
            
            # Print failed links
            if failed_links:
                print("\nFailed downloads:")
                for link in failed_links:
                    print(link)
                print(f"\nFailed download links have been saved to: {failed_file}")
    
    elif not args.download:
        # Just print the links if not downloading
        for i, link in enumerate(links, 1):
            print(f"Link {i}: {link}")

if __name__ == '__main__':
    main() 