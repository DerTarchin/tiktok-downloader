"""File operations and logging functionality."""

import os
from .utils import extract_video_id
import fcntl
import time

class FileHandler:
    def __init__(self, input_path):
        self.input_path = input_path
        self.error_prefix = "[error log] "
        self.success_log_file = "download_success.log"
        self.all_saves_file = "Favorite Videos (URLs).txt"
        self.all_saves_name = "All Uncategorized Favorites"
        
        # Set success_log_path based on input directory
        if os.path.isfile(input_path):
            self.success_log_path = os.path.join(os.path.dirname(input_path), self.success_log_file)
        else:
            self.success_log_path = os.path.join(input_path, self.success_log_file)

    def get_error_log_path(self, file_path):
        """Get the path to the error log file for a given input file"""
        return os.path.join(os.path.dirname(file_path), 
                           f"{self.error_prefix}{os.path.basename(file_path)}")

    def log_error(self, url, error_file_path, is_private=False):
        """Log failed URL to error file with file locking, preventing duplicates"""
        max_retries = 3
        retry_delay = 0.1
        
        # First check if error already exists
        try:
            if os.path.exists(error_file_path):
                with open(error_file_path, "r") as error_file:
                    existing_errors = error_file.readlines()
                    error_entry = f"{url}{' (private)' if is_private else ''}\n"
                    if error_entry in existing_errors:
                        return  # Skip if already logged
        except IOError:
            pass  # If we can't read the file, proceed with write attempt
        
        for attempt in range(max_retries):
            try:
                with open(error_file_path, "a") as error_file:
                    fcntl.flock(error_file.fileno(), fcntl.LOCK_EX)
                    try:
                        error_file.write(f"{url}{' (private)' if is_private else ''}\n")
                        error_file.flush()
                    finally:
                        fcntl.flock(error_file.fileno(), fcntl.LOCK_UN)
                break
            except IOError as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay)

    def log_successful_download(self, url, collection_name=None):
        """Log successfully downloaded URL to the success log file with file locking"""
        max_retries = 3
        retry_delay = 0.1
        
        # Prefix URL with collection name if provided
        log_entry = f"{collection_name}:::{url}\n" if collection_name else f"{url}\n"
        
        for attempt in range(max_retries):
            try:
                with open(self.success_log_path, 'a') as f:
                    # Get an exclusive lock on the file
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    try:
                        f.write(log_entry)
                        f.flush()  # Ensure write is committed to disk
                    finally:
                        # Always release the lock
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                break  # Success - exit retry loop
            except IOError as e:
                if attempt == max_retries - 1:  # Last attempt
                    raise  # Re-raise the exception if all retries failed
                time.sleep(retry_delay)  # Wait before retrying
        
        # Remove from error log if exists
        if collection_name:
            # Get error log path for the collection
            error_file_path = self.get_error_log_path(os.path.join(os.path.dirname(self.success_log_path), f"{collection_name}.txt"))
            if os.path.exists(error_file_path):
                try:
                    with open(error_file_path, 'r') as f:
                        lines = f.readlines()
                    # Remove both normal and private entries for this URL
                    with open(error_file_path, 'w') as f:
                        f.writelines(line for line in lines 
                                   if line.strip() != url and 
                                   line.strip() != f"{url} (private)")
                except IOError:
                    pass  # Ignore errors when trying to clean error log

    def is_url_downloaded(self, url, collection_name=None):
        """
        Check if video ID has been successfully downloaded before.
        
        Args:
            url: URL to check
            collection_name: Optional collection name to check against
            
        Returns:
            bool: True if URL has been downloaded, False otherwise
        """
        if not self.success_log_path or not os.path.exists(self.success_log_path):
            return False
            
        current_video_id = extract_video_id(url)
        if not current_video_id:
            return False
            
        with open(self.success_log_path, 'r') as f:
            logged_entries = {line.strip() for line in f}
            
            # For uncategorized links, match against any instance
            if not collection_name:
                # Extract video IDs from all entries, removing collection prefix if present
                logged_urls = {entry.split(':::', 1)[-1] for entry in logged_entries}
                return any(current_video_id == extract_video_id(logged_url) for logged_url in logged_urls)
            
            # For collection-specific links, only match against that collection
            collection_prefix = f"{collection_name}:::"
            collection_entries = {entry.split(':::', 1)[-1] for entry in logged_entries 
                               if entry.startswith(collection_prefix)}
            return any(current_video_id == extract_video_id(logged_url) for logged_url in collection_entries)

    def count_unique_videos(self):
        """Count unique videos in input path"""
        all_video_ids = set()
        
        if os.path.isdir(self.input_path):
            # First process regular collection files
            text_files = [f for f in os.listdir(self.input_path) 
                         if f.endswith(".txt") and not f.startswith(self.error_prefix) 
                         and f != self.all_saves_file]
            
            # Process regular collections first
            for file_name in text_files:
                file_path = os.path.join(self.input_path, file_name)
                with open(file_path, "r") as f:
                    urls = [url.strip() for url in f.readlines() if url.strip()]
                    video_ids = [extract_video_id(url) for url in urls]
                    all_video_ids.update(vid for vid in video_ids if vid)
            
            # Then process all_saves_file if it exists
            all_saves_path = os.path.join(self.input_path, self.all_saves_file)
            if os.path.exists(all_saves_path):
                with open(all_saves_path, "r") as f:
                    urls = [url.strip() for url in f.readlines() if url.strip()]
                    # Only count videos that weren't in regular collections
                    new_video_ids = [extract_video_id(url) for url in urls]
                    all_video_ids.update(vid for vid in new_video_ids 
                                       if vid and vid not in all_video_ids)
        
        elif os.path.isfile(self.input_path):
            with open(self.input_path, "r") as f:
                urls = [url.strip() for url in f.readlines() if url.strip()]
                video_ids = [extract_video_id(url) for url in urls]
                all_video_ids.update(vid for vid in video_ids if vid)
        
        return len(all_video_ids) 