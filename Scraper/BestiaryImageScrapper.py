import os
import re
import json
import time
import asyncio
import aiohttp
import logging
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import Dict, List, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    filename="logs/bestiary/image_scraper.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

@dataclass
class MonsterImage:
    name: str
    token_url: Optional[str] = None
    full_url: Optional[str] = None

def sanitize_filename(name: str) -> str:
    """Clean the filename to be safe for filesystem."""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def setup_driver():
    """Configure and return the Chrome driver."""
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.98 Safari/537.36")
    
    try:
        driver = uc.Chrome(
            options=options,
            version_main=133,
            suppress_welcome=True
        )
        return driver
    except Exception as e:
        logging.error(f"Failed to initialize Chrome driver: {e}")
        raise

async def download_image(session: aiohttp.ClientSession, image_url: str, save_path: str) -> bool:
    """Download an image asynchronously."""
    try:
        if not image_url.startswith('http'):
            base_url = "https://5e.tools/"
            image_url = urljoin(base_url, image_url)
        
        async with session.get(image_url) as response:
            if response.status == 200:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(await response.read())
                logging.info(f"Image downloaded successfully: {save_path}")
                return True
            else:
                logging.error(f"Failed to download {image_url}, status: {response.status}")
                return False
    except Exception as e:
        logging.error(f"Error downloading image {image_url}: {e}")
        return False

def extract_monster_images(driver: uc.Chrome, monster_element) -> MonsterImage:
    """Extract image URLs for a monster."""
    try:
        name = monster_element.find_element(By.CSS_SELECTOR, "span.best-ecgen__name").text.strip()
        monster = MonsterImage(name=name)
        
        # Click on the monster to open its details
        driver.execute_script("arguments[0].click();", monster_element)
        time.sleep(1)
        
        # Get token image
        try:
            token_img = driver.find_element(By.CSS_SELECTOR, "img.stats__token")
            monster.token_url = token_img.get_attribute("src")
        except Exception:
            logging.warning(f"[{name}] No token image found")
        
        # Get full image
        try:
            images_tab = driver.find_element(By.CSS_SELECTOR, "button.stat-tab-gen")
            driver.execute_script("arguments[0].click();", images_tab)
            time.sleep(0.5)
            
            full_img = driver.find_element(By.CSS_SELECTOR, "img.rd__image")
            monster.full_url = full_img.get_attribute("src")
        except Exception:
            logging.warning(f"[{name}] No full image found")
        
        return monster
    except Exception as e:
        logging.error(f"Error extracting monster images: {e}")
        return None

async def download_monster_images(monsters: List[MonsterImage]):
    """Download images for multiple monsters concurrently."""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for monster in monsters:
            safe_name = sanitize_filename(monster.name)
            
            if monster.token_url:
                token_path = os.path.join("Data", "Images", "tokens", f"{safe_name}.webp")
                tasks.append(download_image(session, monster.token_url, token_path))
            
            if monster.full_url:
                full_path = os.path.join("Data", "Images", "full", f"{safe_name}.webp")
                tasks.append(download_image(session, monster.full_url, full_path))
        
        results = await asyncio.gather(*tasks)
        return results

def process_monster_batch(driver: uc.Chrome, monster_elements: List) -> List[MonsterImage]:
    """Process a batch of monsters to extract their image URLs."""
    monsters = []
    for element in monster_elements:
        monster = extract_monster_images(driver, element)
        if monster:
            monsters.append(monster)
    return monsters

async def main():
    """Main execution function."""
    os.makedirs("logs/bestiary", exist_ok=True)
    os.makedirs("Data/Images/tokens", exist_ok=True)
    os.makedirs("Data/Images/full", exist_ok=True)
    
    driver = None
    try:
        driver = setup_driver()
        wait = WebDriverWait(driver, 20)
        
        # Load the page
        driver.get('https://5e.tools/bestiary.html')
        logging.info("Page loaded: https://5e.tools/bestiary.html")
        time.sleep(5)  # Wait for JavaScript
        
        # Get all monster elements
        monster_elements = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
        total_monsters = len(monster_elements)
        logging.info(f"Found {total_monsters} monsters")
        
        # Process monsters in batches of 10
        batch_size = 10
        for i in range(0, total_monsters, batch_size):
            batch = monster_elements[i:i + batch_size]
            logging.info(f"Processing batch {i//batch_size + 1}/{(total_monsters + batch_size - 1)//batch_size}")
            
            # Extract image URLs for the batch
            monsters = process_monster_batch(driver, batch)
            
            # Download images concurrently
            await download_monster_images(monsters)
            
            # Navigate back to the main list
            driver.get('https://5e.tools/bestiary.html')
            time.sleep(3)  # Wait for page to load
            monster_elements = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
        
    except Exception as e:
        logging.error(f"Error in main execution: {e}")
        raise
    finally:
        if driver:
            driver.quit()
            logging.info("Browser closed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("Image scraping completed successfully!")
    except Exception as e:
        print(f"An error occurred: {e}")
        logging.error(f"Main execution error: {e}") 