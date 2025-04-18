# BrowserCleanup Module

## Overview

The `BrowserCleanup` module provides a comprehensive solution for managing browser driver instances and ensuring proper cleanup of resources. It helps prevent memory leaks, orphaned processes, and other issues that can occur when browser drivers are not properly closed.

## Features

- **Browser Registration**: Track browser instances for automated cleanup
- **Multi-Method Cleanup**: Multiple approaches to ensure browsers are properly closed
- **Force Kill Capability**: Last-resort process termination for stubborn browser instances
- **Automatic Cleanup**: Automatically cleans up registered browsers at program exit
- **Flexible API**: Both class-based and standalone function interfaces
- **Resilient Design**: Works even if browsers throw exceptions during closing

## Core Components

### `BrowserCleanup` Class

The primary class for managing browser cleanup with these key methods:

- `__init__(logger=None)`: Initializes the browser cleanup manager
- `register_browser(browser)`: Register a browser instance for managed cleanup
- `close_browser(browser)`: Close a browser instance with multiple fallback approaches
- `force_kill_processes(process_names=None)`: Force kill browser processes as a last resort
- `close_all_browsers()`: Close all managed browser instances

### Standalone Functions

- `register_browser(browser, logger=None)`: Register a browser for automatic cleanup
- `close_browser(browser, logger=None)`: Close a browser with multiple fallback methods
- `force_kill_browser_processes(logger=None)`: Force kill all browser processes
- `ensure_browser_cleanup(browser, logger=None, force_kill=True)`: Ensure complete browser cleanup

## How It Works

1. **Registration**: Browsers are registered for tracking using a global registry or class instance.
2. **Cleanup Strategy**: When cleanup is requested, the module tries multiple methods:
   - First try `driver.quit()` - the standard way to close a browser
   - If that fails, try `browser.close()` - useful for some driver types
   - If that fails, try `browser.stop()` - specific to undetected_chromedriver
   - As a last resort, force kill browser processes using OS-specific commands
3. **Exit Handling**: At program exit, the module automatically cleans up any registered browsers.

## Error Handling

- Catches and logs exceptions during browser closure
- Ensures browsers are removed from the registry even if closure fails
- Provides detailed logging of cleanup attempts and results
- Implements fallback strategies if primary closure methods fail

## Usage Examples

### Basic Standalone Function Usage

```python
from Scrapper.Modules.BrowserSetup import get_browser_driver
from Scrapper.Modules.BrowserCleanup import ensure_browser_cleanup
import logging

# Set up logging
logger = logging.getLogger("scraper")

# Get a browser driver
driver, _ = get_browser_driver(logger)

try:
    # Use the driver for web scraping
    driver.get("https://example.com")
    page_title = driver.title
    print(f"Page title: {page_title}")
finally:
    # Ensure proper cleanup with all available methods
    ensure_browser_cleanup(driver, logger, force_kill=True)
```

### Using the BrowserCleanup Class

```python
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.BrowserCleanup import BrowserCleanup
import logging

# Set up logging
logger = logging.getLogger("scraper")
logger.setLevel(logging.INFO)

# Initialize browser setup and cleanup
browser_setup = BrowserSetup(logger)
browser_cleanup = BrowserCleanup(logger)

# Get a driver instance
driver = browser_setup.get_driver()

# Register the browser for automated cleanup
browser_cleanup.register_browser(driver)

try:
    # Navigate to a website
    driver.get("https://example.com")
    
    # Perform scraping operations
    elements = driver.find_elements_by_css_selector("h1")
    for element in elements:
        print(element.text)
        
finally:
    # Close all managed browsers
    browser_cleanup.close_all_browsers()
```

### Handling Multiple Browsers

```python
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.BrowserCleanup import BrowserCleanup
from Scrapper.Modules.SetupLogger import get_logger

# Get a logger instance
logger = get_logger("multi_browser_scraper")

# Initialize browser setup and cleanup
browser_setup = BrowserSetup(logger)
browser_cleanup = BrowserCleanup(logger)

# Create multiple browser instances
browsers = []
for i in range(3):
    driver = browser_setup.get_driver()
    browsers.append(driver)
    browser_cleanup.register_browser(driver)
    
try:
    # Use the browsers for different tasks
    for i, browser in enumerate(browsers):
        browser.get(f"https://example.com/page{i+1}")
        logger.info(f"Browser {i+1} title: {browser.title}")
        
finally:
    # Close all browsers at once
    browser_cleanup.close_all_browsers()
    
    # If any browsers are still causing issues, force kill all browser processes
    if browser_cleanup.force_kill_processes():
        logger.info("Force killed remaining browser processes")
```

### Integration in a Scraper Class

```python
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.BrowserCleanup import register_browser, ensure_browser_cleanup
from Scrapper.Modules.SetupLogger import get_logger

class WebScraper:
    def __init__(self):
        self.logger = get_logger("web_scraper")
        self.browser_setup = BrowserSetup(self.logger)
        self.driver = None
        
    def initialize(self):
        self.driver = self.browser_setup.get_driver()
        # Register the browser for automatic cleanup at program exit
        register_browser(self.driver, self.logger)
        
    def scrape_website(self, url):
        if not self.driver:
            self.initialize()
            
        self.driver.get(url)
        # Perform scraping operations
        title = self.driver.title
        self.logger.info(f"Scraped page: {title}")
        return title
        
    def close(self):
        # Ensure proper cleanup
        if self.driver:
            ensure_browser_cleanup(self.driver, self.logger)
            self.driver = None

# Usage
scraper = WebScraper()
try:
    result = scraper.scrape_website("https://example.com")
    print(f"Result: {result}")
finally:
    scraper.close()
```

## Best Practices

1. **Register Early**: Register browsers as soon as they are created
2. **Use try-finally**: Always use try-finally blocks to ensure cleanup
3. **Prefer Class for Multiple Browsers**: Use the BrowserCleanup class when managing multiple browsers
4. **Log Cleanup Actions**: Enable logging to track cleanup operations
5. **Force Kill as Last Resort**: Only use force_kill when normal cleanup methods fail

## Troubleshooting

- **Orphaned Processes**: If Chrome processes remain after scraping, try the force kill functionality
- **Memory Leaks**: Ensure all browsers are properly registered for cleanup
- **Shutdown Errors**: If you see errors during Python shutdown, check the browser cleaning order 