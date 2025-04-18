# SetupLogger Module

## Overview

The `SetupLogger` module provides a standardized and flexible way to set up logging for web scraping applications. It handles the configuration of log files, console output, log levels, and formatting, making it easy to integrate comprehensive logging into any scraper.

## Features

- **Standardized Logging**: Consistent logging format and behavior across modules
- **Dual Output**: Supports both file and console logging simultaneously
- **Directory Management**: Automatically creates log directories as needed
- **Configuration Integration**: Works with the ConfigManager module for centralized settings
- **Module-Level Loggers**: Easy creation of loggers specific to each module
- **Flexible Parameters**: Control over log levels, formats, and output options
- **Automatic Log Cleaning**: Option to clean existing log files to prevent excessive file growth

## Core Functions

- `setup_directories(directories)`: Creates multiple directory paths if they don't exist
- `clean_log_file(log_file)`: Cleans an existing log file by removing its contents
- `setup_logger(log_file, log_level=None, console_output=None, log_format=None, clean_logs=None)`: Sets up and configures a logger
- `get_logger(name, log_dir=None, clean_logs=None)`: Gets a configured logger with automatic file path generation
- `get_module_logger(clean_logs=None)`: Gets a logger for the current module with automatic naming

## How It Works

1. **Configuration Loading**: The module first attempts to load configuration from ConfigManager
2. **Directory Creation**: Log directories are automatically created if they don't exist
3. **Log Cleaning**: If enabled, existing log files are cleaned before logging begins
4. **Logger Setup**: A logger is created with the specified or default configuration
5. **Output Handlers**: File and optional console handlers are configured
6. **Format Configuration**: Log format is applied to all handlers

## Usage Examples

### Basic Usage

```python
from Scrapper.Modules.SetupLogger import get_logger

# Get a logger with automatic file naming
logger = get_logger("my_scraper")

# Log at different levels
logger.debug("This is a debug message")
logger.info("This is an information message")
logger.warning("This is a warning message")
logger.error("This is an error message")
logger.critical("This is a critical message")
```

### Custom Logger Setup

```python
from Scrapper.Modules.SetupLogger import setup_logger
import logging
import os

# Create a custom log file path
log_dir = "CustomLogs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "custom_scraper.log")

# Set up a logger with custom settings
logger = setup_logger(
    log_file=log_file,
    log_level=logging.DEBUG,  # More verbose logging
    console_output=True,      # Output to console
    log_format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Custom format
    clean_logs=True           # Clean the log file on startup
)

# Use the configured logger
logger.debug("Starting scraper with custom logging configuration")
logger.info("Scraper initialized")
```

### Disable Log Cleaning

```python
from Scrapper.Modules.SetupLogger import get_logger

# Get a logger that preserves existing log file content
logger = get_logger("append_scraper", clean_logs=False)

# New log entries will be appended to the existing file
logger.info("This log entry will be appended to any existing content")
```

### Module-Level Logger

```python
# File: my_scraper_module.py
from Scrapper.Modules.SetupLogger import get_module_logger

# Get a logger for this specific module
logger = get_module_logger()

def scrape_website(url):
    """Example function with integrated logging."""
    logger.info(f"Scraping website: {url}")
    
    try:
        # Scraping logic here...
        result = {"title": "Example Title", "url": url}
        logger.debug(f"Scraped data: {result}")
        return result
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return None

# Example usage
if __name__ == "__main__":
    scrape_website("https://example.com")
```

### Creating Directory Structure

```python
from Scrapper.Modules.SetupLogger import setup_directories

# Create multiple directories for the scraper
directories = [
    "Logs",
    "Data",
    "Data/Downloads",
    "Data/Processed",
    "Output"
]

# Create all directories in one go
setup_directories(directories)
```

### Integration with ConfigManager

```python
from Scrapper.Modules.SetupLogger import get_logger
from Scrapper.Modules.ConfigManager import get_config
import os

# Get the configuration manager
config = get_config()

# Set custom logging level and cleaning options in configuration
config.set("logging.level", "DEBUG")
config.set("logging.clean_logs", True)  # Clean logs on startup

# Get a logger (which will use the config settings)
logger = get_logger("config_example")

# Log messages at different levels
logger.debug("Debug message - visible because we set DEBUG level")
logger.info("Info message")

# Change log level and cleaning preference at runtime
config.set("logging.level", "WARNING")
config.set("logging.clean_logs", False)  # Future loggers will preserve log content
# Note: This won't affect existing loggers, only new ones
```

### Manually Cleaning Log Files

```python
from Scrapper.Modules.SetupLogger import clean_log_file, get_logger
import os

# Define a log file path
log_dir = "Logs/Manual"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "manual_clean.log")

# Get a logger without automatic cleaning
logger = get_logger("manual_clean", log_dir=log_dir, clean_logs=False)
logger.info("First log entry")

# Manually clean the log file later in the program
if some_condition:
    clean_log_file(log_file)
    logger.info("Log file has been manually cleaned")
```

### Complete Scraper Example

