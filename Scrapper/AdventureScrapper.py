import os
import sys
import time
import json
import logging
import traceback
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

# Add the parent directory to sys.path to enable imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Conditionally import Selenium components
try:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Import all modular components
try:
    # First try absolute imports
    from Scrapper.Modules.SetupLogger import setup_directories, get_logger
    from Scrapper.Modules.DetectOS import get_os_info
    from Scrapper.Modules.BrowserSetup import BrowserSetup
    from Scrapper.Modules.BrowserCleanup import BrowserCleanup, ensure_browser_cleanup
    from Scrapper.Modules.CookieHandler import CookieHandler
    from Scrapper.Modules.ConfigManager import ConfigManager, get_config
    from Scrapper.Modules.DetectPackages import check_dependency_compatibility
except ImportError:
    try:
        # Then try relative imports
        from Modules.SetupLogger import setup_directories, get_logger
        from Modules.DetectOS import get_os_info
        from Modules.BrowserSetup import BrowserSetup
        from Modules.BrowserCleanup import BrowserCleanup, ensure_browser_cleanup
        from Modules.CookieHandler import CookieHandler
        from Modules.ConfigManager import ConfigManager, get_config
        from Modules.DetectPackages import check_dependency_compatibility
    except ImportError:
        # As a last resort, try direct imports if files are in the same directory
        print("Failed to import modules. Check your project structure and Python path.")
        print(f"Current sys.path: {sys.path}")
        sys.exit(1)

# ===== Setup directories =====
setup_directories([
    "Logs/Adventure", 
    "Data/Adventure"
])

# ===== Get configuration =====
config = get_config()

# ===== Logging configuration =====
logger = get_logger("AdventureScrapper", log_dir="Logs/Adventure", clean_logs=True)


def wait_and_click(driver: Any, wait: WebDriverWait, selector: str, by: By = By.CSS_SELECTOR, 
                  timeout: int = 20, description: str = "element") -> bool:
    """
    Wait for an element to be clickable and click it with proper logging.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
        selector: CSS selector or XPath
        by: Selection method (By.CSS_SELECTOR or By.XPATH)
        timeout: Maximum wait time in seconds
        description: Element description for logging
        
    Returns:
        Boolean indicating success
    """
    try:
        logger.info(f"Waiting for {description} to be clickable...")
        element = wait.until(EC.element_to_be_clickable((by, selector)))
        logger.info(f"Found {description}, attempting to click...")
        
        # Try direct click first
        try:
            element.click()
            logger.info(f"Successfully clicked {description} using direct click")
            return True
        except ElementClickInterceptedException:
            logger.info(f"Direct click failed for {description}, trying JavaScript click...")
            driver.execute_script("arguments[0].click();", element)
            logger.info(f"Successfully clicked {description} using JavaScript")
            return True
            
    except TimeoutException:
        logger.error(f"Timeout waiting for {description} to be clickable")
        return False
    except Exception as e:
        logger.error(f"Error clicking {description}: {e}")
        logger.debug(traceback.format_exc())
        return False


def extract_adventure_metadata(driver: Any, wait: WebDriverWait) -> List[Dict[str, str]]:
    """
    Extract metadata for all adventures from the list.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
    
    Returns:
        List of dictionaries containing adventure metadata
    """
    adventures = []
    
    try:
        # Wait for the list container to be fully loaded
        logger.info("Waiting for adventure list to load...")
        wait.until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "a.lst__row-border")) > 0
        )
        logger.info("Adventure list loaded, extracting metadata...")
        
        # Find all adventure elements
        adventure_elements = driver.find_elements(By.CSS_SELECTOR, "a.split-v-center.lst__row-border")
        logger.info(f"Found {len(adventure_elements)} adventure elements")
        
        for i, element in enumerate(adventure_elements):
            try:
                # Extract metadata from each element
                spans = element.find_elements(By.CSS_SELECTOR, "span.ve-flex span")
                
                # Log span count for debugging
                logger.debug(f"Adventure {i+1} has {len(spans)} span elements")
                
                if len(spans) >= 5:
                    adventure = {
                        "type": spans[0].text.strip(),
                        "name": spans[1].text.strip(),
                        "storyline": spans[2].text.strip(),
                        "level": spans[3].text.strip(),
                        "published_date": spans[4].text.strip(),
                        "url": element.get_attribute("href")
                    }
                    adventures.append(adventure)
                    logger.info(f"Extracted metadata for adventure: {adventure['name']}")
                else:
                    logger.warning(f"Adventure at index {i} has insufficient span elements ({len(spans)})")
            except Exception as e:
                logger.warning(f"Failed to extract metadata for adventure at index {i}: {e}")
                logger.debug(traceback.format_exc())
        
        logger.info(f"Successfully extracted metadata for {len(adventures)} adventures")
        return adventures
    except Exception as e:
        logger.error(f"Error extracting adventure metadata: {e}")
        logger.debug(traceback.format_exc())
        return []


