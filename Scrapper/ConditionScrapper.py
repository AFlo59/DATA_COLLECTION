import os
import re
import json
import time
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
import traceback
import sys

# Add the parent directory to sys.path to enable imports
# This helps in both direct execution and when imported as a module
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
    from Scrapper.Modules.SetupLogger import setup_directories, setup_logger, get_logger
    from Scrapper.Modules.DetectOS import get_os_info
    from Scrapper.Modules.BrowserSetup import BrowserSetup
    from Scrapper.Modules.BrowserCleanup import BrowserCleanup, ensure_browser_cleanup
    from Scrapper.Modules.CookieHandler import CookieHandler
    from Scrapper.Modules.ConfigManager import ConfigManager, get_config
    from Scrapper.Modules.DetectPackages import check_dependency_compatibility
except ImportError:
    try:
        # Then try relative imports
        from Modules.SetupLogger import setup_directories, setup_logger, get_logger
        from Modules.DetectOS import get_os_info
        from Modules.BrowserSetup import BrowserSetup
        from Modules.BrowserCleanup import BrowserCleanup, ensure_browser_cleanup
        from Modules.CookieHandler import CookieHandler
        from Modules.ConfigManager import ConfigManager, get_config
        from Modules.DetectPackages import check_dependency_compatibility
    except ImportError:
        # As a last resort, try direct imports if files are in the same directory
        import sys
        print("Failed to import modules. Check your project structure and Python path.")
        print(f"Current sys.path: {sys.path}")
        sys.exit(1)

# ===== Setup directories =====
setup_directories(["Logs/Condition", "Data/Condition"])

# ===== Get configuration =====
config = get_config()

# ===== Logging configuration =====
logger = get_logger("ConditionScrapper", log_dir="Logs/Condition")

# ===== Data classes =====
@dataclass
class Effect:
    name: str
    description: str

@dataclass
class ConditionData:
    name: str
    source: Optional[str]
    pages: Optional[str]
    description: Optional[str]
    effects: List[Effect]
    table_data: Optional[Dict]
    type: Optional[str] = None

# ===== Helpers =====
def sanitize_filename(name: str) -> str:
    """Convert a string to a safe filename"""
    return re.sub(r'[\\/*?:"<>|]', "", name)


def disable_filters(driver: Any) -> None:
    """
    Disable all active filters on the 5e.tools page.
    
    Args:
        driver: Browser driver instance
    """
    try:
        while True:
            pills = driver.find_elements(By.CSS_SELECTOR, "div.fltr__mini-pill:not([data-state='ignore'])")
            if not pills:
                break
            for p in pills:
                try:
                    driver.execute_script("arguments[0].scrollIntoView(true);", p)
                    time.sleep(0.2)
                    driver.execute_script("arguments[0].click();", p)
                    time.sleep(0.3)
                except Exception as e:
                    logger.warning(f"Could not disable filter: {str(p.text)}")
        logger.info("All filters disabled.")
    except Exception as e:
        logger.warning(f"Error disabling filters: {e}")


def extract_table_data(el: Any) -> Optional[Dict]:
    """
    Extract data from a table element.
    
    Args:
        el: Table element from the page
        
    Returns:
        Dictionary containing table data or None if extraction fails
    """
    try:
        cap = el.find_element(By.TAG_NAME, "caption").text
        hdrs = [th.text for th in el.find_elements(By.CSS_SELECTOR, "thead th")]
        rows = [[td.text for td in tr.find_elements(By.TAG_NAME, "td")] for tr in el.find_elements(By.CSS_SELECTOR, "tbody tr")]
        return {"title": cap, "headers": hdrs, "rows": rows}
    except Exception:
        return None


def extract_effects(cont: Any) -> List[Effect]:
    """
    Extract effect details from a container element.
    
    Args:
        cont: Container element from the page
        
    Returns:
        List of Effect objects
    """
    effs = []
    try:
        for d in cont.find_elements(By.CSS_SELECTOR, "div.rd__b--3"):
            try:
                nm = d.find_element(By.CSS_SELECTOR, "span.entry-title-inner").text
                ds = d.find_element(By.TAG_NAME, "p").text
                effs.append(Effect(name=nm, description=ds))
            except Exception as e:
                logger.warning(f"Error extracting effect details: {e}")
    except Exception as e:
        logger.warning(f"Error processing effects container: {e}")
    return effs


def get_condition_type_from_list(elem: Any) -> Optional[str]:
    """
    Extract condition type from the list element before clicking on it.
    
    Args:
        elem: List element representing the condition
        
    Returns:
        Type as string or None if not found
    """
    try:
        # The type is in the adjacent column in the list view
        type_span = elem.find_element(By.XPATH, "./following-sibling::span[@class='ve-col-3 px-1 ve-text-center']")
        return type_span.text.strip() if type_span else None
    except Exception:
        try:
            # Alternative: get all columns in the row
            parent_row = elem.find_element(By.XPATH, "./..")
            columns = parent_row.find_elements(By.TAG_NAME, "span")
            if len(columns) >= 2:  # Assuming type is in the second column
                return columns[1].text.strip()
        except Exception:
            pass
    return None