```python
from Scrapper.Modules.SetupLogger import get_logger
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.BrowserCleanup import ensure_browser_cleanup
import time

class WebScraper:
    def __init__(self, name="web_scraper", clean_logs=True):
        # Set up logging first
        self.logger = get_logger(name, clean_logs=clean_logs)
        self.logger.info("Initializing web scraper")
        
        # Set up browser
        self.browser_setup = BrowserSetup(self.logger)
        self.driver = None
        
    def initialize(self):
        """Initialize the browser driver."""
        self.logger.info("Setting up browser driver")
        try:
            self.driver = self.browser_setup.get_driver()
            self.logger.info("Browser driver initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize browser driver: {e}")
            return False
            
    def scrape(self, url, max_retries=3):
        """Scrape the given URL with retry logic."""
        if not self.driver and not self.initialize():
            self.logger.error("Cannot scrape - browser driver not initialized")
            return None
            
        # Log the scraping attempt
        self.logger.info(f"Scraping URL: {url}")
        
        # Retry logic with logging
        for attempt in range(1, max_retries + 1):
            try:
                self.logger.debug(f"Attempt {attempt}/{max_retries}")
                
                # Navigate to the page
                self.driver.get(url)
                self.logger.debug(f"Page loaded: {self.driver.title}")
                
                # Extract data
                data = {
                    "title": self.driver.title,
                    "url": url,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                self.logger.info(f"Successfully scraped: {data['title']}")
                return data
                
            except Exception as e:
                self.logger.warning(f"Attempt {attempt} failed: {e}")
                if attempt == max_retries:
                    self.logger.error(f"All {max_retries} attempts failed")
                else:
                    time.sleep(2)  # Wait before retrying
        
        return None
            
    def close(self):
        """Close the browser and clean up resources."""
        self.logger.info("Closing scraper and cleaning up resources")
        if self.driver:
            ensure_browser_cleanup(self.driver, self.logger)
            self.driver = None

# Usage
if __name__ == "__main__":
    # Use clean_logs=False to preserve log history across runs
    scraper = WebScraper("example_scraper", clean_logs=False)
    try:
        result = scraper.scrape("https://example.com")
        if result:
            print(f"Scraped: {result}")
    finally:
        scraper.close()
```

### Rotating Log Files

```python
from Scrapper.Modules.SetupLogger import get_logger, clean_log_file
import logging
from logging.handlers import RotatingFileHandler
import os

def get_rotating_logger(name, max_bytes=1048576, backup_count=5, clean_logs=True):
    """
    Get a logger with rotating file handler.
    
    Args:
        name: Logger name and log file base name
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        clean_logs: Whether to clean log files on startup
        
    Returns:
        Configured logger with rotating file handler
    """
    # Get a basic logger first
    logger = get_logger(name, clean_logs=clean_logs)
    
    # Get the log file path from the existing logger
    log_file = None
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            log_file = handler.baseFilename
            # Remove the original file handler
            logger.removeHandler(handler)
            break
    
    if not log_file:
        log_dir = os.path.join("Logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{name}.log")
    
    # Add rotating file handler
    rotating_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    
    # Set formatter
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    rotating_handler.setFormatter(formatter)
    
    # Add to logger
    logger.addHandler(rotating_handler)
    
    return logger

# Usage
logger = get_rotating_logger("scraper_with_rotation", max_bytes=5120, backup_count=3, clean_logs=True)
logger.info("This log will rotate when it exceeds 5 KB")
```

## Configuration

The module supports the following configuration options, which can be set in the ConfigManager:

| Config Key | Description | Default Value |
|------------|-------------|---------------|
| `logging.level` | The default logging level | `"INFO"` |
| `logging.format` | The format for log messages | `"%(asctime)s - %(levelname)s - %(message)s"` |
| `logging.console_output` | Whether to output logs to console | `True` |
| `logging.file_output` | Whether to output logs to file | `True` |
| `logging.clean_logs` | Whether to clean existing log files on startup | `True` |

## Best Practices

1. **Early Setup**: Set up logging as early as possible in your application
2. **Appropriate Levels**: Use the appropriate log level for each message
3. **Contextual Information**: Include relevant context in log messages
4. **Error Details**: Log full exception information for errors
5. **Consistent Naming**: Use consistent logger naming conventions
6. **Log Cleaning Strategy**: Use appropriate log cleaning settings for your application:
   - Set `clean_logs=True` for development to start with clean logs
   - Set `clean_logs=False` for production to preserve log history
   - Consider rotating log files for long-running applications

## Log Levels

- **DEBUG**: Detailed information, typically useful only for diagnosing problems
- **INFO**: Confirmation that things are working as expected
- **WARNING**: Indication that something unexpected happened, but the application is still working
- **ERROR**: Due to a more serious problem, the application has not been able to perform a function
- **CRITICAL**: A serious error, indicating that the application itself may be unable to continue running

## Troubleshooting

- **No Log Output**: Ensure the log level is not set too high
- **Missing Log Directory**: Verify that the module has write permissions
- **Duplicate Log Entries**: Check for multiple handlers with the same output
- **Performance Issues**: Reduce log verbosity in production environments
- **Log Cleaning Not Working**: Ensure the `clean_logs` parameter is correctly set and that the logger has permissions to modify the file 