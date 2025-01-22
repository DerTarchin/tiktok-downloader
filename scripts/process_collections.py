#!/usr/bin/env python3
"""Script to process TikTok collections and prepare them for downloading."""

import os
import sys
import re
import subprocess
from pathlib import Path

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def get_input(prompt, valid_options=None, case_sensitive=False):
    """Get user input with validation."""
    while True:
        response = input(prompt).strip()
        if not case_sensitive:
            response = response.lower()
        
        if valid_options is None:
            return response
        
        if response in valid_options:
            return response
        
        print(f"Invalid input. Please choose from: {', '.join(valid_options)}")

def find_files(directory, target_files):
    """Find specified files in directory and subdirectories."""
    found_files = {}
    for root, _, files in os.walk(directory):
        for file in files:
            if file in target_files:
                found_files[file] = os.path.join(root, file)
    return found_files

def get_collection_files(directory):
    """Get all .txt files in the top-level directory that aren't special files."""
    special_files = {
        "Favorite Videos.txt", "Liked List.txt", "Posts.txt",
        "links.txt", "combined_urls.txt", "download_success.log",
        "failed_downloads.log"
    }
    return [f for f in os.listdir(directory) 
            if f.endswith('.txt') 
            and f not in special_files 
            and os.path.isfile(os.path.join(directory, f))]

def run_script(script_name, *args, capture_output=True):
    """Run a Python script with arguments."""
    cmd = [sys.executable, os.path.join(project_root, 'scripts', script_name)] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=capture_output, text=True, check=True)
        return result.stdout if capture_output else None
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}: {e}")
        if e.stderr:
            print(f"Error output:\n{e.stderr}")
        sys.exit(1)

def process_files(directory, to_process, should_combine, use_uncategorized_label, begin_downloading):
    """Process the selected files according to user preferences."""
    
    # Create data directory
    data_dir = os.path.join(directory, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Find target files
    target_files = {
        'f': "Favorite Videos.txt",
        'l': "Liked List.txt",
        'p': "Posts.txt"
    }
    
    found_files = find_files(directory, [target_files[key] for key in to_process if key in target_files])
    
    # Get other collections if needed
    other_collections = []
    if ('f' in to_process or 'l' in to_process) and should_combine:
        other_collections = get_collection_files(directory)
    
    # Process favorites and likes
    if 'f' in to_process or 'l' in to_process:
        input_files = []
        if 'f' in to_process and target_files['f'] in found_files:
            input_files.append(found_files[target_files['f']])
        if 'l' in to_process and target_files['l'] in found_files:
            input_files.append(found_files[target_files['l']])
        
        if input_files:
            # Determine output name
            if len(input_files) > 1 and should_combine:
                output_name = "Uncategorized Faves & Likes.txt" if use_uncategorized_label else "Faves & Likes.txt"
            else:
                base = "Uncategorized " if use_uncategorized_label else ""
                base += "Favorites.txt" if 'f' in to_process else "Likes.txt"
                output_name = base
            
            output_file = os.path.join(data_dir, output_name)
            
            # Parse URLs
            run_script('parse_urls.py', *input_files)
            
            # Move and rename the combined file
            combined_file = os.path.join(os.path.dirname(input_files[0]), 'combined_urls.txt')
            if os.path.exists(combined_file):
                os.rename(combined_file, output_file)
                
                # If there are other collections, ensure uniqueness
                if other_collections:
                    collection_paths = [os.path.join(directory, f) for f in other_collections]
                    run_script('dedupe_links.py', directory)
                
                # Check file size and split if needed
                file_size = sum(1 for _ in open(output_file))
                if file_size > 1000:
                    run_script('split_links.py', output_file, '--max-lines', '1000')
                    # Move split files to main directory
                    base_name = os.path.splitext(output_file)[0]
                    for file in os.listdir(data_dir):
                        if file.startswith(os.path.basename(base_name)) and "(Part" in file:
                            os.rename(
                                os.path.join(data_dir, file),
                                os.path.join(directory, file)
                            )
                else:
                    # Copy file to main directory
                    with open(output_file, 'r') as src, open(os.path.join(directory, output_name), 'w') as dst:
                        dst.write(src.read())
    
    # Process sounds
    if 's' in to_process:
        # Look for sound links in favorites and likes files
        potential_files = []
        if target_files['f'] in found_files:
            potential_files.append(found_files[target_files['f']])
        if target_files['l'] in found_files:
            potential_files.append(found_files[target_files['l']])
        
        if potential_files:
            for file in potential_files:
                output_file = os.path.join(data_dir, 'All Saved Sounds.txt')
                run_script('download_sounds.py', file, '--download' if begin_downloading else '')
                
                # Move links file to data directory
                links_file = os.path.join(os.path.dirname(file), 'links.txt')
                if os.path.exists(links_file):
                    with open(links_file, 'r') as src:
                        with open(output_file, 'a') as dst:
                            dst.write(src.read())
                    os.remove(links_file)
    
    # Process posts
    if 'p' in to_process and target_files['p'] in found_files:
        output_file = os.path.join(data_dir, 'All Personal Posts.txt')
        run_script('extract_post_links.py', found_files[target_files['p']], 
                  '--download' if begin_downloading else '')
        
        # Move links file to data directory
        links_file = os.path.join(os.path.dirname(found_files[target_files['p']]), 'links.txt')
        if os.path.exists(links_file):
            os.rename(links_file, output_file)

def main():
    # Get directory path
    if len(sys.argv) > 1:
        directory = os.path.abspath(sys.argv[1])
    else:
        directory = os.getcwd()
    
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a directory")
        sys.exit(1)
    
    # Get which collections to process
    valid_inputs = {'f', 'l', 'p', 's', 'F', 'L', 'P', 'S'}
    prompt = "Which to parse: Favorites (F), Likes (L), Personal Posts (P), Sounds (S)\n" + \
             "Enter space/comma separated values (e.g., 'F L P' or 'fl' or 'L,p'): "
    
    response = get_input(prompt)
    to_process = set()
    
    # Parse response
    for char in re.split(r'[,\s]+', response):
        if char.upper() in valid_inputs:
            to_process.add(char.lower())
    
    if not to_process:
        print("No valid options selected")
        sys.exit(1)
    
    # Additional questions based on selections
    should_combine = False
    if ('f' in to_process and 'l' in to_process) or \
       (('f' in to_process or 'l' in to_process) and get_collection_files(directory)):
        response = get_input(
            "Do you want to avoid downloading duplicates across Faves and Likes and other collections? (y/n): ",
            valid_options={'y', 'n'}
        )
        should_combine = response == 'y'
    
    use_uncategorized_label = False
    if 'f' in to_process:
        response = get_input(
            'Do you want to use the word "Uncategorized"? (y/n): ',
            valid_options={'y', 'n'}
        )
        use_uncategorized_label = response == 'y'
    
    begin_downloading = False
    if 's' in to_process or 'p' in to_process:
        what = []
        if 's' in to_process:
            what.append('Sounds')
        if 'p' in to_process:
            what.append('Posts')
        response = get_input(
            f'Do you want to begin downloading {" AND ".join(what)} now? (y/n): ',
            valid_options={'y', 'n'}
        )
        begin_downloading = response == 'y'
    
    # Process the files
    process_files(directory, to_process, should_combine, use_uncategorized_label, begin_downloading)

if __name__ == '__main__':
    main() 