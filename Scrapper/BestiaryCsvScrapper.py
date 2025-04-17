import os
import time
import logging
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from pathlib import Path

# Configure logging
logging.basicConfig(
    filename="logs/bestiary/csv_scraper.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def setup_driver():
    """Configure and return the Chrome driver."""
    downloads_path = os.path.join(os.getcwd(), "Data", "CSV")
    os.makedirs(downloads_path, exist_ok=True)
    
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.98 Safari/537.36")
    
    # Configure download behavior
    prefs = {
        "download.default_directory": downloads_path,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_settings.popups": 0
    }
    options.add_experimental_option("prefs", prefs)
    
    try:
        driver = uc.Chrome(
            options=options,
            version_main=133,
            suppress_welcome=True
        )
        # Additional download settings
        params = {
            "behavior": "allow",
            "downloadPath": downloads_path
        }
        driver.execute_cdp_cmd("Page.setDownloadBehavior", params)
        return driver
    except Exception as e:
        logging.error(f"Failed to initialize Chrome driver: {e}")
        raise

def wait_and_click(driver, wait, selector, by=By.CSS_SELECTOR, timeout=20, description="element"):
    """Wait for an element to be clickable and click it with proper logging."""
    try:
        logging.info(f"Waiting for {description} to be clickable...")
        element = wait.until(EC.element_to_be_clickable((by, selector)))
        logging.info(f"Found {description}, attempting to click...")
        
        # Try direct click first
        try:
            element.click()
            logging.info(f"Successfully clicked {description} using direct click")
            return True
        except ElementClickInterceptedException:
            logging.info(f"Direct click failed for {description}, trying JavaScript click...")
            driver.execute_script("arguments[0].click();", element)
            logging.info(f"Successfully clicked {description} using JavaScript")
            return True
            
    except TimeoutException:
        logging.error(f"Timeout waiting for {description} to be clickable")
        return False
    except Exception as e:
        logging.error(f"Error clicking {description}: {e}")
        return False

def handle_cookie_consent(driver, wait):
    """Handle the cookie consent popup if present."""
    try:
        logging.info("Checking for cookie consent popup...")
        # Try different selectors for the accept button
        selectors = [
            "button.Accepter",  # Le bouton "Accepter" direct
            "button[class*='accept']",  # Tout bouton avec 'accept' dans sa classe
            "//button[contains(text(), 'Accepter')]",  # Bouton contenant le texte "Accepter"
            "//button[text()='Accepter']"  # Bouton avec exactement le texte "Accepter"
        ]
        
        for selector in selectors:
            try:
                by = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
                if wait_and_click(driver, wait, selector, by, timeout=5, description="Cookie accept button"):
                    logging.info("Successfully accepted cookies")
                    time.sleep(2)  # Wait for popup to disappear
                    return True
            except Exception:
                continue
                
        logging.info("No cookie consent popup found or couldn't interact with it")
        return False
        
    except Exception as e:
        logging.warning(f"Error handling cookie consent: {e}")
        return False

def wait_for_download(directory: str, timeout: int = 60) -> bool:
    """Wait for a .csv file to appear in the directory and be fully downloaded."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        csv_files = list(Path(directory).glob("*.csv"))
        temp_files = list(Path(directory).glob("*.csv.crdownload"))
        
        if csv_files and not temp_files:  # If we have CSV files and no temp files
            logging.info(f"Download completed, found files: {[f.name for f in csv_files]}")
            return True
            
        if temp_files:
            logging.info("Download in progress...")
        
        time.sleep(1)
    
    return False

def download_bestiary_csv():
    """Download the bestiary CSV file."""
    os.makedirs("logs/bestiary", exist_ok=True)
    downloads_path = os.path.join(os.getcwd(), "Data", "CSV")
    os.makedirs(downloads_path, exist_ok=True)
    
    driver = None
    try:
        driver = setup_driver()
        wait = WebDriverWait(driver, 20)
        
        # Load the page
        driver.get('https://5e.tools/bestiary.html')
        logging.info("Page loaded: https://5e.tools/bestiary.html")
        
        # Wait for initial page load and JavaScript initialization
        time.sleep(7)
        
        # Handle cookie consent first
        handle_cookie_consent(driver, wait)
        
        # Click the Table View button
        if not wait_and_click(driver, wait, "btn-show-table", By.ID, description="Table View button"):
            raise Exception("Failed to click Table View button")
        
        # Wait for table to load
        time.sleep(5)
        
        # Try to click the download button with JavaScript
        try:
            logging.info("Attempting direct JavaScript click for CSV download...")
            driver.execute_script("""
                const buttons = Array.from(document.querySelectorAll('button.ve-btn.ve-btn-primary'));
                const downloadButton = buttons.find(b => b.textContent.trim() === 'Download CSV');
                if (downloadButton) {
                    downloadButton.click();
                    console.log('Download button clicked');
                } else {
                    throw new Error('Download button not found');
                }
            """)
            logging.info("Successfully triggered download via JavaScript")
        except Exception as e:
            logging.error(f"JavaScript click failed: {e}")
            raise Exception("Failed to trigger download")
        
        # Wait for download to complete
        logging.info(f"Waiting for download in: {downloads_path}")
        if wait_for_download(downloads_path, timeout=60):
            csv_files = list(Path(downloads_path).glob("*.csv"))
            if csv_files:
                downloaded_file = csv_files[0]
                new_path = os.path.join(downloads_path, "bestiary.csv")
                
                # If the target file already exists, remove it
                if os.path.exists(new_path):
                    os.remove(new_path)
                
                # Rename the downloaded file
                os.rename(str(downloaded_file), new_path)
                logging.info(f"CSV file successfully saved to {new_path}")
                return True
        
        raise Exception("Download failed or timed out")
        
    except Exception as e:
        logging.error(f"Error downloading CSV: {e}")
        return False
        
    finally:
        if driver:
            driver.quit()
            logging.info("Browser closed")

if __name__ == "__main__":
    try:
        success = download_bestiary_csv()
        if success:
            print("CSV file successfully downloaded and saved to Data/CSV/bestiary.csv")
        else:
            print("Failed to download CSV file. Check logs for details.")
    except Exception as e:
        print(f"An error occurred: {e}")
        logging.error(f"Main execution error: {e}") 