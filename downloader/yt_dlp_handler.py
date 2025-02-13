"""yt-dlp based downloader functionality."""

import os
import subprocess
from threading import Lock
from .utils import get_filename_suffix, MAX_FILENAME_LENGTH


class YtDlpHandler:
    def __init__(self):
        self.all_error_types = ["private", "rate limited", "network", "audio only", "not video file", "vpn blocked"]
        
        # Add counters for VPN blocks and successful downloads
        self.vpn_block_count = 0
        self.successful_download_count = 0
        self.vpn_block_threshold = 5  # Ask for user input after this many consecutive blocks
        self.success_reset_threshold = 10  # Reset VPN block count after this many consecutive successes

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
                if "HTTP Error 403: Forbidden" in stderr:
                    # VPN IP has been blocked
                    self.vpn_block_count += 1
                    self.successful_download_count = 0  # Reset success counter
                    
                    if self.vpn_block_count >= self.vpn_block_threshold:
                        input("\n>> Network error disconnected, press enter to continue...")
                        self.vpn_block_count = 0  # Reset block counter after user input
                    else:
                        print(f"\n>> VPN block detected ({self.vpn_block_count}/{self.vpn_block_threshold})")
                        
                    return False, "vpn blocked", 0.0
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

                # Increment successful download counter and check if we should reset VPN block count
                self.successful_download_count += 1
                if self.successful_download_count >= self.success_reset_threshold:
                    if self.vpn_block_count > 0:
                        print(f"\n>> Resetting VPN block counter after {self.success_reset_threshold} successful downloads")
                    self.vpn_block_count = 0
                    self.successful_download_count = 0
                
                return True, None, download_speed
            
            if "HTTP Error 429" in stderr:
                return False, "rate limited", 0.0
            elif "HTTP Error 403: Forbidden" in stderr:
                # VPN IP has been blocked
                self.vpn_block_count += 1
                self.successful_download_count = 0  # Reset success counter
                
                if self.vpn_block_count >= self.vpn_block_threshold:
                    input("\n>> Network error disconnected, press enter to continue...")
                    self.vpn_block_count = 0  # Reset block counter after user input
                else:
                    print(f"\n>> VPN block detected ({self.vpn_block_count}/{self.vpn_block_threshold})")
                    
                return False, "vpn blocked", 0.0
            elif any(msg in stderr for msg in ["Video not available", "This video is private", "Video unavailable", "Unable to extract video data"]):
                return False, "private", 0.0

            return False, stderr, 0.0

        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                return False, "rate limited", 0.0
            elif "403" in error_str:
                # VPN IP has been blocked
                self.vpn_block_count += 1
                self.successful_download_count = 0  # Reset success counter
                
                if self.vpn_block_count >= self.vpn_block_threshold:
                    input("\n>> Network error disconnected, press enter to continue...")
                    self.vpn_block_count = 0  # Reset block counter after user input
                else:
                    print(f"\n>> VPN block detected ({self.vpn_block_count}/{self.vpn_block_threshold})")
                    
                return False, "vpn blocked", 0.0
            elif any(msg in error_str for msg in ["connection", "timeout", "network"]):
                return False, "network", 0.0
            return False, str(e), 0.0

    def shutdown(self):
        """Cleanup resources"""
        pass  # No cleanup needed anymore since workers moved to file_processor.py 