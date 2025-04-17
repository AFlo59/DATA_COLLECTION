import os
import platform
import logging
import time
import json
import re
import subprocess
from typing import List, Optional, Dict
from dataclasses import dataclass, asdict

import pkg_resources
import undetected_chromedriver as uc
import selenium
import bs4
import requests
import pandas as pd
import urllib3
import aiohttp

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===== Setup directories =====
os.makedirs("logs/condition", exist_ok=True)
os.makedirs("Data/Condition", exist_ok=True)

# ===== Logging configuration =====
logging.basicConfig(
    filename="logs/condition/data_scraper.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(console_handler)
logger = logging.getLogger(__name__)

# ===== Data classes =====
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
    effects: List[Effect]
    table_data: Optional[Dict]

# ===== Helpers =====
def sanitize_filename(name: str) -> str:
    """Nettoie le nom pour être compatible avec le système de fichiers."""
    return re.sub(r'[\\/*?:"<>|]', "", name)


def get_headers() -> Dict[str, str]:
    """Construit un User-Agent dynamique selon l'OS et les versions des packages."""
    os_info = f"{platform.system()} {platform.release()}"
    pkgs = ["selenium", "undetected-chromedriver", "beautifulsoup4", "requests", "pandas", "urllib3", "aiohttp"]
    versions = {}
    for pkg in pkgs:
        try:
            versions[pkg] = pkg_resources.get_distribution(pkg).version
        except Exception:
            versions[pkg] = "unknown"
    ua = f"ConditionScraper/1.0 ({os_info}); " + "; ".join(f"{k}/{v}" for k, v in versions.items())
    return {"User-Agent": ua}


def detect_chrome_major_version() -> Optional[int]:
    """Tente de détecter la version majeure de Chrome installée."""
    commands = ['google-chrome', 'google-chrome-stable', 'chrome', 'chromium-browser', 'chromium']
    for cmd in commands:
        try:
            out = subprocess.check_output([cmd, '--version'], stderr=subprocess.DEVNULL).decode()
            m = re.search(r"(\d+)\.", out)
            if m:
                version = int(m.group(1))
                logger.info(f"Version Chrome détectée: {version}")
                return version
        except Exception:
            continue
    logger.warning("Impossible de détecter la version de Chrome installée.")
    return None


def setup_driver() -> uc.Chrome:
    """Configure et retourne le driver Chrome avec un User-Agent adapté et version-compatible."""
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    headers = get_headers()
    options.add_argument(f"user-agent={headers['User-Agent']}")

    version_main = detect_chrome_major_version()
    try:
        if version_main:
            driver = uc.Chrome(options=options, version_main=version_main, suppress_welcome=True)
        else:
            driver = uc.Chrome(options=options, suppress_welcome=True)
        logger.info("Driver Chrome initialisé avec User-Agent: %s", headers['User-Agent'])
        return driver
    except Exception as e:
        logger.error(f"Échec de l'initialisation du driver Chrome: {e}")
        raise


def disable_filters(driver: uc.Chrome):
    """Désactive tous les filtres (sources et types) avant de scraper."""
    try:
        while True:
            active_pills = driver.find_elements(By.CSS_SELECTOR, "div.fltr__mini-pill:not([data-state='ignore'])")
            if not active_pills:
                break
            for pill in active_pills:
                try:
                    driver.execute_script("arguments[0].scrollIntoView(true);", pill)
                    time.sleep(0.2)
                    driver.execute_script("arguments[0].click();", pill)
                    new_state = pill.get_attribute('data-state')
                    logger.info(f"Filtre désactivé: {pill.text} (état après clic: {new_state})")
                    time.sleep(0.3)
                except Exception as e:
                    logger.warning(f"Impossible de désactiver le filtre {pill.text}: {e}")
        logger.info("Tous les filtres sont désactivés.")
    except Exception as e:
        logger.warning(f"Erreur lors de la désactivation des filtres: {e}")


def extract_table_data(table_element) -> Dict:
    """Extrait les données d'un tableau si présent."""
    try:
        caption = table_element.find_element(By.TAG_NAME, "caption").text
        headers = [th.text for th in table_element.find_elements(By.CSS_SELECTOR, "thead th")]
        rows = []
        for tr in table_element.find_elements(By.CSS_SELECTOR, "tbody tr"):
            rows.append([td.text for td in tr.find_elements(By.TAG_NAME, "td")])
        return {"title": caption, "headers": headers, "rows": rows}
    except Exception as e:
        logger.warning(f"Erreur extraction table: {e}")
        return None


def extract_effects(container) -> List[Effect]:
    """Extrait les effets détaillés d'une condition."""
    effects = []
    try:
        for div in container.find_elements(By.CSS_SELECTOR, "div.rd__b--3"):
            try:
                name = div.find_element(By.CSS_SELECTOR, "span.entry-title-inner").text
                desc = div.find_element(By.TAG_NAME, "p").text
                effects.append(Effect(name=name, description=desc))
            except Exception as e:
                logger.warning(f"Erreur extraction effet: {e}")
        return effects
    except Exception as e:
        logger.warning(f"Erreur container effets: {e}")
        return []


def process_condition(driver: uc.Chrome, elem) -> Optional[ConditionData]:
    """Traite une condition et retourne ses données."""
    try:
        name = elem.find_element(By.CSS_SELECTOR, "span.bold").text.strip()
        logger.info(f"Traitement: {name}")
        driver.execute_script("arguments[0].click();", elem)
        wait = WebDriverWait(driver, 10)
        content = wait.until(EC.presence_of_element_located((By.ID, "pagecontent")))

        source = content.find_element(By.CSS_SELECTOR, "a.stats__h-source-abbreviation").text
        pages = content.find_element(By.CSS_SELECTOR, "a.rd__stats-name-page").text.lstrip('p')
        desc = content.find_element(By.CSS_SELECTOR, "div.rd__b--1").text

        data = ConditionData(name=name, source=source, pages=pages, description=desc, effects=[], table_data=None)

        try:
            tbl = content.find_element(By.CSS_SELECTOR, "table.rd__table")
            data.table_data = extract_table_data(tbl)
        except:
            pass

        try:
            cont = content.find_element(By.CSS_SELECTOR, "div.rd__b--2")
            data.effects = extract_effects(cont)
        except:
            pass

        return data
    except Exception as e:
        logger.error(f"Erreur traitement condition: {e}")
        return None


def save_condition_data(cond: ConditionData):
    """Sauvegarde les données d'une condition en JSON."""
    try:
        filename = sanitize_filename(cond.name.lower())
        path = os.path.join("Data/Condition", f"{filename}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(asdict(cond), f, ensure_ascii=False, indent=2)
        logger.info(f"Données sauvegardées: {cond.name}")
    except Exception as e:
        logger.error(f"Erreur sauvegarde {cond.name}: {e}")


def main():
    driver = None
    try:
        driver = setup_driver()
        driver.get('https://5e.tools/conditionsdiseases.html')
        logger.info("Page chargée, attente des filtres...")
        time.sleep(5)

        disable_filters(driver)

        wait = WebDriverWait(driver, 20)
        wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "a.lst__row-border")) == 59)
        logger.info("Tous les filtres désactivés, 59 conditions prêtes à être traitées.")

        elems = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
        total = len(elems)
        count = 0

        for i in range(total):
            elems = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
            elem = elems[i]
            driver.execute_script("arguments[0].scrollIntoView(true);", elem)
            time.sleep(0.3)

            data = process_condition(driver, elem)
            if data:
                save_condition_data(data)
                count += 1
                logger.info(f"Progression: {count}/{total}")

            driver.execute_script("window.location.hash = '';")
            time.sleep(0.5)

        logger.info(f"Scraping terminé: {count} conditions traitées sur {total}.")

    except Exception as e:
        logger.error(f"Erreur principale: {e}")
        raise
    finally:
        if driver:
            driver.quit()
            logger.info("Driver fermé.")

if __name__ == "__main__":
    main()