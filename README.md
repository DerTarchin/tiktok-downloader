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
- Firefox browser (for Selenium)
- rclone (for Google Drive sync)
- Python packages (see requirements.txt)

Note: The Firefox WebDriver (geckodriver) will be automatically installed by the script.

### Multi-Computer Setup

To use this project on multiple computers:

1. **Install System Dependencies**:

   **Firefox Browser**:

   - macOS: `brew install firefox`
   - Ubuntu: `sudo apt install firefox`
   - Windows: Download from https://www.mozilla.org/firefox/

   **rclone**:

   - macOS: `brew install rclone`
   - Ubuntu: `sudo apt install rclone`
   - Windows: Download from https://rclone.org/downloads/

2. **Python Environment Setup**:

   ```bash
   # Clone/copy the repository
   git clone <repository-url>
   cd tiktok-downloader

   # Create virtual environment (recommended)
   python -m venv venv

   # Activate virtual environment (recommended)
   # On macOS/Linux:
   source venv/bin/activate
   # On Windows:
   .\venv\Scripts\activate

   # Install Python dependencies
   pip install -r requirements.txt
   ```

3. **rclone Setup**:

   If setting up from scratch:

   ```bash
   # Configure rclone (interactive setup)
   rclone config

   # Follow prompts to:
   # 1. Select "New remote"
   # 2. Name it "gdrive"
   # 3. Choose "Google Drive" as storage type
   # 4. Follow OAuth setup steps
   ```

   To copy existing rclone config:

   ```bash
   # Find existing config location:
   rclone config file

   # Config is usually located at:
   # Windows: %UserProfile%\.config\rclone\rclone.conf
   # macOS/Linux: ~/.config/rclone/rclone.conf

   # Copy this file to the same location on your new computer
   ```

4. **Environment Variables**:

   ```bash
   # Copy template
   cp .env.template .env

   # Edit .env with your credentials
   nano .env  # or use any text editor
   ```

### Maintenance

When adding new Python packages:

```bash
# Update requirements.txt with all installed packages
pip freeze > requirements.txt

# Or manually add specific packages
echo "package-name>=version" >> requirements.txt
```

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

# Control concurrent downloads (default: 5)
python main.py path/to/directory --concurrent 4

# Control concurrent Selenium downloads (defaults to --concurrent value)
python main.py path/to/directory --concurrent-selenium 3

# Skip download validation step
python main.py path/to/directory --skip-validation

# Skip private videos
python main.py path/to/directory --skip-private

# Skip synchronization step
python main.py path/to/directory --skip-sync

# Keep all uncategorized videos in one file (overrides default group splitting)
python main.py path/to/directory --combine-uncategorized

# Enable verbose output
python main.py path/to/directory --verbose

# Combine multiple flags
python main.py path/to/directory --disable-headless --concurrent 4 --skip-validation --verbose
```

The script will:

1. Create a folder with the same name as the input file
2. Try to download each video/photo using yt-dlp first
3. If yt-dlp fails, try using Selenium with musicaldown.com
4. Save successful downloads to the created folder
5. Create error logs for failed downloads
6. Track successful downloads to avoid duplicates
7. Automatically sync to Google Drive (unless --skip-sync is used)

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

### fetch_collection_videos.py

A utility script to fetch video URLs from a single TikTok collection using their web API.

```bash
# Basic usage (creates new file)
python scripts/fetch_collection_videos.py COLLECTION_ID

# Specify custom output file
python scripts/fetch_collection_videos.py COLLECTION_ID --output-file my_collection.txt

# Continue from a specific cursor
python scripts/fetch_collection_videos.py COLLECTION_ID --cursor "123456"

# Add delay between requests (in seconds)
python scripts/fetch_collection_videos.py COLLECTION_ID --delay 1

# Combine options
python scripts/fetch_collection_videos.py COLLECTION_ID --output-file my_collection.txt --cursor "123456" --delay 0.5
```

The script will:

- Connect to TikTok's web API
- Read existing URLs from output file if it exists
- Fetch all video IDs from the specified collection starting from the cursor
- Only add new unique URLs to avoid duplicates
- Add optional delay between requests to avoid rate limiting
- Display progress and statistics

### fetch_user_collections.py

A utility script to fetch all collections from a TikTok user and download their video URLs.

```bash
# Fetch all collections for a user
python scripts/fetch_user_collections.py OUTPUT_DIR

# Add delay between requests (in seconds)
python scripts/fetch_user_collections.py OUTPUT_DIR --delay 1

