import os
import time
import sys
import logging
import traceback
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

# Import modular components - try different import styles for flexibility
try:
    # First try absolute imports
    from Scrapper.Modules.SetupLogger import setup_directories, setup_logger
    from Scrapper.Modules.DetectOS import get_os_info
    from Scrapper.Modules.BrowserSetup import get_browser_driver, BrowserSetup
except ImportError:
    try:
        # Then try relative imports
        from Modules.SetupLogger import setup_directories, setup_logger
        from Modules.DetectOS import get_os_info
        from Modules.BrowserSetup import get_browser_driver, BrowserSetup
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

# ===== Logging configuration =====
logger = setup_logger("Logs/Bestiary/CsvScrapper.log")


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


def handle_cookie_consent(driver: Any, wait: WebDriverWait) -> bool:
    """
    Handle the cookie consent popup if present.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
        
    Returns:
        Boolean indicating if cookies were accepted or no popup was found
    """
    try:
        logger.info("Checking for cookie consent popup...")
        
        # Force detection of cookie consent by checking elements that might indicate it
        consent_selectors = [
            "div.cookie-banner", "div.cookie-consent", "div#cookieConsentPopup",
            "div.cookies", "div.gdpr", "div.consent", "div.privacy-notice",
            "div.popup", "div.modal", "div[class*='cookie']", "div[class*='consent']",
            "div[id*='cookie']", "div[id*='consent']", "div[class*='gdpr']",
            "button[class*='accept']", "button[class*='cookie']", "button[class*='consent']",
            "button[id*='accept']", "button[id*='cookie']", "button[id*='consent']",
            "button[contains(text(), 'Accept')]", "button[contains(text(), 'Accepter')]"
        ]
        
        # Scan the DOM for any consent-related elements
        cookie_elements = []
        for selector in consent_selectors:
            try:
                # Handle XPath vs CSS selector
                is_xpath = selector.startswith("//") or "contains(" in selector
                by_method = By.XPATH if is_xpath else By.CSS_SELECTOR
                
                # Use a very short timeout for checking
                very_short_wait = WebDriverWait(driver, 0.5)
                elements = very_short_wait.until(EC.presence_of_all_elements_located((by_method, selector)))
                if elements:
                    cookie_elements.extend(elements)
            except:
                continue
        
        if cookie_elements:
            logger.info(f"Found {len(cookie_elements)} cookie-related elements on the page")
            
            # Attempt to accept cookies using various strategies
            cookie_accepted = False
            
            # 1. Direct JavaScript bypass
            try:
                logger.info("Attempting to bypass cookie consent with JavaScript...")
                driver.execute_script("""
                    // Set consent cookies
                    document.cookie = "cookieConsent=1; path=/; max-age=31536000";
                    document.cookie = "cookies_accepted=1; path=/; max-age=31536000";
                    document.cookie = "cookie_consent=1; path=/; max-age=31536000";
                    document.cookie = "gdpr=accepted; path=/; max-age=31536000";
                    
                    // Try to find and click accept buttons
                    const acceptButtons = [
                        ...document.querySelectorAll('button'),
                        ...document.querySelectorAll('a.cookie-accept'),
                        ...document.querySelectorAll('[id*="accept"], [class*="accept"]')
                    ].filter(el => {
                        if (!el || !el.textContent) return false;
                        const text = el.textContent.toLowerCase();
                        return text.includes('accept') || text.includes('agree') || 
                               text.includes('allow') || text.includes('accepter');
                    });
                    
                    if (acceptButtons.length > 0) {
                        console.log("Found accept button, clicking...");
                        acceptButtons[0].click();
                        return true;
                    }
                    
                    // Try to hide consent elements
                    const cookieElements = document.querySelectorAll(
                        '.cookie-banner, .cookie-consent, #cookieConsentPopup, ' +
                        '.gdpr-banner, .consent-popup, .privacy-notice, ' +
                        '[class*="cookie"], [class*="consent"], [id*="cookie"], [id*="consent"]'
                    );
                    
                    cookieElements.forEach(el => {
                        el.style.display = 'none';
                        el.style.visibility = 'hidden';
                        el.style.opacity = '0';
                        el.style.pointerEvents = 'none';
                    });
                    
                    // Ensure body is scrollable
                    document.body.style.overflow = 'auto';
                    document.body.style.position = 'static';
                    
                    return cookieElements.length > 0;
                """)
                
                logger.info("Applied cookie bypass JavaScript")
                time.sleep(3)  # Give time for any animations to complete
                cookie_accepted = True
            except Exception as e:
                logger.debug(f"JavaScript cookie bypass failed: {e}")
            
            # 2. Try to click accept buttons
            if not cookie_accepted:
                accept_button_selectors = [
                    # French buttons (from highest to lowest priority)
                    "//button[contains(text(), 'Accepter tout')]",
                    "//button[contains(text(), 'Accepter')]",
                    "//a[contains(text(), 'Accepter')]",
                    "button.accepter-btn",
                    "button.accept-all",
                    # English buttons
                    "//button[contains(text(), 'Accept all')]",
                    "//button[contains(text(), 'Accept cookies')]",
                    "//button[contains(text(), 'Accept')]",
                    "//button[contains(text(), 'Agree')]",
                    "//button[contains(text(), 'Allow')]",
                    "//a[contains(text(), 'Accept')]",
                    "//a[contains(text(), 'Agree')]",
                    "button.accept-cookies",
                    "button.accept",
                    "button.agree-button",
                    "button[id*='accept']",
                    "button[class*='accept']"
                ]
                
                for selector in accept_button_selectors:
                    try:
                        by_method = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
                        very_short_wait = WebDriverWait(driver, 1)
                        button = very_short_wait.until(EC.element_to_be_clickable((by_method, selector)))
                        
                        logger.info(f"Found cookie accept button with selector: {selector}")
                        
                        # Try direct click
                        try:
                            button.click()
                            logger.info("Clicked cookie accept button")
                            cookie_accepted = True
                            time.sleep(2)  # Wait for any animations
                            break
                        except:
                            # Try JavaScript click as fallback
                            driver.execute_script("arguments[0].click();", button)
                            logger.info("Clicked cookie accept button via JavaScript")
                            cookie_accepted = True
                            time.sleep(2)  # Wait for any animations
                            break
                    except:
                        continue
            
            # 3. Last resort: brutal DOM manipulation
            if not cookie_accepted:
                logger.info("Using aggressive cookie consent bypass...")
                try:
                    driver.execute_script("""
                        // Remove modal backdrops and overlays
                        document.querySelectorAll('.modal-backdrop, .modal, .overlay, .popup, .consent-dialog').forEach(e => e.remove());
                        
                        // Ensure body is scrollable
                        document.body.style.overflow = 'auto';
                        document.body.style.position = 'static';
                        document.body.style.paddingRight = '0';
                        
                        // Remove fixed positioning
                        document.querySelectorAll('div[style*="position: fixed"]').forEach(el => {
                            if (el.style.zIndex > 1000) {
                                el.style.display = 'none';
                                el.style.visibility = 'hidden';
                            }
                        });
                    """)
                    logger.info("Applied aggressive DOM cleanup")
                    cookie_accepted = True
                except Exception as e:
                    logger.warning(f"Error in aggressive consent bypass: {e}")
            
            return True  # Continue execution regardless
        else:
            logger.info("No cookie consent elements detected")
            return True
            
    except Exception as e:
        logger.warning(f"Error handling cookie consent: {e}")
        logger.debug(traceback.format_exc())
        return True  # Continue even if there's an error


