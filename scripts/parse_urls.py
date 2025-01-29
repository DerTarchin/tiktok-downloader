#!/usr/bin/env python3
"""Script to parse TikTok links from text files and save them to a dedicated links file."""

import os
import re
import sys
import argparse

def extract_links(input_file):
    """Extract TikTok links from the input file."""
    links = []
    
    # Determine processing mode based on filename
    filename = os.path.basename(input_file)
    is_sound_file = 'Sound' in filename
    # is_post_file = 'Post' in filename
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if is_sound_file:
        # Process sound links
        pattern = r'Sound Link: (https://[^\s]+)'
    else:
        # Process video/post links (both use same pattern)
        pattern = r'Link: (https://[^\s]+)'
    
    matches = re.finditer(pattern, content)
    links.extend(match.group(1) for match in matches)
    
    # If no structured links found, try to find any TikTok URLs
    if not links:
        url_pattern = r'https://(?:www\.)?(?:vm\.)?tiktok\.com/[^\s)"]+'
        url_matches = re.finditer(url_pattern, content)
        links.extend(match.group(0) for match in url_matches)
        
    return links

def find_input_file(directory):
    """Recursively search for relevant files in the given directory and its subdirectories."""
    target_files = ['Sounds.txt', 'Like List.txt', 'Favorite Videos.txt', 'Post.txt']
    for root, _, files in os.walk(directory):
        for file in files:
            if any(target in file for target in target_files):
                return os.path.join(root, file)
    return None

def main():
    parser = argparse.ArgumentParser(description='Extract TikTok links from input file.')
    parser.add_argument('input_paths', nargs='+', help='Input files containing TikTok links or directory containing target files')
    parser.add_argument('--output', help='Output file path (default: combined_urls.txt in same directory as input)')
    args = parser.parse_args()
    
    all_links = set()  # Use set to automatically dedupe
    base_dir = None
    
    for input_path in args.input_paths:
        # Determine if input is a directory or file
        input_path = os.path.abspath(input_path)
        if os.path.isdir(input_path):
            # Search for relevant file in the directory and subdirectories
            source_path = find_input_file(input_path)
            if not source_path:
                print(f"Warning: Could not find a target file in {input_path} or its subdirectories")
                continue
            if base_dir is None:
                base_dir = input_path
        else:
            source_path = input_path
            if base_dir is None:
                base_dir = os.path.dirname(input_path)
        
        # Extract links
        links = extract_links(source_path)
        all_links.update(links)
        
        # Determine file type for output message
        filename = os.path.basename(source_path)
        if 'Sound' in filename:
            file_type = 'sound'
        elif 'Post' in filename:
            file_type = 'post'
        else:
            file_type = 'video'
        print(f"Found {len(links):,} {file_type} links in {filename}")
    
    if not all_links:
        print("No links found in input files")
        sys.exit(1)
    
    # Determine output file path
    output_file = args.output if args.output else os.path.join(base_dir, 'combined_urls.txt')
    
    # Save links to file
    with open(output_file, 'w', encoding='utf-8') as f:
        for link in sorted(all_links):  # Sort for consistency
            f.write(f"{link}\n")
    print(f"\nSaved {len(all_links):,} unique links to: {output_file}")

if __name__ == '__main__':
    main() 