# CookieHandler Module

## Overview

The `CookieHandler` module provides a comprehensive solution for handling cookie consent popups and banners that commonly appear on websites. It implements multiple strategies to detect, interact with, and bypass these consent dialogs, ensuring smooth automated browsing during web scraping operations.

## Features

- **Multi-Strategy Detection**: Uses various selectors to find cookie consent elements
- **Fallback Mechanisms**: Multiple approaches to handle different types of consent popups
- **JavaScript Injection**: Uses DOM manipulation to handle complex consent scenarios
- **Cross-Language Support**: Handles both English and French consent dialogs
- **Aggressive Cleanup**: Option to forcefully remove overlay elements that block interaction
- **Standalone Usage**: Can be used directly without class instantiation

## Core Components

### `CookieHandler` Class

The main class for handling cookie consent with the following key methods:

- `__init__(logger=None)`: Initializes the cookie handler
- `detect_consent_elements(driver, timeout=0.5)`: Detect cookie consent elements on the page
- `apply_javascript_strategy(driver, strategy)`: Apply a JavaScript-based cookie handling strategy
- `click_accept_buttons(driver, wait_time=1.0)`: Try to find and click accept buttons
- `handle_consent(driver, wait=None)`: Handle cookie consent with multiple strategies
- `add_consent_element_selector(selector)`: Add a custom consent element selector
- `add_accept_button_selector(selector)`: Add a custom accept button selector

### Standalone Function

- `handle_cookie_consent(driver, wait=None, logger=None)`: Handle cookie consent popup without class instantiation

## JavaScript Strategies

The module includes several JavaScript-based strategies:

1. **Set Cookies**: Directly sets common consent cookies
2. **Find and Click**: Identifies and clicks accept buttons via JavaScript
3. **Hide Elements**: Makes consent elements invisible via CSS
4. **Aggressive Cleanup**: Removes modal backdrops and ensures scrollability

## How It Works

1. **Detection**: The handler scans the page for common cookie consent elements using a variety of selectors.
2. **Multi-Stage Approach**:
   - Stage 1: Set cookies directly via JavaScript
   - Stage 2: Try to find and click accept buttons via JavaScript
   - Stage 3: Try to click buttons directly using Selenium
   - Stage 4: Try to hide consent elements via CSS
   - Stage 5: Last resort - aggressive DOM cleanup
3. **Verification**: The handler checks if the consent elements are still present after each stage.

## Usage Examples

### Basic Usage with Standalone Function

```python
from selenium import webdriver
from Scrapper.Modules.BrowserSetup import get_browser_driver
from Scrapper.Modules.CookieHandler import handle_cookie_consent
import logging

# Set up logging
logger = logging.getLogger("cookie_example")
logger.setLevel(logging.INFO)

# Get a browser driver
driver, _ = get_browser_driver(logger)

try:
    # Navigate to a site with cookie consent
    driver.get("https://example.com")
    
    # Handle cookie consent popup if present
    if handle_cookie_consent(driver, logger=logger):
        logger.info("Cookie consent handled successfully")
    else:
        logger.warning("Could not handle cookie consent")
    
    # Continue with scraping operations
    # ...
    
finally:
    driver.quit()
```

### Using the CookieHandler Class

```python
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.CookieHandler import CookieHandler
from Scrapper.Modules.SetupLogger import get_logger

# Get a logger instance
logger = get_logger("cookie_handler_example")

# Initialize browser setup
browser_setup = BrowserSetup(logger)
driver = browser_setup.get_driver()

# Create cookie handler instance
cookie_handler = CookieHandler(logger)

try:
    # Navigate to a site with cookie consent
    driver.get("https://example.com")
    
    # Handle cookie consent
    if cookie_handler.handle_consent(driver):
        logger.info("Cookie consent handled successfully")
    
    # Add custom selectors for other sites
    cookie_handler.add_consent_element_selector("div.custom-cookie-banner")
    cookie_handler.add_accept_button_selector("button.custom-accept")
    
    # Navigate to another site
    driver.get("https://another-example.com")
    
    # Handle cookie consent on the new site
    cookie_handler.handle_consent(driver)
    
finally:
    browser_setup.close()
```

### Integration with WebDriverWait

