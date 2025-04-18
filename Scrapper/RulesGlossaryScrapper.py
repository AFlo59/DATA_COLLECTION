import os
import sys
import time
import json
import logging
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import unquote

# Selenium imports
try:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, StaleElementReferenceException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Add the parent directory to sys.path to enable imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

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
    "Logs/RulesGlossary", 
    "Data/RulesGlossary"
])

# ===== Get configuration =====
config = get_config()

# ===== Logging configuration =====
logger = get_logger("RulesGlossaryScrapper", log_dir="Logs/RulesGlossary", clean_logs=True)


def sanitize_filename(name: str) -> str:
    """
    Sanitize a filename to be safe for all operating systems.
    
    Args:
        name: The name to sanitize
        
    Returns:
        Sanitized filename string
    """
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    
    # Limit length and remove trailing dots and spaces
    name = name.strip().strip('.')
    
    # Ensure the name isn't empty
    if not name:
        name = "unnamed"
        
    return name


def wait_and_click(driver: Any, selector: str, by: By = By.CSS_SELECTOR, 
                  timeout: int = 20, description: str = "element",
                  js_click: bool = False) -> bool:
    """
    Wait for an element to be clickable and click it.
    
    Args:
        driver: Browser driver instance
        selector: CSS selector or XPath
        by: Selection method (By.CSS_SELECTOR or By.XPATH)
        timeout: Maximum wait time in seconds
        description: Element description for logging
        js_click: Whether to use JavaScript click instead of direct click
        
    Returns:
        Boolean indicating success
    """
    try:
        wait = WebDriverWait(driver, timeout)
        logger.info(f"Waiting for {description} to be clickable...")
        element = wait.until(EC.element_to_be_clickable((by, selector)))
        logger.info(f"Found {description}, attempting to click...")
        
        # Use JavaScript click if specified or try direct click first
        if js_click:
            driver.execute_script("arguments[0].click();", element)
            logger.info(f"Successfully clicked {description} using JavaScript")
            return True
        else:
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


def wait_for_js_load(driver: Any, wait: WebDriverWait) -> bool:
    """
    Wait for JavaScript to load completely.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
        
    Returns:
        Boolean indicating success
    """
    try:
        # Wait for the URL to change from the base URL - indicates first rule is loaded
        logger.info("Waiting for JavaScript to load and URL to update...")
        base_url = "https://5e.tools/variantrules.html"
        
        # First wait for initial page load
        time.sleep(5)  # Give time for initial load
        
        # Check if URL already changed (sometimes it's immediate)
        current_url = driver.current_url
        if current_url != base_url and "#" in current_url:
            logger.info(f"URL already updated to: {current_url}")
            return True
            
        # Wait for URL to change, indicating first element loaded
        start_time = time.time()
        timeout = 30  # seconds
        while time.time() - start_time < timeout:
            current_url = driver.current_url
            if current_url != base_url and "#" in current_url:
                logger.info(f"URL updated to: {current_url}")
                return True
            time.sleep(0.5)
            
        # If URL didn't change, check for list elements as backup
        logger.warning("URL did not update within timeout, checking for list elements...")
        list_items = driver.find_elements(By.CSS_SELECTOR, "#list .lst__row")
        if list_items and len(list_items) > 0:
            logger.info(f"Found {len(list_items)} list items, assuming JavaScript is loaded")
            return True
            
        logger.error("JavaScript failed to load completely")
        return False
        
    except Exception as e:
        logger.error(f"Error waiting for JavaScript load: {e}")
        logger.debug(traceback.format_exc())
        return False


