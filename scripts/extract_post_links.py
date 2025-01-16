#!/usr/bin/env python3
"""Script to extract TikTok links from text files and download videos from tiktokv.us URLs."""

import os
import re
import argparse
import subprocess
import time
from pathlib import Path

# Minimum expected file size for a valid video (500KB)
MIN_FILE_SIZE = 500 * 1024

def extract_links(input_file):
    """Extract TikTok links from the input file."""
    links = []
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
        # Find all lines starting with "Link: " and capture the URL
        matches = re.finditer(r'Link:\s*(https?://[^\s\n]+)', content)
        links.extend(match.group(1) for match in matches)
    return links

def download_video(url, output_path, index, max_retries=3):
    """Download video using curl if it's a tiktokv.us URL."""
    if 'tiktokv.us' not in url:
        print(f"Skipping non-tiktokv.us URL: {url}")
        return False
        
    output_file = os.path.join(output_path, f"Video {index}.mp4")
    
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
            
            print(f"\nDownloading Video {index}...")
            result = subprocess.run(cmd)
            
            if result.returncode != 0:
                print(f"Error downloading {url}")
                if attempt < max_retries - 1:
                    print(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                    time.sleep(2)
                continue
                
            # Verify file exists and has minimum size
            if not os.path.exists(output_file):
                print(f"Error: Downloaded file is missing: {output_file}")
                if attempt < max_retries - 1:
                    print(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                    time.sleep(2)
                continue
                
            file_size = os.path.getsize(output_file)
            if file_size < MIN_FILE_SIZE:
                print(f"Error: Downloaded file is too small ({file_size} bytes): {output_file}")
                if attempt < max_retries - 1:
                    print(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                    time.sleep(2)
                continue
                
            print(f"Successfully downloaded: {output_file} ({file_size/1024/1024:.2f} MB)")
            return True
            
        except Exception as e:
            print(f"Error downloading {url}: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                time.sleep(2)
            continue
            
    # If we get here, all retries failed
    print(f"Failed to download {url} after {max_retries} attempts")
    return False

def main():
    parser = argparse.ArgumentParser(description='Extract TikTok links from text files and download videos.')
    parser.add_argument('input_files', nargs='+', help='Input text files to process')
    parser.add_argument('-o', '--output', help='Optional output filename for links (default: links.txt in same directory as input file)')
    parser.add_argument('--download', action='store_true', help='Download videos from tiktokv.us URLs')
    parser.add_argument('--min-size', type=int, default=500, help='Minimum file size in KB (default: 500)')
    
    args = parser.parse_args()
    
    # Update minimum file size if specified
    global MIN_FILE_SIZE
    MIN_FILE_SIZE = args.min_size * 1024
    
    for input_file in args.input_files:
        if not os.path.exists(input_file):
            print(f"Warning: File {input_file} does not exist, skipping...")
            continue
            
        # Get directory of input file and set output path
        input_dir = os.path.dirname(os.path.abspath(input_file))
        if args.output:
            output_file = os.path.join(input_dir, args.output)
        else:
            output_file = os.path.join(input_dir, 'links.txt')
        
        links = extract_links(input_file)
        
        # Write links to output file
        with open(output_file, 'w', encoding='utf-8') as f:
            for link in links:
                f.write(f"{link}\n")
        
        print(f"Extracted {len(links)} links from {input_file} to {output_file}")
        
        # Download videos if requested
        if args.download:
            # Create output directory named after input file (without extension)
            output_dir = os.path.join(input_dir, Path(input_file).stem)
            
            print(f"\nDownloading videos to: {output_dir}")
            successful_downloads = 0
            failed_downloads = []
            
            for i, link in enumerate(links, 1):
                print(f"\nProcessing video {i}/{len(links)}")
                if download_video(link, output_dir, i):
                    successful_downloads += 1
                else:
                    failed_downloads.append(link)
            
            print(f"\nDownload Summary for {input_file}:")
            print(f"- Successfully downloaded: {successful_downloads} videos")
            print(f"- Failed downloads: {len(failed_downloads)} videos")
            
            if failed_downloads:
                failed_file = os.path.join(input_dir, f"{Path(input_file).stem}_failed_downloads.txt")
                with open(failed_file, 'w', encoding='utf-8') as f:
                    for link in failed_downloads:
                        f.write(f"{link}\n")
                print(f"Failed download URLs saved to: {failed_file}")

if __name__ == '__main__':
    main() 