def process_condition(driver: Any, elem: Any) -> Optional[ConditionData]:
    """
    Process a condition element to extract its data.
    
    Args:
        driver: Browser driver instance
        elem: Element representing a condition in the list
        
    Returns:
        ConditionData object or None if processing fails
    """
    try:
        name = elem.find_element(By.CSS_SELECTOR, "span.bold").text.strip()
        
        # Try to get type from the list view before clicking
        type_value = get_condition_type_from_list(elem)
        
        # Navigate to the detail page
        driver.execute_script("arguments[0].click();", elem)
        content = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "pagecontent")))

        # If type wasn't found in list view, try to find it on the detail page
        if not type_value:
            try:
                # Try different selectors for the type
                selectors = [
                    ".ve-col-3.px-1.ve-text-center",
                    ".rd__stats-name-type",
                    ".stats-source-type"
                ]
                
                for selector in selectors:
                    try:
                        type_el = content.find_element(By.CSS_SELECTOR, selector)
                        type_value = type_el.text.strip()
                        if type_value:
                            break
                    except Exception:
                        continue
            except Exception as e:
                logger.debug(f"Could not find type for {name}: {e}")
        
        # Source (span ou a)
        try:
            src_el = content.find_element(By.CSS_SELECTOR, ".stats__h-source-abbreviation")
            source = src_el.text
        except:
            source = None
        
        # Pages (span ou a)
        try:
            pg_el = content.find_element(By.CSS_SELECTOR, ".rd__stats-name-page")
            pages = pg_el.text.lstrip('p')
        except:
            pages = None
        
        # Description
        try:
            desc = content.find_element(By.CSS_SELECTOR, "div.rd__b--1").text
        except:
            desc = None
        
        # Tableau
        table = None
        try:
            tbl = content.find_element(By.CSS_SELECTOR, "table.rd__table")
            table = extract_table_data(tbl)
        except:
            pass
        
        # Effets détaillés
        effs = []
        try:
            cont = content.find_element(By.CSS_SELECTOR, "div.rd__b--2")
            effs = extract_effects(cont)
        except:
            pass

        return ConditionData(
            name=name, 
            source=source, 
            pages=pages, 
            description=desc, 
            effects=effs, 
            table_data=table,
            type=type_value
        )
    except Exception as e:
        logger.error(f"Error processing condition: {e}")
        logger.debug(traceback.format_exc())
        return None


def save_condition_data(cond: ConditionData) -> None:
    """
    Save condition data to a JSON file.
    
    Args:
        cond: ConditionData object to save
    """
    try:
        nm = sanitize_filename(cond.name.lower())
        src = sanitize_filename(cond.source.lower()) if cond.source else "unknown"
        filename = f"{nm}_{src}.json"
        path = os.path.join("Data/Condition", filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(asdict(cond), f, ensure_ascii=False, indent=2)
        logger.info(f"Data saved: {cond.name} ({cond.source})")
    except Exception as e:
        logger.error(f"Error saving condition data: {e}")


def main() -> None:
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
        
        # Configure browser settings from config
        timeout = config.get("browser.page_load_timeout", 90)
        driver.set_page_load_timeout(timeout)
        
        # Navigate to target page
        driver.get('https://5e.tools/conditionsdiseases.html')
        logger.info("Loading page...")
        time.sleep(5)  # Give time for JS to initialize

        # Handle cookie consent if present
        if cookie_handler.handle_consent(driver):
            logger.info("Cookie consent handled.")
        
        # Disable filters
        disable_filters(driver)
        
        # Wait for condition elements to load
        try:
            WebDriverWait(driver, 20).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, "a.lst__row-border")) > 0
            )
        except Exception as e:
            logger.error(f"Error waiting for elements to load: {e}")
            return

        # Get and count elements
        elems = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
        total = len(elems)
        logger.info(f"Found {total} conditions to process")

        # Process each condition
        for idx in range(total):
            try:
                # Need to re-find elements each time as the DOM is refreshed
                elems = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
                el = elems[idx]
                driver.execute_script("arguments[0].scrollIntoView(true);", el)
                time.sleep(0.3)
                
                # Process and save
                cond = process_condition(driver, el)
                if cond:
                    save_condition_data(cond)
                
                logger.info(f"Progress: {idx+1}/{total}")
                
                # Return to list
                driver.execute_script("window.location.hash = '';")
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error processing index {idx}: {e}")
                logger.debug(traceback.format_exc())

        logger.info(f"Scraping completed: {total} conditions.")
    except Exception as e:
        logger.error(f"Main error: {e}")
        logger.debug(traceback.format_exc())
    finally:
        # Clean up browser with enhanced method
        if driver:
            ensure_browser_cleanup(driver, logger)

if __name__ == "__main__":
    main() 