def disable_filters(driver: Any, wait: WebDriverWait) -> bool:
    """
    Disable all filters to show all 243 elements.
    
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
            EC.presence_of_element_located((By.CSS_SELECTOR, ".fltr__mini-view.ve-btn-group"))
        )
        logger.info("Found filter container, looking for filter pills...")
        
        # Find all active filter pills (both default-sel and default-desel)
        active_filters = filter_container.find_elements(By.CSS_SELECTOR, ".fltr__mini-pill[data-state='yes']")
        deselected_filters = filter_container.find_elements(By.CSS_SELECTOR, ".fltr__mini-pill--default-desel[data-state='no']")
        
        # Combine both filter types to disable them
        all_filters = active_filters + deselected_filters
        
        logger.info(f"Found {len(active_filters)} active filters and {len(deselected_filters)} deselected filters to toggle")
        
        # Click each filter pill to disable/enable it
        for i, pill in enumerate(all_filters):
            try:
                # Get the state for logging
                state = pill.get_attribute("data-state")
                is_desel = "default-desel" in pill.get_attribute("class")
                logger.info(f"Filter {i+1}/{len(all_filters)}, current state: {state}, is deselected: {is_desel}")
                
                # Use JavaScript click for reliability
                driver.execute_script("arguments[0].click();", pill)
                
                # Wait briefly for the list to update
                time.sleep(0.5)
                
                # Verify the state changed
                new_state = pill.get_attribute("data-state")
                logger.info(f"Filter {i+1}/{len(all_filters)} toggled: {state} -> {new_state}")
            except Exception as e:
                logger.warning(f"Failed to toggle filter {i+1}: {e}")
        
        # Verify by checking list length after disabling filters
        list_items = driver.find_elements(By.CSS_SELECTOR, "#list .lst__row")
        total_items = len(list_items)
        logger.info(f"After toggling filters, list contains {total_items} items")
        
        # Check if we have close to the expected count
        if total_items < 230:
            logger.warning(f"Expected around 243 items, but only found {total_items}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error disabling filters: {e}")
        logger.debug(traceback.format_exc())
        return False


def extract_rule_data(driver: Any, wait: WebDriverWait) -> Dict[str, Any]:
    """
    Extract data from the currently displayed rule.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
        
    Returns:
        Dictionary with rule data
    """
    try:
        # Wait for content wrapper to be present with a longer timeout
        logger.info("Waiting for content to load...")
        content_wrapper = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#wrp-pagecontent"))
        )
        
        # Ensure the content is refreshed after clicking an item
        time.sleep(1)
        
        # Get the current URL to verify we have the right rule
        url = driver.current_url
        logger.info(f"Current URL for extraction: {url}")
        
        # Extract name from header - ensure we're looking for the fresh element
        try:
            # First try to locate the element again to avoid stale references
            name_element = driver.find_element(By.CSS_SELECTOR, "#wrp-pagecontent h1.stats__h-name")
            name = name_element.text.strip()
            logger.info(f"Extracted name: {name}")
        except Exception as e:
            logger.warning(f"Error extracting name: {e}, trying alternative method")
            # Alternative method - try to get the name from the data attribute
            try:
                header = driver.find_element(By.CSS_SELECTOR, "#wrp-pagecontent th.stats__th-name")
                name = header.get_attribute("data-name")
                logger.info(f"Extracted name from data attribute: {name}")
            except Exception as e2:
                logger.error(f"Failed to extract name with alternative method: {e2}")
                # Last resort - extract from URL
                hash_part = url.split("#")[-1] if "#" in url else ""
                decoded_hash = unquote(hash_part)
                name = decoded_hash.split("_")[0].replace("%20", " ").title()
                logger.info(f"Extracted name from URL: {name}")
        
        # Extract source info
        try:
            source_element = driver.find_element(By.CSS_SELECTOR, "#wrp-pagecontent .stats__h-source-abbreviation")
            source = source_element.text.strip()
            # Get the full source name from title attribute
            source_full = source_element.get_attribute("title")
            logger.info(f"Extracted source: {source}, full: {source_full}")
        except Exception as e:
            logger.warning(f"Error extracting source: {e}, trying alternative method")
            # Alternative method - try to get the source from the data attribute
            try:
                header = driver.find_element(By.CSS_SELECTOR, "#wrp-pagecontent th.stats__th-name")
                source = header.get_attribute("data-source")
                source_full = source
                logger.info(f"Extracted source from data attribute: {source}")
            except Exception as e2:
                logger.error(f"Failed to extract source with alternative method: {e2}")
                # Last resort - extract from URL
                hash_part = url.split("#")[-1] if "#" in url else ""
                decoded_hash = unquote(hash_part)
                if "_" in decoded_hash:
                    source = decoded_hash.split("_")[-1]
                    source_full = source
                    logger.info(f"Extracted source from URL: {source}")
                else:
                    source = "Unknown"
                    source_full = "Unknown Source"
        
        # Extract page number
        page = ""
        try:
            page_element = driver.find_element(By.CSS_SELECTOR, "#wrp-pagecontent .rd__stats-name-page")
            page = page_element.text.strip().replace("p", "")
            logger.info(f"Extracted page: {page}")
        except Exception as e:
            logger.info(f"No page number found: {e}")
        
        # Extract content - wait for fresh content
        content = ""
        try:
            # Look for the div with content, which could have different class names
            content_div = driver.find_element(By.CSS_SELECTOR, "#wrp-pagecontent div[data-source]")
            content = content_div.get_attribute("innerHTML")
            logger.info(f"Extracted content length: {len(content)} characters")
        except Exception as e:
            logger.warning(f"Error extracting content with specific selector: {e}, trying alternative method")
            # Alternate approach if specific selector fails
            try:
                content = content_wrapper.get_attribute("innerHTML")
                logger.info(f"Extracted content (alternative method) length: {len(content)} characters")
            except Exception as e2:
                logger.error(f"Failed to extract content with alternative method: {e2}")
        
        # Extract hash from URL for later reference
        hash_part = url.split("#")[-1] if "#" in url else ""
        
        # Build data dictionary
        rule_data = {
            "name": name,
            "source": source,
            "source_full": source_full,
            "page": page,
            "content": content,
            "hash": unquote(hash_part),
            "url": url
        }
        
        logger.info(f"Successfully extracted rule: {name} ({source})")
        return rule_data
        
    except Exception as e:
        logger.error(f"Error extracting rule data: {e}")
        logger.debug(traceback.format_exc())
        return {}


def extract_list_item_data(item: Any) -> Dict[str, str]:
    """
    Extract basic data from a list item without clicking on it.
    
    Args:
        item: List item element
        
    Returns:
        Dictionary with basic rule data
    """
    try:
        # Extract spans from the list item
        spans = item.find_elements(By.CSS_SELECTOR, "span")
        
        # According to the instructions, there are 3 spans:
        # 1. Name: <span class="bold we-col-7 pl-0 pr-1">name</span>
        # 2. Type: <span class="we-col-3 px-1 ve-text-center">type</span>
        # 3. Source: <span class="we-col-2 ve-text-center">source</span>
        
        name = spans[0].text.strip() if len(spans) > 0 else "Unknown"
        rule_type = spans[1].text.strip() if len(spans) > 1 else ""
        source = spans[2].text.strip() if len(spans) > 2 else "Unknown"
        
        # Extract the hash from the href attribute of the parent anchor, if available
        hash_part = ""
        try:
            # Try to find an anchor tag parent or child
            anchor = item.find_element(By.CSS_SELECTOR, "a")
            href = anchor.get_attribute("href")
            if href and "#" in href:
                hash_part = href.split("#")[-1]
        except:
            # If no anchor is found, try to get it from a data attribute
            try:
                hash_part = item.get_attribute("data-hash") or ""
            except:
                pass
        
        # Construct a basic rule data dictionary
        rule_data = {
            "name": name,
            "type": rule_type,
            "source": source,
            "hash": unquote(hash_part),
            "full_content_extracted": False  # Flag to indicate this is just basic data
        }
        
        logger.info(f"Extracted list item data: {name} ({source})")
        return rule_data
        
    except Exception as e:
        logger.error(f"Error extracting list item data: {e}")
        logger.debug(traceback.format_exc())
        return {}


def extract_detailed_content(driver: Any, wait: WebDriverWait, basic_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract detailed content by clicking on the item and reading the content pane.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
        basic_data: Basic data already extracted from the list
        
    Returns:
        Enhanced data dictionary with detailed content
    """
    try:
        # Create a copy of the basic data
        detailed_data = basic_data.copy()
        
        # Find the item in the list by name and source
        item_selector = f"#list .lst__row:has(span.bold:contains('{basic_data['name']}'))"
        
        logger.info(f"Searching for item in list: {basic_data['name']}")
        
        # Try different approaches to find and click the item
        try:
            # First try with a direct selector (may be more reliable)
            item = driver.find_element(By.CSS_SELECTOR, item_selector)
            logger.info(f"Found list item for: {basic_data['name']}")
            
            # Click the item to view its content
            driver.execute_script("arguments[0].click();", item)
            logger.info(f"Clicked on list item: {basic_data['name']}")
            
            # Wait for content to load
            time.sleep(1.5)
        except Exception as e:
            logger.warning(f"Failed to locate or click item by direct selector: {e}")
            
            # Alternative approach - use JavaScript to find and click by text content
            try:
                script = """
                    const spans = document.querySelectorAll('#list .lst__row span.bold');
                    for (const span of spans) {
                        if (span.textContent.trim() === arguments[0]) {
                            const row = span.closest('.lst__row');
                            if (row) {
                                row.click();
                                return true;
                            }
                        }
                    }
                    return false;
                """
                success = driver.execute_script(script, basic_data['name'])
                if success:
                    logger.info(f"Clicked on list item via JavaScript: {basic_data['name']}")
                    time.sleep(1.5)
                else:
                    logger.error(f"Failed to find item by name in JavaScript: {basic_data['name']}")
                    return detailed_data
            except Exception as e2:
                logger.error(f"JavaScript click method also failed: {e2}")
                return detailed_data
                
        # Wait for content wrapper to load
        try:
            content_wrapper = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#wrp-pagecontent"))
            )
            logger.info("Found content wrapper")
        except Exception as e:
            logger.error(f"Failed to locate content wrapper: {e}")
            return detailed_data
            
        # Extract full content HTML
        try:
            # Get the entire content wrapper HTML
            content_html = content_wrapper.get_attribute("innerHTML")
            logger.info(f"Extracted content HTML: {len(content_html)} characters")
            detailed_data["content_html"] = content_html
            
            # Also try to extract the primary content section which should contain the actual rule
            try:
                content_div = content_wrapper.find_element(By.CSS_SELECTOR, "div[data-source]")
                rule_content = content_div.get_attribute("innerHTML")
                detailed_data["rule_content"] = rule_content
                logger.info(f"Extracted rule content: {len(rule_content)} characters")
            except Exception as e:
                logger.warning(f"Failed to extract specific rule content: {e}")
            
            # Try to extract plaintext content for easier processing
            try:
                paragraphs = content_wrapper.find_elements(By.CSS_SELECTOR, "div[data-source] p")
                plaintext = "\n\n".join([p.text for p in paragraphs if p.text.strip()])
                detailed_data["plaintext"] = plaintext
                logger.info(f"Extracted plaintext content: {len(plaintext)} characters")
            except Exception as e:
                logger.warning(f"Failed to extract plaintext content: {e}")
                
            # Extract the page number if available
            try:
                page_element = content_wrapper.find_element(By.CSS_SELECTOR, ".rd__stats-name-page")
                detailed_data["page"] = page_element.text.strip().replace("p", "")
                logger.info(f"Extracted page number: {detailed_data['page']}")
            except Exception:
                pass
                
            # Set flag to indicate we got detailed content
            detailed_data["full_content_extracted"] = True
        except Exception as e:
            logger.error(f"Failed to extract content: {e}")
        
        return detailed_data
        
    except Exception as e:
        logger.error(f"Error in extract_detailed_content: {e}")
        logger.debug(traceback.format_exc())
        return basic_data


