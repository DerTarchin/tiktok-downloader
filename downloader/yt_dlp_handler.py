"""yt-dlp based downloader functionality."""

import os
import subprocess
import concurrent.futures
from queue import Queue
from threading import Lock
from .utils import get_filename_suffix

MAX_FILENAME_LENGTH = 100

class YtDlpHandler:
    def __init__(self, max_concurrent=3):
        self.max_concurrent = max_concurrent
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent)
        self.download_queue = Queue()
        self.result_lock = Lock()
        self.all_error_types = ["private", "rate limited", "network", "audio only", "not video file"]
        
    def try_yt_dlp(self, url, output_folder):
        """
        Attempt to download using yt-dlp.
        
        Args:
            url: URL to download
            output_folder: Folder to save downloaded file to
            
        Returns:
            tuple: (bool success, str error_message, float speed_mbps)
            Success is True if download successful, False otherwise
            Error message indicates if video is private or audio-only
            Speed in MB/s (0 if download failed)
        """
        video_id_suffix = get_filename_suffix(url)
        download_speed = 0.0
        
        # First, check format without downloading
        check_command = [
            "yt-dlp",
            "--list-formats",
            url
        ]
        
        try:
            process = subprocess.Popen(
                check_command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            # Check for various error conditions
            if "Video not available" in stderr or "status code 10204" in stderr:
                return False, "private", 0.0
            elif "This video is private" in stderr:
                return False, "private", 0.0
            elif "Video unavailable" in stderr:
                return False, "private", 0.0
            elif "Unable to extract video data" in stderr:
                return False, "private", 0.0  # Often means video was deleted or made private
            elif "Unable to download webpage" in stderr:
                return False, "network", 0.0  # Network connectivity issues
            elif "HTTP Error 429" in stderr:
                return False, "rate limited", 0.0  # Rate limiting
                
            # Check if only audio formats are available
            if stdout and any(["audio only" in stderr.lower(), "no video formats found" in stderr.lower()]):
                return False, "audio only", 0.0
            
            # If we have video formats, proceed with download
            download_command = [
                "yt-dlp",
                "--windows-filenames",
                "--concurrent-fragments", "3",  # Enable concurrent fragment downloads
                "-o", f"{output_folder}/%(uploader)s - %(title).{MAX_FILENAME_LENGTH}B{video_id_suffix}.%(ext)s",
                url
            ]
            
            process = subprocess.Popen(
                download_command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()

            
            if process.returncode == 0:
                # Parse download speed from output
                for line in stdout.split('\n'):
                    if "[download] Destination:" in line:
                        filename = line.split("[download] Destination:", 1)[1].strip()
                        # Check if it's a video file
                        ext = os.path.splitext(filename)[1].lower()
                        if ext not in ['.mp4', '.mkv', '.webm', '.avi', '.mov']:  # Video extensions
                            # Delete non-video file
                            try:
                                os.remove(filename)
                            except OSError:
                                pass
                            return False, "not video file", 0.0
                    # Look for the final speed line that includes the total time
                    elif "[download] 100%" in line and "in" in line:
                        try:
                            # Extract speed value (format: "[download] 100% of X.XXMiB in 00:00:00 at Y.YYMiB/s")
                            speed_str = line.split("at", 1)[1].split("MiB/s")[0].strip()
                            download_speed = float(speed_str)
                        except (IndexError, ValueError):
                            pass
                return True, None, download_speed
            
            if "HTTP Error 429" in stderr:
                return False, "rate limited", 0.0
            elif any(msg in stderr for msg in ["Video not available", "This video is private", "Video unavailable", "Unable to extract video data"]):
                return False, "private", 0.0
            
            return False, stderr, 0.0

        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                return False, "rate limited", 0.0
            elif any(msg in error_str for msg in ["connection", "timeout", "network"]):
                return False, "network", 0.0
            return False, str(e), 0.0
            
    def process_url_batch(self, urls, output_folder):
        """
        Process a batch of URLs concurrently.
        
        Args:
            urls: List of URLs to download
            output_folder: Folder to save downloaded files to
            
        Returns:
            dict: Dictionary mapping URLs to their download results
        """
        futures = []
        results = {}
        total_speed = 0.0
        successful_downloads = 0
        
        # Submit all URLs to the thread pool
        for url in urls:
            future = self.thread_pool.submit(self.try_yt_dlp, url, output_folder)
            futures.append((url, future))
        
        # Collect results as they complete
        for url, future in futures:
            try:
                success, error_msg, speed = future.result()
                with self.result_lock:
                    results[url] = (success, error_msg)
                    if success:
                        total_speed += speed
                        successful_downloads += 1
            except Exception as e:
                with self.result_lock:
                    results[url] = (False, str(e))
        
        # Print average download speed if there were successful downloads
        if successful_downloads > 0:
            avg_speed = total_speed / successful_downloads
            print(f"\nAverage download speed for batch: {avg_speed:.2f} MiB/s")
        
        return results
        
    def shutdown(self):
        """Cleanup thread pool resources"""
        self.thread_pool.shutdown(wait=True) 