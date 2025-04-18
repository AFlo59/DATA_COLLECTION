# Complete Scraper Example

This example demonstrates how to use all the scraping modules together to build a robust web scraping application.

## Table of Contents

- [Complete Scraper Implementation](#complete-scraper-implementation)
- [Configuration File Example](#configuration-file-example)
- [Running the Scraper](#running-the-scraper)
- [Advanced Features](#advanced-features)

## Complete Scraper Implementation

```python
import os
import sys
import time
import json
from typing import Dict, List, Optional, Any

# Add parent directories to sys.path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import our modules
from Scrapper.Modules.ConfigManager import ConfigManager, get_config
from Scrapper.Modules.SetupLogger import setup_directories, get_logger
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.BrowserCleanup import BrowserCleanup
from Scrapper.Modules.CookieHandler import CookieHandler
from Scrapper.Modules.DetectOS import get_os_info
from Scrapper.Modules.DetectPackages import check_dependency_compatibility, detect_installed_packages

# Selenium imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class ComprehensiveScraper:
    """
    A complete web scraping application using all modules from the framework.
    This scraper can retrieve product information from e-commerce websites.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize the scraper with optional configuration file.
        
        Args:
            config_file: Optional path to a JSON configuration file
        """
        # Set up directories first
        setup_directories(["Logs", "Data", "Output"])
        
        # Initialize configuration manager
        if config_file and os.path.exists(config_file):
            self.config = ConfigManager(config_file=config_file)
        else:
            self.config = get_config()
            
            # Set some default scraper-specific settings
            self.config.set("scraper.retry_attempts", 3)
            self.config.set("scraper.retry_delay", 2)
            self.config.set("scraper.product_selectors", {
                "title": "h1.product-title",
                "price": "span.price",
                "description": "div.product-description",
                "rating": "div.rating",
                "images": "img.product-image"
            })
        
        # Initialize logger
        self.logger = get_logger("comprehensive_scraper")
        self.logger.info("Initializing comprehensive scraper")
        
        # Log system information
        self._log_system_info()
        
        # Check for compatible dependencies
        if not self._verify_dependencies():
            self.logger.warning("Some dependencies may be incompatible")
        
        # Initialize browser management
        self.browser_setup = BrowserSetup(self.logger)
        self.browser_cleanup = BrowserCleanup(self.logger)
        self.cookie_handler = CookieHandler(self.logger)
        self.driver = None
        
    def _log_system_info(self) -> None:
        """Log system information for debugging purposes."""
        os_info = get_os_info()
        self.logger.info(f"Operating System: {os_info['system']} {os_info['release']}")
        self.logger.info(f"Python Version: {os_info.get('python_version', 'unknown')}")
    
    def _verify_dependencies(self) -> bool:
        """
        Verify that required packages are installed and compatible.
        
        Returns:
            Boolean indicating if all dependencies are compatible
        """
        # Get required packages from config or use defaults
        required_packages = self.config.get("scraper.required_packages", [
            "selenium", 
            "undetected-chromedriver", 
            "requests", 
            "beautifulsoup4", 
            "urllib3"
        ])
        
        # Check installed versions
        versions = detect_installed_packages(required_packages)
        self.logger.info("Installed package versions:")
        for pkg, version in versions.items():
            self.logger.info(f"  {pkg}: {version}")
        
        # Check compatibility
        is_compatible, warnings = check_dependency_compatibility()
        if not is_compatible:
            self.logger.warning("Package compatibility issues detected:")
            for warning in warnings:
                self.logger.warning(f"  {warning}")
        
        return is_compatible
    
    def initialize(self) -> bool:
        """
        Initialize the browser driver.
        
        Returns:
            Boolean indicating success
        """
        try:
            self.logger.info("Initializing browser")
            
            # Get browser driver
            self.driver = self.browser_setup.get_driver()
            
            # Register for cleanup
            self.browser_cleanup.register_browser(self.driver)
            
            # Configure browser settings
            timeout = self.config.get("browser.page_load_timeout", 30)
            implicit_wait = self.config.get("browser.implicit_wait", 10)
            
            self.driver.set_page_load_timeout(timeout)
            self.driver.implicitly_wait(implicit_wait)
            
            self.logger.info("Browser initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize browser: {e}")
            return False
    
    def navigate(self, url: str) -> bool:
        """
        Navigate to a URL and handle cookie consent.
        
        Args:
            url: URL to navigate to
            
        Returns:
            Boolean indicating success
        """
        if not self.driver:
            if not self.initialize():
                return False
        
        try:
            self.logger.info(f"Navigating to {url}")
            self.driver.get(url)
            
            # Handle cookie consent
            if self.cookie_handler.handle_consent(self.driver):
                self.logger.info("Cookie consent handled")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to navigate to {url}: {e}")
            return False
    
    def scrape_product(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape product information from a product page.
        
        Args:
            url: URL of the product page
            
        Returns:
            Dictionary of product information or None if failed
        """
        retry_attempts = self.config.get("scraper.retry_attempts", 3)
        retry_delay = self.config.get("scraper.retry_delay", 2)
        
        # Get selectors from config
        selectors = self.config.get("scraper.product_selectors", {})
        
        for attempt in range(1, retry_attempts + 1):
            try:
                self.logger.info(f"Scraping product attempt {attempt}/{retry_attempts}")
                
                # Navigate to the product page
                if not self.navigate(url):
                    raise Exception("Failed to navigate to product page")
                
                # Wait for the page to load
                wait = WebDriverWait(self.driver, 15)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selectors.get("title", "h1"))))
                
                # Extract product information
                product = {
                    "url": url,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Extract title
                try:
                    title_element = self.driver.find_element(By.CSS_SELECTOR, selectors.get("title", "h1"))
                    product["title"] = title_element.text.strip()
                except NoSuchElementException:
                    self.logger.warning("Could not find product title")
                    product["title"] = "Unknown"
                
                # Extract price
                try:
                    price_element = self.driver.find_element(By.CSS_SELECTOR, selectors.get("price", "span.price"))
                    product["price"] = price_element.text.strip()
                except NoSuchElementException:
                    self.logger.warning("Could not find product price")
                    product["price"] = "Unknown"
                
                # Extract description
                try:
                    desc_element = self.driver.find_element(By.CSS_SELECTOR, selectors.get("description", "div.description"))
                    product["description"] = desc_element.text.strip()
                except NoSuchElementException:
                    self.logger.warning("Could not find product description")
                    product["description"] = "No description available"
                
                # Extract image URLs
                try:
                    image_elements = self.driver.find_elements(By.CSS_SELECTOR, selectors.get("images", "img.product"))
                    product["images"] = [img.get_attribute("src") for img in image_elements if img.get_attribute("src")]
                except NoSuchElementException:
                    self.logger.warning("Could not find product images")
                    product["images"] = []
                
                self.logger.info(f"Successfully scraped product: {product.get('title', 'Unknown')}")
                return product
                
            except Exception as e:
                self.logger.warning(f"Attempt {attempt} failed: {e}")
                if attempt < retry_attempts:
                    time.sleep(retry_delay)
                else:
                    self.logger.error(f"All {retry_attempts} attempts failed")
                    return None
    
    def scrape_products(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Scrape multiple product pages.
        
        Args:
            urls: List of product URLs to scrape
            
        Returns:
            List of product information dictionaries
        """
        products = []
        
        for i, url in enumerate(urls):
            self.logger.info(f"Scraping product {i+1}/{len(urls)}")
            product = self.scrape_product(url)
            if product:
                products.append(product)
            else:
                self.logger.warning(f"Failed to scrape product: {url}")
        
        return products
    
    def save_results(self, products: List[Dict[str, Any]], output_file: str) -> bool:
        """
        Save scraped product information to a JSON file.
        
        Args:
            products: List of product information dictionaries
            output_file: Path to the output file
            
        Returns:
            Boolean indicating success
        """
        try:
            # Ensure the output directory exists
            output_dir = os.path.dirname(output_file)
            os.makedirs(output_dir, exist_ok=True)
            
            self.logger.info(f"Saving {len(products)} products to {output_file}")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(products, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"Successfully saved results to {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save results: {e}")
            return False
    
    def close(self) -> None:
        """Close the browser and clean up resources."""
        self.logger.info("Closing scraper and cleaning up resources")
        if self.driver:
            self.browser_cleanup.close_browser(self.driver)
            self.driver = None


def main():
    """Main function to run the scraper."""
    # Sample product URLs (replace with real URLs)
    product_urls = [
        "https://example.com/product1",
        "https://example.com/product2",
        "https://example.com/product3"
    ]
    
    # Output file path
    output_file = os.path.join("Output", "products.json")
    
    # Create and run the scraper
    scraper = ComprehensiveScraper()
    
    try:
        # Scrape products
        products = scraper.scrape_products(product_urls)
        
        # Save results
        if products:
            scraper.save_results(products, output_file)
            print(f"Successfully scraped {len(products)} products")
            print(f"Results saved to {output_file}")
        else:
            print("No products were successfully scraped")
            
    finally:
        # Always close the scraper
        scraper.close()


if __name__ == "__main__":
    main()
```

## Configuration File Example

Here's an example `config.json` file that can be used with the scraper:

```json
{
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(levelname)s - %(message)s",
    "console_output": true,
    "file_output": true,
    "log_dir": "Logs"
  },
  "browser": {
    "type": "chrome",
    "headless": false,
    "timeout": 30,
    "page_load_timeout": 90,
    "implicit_wait": 10
  },
  "scraper": {
    "retry_attempts": 3,
    "retry_delay": 2,
    "product_selectors": {
      "title": "h1.product-title",
      "price": "span.product-price",
      "description": "div.product-description",
      "rating": "div.product-rating",
      "images": "img.product-image"
    }
  }
}
```

## Running the Scraper

To run the scraper with a custom configuration file:

```python
from comprehensive_scraper import ComprehensiveScraper

# Create the scraper with a custom config file
scraper = ComprehensiveScraper("config.json")

# Define product URLs to scrape
product_urls = [
    "https://example.com/product1",
    "https://example.com/product2",
    "https://example.com/product3"
]

try:
    # Scrape products
    products = scraper.scrape_products(product_urls)
    
    # Save results
    scraper.save_results(products, "Output/products.json")
    
finally:
    # Always close the scraper
    scraper.close()
```

## Advanced Features

### Parallelizing Scraping

For faster scraping, you can extend the example to use multiple browsers in parallel:

```python
import concurrent.futures
from comprehensive_scraper import ComprehensiveScraper

def scrape_url_batch(urls, config_file=None):
    """Scrape a batch of URLs with a single browser instance"""
    scraper = ComprehensiveScraper(config_file)
    try:
        return scraper.scrape_products(urls)
    finally:
        scraper.close()

# Main function with parallel scraping
def main_parallel():
    # Sample product URLs
    all_product_urls = [
        "https://example.com/product1",
        "https://example.com/product2",
        # ... many more URLs ...
        "https://example.com/product50"
    ]
    
    # Split URLs into batches for parallel processing
    num_workers = 4  # Number of parallel browsers
    batch_size = len(all_product_urls) // num_workers
    url_batches = [all_product_urls[i:i+batch_size] for i in range(0, len(all_product_urls), batch_size)]
    
    all_products = []
    
    # Process batches in parallel
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_batch = {executor.submit(scrape_url_batch, batch): batch for batch in url_batches}
        
        for future in concurrent.futures.as_completed(future_to_batch):
            batch = future_to_batch[future]
            try:
                products = future.result()
                all_products.extend(products)
            except Exception as e:
                print(f"Batch failed with error: {e}")
    
    # Save all results
    if all_products:
        scraper = ComprehensiveScraper()
        scraper.save_results(all_products, "Output/all_products.json")
        scraper.close()
        
        print(f"Successfully scraped {len(all_products)} products")
    else:
        print("No products were successfully scraped")

if __name__ == "__main__":
    main_parallel()
```

### Adding Custom Cookie Handling

For websites with specific cookie consent mechanisms:

```python
# Extend the scraper to add custom cookie handling
class CustomScraper(ComprehensiveScraper):
    def __init__(self, config_file=None):
        super().__init__(config_file)
        
        # Add custom cookie selectors for specific sites
        self.cookie_handler.add_consent_element_selector("div.custom-cookie-banner")
        self.cookie_handler.add_accept_button_selector("button.custom-accept")
        
        # Add JavaScript strategy for specific sites
        self.custom_js = """
            // Try to find and click accept buttons
            const acceptButtons = document.querySelectorAll('.cookie-accept-btn');
            if (acceptButtons.length > 0) {
                acceptButtons[0].click();
                return true;
            }
            return false;
        """
    
    def navigate(self, url):
        result = super().navigate(url)
        
        # For specific domains, apply custom handling
        if "example.com" in url:
            self.driver.execute_script(self.custom_js)
            
        return result
```

These examples demonstrate how to use all the modules together to build a robust, maintainable web scraping application. 