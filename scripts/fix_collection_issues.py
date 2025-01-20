#!/usr/bin/env python3

import os
import sys
import subprocess
import shutil

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import argparse
from downloader.validator import Validator
from downloader.utils import extract_video_id
from downloader.file_handler import FileHandler

def move_video(src_path, dest_path, video_id, is_remote=False):
    """Move a video file from source to destination path."""
    if is_remote:
        # For remote files, use rclone moveto
        cmd = ["rclone", "moveto", src_path, dest_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    else:
        # For local files, use shutil.move
        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.move(src_path, dest_path)
            return True
        except Exception:
            return False

def delete_video(path, is_remote=False):
    """Delete a video file."""
    if is_remote:
        # For remote files, use rclone delete
        cmd = ["rclone", "delete", path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    else:
        # For local files, use os.remove
        try:
            os.remove(path)
            return True
        except Exception:
            return False

def remove_from_success_log(success_log_path, video_id):
    """Remove all instances of a video ID from the success log."""
    if not os.path.exists(success_log_path):
        return
    
    temp_path = success_log_path + '.tmp'
    removed = False
    
    try:
        with open(success_log_path, 'r') as f_in, open(temp_path, 'w') as f_out:
            for line in f_in:
                url = line.strip()
                if url and extract_video_id(url) != video_id:
                    f_out.write(line)
                else:
                    removed = True
        
        if removed:
            os.replace(temp_path, success_log_path)
        else:
            os.remove(temp_path)
    except Exception as e:
        print(f"Error updating success log: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)

def move_videos_batch(moves, is_remote=False, batch_size=40):
    """Move multiple video files in a batch. Returns a dict of {video_id: success_bool}."""
    if not moves or not is_remote:
        return {}
    
    results = {}
    total_batches = (len(moves) + batch_size - 1) // batch_size
    
    print(f"\nProcessing {len(moves):,} moves in {total_batches:,} batches of up to {batch_size:,} files each...")
    
    # Process moves in batches
    for batch_num, i in enumerate(range(0, len(moves)), 1):
        batch_items = list(moves.items())[i:i + batch_size]
        print(f"\nProcessing batch {batch_num:,}/{total_batches:,} ({len(batch_items):,} files)...")
        
        # Process all files using individual moveto commands
        for video_id, (src_path, dest_path) in batch_items:
            print(f"Moving: {src_path}\n\t-> {dest_path}")
            
            # Escape special characters in paths for rclone
            escaped_src = src_path.replace("[", "\\[").replace("]", "\\]").replace("{", "\\{").replace("}", "\\}")
            escaped_dest = dest_path.replace("[", "\\[").replace("]", "\\]").replace("{", "\\{").replace("}", "\\}")
            
            cmd = ["rclone", "moveto", escaped_src, escaped_dest]
            result = subprocess.run(cmd, capture_output=True, text=True)
            success = result.returncode == 0
            results[video_id] = success
            print(f"{'✓' if success else '✗'} Move {'succeeded' if success else 'failed'}")
            if not success:
                print("Error output:", result.stderr)
    
    print(f"\nBatch processing complete. {sum(results.values()):,} successful, {len(results) - sum(results.values()):,} failed")
    return results

def main():
    parser = argparse.ArgumentParser(description='Validate and fix TikTok downloads')
    parser.add_argument('input_path', help='Path to the directory containing collections')
    parser.add_argument('--gdrive-base-path', default='gdrive:/TikTok Archives',
                      help='Base path in Google Drive (default: gdrive:/TikTok Archives)')
    parser.add_argument('--dry-run', action='store_true',
                      help='Show what would be done without making changes')
    parser.add_argument('--skip-move', action='store_true',
                      help='Skip moving videos to fix missing entries, just delete extras')
    parser.add_argument('--delete-extra', action='store_true',
                      help='Delete extra videos found in remote storage')

    args = parser.parse_args()

    if not os.path.isdir(args.input_path):
        print(f"Error: {args.input_path} is not a directory")
        sys.exit(1)

    validator = Validator(gdrive_base_path=args.gdrive_base_path)
    file_handler = FileHandler(args.input_path)
    results = validator.validate_downloads(args.input_path)
    
    if not results['missing'] and not results['extra'] and not results['empty']:
        print("\nNo issues found. All collections are valid.")
        return

    print("\nProcessing validation results...")
    
    # Track videos that need to be moved
    videos_to_move = {}  # {video_id: (from_collection, to_collection)}
    
    # First pass: identify videos that can be moved to fix missing entries
    if not args.skip_move:  # Only process moves if --skip-move is not set
        for collection, missing_ids in results['missing'].items():
            for video_id in missing_ids:
                # Check if this missing video exists as an extra in another collection
                for other_collection, extra_videos in results['extra'].items():
                    if video_id in extra_videos:
                        videos_to_move[video_id] = (other_collection, collection)
                        break

    # Calculate total videos to process
    total_videos = (
        (len(videos_to_move) if not args.skip_move else 0) + 
        sum(len(videos) for videos in results['extra'].values()) +
        sum(len(videos) for videos in results['empty'].values())
    )
    videos_processed = 0
    last_percentage = -1  # Track last printed percentage to avoid duplicates

    def update_progress():
        nonlocal videos_processed, last_percentage
        videos_processed += 1
        if total_videos > 0:  # Only calculate percentage if we have videos to process
            current_percentage = (videos_processed * 100) // total_videos
            if current_percentage % 5 == 0 and current_percentage != last_percentage:
                print(f"\nProgress: {current_percentage}% ({videos_processed:,}/{total_videos:,} videos processed)")
                last_percentage = current_percentage

    print(f"\nStarting to process {total_videos:,} videos...")

    # Process moves first
    pending_moves = {}  # {video_id: (src_path, dest_path)}
    
    for video_id, (from_collection, to_collection) in videos_to_move.items():
        # Get the filename from the extra videos map
        filename = results['extra'][from_collection][video_id].split(' ', 1)[1]
        is_remote = results['extra'][from_collection][video_id].startswith('(remote)')
        
        # Construct paths
        if is_remote:
            from_path = f"{args.gdrive_base_path}/{os.path.basename(args.input_path)}/{from_collection}/{filename}"
            to_path = f"{args.gdrive_base_path}/{os.path.basename(args.input_path)}/{to_collection}/{filename}"
            pending_moves[video_id] = (from_path, to_path)
        else:
            from_path = os.path.join(args.input_path, from_collection, filename)
            to_path = os.path.join(args.input_path, to_collection, filename)
            if not args.dry_run:
                if move_video(from_path, to_path, video_id, False):
                    print(f"Successfully moved video {video_id}")
                    del results['extra'][from_collection][video_id]
                else:
                    print(f"Failed to move video {video_id}")
                update_progress()

    # Process remote moves in batches
    if pending_moves and not args.dry_run:
        move_results = move_videos_batch(pending_moves, is_remote=True)
        
        for video_id, success in move_results.items():
            if success:
                print(f"Successfully moved video {video_id}")
                from_collection = videos_to_move[video_id][0]
                del results['extra'][from_collection][video_id]
            else:
                print(f"Failed to move video {video_id}")
            update_progress()

    # Process remaining extra videos (delete them)
    for collection, extra_videos in results['extra'].items():
        for video_id, file_info in extra_videos.items():
            if video_id in videos_to_move:  # Skip if we moved this video
                continue
                
            if  not args.delete_extra:
                print(f"Skipping extra video {video_id} from {collection} (use --delete-extra to delete)")
                update_progress()
                continue

            print(f"Deleting extra video {video_id} from {collection}")
            filename = file_info.split(' ', 1)[1]  # Remove (local) or (remote) prefix
            is_remote = file_info.startswith('(remote)')  # Define is_remote based on file_info prefix
            
            if is_remote:
                path = f"{args.gdrive_base_path}/{os.path.basename(args.input_path)}/{collection}/{filename}"
            else:
                path = os.path.join(args.input_path, collection, filename)
            
            if not args.dry_run:
                if delete_video(path, is_remote):
                    print(f"Successfully deleted video {video_id}")
                else:
                    print(f"Failed to delete video {video_id}")
                update_progress()

    # Process remaining missing videos (remove from success log)
    for collection, missing_ids in results['missing'].items():
        for video_id in missing_ids:
            if video_id not in videos_to_move:  # Skip if we found this video in another collection
                print(f"Removing video {video_id} from download success log")
                if not args.dry_run:
                    remove_from_success_log(file_handler.success_log_path, video_id)

    # Process empty videos (remove from success log)
    for collection, empty_files in results['empty'].items():
        for video_id, file_info in empty_files.items():
            print(f"Removing empty video {video_id} from download success log and deleting file")
            if not args.dry_run:
                # Determine the path and whether it's remote
                is_remote = file_info.startswith('(remote)')
                filename = file_info.split(' ', 1)[1]  # Remove (local) or (remote) prefix
                
                if is_remote:
                    path = f"{args.gdrive_base_path}/{os.path.basename(args.input_path)}/{collection}/{filename}"
                else:
                    path = os.path.join(args.input_path, collection, filename)
                
                # First delete the empty file
                if delete_video(path, is_remote):
                    print(f"Successfully deleted empty video {video_id}")
                else:
                    print(f"Failed to delete empty video {video_id}")
                # Then remove from success log
                remove_from_success_log(file_handler.success_log_path, video_id)
                update_progress()

    if args.dry_run:
        print("\nThis was a dry run. No changes were made.")
    else:
        print("\nFinished processing all issues.")
        
        # Run validation again to show final state
        print("\nRunning final validation check...")
        final_results = validator.validate_downloads(args.input_path)
        
        if not final_results['missing'] and not final_results['extra'] and not final_results['empty']:
            print("\n✓ All issues have been resolved. Collections are now valid.")
        else:
            print("\n! Some issues could not be resolved:")
            if final_results['missing']:
                print("\nStill missing videos:")
                for collection, missing_ids in final_results['missing'].items():
                    print(f"\n{collection}:")
                    for video_id in missing_ids:
                        print(f"  - {video_id}")
            if final_results['extra']:
                print("\nStill have extra videos:")
                for collection, extra_videos in final_results['extra'].items():
                    print(f"\n{collection}:")
                    for video_id, file_info in extra_videos.items():
                        print(f"  - {video_id} ({file_info})")
            if final_results['empty']:
                print("\nStill have empty (zero-byte) files:")
                for collection, empty_files in final_results['empty'].items():
                    print(f"\n{collection}:")
                    for video_id, file_info in empty_files.items():
                        print(f"  - {video_id} ({file_info})")

if __name__ == '__main__':
    main() 