def get_windows_download_folder() -> str:
    """
    Get the path to the Windows default download folder.
    
    Returns:
        Path to the Windows download folder
    """
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                          r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders') as key:
            downloads_path = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')[0]
            return downloads_path
    except Exception:
        return os.path.join(os.path.expanduser('~'), 'Downloads')


def configure_download_settings(driver: Any, download_path: str) -> None:
    """
    Configure browser settings for downloads using multiple approaches.
    
    Args:
        driver: Browser driver instance
        download_path: Path where downloads should be saved
    """
    try:
        # Convert to absolute path and ensure directory exists
        abs_download_path = os.path.abspath(download_path)
        os.makedirs(abs_download_path, exist_ok=True)
        
        # Method 1: Try CDP command for undetected_chromedriver
        try:
            params = {
                "behavior": "allow",
                "downloadPath": abs_download_path
            }
            driver.execute_cdp_cmd("Page.setDownloadBehavior", params)
            logger.info(f"Download path set via CDP: {abs_download_path}")
        except Exception as e:
            logger.debug(f"CDP method failed: {e}")
        
        # Method 2: Try to set preferences directly via experimental options
        try:
            # Access the underlying Chrome options if possible
            if hasattr(driver, '_options'):
                chrome_options = driver._options
                prefs = {
                    "download.default_directory": abs_download_path,
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "safebrowsing.enabled": True,
                    "profile.default_content_settings.popups": 0
                }
                chrome_options.add_experimental_option("prefs", prefs)
                logger.info("Set download preferences via options")
        except Exception as e:
            logger.debug(f"Options method failed: {e}")
        
        # Method 3: Use JavaScript to modify browser settings
        try:
            # For Windows paths, we need to escape backslashes
            js_path = abs_download_path.replace('\\', '\\\\')
            
            driver.execute_script(f"""
                // Set download behavior for this session
                if (window.chrome && window.chrome.downloads) {{
                    window.chrome.downloads.defaultDownloadDirectory = "{js_path}";
                }}
                
                // Add download info to localStorage
                window.localStorage.setItem('downloadPath', '{js_path}');
                window.preferredDownloadPath = '{js_path}';
                
                // Override downloads for this session
                const originalDownload = HTMLAnchorElement.prototype.click;
                HTMLAnchorElement.prototype.click = function() {{
                    if (this.download || this.getAttribute('download')) {{
                        console.log('Intercepted download click');
                        // Set download attribute to force download
                        this.download = this.download || 'adventure.md';
                    }}
                    return originalDownload.apply(this, arguments);
                }};
            """)
            logger.info("Set download preferences via JavaScript")
        except Exception as e:
            logger.debug(f"JavaScript method failed: {e}")
        
        logger.info(f"Download path configured to: {abs_download_path}")
    except Exception as e:
        logger.warning(f"Failed to set download behavior: {e}")
        logger.debug(traceback.format_exc())


