"""Main script for TikTok video downloader."""

import argparse
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
from downloader.worker_pool import WorkerPool
import subprocess


def main():
    parser = argparse.ArgumentParser(description='TikTok video downloader script.')
    parser.add_argument('input_path', help='Input directory or file')
    parser.add_argument('--errors-only', action='store_true', help='Process only error logs')
    parser.add_argument('--disable-headless', action='store_true', help='Disable headless mode for Selenium')
    parser.add_argument('--combine-uncategorized', action='store_true', help='Combine uncategorized videos')
    parser.add_argument('--concurrent', type=int, default=5, help='Number of concurrent downloads')
    parser.add_argument('--skip-validation', action='store_true', help='Skip validation step')
    parser.add_argument('--skip-private', action='store_true', help='Skip private videos')
    parser.add_argument('--skip-sync', action='store_true', help='Skip synchronization step')
    parser.add_argument('--concurrent-selenium', type=int, help='Number of concurrent Selenium downloads (defaults to --concurrent value)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()

    # Get the input path and check for flags
    input_path = args.input_path
    errors_only = args.errors_only
    combine_uncategorized = args.combine_uncategorized
    headless = not args.disable_headless
    skip_validation = args.skip_validation
    skip_private = args.skip_private
    skip_sync = args.skip_sync
    verbose = args.verbose
    
    # Parse concurrent downloads setting
    concurrent_downloads = args.concurrent
    if concurrent_downloads < 1:
        concurrent_downloads = 1
    
    # Set selenium concurrency
    selenium_concurrent = args.concurrent_selenium if args.concurrent_selenium is not None else concurrent_downloads
    if selenium_concurrent < 1:
        selenium_concurrent = 1
    
    # Initialize handlers
    file_handler = FileHandler(input_path)
    
    # Create base temp download directory
    if os.path.isfile(input_path):
        base_dir = os.path.dirname(input_path)
    else:
        base_dir = input_path
    
    total_videos = file_handler.count_unique_videos()
    print(f"\nFound {total_videos:,} unique videos to process\n")
        
    # Create multiple selenium handlers with unique temp directories
    selenium_handlers = []
    for i in range(selenium_concurrent):
        temp_download_dir = os.path.join(base_dir, f"_tmp_{i+1}")
        os.makedirs(temp_download_dir, exist_ok=True)
        selenium_handlers.append(SeleniumHandler(temp_download_dir, headless=headless, worker_num=i+1, verbose=verbose))
    
    # Initialize other handlers
    yt_dlp_handler = YtDlpHandler()
    sync_handler = SyncHandler()
    validator = Validator()
    worker_pool = WorkerPool()

    try:
        # Start up all selenium handlers
        for handler in selenium_handlers:
            handler.startup()
            
        if not skip_sync:
            sync_handler.start_sync_thread()

        if errors_only:
            print("\nRunning in errors-only mode...")
            process_error_logs(input_path if os.path.isdir(input_path) 
                             else os.path.dirname(input_path),
                             file_handler, selenium_handlers, 
                             yt_dlp_handler, sync_handler,
                             skip_sync=skip_sync)
        else:
            # Track all processed URLs
            processed_urls = set()

            if os.path.isdir(input_path):
                # First, pre-process the all_saves_file if it exists
                all_saves_path = os.path.join(input_path, file_handler.all_saves_file)
                group_files = []
                if os.path.exists(all_saves_path):
                    if verbose:
                        print(f"\nPre-processing {file_handler.all_saves_file}")

                    with open(all_saves_path, "r") as f:
                        urls = [url.strip() for url in f.readlines() if url.strip()]
                    
                    if urls:
                        if not combine_uncategorized:
                            # Find highest existing group number
                            start_group = get_highest_group_number(input_path, file_handler.all_saves_name)
                            
                            # Pre-generate all group files
                            group_files = split_into_groups(urls, input_path, file_handler, start_group, verbose=verbose)
                            if len(group_files) > 0 and verbose:
                                if any(os.path.getsize(f) == 0 for f in group_files):
                                    print("Creating new group files...")
                                else:
                                    print("Using existing group files...")
                            if verbose:
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
                            return (is_all_saves, group_num, '')  # Empty string for consistent tuple shape
                        except (ValueError, IndexError):
                            pass
                    
                    # Otherwise sort by lowercase filename
                    return (is_all_saves, float('inf'), x.lower())  # Use float('inf') for non-group files
                
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
                                  file_handler, selenium_handlers, 
                                  yt_dlp_handler, sync_handler,
                                  skip_private=skip_private,
                                  skip_sync=skip_sync,
                                  verbose=verbose,
                                  max_concurrent=concurrent_downloads)

                # Finally, process the uncategorized groups if they were created
                if group_files:
                    print("\nProcessing uncategorized groups...")
                    for group_file in group_files:
                        group_num = int(group_file.split("Group ")[1].split(")")[0])
                        process_file(group_file, group_num + regular_collection_end_index,
                                  total_files,
                                  file_handler, selenium_handlers,
                                  yt_dlp_handler, sync_handler,
                                  skip_private=skip_private,
                                  skip_sync=skip_sync,
                                  verbose=verbose,
                                  max_concurrent=concurrent_downloads)
                elif os.path.exists(all_saves_path) and combine_uncategorized:
                    # Original behavior for non-split processing
                    remaining_uncategorized = os.path.join(input_path, 
                                                         f"{file_handler.all_saves_name}.txt")
                    write_and_process_urls(remaining_uncategorized, urls,
                                        file_handler, selenium_handlers,
                                        yt_dlp_handler, sync_handler,
                                        None, total_files,
                                        skip_private=skip_private,
                                        skip_sync=skip_sync,
                                        verbose=verbose,
                                        max_concurrent=concurrent_downloads)

            elif os.path.isfile(input_path):
                # If it's a single file, process it directly
                if input_path.endswith(".txt"):
                    process_file(input_path, 1, 1,
                              file_handler, selenium_handlers,
                              yt_dlp_handler, sync_handler,
                              skip_private=skip_private,
                              skip_sync=skip_sync,
                              verbose=verbose,
                              max_concurrent=concurrent_downloads)
                else:
                    print(f"File {input_path} is not a .txt file. Skipping.")
            else:
                print(f"Path {input_path} does not exist.")

            # After all regular processing, wait for sync queue to empty
            if not skip_sync:
                print("\n>> Waiting for background syncs to complete...")
                sync_handler.wait_for_syncs()
            
            # Process error logs
            process_error_logs(input_path if os.path.isdir(input_path) 
                             else os.path.dirname(input_path),
                             file_handler, selenium_handlers,
                             yt_dlp_handler, sync_handler,
                             skip_sync=skip_sync)
            
            # Wait for all syncs to complete
            if not skip_sync:
                print("\n>> Waiting for all syncs to complete...")
                sync_handler.wait_for_syncs()
                
                # Stop all workers before final sync
                print("\n>> Stopping all workers before final sync...")
                worker_pool.shutdown()
                
                # Then shutdown each handler with proper cleanup
                for handler in selenium_handlers:
                    try:
                        handler.shutdown()
                    except Exception as e:
                        print(f"\nWarning: Error during handler shutdown: {e}")
                
                # Stop the sync thread
                sync_handler.stop_sync_thread()
                
                print("\n>> Performing final sync of remaining files...")
                sync_handler.sync_remaining_files(input_path if os.path.isdir(input_path) 
                                               else os.path.dirname(input_path))
            
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Cleaning up...")
        # First stop all worker threads
        worker_pool.shutdown()
        
        # Then shutdown each handler with proper cleanup
        for handler in selenium_handlers:
            try:
                handler.shutdown()
            except Exception as e:
                print(f"\nWarning: Error during handler shutdown: {e}")
        
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {str(e)}")
        # First stop all worker threads
        worker_pool.shutdown()
        
        # Then shutdown each handler with proper cleanup
        for handler in selenium_handlers:
            try:
                handler.shutdown()
            except Exception as e:
                print(f"\nWarning: Error during handler shutdown: {e}")
        
        sys.exit(1)
    
    finally:
        # Ensure sync thread is stopped
        sync_handler.stop_sync_thread()
        
        # Stop worker threads
        worker_pool.shutdown()
        
        # Shutdown all selenium handlers with proper cleanup
        for handler in selenium_handlers:
            try:
                handler.shutdown()
            except Exception as e:
                print(f"\nWarning: Error during handler shutdown: {e}")
            
        yt_dlp_handler.shutdown()  # Clean up thread pool

    print("\nProcessing complete.")
    
    # Add validation step unless skipped
    if not skip_validation:
        validation_results = validator.validate_downloads(input_path if os.path.isdir(input_path) 
                                  else os.path.dirname(input_path))
        
        # Only print final summary if there are no issues
        if  validation_results['missing'] or validation_results['extra'] or validation_results['empty']:
            print("Validation results:")
            print(f"Missing: {validation_results['missing']}")
            print(f"Extra: {validation_results['extra']}")
            print(f"Empty (zero-byte): {validation_results['empty']}")
            
    print_final_summary(input_path, file_handler)

if __name__ == "__main__":
    main() 