# DetectPackages Module

## Overview

The `DetectPackages` module provides functions to detect installed Python packages, their versions, and compatibility. It helps web scraping applications ensure that the required dependencies are available and compatible, particularly focusing on packages needed for browser automation.

## Features

- **Package Detection**: Identify installed packages and their versions
- **Chrome Version Detection**: Detect the installed Chrome browser's major version
- **User Agent Generation**: Create custom User-Agent strings with system and package information
- **Dependency Compatibility Check**: Verify compatibility between installed packages

## Core Functions

- `detect_installed_packages(package_names)`: Detects installed packages and their versions
- `detect_chrome_version()`: Detects the installed Chrome browser's major version
- `get_user_agent(include_packages=None)`: Generates a customized User-Agent string
- `check_dependency_compatibility()`: Checks compatibility between installed packages

## How It Works

1. **Package Detection**: The module attempts multiple methods to detect package versions:
   - First using `importlib.metadata` (Python 3.8+)
   - Falling back to module attributes (`__version__` or `version`)
   - Using `pkg_resources` as a last resort
2. **Chrome Detection**: Uses OS-specific methods to find and query Chrome version
3. **User Agent**: Combines system information and package versions into a custom UA string
4. **Compatibility Check**: Examines known compatibility issues between package versions

## Usage Examples

### Basic Package Detection

```python
from Scrapper.Modules.DetectPackages import detect_installed_packages

# Check for commonly used packages
packages_to_check = [
    "selenium", 
    "undetected-chromedriver", 
    "requests", 
    "beautifulsoup4", 
    "pandas"
]

# Get installed versions
installed_packages = detect_installed_packages(packages_to_check)

# Display results
print("Installed Packages:")
for package, version in installed_packages.items():
    if version != "unknown":
        print(f"  {package}: {version}")
    else:
        print(f"  {package}: Not installed or version unknown")
```

### Chrome Version Detection

```python
from Scrapper.Modules.DetectPackages import detect_chrome_version

# Detect Chrome version
chrome_version = detect_chrome_version()

if chrome_version is not None:
    print(f"Chrome version: {chrome_version}")
else:
    print("Chrome not detected or version could not be determined")
```

### Custom User Agent Generation

```python
from Scrapper.Modules.DetectPackages import get_user_agent

# Generate a default user agent with common packages
default_user_agent = get_user_agent()
print(f"Default User-Agent: {default_user_agent}")

# Generate a user agent with specific packages
custom_packages = ["selenium", "requests", "lxml"]
custom_user_agent = get_user_agent(include_packages=custom_packages)
print(f"Custom User-Agent: {custom_user_agent}")
```

### Dependency Compatibility Check

```python
from Scrapper.Modules.DetectPackages import check_dependency_compatibility

# Check compatibility between installed packages
is_compatible, warnings = check_dependency_compatibility()

if is_compatible:
    print("All packages are compatible")
else:
    print("Package compatibility issues detected:")
    for warning in warnings:
        print(f"  - {warning}")
```

### Integration with Browser Setup

```python
from Scrapper.Modules.DetectPackages import detect_chrome_version
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.SetupLogger import get_logger

# Get a logger instance
logger = get_logger("browser_setup_example")

# Detect Chrome version
chrome_version = detect_chrome_version()
if chrome_version:
    logger.info(f"Detected Chrome version: {chrome_version}")
else:
    logger.warning("Chrome version could not be detected")

# Initialize browser setup
browser_setup = BrowserSetup(logger)

try:
    # Create driver with the detected Chrome version
    driver = browser_setup.get_driver()
    # Use the driver...
finally:
    browser_setup.close()
```

### Full Package Environment Check

