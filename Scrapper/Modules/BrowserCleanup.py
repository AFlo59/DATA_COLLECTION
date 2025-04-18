import os
import sys
import time
import logging
import atexit
import weakref
from typing import Any, Optional, List, Dict, Callable, Set

# Add parent directories to sys.path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
modules_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(modules_dir)
for path in [modules_dir, root_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Global registry to track active browser instances
_active_browsers = set()

# Register cleanup function at exit to ensure all browsers are closed
@atexit.register
def _cleanup_all_browsers():
    """
    Clean up any active browsers during application exit.
    This function is automatically called when Python exits.
    """
    global _active_browsers
    for browser in list(_active_browsers):
        try:
            close_browser(browser)
        except Exception:
            pass
    _active_browsers.clear()


class BrowserCleanup:
    """
    Class to manage browser cleanup and proper closure.
    Provides methods to ensure browsers are properly closed
    and resources are released.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the browser cleanup manager.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        self.managed_browsers = set()
        
        # Register cleanup function to be called at exit
        atexit.register(self._cleanup_managed_browsers)
    
    def _cleanup_managed_browsers(self):
        """
        Clean up all managed browsers when instance is destroyed
        or at program exit.
        """
        for browser in list(self.managed_browsers):
            try:
                self.close_browser(browser)
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error during browser cleanup: {e}")
    
    def register_browser(self, browser: Any) -> None:
        """
        Register a browser instance for managed cleanup.
        
        Args:
            browser: Browser driver instance to manage
        """
        if browser is not None:
            self.managed_browsers.add(browser)
            global _active_browsers
            _active_browsers.add(browser)
            if self.logger:
                self.logger.debug(f"Registered browser instance for cleanup: {id(browser)}")
    
    def close_browser(self, browser: Any) -> bool:
        """
        Close a browser instance with multiple fallback approaches.
        
        Args:
            browser: Browser driver instance to close
            
        Returns:
            Boolean indicating success
        """
        if browser is None:
            return False
            
        success = False
        error_message = None
        
        # Method 1: Try driver.quit()
        try:
            if self.logger:
                self.logger.info("Closing browser with driver.quit()...")
            browser.quit()
            time.sleep(1)  # Brief pause for cleanup
            success = True
            if self.logger:
                self.logger.info("Browser successfully closed with driver.quit()")
        except Exception as e:
            error_message = f"Error in driver.quit(): {e}"
            if self.logger:
                self.logger.warning(error_message)
            
        # Method 2: If driver.quit() failed and browser has close() method, try it
        if not success:
            try:
                if hasattr(browser, 'close'):
                    if self.logger:
                        self.logger.info("Trying browser.close() method...")
                    browser.close()
                    time.sleep(1)  # Brief pause for cleanup
                    success = True
                    if self.logger:
                        self.logger.info("Browser successfully closed with browser.close()")
            except Exception as e:
                error_message = f"Error in browser.close(): {e}"
                if self.logger:
                    self.logger.warning(error_message)
        
        # Method 3: Try special handling for undetected_chromedriver
        if not success:
            try:
                if hasattr(browser, 'stop'):
                    if self.logger:
                        self.logger.info("Trying specialized browser.stop() method...")
                    browser.stop()
                    time.sleep(1)  # Brief pause for cleanup
                    success = True
                    if self.logger:
                        self.logger.info("Browser successfully closed with browser.stop()")
            except Exception as e:
                error_message = f"Error in browser.stop(): {e}"
                if self.logger:
                    self.logger.warning(error_message)
        
        # Remove from managed browsers regardless of success
        try:
            self.managed_browsers.discard(browser)
            global _active_browsers
            _active_browsers.discard(browser)
        except Exception:
            pass
            
        return success
    
    def force_kill_processes(self, process_names: Optional[List[str]] = None) -> bool:
        """
        Force kill browser processes as a last resort.
        
        Args:
            process_names: Optional list of process names to kill.
                           Default includes common browser processes.
            
        Returns:
            Boolean indicating if any processes were terminated
        """
        if process_names is None:
            process_names = ['chrome.exe', 'chromedriver.exe', 'firefox.exe', 'geckodriver.exe']
            
        success = False
        
        if os.name == 'nt':  # Windows
            try:
                if self.logger:
                    self.logger.info("Attempting to forcefully terminate browser processes...")
                
                for process in process_names:
                    os.system(f"taskkill /F /IM {process} /T")
                
                success = True
                if self.logger:
                    self.logger.info("Browser processes terminated")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Failed to terminate browser processes: {e}")
        
        elif os.name == 'posix':  # Linux/macOS
            try:
                if self.logger:
                    self.logger.info("Attempting to forcefully terminate browser processes...")
                
                for process in process_names:
                    os.system(f"pkill -f {process}")
                
                success = True
                if self.logger:
                    self.logger.info("Browser processes terminated")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Failed to terminate browser processes: {e}")
                    
        return success
    
    def close_all_browsers(self) -> bool:
        """
        Close all managed browser instances.
        
        Returns:
            Boolean indicating overall success
        """
        if not self.managed_browsers:
            return True
            
        success = True
        
        for browser in list(self.managed_browsers):
            if not self.close_browser(browser):
                success = False
                
        # If any browsers failed to close properly, try force killing processes
        if not success:
            self.force_kill_processes()
            
        return success


# Standalone functions for direct usage without class instantiation

def register_browser(browser: Any, logger: Optional[logging.Logger] = None) -> None:
    """
    Register a browser instance for automatic cleanup at exit.
    
    Args:
        browser: Browser driver instance
        logger: Optional logger instance
    """
    global _active_browsers
    if browser is not None:
        _active_browsers.add(browser)
        if logger:
            logger.debug(f"Registered browser instance for cleanup: {id(browser)}")


def close_browser(browser: Any, logger: Optional[logging.Logger] = None) -> bool:
    """
    Close a browser instance with multiple fallback methods.
    
    Args:
        browser: Browser driver instance
        logger: Optional logger instance
        
    Returns:
        Boolean indicating success
    """
    if browser is None:
        return False
        
    success = False
    
    # Method 1: Try driver.quit()
    try:
        if logger:
            logger.info("Closing browser with driver.quit()...")
        browser.quit()
        time.sleep(1)  # Brief pause for cleanup
        success = True
        if logger:
            logger.info("Browser successfully closed with driver.quit()")
    except Exception as e:
        if logger:
            logger.warning(f"Error in driver.quit(): {e}")
        
    # Method 2: If driver.quit() failed, try browser.close()
    if not success:
        try:
            if hasattr(browser, 'close'):
                if logger:
                    logger.info("Trying browser.close() method...")
                browser.close()
                time.sleep(1)  # Brief pause for cleanup
                success = True
                if logger:
                    logger.info("Browser successfully closed with browser.close()")
        except Exception as e:
            if logger:
                logger.warning(f"Error in browser.close(): {e}")
    
    # Method 3: Try special handling for undetected_chromedriver
    if not success:
        try:
            if hasattr(browser, 'stop'):
                if logger:
                    logger.info("Trying specialized browser.stop() method...")
                browser.stop()
                time.sleep(1)  # Brief pause for cleanup
                success = True
                if logger:
                    logger.info("Browser successfully closed with browser.stop()")
        except Exception as e:
            if logger:
                logger.warning(f"Error in browser.stop(): {e}")
    
    # Remove from global registry
    global _active_browsers
    try:
        _active_browsers.discard(browser)
    except Exception:
        pass
        
    return success


def force_kill_browser_processes(logger: Optional[logging.Logger] = None) -> bool:
    """
    Force kill browser processes as a last resort.
    
    Args:
        logger: Optional logger instance
        
    Returns:
        Boolean indicating success
    """
    success = False
    process_names = ['chrome.exe', 'chromedriver.exe', 'firefox.exe', 'geckodriver.exe']
    
    if os.name == 'nt':  # Windows
        try:
            if logger:
                logger.info("Attempting to forcefully terminate browser processes...")
            
            for process in process_names:
                os.system(f"taskkill /F /IM {process} /T")
            
            success = True
            if logger:
                logger.info("Browser processes terminated")
        except Exception as e:
            if logger:
                logger.warning(f"Failed to terminate browser processes: {e}")
    
    elif os.name == 'posix':  # Linux/macOS
        try:
            if logger:
                logger.info("Attempting to forcefully terminate browser processes...")
            
            for process in process_names:
                os.system(f"pkill -f {process}")
            
            success = True
            if logger:
                logger.info("Browser processes terminated")
        except Exception as e:
            if logger:
                logger.warning(f"Failed to terminate browser processes: {e}")
                
    return success


def ensure_browser_cleanup(browser: Any, 
                          logger: Optional[logging.Logger] = None, 
                          force_kill: bool = True) -> bool:
    """
    Ensure complete browser cleanup with all available methods.
    
    Args:
        browser: Browser driver instance
        logger: Optional logger instance
        force_kill: Whether to try force killing processes if normal methods fail
        
    Returns:
        Boolean indicating success
    """
    success = close_browser(browser, logger)
    
    if not success and force_kill:
        success = force_kill_browser_processes(logger)
        
    return success 