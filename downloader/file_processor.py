"""File processing functions for TikTok downloader."""

import os
from .utils import extract_video_id

def process_file(file_path, index, total_files, file_handler, selenium_handler, 
                yt_dlp_handler, sync_handler, skip_private=False):
    """
    Process a single text file containing URLs to download.
    
    Args:
        file_path: Path to text file containing URLs
        index: Current file index for progress display
        total_files: Total number of files to process
        file_handler: FileHandler instance
        selenium_handler: SeleniumHandler instance
        yt_dlp_handler: YtDlpHandler instance
        sync_handler: SyncHandler instance
        skip_private: Whether to skip known private videos
    """
   
    # Get collection name from file name, handling multiple extensions
    base_name = os.path.basename(file_path)
    collection_name = base_name.split('.')[0]  # Split on first dot
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
    
    # Read URLs from file
    with open(file_path, "r") as f:
        urls = {url.strip() for url in f if url.strip()}

    if os.path.basename(file_path) != file_handler.all_saves_name:
        print(f"\nProcessing {index} of {total_files} collections ({display_name})")
    
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
            print(f"\t{idx}. {url} {'[Photo]' if is_photo else '[Video]'}")
    
    # Report skipped private videos
    if skip_private and known_private_urls:
        print("\nSkipping known private content:")
        for idx, url in enumerate(sorted(known_private_urls), 1):
            print(f"\t{idx}. {url}")
    
    # Separate remaining URLs into photos and videos using sets
    photo_urls = {url for url in remaining_urls if "/photo/" in url}
    video_urls = remaining_urls - photo_urls
    
    # Process all videos first
    if video_urls:
        print("\nProcessing all videos:")
        BATCH_SIZE = yt_dlp_handler.max_concurrent
        video_urls_list = sorted(list(video_urls))  # Convert set to sorted list
        for i in range(0, len(video_urls_list), BATCH_SIZE):
            batch = video_urls_list[i:i + BATCH_SIZE]
            current_batch = i//BATCH_SIZE + 1
            total_batches = (len(video_urls_list) + BATCH_SIZE - 1)//BATCH_SIZE
            print(f"\n\tVideo Batch {current_batch:,} of {total_batches:,}:")
            
            # Show what's being processed
            for idx, url in enumerate(batch, 1):
                print(f"\t  {idx}. {url}")
            
            # Process video URLs with yt-dlp in parallel
            try:
                results = yt_dlp_handler.process_url_batch(batch, output_folder)
                
                # Handle results - only show errors/issues
                for url, (success, error_msg) in results.items():
                    if error_msg == "private":
                        print(f"\t  ❌\tPrivate video: {url}")
                        file_handler.log_error(url, error_file_path, is_private=True)
                    elif error_msg in yt_dlp_handler.all_error_types:
                        print(f"\t  ⚠️\t{error_msg}, using Selenium: {url}")
                        try:
                            selenium_handler.download_with_selenium(url, output_folder, file_handler, collection_name)
                        except Exception as e:
                            if str(e) == "private":
                                print(f"\t  ❌\tPrivate video: {url}")
                                file_handler.log_error(url, error_file_path, is_private=True)
                            else:
                                print(f"\t  ❌\tSelenium failed: {str(e)}")
                                file_handler.log_error(url, error_file_path)
                    elif not success:
                        print(f"\t  ⚠️\tyt-dlp failed ({error_msg}), using Selenium: {url}")
                        try:
                            selenium_handler.download_with_selenium(url, output_folder, file_handler, collection_name)
                        except Exception as e:
                            if str(e) == "private":
                                print(f"\t  ❌\tPrivate video: {url}")
                                file_handler.log_error(url, error_file_path, is_private=True)
                            else:
                                print(f"\t  ❌\tSelenium failed: {str(e)}")
                                file_handler.log_error(url, error_file_path)
                    else:
                        file_handler.log_successful_download(url, collection_name)
            except Exception as e:
                print(f"\t  ❌\tBatch processing failed: {str(e)}")
                # Log errors for all URLs in the batch that haven't been handled
                for url in batch:
                    if not file_handler.is_url_downloaded(url):
                        file_handler.log_error(url, error_file_path)
    
    # Then process all photos
    if photo_urls:
        print("\nProcessing all photos:")
        for idx, url in enumerate(photo_urls, 1):
            print(f"\tPhoto {idx} of {len(photo_urls)}: {url}")
            try:
                selenium_handler.download_with_selenium(url, output_folder, file_handler, collection_name)
                file_handler.log_successful_download(url, collection_name)
            except Exception as e:
                if str(e) == "private":
                    print(f"\t  ❌\tPrivate photo: {url}")
                    file_handler.log_error(url, error_file_path, is_private=True)
                else:
                    print(f"\t  ❌\tPhoto download failed: {str(e)}")
                    file_handler.log_error(url, error_file_path)

    # After processing all URLs, queue the folder for syncing
    if os.path.isdir(output_folder):
        username = os.path.basename(os.path.dirname(file_path))
        sync_handler.queue_sync(output_folder, username)
        print(f">> Queued for background sync: {os.path.basename(output_folder)}")

def process_error_logs(input_path, file_handler, selenium_handler, 
                      yt_dlp_handler, sync_handler):
    """
    Process error log files and retry failed downloads.
    
    Args:
        input_path: Directory containing error log files
        file_handler: FileHandler instance
        selenium_handler: SeleniumHandler instance
        yt_dlp_handler: YtDlpHandler instance
        sync_handler: SyncHandler instance
    """
    print("\nProcessing error logs...")
    error_files = [f for f in os.listdir(input_path) 
                  if f.startswith(file_handler.error_prefix) and f.endswith('.txt')]
    
    if not error_files:
        print("No error logs found.")
        return
    
    # Wait for all queued sync operations to complete before starting error retries
    print("Waiting for all queued sync operations to complete before starting error retries...")
    sync_handler.wait_for_syncs()
    
    folders_to_sync = set()  # Track folders that need syncing
    
    for error_file in error_files:
        # Get original collection name by removing error prefix and getting path
        original_collection = error_file[len(file_handler.error_prefix):]
        # Get collection name from file name, handling multiple extensions
        original_collection_name = original_collection.split('.')[0]  # Split on first dot
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
                    print(f"\t-> Photo URL detected, using Selenium")
                    selenium_handler.download_with_selenium(url, output_folder, file_handler)
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
                        print(f"\t  ⚠️\t{error_msg.capitalize()} error, using Selenium: {url}")
                        try:
                            selenium_handler.download_with_selenium(url, output_folder, file_handler)
                            success = True
                        except Exception as e:
                            if str(e) == "private":
                                print(f"\t  ❌\tPrivate video: {url}")
                                file_handler.log_error(url, error_file_path, is_private=True)
                            else:
                                print(f"\t  ❌\tSelenium failed: {str(e)}")
                                file_handler.log_error(url, error_file_path)
            
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
        
        # If we had any successes, add the folder to sync queue
        if had_success:
            folders_to_sync.add(output_folder)
        else:
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
    
    # Queue all folders that had successful downloads for sync
    if folders_to_sync:
        username = os.path.basename(input_path)
        for folder in folders_to_sync:
            sync_handler.queue_sync(folder, username)
            print(f">> Queued for background sync: {os.path.basename(folder)}") 