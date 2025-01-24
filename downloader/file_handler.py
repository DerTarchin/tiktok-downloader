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
            
        # Initialize caches
        self._success_log_cache = {}
        self._error_log_cache = {}
        self._last_cache_update = 0
        self._last_error_cache_updates = {}
        self._cache_lock = fcntl.flock
        self._update_success_log_cache()

    def _update_success_log_cache(self):
        """Update the in-memory cache of success log entries if file has been modified"""
        try:
            if not os.path.exists(self.success_log_path):
                self._success_log_cache = {}
                return

            mtime = os.path.getmtime(self.success_log_path)
            if mtime > self._last_cache_update:
                with open(self.success_log_path, 'r') as f:
                    # Group entries by collection
                    cache = {}
                    for line in f:
                        line = line.strip()
                        if ':::' in line:
                            collection, url = line.split(':::', 1)
                            if collection not in cache:
                                cache[collection] = set()
                            cache[collection].add(extract_video_id(url))
                        else:
                            if None not in cache:
                                cache[None] = set()
                            cache[None].add(extract_video_id(line))
                    
                    self._success_log_cache = cache
                    self._last_cache_update = mtime
        except Exception as e:
            print(f"Warning: Failed to update success log cache: {e}")
            self._success_log_cache = {}

    def _update_error_log_cache(self, error_file_path):
        """Update the in-memory cache of error log entries if file has been modified"""
        try:
            if not os.path.exists(error_file_path):
                self._error_log_cache[error_file_path] = set()
                return

            mtime = os.path.getmtime(error_file_path)
            last_update = self._last_error_cache_updates.get(error_file_path, 0)
            
            if mtime > last_update:
                with open(error_file_path, 'r') as f:
                    self._error_log_cache[error_file_path] = {line.strip() for line in f}
                self._last_error_cache_updates[error_file_path] = mtime
        except Exception as e:
            print(f"Warning: Failed to update error log cache for {error_file_path}: {e}")
            self._error_log_cache[error_file_path] = set()

    def get_error_log_path(self, file_path):
        """Get the path to the error log file for a given input file"""
        base_name = os.path.basename(file_path)
        if not base_name.endswith('.txt'):
            base_name += '.txt'
        return os.path.join(os.path.dirname(file_path), 
                           f"{self.error_prefix}{base_name}")

    def log_error(self, url, error_file_path, is_private=False):
        """Log failed URL to error file with file locking, preventing duplicates"""
        max_retries = 3
        retry_delay = 0.1
        
        # Update cache if needed
        self._update_error_log_cache(error_file_path)
        
        # Check if error already exists in cache
        error_entry = f"{url}{' (private)' if is_private else ''}"
        if error_entry in self._error_log_cache.get(error_file_path, set()):
            return
        
        for attempt in range(max_retries):
            try:
                with open(error_file_path, "a") as error_file:
                    fcntl.flock(error_file.fileno(), fcntl.LOCK_EX)
                    try:
                        error_file.write(f"{error_entry}\n")
                        error_file.flush()
                        # Update cache
                        if error_file_path not in self._error_log_cache:
                            self._error_log_cache[error_file_path] = set()
                        self._error_log_cache[error_file_path].add(error_entry)
                    finally:
                        fcntl.flock(error_file.fileno(), fcntl.LOCK_UN)
                break
            except IOError as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay)

    def remove_from_error_log(self, url, error_file_path):
        """Remove URL from error log efficiently using cache"""
        if not os.path.exists(error_file_path):
            return
            
        # Update cache if needed
        self._update_error_log_cache(error_file_path)
        
        # Check both normal and private entries
        entries_to_remove = {url, f"{url} (private)"}
        cache_entries = self._error_log_cache.get(error_file_path, set())
        matching_entries = cache_entries & entries_to_remove
        
        if not matching_entries:
            return
            
        try:
            with open(error_file_path, 'r') as f:
                lines = f.readlines()
            
            with open(error_file_path, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    new_lines = [line for line in lines if line.strip() not in entries_to_remove]
                    f.writelines(new_lines)
                    f.flush()
                    # Update cache
                    self._error_log_cache[error_file_path] = {line.strip() for line in new_lines}
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except IOError:
            pass  # Ignore errors when trying to clean error log

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
        
        # Force cache update after successful write
        self._last_cache_update = 0
        
        # Remove from error log if exists
        if collection_name:
            # Get error log path for the collection
            error_file_path = self.get_error_log_path(os.path.join(os.path.dirname(self.success_log_path), f"{collection_name}.txt"))
            self.remove_from_error_log(url, error_file_path)

    def is_url_downloaded(self, url, collection_name=None):
        """Check if video ID has been successfully downloaded before using cache."""
        if not self.success_log_path or not os.path.exists(self.success_log_path):
            return False
            
        current_video_id = extract_video_id(url)
        if not current_video_id:
            return False

        # Update cache if needed
        self._update_success_log_cache()
            
        # For uncategorized links, match against any instance
        if not collection_name:
            return any(current_video_id in video_ids 
                     for video_ids in self._success_log_cache.values())
        
        # For collection-specific links, only match against that collection
        return (collection_name in self._success_log_cache and 
                current_video_id in self._success_log_cache[collection_name])

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