#!/usr/bin/env python3
"""
Launcher script for the condition scraper.
This script ensures the proper Python path setup before running the scraper.
"""

import os
import sys
import platform
import subprocess

# Ensure correct Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

def install_missing_packages():
    """Install missing packages from requirements.txt."""
    try:
        requirements_path = os.path.join(current_dir, 'requirements.txt')
        if os.path.exists(requirements_path):
            print("Checking for missing dependencies...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path])
            print("Dependencies installed successfully.")
        else:
            print("requirements.txt not found.")
    except Exception as e:
        print(f"Error installing dependencies: {e}")

def main():
    """Main function to set up environment and run the scraper."""
    print(f"Running on {platform.system()} {platform.release()}")
    print(f"Python version: {platform.python_version()}")
    print(f"Current directory: {current_dir}")
    
    # Check for any missing packages
    install_missing_packages()
    
    try:
        # Import the scraper module
        print("Importing scraper module...")
        from Scrapper.ConditionScrapper import main as scraper_main
        
        # Run the scraper
        print("Starting the scraper...")
        scraper_main()
    except ImportError as e:
        print(f"Error importing the scraper module: {e}")
        print("\nTrying alternative import method...")
        
        # Try running the script directly as a fallback
        scraper_path = os.path.join(current_dir, 'Scrapper', 'ConditionScrapperV2.py')
        if os.path.exists(scraper_path):
            print(f"Running script directly: {scraper_path}")
            # Run the script with the current Python interpreter
            result = subprocess.run([sys.executable, scraper_path], 
                                   stderr=subprocess.PIPE, 
                                   stdout=subprocess.PIPE,
                                   text=True)
            print(result.stdout)
            if result.stderr:
                print("Errors encountered:")
                print(result.stderr)
        else:
            print(f"Scraper script not found at: {scraper_path}")
    except Exception as e:
        print(f"Error running the scraper: {e}")

if __name__ == "__main__":
    main() 