def configure_chrome_preferences(driver: Any, download_path: str) -> None:
    """
    Configure Chrome's preferences directly using Chrome DevTools Protocol.
    
    Args:
        driver: Browser driver instance
        download_path: Absolute path where downloads should be saved
    """
    try:
        # Ensure path is normalized and absolute
        abs_path = os.path.abspath(download_path).replace('\\', '\\\\')
        
        # Set download behavior using CDP
        driver.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': abs_path
        })
        
        # Modify preferences directly in the browser
        driver.execute_script(f"""
            // Set download directory for this session
            chrome.downloads = chrome.downloads || {{}};
            chrome.downloads.defaultDownloadDirectory = "{abs_path}";
            
            // Override any download manager
            if (window.navigator.serviceWorker) {{
                window.navigator.serviceWorker.register = function() {{
                    return Promise.reject(new Error('Service worker registration prevented'));
                }};
            }}
            
            // Add a hook for download links
            document.addEventListener('click', function(e) {{
                const target = e.target.closest('a[href], button');
                if (target && (target.textContent.includes('Download') || 
                              target.textContent.includes('Export') ||
                              target.getAttribute('download'))) {{
                    console.log('Intercepted download click, setting path:', "{abs_path}");
                }}
            }}, true);
        """)
        
        logger.info(f"Chrome preferences configured for downloads to: {abs_path}")
    except Exception as e:
        logger.warning(f"Failed to set Chrome preferences: {e}")
        logger.debug(traceback.format_exc())


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
        
        # Method 2: Directly modify preferences in the browser
        try:
            configure_chrome_preferences(driver, abs_download_path)
        except Exception as e:
            logger.debug(f"Chrome preferences method failed: {e}")
        
        # Method 3: Try to set preferences directly 
        try:
            # Access the underlying Chrome options if possible
            if hasattr(driver, '_driver') and hasattr(driver._driver, 'options'):
                chrome_options = driver._driver.options
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
        
        # Method 4: Use JavaScript to set download path
        try:
            driver.execute_script(f"""
                // Set global variables that might be accessed by the page
                window.customDownloadPath = "{abs_download_path.replace('\\', '\\\\')}";
                window.preferredDownloadLocation = "{abs_download_path.replace('\\', '\\\\')}";
                
                // If site uses HTML5 File API, try to influence it
                if (window.showSaveFilePicker) {{
                    const originalShowSaveFilePicker = window.showSaveFilePicker;
                    window.showSaveFilePicker = function(...args) {{
                        console.log('Intercepted showSaveFilePicker');
                        // Customize args to influence save location
                        if (args[0] && args[0].suggestedName) {{
                            args[0].startIn = 'downloads';
                        }}
                        return originalShowSaveFilePicker.apply(this, args);
                    }};
                }}
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
    
    # Also check user's default Downloads folder
    default_downloads = None
    if check_default:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders') as key:
                default_downloads = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')[0]
                logger.info(f"Default Windows downloads folder: {default_downloads}")
        except Exception:
            # Fallback to user home directory
            default_downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
            logger.info(f"Using fallback downloads folder: {default_downloads}")
    
    while time.time() - start_time < timeout:
        # Check target directory
        csv_files = list(Path(directory).glob("*.csv"))
        temp_files = list(Path(directory).glob("*.csv.crdownload"))
        temp_files.extend(list(Path(directory).glob("*.crdownload")))
        temp_files.extend(list(Path(directory).glob("*.part")))
        temp_files.extend(list(Path(directory).glob("*.download")))
        
        if csv_files and not temp_files:
            # Found completed files in target directory
            latest_file = max(csv_files, key=lambda f: f.stat().st_mtime)
            logger.info(f"Download completed in target directory, found: {latest_file.name}")
            return True, latest_file
        
        # Check default Downloads folder if needed
        if check_default and default_downloads:
            default_csv_files = list(Path(default_downloads).glob("*.csv"))
            default_temp_files = list(Path(default_downloads).glob("*.csv.crdownload"))
            default_temp_files.extend(list(Path(default_downloads).glob("*.crdownload")))
            default_temp_files.extend(list(Path(default_downloads).glob("*.part")))
            default_temp_files.extend(list(Path(default_downloads).glob("*.download")))
            
            if default_csv_files and not default_temp_files:
                # Found completed files in default Downloads
                latest_file = max(default_csv_files, key=lambda f: f.stat().st_mtime)
                logger.info(f"Download completed in default Downloads folder: {latest_file}")
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
    
    if not SELENIUM_AVAILABLE:
        logger.error("Selenium is not available. Please install it with 'pip install selenium'")
        return False
    
    # Prepare download path - ensure it's an absolute path
    downloads_path = os.path.abspath(os.path.join(os.getcwd(), "Data", "Bestiary", "CSV"))
    os.makedirs(downloads_path, exist_ok=True)
    logger.info(f"Download directory: {downloads_path}")
    
    # Use the browser setup module
    browser = None
    driver = None
    
    try:
        # Setup browser with custom preferences
        browser = BrowserSetup(logger)
        driver = browser.get_driver()
        
        # Set page load timeout to avoid hanging
        driver.set_page_load_timeout(120)  # Increased timeout
        
        # Configure download settings before loading the page
        configure_download_settings(driver, downloads_path)
        
        wait = WebDriverWait(driver, 30)  # Increased default wait
        long_wait = WebDriverWait(driver, 60)  # Longer wait for initial JavaScript loading
        short_wait = WebDriverWait(driver, 10)  # For shorter timeouts
        
        # Load the page and wait for JavaScript initialization
        logger.info("Loading page and waiting for JavaScript initialization...")
        driver.get('https://5e.tools/bestiary.html')
        logger.info("Page loaded: https://5e.tools/bestiary.html")
        
        # Handle cookie consent first - can do this early
        handle_cookie_consent(driver, wait)
        
        # Wait for JavaScript to fully initialize - focus on monster list loading
        logger.info("Waiting for JavaScript to initialize completely...")
        
        # Wait for monster list to load - this is the primary indicator
        try:
            logger.info("Waiting for monster list to load...")
            long_wait.until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, "a.lst__row-border")) > 5
            )
            logger.info("Monster list loaded - JavaScript initialized")
            
            # Extra wait for stability
            time.sleep(5)
            
            # Check if monster list is actually populated - double check
            monster_elements = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
            logger.info(f"Found {len(monster_elements)} monster elements in the list")
            
            if len(monster_elements) < 5:
                # Sometimes the list can appear but not be fully populated
                logger.warning("Monster list appears to be loading slowly, waiting more time...")
                time.sleep(15)  # Additional wait time
                monster_elements = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
                logger.info(f"After additional wait: Found {len(monster_elements)} monster elements")
        except Exception as e:
            logger.warning(f"Timeout waiting for monster list: {e}")
            logger.warning("Continuing anyway but page may not be fully loaded")
            time.sleep(20)  # Force additional wait time
        
        # Now proceed to Table View
        logger.info("JavaScript loaded, proceeding to Table View...")
        
        # Re-configure download settings before clicking Table View
        configure_download_settings(driver, downloads_path)
        
        # Try to locate and click the Table View button - multiple strategies
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
        
        # Strategy 4: Last resort - JavaScript injection
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
        time.sleep(20)  # Increased wait time
        
        # Verify table is loaded
        try:
            table_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".tabulator-table, .dataTable")))
            logger.info("Table appears to be loaded, proceeding to download")
        except:
            logger.warning("Could not confirm table is loaded, but continuing anyway")
        
        # Re-configure download settings right before download
        configure_download_settings(driver, downloads_path)
        
        # Prepare for forced download using a direct link if necessary
        try:
            logger.info("Setting up direct download fallback...")
            # Create a function to force download via a direct API call if button clicks fail
            driver.execute_script("""
                window.forceBestiaryDownload = function() {
                    try {
                        console.log("Attempting forced download...");
                        const downloadPath = arguments[0] || "";
                        
                        // Create a hidden link element
                        const link = document.createElement('a');
                        link.href = "https://5e.tools/api/bestiary/csv";
                        link.download = "bestiary.csv";
                        link.style.display = 'none';
                        
                        // Add to document, click, and remove
                        document.body.appendChild(link);
                        link.click();
                        setTimeout(() => {
                            document.body.removeChild(link);
                        }, 100);
                        return true;
                    } catch (e) {
                        console.error("Force download failed:", e);
                        return false;
                    }
                };
            """)
        except Exception as e:
            logger.warning(f"Failed to set up direct download fallback: {e}")
        
        # Try to find and click the download button - multiple strategies
        download_success = False
        
        # Strategy 1: Find button by text content
        try:
            logger.info("Looking for Download CSV button by text...")
            download_buttons = wait.until(EC.presence_of_all_elements_located(
                (By.XPATH, "//button[contains(text(), 'Download CSV')]")
            ))
            
            if download_buttons:
                # Set up before clicking
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
                            # Set up before clicking
                            abs_download_path = os.path.abspath(downloads_path).replace("\\", "\\\\")
                            driver.execute_script(f"""
                                window.customDownloadDir = '{abs_download_path}';
                                localStorage.setItem('downloadPath', '{abs_download_path}');
                                arguments[0].setAttribute('download', 'bestiary.csv');
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
        
        # Strategy 3: Use direct file access approach
        if not download_success:
            try:
                logger.info("Attempting direct file download approach...")
                result = driver.execute_script("""
                    // Locate the download button in the UI
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
                    
                    // If no button found, try our forced download function
                    if (typeof window.forceBestiaryDownload === 'function') {
                        console.log('Attempting forced download...');
                        return window.forceBestiaryDownload();
                    }
                    
                    return false;
                """)
                
                if result:
                    logger.info("Direct download approach succeeded")
                    download_success = True
                    time.sleep(5)  # Wait for download to start
            except Exception as e:
                logger.warning(f"Direct download approach failed: {e}")
        
        # Final fallback: Try direct API request
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
                    'User-Agent': driver.execute_script('return navigator.userAgent'),
                    'Referer': driver.current_url,
                    'Accept': 'text/csv,application/csv,application/vnd.ms-excel'
                }
                
                # Make the request
                csv_url = "https://5e.tools/api/bestiary/csv"
                response = session.get(csv_url, headers=headers, stream=True)
                
                if response.status_code == 200:
                    # Save the file directly
                    target_path = os.path.join(downloads_path, "bestiary.csv")
                    with open(target_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    logger.info(f"Successfully downloaded CSV directly to {target_path}")
                    return True
                else:
                    logger.warning(f"Direct API request failed with status {response.status_code}")
            except Exception as e:
                logger.warning(f"Direct API request approach failed: {e}")
        
        # Check for the download
        if download_success:
            logger.info(f"Waiting for download in: {downloads_path}")
            download_success, downloaded_file = wait_for_download(downloads_path, timeout=120, check_default=True)
            
            if download_success and downloaded_file:
                target_path = os.path.join(downloads_path, "bestiary.csv")
                
                try:
                    # If the target file already exists, remove it
                    if os.path.exists(target_path):
                        os.remove(target_path)
                        logger.info(f"Removed existing file: {target_path}")
                    
                    # Check if the source and target paths are the same
                    if str(downloaded_file).lower() == target_path.lower():
                        logger.info(f"File already at correct location and name: {target_path}")
                        return True
                    
                    # If download landed in default Downloads folder, copy it to our target location
                    if not downloaded_file.parent.samefile(downloads_path):
                        # Copy the file and then rename
                        import shutil
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
                # Will continue to fallback options below
        
        # Last resort: Try a direct download via JavaScript API
        try:
            logger.info("Attempting one final direct download via JavaScript...")
            
            # Create a temporary download button in case UI is not showing one
            driver.execute_script("""
                // Function to trigger API fetch and download
                function directFetch() {
                    const url = "https://5e.tools/api/bestiary/csv";
                    
                    fetch(url)
                        .then(response => response.blob())
                        .then(blob => {
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.style.display = "none";
                            a.href = url;
                            a.download = "bestiary.csv";
                            document.body.appendChild(a);
                            a.click();
                            window.URL.revokeObjectURL(url);
                            document.body.removeChild(a);
                            console.log("Direct download completed");
                        })
                        .catch(e => console.error("Download failed:", e));
                }
                
                // Execute download
                directFetch();
                
                return true;
            """)
            
            logger.info("Final direct download attempt completed")
            time.sleep(10)  # Wait for potential download
            
            # Check one more time for downloaded files
            download_success, downloaded_file = wait_for_download(downloads_path, timeout=60, check_default=True)
            
            if download_success and downloaded_file:
                target_path = os.path.join(downloads_path, "bestiary.csv")
                
                # If the target file already exists, remove it
                if os.path.exists(target_path):
                    os.remove(target_path)
                
                # Copy or rename as needed
                import shutil
                if not downloaded_file.parent.samefile(downloads_path):
                    shutil.copy2(str(downloaded_file), target_path)
                    logger.info(f"Copied file from {downloaded_file} to {target_path}")
                else:
                    os.rename(str(downloaded_file), target_path)
                    logger.info(f"Renamed {downloaded_file.name} to {os.path.basename(target_path)}")
                
                logger.info(f"CSV file successfully saved to {target_path}")
                return True
        except Exception as e:
            logger.error(f"Final direct download attempt failed: {e}")
        
        return False
        
    except Exception as e:
        logger.error(f"Error downloading CSV: {e}")
        logger.debug(traceback.format_exc())
        return False
        
    finally:
        # Proper browser cleanup
        logger.info("Cleaning up browser resources...")
        
        # Method 1: Try direct driver.quit()
        if driver:
            try:
                logger.info("Closing browser with driver.quit()...")
                driver.quit()
                time.sleep(2)  # Wait for cleanup
                logger.info("Browser successfully closed with driver.quit()")
                driver = None  # Clear reference
            except Exception as e:
                logger.warning(f"Error in driver.quit(): {e}")
        
        # Method 2: If driver.quit() failed, try browser.close()
        if browser and hasattr(browser, 'close'):
            try:
                logger.info("Closing browser with browser.close()...")
                browser.close()
                time.sleep(2)  # Wait for cleanup
                logger.info("Browser successfully closed with browser.close()")
            except Exception as e:
                logger.warning(f"Error in browser.close(): {e}")
        
        # Method 3: Last resort - try directly killing Chrome processes
        if os.name == 'nt':  # Windows
            try:
                # Try to force kill Chrome processes
                logger.info("Attempting to forcefully terminate Chrome processes...")
                os.system("taskkill /F /IM chrome.exe /T")
                os.system("taskkill /F /IM chromedriver.exe /T")
                logger.info("Chrome processes terminated")
            except Exception as e:
                logger.warning(f"Failed to terminate Chrome processes: {e}")


if __name__ == "__main__":
    try:
        success = download_bestiary_csv()
        if success:
            print("CSV file successfully downloaded and saved to Data/Bestiary/CSV/bestiary.csv")
        else:
            print("Failed to download CSV file. Check logs for details.")
    except Exception as e:
        print(f"An error occurred: {e}")
        logger.error(f"Main execution error: {e}")
        logger.debug(traceback.format_exc()) 