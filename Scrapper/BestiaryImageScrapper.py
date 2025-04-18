import os
import re
import time
import asyncio
import aiohttp
import logging
import sys
import traceback
from typing import List, Optional, Any, Dict
from dataclasses import dataclass
from urllib.parse import urljoin

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
    from Scrapper.Modules.DetectPackages import check_dependency_compatibility, get_user_agent
except ImportError:
    try:
        # Then try relative imports
        from Modules.SetupLogger import setup_directories, get_logger
        from Modules.DetectOS import get_os_info
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
    "Data/Bestiary/Images/tokens", 
    "Data/Bestiary/Images/full"
])

# ===== Get configuration =====
config = get_config()

# ===== Logging configuration =====
logger = get_logger("BestiaryImageScrapper", log_dir="Logs/Bestiary")

# ===== Data classes =====
@dataclass
class MonsterImage:
    """Class representing a monster's image data"""
    name: str
    source: Optional[str]
    token_url: Optional[str] = None
    full_url: Optional[str] = None


def sanitize_filename(name: str) -> str:
    """
    Convert a string to a safe filename
    
    Args:
        name: String to sanitize
        
    Returns:
        Sanitized string
    """
    return re.sub(r'[\\/*?:"<>|]', "", name)


async def download_image(
    session: aiohttp.ClientSession, 
    image_url: str, 
    save_path: str,
    base_url: str = "https://5e.tools/"
) -> bool:
    """
    Downloads an image asynchronously
    
    Args:
        session: aiohttp client session
        image_url: URL of the image
        save_path: Path to save the image
        base_url: Base URL to prepend to relative URLs
        
    Returns:
        Boolean indicating success
    """
    try:
        # Handle relative URLs
        if not image_url.startswith('http'):
            image_url = urljoin(base_url, image_url)
        
        # Set headers to mimic browser using the user agent from our module
        headers = {
            'User-Agent': get_user_agent(),
            'Accept': 'image/webp,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://5e.tools/'
        }
        
        # Download image
        async with session.get(image_url, headers=headers) as response:
            if response.status == 200:
                # Ensure directory exists
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                
                # Save image
                with open(save_path, 'wb') as f:
                    f.write(await response.read())
                logger.info(f"Image downloaded successfully: {save_path}")
                return True
            else:
                logger.error(f"Failed to download {image_url}, status: {response.status}")
                return False
    except Exception as e:
        logger.error(f"Error downloading image {image_url}: {e}")
        return False


