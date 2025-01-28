#!/usr/bin/env python3
"""Script to parse TikTok sound links from a text file and save them to a dedicated links file."""

import os
import re
import sys
import argparse

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

def find_input_file(directory):
    """Recursively search for sound-related files in the given directory and its subdirectories."""
    for root, _, files in os.walk(directory):
        for file in files:
            if 'Sounds' in file and file.endswith('.txt'):
                return os.path.join(root, file)
    return None

def main():
    parser = argparse.ArgumentParser(description='Extract TikTok sound links from input file.')
    parser.add_argument('input_path', help='Input file containing TikTok sound links or directory containing a Sounds file')
    args = parser.parse_args()
    
    # Determine if input is a directory or file
    input_path = os.path.abspath(args.input_path)
    if os.path.isdir(input_path):
        # Search for sound file in the directory and subdirectories
        source_path = find_input_file(input_path)
        if not source_path:
            print(f"Error: Could not find a Sounds file in {input_path} or its subdirectories")
            sys.exit(1)
        base_dir = input_path
    else:
        source_path = input_path
        base_dir = os.path.dirname(input_path)
    
    # Extract links
    links = extract_links(source_path)
    print(f"Found {len(links):,} sound links")
    
    if not links:
        print("No links found in input file")
        sys.exit(1)
    
    # Save links to file
    output_file = os.path.join(base_dir, 'Sound Links.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        for link in links:
            f.write(f"{link}\n")
    print(f"\nSaved {len(links):,} links to: {output_file}")

if __name__ == '__main__':
    main() 