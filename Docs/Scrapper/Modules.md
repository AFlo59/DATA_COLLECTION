# Scrapper Modules Documentation

This documentation provides an overview of the modular components used in the scraping framework. Each module is designed with a specific purpose, following clean programming principles and the "Don't Repeat Yourself" (DRY) philosophy.

## Available Modules

| Module | Description | Documentation |
|--------|-------------|---------------|
| **BrowserSetup** | Initializes and configures browser driver instances with fallbacks and error recovery | [BrowserSetup.md](Modules/BrowserSetup.md) |
| **BrowserCleanup** | Ensures proper cleanup of browser resources and prevents memory leaks | [BrowserCleanup.md](Modules/BrowserCleanup.md) |
| **ConfigManager** | Provides centralized configuration management with multiple sources | [ConfigManager.md](Modules/ConfigManager.md) |
| **CookieHandler** | Handles cookie consent popups and banners with multiple strategies | [CookieHandler.md](Modules/CookieHandler.md) |
| **DetectOS** | Provides cross-platform OS detection and system information retrieval | [DetectOS.md](Modules/DetectOS.md) |
| **DetectPackages** | Detects installed Python packages, versions, and compatibility | [DetectPackages.md](Modules/DetectPackages.md) |
| **SetupLogger** | Configures standardized logging with file and console output | [SetupLogger.md](Modules/SetupLogger.md) |

## Module Dependencies

The modules have dependencies on each other as shown in the following diagram:

```
┌───────────────┐     ┌────────────────┐     ┌─────────────────┐
│ SetupLogger   │◄────┤ ConfigManager  │◄────┤ BrowserSetup    │
└───────┬───────┘     └────────┬───────┘     └────────┬────────┘
        │                      │                      │
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐     ┌────────────────┐     ┌─────────────────┐
│ DetectOS      │────►│ DetectPackages │────►│ BrowserCleanup  │
└───────────────┘     └────────────────┘     └─────────────────┘
                              │
                              │
                              ▼
                      ┌────────────────┐
                      │ CookieHandler  │
                      └────────────────┘
```

## Getting Started

To start using these modules in your scraper, the recommended initialization sequence is:

1. Initialize the `ConfigManager` to load configuration
2. Set up logging with `SetupLogger`
3. Create browser instances with `BrowserSetup`
4. Register browsers with `BrowserCleanup` for proper cleanup
5. Use `CookieHandler` when navigating to websites with cookie consent popups

### Basic Usage Example

```python
from Scrapper.Modules.ConfigManager import get_config
from Scrapper.Modules.SetupLogger import get_logger
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.BrowserCleanup import register_browser, ensure_browser_cleanup
from Scrapper.Modules.CookieHandler import handle_cookie_consent

# Get configuration manager
config = get_config()

# Get a logger
logger = get_logger("my_scraper")
logger.info("Initializing scraper")

# Set up browser
browser_setup = BrowserSetup(logger)
driver = browser_setup.get_driver()

# Register browser for automatic cleanup
register_browser(driver, logger)

try:
    # Navigate to a website
    url = "https://example.com"
    logger.info(f"Navigating to {url}")
    driver.get(url)
    
    # Handle cookie consent
    handle_cookie_consent(driver, logger=logger)
    
    # Perform scraping operations
    title = driver.title
    logger.info(f"Page title: {title}")
    
finally:
    # Ensure proper cleanup
    ensure_browser_cleanup(driver, logger)
```

## Comprehensive Example

For a more comprehensive example that uses all the modules together, see the [Scraper Example](Examples/ScraperExample.md) documentation.

## Testing

All modules have comprehensive unit tests in the `Scrapper/Modules/tests` directory. To run the tests, use the following command:

```bash
python -m unittest discover -s Scrapper/Modules/tests
```

## Troubleshooting

If you encounter issues while using these modules, please refer to the troubleshooting section in each module's documentation. Common issues and their solutions are discussed there. 