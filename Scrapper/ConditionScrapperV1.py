import os
import re
import json
import time
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass, asdict

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import modular components
from Scrapper.Modules.SetupLogger import setup_directories, setup_logger
from Scrapper.Modules.DetectOS import get_os_info, is_windows, is_linux, is_macos
from Scrapper.Modules.DetectPackages import detect_chrome_version, get_user_agent, check_dependency_compatibility

# ===== Setup directories =====
setup_directories(["Logs/Condition", "Data/Condition"])

# ===== Logging configuration =====
logger = setup_logger("Logs/Condition/DataScrapper.log")

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


def setup_driver() -> uc.Chrome:
    """
    Set up and initialize the Chrome driver with cross-platform compatibility.
    
    Returns:
        Configured undetected_chromedriver Chrome instance
    """
    opts = uc.ChromeOptions()
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    
    # Get custom user agent with package information
    user_agent = get_user_agent()
    opts.add_argument(f"user-agent={user_agent}")

    # Check compatibility
    is_compatible, warnings = check_dependency_compatibility()
    if not is_compatible:
        for warning in warnings:
            logger.warning(warning)
    
    # Get Chrome version
    chrome_version = detect_chrome_version()
    
    try:
        if chrome_version:
            drv = uc.Chrome(options=opts, version_main=chrome_version, suppress_welcome=True)
        else:
            drv = uc.Chrome(options=opts, suppress_welcome=True)
        logger.info("Chrome driver initialized successfully")
        return drv
    except Exception as e:
        logger.error(f"Failed to initialize Chrome driver: {e}")
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
                    logger.warning(f"Could not disable filter: {p.text}")
        logger.info("All filters disabled.")
    except Exception as e:
        logger.warning(f"Error disabling filters: {e}")


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
    logger.info(f"Data saved: {cond.name} ({cond.source})")


def main():
    # Log OS information
    os_info = get_os_info()
    logger.info(f"Running on: {os_info['system']} {os_info['release']}")
    
    driver = None
    try:
        driver = setup_driver()
        driver.get('https://5e.tools/conditionsdiseases.html')
        logger.info("Loading page...")
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
                logger.info(f"Progress: {idx+1}/{total}")
            except Exception as e:
                logger.error(f"Error processing index {idx}: {e}")
            # Return to list
            driver.execute_script("window.location.hash = '';")
            time.sleep(0.5)

        logger.info(f"Scraping completed: {total} conditions.")
    except Exception as e:
        logger.error(f"Main error: {e}")
    finally:
        if driver:
            driver.quit()
            logger.info("Driver closed.")

if __name__ == "__main__":
    main()