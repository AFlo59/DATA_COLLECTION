# ConfigManager Module

## Overview

The `ConfigManager` module provides a centralized, flexible configuration management system for web scraping applications. It allows for loading configuration from multiple sources (defaults, files, environment variables) and provides a simple interface for accessing and modifying configuration values.

## Features

- **Centralized Configuration**: Single source of truth for application settings
- **Multiple Sources**: Load configuration from defaults, files, and environment variables
- **Hierarchical Settings**: Support for nested configuration with dot notation access
- **Type Conversion**: Automatic conversion of values to appropriate types
- **Singleton Pattern**: Ensures only one configuration manager exists
- **Directory Management**: Utility functions for handling directories
- **Default Fallbacks**: Sensible defaults for all settings

## Core Components

### `ConfigManager` Class

The main class for managing configuration with the following key methods:

- `__init__(config_file=None, logger=None)`: Initializes the configuration manager
- `load_from_file(file_path)`: Load configuration from a JSON file
- `get(key_path, default=None)`: Get a configuration value by key path
- `set(key_path, value)`: Set a configuration value by key path
- `save_to_file(file_path)`: Save the current configuration to a JSON file
- `get_logging_config()`: Get logging configuration
- `get_browser_config()`: Get browser configuration
- `get_directory(name)`: Get a directory path from configuration
- `ensure_directory(name)`: Get a directory path and ensure it exists
- `get_all()`: Get the entire configuration

### Standalone Functions

- `get_config()`: Get the global configuration manager instance
- `get(key_path, default=None)`: Convenience function for direct access to configuration values

## Default Configuration

The module provides sensible defaults for common settings:

- **Logging**: Level, format, console/file output, and log directory
- **Browser**: Browser type, headless mode, timeouts, user agent, and arguments
- **Cookies**: Detection and handling settings
- **Directories**: Standard directory structure for logs, data, output, etc.
- **Scraper**: Retry attempts, timeouts, and other behavior settings

## How It Works

1. **Initialization**: The module creates a singleton instance of the ConfigManager with default values.
2. **Loading**: Configuration can be loaded from JSON files, which are deep-merged with defaults.
3. **Environment Variables**: Settings can be overridden by environment variables with the prefix `SCRAPER_`.
4. **Access**: Values can be accessed using dot notation (`logging.level`) with fallback defaults.
5. **Modification**: Settings can be modified at runtime and optionally saved back to a file.

## Usage Examples

### Basic Usage

```python
from Scrapper.Modules.ConfigManager import get, get_config

# Access a configuration value directly
log_level = get("logging.level")
print(f"Log level: {log_level}")

# Get the timeout setting with a default fallback
timeout = get("browser.timeout", 30)
print(f"Browser timeout: {timeout}")

# Get the entire configuration manager
config = get_config()
browser_config = config.get_browser_config()
print(f"Browser configuration: {browser_config}")
```

### Loading from a File

```python
import json
from Scrapper.Modules.ConfigManager import ConfigManager
from Scrapper.Modules.SetupLogger import get_logger

# Create a logger instance
logger = get_logger("config_example")

# Create a configuration file
config_data = {
    "logging": {
        "level": "DEBUG"
    },
    "browser": {
        "headless": True,
        "timeout": 60
    }
}

# Write the config to a file
with open("my_config.json", "w") as f:
    json.dump(config_data, f, indent=2)

# Initialize the configuration manager with the file
config = ConfigManager(config_file="my_config.json", logger=logger)

# Access values that should be overridden from the file
log_level = config.get("logging.level")  # Should be "DEBUG"
is_headless = config.get("browser.headless")  # Should be True
timeout = config.get("browser.timeout")  # Should be 60

print(f"Log level: {log_level}")
print(f"Headless mode: {is_headless}")
print(f"Timeout: {timeout}")
```

### Modifying and Saving Configuration