async def process_monster_batch(
    driver: Any, 
    monster_elements: List, 
    session: aiohttp.ClientSession, 
    start_idx: int, 
    batch_size: int, 
    total_monsters: int
) -> None:
    """
    Process a batch of monsters without reloading the page
    
    Args:
        driver: Browser driver instance
        monster_elements: List of monster elements
        session: aiohttp client session
        start_idx: Starting index
        batch_size: Batch size
        total_monsters: Total number of monsters
    """
    wait = WebDriverWait(driver, 10)
    short_wait = WebDriverWait(driver, 3)  # Shorter timeout for optional elements
    
    for i in range(start_idx, min(start_idx + batch_size, total_monsters)):
        try:
            # Find current monster in the list
            current_monster = monster_elements[i]
            
            # Extract name and source
            try:
                name_el = current_monster.find_element(By.CSS_SELECTOR, "span.bold")
                name = name_el.text.strip()
            except Exception:
                try:
                    # Alternate selector for name
                    name_el = current_monster.find_element(By.CSS_SELECTOR, "span.best-ecgen__name")
                    name = name_el.text.strip()
                except Exception as e:
                    logger.warning(f"Could not find name for monster at index {i}: {e}")
                    name = f"unknown_monster_{i}"
            
            # Try to get source with improved selectors for MM'25 and other sources
            source = "unknown"
            try:
                # Try multiple source selectors in order
                for selector in [
                    "span[class*='source__']",    # Match any source class (best option)
                    "span.source__XMM",           # Specific MM'25 source
                    "span.ve-col-2.ve-text-center", # Layout-based selector
                    "span.help-subtle",           # Original selector
                    "span.best-ecgen__source"     # Alternative selector
                ]:
                    try:
                        source_elements = current_monster.find_elements(By.CSS_SELECTOR, selector)
                        if source_elements:
                            for source_el in source_elements:
                                # Extract source text
                                src_text = source_el.text.strip()
                                if src_text:
                                    source = src_text.replace(" ", "")
                                    logger.debug(f"Found source '{source}' for monster {name} using selector: {selector}")
                                    break
                            if source != "unknown":
                                break
                    except Exception as e:
                        continue

                # If still not found, try looking for title attribute
                if source == "unknown":
                    spans = current_monster.find_elements(By.TAG_NAME, "span")
                    for span in spans:
                        try:
                            title = span.get_attribute("title")
                            if title and ("Monster Manual" in title or "Manual of" in title):
                                source = span.text.strip().replace(" ", "")
                                logger.debug(f"Found source '{source}' from title attribute for monster {name}")
                                break
                        except:
                            continue
            except Exception as e:
                logger.warning(f"Error finding source for monster {name}: {e}")
                source = "unknown"

            # Log source finding result
            if source == "unknown":
                logger.warning(f"Could not determine source for monster {name}, using 'unknown'")
            
            safe_name = sanitize_filename(f"{name.lower()}_{source.lower()}")
            logger.info(f"Processing monster {i+1}/{total_monsters}: {name} ({source})")
            
            # Ensure element is visible
            driver.execute_script("arguments[0].scrollIntoView(true);", current_monster)
            time.sleep(0.5)  # Small delay for scrolling
            
            # Click on the monster and wait for the token
            driver.execute_script("arguments[0].click();", current_monster)
            
            # Process token and full image
            token_url = None
            full_url = None
            
            # Wait and download token
            try:
                token_img = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "img.stats__token")))
                token_url = token_img.get_attribute("src")
                if token_url:
                    token_path = os.path.join("Data", "Bestiary", "Images", "tokens", f"{safe_name}.webp")
                    await download_image(session, token_url, token_path)
                
                # Try to click Images tab with a short timeout - it might not exist
                has_images_tab = False
                try:
                    # First check if the Images tab exists
                    images_tabs = short_wait.until(EC.presence_of_all_elements_located(
                        (By.XPATH, "//button[contains(@class, 'ui-tab__btn-tab-head') and contains(@class, 'stat-tab-gen')]")
                    ))
                    
                    # Find the Images tab if it exists
                    images_tab = None
                    for tab in images_tabs:
                        if "Images" in tab.text:
                            images_tab = tab
                            has_images_tab = True
                            break
                    
                    if has_images_tab and images_tab:
                        logger.debug(f"Images tab found for {name}")
                        driver.execute_script("arguments[0].click();", images_tab)
                        time.sleep(0.5)  # Short delay for tab change
                        
                        # Wait and download full image with a short timeout
                        try:
                            full_img_container = short_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.rd__wrp-image")))
                            full_img_link = full_img_container.find_element(By.CSS_SELECTOR, "a")
                            full_url = full_img_link.get_attribute("href")
                            
                            if full_url:
                                full_path = os.path.join("Data", "Bestiary", "Images", "full", f"{safe_name}.webp")
                                await download_image(session, full_url, full_path)
                        except Exception as e:
                            logger.debug(f"No full image for {name}: {e}")
                    else:
                        logger.debug(f"No Images tab found for {name}")
                except Exception as e:
                    logger.debug(f"Failed to check for Images tab for {name}: {e}")
            except Exception as e:
                logger.warning(f"Error processing token for {name}: {e}")
            
            # No need to close anything - just continue to the next monster
            # The monster details panel will update when we select another monster

        except Exception as e:
            logger.error(f"Error processing monster at index {i}: {e}")
            logger.debug(traceback.format_exc())
            continue


