"""Download validation functionality."""

import os
import subprocess
from .utils import extract_video_id

class Validator:
    def __init__(self, gdrive_base_path="gdrive:/TikTok Archives"):
        self.gdrive_base_path = gdrive_base_path
        self.error_prefix = "[error log] "

    def validate_downloads(self, input_path):
        """
        Validates that all videos from text files are either downloaded as MP4s or listed in error logs.
        Also checks for zero-byte files.
        
        Returns:
            dict: {
                'missing': {collection_name: set(missing_ids)},
                'extra': {collection_name: {id: filename}},
                'empty': {collection_name: {id: filename}}  # Zero-byte files
            }
        """
        print("\nValidating downloads...")
        
        validation_results = {
            'missing': {},
            'extra': {},
            'empty': {}  # Zero-byte files
        }
        
        # Define video extensions at the start of the method
        video_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
        
        if not os.path.isdir(input_path):
            print(f"Error: {input_path} is not a directory")
            return validation_results
        
        username = os.path.basename(input_path)
        
        # Get all text files (excluding error logs, .DS_Store, and all_saves_file)
        text_files = [f for f in os.listdir(input_path) 
                     if f.endswith(".txt") 
                     and not f.startswith(self.error_prefix) 
                     and f != ".DS_Store"
                     and f != "Favorite Videos (URLs).txt"]
        
        # Sort files: regular collections first (alphabetically), then uncategorized by group number
        def sort_key(filename):
            # First sort by whether it starts with "All Uncategorized Favorites"
            if filename.startswith("All Uncategorized Favorites"):
                if " (Group " in filename:
                    try:
                        # Extract group number for uncategorized group files
                        group_num = int(filename.split("Group ")[1].split(")")[0])
                        return (1, group_num, '')  # 1 to put after regular collections
                    except (IndexError, ValueError):
                        return (1, float('inf'), filename.lower())  # Handle malformed filenames
                return (1, float('inf'), filename.lower())  # Regular uncategorized files
            
            # Regular collection files (e.g., "Home.txt", "Korean food.txt", etc.)
            return (0, 0, filename.lower())  # 0 to put regular collections first
        
        text_files.sort(key=sort_key)
        
        # Read success log once at the start
        success_log_path = os.path.join(input_path, "success.log")
        success_log_entries = set()
        if os.path.exists(success_log_path):
            with open(success_log_path, 'r') as f:
                success_log_entries = {line.strip() for line in f}
        
        for txt_file in text_files:
            collection_name = os.path.splitext(txt_file)[0]
            collection_folder = os.path.join(input_path, collection_name)
            txt_path = os.path.join(input_path, txt_file)
            error_log_path = os.path.join(input_path, f"{self.error_prefix}{txt_file}")
            remote_path = f"{self.gdrive_base_path}/{username}/{collection_name}"
            
            print(f"\nValidating: {collection_name}")
            
            # Get video IDs from text file and check for duplicates
            video_ids = []
            with open(txt_path, 'r') as f:
                for line in f:
                    if line.strip():
                        vid_id = extract_video_id(line.strip())
                        if vid_id:
                            video_ids.append(vid_id)
            
            # Check for duplicates
            duplicate_ids = {vid_id: count for vid_id, count in zip(video_ids, map(video_ids.count, video_ids)) 
                            if count > 1}
            if duplicate_ids:
                print(f"Duplicate video IDs found in {txt_file}:")
                for vid_id, count in duplicate_ids.items():
                    print(f"  - ID {vid_id} appears {count} times")
            
            expected_ids = set(video_ids)
            downloaded_ids = set()
            downloaded_map = {}  # Map IDs to their filenames
            extra_ids = {}  # Store extra IDs and filenames
            empty_files = {}  # Store zero-byte files
            
            # Check local folder if it exists
            if os.path.exists(collection_folder):
                local_files = [f for f in os.listdir(collection_folder) 
                              if os.path.isfile(os.path.join(collection_folder, f))
                              and f != ".DS_Store"]
                
                for filename in local_files:
                    file_path = os.path.join(collection_folder, filename)
                    # Check for video files with matching ID pattern
                    if filename.lower().endswith(video_extensions):
                        file_id = filename.rsplit(' ', 1)[-1].split('.')[0]  # Remove any extension
                        file_size = os.path.getsize(file_path)
                        
                        if file_id.isdigit():
                            if file_size == 0:
                                empty_files[file_id] = f"(local) {filename}"
                            else:
                                downloaded_ids.add(file_id)
                                downloaded_map[file_id] = f"(local) {filename}"
                        else:
                            # Video files without valid IDs are considered extra
                            extra_ids[f"invalid_id_{len(extra_ids)}"] = f"(local) {filename}"
                    else:
                        # Non-video files are considered extra
                        extra_ids[f"non_video_{len(extra_ids)}"] = f"(local) {filename}"
            
            # Check remote folder using rclone
            try:
                # Use rclone ls to get file sizes
                cmd = ["rclone", "ls", remote_path, "--fast-list"]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    remote_files = result.stdout.splitlines()
                    for line in remote_files:
                        # rclone ls format: "   12345 filename.mp4"
                        try:
                            size_str, filename = line.strip().split(maxsplit=1)
                            file_size = int(size_str)
                            
                            if filename.lower().endswith(video_extensions):
                                file_id = filename.rsplit(' ', 1)[-1].split('.')[0]  # Remove any extension
                                
                                if file_id.isdigit():
                                    if file_size == 0:
                                        empty_files[file_id] = f"(remote) {filename}"
                                    else:
                                        downloaded_ids.add(file_id)
                                        downloaded_map[file_id] = f"(remote) {filename}"
                                else:
                                    # Video files without valid IDs are considered extra
                                    extra_ids[f"invalid_id_{len(extra_ids)}"] = f"(remote) {filename}"
                            else:
                                # Non-video files are considered extra
                                extra_ids[f"non_video_{len(extra_ids)}"] = f"(remote) {filename}"
                        except ValueError:
                            print(f"Warning: Could not parse rclone output line: {line}")
                else:
                    print(f"Warning: Could not check remote folder: {result.stderr}")
            except Exception as e:
                print(f"Error checking remote folder: {e}")
            
            # Get error log IDs
            error_ids = set()
            if os.path.exists(error_log_path):
                with open(error_log_path, 'r') as f:
                    error_ids = {extract_video_id(url.strip().replace(' (private)', '')) 
                               for url in f if url.strip()}
            
            # Check success log for this collection
            # First try collection-prefixed entries
            collection_prefix = f"{collection_name}:::"
            collection_success_entries = {entry.split(':::', 1)[-1] for entry in success_log_entries 
                                       if entry.startswith(collection_prefix)}
            
            # If no prefixed entries found, fall back to non-prefixed entries
            if not collection_success_entries:
                # Check for entries that don't have a collection prefix
                # We split on pipe and check if the first part is a known collection name
                collection_success_entries = {entry for entry in success_log_entries 
                                           if not any(entry.startswith(f"{f.split('.')[0]}:::") 
                                                    for f in text_files)}
            
            success_ids = {extract_video_id(url) for url in collection_success_entries}
            downloaded_ids.update(success_ids)
            
            # Find missing and extra IDs
            missing_ids = expected_ids - (downloaded_ids | error_ids | set(empty_files.keys()))
            extra_ids = {id_: filename for id_, filename in downloaded_map.items() 
                        if id_ not in expected_ids}
            
            # Store results
            if missing_ids:
                validation_results['missing'][collection_name] = missing_ids
            if extra_ids:
                validation_results['extra'][collection_name] = extra_ids
            if empty_files:
                validation_results['empty'][collection_name] = empty_files
            
            # Report findings
            if extra_ids:
                print(f"{len(extra_ids):,} extra videos detected:")
                for id_, filename in extra_ids.items():
                    print(f"\t{id_}, {filename}")
            
            if missing_ids:
                print(f"{len(missing_ids):,} missing videos detected:")
                for vid_id in missing_ids:
                    print(f"\t{vid_id}")
                    
            if empty_files:
                print(f"{len(empty_files):,} empty (zero-byte) files detected:")
                for vid_id, filename in empty_files.items():
                    print(f"\t{vid_id}, {filename}")
            
            if not (extra_ids or missing_ids or empty_files):
                print(f"✓ All videos accounted for in {collection_name}")
                print(f"  Total unique IDs in text file: {len(expected_ids):,}")
                print(f"  Downloaded: {len(downloaded_ids):,}")
                print(f"  In error log: {len(error_ids):,}") 
        
        return validation_results 