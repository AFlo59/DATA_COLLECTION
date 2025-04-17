import os
import re
import time
import asyncio
import aiohttp
import logging
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin
from typing import List, Optional
from dataclasses import dataclass

# Création des dossiers nécessaires
os.makedirs("logs/bestiary", exist_ok=True)
os.makedirs("Data/bestiary/Images/tokens", exist_ok=True)
os.makedirs("Data/bestiary/Images/full", exist_ok=True)

# Configuration du logging
logging.basicConfig(
    filename="logs/bestiary/image_scraper.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Ajout du logging console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)

logger = logging.getLogger(__name__)

@dataclass
class MonsterImage:
    name: str
    token_url: Optional[str] = None
    full_url: Optional[str] = None

def sanitize_filename(name: str) -> str:
    """Nettoie le nom pour être compatible avec le système de fichiers."""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def setup_driver():
    """Configure et retourne le driver Chrome."""
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")
    
    try:
        driver = uc.Chrome(
            options=options,
            version_main=133,
            suppress_welcome=True
        )
        return driver
    except Exception as e:
        logger.error(f"Échec de l'initialisation du driver Chrome: {e}")
        raise

async def download_image(session: aiohttp.ClientSession, image_url: str, save_path: str) -> bool:
    """Télécharge une image de façon asynchrone."""
    try:
        if not image_url.startswith('http'):
            base_url = "https://5e.tools/"
            image_url = urljoin(base_url, image_url)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'Accept': 'image/webp,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://5e.tools/'
        }
        
        async with session.get(image_url, headers=headers) as response:
            if response.status == 200:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(await response.read())
                logger.info(f"Image téléchargée avec succès : {save_path}")
                return True
            else:
                logger.error(f"Échec du téléchargement de {image_url}, status: {response.status}")
                return False
    except Exception as e:
        logger.error(f"Erreur pendant le téléchargement de l'image {image_url}: {e}")
        return False

async def process_monster_batch(driver: uc.Chrome, monster_elements: List, session: aiohttp.ClientSession, start_idx: int, batch_size: int, total_monsters: int):
    """Traite un lot de monstres sans recharger la page inutilement."""
    wait = WebDriverWait(driver, 10)
    
    for i in range(start_idx, min(start_idx + batch_size, total_monsters)):
        try:
            # Trouver le monstre actuel dans la liste
            current_monster = monster_elements[i]
            name = current_monster.find_element(By.CSS_SELECTOR, "span.best-ecgen__name").text.strip()
            safe_name = sanitize_filename(name)
            logger.info(f"Traitement du monstre {i+1}/{total_monsters}: {name}")
            
            # S'assurer que l'élément est visible
            driver.execute_script("arguments[0].scrollIntoView(true);", current_monster)
            time.sleep(0.5)  # Petit délai pour le scroll
            
            # 1. Cliquer sur le monstre et attendre le token
            driver.execute_script("arguments[0].click();", current_monster)
            
            # Attendre et télécharger le token
            try:
                token_img = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "img.stats__token")))
                token_url = token_img.get_attribute("src")
                if token_url:
                    token_path = os.path.join("Data", "Images", "tokens", f"{safe_name}.webp")
                    await download_image(session, token_url, token_path)
                
                # 2. Cliquer sur l'onglet Images et télécharger l'image complète
                try:
                    images_tab = wait.until(EC.element_to_be_clickable(
                        (By.XPATH, "//button[contains(@class, 'ui-tab__btn-tab-head') and contains(@class, 'stat-tab-gen') and text()='Images']")
                    ))
                    driver.execute_script("arguments[0].click();", images_tab)
                    time.sleep(1)  # Court délai pour le changement d'onglet
                    
                    # Attendre et télécharger l'image complète
                    full_img_container = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.rd__wrp-image")))
                    full_img_link = full_img_container.find_element(By.CSS_SELECTOR, "a")
                    full_url = full_img_link.get_attribute("href")
                    
                    if full_url:
                        full_path = os.path.join("Data", "Images", "full", f"{safe_name}.webp")
                        await download_image(session, full_url, full_path)
                except Exception as e:
                    logger.warning(f"Pas d'image complète pour {name}: {e}")
            except Exception as e:
                logger.error(f"Erreur lors du traitement de {name}: {e}")
            
            # Retourner à la liste en cliquant sur le premier onglet (Stats)
            try:
                stats_tab = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(@class, 'ui-tab__btn-tab-head') and contains(@class, 'stat-tab-gen') and contains(text(), 'Stat')]")
                ))
                driver.execute_script("arguments[0].click();", stats_tab)
            except Exception as e:
                logger.warning(f"Impossible de revenir à l'onglet Stats pour {name}: {e}")
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement du monstre à l'index {i}: {e}")
            continue

async def main():
    """Fonction principale d'exécution."""
    driver = None
    try:
        driver = setup_driver()
        
        # Chargement initial
        driver.get('https://5e.tools/bestiary.html')
        logger.info("Chargement de la page du bestiaire...")
        time.sleep(5)
        
        # Attendre que la liste soit chargée
        wait = WebDriverWait(driver, 20)
        monster_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.lst__row-border")))
        
        total_monsters = len(monster_elements)
        logger.info(f"Nombre total de monstres trouvés : {total_monsters}")
        
        batch_size = 10  # On peut augmenter la taille du batch car on ne recharge plus la page
        async with aiohttp.ClientSession() as session:
            for start_idx in range(0, total_monsters, batch_size):
                logger.info(f"Traitement du lot {start_idx//batch_size + 1}/{(total_monsters + batch_size - 1)//batch_size}")
                await process_monster_batch(driver, monster_elements, session, start_idx, batch_size, total_monsters)
        
        logger.info("Scraping terminé avec succès!")
        
    except Exception as e:
        logger.error(f"Erreur dans l'exécution principale: {e}")
        raise
    finally:
        if driver:
            driver.quit()
            logger.info("Navigateur fermé")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Erreur dans la boucle principale: {e}")
        print(f"Une erreur est survenue: {e}")
