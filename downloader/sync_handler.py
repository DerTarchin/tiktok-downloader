"""Google Drive sync functionality."""

import os
import subprocess
import threading
from queue import Queue

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

    def wait_for_syncs(self):
        """Wait for all queued sync operations to complete"""
        self.sync_queue.join()

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

    def _run_rclone_sync(self, local_path, remote_path, folder_name=None):
        """
        Helper function to run rclone copy (not sync) with error handling.
        
        Args:
            local_path: Path to local folder to copy
            remote_path: Remote Google Drive path to copy to
            folder_name: Optional name of folder for logging purposes
            
        Returns:
            bool: True if copy was successful, False otherwise
        """
        cmd = [
            "rclone", "copy",  # Changed from sync to copy
            local_path,
            remote_path,
        ] + self.rclone_modifiers
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f">> Error copying{' folder ' + folder_name if folder_name else ''}: {result.stderr}")
                return False
            else:
                print(f">> Successfully copied: {folder_name}")
                return True
        except Exception as e:
            print(f">> Error during copy{' of ' + folder_name if folder_name else ''}: {e}")
            return False

    def _sync_and_delete_folder(self, local_path, username):
        """
        Sync folder to Google Drive and delete local copy if successful.
        
        Args:
            local_path: Path to local folder to sync
            username: Username for remote path construction
            
        Returns:
            bool: True if sync and delete were successful, False otherwise
        """
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
        
        # Sync using copy to preserve remote folders
        cmd = [
            "rclone", "copy",  # Using copy instead of sync to preserve remote folders
            input_path,
            remote_path,
            "--include", "*.txt",  # Only sync text files and logs
            "--include", "*.log",
        ] + self.rclone_modifiers
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f">> Error syncing remaining files: {result.stderr}")
        else:
            print(">> Successfully synced remaining files to Google Drive") 