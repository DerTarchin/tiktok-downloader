"""Utility functions for TikTok downloader."""

import os
import sys
import re
from urllib.parse import urlparse
import time
import subprocess

SPLIT_SIZE = 500  # Maximum number of URLs per split file


def clean_filename(name):
    """
    Clean a filename by removing invalid characters and limiting length while preserving extension and ID.
    
    Args:
        name: Original filename to clean
        
    Returns:
        str: Cleaned filename safe for use in filesystem
    """
    # First, replace any invalid Unicode characters and control characters
    name = ''.join(char for char in name if ord(char) < 65536 and ord(char) >= 32 and char != '\ufff6')
    name = name.encode('ascii', 'ignore').decode('ascii')
    
    # Remove other invalid filename characters
    invalid_chars = '<>:"/\\|?*\x00-\x1f\x7f'
    name = ''.join(char for char in name if char not in invalid_chars)
    
    # Replace empty result with empty string
    if not name.strip():
        name = ""
        return name
    
    # Remove leading periods
    while name.startswith('.'):
        name = name[1:]
        
    return name

def extract_video_id(url):
    """
    Extract video ID from TikTok URL, handling both video and photo formats.
    
    Args:
        url: TikTok URL to extract ID from
        
    Returns:
        str: Video/photo ID if found, None otherwise
    """
    # Remove any leading @ symbol first
    url = url.lstrip('@')
    match = re.search(r'/video/(\d+)|/photo/(\d+)', url)
    if match:
        # Return first matching group (video ID) or second matching group (photo ID)
        return match.group(1) if match.group(1) else match.group(2)
    return None

def get_username_from_path(path):
    """Extract username from path by getting the parent directory name"""
    return os.path.basename(os.path.dirname(path))

def get_filename_suffix(url):
    """
    Get video ID suffix for filename.
    
    Args:
        url: URL to extract ID from
        
    Returns:
        str: Video ID suffix with space prefix if ID found, empty string otherwise
    """
    video_id = extract_video_id(url)
    return f" {video_id}" if video_id else "" 

def get_highest_group_number(input_path, all_saves_name):
    """
    Find the highest existing group number in the directory.
    
    Args:
        input_path: Directory to search in
        all_saves_name: Base name for group files
        
    Returns:
        int: Highest group number found
    """
    highest_group = 0
    for file in os.listdir(input_path):
        if file.startswith(f"{all_saves_name} (Group ") and file.endswith(").txt"):
            try:
                group_num = int(file.split("Group ")[1].split(")")[0])
                highest_group = max(highest_group, group_num)
            except (ValueError, IndexError):
                continue
    return highest_group

