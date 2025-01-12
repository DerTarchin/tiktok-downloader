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
        """Quit the Selenium WebDriver"""
        if self.driver:
            self.driver.quit()
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
            if str(e) != "private":
                print(f"\t-> Failed to download: {url}")
                print(f"\t-> Current page URL: {self.driver.current_url}")
                print(f"\t-> Error details: {e}")
            raise

        # After successful download
        file_handler.log_successful_download(url, collection_name)

    def _handle_photo_download(self, url, output_folder, video_id_suffix):
        """Handle photo download process"""
        try:
            convert_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'button[data-event="video_convert_click"]'))
            )
            convert_button.click()

            # Wait for new file to appear in temp downloads directory
            max_wait = 90
            start_time = time.time()
            while time.time() - start_time < max_wait:
                downloaded_files = os.listdir(self.temp_download_dir)
                if downloaded_files:
                    # Filter out partial downloads
                    complete_files = [f for f in downloaded_files if not f.endswith('.part')]
                    if complete_files:
                        # Get the most recently modified file
                        latest_file = max(
                            complete_files,
                            key=lambda f: os.path.getmtime(os.path.join(self.temp_download_dir, f))
                        )
                        downloaded_file = os.path.join(self.temp_download_dir, latest_file)
                        self._process_downloaded_photo_file(downloaded_file, url, output_folder, video_id_suffix)
                        return
                time.sleep(0.5)
                
            raise Exception("Timeout waiting for photo download")        
        except Exception as e:
            print(f"\t-> Failed at: Photo download process")
            print(f"\t-> Error details: {str(e)}")
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
            
            if description:
                filename = clean_filename(f"{(uploader + description)[:150]}{video_id_suffix}.mp4")
            else:
                filename = clean_filename(f"{uploader[:150]}{video_id_suffix}.mp4")
            
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
                else:
                    raise Exception(f"Curl download failed with error: {result.stderr}")
                    
        except Exception as e:
            print(e)
            print(str(e))
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
        filename = clean_filename(f"{(uploader+title_text)[:150]}{suffix}.mp4")
        output_path = os.path.join(output_folder, filename)
        
        # Wait a brief moment to ensure file is completely downloaded
        time.sleep(1)
        try:
            os.rename(downloaded_file, output_path)
        except OSError as e:
            if "[Errno 92] Illegal byte sequence" in str(e):
                simple_filename = clean_filename(f"{video_id_suffix.strip()}.mp4")
                simple_output_path = os.path.join(output_folder, simple_filename)
                os.rename(downloaded_file, simple_output_path)
            else:
                raise 