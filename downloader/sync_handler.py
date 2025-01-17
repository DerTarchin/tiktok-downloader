"""Google Drive sync functionality."""

import os
import subprocess
import threading
from queue import Queue
import shlex
from urllib.parse import quote

class SyncHandler:
    def __init__(self):
        self.sync_queue = Queue()
        self.sync_thread = None
        self.gdrive_base_path = "gdrive:/TikTok Archives"
        self.rclone_modifiers = [
            "--transfers=20",
            "--drive-chunk-size=256M",
            "--exclude=.DS_Store",
            "-P"
        ]

    def start_sync_thread(self):
        """Start the background sync thread if not already running"""
        if self.sync_thread is None:
            self.sync_thread = threading.Thread(target=self._background_sync_worker, daemon=True)
            self.sync_thread.start()

    def stop_sync_thread(self):
        """Stop the background sync thread"""
        if self.sync_thread is not None:
            self.sync_queue.put(None)  # Poison pill
            self.sync_thread.join()
            self.sync_thread = None

    def queue_sync(self, local_path, username):
        """Queue a folder for syncing"""
        self.sync_queue.put((local_path, username))

    def wait_for_syncs(self, show_progress=True):
        """
        Wait for all queued sync operations to complete
        
        Args:
            show_progress: Whether to show live progress output for remaining syncs
        """
        # Store current queue size
        remaining = self.sync_queue.qsize()
        if remaining > 0:
            print(f"\n>> Waiting for {remaining} sync operations to complete...")
            
            # Create a list to track tasks that need to be requeued
            tasks = []
            while not self.sync_queue.empty():
                task = self.sync_queue.get()
                if task is not None:  # Don't store the poison pill
                    tasks.append(task)
                self.sync_queue.task_done()
            
            # Stop existing thread
            self.stop_sync_thread()
            
            # Process tasks with progress
            for task in tasks:
                local_path, username = task
                folder_name = os.path.basename(local_path)
                remote_path = f"{self.gdrive_base_path}/{username}/{folder_name}"
                
                try:
                    # Run sync with progress output
                    self._run_rclone_sync(local_path, remote_path, folder_name, show_progress=True)
                    # Delete the folder after successful sync
                    if os.path.exists(local_path):
                        import shutil
                        shutil.rmtree(local_path)
                        print(f">> Deleted local folder: {folder_name}")
                except Exception as e:
                    print(f">> Error syncing {folder_name}: {str(e)}")
            
            # Restart the sync thread for any future tasks
            self.start_sync_thread()

    def _background_sync_worker(self):
        """
        Worker thread that processes sync requests from the queue.
        Runs continuously until receiving None as poison pill.
        """
        while True:
            task = self.sync_queue.get()
            if task is None:  # Poison pill to stop the thread
                break
                
            local_path, username = task
            self._sync_and_delete_folder(local_path, username)
            self.sync_queue.task_done()

    def _run_rclone_sync(self, local_path, remote_path, folder_name=None, show_progress=False):
        """
        Helper function to run rclone copy (not sync) with error handling.
        
        Args:
            local_path: Path to local folder to copy
            remote_path: Remote Google Drive path to copy to
            folder_name: Optional name of folder for logging purposes
            show_progress: Whether to show live progress output
            
        Returns:
            bool: True if copy was successful, False otherwise
            
        Raises:
            RuntimeError: If the source directory doesn't exist or other rclone errors occur
        """
        # First verify the source directory exists
        if not os.path.exists(local_path):
            error_msg = f"Source directory not found: {local_path}"
            print(f">> Error: {error_msg}")
            raise RuntimeError(error_msg)
            
        # Skip empty folders
        if not os.listdir(local_path):
            print(f">> Skipping empty folder: {folder_name}")
            return True
            
        # Escape paths with special characters
        escaped_local_path = shlex.quote(local_path)
        escaped_remote_path = shlex.quote(remote_path)
        
        cmd = [
            "rclone",
            "copy",
            escaped_local_path,
            escaped_remote_path,
        ] + self.rclone_modifiers
        
        try:
            cmd_str = " ".join(cmd)
            if show_progress:
                # Show live output
                result = subprocess.run(cmd_str, shell=True, check=True)
            else:
                # Capture output during normal processing
                result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, check=True)
            
            print(f">> Successfully copied: {folder_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = f"rclone error copying{' folder ' + folder_name if folder_name else ''}"
            if not show_progress and hasattr(e, 'stderr'):
                error_msg += f": {e.stderr}"
            print(f">> Error: {error_msg}")
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"Error during copy{' of ' + folder_name if folder_name else ''}: {str(e)}"
            print(f">> Error: {error_msg}")
            raise RuntimeError(error_msg) from e

    def _sync_and_delete_folder(self, local_path, username):
        """
        Sync folder to Google Drive and delete local copy if successful.
        
        Args:
            local_path: Path to local folder to sync
            username: Username for remote path construction
            
        Returns:
            bool: True if sync and delete were successful, False otherwise
        """
        # Skip if path components are invalid
        if not local_path or not username or local_path == os.path.dirname(local_path):
            print(f">> Skipping invalid path: {local_path}")
            return True
            
        # Skip if folder doesn't exist
        if not os.path.exists(local_path):
            print(f">> Skipping non-existent folder: {os.path.basename(local_path)}")
            return True
            
        folder_name = os.path.basename(local_path)
        remote_path = f"{self.gdrive_base_path}/{username}/{folder_name}"
        
        # Skip empty folders
        if not os.listdir(local_path):
            print(f">> Skipping empty folder: {folder_name}")
            try:
                import shutil
                shutil.rmtree(local_path)
                print(f">> Deleted empty local folder: {folder_name}")
                return True
            except Exception as e:
                print(f">> Error deleting empty folder {folder_name}: {e}")
                return False
        
        # Add check and rename for files starting with period or space
        was_renamed = False  # Initialize the variable
        for filename in os.listdir(local_path):
            was_renamed = False  # Reset for each file
            if filename.startswith('.'):
                new_filename = '_' + filename
                was_renamed = True
            elif filename.startswith(' '):
                new_filename = filename.lstrip()
                was_renamed = True
            if was_renamed:
                old_path = os.path.join(local_path, filename)
                new_path = os.path.join(local_path, new_filename)
                try:
                    os.rename(old_path, new_path)
                except Exception as e:
                    print(f">> Error renaming file {filename}: {e}")
        
        print(f">> Starting sync of {folder_name}...")
        if self._run_rclone_sync(local_path, remote_path, folder_name):
            try:
                import shutil
                shutil.rmtree(local_path)
                print(f">> Deleted local folder: {folder_name}")
                return True
            except Exception as e:
                print(f">> Error deleting folder {folder_name}: {e}")
                return False
        return False

    def sync_remaining_files(self, input_path):
        """
        Sync remaining files (text files, logs) without deleting remote folders.
        
        Args:
            input_path: Path containing files to sync
        """
        username = os.path.basename(input_path)
        remote_path = f"{self.gdrive_base_path}/{username}"

        # Track if we have any queued tasks
        has_queued_tasks = False

        # Queue each folder corresponding to a text file
        for file in os.listdir(input_path):
            if file.endswith('.txt'):
                # Get folder name from file name, handling multiple extensions
                folder_name = file.rsplit('.', 1)[0]  # Split on the last dot
                folder_path = os.path.join(input_path, folder_name)
                if os.path.isdir(folder_path):
                    self.queue_sync(folder_path, username)
                    has_queued_tasks = True
        
        # Only wait for syncs if we actually queued any tasks
        if has_queued_tasks:
            print(">> Waiting for folder syncs to complete...")
            self.wait_for_syncs(show_progress=True)
        
        # Sync text files and logs using copy to preserve remote folders
        escaped_input_path = shlex.quote(input_path)
        escaped_remote_path = shlex.quote(remote_path)
        
        cmd = [
            "rclone", "copy",  # Using copy instead of sync to preserve remote folders
            escaped_input_path,
            escaped_remote_path,
            "--filter", '"+ *.txt"',  # Only sync text files and logs
            "--filter", '"+ *.log"',
            "--filter", '"- geckodriver.log"',  # Exclude geckodriver.log specifically
            "--filter", '"- *"',  # Exclude everything else
        ] + self.rclone_modifiers
        
        cmd_str = " ".join(cmd)

        try:
            # Always show progress for final sync
            process = subprocess.run(cmd_str, shell=True, check=True, timeout=300)  # 5 minute timeout
            print(">> Successfully synced remaining files to Google Drive")
        except subprocess.TimeoutExpired:
            print(">> Error: Final sync timed out after 5 minutes")
        except subprocess.CalledProcessError as e:
            print(f">> Error syncing remaining files: {str(e)}")
        except Exception as e:
            print(f">> Unexpected error during final sync: {str(e)}")
            
        # No need for a final wait since we already waited for queued tasks
        # and the rclone command is synchronous
        
        