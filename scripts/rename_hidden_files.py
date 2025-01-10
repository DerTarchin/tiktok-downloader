import os
import sys
import subprocess

def rename_hidden_files(directory, handle_remote=False, dry_run=False):
    """
    Recursively walk through directory and rename files starting with '.'
    except for .DS_Store files. Can also handle remote files if specified.
    If dry_run is True, only show what changes would be made without actually renaming.
    """
    files_renamed = 0  # Initialize counter
    
    # Handle local files
    for root, dirs, files in os.walk(directory):
        for filename in files:
            # Skip .DS_Store files
            if filename == '.DS_Store':
                continue
                
            # Check if filename starts with '.'
            if filename.startswith('.'):
                old_path = os.path.join(root, filename)
                # Create new filename by prepending underscore
                new_filename = "_" + filename
                new_path = os.path.join(root, new_filename)
                
                try:
                    if dry_run:
                        print(f"Would rename: {old_path} -> {new_path}")
                        files_renamed += 1
                    else:
                        os.rename(old_path, new_path)
                        files_renamed += 1  # Increment counter
                        print(f"Renamed: {old_path} -> {new_path}")
                except OSError as e:
                    print(f"Error renaming {old_path}: {e}")
    
    # Handle remote files if requested
    if handle_remote:
        try:
            # Get username from directory path
            username = os.path.basename(directory)
            remote_path = f"gdrive:/TikTok Archives/{username}"
            
            # List remote files
            cmd = ["rclone", "lsf", remote_path, "--recursive", "--include", ".*"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                remote_files = result.stdout.splitlines()
                
                for remote_file in remote_files:
                    if remote_file.endswith('.DS_Store'):
                        continue
                        
                    # Get just the filename part
                    filename = os.path.basename(remote_file)
                    if filename.startswith('.'):
                        old_remote_path = os.path.join(remote_path, remote_file)
                        # Create new path with underscore prefix on filename only
                        new_remote_path = os.path.join(remote_path, os.path.dirname(remote_file), "_" + filename)
                        
                        if dry_run:
                            print(f"Would rename remote: {old_remote_path} -> {new_remote_path}")
                            files_renamed += 1
                        else:
                            # Rename remote file
                            cmd = ["rclone", "moveto", old_remote_path, new_remote_path]
                            result = subprocess.run(cmd, capture_output=True, text=True)
                            
                            if result.returncode == 0:
                                files_renamed += 1
                                print(f"Renamed remote: {old_remote_path} -> {new_remote_path}")
                            else:
                                print(f"Error renaming remote file {old_remote_path}: {result.stderr}")
            else:
                print(f"Error listing remote files: {result.stderr}")
                
        except Exception as e:
            print(f"Error handling remote files: {e}")
    
    return files_renamed  # Add return statement

def main():
    # Get directory from command line args or use current directory
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
        if not os.path.isdir(target_dir):
            print(f"Error: '{target_dir}' is not a valid directory")
            return
    else:
        target_dir = os.getcwd()
    
    # Check if this is a dry run
    dry_run = len(sys.argv) > 2 and sys.argv[2].lower() in ('--dry-run', '-n')
    
    print(f"Starting to rename hidden files in: {target_dir}")
    print("Note: .DS_Store files will be skipped")
    print("Processing both local and remote files")
    if dry_run:
        print("DRY RUN: No files will actually be renamed")
    
    files_renamed = rename_hidden_files(target_dir, handle_remote=True, dry_run=dry_run)
    if dry_run:
        print(f"\nDry run completed. Would rename {files_renamed} files")
    else:
        print(f"\nOperation completed. Renamed {files_renamed} files")

if __name__ == "__main__":
    main() 