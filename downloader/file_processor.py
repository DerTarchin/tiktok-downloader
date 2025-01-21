"""File processing functions for TikTok downloader."""

import os
import threading
from queue import Queue
from .utils import extract_video_id, split_urls_by_type, get_output_folder, get_error_file_path

# Queue for failed yt-dlp downloads that need selenium processing
selenium_queue = Queue()
selenium_threads = []
selenium_thread_stop = threading.Event()
selenium_total_items = 0
selenium_processed_items = 0
selenium_counter_lock = threading.Lock()

def selenium_worker(selenium_handler, file_handler, yt_dlp_handler, worker_num):
    """Worker thread that processes failed yt-dlp downloads using Selenium."""
    global selenium_processed_items, selenium_total_items
    
    while not selenium_thread_stop.is_set():
        try:
            # Get next item from queue with timeout to allow checking stop flag
            try:
                url, collection_name, error_msg, output_folder = selenium_queue.get(timeout=1)
            except:
                # Reset counters if queue is empty
                if selenium_queue.empty():
                    with selenium_counter_lock:
                        selenium_processed_items = 0
                        selenium_total_items = 0
                continue
                
            try:
                error_file_path = get_error_file_path(output_folder)
                
                # Update progress counter
                with selenium_counter_lock:
                    selenium_processed_items += 1
                    current = selenium_processed_items
                    total = selenium_total_items
                    print(f"\n[Worker {worker_num}] [Selenium Progress: {current}/{total}]")
                
                # Handle different error types
                if error_msg == "private":
                    print(f"[Worker {worker_num}] \t  ❌\tPrivate video: {url}")
                    file_handler.log_error(url, error_file_path, is_private=True)
                    continue  # Skip selenium attempt but let finally block handle task_done
                    
                # For all other errors, try selenium
                if error_msg in yt_dlp_handler.all_error_types:
                    print(f"[Worker {worker_num}] \t  ⚠️\t{error_msg}, using Selenium: {url}")
                else:
                    print(f"[Worker {worker_num}] \t  ⚠️\tyt-dlp failed ({error_msg}), using Selenium: {url}")
                    
                try:
                    selenium_handler.download_with_selenium(url, output_folder, file_handler, collection_name)
                    file_handler.log_successful_download(url, collection_name)
                except Exception as e:
                    if str(e) == "private":
                        print(f"[Worker {worker_num}] \t  ❌\tPrivate video: {url}")
                        file_handler.log_error(url, error_file_path, is_private=True)
                    else:
                        print(f"[Worker {worker_num}] \t  ❌\tSelenium failed: {str(e)}")
                        file_handler.log_error(url, error_file_path)
                        
            except Exception as e:
                print(f"[Worker {worker_num}] \t  ❌\tSelenium worker error for {url}: {str(e)}")
                error_file_path = get_error_file_path(output_folder)
                file_handler.log_error(url, error_file_path)
            finally:
                selenium_queue.task_done()  # Only call task_done once, in finally block
        except Exception as e:
            print(f"[Worker {worker_num}] \t  ❌\tSelenium worker error: {str(e)}")

def start_selenium_threads(selenium_handlers, file_handler, yt_dlp_handler):
    """Start multiple Selenium worker threads."""
    global selenium_threads, selenium_processed_items, selenium_total_items
    selenium_thread_stop.clear()
    selenium_processed_items = 0
    selenium_total_items = 0
    
    # Create and start a thread for each selenium handler
    for i, handler in enumerate(selenium_handlers, 1):
        thread = threading.Thread(
            target=selenium_worker,
            args=(handler, file_handler, yt_dlp_handler, i),
            daemon=True
        )
        thread.start()
        selenium_threads.append(thread)

def queue_selenium_download(url, collection_name, error_msg, output_folder):
    """Queue a URL for selenium download and update counter."""
    global selenium_total_items
    with selenium_counter_lock:
        selenium_total_items += 1
    selenium_queue.put((url, collection_name, error_msg, output_folder))

def stop_selenium_threads():
    """Stop all Selenium worker threads and wait for them to finish."""
    selenium_thread_stop.set()
    for thread in selenium_threads:
        thread.join()
    selenium_threads.clear()
        
def wait_for_selenium_queue():
    """Wait for all queued Selenium downloads to complete."""
    selenium_queue.join()

def process_file(file_path, index, total_files, file_handler, selenium_handlers, 
                yt_dlp_handler, sync_handler, skip_private=False, skip_sync=False):
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
    if not selenium_threads:
        start_selenium_threads(selenium_handlers, file_handler, yt_dlp_handler)
    
    try:
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
        
        # First process all videos in batches
        if video_urls:
            print(f"\nProcessing {len(video_urls)} videos:")
            
            # Convert set to list for batch processing
            video_urls_list = sorted(list(video_urls))
            
            # Process in batches using yt_dlp_handler's max_concurrent setting
            batch_size = yt_dlp_handler.max_concurrent
            for i in range(0, len(video_urls_list), batch_size):
                batch = video_urls_list[i:i + batch_size]
                print(f"\nBatch {(i//batch_size)+1} of {(len(video_urls_list)-1)//batch_size + 1}:")
                
                # Show what's being processed
                for idx, url in enumerate(batch, 1):
                    print(f"\t{idx}. {url}")
                
                try:
                    # Process batch with yt-dlp
                    results = yt_dlp_handler.process_url_batch(batch, output_folder)
                    
                    # Handle results
                    for url, (success, error_msg) in results.items():
                        if success:
                            file_handler.log_successful_download(url, collection_name)
                        else:
                            # Skip selenium for private videos and just log them
                            if error_msg == "private":
                                print(f"\t  ❌\tPrivate video: {url}")
                                file_handler.log_error(url, error_file_path, is_private=True)
                            else:
                                # Queue failed downloads for selenium processing with error message
                                queue_selenium_download(url, collection_name, error_msg, output_folder)
                except Exception as e:
                    print(f"\t  ❌\tBatch processing failed: {str(e)}")
                    # Queue all unhandled URLs in the batch for selenium processing
                    for url in batch:
                        if not file_handler.is_url_downloaded(url):
                            queue_selenium_download(url, collection_name, str(e), output_folder)
        
        # Then process all photos
        if photo_urls:
            print("\nProcessing all photos:")
            for idx, url in enumerate(photo_urls, 1):
                print(f"\tPhoto {idx} of {len(photo_urls)}: {url}")
                # Queue photo downloads for selenium processing
                queue_selenium_download(url, collection_name, "photo", output_folder)
                
        # Wait for all selenium downloads to complete before returning
        print("\nWaiting for queued downloads to complete...")
        wait_for_selenium_queue()
        
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
                    print(f"\t-> Photo URL detected, using Selenium")
                    for handler in selenium_handlers:
                        handler.download_with_selenium(url, output_folder, file_handler)
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
                        for handler in selenium_handlers:
                            try:
                                handler.download_with_selenium(url, output_folder, file_handler)
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