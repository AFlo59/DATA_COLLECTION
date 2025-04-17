import platform
import re
import subprocess
import sys
import os
from typing import Dict, List, Optional, Union, Tuple
import importlib.metadata

# Add parent directories to sys.path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
modules_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(modules_dir)
for path in [modules_dir, root_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)


def detect_installed_packages(package_names: List[str]) -> Dict[str, str]:
    """
    Detects installed packages and their versions.
    
    Args:
        package_names: List of package names to detect
        
    Returns:
        Dictionary of package names and their versions
    """
    versions = {}
    
    for pkg in package_names:
        try:
            # Try to get version using importlib.metadata (Python 3.8+)
            versions[pkg] = importlib.metadata.version(pkg)
        except Exception:
            try:
                # Alternative method
                module = __import__(pkg)
                if hasattr(module, '__version__'):
                    versions[pkg] = module.__version__
                elif hasattr(module, 'version'):
                    versions[pkg] = module.version
                else:
                    # Try to get version using pkg_resources as last resort
                    try:
                        import pkg_resources
                        versions[pkg] = pkg_resources.get_distribution(pkg).version
                    except Exception:
                        versions[pkg] = "unknown"
            except Exception:
                versions[pkg] = "unknown"
    
    return versions


def detect_chrome_version() -> Optional[int]:
    """
    Detects the installed Chrome browser's major version.
    
    Returns:
        Major version number as integer, or None if not detected
    """
    try:
        from Scrapper.Modules.DetectOS import is_windows, is_linux, is_macos, execute_command, get_chrome_executable
    except ImportError:
        try:
            from Modules.DetectOS import is_windows, is_linux, is_macos, execute_command, get_chrome_executable
        except ImportError:
            # Minimal fallback if DetectOS module is not available
            def is_windows(): return platform.system() == "Windows"
            def is_linux(): return platform.system() == "Linux"
            def is_macos(): return platform.system() == "Darwin"
            def execute_command(cmd): return False, "", ""
            def get_chrome_executable(): return None
    
    chrome_path = get_chrome_executable()
    
    if not chrome_path:
        return None
    
    try:
        if is_windows():
            # Windows method
            cmd = [chrome_path, "--version"]
            success, stdout, _ = execute_command(cmd)
            if success:
                match = re.search(r"(\d+)\.", stdout)
                if match:
                    return int(match.group(1))
                
        elif is_linux() or is_macos():
            # Linux/macOS method
            cmd = [chrome_path, "--version"]
            success, stdout, _ = execute_command(cmd)
            if success:
                match = re.search(r"(\d+)\.", stdout)
                if match:
                    return int(match.group(1))
    
    except Exception:
        pass
    
    return None


def get_user_agent(include_packages: List[str] = None) -> str:
    """
    Generates a customized User-Agent string with system and package information.
    
    Args:
        include_packages: Optional list of package names to include in the UA string
        
    Returns:
        Formatted User-Agent string
    """
    # Default packages to include if none specified
    if include_packages is None:
        include_packages = [
            "selenium", 
            "undetected-chromedriver", 
            "requests", 
            "beautifulsoup4", 
            "urllib3"
        ]
    
    # Get OS information
    os_info = f"{platform.system()} {platform.release()}"
    
    # Get package versions
    versions = detect_installed_packages(include_packages)
    
    # Format the User-Agent string
    pkg_string = "; ".join(f"{k}/{v}" for k, v in versions.items())
    user_agent = f"CustomScraper/1.0 ({os_info}); {pkg_string}"
    
    return user_agent


def check_dependency_compatibility() -> Tuple[bool, List[str]]:
    """
    Checks compatibility between installed packages.
    
    Returns:
        Tuple containing:
            - Boolean indicating overall compatibility
            - List of warning messages for incompatible packages
    """
    warnings = []
    is_compatible = True
    
    # Get versions of key packages
    versions = detect_installed_packages([
        "selenium", 
        "undetected-chromedriver", 
        "webdriver_manager",
        "urllib3",
        "requests"
    ])
    
    # Check selenium and undetected-chromedriver compatibility
    if "selenium" in versions and "undetected-chromedriver" in versions:
        selenium_version = versions["selenium"]
        uc_version = versions["undetected-chromedriver"]
        
        # Convert version strings to components
        try:
            selenium_major = int(selenium_version.split('.')[0])
            
            # Known compatibility issues
            if selenium_major >= 4 and uc_version < "3.0.0":
                warnings.append(f"undetected-chromedriver {uc_version} may not be compatible with selenium {selenium_version}")
                is_compatible = False
        except Exception:
            # If we can't parse versions, assume compatible
            pass
    
    # Check urllib3 and requests compatibility
    if "urllib3" in versions and "requests" in versions:
        urllib3_version = versions["urllib3"]
        requests_version = versions["requests"]
        
        try:
            urllib3_major = int(urllib3_version.split('.')[0])
            if urllib3_major >= 2 and requests_version < "2.31.0":
                warnings.append(f"urllib3 {urllib3_version} may not be compatible with requests {requests_version}")
                is_compatible = False
        except Exception:
            pass
    
    return is_compatible, warnings