def wait_for_download(directory: str, timeout: int = 90, check_default: bool = True) -> Tuple[bool, Optional[Path]]:
    """
    Wait for a .md file to appear in the directory and be fully downloaded.
    
    Args:
        directory: Directory to watch for files
        timeout: Maximum wait time in seconds
        check_default: Whether to also check the default Downloads folder
        
    Returns:
        Tuple containing:
            - Boolean indicating success
            - Path object to the downloaded file if found, None otherwise
    """
    start_time = time.time()
    
    # Get OS info to check for Windows
    is_windows = False
    try:
        from Modules.DetectOS import is_windows as detect_windows
        is_windows = detect_windows()
    except ImportError:
        is_windows = os.name == 'nt'
    
    # Also check user's default Downloads folder if on Windows
    default_downloads = None
    if check_default and is_windows:
        default_downloads = get_windows_download_folder()
        logger.info(f"Default Windows downloads folder: {default_downloads}")
    
    # Also check the Data/Downloads folder
    data_downloads = os.path.abspath(os.path.join("Data", "Downloads"))
    if os.path.exists(data_downloads):
        logger.info(f"Checking additional downloads folder: {data_downloads}")
    
    directory_path = Path(directory)
    
    while time.time() - start_time < timeout:
        # Check target directory
        md_files = list(directory_path.glob("*.md"))
        temp_files = list(directory_path.glob("*.md.crdownload"))
        temp_files.extend(list(directory_path.glob("*.crdownload")))
        temp_files.extend(list(directory_path.glob("*.part")))
        temp_files.extend(list(directory_path.glob("*.download")))
        
        if md_files and not temp_files:
            # Found completed files in target directory
            latest_file = max(md_files, key=lambda f: f.stat().st_mtime)
            logger.info(f"Download completed in target directory, found: {latest_file.name}")
            return True, latest_file
        
        # Check default Windows Downloads folder if needed
        if check_default and default_downloads:
            downloads_path = Path(default_downloads)
            default_md_files = list(downloads_path.glob("*.md"))
            default_temp_files = list(downloads_path.glob("*.md.crdownload"))
            default_temp_files.extend(list(downloads_path.glob("*.crdownload")))
            default_temp_files.extend(list(downloads_path.glob("*.part")))
            default_temp_files.extend(list(downloads_path.glob("*.download")))
            
            if default_md_files and not default_temp_files:
                # Found completed files in default Downloads
                latest_file = max(default_md_files, key=lambda f: f.stat().st_mtime)
                logger.info(f"Download completed in default Downloads folder: {latest_file}")
                return True, latest_file
        
        # Check Data/Downloads folder
        if os.path.exists(data_downloads):
            data_downloads_path = Path(data_downloads)
            data_md_files = list(data_downloads_path.glob("*.md"))
            data_temp_files = list(data_downloads_path.glob("*.md.crdownload"))
            data_temp_files.extend(list(data_downloads_path.glob("*.crdownload")))
            data_temp_files.extend(list(data_downloads_path.glob("*.part")))
            data_temp_files.extend(list(data_downloads_path.glob("*.download")))
            
            if data_md_files and not data_temp_files:
                # Found completed files in Data/Downloads
                latest_file = max(data_md_files, key=lambda f: f.stat().st_mtime)
                logger.info(f"Download completed in Data/Downloads folder: {latest_file}")
                return True, latest_file
        
        # Log download progress
        if temp_files:
            logger.info("Download in progress...")
        
        time.sleep(1)
    
    logger.error(f"Download timed out after {timeout} seconds")
    return False, None


