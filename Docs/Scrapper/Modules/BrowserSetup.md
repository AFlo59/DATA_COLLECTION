# BrowserSetup Module

## Overview

The `BrowserSetup` module provides a robust, cross-platform solution for initializing and managing browser driver instances for web scraping. It is designed to handle the complexities of browser automation with built-in fallbacks and error recovery mechanisms.

## Features

- **Driver Initialization**: Creates and configures browser drivers with appropriate settings
- **Fallback Mechanisms**: Falls back to alternative drivers if the primary option fails
- **Cross-Browser Support**: Focus on Chrome with potential for expansion
- **Headless Mode**: Option to run browsers in headless mode
- **User Agent Management**: Customizable user agent strings
- **Download Directory Configuration**: Configurable download paths
- **Resource Management**: Automatic cleanup of browser resources

## Core Components

### `BrowserSetup` Class

The main class for managing browser setup with the following key methods:

- `__init__(logger=None)`: Initializes the browser setup manager
- `setup_chrome_options()`: Sets up Chrome options with appropriate settings
- `create_driver()`: Creates and configures a browser driver with fallbacks
- `get_driver()`: Gets or creates a browser driver instance
- `close()`: Closes and cleans up the browser driver

### Standalone Function

- `get_browser_driver(logger=None)`: Helper function to get a browser driver with setup handled

## Prerequisites

This module requires one or more of the following packages:
- `selenium`
- `undetected-chromedriver`
- `webdriver-manager`

## How It Works

1. **Initialization**: The module first checks for available browser driver libraries.
2. **Configuration**: Chrome options are configured with appropriate arguments.
3. **Driver Creation**: The module attempts to create a driver using the following strategy:
   - First try with `undetected_chromedriver` (best for avoiding detection)
   - Fall back to selenium with webdriver_manager
   - Last resort: selenium with manually specified chromedriver
4. **Resource Tracking**: All created drivers are tracked for proper cleanup.
5. **Cleanup**: When the driver is no longer needed, resources are properly released.

## Error Handling

The module includes robust error handling:
- Graceful fallbacks if primary driver initialization fails
- Patched `__del__` method for `undetected_chromedriver` to prevent shutdown errors
- Detailed logging of initialization attempts and failures

## Usage Examples

### Basic Usage

```python
from Scrapper.Modules.BrowserSetup import get_browser_driver
import logging

# Set up logging
logger = logging.getLogger("scraper")

# Get a browser driver (returns driver and boolean indicating if it's undetected_chromedriver)
driver, is_undetected = get_browser_driver(logger)

try:
    # Use the driver for web scraping
    driver.get("https://example.com")
    page_title = driver.title
    print(f"Page title: {page_title}")
finally:
    # Always close the driver to release resources
    if driver:
        driver.quit()
```

### Using the BrowserSetup Class

```python
from Scrapper.Modules.BrowserSetup import BrowserSetup
import logging

# Set up logging
logger = logging.getLogger("scraper")
logger.setLevel(logging.INFO)

# Initialize browser setup
browser_setup = BrowserSetup(logger)

try:
    # Get a driver instance
    driver = browser_setup.get_driver()
    
    # Navigate to a website
    driver.get("https://example.com")
    
    # Perform scraping operations
    elements = driver.find_elements_by_css_selector("h1")
    for element in elements:
        print(element.text)
        
finally:
    # Close the browser and clean up resources
    browser_setup.close()
```

### Integration with Other Modules

```python
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.CookieHandler import handle_cookie_consent
from Scrapper.Modules.SetupLogger import get_logger

# Get a logger instance
logger = get_logger("my_scraper")

# Initialize browser setup
browser_setup = BrowserSetup(logger)

try:
    # Get a driver instance
    driver = browser_setup.get_driver()
    
    # Navigate to a website
    driver.get("https://example.com")
    
    # Handle cookie consent popup if present
    handle_cookie_consent(driver, logger=logger)
    
    # Continue with scraping...
    
finally:
    # Close the browser and clean up resources
    browser_setup.close()
```

## Best Practices

1. **Always Close Drivers**: Always close browser drivers in a `finally` block to ensure resources are properly released.
2. **Use Logging**: Provide a logger instance to track browser setup events and potential issues.
3. **Handle Exceptions**: Wrap browser operations in try-except blocks to handle potential errors.
4. **Use Timeouts**: Set appropriate timeouts for page loads and element searches.
5. **Resource Management**: For long-running processes, consider using the browser cleanup module to ensure all resources are properly released.

## Troubleshooting

- **Driver Initialization Failures**: Check Chrome version compatibility with the driver version
- **Resource Leaks**: If you experience memory issues, ensure all drivers are properly closed
- **Detection Issues**: If you're being detected as a bot, try using `undetected_chromedriver` 