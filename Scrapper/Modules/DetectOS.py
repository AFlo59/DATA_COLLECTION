import os
import platform
import subprocess
import sys
from typing import List, Dict, Optional, Tuple, Any

# Add parent directories to sys.path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
modules_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(modules_dir)
for path in [modules_dir, root_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)


def get_os_info() -> Dict[str, str]:
    """
    Gets detailed information about the operating system.
    
    Returns:
        Dictionary containing OS information
    """
    os_info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version()
    }
    
    # Add distro info for Linux systems
    if os_info["system"] == "Linux":
        try:
            import distro
            os_info["distro"] = distro.name(pretty=True)
        except ImportError:
            try:
                # Alternative method if distro module not available
                with open("/etc/os-release") as f:
                    lines = f.readlines()
                    for line in lines:
                        if line.startswith("PRETTY_NAME="):
                            os_info["distro"] = line.split("=")[1].strip().strip('"')
                            break
            except Exception:
                os_info["distro"] = "Unknown Linux Distribution"
    
    return os_info


def is_windows() -> bool:
    """Check if the current OS is Windows."""
    return platform.system() == "Windows"


def is_linux() -> bool:
    """Check if the current OS is Linux."""
    return platform.system() == "Linux"


def is_macos() -> bool:
    """Check if the current OS is macOS."""
    return platform.system() == "Darwin"


def execute_command(command: List[str]) -> Tuple[bool, str, str]:
    """
    Executes a system command in a cross-platform manner.
    
    Args:
        command: List of command parts to execute
        
    Returns:
        Tuple containing (success_status, stdout, stderr)
    """
    try:
        # Use shell=True for Windows when needed
        use_shell = is_windows() and len(command) == 1
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=use_shell,
            universal_newlines=True
        )
        
        stdout, stderr = process.communicate()
        success = process.returncode == 0
        
        return success, stdout, stderr
    
    except Exception as e:
        return False, "", str(e)


def adapt_command(base_command: str, args: List[str] = None) -> List[str]:
    """
    Adapts a command based on the current operating system.
    
    Args:
        base_command: Base command to execute
        args: Arguments to pass to the command
        
    Returns:
        Command list adapted for the current OS
    """
    if args is None:
        args = []
    
    system = platform.system()
    
    if system == "Windows":
        # Special case for certain Windows commands
        if base_command == "ls":
            return ["dir"] + args
        elif base_command == "rm":
            return ["del" if len(args) == 1 else "rmdir", "/Q" if "/f" in args else ""] + [a for a in args if a != "/f"]
        elif base_command == "grep":
            return ["findstr"] + args
        else:
            return [base_command] + args
    else:
        # Linux/macOS
        return [base_command] + args


def get_chrome_executable() -> Optional[str]:
    """
    Gets the path to the Chrome executable based on the current OS.
    
    Returns:
        Path to Chrome executable or None if not found
    """
    if is_windows():
        locations = [
            os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google\\Chrome\\Application\\chrome.exe")
        ]
        for loc in locations:
            if os.path.exists(loc):
                return loc
    
    elif is_linux():
        for cmd in ["google-chrome", "google-chrome-stable", "chrome", "chromium-browser", "chromium"]:
            try:
                # Check if executable exists in PATH
                result, _, _ = execute_command(["which", cmd])
                if result:
                    return cmd
            except Exception:
                continue
    
    elif is_macos():
        locations = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        ]
        for loc in locations:
            if os.path.exists(os.path.expanduser(loc)):
                return loc
    
    return None
