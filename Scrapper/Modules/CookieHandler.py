import os
import time
import logging
from typing import Any, Optional, List, Dict, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Add parent directories to sys.path for imports
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
modules_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(modules_dir)
for path in [modules_dir, root_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)


class CookieHandler:
    """
    Class to handle cookie consent popups across different websites
    with multiple strategies for detection and acceptance.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the cookie handler.
        
        Args:
            logger: Optional logger instance, will create one if not provided
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # Default selectors for cookie consent elements and buttons
        self.consent_element_selectors = [
            # Div containers that might contain cookie consent
            "div.cookie-banner", "div.cookie-consent", "div#cookieConsentPopup",
            "div.cookies", "div.gdpr", "div.consent", "div.privacy-notice",
            "div.popup", "div.modal", "div[class*='cookie']", "div[class*='consent']",
            "div[id*='cookie']", "div[id*='consent']", "div[class*='gdpr']",
            # Button selectors are handled separately
        ]
        
        self.accept_button_selectors = [
            # French buttons (from highest to lowest priority)
            "//button[contains(text(), 'Accepter tout')]",
            "//button[contains(text(), 'Accepter')]",
            "//button[contains(text(), 'J'accepte')]",
            "//a[contains(text(), 'Accepter')]",
            "button.accepter-btn",
            "button.accept-all",
            # English buttons
            "//button[contains(text(), 'Accept all')]",
            "//button[contains(text(), 'Accept cookies')]",
            "//button[contains(text(), 'Accept')]",
            "//button[contains(text(), 'Agree')]",
            "//button[contains(text(), 'Allow')]",
            "//a[contains(text(), 'Accept')]",
            "//a[contains(text(), 'Agree')]",
            # Generic selectors
            "button.accept-cookies",
            "button.accept",
            "button.agree-button",
            "button[id*='accept']",
            "button[class*='accept']",
            "button[class*='cookie']",
            "button[class*='consent']",
            "button[id*='cookie']",
            "button[id*='consent']"
        ]
        
        # JavaScript templates for different cookie handling strategies
        self.js_templates = {
            "set_cookies": """
                // Set common consent cookies
                document.cookie = "cookieConsent=1; path=/; max-age=31536000";
                document.cookie = "cookies_accepted=1; path=/; max-age=31536000";
                document.cookie = "cookie_consent=1; path=/; max-age=31536000";
                document.cookie = "gdpr=accepted; path=/; max-age=31536000";
                return true;
            """,
            
            "find_and_click": """
                // Try to find and click accept buttons
                const acceptButtons = [
                    ...document.querySelectorAll('button'),
                    ...document.querySelectorAll('a.cookie-accept'),
                    ...document.querySelectorAll('[id*="accept"], [class*="accept"]')
                ].filter(el => {
                    if (!el || !el.textContent) return false;
                    const text = el.textContent.toLowerCase();
                    return text.includes('accept') || text.includes('agree') || 
                           text.includes('allow') || text.includes('accepter');
                });
                
                if (acceptButtons.length > 0) {
                    console.log("Found accept button, clicking...");
                    acceptButtons[0].click();
                    return true;
                }
                return false;
            """,
            
            "hide_elements": """
                // Try to hide consent elements
                const cookieElements = document.querySelectorAll(
                    '.cookie-banner, .cookie-consent, #cookieConsentPopup, ' +
                    '.gdpr-banner, .consent-popup, .privacy-notice, ' +
                    '[class*="cookie"], [class*="consent"], [id*="cookie"], [id*="consent"]'
                );
                
                cookieElements.forEach(el => {
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                    el.style.opacity = '0';
                    el.style.pointerEvents = 'none';
                });
                
                // Ensure body is scrollable
                document.body.style.overflow = 'auto';
                document.body.style.position = 'static';
                
                return cookieElements.length > 0;
            """,
            
            "aggressive_cleanup": """
                // Remove modal backdrops and overlays
                document.querySelectorAll('.modal-backdrop, .modal, .overlay, .popup, .consent-dialog').forEach(e => e.remove());
                
                // Ensure body is scrollable
                document.body.style.overflow = 'auto';
                document.body.style.position = 'static';
                document.body.style.paddingRight = '0';
                
                // Remove fixed positioning
                document.querySelectorAll('div[style*="position: fixed"]').forEach(el => {
                    if (el.style.zIndex > 1000) {
                        el.style.display = 'none';
                        el.style.visibility = 'hidden';
                    }
                });
                
                return true;
            """
        }
    
    def detect_consent_elements(self, driver: Any, timeout: float = 0.5) -> List:
        """
        Detect cookie consent elements on the page.
        
        Args:
            driver: Browser driver instance
            timeout: Timeout for element detection in seconds
            
        Returns:
            List of detected cookie consent elements
        """
        cookie_elements = []
        
        # Combined selectors including buttons
        all_selectors = self.consent_element_selectors + [
            selector for selector in self.accept_button_selectors 
            if not selector.startswith("//")  # Skip XPath selectors
        ]
        
        # Scan the DOM for any consent-related elements
        for selector in all_selectors:
            try:
                # Use a very short timeout for checking
                very_short_wait = WebDriverWait(driver, timeout)
                elements = very_short_wait.until(EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, selector)
                ))
                if elements:
                    cookie_elements.extend(elements)
            except Exception:
                continue
                
        # Try XPath selectors separately
        for selector in self.accept_button_selectors:
            if selector.startswith("//"):  # XPath selector
                try:
                    very_short_wait = WebDriverWait(driver, timeout)
                    elements = very_short_wait.until(EC.presence_of_all_elements_located(
                        (By.XPATH, selector)
                    ))
                    if elements:
                        cookie_elements.extend(elements)
                except Exception:
                    continue
        
        return cookie_elements
    
    def apply_javascript_strategy(self, driver: Any, strategy: str) -> bool:
        """
        Apply a JavaScript-based cookie handling strategy.
        
        Args:
            driver: Browser driver instance
            strategy: Strategy name from self.js_templates
            
        Returns:
            Boolean indicating success
        """
        if strategy not in self.js_templates:
            self.logger.warning(f"Unknown strategy: {strategy}")
            return False
            
        try:
            result = driver.execute_script(self.js_templates[strategy])
            self.logger.info(f"Applied JavaScript strategy: {strategy}")
            return bool(result)
        except Exception as e:
            self.logger.debug(f"JavaScript strategy {strategy} failed: {e}")
            return False
    
    def click_accept_buttons(self, driver: Any, wait_time: float = 1.0) -> bool:
        """
        Try to find and click accept buttons with multiple selectors.
        
        Args:
            driver: Browser driver instance
            wait_time: Wait time for each button detection attempt
            
        Returns:
            Boolean indicating if any button was successfully clicked
        """
        for selector in self.accept_button_selectors:
            try:
                by_method = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
                very_short_wait = WebDriverWait(driver, wait_time)
                button = very_short_wait.until(EC.element_to_be_clickable((by_method, selector)))
                
                self.logger.info(f"Found cookie accept button with selector: {selector}")
                
                # Try direct click
                try:
                    button.click()
                    self.logger.info("Clicked cookie accept button")
                    time.sleep(1)  # Brief wait for animations
                    return True
                except Exception:
                    # Try JavaScript click as fallback
                    driver.execute_script("arguments[0].click();", button)
                    self.logger.info("Clicked cookie accept button via JavaScript")
                    time.sleep(1)  # Brief wait for animations
                    return True
            except Exception:
                continue
                
        return False
    
    def handle_consent(self, driver: Any, wait: Optional[WebDriverWait] = None) -> bool:
        """
        Handle cookie consent with multiple strategies, with fallbacks.
        
        Args:
            driver: Browser driver instance
            wait: Optional WebDriverWait instance (will create one if not provided)
            
        Returns:
            Boolean indicating if cookies were accepted or bypassed
        """
        try:
            self.logger.info("Checking for cookie consent popup...")
            
            # Create a wait object if not provided
            if wait is None:
                wait = WebDriverWait(driver, 10)
            
            # Detect cookie consent elements
            cookie_elements = self.detect_consent_elements(driver)
            
            if cookie_elements:
                self.logger.info(f"Found {len(cookie_elements)} cookie-related elements on the page")
                
                # Multi-stage approach with fallbacks
                
                # Stage 1: Set cookies directly via JavaScript
                self.apply_javascript_strategy(driver, "set_cookies")
                
                # Stage 2: Try to find and click accept buttons via JavaScript
                if self.apply_javascript_strategy(driver, "find_and_click"):
                    time.sleep(2)  # Wait for popup to disappear
                    return True
                
                # Stage 3: Try to click buttons directly
                if self.click_accept_buttons(driver):
                    time.sleep(2)  # Wait for popup to disappear
                    return True
                
                # Stage 4: Try to hide consent elements
                self.apply_javascript_strategy(driver, "hide_elements")
                
                # Stage 5: Last resort - aggressive DOM cleanup
                self.apply_javascript_strategy(driver, "aggressive_cleanup")
                
                # Consider handled even if we couldn't click a button
                return True
            else:
                self.logger.info("No cookie consent elements detected")
                return True
                
        except Exception as e:
            self.logger.warning(f"Error handling cookie consent: {e}")
            return False  # Return False to indicate we couldn't handle cookies
    
    def add_consent_element_selector(self, selector: str) -> None:
        """
        Add a custom consent element selector.
        
        Args:
            selector: CSS selector string
        """
        if selector not in self.consent_element_selectors:
            self.consent_element_selectors.append(selector)
    
    def add_accept_button_selector(self, selector: str) -> None:
        """
        Add a custom accept button selector.
        
        Args:
            selector: CSS or XPath selector string
        """
        if selector not in self.accept_button_selectors:
            self.accept_button_selectors.append(selector)


# Standalone function for direct usage without class instantiation
def handle_cookie_consent(driver: Any, wait: Optional[WebDriverWait] = None, 
                         logger: Optional[logging.Logger] = None) -> bool:
    """
    Handle cookie consent popup if present.
    
    Args:
        driver: Browser driver instance
        wait: Optional WebDriverWait instance
        logger: Optional logger instance
        
    Returns:
        Boolean indicating if cookies were accepted or no popup was found
    """
    handler = CookieHandler(logger)
    return handler.handle_consent(driver, wait) 