def download_adventure_as_markdown(driver: Any, wait: WebDriverWait, adventure: Dict[str, str], output_dir: str) -> bool:
    """
    Download a single adventure as markdown.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
        adventure: Dictionary containing adventure metadata
        output_dir: Directory to save the downloaded adventure
        
    Returns:
        Boolean indicating success
    """
    try:
        # Configure download settings before navigation
        configure_download_settings(driver, output_dir)
        
        # Navigate to adventure page
        logger.info(f"Navigating to adventure page: {adventure['name']}")
        driver.get(adventure["url"])
        
        # Wait for loading to complete
        logger.info("Waiting for adventure page to load...")
        try:
            wait.until_not(EC.presence_of_element_located((By.CLASS_NAME, "initial-message")))
            logger.info("Adventure page loaded")
        except TimeoutException:
            logger.warning("Timeout waiting for initial message to disappear, continuing anyway")
        
        time.sleep(2)  # Give extra time for page to stabilize
        
        # Reconfigure download settings before clicking buttons
        configure_download_settings(driver, output_dir)
        
        # Click options button - CORRECTED SELECTOR to target the "Other Options" button specifically
        logger.info("Looking for 'Other Options' button...")
        options_button_clicked = wait_and_click(
            driver, 
            wait, 
            "button.ve-btn.ve-btn-xs.ve-btn-default[title='Other Options']", 
            description="options button"
        )
        
        # Alternative approach using the vertical dots icon if title selector fails
        if not options_button_clicked:
            logger.info("Trying alternative selector for options button with vertical dots icon...")
            options_button_clicked = wait_and_click(
                driver,
                wait,
                "button.ve-btn.ve-btn-xs.ve-btn-default span.glyphicon.glyphicon-option-vertical",
                description="options button (vertical dots)"
            )
            
        if not options_button_clicked:
            logger.error("Failed to click options button")
            return False
        
        # Click download button - CORRECTED SELECTOR to match the exact element
        logger.info("Looking for 'Download Adventure as Markdown' option...")
        download_button_clicked = wait_and_click(
            driver,
            wait,
            "//div[contains(@class, 'ui-ctx__btn') and contains(text(), 'Download Adventure as Markdown')]",
            By.XPATH,
            description="download markdown button"
        )
        
        if not download_button_clicked:
            # Try alternative approach
            logger.info("Trying alternative selector for download button...")
            download_button_clicked = wait_and_click(
                driver,
                wait,
                ".w-100.min-w-0.ui-ctx__btn.py-1.pl-5.pr-5",
                description="download button (class selector)"
            )
        
        if not download_button_clicked:
            logger.error("Failed to click download button")
            return False
        
        # Wait for download to complete and check for the file
        logger.info("Waiting for adventure download to complete...")
        download_success, downloaded_file = wait_for_download(output_dir, timeout=120, check_default=True)
        
        if download_success and downloaded_file:
            # Generate expected filename
            safe_name = adventure['name'].replace(" ", "_").replace("/", "-")
            safe_date = adventure['published_date'].replace(" ", "_").replace("/", "-").replace(",", "")
            filename = f"{safe_name}_{safe_date}.md"
            filepath = os.path.join(output_dir, filename)
            
            try:
                # If the target file already exists, remove it
                if os.path.exists(filepath) and str(downloaded_file).lower() != filepath.lower():
                    os.remove(filepath)
                    logger.info(f"Removed existing file: {filepath}")
                
                # Check if the source and target paths are the same
                if str(downloaded_file).lower() == filepath.lower():
                    logger.info(f"File already at correct location and name: {filepath}")
                    return True
                
                # If download landed somewhere else, copy it to our target location
                if not downloaded_file.parent.samefile(Path(output_dir)):
                    # Copy the file to the target location
                    shutil.copy2(str(downloaded_file), filepath)
                    logger.info(f"Copied file from {downloaded_file} to {filepath}")
                else:
                    # Rename the file if it's already in our target directory but has a different name
                    os.rename(str(downloaded_file), filepath)
                    logger.info(f"Renamed {downloaded_file.name} to {os.path.basename(filepath)}")
                
                logger.info(f"Adventure file successfully saved to {filepath}")
                return True
                
            except Exception as e:
                logger.error(f"Error processing downloaded file: {e}")
                logger.debug(traceback.format_exc())
                
                # If processing failed but we found the file, consider it a success
                # and just report where it is
                logger.info(f"Adventure file available at: {downloaded_file}")
                return True
        else:
            logger.error("No Markdown files found after download completed")
            return False
            
    except Exception as e:
        logger.error(f"Error downloading adventure {adventure.get('name', 'unknown')}: {e}")
        logger.debug(traceback.format_exc())
        return False


