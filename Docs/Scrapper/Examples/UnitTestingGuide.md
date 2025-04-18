# Unit Testing Guide for Scraping Modules

This guide provides instructions and examples for creating effective unit tests for the scraping framework modules.

## Table of Contents

- [Testing Philosophy](#testing-philosophy)
- [Testing Environment Setup](#testing-environment-setup)
- [Test Directory Structure](#test-directory-structure)
- [Essential Testing Patterns](#essential-testing-patterns)
- [Mock Examples](#mock-examples)
- [Individual Module Testing](#individual-module-testing)
- [Integration Testing](#integration-testing)
- [Continuous Integration](#continuous-integration)

## Testing Philosophy

When testing scraping modules, follow these principles:

1. **Isolate modules**: Test each module independently before testing their interactions
2. **Mock external dependencies**: Don't rely on actual websites or browsers for unit tests
3. **Test edge cases**: Include tests for error conditions and unexpected inputs
4. **Parameterize tests**: Use different test data to ensure robustness
5. **Keep tests fast**: Unit tests should execute quickly to enable rapid development

## Testing Environment Setup

First, set up a proper testing environment:

```bash
# Install testing dependencies
pip install pytest pytest-cov pytest-mock requests-mock

# Create a tests directory structure
mkdir -p Scrapper/tests/unit
mkdir -p Scrapper/tests/integration
mkdir -p Scrapper/tests/fixtures
```

Create a basic `conftest.py` in the tests directory:

```python
# Scrapper/tests/conftest.py
import os
import sys
import pytest
import json
import tempfile

# Add project root to path to ensure imports work correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Sample config for testing
@pytest.fixture
def sample_config():
    return {
        "logging": {
            "level": "DEBUG",
            "format": "%(asctime)s - %(levelname)s - %(message)s",
            "console_output": True,
            "file_output": False
        },
        "browser": {
            "type": "chrome",
            "headless": True,
            "timeout": 10
        }
    }

# Temporary config file fixture
@pytest.fixture
def config_file():
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
        json.dump({
            "logging": {
                "level": "DEBUG",
                "format": "%(asctime)s - %(levelname)s - %(message)s",
                "console_output": True,
                "file_output": False
            },
            "browser": {
                "type": "chrome",
                "headless": True,
                "timeout": 10
            }
        }, f)
        config_path = f.name
    
    yield config_path
    
    # Clean up the temporary file
    if os.path.exists(config_path):
        os.unlink(config_path)

# Mock logger fixture
@pytest.fixture
def mock_logger():
    class MockLogger:
        def __init__(self):
            self.info_messages = []
            self.warning_messages = []
            self.error_messages = []
            self.debug_messages = []
        
        def info(self, msg):
            self.info_messages.append(msg)
        
        def warning(self, msg):
            self.warning_messages.append(msg)
        
        def error(self, msg):
            self.error_messages.append(msg)
        
        def debug(self, msg):
            self.debug_messages.append(msg)
    
    return MockLogger()

# Mock browser driver
@pytest.fixture
def mock_driver():
    class MockDriver:
        def __init__(self):
            self.current_url = "https://example.com"
            self.page_source = "<html><body>Example Page</body></html>"
            self.closed = False
            self.commands = []
            self.options = {}
        
        def get(self, url):
            self.commands.append(f"get: {url}")
            self.current_url = url
        
        def quit(self):
            self.commands.append("quit")
            self.closed = True
        
        def close(self):
            self.commands.append("close")
            self.closed = True
        
        def find_element(self, by, value):
            self.commands.append(f"find_element: {by}, {value}")
            return MockElement(f"Element: {by}={value}")
        
        def find_elements(self, by, value):
            self.commands.append(f"find_elements: {by}, {value}")
            return [MockElement(f"Element {i}: {by}={value}") for i in range(3)]
        
        def execute_script(self, script, *args):
            self.commands.append(f"execute_script: {script[:50]}...")
            return "script_result"
        
        def set_page_load_timeout(self, timeout):
            self.commands.append(f"set_page_load_timeout: {timeout}")
            self.options['page_load_timeout'] = timeout
        
        def implicitly_wait(self, timeout):
            self.commands.append(f"implicitly_wait: {timeout}")
            self.options['implicit_wait'] = timeout
    
    class MockElement:
        def __init__(self, name):
            self.name = name
            self.text = f"Text of {name}"
            self.tag_name = "div"
            self.attributes = {"src": "image.jpg", "href": "https://example.com/link"}
        
        def click(self):
            return f"Clicked {self.name}"
        
        def get_attribute(self, attr):
            return self.attributes.get(attr)
    
    return MockDriver()
```

## Test Directory Structure

Organize your tests following this structure:

```
Scrapper/
├── tests/
│   ├── conftest.py                # Common fixtures
│   ├── fixtures/                  # Test data files
│   │   ├── config_sample.json
│   │   └── html_samples/
│   │       ├── product_page.html
│   │       └── cookie_consent.html
│   ├── unit/                      # Unit tests
│   │   ├── test_browser_setup.py
│   │   ├── test_browser_cleanup.py
│   │   ├── test_config_manager.py
│   │   ├── test_cookie_handler.py
│   │   ├── test_detect_os.py
│   │   ├── test_detect_packages.py
│   │   └── test_setup_logger.py
│   └── integration/               # Integration tests
│       ├── test_browser_workflow.py
│       └── test_scraping_pipeline.py
```

## Essential Testing Patterns

### 1. Using Pytest Fixtures

Example of using fixtures in a test:

```python
# test_config_manager.py
import pytest
from Scrapper.Modules.ConfigManager import ConfigManager

def test_config_manager_initialization(config_file):
    """Test ConfigManager initialization with a file"""
    config = ConfigManager(config_file=config_file)
    assert config.get("logging.level") == "DEBUG"
    assert config.get("browser.headless") == True

def test_config_manager_set_get():
    """Test setting and getting config values"""
    config = ConfigManager()
    config.set("test.key", "test_value")
    assert config.get("test.key") == "test_value"
    
    # Test nested values
    config.set("nested.value.key", 42)
    assert config.get("nested.value.key") == 42
    
    # Test default value
    assert config.get("non.existent.key", "default") == "default"
```

### 2. Mocking External Dependencies

```python
# test_browser_setup.py
import pytest
from unittest.mock import patch, MagicMock
from Scrapper.Modules.BrowserSetup import BrowserSetup

def test_browser_setup_initialization(mock_logger):
    """Test BrowserSetup initialization"""
    browser_setup = BrowserSetup(mock_logger)
    assert browser_setup.logger == mock_logger

@patch("Scrapper.Modules.BrowserSetup.uc")
def test_get_driver_with_undetected_chromedriver(mock_uc, mock_logger):
    """Test get_driver using undetected_chromedriver"""
    # Setup mock
    mock_driver = MagicMock()
    mock_uc.Chrome.return_value = mock_driver
    
    # Create browser setup and get driver
    browser_setup = BrowserSetup(mock_logger)
    driver = browser_setup.get_driver(use_undetected=True)
    
    # Assertions
    assert driver == mock_driver
    assert "initialized undetected_chromedriver" in " ".join(mock_logger.info_messages).lower()
    mock_uc.Chrome.assert_called_once()
```

### 3. Testing Error Handling

```python
# test_cookie_handler.py
import pytest
from selenium.common.exceptions import TimeoutException
from Scrapper.Modules.CookieHandler import CookieHandler

def test_cookie_handler_handle_consent_with_exception(mock_logger, mock_driver):
    """Test cookie handler when an exception occurs"""
    # Setup mock driver to raise exception on find_element
    def raise_timeout(*args, **kwargs):
        raise TimeoutException("Timeout finding cookie banner")
    
    original_find_element = mock_driver.find_element
    mock_driver.find_element = raise_timeout
    
    # Create cookie handler and test
    cookie_handler = CookieHandler(mock_logger)
    result = cookie_handler.handle_consent(mock_driver)
    
    # Assertions
    assert result is False
    assert any("failed to handle cookie consent" in msg.lower() for msg in mock_logger.error_messages)
    
    # Restore original method
    mock_driver.find_element = original_find_element
```

## Mock Examples

### 1. Mocking Selenium WebDriver

```python
# test_browser_cleanup.py
import pytest
from Scrapper.Modules.BrowserCleanup import BrowserCleanup

def test_close_browser(mock_logger, mock_driver):
    """Test browser cleanup close_browser method"""
    browser_cleanup = BrowserCleanup(mock_logger)
    result = browser_cleanup.close_browser(mock_driver)
    
    # Assertions
    assert result is True
    assert mock_driver.closed is True
    assert "browser closed successfully" in " ".join(mock_logger.info_messages).lower()
```

### 2. Mocking OS Functions

```python
# test_detect_os.py
import pytest
from unittest.mock import patch
from Scrapper.Modules.DetectOS import get_os_info

@patch("platform.system", return_value="TestOS")
@patch("platform.release", return_value="1.0")
@patch("platform.machine", return_value="x64")
@patch("sys.version", "3.9.0")
def test_get_os_info(mock_system, mock_release, mock_machine):
    """Test get_os_info with mocked platform functions"""
    os_info = get_os_info()
    
    # Assertions
    assert os_info["system"] == "TestOS"
    assert os_info["release"] == "1.0"
    assert os_info["machine"] == "x64"
    assert "3.9.0" in os_info["python_version"]
```

## Individual Module Testing

### Testing ConfigManager

```python
# test_config_manager.py
import pytest
import os
import json
from Scrapper.Modules.ConfigManager import ConfigManager, get_config

def test_config_manager_save(tmp_path):
    """Test saving configuration to a file"""
    # Create config
    config = ConfigManager()
    config.set("test.key", "test_value")
    
    # Save to file
    config_path = os.path.join(tmp_path, "test_config.json")
    config.save(config_path)
    
    # Verify file contents
    with open(config_path, 'r') as f:
        saved_config = json.load(f)
    
    assert "test" in saved_config
    assert saved_config["test"]["key"] == "test_value"

def test_get_config_singleton():
    """Test that get_config returns a singleton instance"""
    config1 = get_config()
    config2 = get_config()
    
    # Both should be the same instance
    assert config1 is config2
    
    # Modify one and check the other
    config1.set("singleton.test", "value")
    assert config2.get("singleton.test") == "value"
```

### Testing BrowserSetup

```python
# test_browser_setup.py
import pytest
from unittest.mock import patch, MagicMock
from Scrapper.Modules.BrowserSetup import BrowserSetup

@patch("Scrapper.Modules.BrowserSetup.webdriver")
def test_browser_setup_regular_chrome(mock_webdriver, mock_logger):
    """Test BrowserSetup with regular Chrome driver"""
    mock_chrome = MagicMock()
    mock_options = MagicMock()
    mock_webdriver.ChromeOptions.return_value = mock_options
    mock_webdriver.Chrome.return_value = mock_chrome
    
    browser_setup = BrowserSetup(mock_logger)
    driver = browser_setup.get_driver(use_undetected=False)
    
    assert driver == mock_chrome
    mock_webdriver.Chrome.assert_called_once()
    assert mock_options.add_argument.call_count > 0

@pytest.mark.parametrize("headless", [True, False])
@patch("Scrapper.Modules.BrowserSetup.webdriver")
def test_chrome_options_headless(mock_webdriver, mock_logger, headless):
    """Test Chrome options with different headless settings"""
    # Setup mocks
    mock_options = MagicMock()
    mock_webdriver.ChromeOptions.return_value = mock_options
    
    # Create browser setup with config setting
    browser_setup = BrowserSetup(mock_logger)
    browser_setup.config.set("browser.headless", headless)
    
    # Get driver
    browser_setup.get_driver(use_undetected=False)
    
    # Check if headless argument was added properly
    if headless:
        mock_options.add_argument.assert_any_call("--headless=new")
    else:
        # Not a perfect test, but checks that exact headless string wasn't passed
        assert not any("--headless=new" in str(call) for call in mock_options.add_argument.call_args_list)
```

### Testing SetupLogger

```python
# test_setup_logger.py
import pytest
import os
import logging
from Scrapper.Modules.SetupLogger import setup_logger, get_logger, setup_directories

def test_setup_logger():
    """Test that setup_logger creates a proper logger"""
    logger = setup_logger("test_logger", log_level=logging.DEBUG)
    
    # Check logger properties
    assert logger.name == "test_logger"
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) > 0

def test_get_logger_singleton():
    """Test that get_logger returns the same logger for the same name"""
    logger1 = get_logger("singleton_test")
    logger2 = get_logger("singleton_test")
    
    assert logger1 is logger2

def test_setup_directories(tmp_path):
    """Test that setup_directories creates directories as expected"""
    base_dir = str(tmp_path)
    dirs_to_create = ["logs", "data", "output"]
    
    # Run the function
    created_dirs = setup_directories(dirs_to_create, base_dir)
    
    # Check that all directories were created
    assert len(created_dirs) == len(dirs_to_create)
    for dir_name in dirs_to_create:
        expected_path = os.path.join(base_dir, dir_name)
        assert os.path.exists(expected_path)
        assert os.path.isdir(expected_path)
        assert expected_path in created_dirs
```

## Integration Testing

For integration tests, we'll test how multiple modules work together:

```python
# test_browser_workflow.py
import pytest
from unittest.mock import patch
from Scrapper.Modules.ConfigManager import get_config
from Scrapper.Modules.SetupLogger import get_logger
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.BrowserCleanup import BrowserCleanup
from Scrapper.Modules.CookieHandler import CookieHandler

@patch("Scrapper.Modules.BrowserSetup.webdriver")
def test_browser_setup_cleanup_integration(mock_webdriver, mock_logger):
    """Test the integration between BrowserSetup and BrowserCleanup"""
    # Setup mocks
    mock_driver = mock_webdriver.Chrome.return_value
    
    # Setup modules
    browser_setup = BrowserSetup(mock_logger)
    browser_cleanup = BrowserCleanup(mock_logger)
    
    # Register browser with cleanup
    driver = browser_setup.get_driver(use_undetected=False)
    browser_cleanup.register_browser(driver)
    
    # Close registered browsers
    browser_cleanup.close_all_browsers()
    
    # Check that the driver was closed
    mock_driver.quit.assert_called_once()
```

## Continuous Integration

Creating a GitHub Actions workflow for your tests:

Create a file at `.github/workflows/tests.yml`:

```yaml
name: Run Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, '3.10']

    steps:
    - uses: actions/checkout@v3
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest pytest-cov pytest-mock requests-mock
        if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
    
    - name: Test with pytest
      run: |
        pytest --cov=Scrapper --cov-report=xml
    
    - name: Upload coverage report
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: false
```

## Running Tests

Run your tests with:

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=Scrapper

# Run specific test file
pytest Scrapper/tests/unit/test_config_manager.py

# Run tests matching a pattern
pytest -k "config"
```

Following these guidelines will help you create a comprehensive test suite for your scraping modules, ensuring they function correctly and reliably. 