"""Main script for TikTok video downloader."""

import os
import sys
from downloader.file_handler import FileHandler
from downloader.selenium_handler import SeleniumHandler
from downloader.yt_dlp_handler import YtDlpHandler
from downloader.sync_handler import SyncHandler
from downloader.validator import Validator
from downloader.utils import (get_highest_group_number, write_and_process_urls, 
                            split_into_groups, print_final_summary)
from downloader.file_processor import process_file, process_error_logs
import subprocess


def main():
    # Check for correct usage
    if len(sys.argv) < 2:
        print("Usage: python script.py <input_directory_or_file> [--errors-only] [--disable-headless] [--combine-uncategorized] [--concurrent N] [--skip-validation] [--skip-private]")
        sys.exit(1)

    # Get the input path and check for flags
    input_path = sys.argv[1]
    errors_only = "--errors-only" in sys.argv
    combine_uncategorized = "--combine-uncategorized" in sys.argv
    headless = "--disable-headless" not in sys.argv
    skip_validation = "--skip-validation" in sys.argv
    skip_private = "--skip-private" in sys.argv
    
    # Parse concurrent downloads setting
    concurrent_downloads = 3
    for i, arg in enumerate(sys.argv):
        if arg == "--concurrent" and i + 1 < len(sys.argv):
            try:
                concurrent_downloads = int(sys.argv[i + 1])
                if concurrent_downloads < 1:
                    concurrent_downloads = 1
                elif concurrent_downloads > 5:
                    print("Warning: High concurrency may trigger rate limiting. Limiting to 3 concurrent downloads.")
                    concurrent_downloads = 5
            except ValueError:
                print("Warning: Invalid concurrent downloads value. Using default (2).")
    
    # Initialize handlers
    file_handler = FileHandler(input_path)
    
    # Create temp_download_dir in the same directory as input_path
    if os.path.isfile(input_path):
        base_dir = os.path.dirname(input_path)
    else:
        base_dir = input_path
    temp_download_dir = os.path.join(base_dir, "_tmp")
    os.makedirs(temp_download_dir, exist_ok=True)
    
    selenium_handler = SeleniumHandler(temp_download_dir, headless=headless)
    yt_dlp_handler = YtDlpHandler(max_concurrent=concurrent_downloads)
    sync_handler = SyncHandler()
    validator = Validator()

    total_videos = file_handler.count_unique_videos()
    print(f"\nFound {total_videos:,} unique videos to process")
    
    try:
        selenium_handler.startup()
        sync_handler.start_sync_thread()

        if errors_only:
            print("\nRunning in errors-only mode...")
            process_error_logs(input_path if os.path.isdir(input_path) 
                             else os.path.dirname(input_path),
                             file_handler, selenium_handler, 
                             yt_dlp_handler, sync_handler)
        else:
            # Track all processed URLs
            processed_urls = set()

            if os.path.isdir(input_path):
                # First, pre-process the all_saves_file if it exists
                all_saves_path = os.path.join(input_path, file_handler.all_saves_file)
                group_files = []
                if os.path.exists(all_saves_path):
                    print(f"\nPre-processing {file_handler.all_saves_file}")
                    with open(all_saves_path, "r") as f:
                        urls = [url.strip() for url in f.readlines() if url.strip()]
                    
                    if urls:
                        if not combine_uncategorized:
                            # Find highest existing group number
                            start_group = get_highest_group_number(input_path, file_handler.all_saves_name)
                            
                            # Pre-generate all group files
                            group_files = split_into_groups(urls, input_path, file_handler, start_group)
                            if len(group_files) > 0:
                                if any(os.path.getsize(f) == 0 for f in group_files):
                                    print("Creating new group files...")
                                else:
                                    print("Using existing group files...")
                            print(f"Found {len(group_files):,} group files")
                
                # If it's a directory, process all text files in the directory
                text_files = [f for f in os.listdir(input_path) 
                            if f.endswith(".txt") 
                            and not f.startswith(file_handler.error_prefix)
                            and f != file_handler.all_saves_file]
                
                # Sort files: regular collections first, then uncategorized groups
                def sort_key(x):
                    # First sort by whether it starts with all_saves_name
                    is_all_saves = os.path.basename(x).startswith(f"{file_handler.all_saves_name}")
                    
                    # For all_saves files, extract and sort by group number if it exists
                    if is_all_saves and "Group " in x:
                        try:
                            group_num = int(x.split("Group ")[1].split(")")[0])
                            return (is_all_saves, group_num)
                        except (ValueError, IndexError):
                            pass
                    
                    # Otherwise sort by lowercase filename
                    return (is_all_saves, x.lower())
                
                text_files.sort(key=sort_key)
                group_files.sort(key=sort_key)
                total_files = len(text_files)

                # Process regular collection files first
                regular_collection_end_index = 0
                for index, file_name in enumerate(text_files, start=1):
                    if (not file_name.startswith(file_handler.error_prefix) and 
                        file_name != file_handler.all_saves_file and
                        not file_name.startswith(f"{file_handler.all_saves_name} (Group")):
                        regular_collection_end_index = index
                        file_path = os.path.join(input_path, file_name)
                        # Collect URLs from each file
                        with open(file_path, "r") as f:
                            processed_urls.update(url.strip() for url in f.readlines() if url.strip())
                        process_file(file_path, index, total_files,
                                  file_handler, selenium_handler, 
                                  yt_dlp_handler, sync_handler,
                                  skip_private=skip_private)

                # Finally, process the uncategorized groups if they were created
                if group_files:
                    print("\nProcessing uncategorized groups...")
                    for group_file in group_files:
                        group_num = int(group_file.split("Group ")[1].split(")")[0])
                        process_file(group_file, group_num + regular_collection_end_index,
                                  total_files,
                                  file_handler, selenium_handler,
                                  yt_dlp_handler, sync_handler,
                                  skip_private=skip_private)
                elif os.path.exists(all_saves_path) and combine_uncategorized:
                    # Original behavior for non-split processing
                    remaining_uncategorized = os.path.join(input_path, 
                                                         f"{file_handler.all_saves_name}.txt")
                    write_and_process_urls(remaining_uncategorized, urls,
                                        file_handler, selenium_handler,
                                        yt_dlp_handler, sync_handler,
                                        None, total_files,
                                        skip_private=skip_private)

            elif os.path.isfile(input_path):
                # If it's a single file, process it directly
                if input_path.endswith(".txt"):
                    process_file(input_path, 1, 1,
                              file_handler, selenium_handler,
                              yt_dlp_handler, sync_handler,
                              skip_private=skip_private)
                else:
                    print(f"File {input_path} is not a .txt file. Skipping.")
            else:
                print(f"Path {input_path} does not exist.")

            # After all regular processing, wait for sync queue to empty
            print("\n>> Waiting for background syncs to complete...")
            sync_handler.wait_for_syncs()
            
            # Process error logs after all syncs are complete
            process_error_logs(input_path if os.path.isdir(input_path) 
                             else os.path.dirname(input_path),
                             file_handler, selenium_handler,
                             yt_dlp_handler, sync_handler)
            
            # Wait for any new syncs from error retries
            print("\n>> Waiting for error retry syncs to complete...")
            sync_handler.wait_for_syncs()
            
            # Stop the sync thread
            sync_handler.stop_sync_thread()
            
            print("\n>> Performing final sync of remaining files...")
            sync_handler.sync_remaining_files(input_path if os.path.isdir(input_path) 
                                           else os.path.dirname(input_path))
            
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Cleaning up...")
        selenium_handler.cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {str(e)}")
        selenium_handler.cleanup()
        sys.exit(1)
    
    finally:
        # Ensure sync thread is stopped
        sync_handler.stop_sync_thread()
        selenium_handler.shutdown()
        yt_dlp_handler.shutdown()  # Clean up thread pool
        
        # Clean up temp download directory
        if os.path.exists(temp_download_dir):
            for file in os.listdir(temp_download_dir):
                try:
                    os.remove(os.path.join(temp_download_dir, file))
                except:
                    pass
            try:
                os.rmdir(temp_download_dir)
            except:
                pass

    print("\nProcessing complete.")
    
    # Add validation step unless skipped
    if not skip_validation:
        validator.validate_downloads(input_path if os.path.isdir(input_path) 
                                  else os.path.dirname(input_path))
        
    # Print final summary after processing is complete
    print_final_summary(input_path, file_handler)

if __name__ == "__main__":
    main() 