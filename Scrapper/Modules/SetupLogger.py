import os
import sys
import logging
from typing import List, Optional

# Add parent directories to sys.path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
modules_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(modules_dir)
for path in [modules_dir, root_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)


def setup_directories(directories: List[str]) -> None:
    """
    Creates multiple directory paths if they don't exist.
    
    Args:
        directories: List of directory paths to create
    """
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def setup_logger(
    log_file: str, 
    log_level: int = logging.INFO,
    console_output: bool = True,
    log_format: str = "%(asctime)s - %(levelname)s - %(message)s"
) -> logging.Logger:
    """
    Sets up and configures a logger with file and optional console output.
    
    Args:
        log_file: Path to the log file
        log_level: Logging level (default: INFO)
        console_output: Whether to output logs to console (default: True)
        log_format: Format string for log messages
        
    Returns:
        Configured logger instance
    """
    # Create directory for log file if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Configure basic logging to file
    logging.basicConfig(
        filename=log_file,
        level=log_level,
        format=log_format
    )
    
    # Add console handler if requested
    if console_output:
        console = logging.StreamHandler()
        console.setLevel(log_level)
        console.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(console)
    
    # Return logger instance
    return logging.getLogger()
