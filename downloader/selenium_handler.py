"""Selenium-based downloader functionality."""

import os
import time
import urllib.request
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess
from urllib.parse import urlparse

from .utils import clean_filename, extract_video_id, get_filename_suffix

# Define constants for wait times
MAX_WAIT_TIME_PART_FILE = 90  # Maximum wait time for .part files in seconds
MAX_WAIT_TIME_SHORT = 5  # Maximum wait time for no file size change or download started in seconds
MAX_WAIT_TIME_RENDER = 90  # Maximum wait time for photo render completion

MAX_FILENAME_LENGTH = 70

class SeleniumHandler:
    def __init__(self, temp_download_dir, headless=True):
        # Convert temp_download_dir to absolute path if it's not already
        self.temp_download_dir = os.path.abspath(temp_download_dir)
        self.driver = None
        self.headless = headless
        
    def startup(self):
        """
        Initialize and configure Selenium WebDriver with Firefox.
        Downloads and installs uBlock Origin, configures download settings.
        """
        print("\nStarting Selenium...")

        # Download uBlock Origin XPI
        xpi_url = "https://addons.mozilla.org/firefox/downloads/file/4003969/ublock_origin-1.52.2.xpi"
        xpi_path = os.path.join(os.getcwd(), "ublock_origin.xpi")
        urllib.request.urlretrieve(xpi_url, xpi_path)

        options = Options()
        options.add_argument("--disable-notifications")
        
        # Add headless mode if enabled
        if self.headless:
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
        
        # Configure Firefox download settings
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.manager.showWhenStarting", False)
        options.set_preference("browser.download.dir", self.temp_download_dir)
        options.set_preference("browser.download.useDownloadDir", True)
        options.set_preference("browser.download.always_ask_before_handling_new_types", False)
        options.set_preference("browser.download.manager.closeWhenDone", True)
        options.set_preference("browser.download.manager.focusWhenStarting", False)
        options.set_preference("browser.download.manager.showAlertOnComplete", False)
        options.set_preference("browser.download.manager.useWindow", False)
        options.set_preference("browser.download.panel.shown", True)
        options.set_preference("browser.download.saveLinkAsFilenameTimeout", 0)
        options.set_preference("browser.download.forbid_open_with", True)
        options.set_preference("pdfjs.disabled", True)  # Disable built-in PDF viewer
        options.set_preference("browser.helperApps.alwaysAsk.force", False)
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", 
            "image/jpeg,image/png,image/jpg,image/webp,video/mp4,video/webm,video/x-matroska,"
            "video/quicktime,video/x-msvideo,video/x-flv,application/x-mpegURL,"
            "video/MP2T,video/3gpp,video/mpeg,application/zip,application/x-zip,"
            "application/x-zip-compressed,application/octet-stream,"
            "application/binary,application/x-unknown,application/force-download,"
            "application/download,binary/octet-stream")

        # Install uBlock Origin
        options.set_preference("extensions.autoDisableScopes", 0)
        options.add_argument("--load-extension=ublock-origin")
        
        # Enable installation of extensions from URLs
        options.set_preference("xpinstall.signatures.required", False)
        options.set_preference("extensions.webextensions.uuids", 
            '{"uBlock0@raymondhill.net":"c2c003ee-bd69-4b2b-b069-9a801134a23b"}')
        
        # Configure uBlock Origin settings
        ublock_preferences = {
            "browser.contentblocking.category": "custom",
            "extensions.webextensions.uuids": 
                '{"uBlock0@raymondhill.net":"c2c003ee-bd69-4b2b-b069-9a801134a23b"}',
            "extensions.webextensions.ExtensionStorageIDB.migrated.uBlock0@raymondhill.net": True,
        }
        for pref, value in ublock_preferences.items():
            options.set_preference(pref, value)

        # Configure Selenium WebDriver
        gecko_path = GeckoDriverManager().install()
        service = Service(gecko_path)
        self.driver = webdriver.Firefox(service=service, options=options)

        # Install uBlock Origin from local file
        self.driver.install_addon(xpi_path, temporary=True)
        
        # Clean up the XPI file
        try:
            os.remove(xpi_path)
        except:
            pass
        
        print("Selenium started")

    def shutdown(self):
        """Quit the Selenium WebDriver with timeout protection"""
        if self.driver:
            try:
                # Set page load timeout to 5 seconds to prevent hanging
                self.driver.set_page_load_timeout(5)
                # Try graceful shutdown first
                self.driver.quit()
            except Exception as e:
                print(f"\nWarning: Graceful Selenium shutdown failed: {e}")
                try:
                    # Force kill the browser process if graceful shutdown fails
                    self.driver.quit()
                except:
                    pass
            finally:
                self.driver = None

    def cleanup(self):
        """Alias for shutdown to maintain compatibility with signal handling"""
        self.shutdown()

    def get_uploader_from_page(self, url):
        """
        Extract uploader name from page title or URL fallback.
        
        Args:
            url: URL to extract username from
            
        Returns:
            str: Cleaned uploader name with dash suffix if found, empty string otherwise
        """
        # Extract username from URL if present
        uploader = ""
        if "/@" in url:
            try:
                # Split URL by /@ and take everything after it up to next /
                uploader = url.split("/@")[1].split("/")[0].lstrip('@')
            except:
                pass
        
        # extract from webpage title
        if not uploader:
            try:
                title_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, 'title'))
                )
                uploader = title_element.get_attribute('innerHTML').split(" | Download Now!")[0]
            except:
                pass

        return f"{uploader} - " if uploader else ""

    def download_with_selenium(self, url, output_folder, file_handler, collection_name=None):
        """
        Download video/photo using Selenium automation of musicaldown.com.
        Falls back to snaptik.app if musicaldown fails.
        
        Args:
            url: URL to download
            output_folder: Folder to save downloaded file to
            file_handler: FileHandler instance for logging
            collection_name: Optional collection name for tracking downloads
        
        Raises:
            Exception: If download fails at any step
        """
        # Skip if URL was already successfully downloaded
        if file_handler.is_url_downloaded(url, collection_name):
            print(f"\t-> Already downloaded: {url}")
            return
        
        # Clear temp download directory before starting new download
        for file in os.listdir(self.temp_download_dir):
            try:
                os.remove(os.path.join(self.temp_download_dir, file))
            except Exception as e:
                print(f"\t-> Warning: Could not remove temp file {file}: {e}")

        try:
            # Try musicaldown first
            self._try_musicaldown_download(url, output_folder)
            # After successful download and validation, log success
            file_handler.log_successful_download(url, collection_name)
        except Exception as e:
            if str(e) == "private":
                raise
            print(f"\t-> MusicalDown failed, trying SnapTik...")
            try:
                # Try snaptik as fallback
                self._try_snaptik_download(url, output_folder)
                # After successful download and validation, log success
                file_handler.log_successful_download(url, collection_name)
            except Exception as e:
                if str(e) != "private":
                    print(f"\t-> Failed to download: {url}")
                raise

    def _try_musicaldown_download(self, url, output_folder):
        """Original musicaldown.com download logic"""
        # Get video ID from URL
        video_id_suffix = get_filename_suffix(url)

        try:
            self.driver.get("https://musicaldown.com/en")

            # Find the input field and paste the URL
            try:
                input_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "link_url"))
                )
                input_element.clear()
                # Reformat tiktokv.com URLs to standard tiktok.com format
                if "www.tiktokv.com" in url:
                    video_id = extract_video_id(url)
                    url = f"https://www.tiktok.com/@/video/{video_id}/"
                input_element.send_keys(url)
            except Exception as e:
                print(f"\t-> Failed at: Finding and entering URL in input field")
                print(f"\t-> Looking for element: ID 'link_url'")
                raise Exception(f"Failed to find or interact with URL input field: {str(e)}")

            # Click submit and handle download based on content type
            try:
                submit_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
                )
                submit_button.click()
            except Exception as e:
                print(f"\t-> Failed at: Finding and clicking submit button")
                print(f"\t-> Looking for element: CSS 'button[type='submit']'")
                raise Exception(f"Failed to find or click submit button: {str(e)}")
            
            if "/photo/" in self.driver.current_url:
                self._handle_photo_download(url, output_folder, video_id_suffix)
            elif "/video/" in url:
                self._handle_video_download(url, output_folder, video_id_suffix)
            else:
                raise Exception("URL is neither a photo nor a video post")

        except Exception as e:
            raise

    def _dismiss_snaptik_ads(self):
        """Attempt to dismiss any visible ad/popup elements on SnapTik"""
        try:
            # Look for dismiss button with specific class and attributes
            dismiss_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'div#dismiss-button.btn.skip[aria-label="Close ad"][role="button"][tabindex="0"]')
            for button in dismiss_buttons:
                if button.is_displayed():
                    button.click()
                    time.sleep(0.5)  # Brief pause after clicking

            # Look for "Continue using the web" button
            continue_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button.button.is-link.continue-web')
            for button in continue_buttons:
                if button.is_displayed():
                    button.click()
                    time.sleep(0.5)  # Brief pause after clicking
        except:
            pass

    def _try_snaptik_download(self, url, output_folder):
        """
        Try downloading using snaptik.app as a fallback.
        
        Args:
            url: URL to download
            output_folder: Folder to save downloaded file to
            
        Raises:
            Exception: If download fails at any step
        """
        video_id_suffix = get_filename_suffix(url)
        
        try:
            # Navigate to snaptik
            self.driver.get("https://snaptik.app/en2")
            
            # Check for and dismiss any initial ads
            self._dismiss_snaptik_ads()
            
            # Find and fill URL input
            try:
                input_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='url']"))
                )
                self._dismiss_snaptik_ads()  # Check again before interacting
                input_element.clear()
                # Reformat tiktokv.com URLs to standard tiktok.com format
                if "www.tiktokv.com" in url:
                    video_id = extract_video_id(url)
                    url = f"https://www.tiktok.com/@/video/{video_id}/"
                input_element.send_keys(url)
            except Exception as e:
                print(f"\t-> Failed at: Finding and entering URL in SnapTik input field")
                raise Exception(f"Failed to find or interact with SnapTik URL input field: {str(e)}")

            self._dismiss_snaptik_ads()  # Check before clicking submit

            # Click submit button
            try:
                submit_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.button.button-go.is-link.transition-all"))
                )
                self._dismiss_snaptik_ads()  # Check again right before clicking
                submit_button.click()
            except Exception as e:
                print(f"\t-> Failed at: Finding and clicking SnapTik submit button")
                raise Exception(f"Failed to find or click SnapTik submit button: {str(e)}")

            # Check for and dismiss any ads that appeared after submission
            self._dismiss_snaptik_ads()

            # Wait for video title to appear
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.video-title"))
                )
                self._dismiss_snaptik_ads()  # Check after title appears
            except Exception as e:
                print(f"\t-> Failed at: Waiting for SnapTik video title")
                raise Exception(f"Failed to find video title on SnapTik: {str(e)}")

            # Get description and username
            try:
                self._dismiss_snaptik_ads()  # Check before getting text
                description = self.driver.find_element(By.CSS_SELECTOR, "div.video-title").text
                username = self.driver.find_element(By.CSS_SELECTOR, "div.video-title + span").text
            except:
                description = ""
                username = ""

            self._dismiss_snaptik_ads()  # Check before looking for download options

            # First check which type of download is available
            try:
                # Look for both video and photo download elements
                video_link = self.driver.find_element(By.CSS_SELECTOR, "a.download-file[data-event='server01_file']")
                render_button = self.driver.find_element(By.CSS_SELECTOR, "button.btn-render")
                
                # Determine which one is displayed
                if video_link.is_displayed():
                    is_video = True
                elif render_button.is_displayed():
                    is_video = False
                else:
                    raise Exception("Neither video nor photo download options are visible")
            except Exception as e:
                if "Neither video nor photo download options are visible" in str(e):
                    raise
                # If element not found, try individual checks
                try:
                    video_link = self.driver.find_element(By.CSS_SELECTOR, "a.download-file[data-event='server01_file']")
                    is_video = video_link.is_displayed()
                except:
                    try:
                        render_button = self.driver.find_element(By.CSS_SELECTOR, "button.btn-render")
                        is_video = not render_button.is_displayed()
                    except:
                        raise Exception("No video or photo download options found on SnapTik")

            # Handle video download
            if is_video:
                try:
                    self._dismiss_snaptik_ads()  # Check before getting href
                    download_url = video_link.get_attribute("href")
                    if not download_url:
                        raise Exception("Download button found but href attribute is empty")

                    if description:
                        filename = clean_filename(f"{(username + ' - ' + description)[:MAX_FILENAME_LENGTH]}{video_id_suffix}.mp4")
                    else:
                        filename = clean_filename(f"{username[:MAX_FILENAME_LENGTH]}{video_id_suffix}.mp4")
                    
                    download_path = os.path.join(output_folder, filename)
                    
                    # Download using curl
                    cmd = ["curl", "-L", "-s", download_url, "-o", download_path]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        if "[Errno 92] Illegal byte sequence" in result.stderr:
                            simple_filename = f"{video_id_suffix.strip()}.mp4"
                            if simple_filename.startswith('.'):
                                simple_filename = simple_filename[1:]
                            simple_download_path = os.path.join(output_folder, simple_filename)
                            result = subprocess.run(["curl", "-L", "-s", download_url, "-o", simple_download_path],
                                                capture_output=True, text=True)
                            if result.returncode != 0:
                                raise Exception(f"Curl download failed with error: {result.stderr}")
                            download_path = simple_download_path
                        else:
                            raise Exception(f"Curl download failed with error: {result.stderr}")
                    
                    # Check if downloaded file is empty with retries
                    self._check_file_size_with_retries(download_path)
                    return
                except Exception as e:
                    print(f"\t-> Failed at: Video download process on SnapTik")
                    raise

            # Handle photo download
            else:
                try:
                    self._dismiss_snaptik_ads()  # Check before clicking render
                    render_button.click()
                    
                    # Wait for render completion
                    start_time = time.time()
                    while time.time() - start_time < MAX_WAIT_TIME_RENDER:
                        self._dismiss_snaptik_ads()  # Check during render wait
                        try:
                            # Check for fail element first
                            fail_element = self.driver.find_element(By.CSS_SELECTOR, "span.alert-render")
                            if fail_element.is_displayed():
                                raise Exception("Failed to render photo - error element detected")
                            
                            render_label = self.driver.find_element(By.CSS_SELECTOR, "p.render-label")
                            if render_label.text == "Render Completed":
                                break
                        except Exception as e:
                            if "Failed to render photo" in str(e):
                                raise
                            pass
                        time.sleep(0.5)
                    else:
                        raise Exception("Photo render timed out")

                    self._dismiss_snaptik_ads()  # Check before getting download link

                    # Get download link
                    download_link = self.driver.find_element(By.CSS_SELECTOR, "a.download-render")
                    download_url = download_link.get_attribute("href")
                    if not download_url:
                        raise Exception("Photo download button found but href attribute is empty")

                    if description:
                        filename = clean_filename(f"{(username + ' - ' + description)[:MAX_FILENAME_LENGTH]}{video_id_suffix}.mp4")
                    else:
                        filename = clean_filename(f"{username[:MAX_FILENAME_LENGTH]}{video_id_suffix}.mp4")
                    
                    download_path = os.path.join(output_folder, filename)
                    
                    # Download using curl
                    cmd = ["curl", "-L", "-s", download_url, "-o", download_path]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        if "[Errno 92] Illegal byte sequence" in result.stderr:
                            simple_filename = f"{video_id_suffix.strip()}.mp4"
                            if simple_filename.startswith('.'):
                                simple_filename = simple_filename[1:]
                            simple_download_path = os.path.join(output_folder, simple_filename)
                            result = subprocess.run(["curl", "-L", "-s", download_url, "-o", simple_download_path],
                                                capture_output=True, text=True)
                            if result.returncode != 0:
                                raise Exception(f"Curl download failed with error: {result.stderr}")
                            download_path = simple_download_path
                        else:
                            raise Exception(f"Curl download failed with error: {result.stderr}")
                    
                    # Check if downloaded file is empty with retries
                    self._check_file_size_with_retries(download_path)
                    return
                except Exception as e:
                    print(f"\t-> Failed at: Photo download process on SnapTik")
                    raise

        except Exception as e:
            raise

    def _handle_photo_download(self, url, output_folder, video_id_suffix):
        """Handle photo download process"""
        try:
            convert_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'button[data-event="video_convert_click"]'))
            )
            convert_button.click()

            # Wait for new file to appear in temp downloads directory
            print(f"Waiting for download to start...")
            start_time = time.time()
            while time.time() - start_time < MAX_WAIT_TIME_SHORT:  # Short timeout just to detect if download started
                downloaded_files = os.listdir(self.temp_download_dir)
                if downloaded_files:
                    print(f"Found {len(downloaded_files)} files in download directory")
                    # Include .part files in the search but prioritize complete files
                    complete_files = [f for f in downloaded_files if not f.endswith('.part')]
                    if complete_files:
                        # Get the most recently modified file
                        latest_file = max(
                            complete_files,
                            key=lambda f: os.path.getmtime(os.path.join(self.temp_download_dir, f))
                        )
                        downloaded_file = os.path.join(self.temp_download_dir, latest_file)
                        print(f"Selected most recent file: {latest_file}")
                        
                        # Check if file is empty before processing
                        print("Checking file size and waiting for download completion...")
                        self._check_file_size_with_retries(downloaded_file)
                        
                        print("Processing downloaded photo file...")
                        self._process_downloaded_photo_file(downloaded_file, url, output_folder, video_id_suffix)
                        return
                time.sleep(0.5)
                
            raise Exception(f"No download started after {MAX_WAIT_TIME_SHORT} seconds")
        except Exception as e:
            print(f"\t-> Failed at: Photo download process")
            raise

    def _handle_video_download(self, url, output_folder, video_id_suffix):
        """Handle video download process"""
        try:
            # Create a condition to check for either the download button or private video message
            private_video = False

            def check_elements():
                try:
                    # Check for private video message
                    try:
                        toast = self.driver.find_element(By.CSS_SELECTOR, 'div.toast')
                        if "Video is private or removed!" in toast.text:
                            nonlocal private_video
                            private_video = True
                            return True
                    except:
                        pass
                    
                    # Check for download button
                    download_button = self.driver.find_element(By.CSS_SELECTOR, 'a[data-event="hd_download_click"]')
                    return download_button.is_displayed()
                except:
                    return False

            # Wait for either element to appear
            WebDriverWait(self.driver, 10).until(lambda d: check_elements())
            
            # If private video was found, raise appropriate exception
            if private_video:
                raise Exception("private")

            # Get the download button (we know it exists if we got here)
            download_button = self.driver.find_element(By.CSS_SELECTOR, 'a[data-event="hd_download_click"]')
            download_url = download_button.get_attribute("href")
            if not download_url:
                raise Exception("Download button found but href attribute is empty")

            # Rest of the existing download logic
            uploader = self.get_uploader_from_page(url)
            description = self._get_video_description()
            
            # Only add description if it's different from uploader
            if description and description.strip() != uploader.strip():
                filename = clean_filename(f"{uploader} - {description[:MAX_FILENAME_LENGTH]}{video_id_suffix}.mp4")
            else:
                filename = clean_filename(f"{uploader[:MAX_FILENAME_LENGTH]}{video_id_suffix}.mp4")
            
            download_path = os.path.join(output_folder, filename)
            
            # Download using curl
            cmd = ["curl", "-L", "-s", download_url, "-o", download_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                if "[Errno 92] Illegal byte sequence" in result.stderr:
                    simple_filename = f"{video_id_suffix.strip()}.mp4"
                    if simple_filename.startswith('.'):
                        simple_filename = simple_filename[1:]
                    simple_download_path = os.path.join(output_folder, simple_filename)
                    result = subprocess.run(["curl", "-L", "-s", download_url, "-o", simple_download_path],
                                         capture_output=True, text=True)
                    if result.returncode != 0:
                        raise Exception(f"Curl download failed with error: {result.stderr}")
                    download_path = simple_download_path
                else:
                    raise Exception(f"Curl download failed with error: {result.stderr}")
            
            # Check if downloaded file is empty with retries
            self._check_file_size_with_retries(download_path)

        except Exception as e:
            if str(e) == "private":
                raise Exception("private")
            elif "href attribute is empty" not in str(e):
                print(f"\t-> Failed at: Video download process")
                print(f"\t-> Looking for element: CSS 'a[data-event=\"hd_download_click\"]'")
            raise

    def _get_video_description(self):
        """Get video description from page"""
        try:
            desc_element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'p.video-desc'))
            )
            return desc_element.text
        except:
            return ""

    def _process_downloaded_photo_file(self, downloaded_file, url, output_folder, video_id_suffix):
        """Process and rename downloaded file"""
        try:
            title_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, 'title'))
            )
            title_text = title_element.get_attribute('innerHTML').split(" | Download Now!")[0]
            if title_text == '\ufff6' or not title_text.strip():
                title_text = ""
        except:
            print("Could not find title element, using URL-based name")
            title_text = urlparse(url).path.split('/')[-1]

        uploader = self.get_uploader_from_page(url)
        suffix = video_id_suffix if title_text else extract_video_id(url)
        filename = clean_filename(f"{(uploader+title_text)[:MAX_FILENAME_LENGTH]}{suffix}.mp4")
        output_path = os.path.join(output_folder, filename)
        
        # Wait a brief moment to ensure file is completely downloaded
        time.sleep(1)
        try:
            os.rename(downloaded_file, output_path)
            
            # Check if renamed file is empty with retries
            self._check_file_size_with_retries(output_path)
                
        except OSError as e:
            if "[Errno 92] Illegal byte sequence" in str(e):
                simple_filename = clean_filename(f"{video_id_suffix.strip()}.mp4")
                simple_output_path = os.path.join(output_folder, simple_filename)
                os.rename(downloaded_file, simple_output_path)
                
                # Check if renamed file is empty with retries
                self._check_file_size_with_retries(simple_output_path)
            else:
                raise 

    def _check_file_size_with_retries(self, file_path, max_retries=10, retry_delay=0.5):
        """
        Check if a file has non-zero size, with retries to handle in-progress downloads.
        Also checks for corresponding .part files to detect in-progress downloads.
        
        If a .part file is detected, uses a 90-second max wait time.
        If no .part file is found, uses the specified retry parameters.
        
        Monitors file size changes and aborts if no changes detected for 10 seconds.
        
        Args:
            file_path: Path to the file to check
            max_retries: Maximum number of retries (default 20 tries = 20 seconds total)
            retry_delay: Delay between retries in seconds (default 1 second)
            
        Returns:
            bool: True if file has non-zero size, False otherwise
            
        Raises:
            Exception: If file remains empty after all retries or if no size changes for 10 seconds
        """
        base_name = os.path.basename(file_path)
        dir_path = os.path.dirname(file_path)
        
        # First check if there's a .part file
        part_files = [f for f in os.listdir(dir_path) if f.endswith('.part') and base_name.split('_')[-1] in f]
        
        if part_files or base_name.endswith('.part'):
            # Use max wait time for .part files
            start_time = time.time()
            last_size_change = time.time()
            last_size = 0
            
            while time.time() - start_time < MAX_WAIT_TIME_PART_FILE:
                current_part_files = [f for f in os.listdir(dir_path) if f.endswith('.part') and base_name.split('_')[-1] in f]
                
                # If .part no longer exists, check the main file
                if not current_part_files and not base_name.endswith('.part'):
                    current_size = os.path.getsize(file_path)
                    if current_size > 0:
                        print(f"File has been successfully downloaded: {current_size / 1_000_000:.2f} MB")
                        return True
                else:
                    # Check size of part file
                    part_file = current_part_files[0] if current_part_files else base_name
                    part_path = os.path.join(dir_path, part_file)
                    current_size = os.path.getsize(part_path)
                
                # Check if file size has changed
                if current_size != last_size:
                    last_size = current_size
                    last_size_change = time.time()
                    print(f"File {part_file} is downloading, current size: {current_size / 1_000_000:.2f} MB")
                elif time.time() - last_size_change > MAX_WAIT_TIME_SHORT:
                    raise Exception(f"Download stalled - no file size changes for {MAX_WAIT_TIME_SHORT} seconds. Last size: {last_size / 1_000_000:.2f} MB")
                
                time.sleep(0.5)
                
            raise Exception(f"File remains empty (0 bytes) or incomplete after {MAX_WAIT_TIME_PART_FILE}-second wait: {base_name}")
        
        else:
            # No .part file found, use standard retry logic
            for attempt in range(max_retries):
                current_size = os.path.getsize(file_path)
                if current_size > 0:
                    print(f"File has been successfully downloaded: {current_size / 1_000_000:.2f} MB")
                    return True
                    
                print(f"Retry {attempt + 1}/{max_retries}: File {base_name} is still empty, waiting...")
                time.sleep(retry_delay)
                
            raise Exception(f"File remains empty (0 bytes) after {max_retries} retries: {base_name}")