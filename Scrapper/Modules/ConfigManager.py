import os
import sys
import json
import logging
import platform
from typing import Any, Dict, List, Optional, Union, Tuple
from pathlib import Path

# Add parent directories to sys.path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
modules_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(modules_dir)
for path in [modules_dir, root_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Default configuration
DEFAULT_CONFIG = {
    # Logging configuration
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(levelname)s - %(message)s",
        "console_output": True,
        "file_output": True,
        "log_dir": "Logs",
    },
    
    # Browser configuration
    "browser": {
        "type": "chrome",
        "headless": False,
        "timeout": 30,
        "page_load_timeout": 90,
        "implicit_wait": 10,
        "user_agent_packages": [
            "selenium", 
            "undetected-chromedriver", 
            "requests", 
            "beautifulsoup4", 
            "urllib3"
        ],
        "browser_args": [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions"
        ],
        "download_directory": os.path.join("Data", "Downloads")
    },
    
    # Cookie handling configuration
    "cookies": {
        "detection_timeout": 0.5,
        "button_wait_time": 1.0,
        "animation_wait_time": 2.0,
        "enable_aggressive_cleanup": True
    },
    
    # Project structure
    "directories": {
        "logs": "Logs",
        "data": "Data",
        "output": "Output",
        "cache": "Cache",
        "temp": "Temp"
    },
    
    # Scraper behavior
    "scraper": {
        "retry_attempts": 3,
        "retry_delay": 2,
        "request_timeout": 30,
        "respect_robots_txt": True,
        "user_agent": None  # Will be generated dynamically
    }
}


class ConfigManager:
    """
    Centralized configuration manager for standardizing options across modules.
    Allows loading from files, environment variables, and programmatic overrides.
    """
    
    _instance = None  # Singleton instance
    
    def __new__(cls, *args, **kwargs):
        """
        Singleton pattern to ensure only one configuration manager exists.
        """
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_file: Optional[str] = None, logger: Optional[logging.Logger] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_file: Optional path to a JSON configuration file
            logger: Optional logger instance
        """
        # Skip initialization if already done (singleton pattern)
        if self._initialized:
            return
            
        self.logger = logger or logging.getLogger(__name__)
        
        # Start with default configuration
        self.config = DEFAULT_CONFIG.copy()
        
        # Add system information
        self._add_system_info()
        
        # Load configuration from file if provided
        if config_file:
            self.load_from_file(config_file)
            
        # Load configuration from environment variables
        self._load_from_env()
        
        # Mark as initialized
        self._initialized = True
    
    def _add_system_info(self) -> None:
        """
        Add system information to the configuration.
        """
        self.config["system"] = {
            "os": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version()
        }
    
    def load_from_file(self, file_path: str) -> bool:
        """
        Load configuration from a JSON file.
        
        Args:
            file_path: Path to the JSON configuration file
            
        Returns:
            Boolean indicating success
        """
        try:
            with open(file_path, 'r') as f:
                file_config = json.load(f)
                
            # Deep merge with existing configuration
            self._deep_merge(self.config, file_config)
            
            self.logger.info(f"Loaded configuration from {file_path}")
            return True
        except Exception as e:
            self.logger.warning(f"Failed to load configuration from {file_path}: {e}")
            return False
    
    def _deep_merge(self, target: Dict, source: Dict) -> None:
        """
        Deep merge source dictionary into target dictionary.
        
        Args:
            target: Target dictionary to merge into
            source: Source dictionary to merge from
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
    
    def _load_from_env(self) -> None:
        """
        Load configuration from environment variables.
        Environment variables should be prefixed with SCRAPER_.
        """
        prefix = "SCRAPER_"
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Remove prefix and split by underscore to get nested keys
                key_parts = key[len(prefix):].lower().split('__')
                
                # Navigate to the correct nested dictionary
                current = self.config
                for part in key_parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                
                # Set the value with appropriate type conversion
                try:
                    # Try to parse as JSON first (for lists, dicts, booleans, etc.)
                    current[key_parts[-1]] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # Fallback to string
                    current[key_parts[-1]] = value
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value by key path.
        
        Args:
            key_path: Dot-separated path to the configuration value
            default: Default value to return if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set a configuration value by key path.
        
        Args:
            key_path: Dot-separated path to the configuration value
            value: Value to set
        """
        keys = key_path.split('.')
        target = self.config
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        # Set the value
        target[keys[-1]] = value
    
    def save_to_file(self, file_path: str) -> bool:
        """
        Save the current configuration to a JSON file.
        
        Args:
            file_path: Path to save the configuration to
            
        Returns:
            Boolean indicating success
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            
            with open(file_path, 'w') as f:
                json.dump(self.config, f, indent=4)
                
            self.logger.info(f"Saved configuration to {file_path}")
            return True
        except Exception as e:
            self.logger.warning(f"Failed to save configuration to {file_path}: {e}")
            return False
    
    def get_logging_config(self) -> Dict[str, Any]:
        """
        Get logging configuration.
        
        Returns:
            Dictionary with logging configuration
        """
        return self.config.get("logging", {})
    
    def get_browser_config(self) -> Dict[str, Any]:
        """
        Get browser configuration.
        
        Returns:
            Dictionary with browser configuration
        """
        return self.config.get("browser", {})
    
    def get_cookie_config(self) -> Dict[str, Any]:
        """
        Get cookie handling configuration.
        
        Returns:
            Dictionary with cookie handling configuration
        """
        return self.config.get("cookies", {})
    
    def get_directory(self, name: str) -> str:
        """
        Get a directory path from configuration.
        
        Args:
            name: Directory name in configuration
            
        Returns:
            Directory path
        """
        directories = self.config.get("directories", {})
        return directories.get(name, name)
    
    def ensure_directory(self, name: str) -> str:
        """
        Get a directory path and ensure it exists.
        
        Args:
            name: Directory name in configuration
            
        Returns:
            Directory path
        """
        directory = self.get_directory(name)
        os.makedirs(directory, exist_ok=True)
        return directory
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get the entire configuration.
        
        Returns:
            Complete configuration dictionary
        """
        return self.config


# Singleton instance for global access
config_manager = ConfigManager()


def get_config() -> ConfigManager:
    """
    Get the global configuration manager instance.
    
    Returns:
        ConfigManager instance
    """
    return config_manager


# Convenience function for direct access to configuration values
def get(key_path: str, default: Any = None) -> Any:
    """
    Get a configuration value by key path.
    
    Args:
        key_path: Dot-separated path to the configuration value
        default: Default value to return if key not found
        
    Returns:
        Configuration value or default
    """
    return config_manager.get(key_path, default) 