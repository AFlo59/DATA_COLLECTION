import logging
import os
import time
import sys
from typing import Optional, Dict, Any, Tuple, List

# Add parent directories to sys.path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
modules_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(modules_dir)
for path in [modules_dir, root_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Import browser driver libraries with fallbacks
SELENIUM_AVAILABLE = False
UNDETECTED_AVAILABLE = False
WEBDRIVER_MANAGER_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    SELENIUM_AVAILABLE = True
except ImportError:
    pass

# First try undetected_chromedriver
try:
    import undetected_chromedriver as uc
    UNDETECTED_AVAILABLE = True
except ImportError:
    pass

# Try webdriver_manager as fallback
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    pass

# Import internal modules with error handling
try:
    from Scrapper.Modules.DetectOS import get_os_info, get_chrome_executable
    from Scrapper.Modules.DetectPackages import get_user_agent, detect_chrome_version
except ImportError:
    try:
        from Modules.DetectOS import get_os_info, get_chrome_executable
        from Modules.DetectPackages import get_user_agent, detect_chrome_version
    except ImportError:
        # Define minimal fallbacks if modules not available
        def get_os_info() -> Dict[str, str]:
            import platform
            return {"system": platform.system(), "release": platform.release()}
        
        def get_chrome_executable() -> Optional[str]:
            return None
        
        def get_user_agent() -> str:
            import platform
            return f"CustomScraper/1.0 ({platform.system()} {platform.release()})"
        
        def detect_chrome_version() -> Optional[int]:
            return None


class BrowserSetup:
    """
    Class to manage browser setup with fallbacks and error handling
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the browser setup manager
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        self.browser_type = "chrome"  # Currently only Chrome is supported
        self.driver = None
        
        # Check available browser driver libraries
        self._check_available_drivers()
    
    def _check_available_drivers(self) -> None:
        """Check and log available browser driver libraries"""
        drivers = []
        if UNDETECTED_AVAILABLE:
            drivers.append("undetected_chromedriver")
        if SELENIUM_AVAILABLE:
            drivers.append("selenium")
        if WEBDRIVER_MANAGER_AVAILABLE:
            drivers.append("webdriver_manager")
            
        self.logger.info(f"Available browser drivers: {', '.join(drivers) if drivers else 'None'}")

    def setup_chrome_options(self) -> Any:
        """
        Set up Chrome options with appropriate settings
        
        Returns:
            Chrome options object (either selenium.webdriver.chrome.options.Options or uc.ChromeOptions)
        """
        if UNDETECTED_AVAILABLE:
            options = uc.ChromeOptions()
        elif SELENIUM_AVAILABLE:
            options = ChromeOptions()
        else:
            self.logger.error("No browser driver libraries available")
            raise ImportError("No browser driver libraries available")
        
        # Common options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')
        
        # Add user agent
        user_agent = get_user_agent()
        options.add_argument(f"user-agent={user_agent}")
        
        return options

    def create_driver(self) -> Any:
        """
        Create and configure a browser driver with fallbacks
        
        Returns:
            Configured browser driver instance
        """
        options = self.setup_chrome_options()
        chrome_version = detect_chrome_version()
        
        # Try undetected_chromedriver first (most reliable for avoiding detection)
        if UNDETECTED_AVAILABLE:
            try:
                self.logger.info("Trying undetected_chromedriver...")
                if chrome_version:
                    driver = uc.Chrome(options=options, version_main=chrome_version, suppress_welcome=True)
                else:
                    driver = uc.Chrome(options=options, suppress_welcome=True)
                self.logger.info("Successfully initialized undetected_chromedriver")
                return driver
            except Exception as e:
                self.logger.warning(f"Failed to initialize undetected_chromedriver: {e}")
        
        # Fall back to selenium with webdriver_manager
        if SELENIUM_AVAILABLE and WEBDRIVER_MANAGER_AVAILABLE:
            try:
                self.logger.info("Trying selenium with webdriver_manager...")
                service = ChromeService(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
                self.logger.info("Successfully initialized selenium with webdriver_manager")
                return driver
            except Exception as e:
                self.logger.warning(f"Failed to initialize selenium with webdriver_manager: {e}")
        
        # Last resort: selenium with manually specified chromedriver
        if SELENIUM_AVAILABLE:
            try:
                self.logger.info("Trying selenium with system ChromeDriver...")
                chrome_executable = get_chrome_executable()
                if chrome_executable:
                    service = ChromeService(executable_path=chrome_executable)
                    driver = webdriver.Chrome(service=service, options=options)
                    self.logger.info("Successfully initialized selenium with system ChromeDriver")
                    return driver
            except Exception as e:
                self.logger.warning(f"Failed to initialize selenium with system ChromeDriver: {e}")
        
        # If all else fails
        raise RuntimeError("Failed to initialize any browser driver")

    def get_driver(self) -> Any:
        """
        Get or create a browser driver instance
        
        Returns:
            Browser driver instance
        """
        if self.driver is None:
            self.driver = self.create_driver()
        return self.driver
    
    def close(self) -> None:
        """Close and clean up the browser driver"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Browser driver closed")
            except Exception as e:
                self.logger.warning(f"Error closing browser driver: {e}")
            finally:
                self.driver = None


def get_browser_driver(logger: Optional[logging.Logger] = None) -> Tuple[Any, bool]:
    """
    Helper function to get a browser driver with setup handled
    
    Args:
        logger: Optional logger instance
    
    Returns:
        Tuple containing (driver instance, is_undetected_chromedriver)
    """
    setup = BrowserSetup(logger)
    driver = setup.get_driver()
    is_undetected = UNDETECTED_AVAILABLE and isinstance(driver, uc.Chrome)
    return driver, is_undetected 