```python
from Scrapper.Modules.ConfigManager import get_config
import os

# Get the configuration manager
config = get_config()

# Modify some settings
config.set("browser.headless", True)
config.set("browser.timeout", 60)
config.set("logging.level", "DEBUG")

# Create a custom setting
config.set("my_scraper.target_site", "https://example.com")
config.set("my_scraper.elements_to_extract", ["title", "description", "price"])

# Ensure the output directory exists
output_dir = config.ensure_directory("output")
print(f"Output directory: {output_dir}")

# Save the modified configuration
config_file = os.path.join(output_dir, "scraper_config.json")
if config.save_to_file(config_file):
    print(f"Configuration saved to {config_file}")
```

### Integration with Other Modules

```python
from Scrapper.Modules.ConfigManager import get_config
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.SetupLogger import setup_logger

# Get the configuration manager
config = get_config()

# Set up logging using the configuration
log_dir = config.ensure_directory("logs")
log_file = os.path.join(log_dir, "scraper.log")
logger = setup_logger(
    log_file, 
    log_level=None,  # Use from config
    console_output=None,  # Use from config
    log_format=None  # Use from config
)

# Get browser configuration
browser_config = config.get_browser_config()
logger.info(f"Using browser configuration: {browser_config}")

# Set up the browser
browser_setup = BrowserSetup(logger)
driver = browser_setup.get_driver()

# Use timeout from configuration
page_load_timeout = config.get("browser.page_load_timeout", 30)
driver.set_page_load_timeout(page_load_timeout)

try:
    # Use the driver for web scraping
    driver.get("https://example.com")
    logger.info(f"Page title: {driver.title}")
finally:
    browser_setup.close()
```

### Creating a Configurable Scraper Class

```python
from Scrapper.Modules.ConfigManager import get_config
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.BrowserCleanup import ensure_browser_cleanup
from Scrapper.Modules.SetupLogger import get_logger

class ConfigurableScraper:
    def __init__(self, custom_config_file=None):
        # Initialize configuration first
        if custom_config_file:
            self.config = get_config()
            self.config.load_from_file(custom_config_file)
        else:
            self.config = get_config()
            
        # Set up logger
        self.logger = get_logger("configurable_scraper")
        
        # Get retry settings from config
        self.retry_attempts = self.config.get("scraper.retry_attempts", 3)
        self.retry_delay = self.config.get("scraper.retry_delay", 2)
        
        # Browser setup
        self.browser_setup = BrowserSetup(self.logger)
        self.driver = None
        
    def initialize(self):
        self.driver = self.browser_setup.get_driver()
        
        # Apply browser settings from config
        page_load_timeout = self.config.get("browser.page_load_timeout", 30)
        implicit_wait = self.config.get("browser.implicit_wait", 10)
        
        self.driver.set_page_load_timeout(page_load_timeout)
        self.driver.implicitly_wait(implicit_wait)
        
    def scrape(self, url):
        if not self.driver:
            self.initialize()
            
        # Use retry mechanism from config
        for attempt in range(self.retry_attempts):
            try:
                self.driver.get(url)
                # More scraping code...
                return {"title": self.driver.title, "url": url}
            except Exception as e:
                self.logger.warning(f"Attempt {attempt+1}/{self.retry_attempts} failed: {e}")
                if attempt < self.retry_attempts - 1:
                    import time
                    time.sleep(self.retry_delay)
                else:
                    self.logger.error(f"All retry attempts failed for URL: {url}")
                    raise
                    
    def close(self):
        if self.driver:
            ensure_browser_cleanup(self.driver, self.logger)
            self.driver = None
            
# Usage
scraper = ConfigurableScraper()
try:
    result = scraper.scrape("https://example.com")
    print(f"Scraped: {result}")
finally:
    scraper.close()
```

## Best Practices

1. **Use the Singleton**: Access the config through `get_config()` or `get()` to ensure consistency
2. **Override Judiciously**: Only override settings you need to change
3. **Validate Settings**: Verify critical settings before using them
4. **Use Environment Variables**: For deployment-specific or sensitive settings
5. **Log Configuration**: Log the active configuration at startup for troubleshooting

## Troubleshooting

- **Missing Settings**: Check if you're using the correct key path with `get()`
- **Type Issues**: Ensure environment variables are properly converted to expected types
- **File Loading Problems**: Verify JSON file format and permissions 