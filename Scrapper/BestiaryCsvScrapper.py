import os
import time
import sys
import logging
import traceback
import shutil
import winreg
from pathlib import Path
from typing import Optional, Any, List, Dict, Tuple
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
    from Scrapper.Modules.DetectOS import get_os_info, is_windows
    from Scrapper.Modules.BrowserSetup import BrowserSetup
    from Scrapper.Modules.BrowserCleanup import BrowserCleanup, ensure_browser_cleanup
    from Scrapper.Modules.CookieHandler import CookieHandler
    from Scrapper.Modules.ConfigManager import ConfigManager, get_config
    from Scrapper.Modules.DetectPackages import check_dependency_compatibility, get_user_agent
except ImportError:
    try:
        # Then try relative imports
        from Modules.SetupLogger import setup_directories, get_logger
        from Modules.DetectOS import get_os_info, is_windows
        from Modules.BrowserSetup import BrowserSetup
        from Modules.BrowserCleanup import BrowserCleanup, ensure_browser_cleanup
        from Modules.CookieHandler import CookieHandler
        from Modules.ConfigManager import ConfigManager, get_config
        from Modules.DetectPackages import check_dependency_compatibility, get_user_agent
    except ImportError:
        # As a last resort, try direct imports if files are in the same directory
        print("Failed to import modules. Check your project structure and Python path.")
        print(f"Current sys.path: {sys.path}")
        sys.exit(1)

# ===== Setup directories =====
setup_directories([
    "Logs/Bestiary", 
    "Data/Bestiary/CSV"
])

# ===== Get configuration =====
config = get_config()

# ===== Logging configuration =====
logger = get_logger("BestiaryCsvScrapper", log_dir="Logs/Bestiary", clean_logs=True)


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


def get_windows_download_folder() -> str:
    """
    Get the path to the Windows default download folder.
    
    Returns:
        Path to the Windows download folder
    """
    try:
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
                        this.download = this.download || 'bestiary.csv';
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
    Wait for a .csv file to appear in the directory and be fully downloaded.
    
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
    
    # Also check user's default Downloads folder if on Windows
    default_downloads = None
    if check_default and is_windows():
        default_downloads = get_windows_download_folder()
        logger.info(f"Default Windows downloads folder: {default_downloads}")
    
    # Also check the Data/Downloads folder
    data_downloads = os.path.abspath(os.path.join("Data", "Downloads"))
    if os.path.exists(data_downloads):
        logger.info(f"Checking additional downloads folder: {data_downloads}")
    
    directory_path = Path(directory)
    
    while time.time() - start_time < timeout:
        # Check target directory
        csv_files = list(directory_path.glob("*.csv"))
        temp_files = list(directory_path.glob("*.csv.crdownload"))
        temp_files.extend(list(directory_path.glob("*.crdownload")))
        temp_files.extend(list(directory_path.glob("*.part")))
        temp_files.extend(list(directory_path.glob("*.download")))
        
        if csv_files and not temp_files:
            # Found completed files in target directory
            latest_file = max(csv_files, key=lambda f: f.stat().st_mtime)
            logger.info(f"Download completed in target directory, found: {latest_file.name}")
            return True, latest_file
        
        # Check default Windows Downloads folder if needed
        if check_default and default_downloads:
            downloads_path = Path(default_downloads)
            default_csv_files = list(downloads_path.glob("*.csv"))
            default_temp_files = list(downloads_path.glob("*.csv.crdownload"))
            default_temp_files.extend(list(downloads_path.glob("*.crdownload")))
            default_temp_files.extend(list(downloads_path.glob("*.part")))
            default_temp_files.extend(list(downloads_path.glob("*.download")))
            
            if default_csv_files and not default_temp_files:
                # Found completed files in default Downloads
                latest_file = max(default_csv_files, key=lambda f: f.stat().st_mtime)
                logger.info(f"Download completed in default Downloads folder: {latest_file}")
                return True, latest_file
        
        # Check Data/Downloads folder
        if os.path.exists(data_downloads):
            data_downloads_path = Path(data_downloads)
            data_csv_files = list(data_downloads_path.glob("*.csv"))
            data_temp_files = list(data_downloads_path.glob("*.csv.crdownload"))
            data_temp_files.extend(list(data_downloads_path.glob("*.crdownload")))
            data_temp_files.extend(list(data_downloads_path.glob("*.part")))
            data_temp_files.extend(list(data_downloads_path.glob("*.download")))
            
            if data_csv_files and not data_temp_files:
                # Found completed files in Data/Downloads
                latest_file = max(data_csv_files, key=lambda f: f.stat().st_mtime)
                logger.info(f"Download completed in Data/Downloads folder: {latest_file}")
                return True, latest_file
        
        # Log download progress
        if temp_files:
            logger.info("Download in progress...")
        
        time.sleep(1)
    
    logger.error(f"Download timed out after {timeout} seconds")
    return False, None