def scrape_adventures() -> bool:
    """
    Main function to scrape D&D adventures from 5e.tools.
    
    Returns:
        Boolean indicating overall success
    """
    # Log system information
    try:
        os_info = get_os_info()
        logger.info(f"Running on: {os_info['system']} {os_info['release']}")
    except Exception as e:
        logger.error(f"Could not get OS info: {e}")
    
    # Check package compatibility
    is_compatible, warnings = check_dependency_compatibility()
    if not is_compatible:
        logger.warning("Some package compatibility issues detected:")
        for warning in warnings:
            logger.warning(f"  {warning}")
    
    if not SELENIUM_AVAILABLE:
        logger.error("Selenium is not available. Please install it with 'pip install selenium'")
        return False
    
    # Get adventure directory from config
    adventures_path = os.path.join("Data", "Adventure")
    os.makedirs(adventures_path, exist_ok=True)
    logger.info(f"Adventure output directory: {adventures_path}")
    
    # Initialize browser management modules
    browser_setup = BrowserSetup(logger)
    browser_cleanup = BrowserCleanup(logger)
    cookie_handler = CookieHandler(logger)
    driver = None
    
    try:
        # Get driver
        logger.info("Initializing browser...")
        driver = browser_setup.get_driver()
        
        # Register browser for automatic cleanup
        browser_cleanup.register_browser(driver)
        
        # Configure browser settings
        timeout = config.get("browser.page_load_timeout", 120)
        driver.set_page_load_timeout(timeout)
        
        # Setup wait objects
        wait = WebDriverWait(driver, 30)
        long_wait = WebDriverWait(driver, 60)
        short_wait = WebDriverWait(driver, 10)
        
        # Configure download settings at the start
        configure_download_settings(driver, adventures_path)
        
        # Load the adventures page
        logger.info("Loading adventures page and waiting for JavaScript initialization...")
        driver.get('https://5e.tools/adventures.html')
        logger.info("Page loaded: https://5e.tools/adventures.html")
        
        # Handle cookie consent
        logger.info("Checking for cookie consent...")
        if cookie_handler.handle_consent(driver, wait):
            logger.info("Cookie consent handled successfully")
        else:
            logger.warning("Failed to handle cookie consent, continuing anyway")
        
        # Wait for JavaScript to fully initialize
        time.sleep(5)  # Give extra time for JavaScript to initialize
        
        # Extract adventure metadata
        adventures = extract_adventure_metadata(driver, wait)
        
        if not adventures:
            logger.error("No adventures found or failed to extract metadata")
            return False
        
        # Save metadata to file
        metadata_file = os.path.join(adventures_path, "metadata_adventures.json")
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(adventures, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved metadata for {len(adventures)} adventures to {metadata_file}")
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            logger.debug(traceback.format_exc())
        
        # Download each adventure
        successful_downloads = 0
        
        for i, adventure in enumerate(adventures):
            logger.info(f"Processing adventure {i+1}/{len(adventures)}: {adventure['name']}")
            
            # Download the adventure
            success = download_adventure_as_markdown(driver, wait, adventure, adventures_path)
            
            if success:
                successful_downloads += 1
                logger.info(f"Successfully downloaded adventure ({i+1}/{len(adventures)}): {adventure['name']}")
            else:
                logger.warning(f"Failed to download adventure: {adventure['name']}")
            
            # Return to the adventure list
            logger.info("Returning to adventure list...")
            driver.get("https://5e.tools/adventures.html")
            time.sleep(2)  # Wait for navigation
            
            # Handle cookie consent again after navigation if needed
            if cookie_handler.handle_consent(driver, short_wait):
                logger.debug("Cookie consent handled on return to list")
            
            # Wait for list to reload
            try:
                wait.until(
                    lambda d: len(d.find_elements(By.CSS_SELECTOR, "a.lst__row-border")) > 0
                )
                logger.debug("Adventure list reloaded")
            except TimeoutException:
                logger.warning("Timeout waiting for adventure list to reload, continuing anyway")
        
        # Log final results
        logger.info(f"Adventure scraping completed: {successful_downloads}/{len(adventures)} adventures downloaded")
        return successful_downloads > 0
        
    except Exception as e:
        logger.error(f"Error in main adventure scraping process: {e}")
        logger.debug(traceback.format_exc())
        return False
        
    finally:
        # Clean up with enhanced method
        if driver:
            logger.info("Cleaning up browser resources...")
            ensure_browser_cleanup(driver, logger)
            logger.info("Browser cleanup completed")


if __name__ == "__main__":
    try:
        success = scrape_adventures()
        if success:
            adventures_path = os.path.abspath(os.path.join("Data", "Adventure"))
            print(f"Adventures successfully scraped and saved to {adventures_path}")
            sys.exit(0)
        else:
            print("Failed to scrape adventures. Check logs for details.")
            sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        logger.error(f"Main execution error: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1) 