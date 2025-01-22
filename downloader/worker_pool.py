"""Worker thread management for TikTok downloader."""

import threading
from queue import Queue
from .utils import extract_video_id, log_worker

class WorkerPool:
    """Manages a pool of worker threads for downloading content."""
    
    def __init__(self):
        # Queue for failed yt-dlp downloads that need selenium processing
        self.selenium_queue = Queue()
        self.selenium_threads = []
        self.selenium_thread_stop = threading.Event()
        self.selenium_total_items = 0
        self.selenium_processed_items = 0
        self.selenium_counter_lock = threading.Lock()

        # Queue for yt-dlp downloads
        self.yt_dlp_queue = Queue()
        self.yt_dlp_threads = []
        self.yt_dlp_thread_stop = threading.Event()
        self.yt_dlp_total_items = 0
        self.yt_dlp_processed_items = 0
        self.yt_dlp_counter_lock = threading.Lock()
        self.yt_dlp_result_lock = threading.Lock()

    def log_selenium_worker(self, worker_num, message):
        """Log a message for a selenium worker."""
        log_worker("SL", worker_num, message)

    def log_yt_dlp_worker(self, worker_num, message):
        """Log a message for a yt-dlp worker."""
        log_worker("YT", worker_num, message)

    def selenium_worker(self, selenium_handler, file_handler, yt_dlp_handler, worker_num):
        """Worker thread that processes failed yt-dlp downloads using Selenium."""
        while not self.selenium_thread_stop.is_set():
            try:
                # Get next item from queue with timeout to allow checking stop flag
                try:
                    url, collection_name, error_msg, output_folder = self.selenium_queue.get(timeout=1)
                except:
                    continue
                    
                try:
                    error_file_path = file_handler.get_error_log_path(output_folder)
                    
                    # Update progress counter
                    with self.selenium_counter_lock:
                        self.selenium_processed_items += 1
                        current = self.selenium_processed_items
                        total = self.selenium_total_items
                        self.log_selenium_worker(worker_num, f"{current:,} of {total:,}: {url}")
                    
                    # Handle different error types
                    if error_msg == "private":
                        self.log_selenium_worker(worker_num, f"Private video: {url}")
                        file_handler.log_error(url, error_file_path, is_private=True)
                        continue  # Skip selenium attempt but let finally block handle task_done
                        
                    try:
                        selenium_handler.download_with_selenium(url, output_folder, file_handler, collection_name)
                        file_handler.log_successful_download(url, collection_name)
                    except Exception as e:
                        if str(e) == "private":
                            self.log_selenium_worker(worker_num, f"❌\tPrivate video: {url}")
                            file_handler.log_error(url, error_file_path, is_private=True)
                        else:
                            self.log_selenium_worker(worker_num, f"❌\t[{extract_video_id(url)}] Selenium failed:\n{str(e)}")
                            file_handler.log_error(url, error_file_path)
                            
                except Exception as e:
                    self.log_selenium_worker(worker_num, f"❌\tSelenium worker error for {url}: {str(e)}")
                    error_file_path = file_handler.get_error_log_path(output_folder)
                    file_handler.log_error(url, error_file_path)
                finally:
                    self.selenium_queue.task_done()  # Only call task_done once, in finally block
                    # Reset counters if queue is empty after processing this item
                    if self.selenium_queue.empty():
                        with self.selenium_counter_lock:
                            self.selenium_processed_items = 0
                            self.selenium_total_items = 0
            except Exception as e:
                self.log_selenium_worker(worker_num, f"❌\tSelenium worker error: {str(e)}")

    def yt_dlp_worker(self, yt_dlp_handler, file_handler, worker_num, verbose=False):
        """Worker thread that processes downloads from the yt-dlp queue."""
        while not self.yt_dlp_thread_stop.is_set():
            try:
                # Get next item from queue with timeout to allow checking stop flag
                try:
                    url, output_folder, collection_name, callback = self.yt_dlp_queue.get(timeout=1)
                except:
                    continue
                    
                try:
                    # Update progress counter
                    with self.yt_dlp_counter_lock:
                        self.yt_dlp_processed_items += 1
                        current = self.yt_dlp_processed_items
                        total = self.yt_dlp_total_items
                        self.log_yt_dlp_worker(worker_num, f"{current:,} of {total:,}: {url}")
                    
                    success, error_msg, speed = yt_dlp_handler.try_yt_dlp(url, output_folder)
                    
                    if verbose:
                        if success:
                            self.log_yt_dlp_worker(worker_num, f"Successfully downloaded at {speed:.2f} MiB/s: {extract_video_id(url)}")
                        else:
                            # For all other errors, try selenium
                            if error_msg == "private":
                                self.log_yt_dlp_worker(worker_num, f"❌\tPrivate video: {url}")
                            elif error_msg in yt_dlp_handler.all_error_types:
                                self.log_yt_dlp_worker(worker_num, f"⚠️\t{error_msg}, using Selenium for {url}")
                            else:
                                self.log_yt_dlp_worker(worker_num, f"⚠️\tyt-dlp failed ({error_msg}), using Selenium for {url}")
                    
                    if callback:
                        callback(url, success, error_msg, speed)
                        
                except Exception as e:
                    self.log_yt_dlp_worker(worker_num, f"Error processing task: {str(e)}")
                    if callback:
                        callback(url, False, str(e), 0.0)
                finally:
                    self.yt_dlp_queue.task_done()
                    # Reset counters if queue is empty after processing this item
                    if self.yt_dlp_queue.empty():
                        with self.yt_dlp_counter_lock:
                            self.yt_dlp_processed_items = 0
                            self.yt_dlp_total_items = 0
                    
            except Exception as e:
                self.log_yt_dlp_worker(worker_num, f"Worker error: {str(e)}")

    def start_selenium_threads(self, selenium_handlers, file_handler, yt_dlp_handler):
        """Start multiple Selenium worker threads."""
        self.selenium_thread_stop.clear()
        self.selenium_processed_items = 0
        self.selenium_total_items = 0
        
        # Create and start a thread for each selenium handler
        for i, handler in enumerate(selenium_handlers, 1):
            thread = threading.Thread(
                target=self.selenium_worker,
                args=(handler, file_handler, yt_dlp_handler, i),
                daemon=True
            )
            thread.start()
            self.selenium_threads.append(thread)

    def start_yt_dlp_threads(self, yt_dlp_handler, file_handler, max_concurrent=3, verbose=False):
        """Start multiple yt-dlp worker threads."""
        self.yt_dlp_thread_stop.clear()
        self.yt_dlp_processed_items = 0
        self.yt_dlp_total_items = 0
        
        # Create and start worker threads
        for i in range(max_concurrent):
            thread = threading.Thread(
                target=self.yt_dlp_worker,
                args=(yt_dlp_handler, file_handler, i + 1, verbose),
                daemon=True
            )
            thread.start()
            self.yt_dlp_threads.append(thread)
            self.log_yt_dlp_worker(i + 1, f"Started yt-dlp worker")

    def queue_selenium_download(self, url, collection_name, error_msg, output_folder):
        """Queue a URL for selenium download and update counter."""
        with self.selenium_counter_lock:
            self.selenium_total_items += 1
        self.selenium_queue.put((url, collection_name, error_msg, output_folder))

    def queue_yt_dlp_download(self, url, output_folder, collection_name, callback=None):
        """Queue a URL for yt-dlp download and update counter."""
        with self.yt_dlp_counter_lock:
            self.yt_dlp_total_items += 1
        self.yt_dlp_queue.put((url, output_folder, collection_name, callback))

    def stop_selenium_threads(self):
        """Stop all Selenium worker threads and wait for them to finish."""
        self.selenium_thread_stop.set()
        for thread in self.selenium_threads:
            thread.join()
        self.selenium_threads.clear()

    def stop_yt_dlp_threads(self):
        """Stop all yt-dlp worker threads and wait for them to finish."""
        self.yt_dlp_thread_stop.set()
        for thread in self.yt_dlp_threads:
            thread.join()
        self.yt_dlp_threads.clear()

    def wait_for_selenium_queue(self):
        """Wait for all queued Selenium downloads to complete."""
        self.selenium_queue.join()

    def wait_for_yt_dlp_queue(self):
        """Wait for all queued yt-dlp downloads to complete."""
        self.yt_dlp_queue.join()

    def shutdown(self):
        """Stop all worker threads and clean up resources."""
        # Stop selenium threads first since they might depend on yt-dlp
        self.stop_selenium_threads()
        
        # Stop yt-dlp threads
        self.stop_yt_dlp_threads()
        
        # Clear any remaining items from queues
        while not self.selenium_queue.empty():
            try:
                self.selenium_queue.get_nowait()
                self.selenium_queue.task_done()
            except:
                pass
                
        while not self.yt_dlp_queue.empty():
            try:
                self.yt_dlp_queue.get_nowait()
                self.yt_dlp_queue.task_done()
            except:
                pass
        
        # Reset counters
        self.selenium_total_items = 0
        self.selenium_processed_items = 0
        self.yt_dlp_total_items = 0
        self.yt_dlp_processed_items = 0 