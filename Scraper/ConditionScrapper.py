import os
import re
import json
import time
import logging
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import List, Optional, Dict
from dataclasses import dataclass, asdict

# Création des dossiers nécessaires
os.makedirs("logs/condition", exist_ok=True)
os.makedirs("Data/condition", exist_ok=True)

# Configuration du logging
logging.basicConfig(
    filename="logs/condition/data_scraper.log",
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
class Effect:
    name: str
    description: str

@dataclass
class ConditionData:
    name: str
    source: str
    pages: str
    description: str
    effects: List[Effect] = None
    table_data: Optional[Dict] = None

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

def extract_table_data(table_element) -> Dict:
    """Extrait les données d'un tableau si présent."""
    try:
        # Récupérer le titre du tableau
        caption = table_element.find_element(By.TAG_NAME, "caption").text
        
        # Récupérer les en-têtes
        headers = [th.text for th in table_element.find_elements(By.CSS_SELECTOR, "thead th")]
        
        # Récupérer les lignes
        rows = []
        for tr in table_element.find_elements(By.CSS_SELECTOR, "tbody tr"):
            row = [td.text for td in tr.find_elements(By.TAG_NAME, "td")]
            rows.append(row)
            
        return {
            "title": caption,
            "headers": headers,
            "rows": rows
        }
    except Exception as e:
        logger.warning(f"Erreur lors de l'extraction des données du tableau: {e}")
        return None

def extract_effects(effects_container) -> List[Effect]:
    """Extrait les effets détaillés d'une condition."""
    effects = []
    try:
        for effect_div in effects_container.find_elements(By.CSS_SELECTOR, "div.rd__b--3"):
            try:
                name = effect_div.find_element(By.CSS_SELECTOR, "span.entry-title-inner").text
                description = effect_div.find_element(By.TAG_NAME, "p").text
                effects.append(Effect(name=name, description=description))
            except Exception as e:
                logger.warning(f"Erreur lors de l'extraction d'un effet: {e}")
                continue
        return effects
    except Exception as e:
        logger.warning(f"Erreur lors de l'extraction des effets: {e}")
        return []

def process_condition(driver: uc.Chrome, condition_element) -> Optional[ConditionData]:
    """Traite une condition et extrait ses données."""
    try:
        # Récupérer le nom avant de cliquer
        name = condition_element.find_element(By.CSS_SELECTOR, "span.bold").text.strip()
        logger.info(f"Traitement de la condition: {name}")
        
        # Cliquer sur la condition
        driver.execute_script("arguments[0].click();", condition_element)
        time.sleep(1)
        
        wait = WebDriverWait(driver, 10)
        content = wait.until(EC.presence_of_element_located((By.ID, "pagecontent")))
        
        # Extraire les informations de base
        source = content.find_element(By.CSS_SELECTOR, "a.stats__h-source-abbreviation").text
        pages = content.find_element(By.CSS_SELECTOR, "a.rd__stats-name-page").text.replace("p", "")
        description = content.find_element(By.CSS_SELECTOR, "div.rd__b--1").text
        
        condition_data = ConditionData(
            name=name,
            source=source,
            pages=pages,
            description=description,
            effects=[],
            table_data=None
        )
        
        # Vérifier s'il y a un tableau
        try:
            table = content.find_element(By.CSS_SELECTOR, "table.rd__table")
            condition_data.table_data = extract_table_data(table)
        except:
            pass
        
        # Vérifier s'il y a des effets détaillés
        try:
            effects_container = content.find_element(By.CSS_SELECTOR, "div.rd__b--2")
            condition_data.effects = extract_effects(effects_container)
        except:
            pass
        
        return condition_data
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la condition: {e}")
        return None

def save_condition_data(condition: ConditionData):
    """Sauvegarde les données d'une condition au format JSON."""
    try:
        safe_name = sanitize_filename(condition.name.lower())
        file_path = os.path.join("Data", "condition", f"{safe_name}.json")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(condition), f, ensure_ascii=False, indent=2)
            
        logger.info(f"Données sauvegardées pour {condition.name}")
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde des données pour {condition.name}: {e}")

def main():
    """Fonction principale d'exécution."""
    driver = None
    try:
        driver = setup_driver()
        
        # Chargement initial
        driver.get('https://5e.tools/conditionsdiseases.html')
        logger.info("Chargement de la page des conditions...")
        time.sleep(5)
        
        # Attendre que la liste soit chargée (URL change avec #)
        wait = WebDriverWait(driver, 20)
        condition_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.lst__row-border")))
        
        total_conditions = len(condition_elements)
        logger.info(f"Nombre total de conditions trouvées : {total_conditions}")
        
        processed_count = 0
        for i in range(total_conditions):
            try:
                # Récupérer la liste à chaque itération pour éviter les éléments périmés
                condition_elements = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
                current_condition = condition_elements[i]
                
                # S'assurer que l'élément est visible
                driver.execute_script("arguments[0].scrollIntoView(true);", current_condition)
                time.sleep(0.5)
                
                condition_data = process_condition(driver, current_condition)
                if condition_data:
                    save_condition_data(condition_data)
                    processed_count += 1
                    logger.info(f"Progression: {processed_count}/{total_conditions} ({(processed_count/total_conditions)*100:.1f}%)")
                
                # Retourner à la liste en cliquant sur le titre de la page
                try:
                    title = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "h1.stats__h-name")))
                    driver.execute_script("arguments[0].click();", title)
                    time.sleep(0.5)  # Court délai pour le retour à la liste
                except Exception as e:
                    logger.warning(f"Impossible de cliquer sur le titre, utilisation de l'URL directe: {e}")
                    # Si on ne peut pas cliquer sur le titre, on utilise l'URL avec le fragment
                    driver.execute_script("window.location.hash = '';")
                    time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Erreur lors du traitement d'une condition: {e}")
                continue
        
        logger.info(f"Scraping terminé! {processed_count} conditions traitées sur {total_conditions}")
        
    except Exception as e:
        logger.error(f"Erreur dans l'exécution principale: {e}")
        raise
    finally:
        if driver:
            driver.quit()
            logger.info("Navigateur fermé")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Erreur dans la boucle principale: {e}")
        print(f"Une erreur est survenue: {e}")
