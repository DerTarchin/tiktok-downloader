#!/usr/bin/env python3
"""Script to process TikTok collections and prepare them for downloading."""

import os
import sys
import re
import subprocess
from pathlib import Path

LIKE_FILE = "Like List.txt"
FAVE_FILE = "Favorite Videos.txt"
POST_FILE = "Post.txt"
SOUND_FILE = "Favorite Sounds.txt"

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can import from downloader package
from downloader.utils import filter_links_against_collections

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
        FAVE_FILE, LIKE_FILE, POST_FILE,
        "links.txt", "combined_urls.txt"
    }
    return [f for f in os.listdir(directory) 
            if f.endswith('.txt') 
            and f not in special_files 
            and not f.endswith('.log')
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
        else:
            print("No error output available.")
        sys.exit(1)

def process_files(directory, to_process, should_combine, use_uncategorized_label, begin_downloading):
    """Process the selected files according to user preferences."""
    
    # Create data directory
    data_dir = os.path.join(directory, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Find target files
    target_files = {
        'f': FAVE_FILE,
        'l': LIKE_FILE,
        'p': POST_FILE,
        's': SOUND_FILE
    }
    
    # Get list of files to search for based on what we're processing
    files_to_find = [target_files[key] for key in to_process if key in target_files]
    found_files = find_files(directory, files_to_find)
    
    # Get other collections if needed
    other_collections = []
    collection_paths = []
    if ('f' in to_process or 'l' in to_process) and should_combine:
        other_collections = get_collection_files(directory)
        collection_paths = [os.path.join(directory, f) for f in other_collections]
    
    # Process favorites and likes
    if 'f' in to_process or 'l' in to_process:
        # Process each type separately if not combining
        files_to_process = []
        
        # First check if we have both types and should combine
        have_both = ('f' in to_process and FAVE_FILE in found_files and 
                    'l' in to_process and LIKE_FILE in found_files)
        
        if have_both and should_combine:
            # Combine both files into one
            input_files = []
            input_files.append(found_files[FAVE_FILE])
            input_files.append(found_files[LIKE_FILE])
            files_to_process.append(('combined', input_files))
        else:
            # Process separately
            if 'f' in to_process and FAVE_FILE in found_files:
                files_to_process.append(('f', found_files[FAVE_FILE]))
            if 'l' in to_process and LIKE_FILE in found_files:
                files_to_process.append(('l', found_files[LIKE_FILE]))
        
        # Process each file or combination
        for file_type, input_file in files_to_process:
            # Determine output name
            if file_type == 'combined':
                output_name = "Uncategorized Faves & Likes.txt" if use_uncategorized_label else "Faves & Likes.txt"
            else:
                base = "Uncategorized " if use_uncategorized_label and file_type == 'f' else ""
                base += "Favorites" if file_type == 'f' else "Likes"
                output_name = f"{base}.txt"
            
            output_file = os.path.join(data_dir, output_name)
            
            # Parse URLs
            if file_type == 'combined':
                run_script('parse_urls.py', *input_file)
                combined_file = os.path.join(os.path.dirname(input_file[0]), 'combined_urls.txt')
            else:
                run_script('parse_urls.py', input_file)
                combined_file = os.path.join(os.path.dirname(input_file), 'combined_urls.txt')
            
            if os.path.exists(combined_file):
                # If there are other collections, filter out duplicates
                if collection_paths:
                    with open(combined_file, 'r') as f:
                        links = [line.strip() for line in f if line.strip()]
                    
                    filtered_links = filter_links_against_collections(links, collection_paths)
                    
                    # Write filtered links to output file
                    with open(output_file, 'w') as f:
                        f.write('\n'.join(filtered_links))
                        if filtered_links:  # Add final newline if file is not empty
                            f.write('\n')
                    
                    # Print stats
                    print(f"Filtered {len(links) - len(filtered_links):,} duplicates from collections")
                    print(f"Remaining links: {len(filtered_links):,}")
                else:
                    os.rename(combined_file, output_file)
                
                # For combined files, dedupe the output file
                if file_type == 'combined':
                    run_script('dedupe_links.py', os.path.dirname(output_file))
                
                # Check file size and split if needed
                file_size = sum(1 for _ in open(output_file))
                if file_size > 1000:
                    run_script('split_links.py', output_file, '--max-lines', '500')
                    # Move split files to main directory and ensure correct naming
                    base_name = os.path.splitext(output_file)[0]
                    for file in os.listdir(data_dir):
                        if file.startswith(os.path.basename(base_name)) and "(Part" in file:
                            # Rename to match the correct format
                            new_name = file.replace(os.path.basename(base_name), base_name.split('/')[-1])
                            os.rename(
                                os.path.join(data_dir, file),
                                os.path.join(directory, new_name)
                            )
                else:
                    # Copy file to main directory
                    with open(output_file, 'r') as src, open(os.path.join(directory, output_name), 'w') as dst:
                        dst.write(src.read())
                
                # Clean up combined_urls.txt if it still exists
                if os.path.exists(combined_file):
                    os.remove(combined_file)
    
    # Process sounds
    if 's' in to_process and SOUND_FILE in found_files:
        output_file = os.path.join(data_dir, 'All Saved Sounds.txt')
        sound_file = found_files[SOUND_FILE]
        print(f"\nProcessing sounds from: {sound_file}")
        
        # Parse URLs first, writing directly to output file
        run_script('parse_urls.py', sound_file, '--output', output_file, capture_output=False)
        
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                num_links = sum(1 for _ in f)
            print(f"{num_links:,} sounds found.")
    
    # Process posts
    if 'p' in to_process and POST_FILE in found_files:
        output_file = os.path.join(data_dir, 'All Personal Posts.txt')
        post_file = found_files[POST_FILE]
        print(f"\nProcessing posts from: {post_file}")
        
        # Parse URLs first, writing directly to output file
        run_script('parse_urls.py', post_file, '--output', output_file, capture_output=False)
        
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                num_links = sum(1 for _ in f)
            print(f"{num_links:,} posts found.")

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
    valid_inputs = {'f', 'l', 'p', 's'}
    prompt = "Which to parse: Favorites (F), Likes (L), Personal Posts (P), Sounds (S)\n" + \
             "Enter choices: "
    
    response = get_input(prompt)
    to_process = set()
    
    # Parse response
    for char in response:
        if char.lower() in valid_inputs:
            to_process.add(char.lower())
    
    if not to_process:
        print("No valid options selected")
        sys.exit(1)
    
    # Additional questions based on selections
    should_combine = False
    if ('f' in to_process and 'l' in to_process) or \
       (('f' in to_process or 'l' in to_process) and get_collection_files(directory)):
        response = get_input(
            "Do you want to avoid downloading duplicates across Faves, Likes and other collections? (y/n): ",
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
            f'Do you want to begin downloading {" and ".join(what)} now? (y/n): ',
            valid_options={'y', 'n'}
        )
        begin_downloading = response == 'y'
    
    # Process the files
    process_files(directory, to_process, should_combine, use_uncategorized_label, begin_downloading)

    # Run count script to show number of videos to download
    if 'l' in to_process or 'f' in to_process:
        run_script('count_videos_to_download.py', directory, capture_output=False)

    # begin downloading sounds
    if 's' in to_process and begin_downloading:
        run_script('download_sounds.py', directory, capture_output=False)

    # Run download_posts.py if downloading is requested
    if 'p' in to_process and begin_downloading:
        run_script('download_posts.py', directory, capture_output=False)

if __name__ == '__main__':
    main() 