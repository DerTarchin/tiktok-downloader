"""Utility functions for TikTok downloader."""

import os
import re
from urllib.parse import urlparse
import time
import subprocess
import sys

SPLIT_SIZE = 500  # Maximum number of URLs per split file
FILE_SIZE_THRESHOLD_KB = 50 # Minimum file size in KB
MAX_FILENAME_LENGTH = 70


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
    
    # Remove newline characters
    name = name.replace('\n', '').replace('\r', '')
    
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
                          yt_dlp_handler, sync_handler, group_num=None, total_files=None, 
                          skip_private=False, skip_sync=False, verbose=False, max_concurrent=3):
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
        skip_sync: Whether to skip syncing the processed folder
        verbose: Whether to print verbose output
        max_concurrent: Maximum number of concurrent yt-dlp downloads
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
                              file_handler, selenium_handler, yt_dlp_handler, sync_handler, 
                              skip_private=skip_private, skip_sync=skip_sync, verbose=verbose,
                              max_concurrent=max_concurrent)
                else:
                    process_file(output_file, total_files, total_files,
                              file_handler, selenium_handler, yt_dlp_handler, sync_handler, 
                              skip_private=skip_private, skip_sync=skip_sync, verbose=verbose,
                              max_concurrent=max_concurrent)
                break  # Success - exit retry loop
                
            except Exception as e:
                if "HTTP Error 429" in str(e) or "Too Many Requests" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        print(f"\nRate limit detected. Waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
                        continue
                raise  # Re-raise the exception if we've exhausted retries

def split_into_groups(urls, input_path, file_handler, start_group, verbose=False):
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
        verbose: Whether to print verbose output
        
    Returns:
        list: Paths to all group files (existing + new)
    """
    if verbose:
        print(f"\nAnalyzing existing groups and URLs...")
        print(f"Total URLs to process: {len(urls):,}")
    
    group_files = []
    existing_urls = set()
    existing_video_ids = set()  # New set to store extracted video IDs
    
    # First, collect URLs from existing group files and map them to their groups
    group_to_urls = {}
    if verbose:
        print("Scanning for existing group files...")
    
    # First check source files for duplicates
    if verbose:
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
    
    if verbose:
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
                if verbose:
                    print(f"Skipping invalid group file: {file}")
                continue
    
    if verbose:
        print(f"Found {len(group_files):,} existing group files")
        print(f"Found {len(existing_urls):,} existing URLs")
    
    # Find URLs that aren't in any existing group or source file
    if verbose:
        print("Checking for new URLs...")
    new_urls = []
    
    for url in urls:
        video_id = extract_video_id(url)
        # Check against both group files and source files
        is_new = video_id not in existing_video_ids and video_id not in source_video_ids
        if is_new:
            new_urls.append(url)
    if verbose:
        print(f"Found {len(new_urls):,} new URLs to process")

    if not new_urls and group_files:
        if verbose:
            print("No new URLs to process - using existing group files")
        return sorted(group_files)
    
    # Find the highest existing group number and any gaps in numbering
    highest_group = 0
    expected_groups = set()
    if group_to_urls:
        highest_group = max(group_to_urls.keys())
        expected_groups = set(range(1, highest_group + 1))
        missing_groups = expected_groups - set(group_to_urls.keys())
        if missing_groups and verbose:
            print(f"Found gaps in group numbering: missing groups {sorted(missing_groups)}")
    
    # Calculate how many groups we need for new URLs
    total_groups_needed = (len(new_urls) + SPLIT_SIZE - 1) // SPLIT_SIZE
    if verbose:
        print(f"Need {total_groups_needed:,} groups for new URLs (max {SPLIT_SIZE} URLs per group)")
    
    # If we have missing groups, use those numbers first
    if group_to_urls:
        missing_groups = expected_groups - set(group_to_urls.keys())
        available_group_nums = sorted(missing_groups) + list(range(highest_group + 1, highest_group + total_groups_needed + 1))
        if verbose:
            print(f"Will use group numbers: {available_group_nums}")
    else:
        available_group_nums = list(range(1, total_groups_needed + 1))
        if verbose:
            print(f"Creating new groups numbered 1 to {total_groups_needed:,}")
    
    # Create new group files for new URLs
    if verbose:
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
    
    if verbose:
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
    username = os.path.basename(input_path if os.path.isdir(input_path) 
                              else os.path.dirname(input_path))
    remote_path = f"gdrive:/TikTok Archives/{username}"
    
    # Generate shareable link for Google Drive
    drive_link = ""
    try:
        # Run rclone link command to get a shareable link
        result = subprocess.run(['rclone', 'link', remote_path], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            drive_link = result.stdout.strip()
        else:
            drive_link = "Unable to generate link (please contact support)"
    except Exception as e:
        drive_link = f"Unable to generate link: {str(e)}"
    
    # Get size information
    try:
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
    
    # Create clean stats summary without visual flair
    stats_summary = f"Total videos downloaded: {success_count:,}\n"
    if total_private > 0:
        stats_summary += f"Total private videos: {total_private:,} (I can't download these, sorry)\n"
    else:
        stats_summary += "Total private videos: 0\n"
    stats_summary += f"Total failed: {total_failed:,}\n"
    stats_summary += f"Total size: {total_size}"
    
    # Create the new user-friendly message
    friendly_message = "\nGreat news! Your videos are ready 😊🎉\n"
    friendly_message += "Here's the TEMPORARY link to them in google drive, IT WILL NOT EXIST IN A DAY OR SO unless you need more time to download them:\n\n"
    friendly_message += f"{drive_link}\n\n"
    friendly_message += f"{stats_summary}\n\n"
    friendly_message += "You can download them from there and save them to your computer. Please do so as soon as you can, "
    friendly_message += "and let me know when you're done, because I'd like to have that space available again to help other TikTokers\n\n"
    friendly_message += "And I suggest you download folder-by-folder instead of downloading the entire archive at once, "
    friendly_message += "because it's easier to manage smaller downloads at a time.\n\n"
    friendly_message += "Here's where you can find the download buttons:\n"
    friendly_message += "https://imgur.com/a/wRT1Zawa\n"
    
    # Print to console
    print(friendly_message)
    
    # Also save the original detailed summary for logging purposes
    detailed_summary = "\n" + "="*50 + "\n"
    detailed_summary += "FINAL SUMMARY\n"
    detailed_summary += "="*50 + "\n"
    detailed_summary += f"Total videos downloaded: {success_count:,}\n"
    if total_private > 0:
        detailed_summary += f"Total private videos: {total_private:,} (I can't download these, sorry)\n"
    else:
        detailed_summary += "Total private videos: 0\n"
    detailed_summary += f"Total failed: {total_failed:,}\n"
    detailed_summary += f"Total size: {total_size}\n"
    detailed_summary += f"Google Drive link: {drive_link}\n"
    detailed_summary += "="*50 + "\n"
    
    # Save to file (in current directory instead of parent)
    summary_path = os.path.join(input_path if os.path.isdir(input_path) 
                               else os.path.dirname(input_path), "summary.log")
    with open(summary_path, 'w') as f:
        f.write(detailed_summary)
        f.write("\n\nUser-friendly message:\n\n")
        f.write(friendly_message)

def split_urls_by_type(urls):
    """
    Split URLs into video and photo URLs.
    
    Args:
        urls: Iterable of URLs to split
        
    Returns:
        tuple: (video_urls, photo_urls) where each is a set of URLs
    """
    photo_urls = {url for url in urls if "/photo/" in url}
    video_urls = {url for url in urls if url not in photo_urls}
    return video_urls, photo_urls

def get_output_folder(file_path):
    """
    Get the output folder path for a given input file.
    
    Args:
        file_path: Path to input file
        
    Returns:
        str: Path to output folder
    """
    # Get collection name from file name, handling multiple extensions
    base_name = os.path.basename(file_path)
    collection_name = base_name.split('.txt')[0]
    while collection_name.endswith('.'):
        collection_name = collection_name[:-1]
    return os.path.join(os.path.dirname(file_path), collection_name)

def get_error_file_path(output_folder):
    """
    Get the error log file path for a given output folder.
    
    Args:
        output_folder: Path to output folder
        
    Returns:
        str: Path to error log file
    """
    collection_name = os.path.basename(output_folder)
    return os.path.join(os.path.dirname(output_folder), f"[error log] {collection_name}.txt")
    
def log_worker(worker_type, worker_num, message):
    """Log a message for a worker."""
    print(f"{time.strftime('%I:%M:%S')} [{worker_type}-{'0' if worker_num < 10 else ''}{worker_num}] {message}")

def is_file_size_valid(file_size_in_bytes):
    """Check if a file is valid based on its size."""
    return file_size_in_bytes / 1_000 > FILE_SIZE_THRESHOLD_KB

def filter_links_against_collections(links, collection_paths):
    """
    Filter out links that exist in any of the collection files.
    
    Args:
        links (list): List of URLs to filter
        collection_paths (list): List of paths to collection files to check against
        
    Returns:
        list: Filtered list of URLs that don't exist in any collection
    """
    # Get all video IDs from collections
    collection_video_ids = set()
    for collection_path in collection_paths:
        try:
            with open(collection_path, 'r') as f:
                for line in f:
                    if line.strip():
                        video_id = extract_video_id(line.strip())
                        if video_id:
                            collection_video_ids.add(video_id)
        except Exception as e:
            print(f"Error reading {collection_path}: {str(e)}", file=sys.stderr)
            continue
    
    # Filter out links that exist in collections
    filtered_links = []
    for link in links:
        video_id = extract_video_id(link)
        if video_id not in collection_video_ids:
            filtered_links.append(link)
    
    return filtered_links