def save_rule_data(rule_data: Dict[str, Any], output_dir: str) -> bool:
    """
    Save rule data to a JSON file.
    
    Args:
        rule_data: Dictionary with rule data
        output_dir: Directory to save the file
        
    Returns:
        Boolean indicating success
    """
    try:
        if not rule_data or not rule_data.get("name"):
            logger.warning("No valid rule data to save")
            return False
            
        # Create filename from name and source
        name = rule_data["name"]
        source = rule_data["source"]
        filename = sanitize_filename(f"{name}_{source}.json")
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Save to file
        output_path = os.path.join(output_dir, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(rule_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Saved rule data to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving rule data: {e}")
        logger.debug(traceback.format_exc())
        return False


def scrape_rules_glossary() -> bool:
    """
    Main function to scrape rules glossary from 5e.tools.
    
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
    
    # Setup output directory
    output_dir = os.path.abspath(os.path.join("Data", "RulesGlossary"))
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")
    
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
        
        # Setup wait objects
        wait = WebDriverWait(driver, 30)
        long_wait = WebDriverWait(driver, 60)
        short_wait = WebDriverWait(driver, 10)
        
        # Load the page
        logger.info("Loading 5e.tools variant rules page...")
        driver.get('https://5e.tools/variantrules.html')
        logger.info("Page loaded: https://5e.tools/variantrules.html")
        
        # Handle cookie consent
        if cookie_handler.handle_consent(driver):
            logger.info("Cookie consent handled.")
        
        # Wait for JavaScript to fully initialize
        if not wait_for_js_load(driver, long_wait):
            logger.error("Failed to confirm JavaScript loading, attempting to continue anyway")
        
        # Disable filters to show all rules
        if not disable_filters(driver, wait):
            logger.warning("Failed to disable all filters, continuing with visible rules only")
        
        # Get all list items after toggling filters
        logger.info("Getting all list items...")
        list_container = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#list"))
        )
        list_items = list_container.find_elements(By.CSS_SELECTOR, ".lst__row")
        total_items = len(list_items)
        logger.info(f"Found {total_items} rules to process")
        
        # Track processed rules
        processed_count = 0
        success_count = 0
        detailed_count = 0
        failed_items = []
        
        # Process each list item
        for index in range(total_items):
            try:
                # Refresh the list every 30 items to avoid stale references
                if index % 30 == 0:
                    logger.info(f"Refreshing list at item {index+1}/{total_items}...")
                    try:
                        list_container = wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "#list"))
                        )
                        list_items = list_container.find_elements(By.CSS_SELECTOR, ".lst__row")
                        # Make sure we have all items
                        if len(list_items) < total_items:
                            logger.warning(f"List refresh returned fewer items: {len(list_items)} < {total_items}")
                            total_items = len(list_items)  # Update total count
                    except Exception as e:
                        logger.error(f"Error refreshing list: {e}")
                        if index == 0:  # Critical failure at the start
                            return False
                
                # Get the current item
                try:
                    item = list_items[index]
                except IndexError:
                    logger.error(f"Index error accessing item {index+1}/{total_items}")
                    failed_items.append(index)
                    continue
                
                # Extract basic data directly from list item
                basic_data = extract_list_item_data(item)
                
                # Check if we got meaningful data
                if not basic_data or not basic_data.get("name"):
                    logger.error(f"Failed to extract meaningful data for item {index+1}")
                    failed_items.append(index)
                    continue
                
                # Try to extract detailed content by clicking on the item
                detailed_data = extract_detailed_content(driver, wait, basic_data)
                
                # Check if we successfully extracted detailed content
                if detailed_data.get("full_content_extracted", False):
                    detailed_count += 1
                
                # Save the data
                if save_rule_data(detailed_data, output_dir):
                    success_count += 1
                else:
                    failed_items.append(index)
                
                processed_count += 1
                
                # Progress logging
                if processed_count % 10 == 0 or processed_count == total_items:
                    logger.info(f"Progress: {processed_count}/{total_items} rules processed ({success_count} successful, {detailed_count} with full content)")
                
                # Prevent rate limiting/overloading
                time.sleep(0.2)
                
            except StaleElementReferenceException:
                logger.warning(f"Stale element reference for item {index+1}, refreshing list...")
                failed_items.append(index)
                
                # Refresh list and continue with next items
                try:
                    list_container = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#list"))
                    )
                    list_items = list_container.find_elements(By.CSS_SELECTOR, ".lst__row")
                except Exception as refresh_error:
                    logger.error(f"Failed to refresh list: {refresh_error}")
                    # Don't break, try to continue with next item
                    
            except Exception as e:
                logger.error(f"Error processing item {index+1}: {e}")
                logger.debug(traceback.format_exc())
                failed_items.append(index)
        
        # Log summary
        logger.info(f"Scraping completed: {success_count}/{total_items} rules successfully processed, {detailed_count} with full content")
        if failed_items:
            logger.warning(f"Failed to process {len(failed_items)} items: {failed_items}")
            
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Error scraping rules glossary: {e}")
        logger.debug(traceback.format_exc())
        return False
        
    finally:
        # Clean up with enhanced method
        if driver:
            ensure_browser_cleanup(driver, logger)


if __name__ == "__main__":
    try:
        success = scrape_rules_glossary()
        if success:
            output_dir = os.path.abspath(os.path.join("Data", "RulesGlossary"))
            print(f"Rules glossary successfully scraped. Data saved to {output_dir}")
        else:
            print("Failed to scrape rules glossary. Check logs for details.")
    except Exception as e:
        print(f"An error occurred: {e}")
        logger.error(f"Main execution error: {e}")
        logger.debug(traceback.format_exc()) 