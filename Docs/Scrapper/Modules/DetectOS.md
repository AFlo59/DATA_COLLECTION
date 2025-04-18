# DetectOS Module

## Overview

The `DetectOS` module provides cross-platform operating system detection and system information retrieval functions for web scraping applications. It simplifies the process of adapting scripts to different operating systems and retrieving system-specific information needed for browser automation.

## Features

- **OS Detection**: Identify the current operating system (Windows, Linux, macOS)
- **System Information**: Retrieve detailed information about the operating system
- **Command Execution**: Cross-platform command execution utilities
- **Command Adaptation**: Adapt commands based on the detected operating system
- **Chrome Location**: Find Chrome executable paths on different operating systems

## Core Functions

### OS Detection

- `get_os_info()`: Get detailed information about the operating system
- `is_windows()`: Check if the current OS is Windows
- `is_linux()`: Check if the current OS is Linux
- `is_macos()`: Check if the current OS is macOS

### Command Execution

- `execute_command(command)`: Execute a system command in a cross-platform manner
- `adapt_command(base_command, args)`: Adapt a command based on the current operating system

### Browser-Related Functions

- `get_chrome_executable()`: Get the path to the Chrome executable based on the current OS

## How It Works

1. **OS Identification**: The module uses Python's `platform` module to detect the operating system.
2. **Command Adaptation**: Commands are adapted to be compatible with the detected operating system.
3. **Path Resolution**: System-specific file paths are resolved based on the OS.
4. **Process Execution**: Commands are executed in a safe and cross-platform manner.

## Usage Examples

### Basic OS Detection

```python
from Scrapper.Modules.DetectOS import is_windows, is_linux, is_macos, get_os_info

# Get detailed OS information
os_info = get_os_info()
print(f"Operating System: {os_info['system']} {os_info['release']}")
print(f"Version: {os_info['version']}")
print(f"Machine: {os_info['machine']}")

# Check for specific operating systems
if is_windows():
    print("Running on Windows")
elif is_linux():
    print("Running on Linux")
elif is_macos():
    print("Running on macOS")
else:
    print("Running on an unrecognized operating system")
```

### Command Execution

```python
from Scrapper.Modules.DetectOS import execute_command, adapt_command

# Execute a command and get its output
command = ["python", "--version"]
success, stdout, stderr = execute_command(command)

if success:
    print(f"Python version: {stdout}")
else:
    print(f"Error: {stderr}")

# Adapt a command for the current OS
# e.g. 'ls' on Unix becomes 'dir' on Windows
adapted_command = adapt_command("ls", ["-la"])
success, stdout, stderr = execute_command(adapted_command)

if success:
    print("Directory listing:")
    print(stdout)
else:
    print(f"Error listing directory: {stderr}")
```

### Finding Chrome Installation

```python
from Scrapper.Modules.DetectOS import get_chrome_executable

# Get the path to the Chrome executable
chrome_path = get_chrome_executable()

if chrome_path:
    print(f"Chrome executable found at: {chrome_path}")
else:
    print("Chrome executable not found")
```

### Integration with BrowserSetup

```python
from Scrapper.Modules.DetectOS import get_chrome_executable, get_os_info
from Scrapper.Modules.BrowserSetup import BrowserSetup
from Scrapper.Modules.SetupLogger import get_logger

# Get a logger instance
logger = get_logger("browser_setup_example")

# Log OS information
os_info = get_os_info()
logger.info(f"Running on {os_info['system']} {os_info['release']}")

# Check if Chrome is installed
chrome_path = get_chrome_executable()
if chrome_path:
    logger.info(f"Chrome executable found at: {chrome_path}")
else:
    logger.warning("Chrome executable not found, may need to install Chrome")
    
# Initialize browser setup
browser_setup = BrowserSetup(logger)
try:
    driver = browser_setup.get_driver()
    # Use the driver...
finally:
    browser_setup.close()
```

### Custom Command Execution Based on OS

```python
from Scrapper.Modules.DetectOS import is_windows, is_linux, is_macos, execute_command
import os

def clean_temp_files(directory):
    """Clean temporary files in a directory using OS-specific commands."""
    if is_windows():
        # Windows command to delete temporary files
        command = ["del", "/Q", os.path.join(directory, "*.tmp")]
    elif is_linux() or is_macos():
        # Unix command to delete temporary files
        command = ["rm", "-f", os.path.join(directory, "*.tmp")]
    else:
        raise OSError("Unsupported operating system")
    
    success, stdout, stderr = execute_command(command)
    if success:
        print(f"Successfully cleaned temporary files in {directory}")
    else:
        print(f"Failed to clean temporary files: {stderr}")

# Usage
clean_temp_files("./temp")
```

### Comprehensive System Information Logger

```python
from Scrapper.Modules.DetectOS import get_os_info, get_chrome_executable, execute_command
from Scrapper.Modules.SetupLogger import get_logger
import platform
import os

def log_system_info():
    """Log comprehensive system information for debugging."""
    logger = get_logger("system_info")
    
    # Get basic OS info
    os_info = get_os_info()
    logger.info(f"Operating System: {os_info['system']} {os_info['release']}")
    logger.info(f"Version: {os_info['version']}")
    logger.info(f"Machine: {os_info['machine']}")
    logger.info(f"Processor: {os_info['processor']}")
    
    # Python information
    logger.info(f"Python Version: {platform.python_version()}")
    logger.info(f"Python Implementation: {platform.python_implementation()}")
    logger.info(f"Python Compiler: {platform.python_compiler()}")
    
    # Browser information
    chrome_path = get_chrome_executable()
    if chrome_path:
        logger.info(f"Chrome executable: {chrome_path}")
        # Try to get Chrome version
        if os_info['system'] == "Windows":
            cmd = [chrome_path, "--version"]
        else:
            cmd = ["--version"]
        success, stdout, stderr = execute_command(cmd)
        if success:
            logger.info(f"Chrome version: {stdout.strip()}")
    else:
        logger.warning("Chrome executable not found")
    
    # Network information (basic)
    try:
        import socket
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        logger.info(f"Hostname: {hostname}")
        logger.info(f"IP Address: {ip_address}")
    except Exception as e:
        logger.warning(f"Could not get network information: {e}")
    
    # Environment variables
    logger.info("Relevant Environment Variables:")
    for var in ['PATH', 'PYTHONPATH', 'APPDATA', 'LOCALAPPDATA', 'HOME', 'USER', 'LANG']:
        if var in os.environ:
            logger.info(f"  {var}: {os.environ[var]}")

# Usage
log_system_info()
```

## Best Practices

1. **Error Handling**: Always check the return values of functions that might fail
2. **Logging**: Log OS information for debugging cross-platform issues
3. **Command Execution**: Use the provided functions rather than direct OS calls
4. **Fallbacks**: Implement fallbacks for when specific OS features are not available
5. **Testing**: Test your code on all target operating systems

## Troubleshooting

- **Command Execution Failures**: Check permissions and command availability on the current OS
- **Path Issues**: Ensure paths use the correct separators for the current OS
- **Chrome Not Found**: Check that Chrome is installed in standard locations or specify a custom path
- **OS Detection Issues**: For uncommon OS versions, implement custom detection logic 