def download_bestiary_csv() -> bool:
    """
    Download the bestiary CSV file.
    
    Returns:
        Boolean indicating success
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
    
    # Get download directory from config - IMPORTANT: Always use Data/Bestiary/CSV
    downloads_path = os.path.abspath(os.path.join("Data", "Bestiary", "CSV"))
    os.makedirs(downloads_path, exist_ok=True)
    logger.info(f"Target download directory: {downloads_path}")
    
    # Initialize browser management modules
    browser_setup = BrowserSetup(logger)
    browser_cleanup = BrowserCleanup(logger)
    cookie_handler = CookieHandler(logger)
    driver = None
    
    try:
        # Get driver
        driver = browser_setup.get_driver()
        
        # Register browser for automatic cleanup
        browser_cleanup.register_browser(driver)
        
        # Configure browser settings
        timeout = config.get("browser.page_load_timeout", 120)
        driver.set_page_load_timeout(timeout)
        
        # Configure download settings before loading the page
        configure_download_settings(driver, downloads_path)
        
        # Setup wait objects
        wait = WebDriverWait(driver, 30)
        long_wait = WebDriverWait(driver, 60)
        short_wait = WebDriverWait(driver, 10)
        
        # Load the page
        logger.info("Loading page and waiting for JavaScript initialization...")
        driver.get('https://5e.tools/bestiary.html')
        logger.info("Page loaded: https://5e.tools/bestiary.html")
        
        # Handle cookie consent
        if cookie_handler.handle_consent(driver):
            logger.info("Cookie consent handled.")
        
        # Wait for JavaScript to fully initialize - focus on monster list loading
        logger.info("Waiting for JavaScript to initialize completely...")
        
        # Wait for monster list to load
        try:
            logger.info("Waiting for monster list to load...")
            long_wait.until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, "a.lst__row-border")) > 5
            )
            logger.info("Monster list loaded - JavaScript initialized")
            
            # Extra wait for stability
            time.sleep(5)
            
            # Check if monster list is actually populated
            monster_elements = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
            logger.info(f"Found {len(monster_elements)} monster elements in the list")
            
            if len(monster_elements) < 5:
                logger.warning("Monster list appears to be loading slowly, waiting more time...")
                time.sleep(15)
                monster_elements = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
                logger.info(f"After additional wait: Found {len(monster_elements)} monster elements")
        except Exception as e:
            logger.warning(f"Timeout waiting for monster list: {e}")
            logger.warning("Continuing anyway but page may not be fully loaded")
            time.sleep(20)
        
        # Now proceed to Table View
        logger.info("JavaScript loaded, proceeding to Table View...")
        
        # Reconfigure download settings before clicking Table View
        configure_download_settings(driver, downloads_path)
        
        # Try to find and click the Table View button using multiple strategies
        table_button_found = False
        
        # Strategy 1: Find by ID
        try:
            logger.info("Looking for Table View button by ID...")
            table_button = wait.until(EC.element_to_be_clickable((By.ID, "btn-show-table")))
            logger.info("Found Table View button by ID, clicking...")
            driver.execute_script("arguments[0].click();", table_button)
            logger.info("Successfully clicked Table View button")
            table_button_found = True
        except Exception as e:
            logger.warning(f"Could not find Table View button by ID: {e}")
        
        # Strategy 2: Find by title attribute
        if not table_button_found:
            try:
                logger.info("Looking for Table View button by title attribute...")
                buttons = driver.find_elements(By.CSS_SELECTOR, "button[title*='View and Download']")
                if buttons:
                    logger.info("Found Table View button by title, clicking...")
                    driver.execute_script("arguments[0].click();", buttons[0])
                    logger.info("Successfully clicked Table View button by title")
                    table_button_found = True
            except Exception as e:
                logger.warning(f"Could not find Table View button by title: {e}")
        
        # Strategy 3: Find any button that might be the Table View button
        if not table_button_found:
            try:
                logger.info("Looking for Table View button by text content...")
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for button in buttons:
                    try:
                        text = button.text.lower()
                        title = button.get_attribute("title") or ""
                        if "table" in text or "table" in title.lower() or "csv" in text or "download" in text:
                            logger.info(f"Found possible Table View button: '{text}' or '{title}', clicking...")
                            driver.execute_script("arguments[0].click();", button)
                            logger.info("Successfully clicked possible Table View button")
                            table_button_found = True
                            break
                    except:
                        continue
            except Exception as e:
                logger.warning(f"Could not find Table View button by text: {e}")
        
        # JavaScript injection as last resort
        if not table_button_found:
            try:
                logger.info("Trying to find and click Table View button via JavaScript...")
                result = driver.execute_script("""
                    // Try to find the button by ID
                    let button = document.getElementById('btn-show-table');
                    
                    // If not found, try by title
                    if (!button) {
                        const buttons = Array.from(document.querySelectorAll('button'));
                        button = buttons.find(b => {
                            if (b.title && b.title.includes('View and Download')) return true;
                            if (b.textContent && (
                                b.textContent.toLowerCase().includes('table') || 
                                b.textContent.toLowerCase().includes('csv') ||
                                b.textContent.toLowerCase().includes('download')
                            )) return true;
                            return false;
                        });
                    }
                    
                    // Click the button if found
                    if (button) {
                        console.log('Found Table View button via JavaScript, clicking...');
                        button.click();
                        return true;
                    }
                    
                    return false;
                """)
                
                if result:
                    logger.info("Successfully clicked Table View button via JavaScript")
                    table_button_found = True
                else:
                    logger.warning("No Table View button found via JavaScript")
            except Exception as e:
                logger.warning(f"JavaScript approach for Table View button failed: {e}")
        
        if not table_button_found:
            logger.error("Failed to find and click Table View button")
            raise Exception("Could not activate Table View")
        
        # Wait for table to load
        logger.info("Waiting for table to fully load...")
        time.sleep(20)
        
        # Verify table is loaded
        try:
            table_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tabulator-table, .dataTable")))
            logger.info("Table appears to be loaded, proceeding to download")
        except:
            logger.warning("Could not confirm table is loaded, but continuing anyway")
        
        # Reconfigure download settings right before download
        configure_download_settings(driver, downloads_path)
        
        # Try to find and click the download button
        download_success = False
        
        # Strategy 1: Find button by text content
        try:
            logger.info("Looking for Download CSV button by text...")
            download_buttons = wait.until(EC.presence_of_all_elements_located(
                (By.XPATH, "//button[contains(text(), 'Download CSV')]")
            ))
            
            if download_buttons:
                # Final download path setup
                abs_download_path = os.path.abspath(downloads_path).replace("\\", "\\\\")
                driver.execute_script(f"""
                    window.customDownloadDir = '{abs_download_path}';
                    window.localStorage.setItem('downloadPath', '{abs_download_path}');
                    
                    // Try to modify the button's behavior
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {{
                        if (btn.textContent.includes('Download CSV')) {{
                            // Force download attribute
                            btn.setAttribute('download', 'bestiary.csv');
                        }}
                    }}
                """)
                
                # Click the button
                logger.info("Found Download CSV button, clicking...")
                driver.execute_script("arguments[0].click();", download_buttons[0])
                logger.info("Clicked Download CSV button")
                download_success = True
                time.sleep(5)  # Wait for download to start
            else:
                logger.warning("No Download CSV button found by text")
        except Exception as e:
            logger.warning(f"Could not find or click Download CSV button by text: {e}")
        
        # Strategy 2: Try alternative button selectors
        if not download_success:
            try:
                logger.info("Looking for Download CSV button by class...")
                buttons = driver.find_elements(By.CSS_SELECTOR, "button.ve-btn.ve-btn-primary")
                
                for button in buttons:
                    try:
                        text = button.text.lower()
                        if "download" in text or "csv" in text:
                            # Setup before clicking
                            abs_download_path = os.path.abspath(downloads_path).replace("\\", "\\\\")
                            driver.execute_script(f"""
                                arguments[0].setAttribute('download', 'bestiary.csv');
                                window.customDownloadDir = '{abs_download_path}';
                                window.localStorage.setItem('downloadPath', '{abs_download_path}');
                            """, button)
                            
                            # Click the button
                            logger.info(f"Found Download button with text '{button.text}', clicking...")
                            driver.execute_script("arguments[0].click();", button)
                            logger.info("Clicked Download button")
                            download_success = True
                            time.sleep(5)  # Wait for download to start
                            break
                    except:
                        continue
            except Exception as e:
                logger.warning(f"Could not find or click Download CSV button by class: {e}")
        
        # Strategy 3: Direct API call approach
        if not download_success:
            try:
                logger.info("Attempting direct file download approach...")
                result = driver.execute_script("""
                    // First try to locate and click a download button
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const downloadButton = buttons.find(btn => 
                        btn.textContent.includes('Download CSV') || 
                        (btn.classList.contains('ve-btn-primary') && 
                         btn.textContent.toLowerCase().includes('download'))
                    );
                    
                    if (downloadButton) {
                        console.log('Found download button, clicking directly...');
                        downloadButton.click();
                        return true;
                    }
                    
                    // If no button found, create our own download link
                    const csvUrl = "https://5e.tools/api/bestiary/csv";
                    const a = document.createElement('a');
                    a.href = csvUrl;
                    a.download = "bestiary.csv";
                    a.style.display = 'none';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    console.log('Created temporary download link');
                    return true;
                """)
                
                if result:
                    logger.info("Direct download approach succeeded")
                    download_success = True
                    time.sleep(5)  # Wait for download to start
            except Exception as e:
                logger.warning(f"Direct download approach failed: {e}")
        
        # Final direct HTTP request approach
        if not download_success:
            try:
                logger.info("Attempting direct API request for CSV download...")
                
                # Get cookies from the current session
                cookies = driver.get_cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                
                # Create a requests session with the same cookies
                import requests
                session = requests.Session()
                for name, value in cookie_dict.items():
                    session.cookies.set(name, value)
                
                # Set headers to mimic browser
                headers = {
                    'User-Agent': get_user_agent(),
                    'Referer': 'https://5e.tools/bestiary.html',
                    'Accept': 'text/csv,application/csv,application/vnd.ms-excel'
                }
                
                # Make the request
                csv_url = "https://5e.tools/api/bestiary/csv"
                response = session.get(csv_url, headers=headers, stream=True)
                
                if response.status_code == 200:
                    # Save the file directly to the target path
                    target_path = os.path.join(downloads_path, "bestiary.csv")
                    with open(target_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    logger.info(f"Successfully downloaded CSV directly to {target_path}")
                    return True
                else:
                    logger.warning(f"Direct API request failed with status {response.status_code}")
            except Exception as e:
                logger.warning(f"Direct API request failed with error: {e}")
        
        # Check for downloaded file and process it
        if download_success:
            logger.info(f"Waiting for download in: {downloads_path}")
            download_success, downloaded_file = wait_for_download(downloads_path, timeout=120, check_default=True)
            
            if download_success and downloaded_file:
                target_path = os.path.join(downloads_path, "bestiary.csv")
                
                try:
                    # If the target file already exists, remove it
                    if os.path.exists(target_path) and str(downloaded_file).lower() != target_path.lower():
                        os.remove(target_path)
                        logger.info(f"Removed existing file: {target_path}")
                    
                    # Check if the source and target paths are the same
                    if str(downloaded_file).lower() == target_path.lower():
                        logger.info(f"File already at correct location and name: {target_path}")
                        return True
                    
                    # If download landed somewhere else, copy it to our target location
                    if not downloaded_file.parent.samefile(downloads_path):
                        # Copy the file to the target location
                        shutil.copy2(str(downloaded_file), target_path)
                        logger.info(f"Copied file from {downloaded_file} to {target_path}")
                    else:
                        # Rename the file if it's already in our target directory
                        os.rename(str(downloaded_file), target_path)
                        logger.info(f"Renamed {downloaded_file.name} to {os.path.basename(target_path)}")
                    
                    logger.info(f"CSV file successfully saved to {target_path}")
                    return True
                    
                except Exception as e:
                    logger.error(f"Error processing downloaded file: {e}")
                    logger.debug(traceback.format_exc())
                    
                    # If processing failed but we found the file, consider it a success
                    # and just report where it is
                    logger.info(f"CSV file available at: {downloaded_file}")
                    return True
            else:
                logger.error("No CSV files found after download completed")
        
        return False
        
    except Exception as e:
        logger.error(f"Error downloading CSV: {e}")
        logger.debug(traceback.format_exc())
        return False
        
    finally:
        # Clean up with enhanced method
        if driver:
            ensure_browser_cleanup(driver, logger)


if __name__ == "__main__":
    try:
        success = download_bestiary_csv()
        if success:
            csv_path = os.path.abspath(os.path.join("Data", "Bestiary", "CSV", "bestiary.csv"))
            print(f"CSV file successfully downloaded and saved to {csv_path}")
        else:
            print("Failed to download CSV file. Check logs for details.")
    except Exception as e:
        print(f"An error occurred: {e}")
        logger.error(f"Main execution error: {e}")
        logger.debug(traceback.format_exc()) 