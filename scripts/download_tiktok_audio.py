#!/usr/bin/env python3
"""Script to extract and optionally download TikTok audio files from a text file containing sound links."""

import os
import re
import sys
import time
import argparse
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
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
    # options.add_argument('--headless')
    
    # Create driver
    driver = webdriver.Firefox(options=options)
    return driver

def get_audio_download_link(driver, tiktok_url):
    """Get the audio download link from musicaldown.com."""
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
        return None
    except Exception as e:
        print(f"Error processing {tiktok_url}: {str(e)}")
        return None

def download_audio(url, output_dir, index):
    """Download the audio file from the given URL."""
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
        
        # Download the file
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
        return filepath
    except Exception as e:
        print(f"Error downloading audio: {str(e)}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Extract and download TikTok audio files.')
    parser.add_argument('input_file', help='Input file containing TikTok sound links')
    parser.add_argument('--download', action='store_true', help='Download the audio files')
    args = parser.parse_args()
    
    # Extract links
    links = extract_links(args.input_file)
    print(f"Found {len(links)} sound links")
    
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
    print(f"\nSaved {len(links)} links to: {links_file}")
    
    # Create Sounds directory if downloading
    if args.download:
        output_dir = os.path.join(input_dir, 'Sounds')
        os.makedirs(output_dir, exist_ok=True)
        print(f"Created output directory: {output_dir}")
    
    # Set up webdriver if needed
    driver = None
    if args.download:
        driver = setup_driver()
    
    try:
        for i, link in enumerate(links, 1):
            print(f"\nProcessing link {i}/{len(links)}: {link}")
            
            if args.download:
                # Get download link
                download_link = get_audio_download_link(driver, link)
                if download_link:
                    print(f"Found download link: {download_link}")
                    
                    # Download the file
                    filepath = download_audio(download_link, output_dir, i)
                    if filepath:
                        print(f"Downloaded to: {filepath}")
                    else:
                        print("Failed to download audio")
                else:
                    print("Failed to get download link")
            else:
                print(f"Link {i}: {link}")
            
    
    finally:
        if driver:
            driver.quit()

if __name__ == '__main__':
    main() 