```python
from Scrapper.Modules.DetectPackages import detect_installed_packages, check_dependency_compatibility
from Scrapper.Modules.SetupLogger import get_logger
import sys

def verify_environment():
    """Verify that all required packages are installed and compatible."""
    logger = get_logger("environment_check")
    
    # Define required packages with minimum versions
    required_packages = {
        "selenium": "4.1.0",
        "undetected-chromedriver": "3.0.5",
        "beautifulsoup4": "4.9.3",
        "requests": "2.26.0",
        "pandas": "1.3.0",
        "urllib3": "1.26.7"
    }
    
    # Check installed packages
    installed = detect_installed_packages(list(required_packages.keys()))
    
    # Check for missing packages
    missing_packages = []
    outdated_packages = []
    
    for package, required_version in required_packages.items():
        if package not in installed or installed[package] == "unknown":
            missing_packages.append(package)
        elif installed[package] != "unknown":
            # Very basic version comparison (would need more robust parsing for real use)
            try:
                installed_parts = [int(p) for p in installed[package].split('.')]
                required_parts = [int(p) for p in required_version.split('.')]
                
                # Pad with zeros for different length versions
                while len(installed_parts) < len(required_parts):
                    installed_parts.append(0)
                while len(required_parts) < len(installed_parts):
                    required_parts.append(0)
                
                # Compare versions
                if installed_parts < required_parts:
                    outdated_packages.append(
                        f"{package} (installed: {installed[package]}, required: {required_version})"
                    )
            except (ValueError, TypeError):
                logger.warning(f"Could not compare versions for {package}")
    
    # Check compatibility
    is_compatible, compatibility_warnings = check_dependency_compatibility()
    
    # Output results
    if missing_packages:
        logger.error("Missing required packages:")
        for package in missing_packages:
            logger.error(f"  - {package} (required: {required_packages[package]})")
            
    if outdated_packages:
        logger.warning("Outdated packages:")
        for package_info in outdated_packages:
            logger.warning(f"  - {package_info}")
            
    if not is_compatible:
        logger.warning("Package compatibility issues detected:")
        for warning in compatibility_warnings:
            logger.warning(f"  - {warning}")
            
    if not missing_packages and not outdated_packages and is_compatible:
        logger.info("Environment check passed. All required packages are installed and compatible.")
        return True
    else:
        logger.error("Environment check failed. Please install/update required packages.")
        return False

# Usage
if not verify_environment():
    print("Please fix environment issues before continuing.")
    sys.exit(1)
```

### Creating a Custom Browser Manager

```python
from Scrapper.Modules.DetectPackages import detect_chrome_version, get_user_agent
from Scrapper.Modules.SetupLogger import get_logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

class BrowserManager:
    def __init__(self):
        self.logger = get_logger("browser_manager")
        self.driver = None
        
    def create_driver(self, headless=False):
        # Get Chrome version
        chrome_version = detect_chrome_version()
        if chrome_version:
            self.logger.info(f"Detected Chrome version: {chrome_version}")
        else:
            self.logger.warning("Chrome version not detected")
        
        # Setup Chrome options
        options = Options()
        
        # Set a custom user agent
        user_agent = get_user_agent()
        options.add_argument(f'user-agent={user_agent}')
        
        # Set headless mode if requested
        if headless:
            options.add_argument('--headless')
        
        # Common options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        # Create the driver
        try:
            self.driver = webdriver.Chrome(options=options)
            self.logger.info("Chrome driver created successfully")
            return self.driver
        except Exception as e:
            self.logger.error(f"Failed to create Chrome driver: {e}")
            raise
            
    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logger.info("Chrome driver closed")

# Usage
browser = BrowserManager()
try:
    driver = browser.create_driver(headless=True)
    driver.get("https://example.com")
    print(f"Page title: {driver.title}")
finally:
    browser.close()
```

## Best Practices

1. **Version Checking**: Verify package versions before starting scraping operations
2. **Compatibility Verification**: Check for known compatibility issues between packages
3. **Custom User Agents**: Use customized user agents to blend in with normal web traffic
4. **Error Handling**: Implement robust error handling for package detection failures
5. **Chrome Version Handling**: Use detected Chrome version for compatible driver selection

## Troubleshooting

- **Package Not Found**: Ensure the package is installed and accessible in the current Python environment
- **Version Detection Failure**: Try alternative methods like `pip freeze` to list installed packages
- **Chrome Not Detected**: Verify Chrome is installed in a standard location or provide a custom path
- **Compatibility Issues**: Update packages to compatible versions based on compatibility warnings 