# Use existing directory.log file instead of fetching collections
python scripts/fetch_user_collections.py OUTPUT_DIR --directory path/to/directory.log
```

The script will:

- Extract username from the output directory name
- Fetch all collections for the specified user
- For each collection:
  - Fetch all video URLs
  - Save them to a text file named after the collection
- Create a separate file for each collection in the output directory
- Display a summary of total collections and videos found

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
- Process collections first, then uncategorized files
- Report the number of duplicates removed from each file
- Show a summary of total duplicates removed

### download_slideshows.py

A utility script to download TikTok slideshows using only the selenium pipeline, skipping yt-dlp.

```bash
# Download from a single file
python scripts/download_slideshows.py path/to/urls.txt

# Download from all .txt files in a directory
python scripts/download_slideshows.py path/to/directory

# Disable headless mode (show browser)
python scripts/download_slideshows.py path/to/directory --disable-headless

# Control concurrent downloads (default: 5)
python scripts/download_slideshows.py path/to/directory --concurrent 3
```

The script will:

- Process URLs from a single file or all .txt files in a directory
- Use only the selenium pipeline for downloading (skips yt-dlp)
- Create folders based on input file names
- Track successful downloads to avoid duplicates
- Handle private videos gracefully
- Clean up temporary files after completion

### download_sounds.py

A utility script to extract and download TikTok audio files from a text file containing sound links.

```bash
# Extract links only (saves to links.txt in same directory)
python scripts/download_sounds.py input_file.txt

# Download audio files (saves to Sounds directory)
python scripts/download_sounds.py input_file.txt --download

# Control number of concurrent downloads (default: 5)
python scripts/download_sounds.py input_file.txt --download --concurrent 3
```

The script will:

- Extract TikTok sound links from the input file
- Save extracted links to links.txt in the same directory as input file
- Create a Sounds directory in the same location as input file
- When downloading:
  - Use concurrent downloads for better performance (default: 5 concurrent)
  - Save files in format: "original_name music_id.mp3" (limited to 70 chars)
  - Track successful and failed downloads in real-time
  - Remove successful downloads from failed log automatically
  - Skip already downloaded files
  - Validate files after download
  - Show detailed progress and statistics
- Handle errors gracefully with detailed logging
- Provide a final summary with:
  - Successfully downloaded files this session
  - Total successful downloads
  - Actual files in directory
  - Failed downloads
  - Any mismatches or validation issues

### remove_group_duplicates.py

A utility script to remove duplicate URLs from uncategorized group files if they exist in any regular collection file.

```bash
# Remove duplicates from group files
python scripts/remove_group_duplicates.py path/to/directory

# Show what would be done without making changes
python scripts/remove_group_duplicates.py path/to/directory --dry-run
```

The script will:

- Find all regular collection files (excluding error logs and uncategorized groups)
- For each regular collection file:
  - Remove its URLs from all uncategorized group files
  - Preserve the order of remaining URLs in group files
- Report the total number of duplicates removed

### fix_issues.py

A utility script to validate and fix TikTok downloads.

```bash
# Basic usage
python scripts/fix_issues.py path/to/directory

# Show what would be done without making changes
python scripts/fix_issues.py path/to/directory --dry-run

# Skip moving videos to fix missing entries, just delete extras
python scripts/fix_issues.py path/to/directory --skip-move

# Delete extra videos found in remote storage
python scripts/fix_issues.py path/to/directory --delete-extra

# Specify custom Google Drive base path
python scripts/fix_issues.py path/to/directory --gdrive-base-path "gdrive:/Custom Path"
```

The script will:

1. Validate all collections in the directory
2. Move misplaced videos to their correct collections
3. Remove extra videos that don't belong anywhere
4. Clean up download logs for missing videos
5. Delete files under 50kb (corrupted)
6. Delete files without extensions
7. Handle both local and remote (Google Drive) files

### parse_urls.py

A utility script to extract and combine URLs from multiple text files.

```bash
# Process a single file
python scripts/parse_urls.py input_file.txt

# Process multiple files
python scripts/parse_urls.py file1.txt file2.txt file3.txt
```

The script will:

- Read all input files
- Extract valid TikTok URLs from each file
- Combine all unique URLs into a single output file (`combined_urls.txt`)
- Save the output file in the same directory as the first input file

### rename_hidden_files.py

A utility script to rename files that start with a dot (hidden files).

```bash
# Process current directory
python scripts/rename_hidden_files.py

