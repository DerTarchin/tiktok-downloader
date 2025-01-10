# TikTok Video Downloader

A collection of tools to download TikTok videos and photos. This toolkit consists of three main components:

## get_urls.js

A browser-based script to extract TikTok video/photo URLs from a page. This script automatically scrolls through a TikTok page (like your favorites or a user's profile) and collects all video/photo URLs.

### How to Use get_urls.js:

1. Copy the contents of `get_urls.js` or `get_urls.min.js`
2. Open the TikTok page you want to extract URLs from (e.g., your favorites page, a user's profile)
3. Open your browser's developer console (usually F12 or right-click -> Inspect -> Console)
4. Paste the script and press Enter
5. The script will:
   - Automatically scroll through the page
   - Collect all video/photo URLs
   - Download a text file named after the page title (e.g., "Favorites.txt")

## parse_urls.py

A Python script that extracts clean URLs from text files. It can process multiple input files and combine all URLs into a single output file.

### How to Use parse_urls.py:

```bash
# Process a single file
python scripts/parse_urls.py input_file.txt

# Process multiple files
python scripts/parse_urls.py file1.txt file2.txt file3.txt
```

The script will:

- Read all input files
- Extract URLs from each file
- Combine all unique URLs into a single output file (`combined_urls.txt`)
- Save the output file in the same directory as the first input file
- Show progress and statistics for each processed file

## Video Downloader (main.py)

The main downloader script that downloads TikTok videos and photos using both yt-dlp and Selenium as a fallback. The code is now organized in a modular structure for better maintainability.

### Project Structure:

```
.
├── main.py                    # Main script with argument parsing and high-level flow
└── downloader/               # Package directory
    ├── __init__.py           # Package initialization
    ├── utils.py              # Common utility functions
    ├── file_handler.py       # File operations and logging
    ├── selenium_handler.py   # Selenium-based downloader
    ├── yt_dlp_handler.py     # yt-dlp based downloader
    ├── sync_handler.py       # Google Drive sync functionality
    └── validator.py          # Download validation functionality
```

### Requirements:

- Python 3.x
- Firefox browser (geckodriver)
- yt-dlp
- selenium
- webdriver_manager

### How to Use:

Basic usage:

```bash
# Download from a single file
python main.py path/to/urls.txt

# Download from all .txt files in a directory
python main.py path/to/directory
```

Advanced options:

```bash
# Retry failed downloads only
python main.py path/to/directory --errors-only

# Disable headless mode (show browser)
python main.py path/to/directory --disable-headless

# Split uncategorized videos into groups
python main.py path/to/directory --split-uncategorized

# Combine flags
python main.py path/to/directory --disable-headless --split-uncategorized
```

The script will:

1. Create a folder with the same name as the input file
2. Try to download each video/photo using yt-dlp first
3. If yt-dlp fails, try using Selenium with musicaldown.com
4. Save successful downloads to the created folder
5. Create error logs for failed downloads
6. Track successful downloads to avoid duplicates

### Features:

- Handles both videos and photos
- Automatically retries failed downloads
- Maintains a log of successful downloads
- Creates organized folders for each collection
- Supports batch processing of multiple files
- Handles duplicate URLs across collections
- Modular code structure for better maintainability
- Automatic Google Drive synchronization
- Download validation and reporting

## Uploading videos to Google Drive

The script now handles Google Drive synchronization automatically, but you can also manually sync using:

```bash
# delete remote files as well if they dont exist locally
rclone sync /path/to/mac/folder "gdrive:/TikTok Archives/<username>" --transfers=20 --drive-chunk-size=256M -P
# copies only net-new files
rclone copy /path/to/mac/folder "gdrive:/TikTok Archives/<username>" --transfers=20 --drive-chunk-size=256M -P
```

_Note: 20 transfers and 256M chunks are maximum values. 20 \* 256 = 5GB of RAM required, and sufficient enough network speeds_

## Legacy Version

The original script (`dl_vids.py`) is kept as a backup and provides the same functionality in a single file. You can use it the same way as `main.py` if needed.

## Utility Scripts

### dedupe_links.py

A utility script to remove duplicate URLs from text files in a directory.

```bash
# Remove duplicates from all .txt files in a directory
python scripts/dedupe_links.py path/to/directory

# Show what would be done without making changes
python scripts/dedupe_links.py path/to/directory --dry-run
```

The script will:

- Process all .txt files in the specified directory
- Remove duplicate URLs while preserving order
- Report the number of duplicates removed from each file
- Show a summary of total duplicates removed

### remove_group_duplicates.py

A utility script to remove duplicate URLs from uncategorized group files if they exist in any regular collection file. This ensures links only exist in one place - either in regular collections or in uncategorized groups.

```bash
# Remove duplicates from group files
python scripts/remove_group_duplicates.py path/to/directory

Example:
python scripts/remove_group_duplicates.py dertarchin
```

The script will:

- Find all regular collection files (excluding error logs and uncategorized groups)
- For each regular collection file:
  - Remove its URLs from all uncategorized group files
  - Preserve the order of remaining URLs in group files
- Report the total number of duplicates removed

### fix_collection_issues.py

A utility script to validate and fix issues with TikTok video collections. It handles:

1. Moving misplaced videos to their correct collections
2. Removing extra videos that don't belong anywhere
3. Cleaning up download logs for missing videos

```bash
# Validate and fix issues in a directory (dry run)
python scripts/fix_collection_issues.py path/to/directory --dry-run

# Validate and fix issues in a directory (apply changes)
python scripts/fix_collection_issues.py path/to/directory

# Specify custom Google Drive base path
python scripts/fix_collection_issues.py path/to/directory --gdrive-base-path "gdrive:/Custom Path"
```

The script will:

- Check all collection files in the specified directory
- Verify each video ID is either:
  - Downloaded as an MP4 file
  - Listed in an error log
- Report any missing or extra videos
- Fix issues by:
  - Moving videos to their correct collections
  - Removing extra videos
  - Updating download logs
- Validate against both local files and Google Drive

### rename_hidden_files.py

A utility script to recursively rename files that start with a dot (hidden files) in a directory, except for `.DS_Store` files. This is useful for fixing filenames that were accidentally prefixed with a dot.

```bash
# Process current directory
python scripts/rename_hidden_files.py

# Process specific directory
python scripts/rename_hidden_files.py path/to/directory
```

The script will:

- Recursively walk through the specified directory
- Find files that start with a dot (except .DS_Store)
- Remove the leading dot from the filename
- Report each rename operation
- Show a summary of total files renamed
