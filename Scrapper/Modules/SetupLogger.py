import os
import sys
import logging
from typing import List, Optional, Dict, Any

# Add parent directories to sys.path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
modules_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(modules_dir)
for path in [modules_dir, root_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Try to import ConfigManager
try:
    from Scrapper.Modules.ConfigManager import get_config
except ImportError:
    try:
        from Modules.ConfigManager import get_config
    except ImportError:
        # Define minimal fallback if ConfigManager is not available
        class DummyConfigManager:
            def get_logging_config(self):
                return {
                    "level": "INFO",
                    "format": "%(asctime)s - %(levelname)s - %(message)s",
                    "console_output": True,
                    "file_output": True,
                    "log_dir": "Logs",
                    "clean_logs": True
                }
            
            def get_directory(self, name):
                return name
            
            def ensure_directory(self, name):
                os.makedirs(name, exist_ok=True)
                return name
                
            def get(self, key_path, default=None):
                # Simple parsing for "logging.level" style paths
                if key_path == "logging.level":
                    return "INFO"
                elif key_path == "logging.format":
                    return "%(asctime)s - %(levelname)s - %(message)s"
                elif key_path == "logging.clean_logs":
                    return True
                return default
        
        def get_config():
            return DummyConfigManager()


def setup_directories(directories: List[str]) -> None:
    """
    Creates multiple directory paths if they don't exist.
    
    Args:
        directories: List of directory paths to create
    """
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def clean_log_file(log_file: str) -> bool:
    """
    Cleans an existing log file by removing its contents.
    
    Args:
        log_file: Path to the log file to clean
        
    Returns:
        Boolean indicating whether the file was cleaned
    """
    try:
        if os.path.exists(log_file):
            # Open the file in write mode, which truncates it to zero length
            with open(log_file, 'w') as f:
                f.write(f"Log file cleaned at {logging.Formatter().formatTime(logging.LogRecord('', 0, '', 0, '', [], None))}\n")
            return True
        return False
    except Exception as e:
        print(f"Error cleaning log file {log_file}: {e}")
        return False


def setup_logger(
    log_file: str, 
    log_level: Optional[int] = None,
    console_output: Optional[bool] = None,
    log_format: Optional[str] = None,
    clean_logs: Optional[bool] = None
) -> logging.Logger:
    """
    Sets up and configures a logger with file and optional console output.
    Uses configuration from ConfigManager when parameters are not provided.
    
    Args:
        log_file: Path to the log file
        log_level: Logging level (default: from config)
        console_output: Whether to output logs to console (default: from config)
        log_format: Format string for log messages (default: from config)
        clean_logs: Whether to clean existing log files (default: from config)
        
    Returns:
        Configured logger instance
    """
    # Get configuration manager
    config = get_config()
    
    # Get logging configuration with defaults
    logging_config = config.get_logging_config()
    
    # Use provided parameters or fall back to configuration
    if log_level is None:
        level_str = logging_config.get("level", "INFO")
        log_level = getattr(logging, level_str.upper(), logging.INFO)
    
    if console_output is None:
        console_output = logging_config.get("console_output", True)
    
    if log_format is None:
        log_format = logging_config.get("format", "%(asctime)s - %(levelname)s - %(message)s")
    
    if clean_logs is None:
        clean_logs = logging_config.get("clean_logs", True)
    
    # Create directory for log file if it doesn't exist
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)
    
    # Clean log file if it exists and clean_logs is True
    if clean_logs:
        clean_log_file(log_file)
    
    # Get a logger instance
    logger = logging.getLogger()
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Set the overall log level
    logger.setLevel(log_level)
    
    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(file_handler)
    
    # Add console handler if requested
    if console_output:
        console = logging.StreamHandler()
        console.setLevel(log_level)
        console.setFormatter(logging.Formatter(log_format))
        logger.addHandler(console)
    
    return logger


def get_logger(name: str, log_dir: Optional[str] = None, clean_logs: Optional[bool] = None) -> logging.Logger:
    """
    Gets a configured logger with automatic file path generation.
    
    Args:
        name: Logger name, also used for log file naming
        log_dir: Optional custom log directory (default: from config)
        clean_logs: Whether to clean existing log files (default: from config)
        
    Returns:
        Configured logger instance
    """
    # Get configuration manager
    config = get_config()
    
    # Use provided log directory or get from config
    if log_dir is None:
        log_dir = config.get_directory("logs")
    
    # Get clean_logs setting from config if not provided
    if clean_logs is None:
        clean_logs = config.get("logging.clean_logs", True)
    
    # Ensure directory exists
    os.makedirs(log_dir, exist_ok=True)
    
    # Create log file path
    log_file = os.path.join(log_dir, f"{name}.log")
    
    # Set up logger with clean_logs parameter
    return setup_logger(log_file, clean_logs=clean_logs)


def get_module_logger(clean_logs: Optional[bool] = None) -> logging.Logger:
    """
    Gets a logger for the current module with automatic naming.
    
    Args:
        clean_logs: Whether to clean existing log files (default: from config)
        
    Returns:
        Configured logger instance for current module
    """
    # Get module name from caller's module
    import inspect
    caller_frame = inspect.stack()[1]
    module = inspect.getmodule(caller_frame[0])
    module_name = module.__name__.split('.')[-1] if module else "unknown"
    
    return get_logger(module_name, clean_logs=clean_logs)