# Process specific directory
python scripts/rename_hidden_files.py path/to/directory

# Show what would be done without making changes
python scripts/rename_hidden_files.py path/to/directory --dry-run

# Also handle files in Google Drive
python scripts/rename_hidden_files.py path/to/directory --handle-remote
```

The script will:

- Find all files starting with a dot (except .DS_Store)
- Rename them to start with underscore instead
- Handle both local and remote (Google Drive) files if requested
- Show progress and statistics

### count_unique_videos.py

A utility script to count unique videos across all collections in a directory.

```bash
# Count unique videos in a directory
python scripts/count_unique_videos.py path/to/directory

# Show detailed breakdown
python scripts/count_unique_videos.py path/to/directory --verbose
```

The script will:

- Process all .txt files in the directory
- Count total unique video URLs
- Show breakdown by collection if verbose
- Identify duplicates across collections
- Display summary statistics

### split_links.py

A utility script to split a text file containing URLs into multiple files.

```bash
# Basic usage (splits into files of 500 lines each)
python scripts/split_links.py input_file.txt

# Custom number of lines per file
python scripts/split_links.py input_file.txt --max-lines 1000
```

The script will:

- Read the input file
- Split it into multiple files with max lines per file (default: 500)
- Create files named like "original_name (Part 1).txt", "original_name (Part 2).txt", etc.
- Show progress and statistics for each file created

### extract_post_links.py

A utility script to extract TikTok video links from text files containing TikTok metadata.

```bash
# Extract links from a single file (creates links.txt)
python scripts/extract_post_links.py metadata.txt

# Extract links from multiple files
python scripts/extract_post_links.py file1.txt file2.txt file3.txt

# Save links to custom filename
python scripts/extract_post_links.py metadata.txt -o my_links.txt

# Set minimum file size in KB (default: 500)
python scripts/extract_post_links.py metadata.txt --min-size 1000

# Download videos from extracted URLs
python scripts/extract_post_links.py metadata.txt --download
```

The script will:

1. Extract TikTok links:

   - Process each input file
   - Save links to links.txt (or specified filename)
   - Create separate output for each input file
   - Handle multiple input files

2. If --download is specified:
   - Create directory named after input file
   - Download videos from tiktokv.us URLs
   - Save videos as "Video 1.mp4", "Video 2.mp4", etc.
   - Skip non-tiktokv.us URLs

### sync_to_remote.py

A utility script to sync a directory to remote Google Drive using the same logic as the main script's final sync.

```bash
# Basic usage
python scripts/sync_to_remote.py path/to/directory

# Show what would be synced without making changes
python scripts/sync_to_remote.py path/to/directory --dry-run

# Specify custom Google Drive base path
python scripts/sync_to_remote.py path/to/directory --gdrive-base "gdrive:/Custom Path"
```

The script will:

1. Sync all folders that correspond to .txt files
2. Handle files starting with periods or spaces
3. Skip empty folders
4. Sync text files and logs
5. Use optimal rclone settings (20 transfers, 256M chunks)

### count_videos_to_download.py

A utility script to count the total number of videos to be downloaded across text files in a directory. It provides a breakdown by collection and accounts for private/unavailable videos.

```bash
# Basic usage
python scripts/count_videos_to_download.py path/to/directory
```

### update_aliases.py

A utility script to update shell aliases for all TikTok Downloader scripts in your `~/.zshrc` file. The script automatically detects the project location and updates the aliases accordingly.

```bash
# Update aliases in ~/.zshrc
python scripts/update_aliases.py
```

The script will:

1. Detect the project root directory
2. Generate aliases for all TikTok Downloader scripts
3. Clean up any existing TikTok Downloader aliases
4. Add new aliases with correct paths
5. Maintain a help command (`tthelp`) that shows all available commands with their script paths

Available aliases:

- `tt`: Run the main downloader script
- `ttaudio`: Download TikTok audio files
- `ttcollect`: Fetch user collections
- `ttcollection`: Fetch collection videos
- `ttcount`: Count videos to download
- `ttdedupe`: Remove duplicate URLs
- `ttfix`: Fix download issues
- `ttgroupdedupe`: Remove group duplicates
- `ttparse`: Parse and combine URLs
- `ttphotos`: Download slideshows
- `ttsplit`: Split URL files
- `ttsync`: Sync to Google Drive
- `tthelp`: Show all available commands
- `ttprep`: Prepare TikTok collections for downloading

After running the script, remember to:

```bash
source ~/.zshrc  # Apply the changes
```