```python
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.CookieHandler import handle_cookie_consent
from Scrapper.Modules.SetupLogger import get_logger
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Get a logger instance
logger = get_logger("cookie_wait_example")

# Initialize browser setup
browser_setup = BrowserSetup(logger)
driver = browser_setup.get_driver()

try:
    # Navigate to a site with cookie consent
    driver.get("https://example.com")
    
    # Create a wait object
    wait = WebDriverWait(driver, 10)
    
    # Handle cookie consent with the wait object
    handle_cookie_consent(driver, wait, logger)
    
    # Now we can wait for elements that might have been blocked by the consent popup
    element = wait.until(EC.element_to_be_clickable((By.ID, "main-content")))
    element.click()
    
finally:
    browser_setup.close()
```

### Using Inside a Scraper Class

```python
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.CookieHandler import CookieHandler
from Scrapper.Modules.SetupLogger import get_logger
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class WebScraper:
    def __init__(self):
        self.logger = get_logger("web_scraper")
        self.browser_setup = BrowserSetup(self.logger)
        self.driver = None
        self.cookie_handler = CookieHandler(self.logger)
        
    def initialize(self):
        self.driver = self.browser_setup.get_driver()
        
    def navigate(self, url):
        if not self.driver:
            self.initialize()
            
        self.driver.get(url)
        
        # Handle any cookie consent popup
        self.cookie_handler.handle_consent(self.driver)
        
        # Wait for the page to be properly loaded after consent handling
        wait = WebDriverWait(self.driver, 10)
        try:
            # Wait for a typical page element that should be visible after consent is handled
            wait.until(EC.visibility_of_element_located((By.TAG_NAME, "main")))
        except Exception:
            self.logger.warning("Could not verify page load after consent handling")
        
    def scrape_page(self, url):
        self.navigate(url)
        
        # Now we can scrape the page
        title = self.driver.title
        self.logger.info(f"Scraped page title: {title}")
        
        # More scraping operations...
        
        return {"title": title, "url": url}
        
    def close(self):
        if self.driver:
            self.browser_setup.close()
            self.driver = None

# Usage
scraper = WebScraper()
try:
    result = scraper.scrape_page("https://example.com")
    print(f"Scraped: {result}")
finally:
    scraper.close()
```

### Custom Cookie Handling for Specific Sites

```python
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.CookieHandler import CookieHandler
from Scrapper.Modules.SetupLogger import get_logger

# Get a logger instance
logger = get_logger("custom_cookie_example")

# Initialize browser setup
browser_setup = BrowserSetup(logger)
driver = browser_setup.get_driver()

# Create cookie handler instance with site-specific selectors
cookie_handler = CookieHandler(logger)

# Add site-specific selectors for different websites
site_selectors = {
    "site1.com": {
        "consent_elements": ["div.gdpr-banner", "#cookie-notice"],
        "accept_buttons": ["button.accept-all", "//button[contains(text(), 'Accept')]"]
    },
    "site2.com": {
        "consent_elements": ["div.cookie-wall", "#consent-modal"],
        "accept_buttons": ["button.agree", "//a[contains(text(), 'I agree')]"]
    }
}

try:
    # Function to set up handlers for a specific site
    def setup_for_site(site_domain):
        if site_domain in site_selectors:
            # Clear any previous custom selectors
            cookie_handler.consent_element_selectors = cookie_handler.consent_element_selectors[:10]
            cookie_handler.accept_button_selectors = cookie_handler.accept_button_selectors[:10]
            
            # Add site-specific selectors
            for selector in site_selectors[site_domain]["consent_elements"]:
                cookie_handler.add_consent_element_selector(selector)
                
            for selector in site_selectors[site_domain]["accept_buttons"]:
                cookie_handler.add_accept_button_selector(selector)
                
            logger.info(f"Set up custom cookie handling for {site_domain}")
    
    # Visit site1
    setup_for_site("site1.com")
    driver.get("https://site1.com")
    cookie_handler.handle_consent(driver)
    
    # Visit site2
    setup_for_site("site2.com")
    driver.get("https://site2.com")
    cookie_handler.handle_consent(driver)
    
finally:
    browser_setup.close()
```

## Best Practices

1. **Handle Early**: Handle cookie consent immediately after navigating to a page
2. **Use Logging**: Enable logging to track cookie consent handling
3. **Custom Selectors**: Add custom selectors for sites with unique consent mechanisms
4. **Verification**: Verify that consent handling worked before continuing with scraping
5. **Fallbacks**: Be prepared to handle cases where cookie consent can't be dismissed

## Troubleshooting

- **Consent Still Visible**: Try using the aggressive cleanup strategy or adding custom selectors
- **Page Interaction Blocked**: Check if other overlay elements are blocking interaction
- **Script Errors**: Ensure JavaScript execution is enabled in the browser
- **Language Issues**: Add more localized selectors for non-English/French consent dialogs 