def disable_filters(driver: Any, wait: WebDriverWait) -> bool:
    """
    Disable all filters to show all monsters.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
        
    Returns:
        Boolean indicating success
    """
    try:
        # Find the filter container
        logger.info("Looking for filter container...")
        filter_container = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".fltr__mini-view"))
        )
        logger.info("Found filter container, looking for filter pills...")
        
        # Find both types of filter pills by data-state
        active_filters = filter_container.find_elements(By.CSS_SELECTOR, ".fltr__mini-pill[data-state='yes']")
        deselected_filters = filter_container.find_elements(By.CSS_SELECTOR, ".fltr__mini-pill--default-desel[data-state='no']")
        ignored_filters = filter_container.find_elements(By.CSS_SELECTOR, ".fltr__mini-pill[data-state='ignore']")
        
        # Combine active and deselected filters (exclude ignored filters)
        all_filters = active_filters + deselected_filters
        
        logger.info(f"Found {len(active_filters)} active filters, {len(deselected_filters)} deselected filters, and {len(ignored_filters)} ignored filters")
        
        # Set a limit to avoid infinite loops
        max_attempts = 3
        attempt = 0
        
        while attempt < max_attempts and all_filters:
            attempt += 1
            logger.info(f"Filter processing attempt {attempt}/{max_attempts}")
            
            # Click each filter pill to disable/enable it
            filters_processed = 0
            for i, pill in enumerate(all_filters):
                try:
                    # Get filter info before clicking
                    state = pill.get_attribute("data-state")
                    is_desel = "default-desel" in pill.get_attribute("class")
                    filter_text = pill.text.strip() if pill.text else f"Filter{i+1}"
                    
                    logger.info(f"Filter {i+1}/{len(all_filters)} '{filter_text}', current state: {state}, is deselected: {is_desel}")
                    
                    # Scroll into view and click
                    driver.execute_script("arguments[0].scrollIntoView(true);", pill)
                    time.sleep(0.2)  # Small delay for scrolling
                    driver.execute_script("arguments[0].click();", pill)
                    
                    # Get the new state for logging
                    try:
                        new_state = pill.get_attribute("data-state")
                        logger.info(f"Filter {i+1}/{len(all_filters)} '{filter_text}' toggled: {state} -> {new_state}")
                    except:
                        logger.info(f"Filter {i+1}/{len(all_filters)} '{filter_text}' toggled (couldn't get new state)")
                    
                    filters_processed += 1
                    time.sleep(0.3)  # Small delay to let the list update
                except Exception as e:
                    logger.warning(f"Could not toggle filter {i+1}: {e}")
            
            logger.info(f"Processed {filters_processed}/{len(all_filters)} filters in attempt {attempt}")
            
            # Check if there are still filters to process
            try:
                active_filters = filter_container.find_elements(By.CSS_SELECTOR, ".fltr__mini-pill[data-state='yes']")
                deselected_filters = filter_container.find_elements(By.CSS_SELECTOR, ".fltr__mini-pill--default-desel[data-state='no']")
                all_filters = active_filters + deselected_filters
                
                if not all_filters:
                    logger.info("All filters have been processed successfully")
                    break
                else:
                    logger.warning(f"Still found {len(all_filters)} filters to process after attempt {attempt}")
            except Exception as e:
                logger.error(f"Error checking remaining filters: {e}")
                break
        
        # Final verification
        try:
            remaining_filters = filter_container.find_elements(By.CSS_SELECTOR, ".fltr__mini-pill:not([data-state='ignore'])")
            if remaining_filters:
                logger.warning(f"Still found {len(remaining_filters)} filters that are not ignored after all attempts")
            else:
                logger.info("All filters disabled successfully")
        except Exception as e:
            logger.error(f"Error in final verification: {e}")
        
        return True
    except Exception as e:
        logger.error(f"Error disabling filters: {e}")
        logger.debug(traceback.format_exc())
        return False


async def main() -> None:
    """Main function to run the scraper"""
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
        return
    
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
        
        # Set page load timeout from config
        timeout = config.get("browser.page_load_timeout", 90)
        driver.set_page_load_timeout(timeout)
        
        # Navigate to target page
        driver.get('https://5e.tools/bestiary.html')
        logger.info("Loading bestiary page...")
        time.sleep(5)  # Give time for JS to initialize
        
        # Handle cookie consent if present
        if cookie_handler.handle_consent(driver):
            logger.info("Cookie consent handled.")

        # Wait for initial monster elements to load before disabling filters
        try:
            WebDriverWait(driver, 20).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, "a.lst__row-border")) > 0
            )
            logger.info("Initial monster list loaded, now disabling filters...")
        except Exception as e:
            logger.warning(f"Timeout waiting for initial monster list: {e}")
            # Continue anyway as the page might still be usable

        # Disable all filters
        wait = WebDriverWait(driver, 10)
        if not disable_filters(driver, wait):
            logger.warning("Failed to disable all filters, continuing with visible monsters only")
        
        # Try different CSS selectors for monster elements
        monster_elements = []
        selectors = [
            "a.lst__row-border",  # Primary selector 
            "a.lst__row",         # Alternative selector
            "div.lst__row-inner"  # Fallback selector
        ]
        
        for selector in selectors:
            try:
                logger.info(f"Trying to find monsters with selector: {selector}")
                monster_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if monster_elements and len(monster_elements) > 0:
                    logger.info(f"Found {len(monster_elements)} monsters using selector: {selector}")
                    break
            except Exception as e:
                logger.warning(f"Error finding monsters with selector {selector}: {e}")
        
        total_monsters = len(monster_elements)
        if total_monsters == 0:
            logger.error("No monsters found. Check the page structure or CSS selectors.")
            return
        
        logger.info(f"Found {total_monsters} monsters to process")
        
        # Process monsters in batches using asyncio for image downloads
        batch_size = 10
        async with aiohttp.ClientSession() as session:
            for start_idx in range(0, total_monsters, batch_size):
                batch_num = start_idx // batch_size + 1
                total_batches = (total_monsters + batch_size - 1) // batch_size
                logger.info(f"Processing batch {batch_num}/{total_batches} (monsters {start_idx+1}-{min(start_idx+batch_size, total_monsters)})")
                
                await process_monster_batch(
                    driver, 
                    monster_elements, 
                    session, 
                    start_idx, 
                    batch_size, 
                    total_monsters
                )

        logger.info(f"Scraping completed: {total_monsters} monsters processed.")
    except Exception as e:
        logger.error(f"Main error: {e}")
        logger.debug(traceback.format_exc())
    finally:
        # Clean up with enhanced method
        if driver:
            ensure_browser_cleanup(driver, logger)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception in main loop: {e}")
        logger.debug(traceback.format_exc()) 