def write_and_process_urls(output_file, urls_to_add, file_handler, selenium_handler, 
                         yt_dlp_handler, sync_handler, group_num=None, total_files=None, skip_private=False):
    """
    Write URLs to file and process them.
    
    Args:
        output_file: Path to write URLs to
        urls_to_add: List of URLs to add
        file_handler: FileHandler instance
        selenium_handler: SeleniumHandler instance
        yt_dlp_handler: YtDlpHandler instance
        sync_handler: SyncHandler instance
        group_num: Optional group number for progress display
        total_files: Optional total number of files for progress display
        skip_private: Whether to skip known private videos
    """
    # Get existing URLs if file exists
    existing_urls = []
    if os.path.exists(output_file):
        with open(output_file, "r") as f:
            existing_urls = [url.strip() for url in f.readlines() if url.strip()]
    
    # Only add URLs that don't exist in file
    urls_to_write = [url for url in urls_to_add 
                    if not any(extract_video_id(url) == extract_video_id(existing_url)
                             for existing_url in existing_urls)]
    
    if urls_to_write:
        with open(output_file, "w") as f:
            f.write("\n".join(existing_urls + urls_to_write))
        
        # Add retry logic with exponential backoff
        max_retries = 3
        retry_delay = 30  # Initial delay in seconds
        
        for attempt in range(max_retries):
            try:
                from .file_processor import process_file
                if group_num is not None:
                    process_file(output_file, group_num, total_files,
                              file_handler, selenium_handler, yt_dlp_handler, sync_handler, skip_private=skip_private)
                else:
                    process_file(output_file, total_files, total_files,
                              file_handler, selenium_handler, yt_dlp_handler, sync_handler, skip_private=skip_private)
                break  # Success - exit retry loop
                
            except Exception as e:
                if "HTTP Error 429" in str(e) or "Too Many Requests" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        print(f"\nRate limit detected. Waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
                        continue
                raise  # Re-raise the exception if we've exhausted retries

def split_into_groups(urls, input_path, file_handler, start_group):
    """
    Split URLs into group files and return the file paths.
    Preserves existing group files and their contents.
    Creates missing group files if needed.
    Ensures no duplicates exist in source files before adding to groups.
    
    Args:
        urls: List of URLs to split into groups
        input_path: Directory to create group files in
        file_handler: FileHandler instance
        start_group: Starting group number
        
    Returns:
        list: Paths to all group files (existing + new)
    """
    print(f"\nAnalyzing existing groups and URLs...")
    print(f"Total URLs to process: {len(urls):,}")
    
    group_files = []
    existing_urls = set()
    existing_video_ids = set()  # New set to store extracted video IDs
    
    # First, collect URLs from existing group files and map them to their groups
    group_to_urls = {}
    print("Scanning for existing group files...")
    
    # First check source files for duplicates
    print("Checking source files for duplicates...")
    source_video_ids = set()
    text_files = [f for f in os.listdir(input_path) 
                 if f.endswith(".txt") 
                 and not f.startswith(file_handler.error_prefix)
                 and not f.startswith(file_handler.all_saves_name)
                 and f != "Favorite Videos (URLs).txt"]
    
    for source_file in text_files:
        source_path = os.path.join(input_path, source_file)
        with open(source_path, 'r') as f:
            source_links = [url.strip() for url in f.readlines() if url.strip()]
            source_video_ids.update(extract_video_id(url) for url in source_links)
    
    print(f"Found {len(source_video_ids):,} existing video IDs in source files")
    
    # Now check existing group files
    for file in os.listdir(input_path):
        if file.startswith(f"{file_handler.all_saves_name} (Group ") and file.endswith(").txt"):
            file_path = os.path.join(input_path, file)
            try:
                group_num = int(file.split("Group ")[1].split(")")[0])
                group_to_urls[group_num] = set()
                with open(file_path, 'r') as f:
                    file_urls = [url.strip() for url in f.readlines() if url.strip()]
                    group_to_urls[group_num].update(file_urls)
                    existing_urls.update(file_urls)
                    # Extract and store video IDs
                    existing_video_ids.update(
                        vid for url in file_urls 
                        if (vid := extract_video_id(url)) is not None
                    )
                group_files.append(file_path)
            except (ValueError, IndexError):
                print(f"Skipping invalid group file: {file}")
                continue
    
    print(f"Found {len(group_files):,} existing group files")
    print(f"Found {len(existing_urls):,} existing URLs")
    
    # Find URLs that aren't in any existing group or source file
    print("Checking for new URLs...")
    new_urls = []
    
    for url in urls:
        video_id = extract_video_id(url)
        # Check against both group files and source files
        is_new = video_id not in existing_video_ids and video_id not in source_video_ids
        if is_new:
            new_urls.append(url)
    print(f"Found {len(new_urls):,} new URLs to process")

    if not new_urls and group_files:
        print("No new URLs to process - using existing group files")
        return sorted(group_files)
    
    # Find the highest existing group number and any gaps in numbering
    highest_group = 0
    expected_groups = set()
    if group_to_urls:
        highest_group = max(group_to_urls.keys())
        expected_groups = set(range(1, highest_group + 1))
        missing_groups = expected_groups - set(group_to_urls.keys())
        if missing_groups:
            print(f"Found gaps in group numbering: missing groups {sorted(missing_groups)}")
    
    # Calculate how many groups we need for new URLs
    total_groups_needed = (len(new_urls) + SPLIT_SIZE - 1) // SPLIT_SIZE
    print(f"Need {total_groups_needed:,} groups for new URLs (max {SPLIT_SIZE} URLs per group)")
    
    # If we have missing groups, use those numbers first
    if group_to_urls:
        missing_groups = expected_groups - set(group_to_urls.keys())
        available_group_nums = sorted(missing_groups) + list(range(highest_group + 1, highest_group + total_groups_needed + 1))
        print(f"Will use group numbers: {available_group_nums}")
    else:
        available_group_nums = list(range(1, total_groups_needed + 1))
        print(f"Creating new groups numbered 1 to {total_groups_needed:,}")
    
    # Create new group files for new URLs
    print(f"\nCreating group files (with {SPLIT_SIZE:,} each)...")
    for i in range(0, len(new_urls), SPLIT_SIZE):
        group_num = available_group_nums[i // SPLIT_SIZE]
        group_urls = new_urls[i:i + SPLIT_SIZE]
        group_file = os.path.join(input_path, f"{file_handler.all_saves_name} (Group {group_num}).txt")
        
        # Write URLs to group file
        with open(group_file, "w") as f:
            f.write("\n".join(group_urls))
        
        if group_file not in group_files:
            group_files.append(group_file)
    
    print(f"Finished creating {len(group_files):,} total group files")
    return sorted(group_files)  # Return all files (existing + new) in sorted order

def remove_duplicates_from_groups(source_file, directory, dry_run=False):
    """
    Remove links from uncategorized group files if they exist in the source file.
    
    Args:
        source_file (str): Path to the source file containing links
        directory (str): Directory containing the group files to check
        dry_run (bool): If True, only simulate the changes without writing to files
    
    Returns:
        int: Number of links removed from group files
    """
    # Read source file links
    with open(source_file, 'r') as f:
        source_links = set(url.strip() for url in f.readlines() if url.strip())
        source_video_ids = set(extract_video_id(url) for url in source_links)

    # Print which file we're processing
    print(f"\nProcessing source file: {os.path.basename(source_file)}")
    print(f"Found {len(source_links):,} links in source file")
    
    # Find all group files
    group_files = [f for f in os.listdir(directory) 
                  if f.endswith('.txt') and ' (Group ' in f and not f.startswith('[error')]
    
    if not group_files:
        print("No group files found.")
        return 0
    
    print(f"Processing {len(group_files):,} group files...")
    total_removed = 0
    
    for group_file in group_files:
        group_path = os.path.join(directory, group_file)
        with open(group_path, 'r') as f:
            group_links = [url.strip() for url in f.readlines() if url.strip()]
        
        # Filter out links that exist in source file
        filtered_links = []
        removed_count = 0
        
        for link in group_links:
            video_id = extract_video_id(link)
            if video_id not in source_video_ids:
                filtered_links.append(link)
            else:
                removed_count += 1
        
        if removed_count > 0:
            print(f"Removing {removed_count:,} duplicates from {group_file}")
            print("Removed IDs:")
            for link in group_links:
                video_id = extract_video_id(link)
                if video_id in source_video_ids:
                    print(f"\t{video_id}")
            
            if not dry_run:
                # Write the filtered links back to the group file
                with open(group_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(filtered_links))
            total_removed += removed_count
            
            action = "Would remove" if dry_run else "Removed"
            print(f"{action} {removed_count} links from {group_file}")
    
    print(f"Total links removed: {total_removed}")
    return total_removed

def print_final_summary(input_path, file_handler):
    """Print final summary statistics after processing is complete"""
    # Count successfully downloaded videos (deduped by video ID)
    success_count = 0
    unique_video_ids = set()
    if os.path.exists(file_handler.success_log_path):
        with open(file_handler.success_log_path, 'r') as f:
            for line in f:
                if line.strip():
                    video_id = extract_video_id(line.strip())
                    if video_id:
                        unique_video_ids.add(video_id)
            success_count = len(unique_video_ids)
    
    # Count failed and private videos from error logs
    total_private = 0
    total_failed = 0
    
    # Get all error log files
    error_files = []
    if os.path.isfile(input_path):
        error_file = file_handler.get_error_log_path(input_path)
        if os.path.exists(error_file):
            error_files.append(error_file)
    else:
        for file in os.listdir(input_path):
            if file.startswith(file_handler.error_prefix):
                error_files.append(os.path.join(input_path, file))
    
    # Process each error log
    for error_file in error_files:
        if os.path.exists(error_file):
            with open(error_file, 'r') as f:
                for line in f:
                    if line.strip():
                        if line.strip().endswith(" (private)"):
                            total_private += 1
                        else:
                            total_failed += 1
    
    # Get total size of remote directory for this user
    total_size = 0
    try:
        username = os.path.basename(input_path if os.path.isdir(input_path) 
                                  else os.path.dirname(input_path))
        remote_path = f"gdrive:/TikTok Archives/{username}"
        
        result = subprocess.run(['rclone', 'size', remote_path], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            # Extract total size from output and convert to GB
            size_lines = [line for line in result.stdout.split('\n') 
                         if 'Total size:' in line]
            if size_lines:
                # Extract bytes value and convert to GB
                bytes_str = size_lines[0].split('(')[1].split()[0]
                bytes_val = float(bytes_str)
                gb_val = round(bytes_val / (1024**3))  # Convert bytes to GB and round
                total_size = f"{gb_val}GB"
            else:
                total_size = "No size information found"
        else:
            total_size = f"rclone error (code {result.returncode})"
    except Exception as e:
        total_size = f"Unable to determine: {str(e)}"
    
    # Convert total_size to a float for comparison
    try:
        size_value = float(total_size.replace("GB", "").strip())
    except ValueError:
        size_value = 0  # Default to 0 if conversion fails

    # Create summary text
    summary_text = "\n" + "="*50 + "\n"
    summary_text += "FINAL SUMMARY\n"
    summary_text += "="*50 + "\n"
    summary_text += f"Total videos downloaded: {success_count:,}\n"
    summary_text += f"Total private videos: {total_private:,} (i can't downlaod these, sorry)\n"
    summary_text += f"Total failed: {total_failed:,}\n"
    summary_text += f"Total size: {total_size}\n"
    summary_text += "="*50 + "\n"
    
    # Print to console
    print(summary_text)
    
    # Save to file (in current directory instead of parent)
    summary_path = os.path.join(input_path if os.path.isdir(input_path) 
                               else os.path.dirname(input_path), "summary.log")
    with open(summary_path, 'w') as f:
        f.write(summary_text)
    
    print("\n --- message template --- \n")
    print("Great news! Your videos are ready 😊🎉")
    # ADD SUMMARY HERE
    print("Here's the temporary link to them in google drive:")
    print("\n --- LINK HERE --- \n")
    print("You can download them from there and save them to your computer. Please do so as soon as you can, and let me know when you're done, because i'd like to have that space available again to help other TikTokers")
    if size_value > 3:
        print("And i suggest you download folder-by-folder instead of downloading the entire archive at once, because it's easier to manage smaller downloads at a time")
        print("Here's where you can find the download buttons:")
        print("https://imgur.com/a/wRT1Zaw")
    