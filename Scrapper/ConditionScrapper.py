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

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===== Setup directories =====
os.makedirs("Logs/Condition", exist_ok=True)
os.makedirs("Data/Condition", exist_ok=True)

# ===== Logging configuration =====
logging.basicConfig(
    filename="logs/condition/Data_scrapper.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(console)
logger = logging.getLogger(__name__)

# ===== Data classes =====
@dataclass
class Effect:
    name: str
    description: str

@dataclass
class ConditionData:
    name: str
    source: Optional[str]
    pages: Optional[str]
    description: Optional[str]
    effects: List[Effect]
    table_data: Optional[Dict]

# ===== Helpers =====
def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)


def get_headers() -> Dict[str, str]:
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
    cmds = ['google-chrome', 'google-chrome-stable', 'chrome', 'chromium-browser', 'chromium']
    for cmd in cmds:
        try:
            out = subprocess.check_output([cmd, '--version'], stderr=subprocess.DEVNULL).decode()
            m = re.search(r"(\d+)\.", out)
            if m:
                v = int(m.group(1))
                logger.info(f"Version Chrome détectée: {v}")
                return v
        except Exception:
            continue
    logger.warning("Impossible de détecter la version de Chrome.")
    return None


def setup_driver() -> uc.Chrome:
    opts = uc.ChromeOptions()
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    headers = get_headers()
    opts.add_argument(f"user-agent={headers['User-Agent']}")

    vmain = detect_chrome_major_version()
    try:
        if vmain:
            drv = uc.Chrome(options=opts, version_main=vmain, suppress_welcome=True)
        else:
            drv = uc.Chrome(options=opts, suppress_welcome=True)
        logger.info("Driver Chrome initialisé")
        return drv
    except Exception as e:
        logger.error(f"Échec init driver: {e}")
        raise


def disable_filters(driver: uc.Chrome):
    try:
        while True:
            pills = driver.find_elements(By.CSS_SELECTOR, "div.fltr__mini-pill:not([data-state='ignore'])")
            if not pills:
                break
            for p in pills:
                try:
                    driver.execute_script("arguments[0].scrollIntoView(true);", p)
                    time.sleep(0.2)
                    driver.execute_script("arguments[0].click();", p)
                    time.sleep(0.3)
                except Exception as e:
                    logger.warning(f"Filtre non désactivé: {p.text}")
        logger.info("Tous les filtres désactivés.")
    except Exception as e:
        logger.warning(f"Erreur désactivation filtres: {e}")


def extract_table_data(el) -> Optional[Dict]:
    try:
        cap = el.find_element(By.TAG_NAME, "caption").text
        hdrs = [th.text for th in el.find_elements(By.CSS_SELECTOR, "thead th")]
        rows = [[td.text for td in tr.find_elements(By.TAG_NAME, "td")] for tr in el.find_elements(By.CSS_SELECTOR, "tbody tr")]
        return {"title": cap, "headers": hdrs, "rows": rows}
    except:
        return None


def extract_effects(cont) -> List[Effect]:
    effs = []
    for d in cont.find_elements(By.CSS_SELECTOR, "div.rd__b--3"):
        nm = d.find_element(By.CSS_SELECTOR, "span.entry-title-inner").text
        ds = d.find_element(By.TAG_NAME, "p").text
        effs.append(Effect(name=nm, description=ds))
    return effs


def process_condition(driver: uc.Chrome, elem) -> ConditionData:
    name = elem.find_element(By.CSS_SELECTOR, "span.bold").text.strip()
    driver.execute_script("arguments[0].click();", elem)
    content = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "pagecontent")))

    # Source (span ou a)
    try:
        src_el = content.find_element(By.CSS_SELECTOR, ".stats__h-source-abbreviation")
        source = src_el.text
    except:
        source = None
    # Pages (span ou a)
    try:
        pg_el = content.find_element(By.CSS_SELECTOR, ".rd__stats-name-page")
        pages = pg_el.text.lstrip('p')
    except:
        pages = None
    # Description
    try:
        desc = content.find_element(By.CSS_SELECTOR, "div.rd__b--1").text
    except:
        desc = None
    # Tableau
    table = None
    try:
        tbl = content.find_element(By.CSS_SELECTOR, "table.rd__table")
        table = extract_table_data(tbl)
    except:
        pass
    # Effets détaillés
    effs = []
    try:
        cont = content.find_element(By.CSS_SELECTOR, "div.rd__b--2")
        effs = extract_effects(cont)
    except:
        pass

    return ConditionData(name=name, source=source, pages=pages, description=desc, effects=effs, table_data=table)


def save_condition_data(cond: ConditionData):
    nm = sanitize_filename(cond.name.lower())
    src = sanitize_filename(cond.source.lower()) if cond.source else "unknown"
    filename = f"{nm}_{src}.json"
    path = os.path.join("Data/Condition", filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(asdict(cond), f, ensure_ascii=False, indent=2)
    logger.info(f"Données sauvegardées: {cond.name} ({cond.source})")


def main():
    driver = None
    try:
        driver = setup_driver()
        driver.get('https://5e.tools/conditionsdiseases.html')
        logger.info("Chargement de la page...")
        time.sleep(5)

        disable_filters(driver)
        WebDriverWait(driver, 20).until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "a.lst__row-border")) == 59)

        elems = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
        total = len(elems)
        for idx in range(total):
            elems = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
            el = elems[idx]
            driver.execute_script("arguments[0].scrollIntoView(true);", el)
            time.sleep(0.3)
            try:
                cond = process_condition(driver, el)
                save_condition_data(cond)
                logger.info(f"Progression: {idx+1}/{total}")
            except Exception as e:
                logger.error(f"Erreur traitement idx={idx}: {e}")
            # Retour à la liste
            driver.execute_script("window.location.hash = '';")
            time.sleep(0.5)

        logger.info(f"Scraping terminé: {total} conditions.")
    except Exception as e:
        logger.error(f"Erreur principale: {e}")
    finally:
        if driver:
            driver.quit()
            logger.info("Driver fermé.")

if __name__ == "__main__":
    main()