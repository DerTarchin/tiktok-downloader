"""File processing functions for TikTok downloader."""

import os
from .utils import extract_video_id
from .worker_pool import WorkerPool

# Create a global worker pool instance
worker_pool = WorkerPool()

def process_file(file_path, index, total_files, file_handler, selenium_handlers, 
                yt_dlp_handler, sync_handler, skip_private=False, skip_sync=False, verbose=False, max_concurrent=3):
    """
    Process a single text file containing URLs to download.
    
    Args:
        file_path: Path to text file containing URLs
        index: Current file index for progress display
        total_files: Total number of files to process
        file_handler: FileHandler instance
        selenium_handlers: List of SeleniumHandler instances
        yt_dlp_handler: YtDlpHandler instance
        sync_handler: SyncHandler instance
        skip_private: Whether to skip known private videos
        skip_sync: Whether to skip syncing the processed folder
        verbose: Whether to print verbose output
        max_concurrent: Maximum number of concurrent yt-dlp downloads
    """

    # Get collection name from file name, handling multiple extensions
    base_name = os.path.basename(file_path)
    collection_name = base_name.split('.txt')[0]
    while collection_name.endswith('.'):
        collection_name = collection_name[:-1]
    display_name = collection_name
    output_folder = os.path.join(os.path.dirname(file_path), collection_name)
    
    # For uncategorized files, set collection_name to None AFTER creating output_folder
    if collection_name.startswith(file_handler.all_saves_name):
        collection_name = None

    # Create output folder
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created output folder: {os.path.basename(output_folder)}")
    
    # Get error log path
    error_file_path = file_handler.get_error_log_path(file_path)
    
    # Start selenium worker threads if not already running
    if not worker_pool.selenium_threads:
        worker_pool.start_selenium_threads(selenium_handlers, file_handler, yt_dlp_handler)
    
    # Start yt-dlp worker threads if not already running
    if not worker_pool.yt_dlp_threads:
        worker_pool.start_yt_dlp_threads(yt_dlp_handler, file_handler, max_concurrent=max_concurrent, verbose=verbose)
    
    try:
        # Read URLs from file
        with open(file_path, "r") as f:
            urls = {url.strip() for url in f if url.strip()}

        if os.path.basename(file_path) != file_handler.all_saves_name:
            print(f"\nProcessing {index:,} of {total_files:,} collections ({display_name})")
        
        # Get known private videos if skip_private is True
        known_private_urls = set()
        if skip_private and os.path.exists(error_file_path):
            with open(error_file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.endswith(" (private)"):
                        known_private_urls.add(line[:-10])  # Remove " (private)" suffix
        
        # Create sets for faster membership testing and filter out private URLs if skip_private is True
        downloaded_urls = {url for url in urls if file_handler.is_url_downloaded(url, collection_name)}
        remaining_urls = urls - downloaded_urls
        if skip_private:
            remaining_urls = remaining_urls - known_private_urls

        # Report already downloaded URLs
        if downloaded_urls:
            print("\nSkipping already downloaded content:")
            for idx, url in enumerate(sorted(downloaded_urls), 1):
                is_photo = '/photo/' in url
                print(f"\t{idx:,}. {url} {'[Photo]' if is_photo else '[Video]'}")
        
        # Report skipped private videos
        if skip_private and known_private_urls:
            print("\nSkipping known private content:")
            for idx, url in enumerate(sorted(known_private_urls), 1):
                print(f"\t{idx:,}. {url}")
        
        # Separate remaining URLs into photos and videos using sets
        print(f"\nProcessing {len(remaining_urls):,} URLs...")
        photo_urls = {url for url in remaining_urls if "/photo/" in url}
        video_urls = remaining_urls - photo_urls
        
        # Process photos and videos concurrently
        if photo_urls:
            if verbose:
                print("\nQueueing photos for processing:")
            for idx, url in enumerate(photo_urls, 1):
                if verbose:
                    print(f"\tPhoto {idx:,} of {len(photo_urls):,}: {url}")
                # Queue photo downloads for selenium processing
                worker_pool.queue_selenium_download(url, collection_name, "known-photo", output_folder)
        
        # Process all videos using yt-dlp workers
        if video_urls:
            # Show what's being processed
            if verbose:
                print(f"\nProcessing {len(video_urls):,} videos{':' if verbose else ''}")
                for idx, url in enumerate(sorted(video_urls), 1):
                    print(f"\t{idx:,}. {url}")
            
            def handle_result(url, success, error_msg, speed):
                if success:
                    file_handler.log_successful_download(url, collection_name)
                else:
                    # Skip selenium for private videos and just log them
                    if error_msg == "private":
                        file_handler.log_error(url, error_file_path, is_private=True)
                    else:
                        # Queue failed downloads for selenium processing with error message
                        worker_pool.queue_selenium_download(url, collection_name, error_msg, output_folder)

            # Queue all videos for yt-dlp processing
            if verbose:
                print("Queueing videos for yt-dlp workers...")
            for url in sorted(video_urls):
                worker_pool.queue_yt_dlp_download(url, output_folder, collection_name, handle_result)
            
            if verbose:
                print("yt-dlp workers finished")
                
        # Wait for all selenium downloads to complete before returning
        print("\nWaiting for queued downloads to complete...")
        worker_pool.wait_for_yt_dlp_queue()
        worker_pool.wait_for_selenium_queue()
        
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        raise

    # After processing all URLs, queue the folder for syncing
    if os.path.isdir(output_folder) and not skip_sync:
        username = os.path.basename(os.path.dirname(file_path))
        sync_handler.queue_sync(output_folder, username)
        print(f">> Queued for background sync: {os.path.basename(output_folder)}")

def process_error_logs(input_path, file_handler, selenium_handlers, 
                      yt_dlp_handler, sync_handler, skip_sync=False):
    """
    Process error log files and retry failed downloads.
    
    Args:
        input_path: Directory containing error log files
        file_handler: FileHandler instance
        selenium_handlers: List of SeleniumHandler instances
        yt_dlp_handler: YtDlpHandler instance
        sync_handler: SyncHandler instance
        skip_sync: Whether to skip syncing the processed folder
    """
    print("\nProcessing error logs...")
    error_files = [f for f in os.listdir(input_path) 
                  if f.startswith(file_handler.error_prefix) and f.endswith('.txt')]
    
    if not error_files:
        print("No error logs found.")
        return
    
    for error_file in error_files:
        # Get original collection name by removing error prefix and getting path
        original_collection = error_file[len(file_handler.error_prefix):]
        # Get collection name from file name, handling multiple extensions
        original_collection_name = original_collection.split('.txt')[0]
        while original_collection_name.endswith('.'):
            original_collection_name = original_collection_name[:-1]
        original_folder = original_collection_name  # Use the same name for folder
        output_folder = os.path.join(input_path, original_folder)
        
        print(f"\nRetrying failed downloads for: {original_collection_name}")
        error_file_path = os.path.join(input_path, error_file)
        
        # Read all URLs initially
        with open(error_file_path, 'r') as f:
            failed_urls = [url.strip() for url in f.readlines() if url.strip()]
        
        # Track if we've made any successful downloads
        had_success = False
        
        # Create output folder if it doesn't exist
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            print(f"\t-> Created output folder: {original_folder}")
        
        for url in failed_urls:
            # Skip URLs marked as private
            if url.endswith(" (private)"):
                print(f"\t-> Skipping private video: {url.replace(' (private)', '')}")
                continue
                
            print(f"\tRetrying: {url}")
            success = False
            
            try:
                # Skip yt-dlp for photo URLs
                if "/photo/" in url:
                    print(f"\t-> Photo URL detected, adding to Selenium queue")
                    worker_pool.queue_selenium_download(url, original_collection_name, "known-photo", output_folder)
                    success = True
                else:
                    # Try yt-dlp first
                    success, error_msg, download_speed = yt_dlp_handler.try_yt_dlp(url, output_folder)
                    
                    if error_msg == "private":
                        print(f"\t-> Video not available: {url}")
                        # Check if URL already exists in error log
                        target_video_id = extract_video_id(url)
                        with open(error_file_path, 'r') as f:
                            lines = f.readlines()
                        # Remove any existing entries for this video ID
                        with open(error_file_path, 'w') as f:
                            for line in lines:
                                line_url = line.strip().replace(' (private)', '')
                                
                                if extract_video_id(line_url) != target_video_id:
                                    f.write(line)
                        # Now log the error as private
                        file_handler.log_error(url, error_file_path, is_private=True)
                        continue
                    elif error_msg in yt_dlp_handler.all_error_types or not success:
                        print(f"\t  ⚠️\t{error_msg.capitalize()} error, adding to Selenium queue: {url}")
                        worker_pool.queue_selenium_download(url, original_collection_name, error_msg, output_folder)
                        success = True

            except Exception as e:
                print(f"\t-> Retry failed: {e}")
                success = False
            
            # Update error log file in real time
            if success:
                had_success = True
                # Remove the successful URL from the error log
                with open(error_file_path, 'r') as f:
                    lines = f.readlines()
                with open(error_file_path, 'w') as f:
                    f.writelines(line for line in lines if line.strip() != url)
                # Log successful download
                file_handler.log_successful_download(url, original_collection_name)
        
        # If we had any successes, queue the folder for sync immediately
        if had_success and not skip_sync:
            username = os.path.basename(input_path)
            sync_handler.queue_sync(output_folder, username)
            print(f">> Queued for background sync: {os.path.basename(output_folder)}")
        elif not skip_sync:
            # If no successes and folder is empty, remove it
            if os.path.exists(output_folder) and not os.listdir(output_folder):
                try:
                    os.rmdir(output_folder)
                    print(f"\t-> Removed empty folder: {original_folder}")
                except Exception as e:
                    print(f"\t-> Warning: Could not remove empty folder {original_folder}: {e}")
        
        # Check if error file is empty and delete if so
        if os.path.exists(error_file_path):
            with open(error_file_path, 'r') as f:
                remaining_urls = f.read().strip()
            if not remaining_urls:
                os.remove(error_file_path)
                print(f"\tAll URLs successfully downloaded for {original_collection_name}")
            else:
                print(f"\tSome URLs still failed for {original_collection_name}") 