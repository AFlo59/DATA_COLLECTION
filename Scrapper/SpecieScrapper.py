import os
import sys
import time
import json
import logging
import traceback
import shutil
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any, Tuple, Set
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

# Add the parent directory to sys.path to enable imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Conditionally import Selenium components
try:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Import all modular components
try:
    # First try absolute imports
    from Scrapper.Modules.SetupLogger import setup_directories, get_logger
    from Scrapper.Modules.DetectOS import get_os_info
    from Scrapper.Modules.BrowserSetup import BrowserSetup
    from Scrapper.Modules.BrowserCleanup import BrowserCleanup, ensure_browser_cleanup
    from Scrapper.Modules.CookieHandler import CookieHandler
    from Scrapper.Modules.ConfigManager import ConfigManager, get_config
    from Scrapper.Modules.DetectPackages import check_dependency_compatibility
except ImportError:
    try:
        # Then try relative imports
        from Modules.SetupLogger import setup_directories, get_logger
        from Modules.DetectOS import get_os_info
        from Modules.BrowserSetup import BrowserSetup
        from Modules.BrowserCleanup import BrowserCleanup, ensure_browser_cleanup
        from Modules.CookieHandler import CookieHandler
        from Modules.ConfigManager import ConfigManager, get_config
        from Modules.DetectPackages import check_dependency_compatibility
    except ImportError:
        # As a last resort, try direct imports if files are in the same directory
        print("Failed to import modules. Check your project structure and Python path.")
        print(f"Current sys.path: {sys.path}")
        sys.exit(1)

# ===== Setup directories =====
setup_directories([
    "Logs/Specie", 
    "Data/Specie/Images",
    "Data/Specie/Json"
])

# ===== Get configuration =====
config = get_config()

# ===== Logging configuration =====
logger = get_logger("SpecieScrapper", log_dir="Logs/Specie", clean_logs=True)

# ===== Data classes =====
@dataclass
class SpecieImage:
    """Class representing a specie's image data"""
    url: Optional[str] = None
    file_path: Optional[str] = None
    downloaded: bool = False

@dataclass
class SpecieBase:
    """Class representing basic specie information"""
    name: str
    source: str
    url: str
    
@dataclass
class SpecieData(SpecieBase):
    """Class representing detailed specie data including traits and image"""
    traits: Dict[str, Any] = field(default_factory=dict)
    info: Dict[str, Any] = field(default_factory=dict)
    image: Optional[SpecieImage] = None
    processed: bool = False


def sanitize_filename(name: str) -> str:
    """
    Convert a string to a safe filename.
    
    Args:
        name: String to sanitize
        
    Returns:
        Sanitized string
    """
    import re
    # Replace any non-alphanumeric characters (except underscores) with underscores
    sanitized = re.sub(r'[\\/*?:"<>|]', "", name)
    return sanitized


def wait_and_click(driver: Any, wait: WebDriverWait, selector: str, by: By = By.CSS_SELECTOR, 
                  timeout: int = 20, description: str = "element") -> bool:
    """
    Wait for an element to be clickable and click it with proper logging.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
        selector: CSS selector or XPath
        by: Selection method (By.CSS_SELECTOR or By.XPATH)
        timeout: Maximum wait time in seconds
        description: Element description for logging
        
    Returns:
        Boolean indicating success
    """
    try:
        logger.info(f"Waiting for {description} to be clickable...")
        element = wait.until(EC.element_to_be_clickable((by, selector)))
        logger.info(f"Found {description}, attempting to click...")
        
        # Try direct click first
        try:
            element.click()
            logger.info(f"Successfully clicked {description} using direct click")
            return True
        except ElementClickInterceptedException:
            logger.info(f"Direct click failed for {description}, trying JavaScript click...")
            driver.execute_script("arguments[0].click();", element)
            logger.info(f"Successfully clicked {description} using JavaScript")
            return True
            
    except TimeoutException:
        logger.error(f"Timeout waiting for {description} to be clickable")
        return False
    except Exception as e:
        logger.error(f"Error clicking {description}: {e}")
        logger.debug(traceback.format_exc())
        return False


async def download_image(session: Any, image_url: str, save_path: str, base_url: str = "https://5e.tools/") -> bool:
    """
    Downloads an image asynchronously
    
    Args:
        session: aiohttp client session
        image_url: URL of the image
        save_path: Path to save the image
        base_url: Base URL to prepend to relative URLs
        
    Returns:
        Boolean indicating success
    """
    try:
        import aiohttp
        from urllib.parse import urljoin
        
        # Handle relative URLs
        if not image_url.startswith('http'):
            image_url = urljoin(base_url, image_url)
        
        # Set headers to mimic browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/webp,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://5e.tools/'
        }
        
        # Download image
        async with session.get(image_url, headers=headers) as response:
            if response.status == 200:
                # Ensure directory exists
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                
                # Save image
                with open(save_path, 'wb') as f:
                    f.write(await response.read())
                logger.info(f"Image downloaded successfully: {save_path}")
                return True
            else:
                logger.error(f"Failed to download {image_url}, status: {response.status}")
                return False
    except Exception as e:
        logger.error(f"Error downloading image {image_url}: {e}")
        logger.debug(traceback.format_exc())
        return False


def download_image_sync(driver: Any, image_url: str, save_path: str, base_url: str = "https://5e.tools/") -> bool:
    """
    Downloads an image synchronously using requests
    
    Args:
        driver: Browser driver instance (for cookies)
        image_url: URL of the image
        save_path: Path to save the image
        base_url: Base URL to prepend to relative URLs
        
    Returns:
        Boolean indicating success
    """
    try:
        import requests
        from urllib.parse import urljoin
        
        # Handle relative URLs
        if not image_url.startswith('http'):
            image_url = urljoin(base_url, image_url)
        
        # Get cookies from driver
        cookies = driver.get_cookies()
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
        
        # Set up session with cookies
        session = requests.Session()
        for name, value in cookie_dict.items():
            session.cookies.set(name, value)
        
        # Set headers to mimic browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/webp,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://5e.tools/'
        }
        
        # Download image
        response = session.get(image_url, headers=headers, stream=True)
        if response.status_code == 200:
            # Ensure directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Save image
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"Image downloaded successfully: {save_path}")
            return True
        else:
            logger.error(f"Failed to download {image_url}, status: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error downloading image {image_url}: {e}")
        logger.debug(traceback.format_exc())
        return False


def extract_species_metadata(driver: Any, wait: WebDriverWait) -> List[SpecieBase]:
    """
    Extract basic metadata for all species from the list.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
    
    Returns:
        List of SpecieBase objects
    """
    species = []
    
    try:
        # Wait for the list container to be fully loaded
        logger.info("Waiting for species list to load...")
        wait.until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "a.lst__row-border")) > 0
        )
        logger.info("Species list loaded, extracting metadata...")
        
        # Désactiver tous les filtres un par un en passant chaque data-state en ignore
        logger.info("Disabling all filters by setting each data-state to ignore...")
        try:
            # Script JavaScript pour désactiver tous les filtres
            disable_filters_script = """
            // Fonction pour désactiver tous les filtres
            function disableAllFilters() {
                // Désactiver tous les éléments avec un attribut data-state
                const filterElements = document.querySelectorAll('[data-state]');
                filterElements.forEach(el => {
                    el.setAttribute('data-state', 'ignore');
                });
                
                // Cliquer sur les boutons "Reset"
                const resetButtons = document.querySelectorAll('button.fltr__btn-reset');
                resetButtons.forEach(btn => {
                    btn.click();
                });
                
                // Cliquer sur les boutons "All"
                const allButtons = document.querySelectorAll('button.fltr__h-btn--all');
                allButtons.forEach(btn => {
                    btn.click();
                });
                
                // Désactiver les options de source
                const sourceCheckboxes = document.querySelectorAll('.fltr__src-yes');
                sourceCheckboxes.forEach(cb => {
                    if (cb.checked) {
                        cb.click();
                    }
                });
                
                // Cliquer sur les liens "Select All/None"
                const allNoneLinks = document.querySelectorAll('a.fltr__h-click-all, a.fltr__h-click-none');
                const allLinks = [...allNoneLinks].filter(a => a.textContent.includes('All'));
                allLinks.forEach(a => {
                    a.click();
                });
                
                // Pour les boutons radio, sélectionner "Any"
                const anyRadios = document.querySelectorAll('input[type="radio"][value="*"]');
                anyRadios.forEach(radio => {
                    radio.click();
                });
                
                // Retourner le nombre de filtres trouvés
                return {
                    dataState: filterElements.length,
                    resetButtons: resetButtons.length,
                    allButtons: allButtons.length,
                    sourceCheckboxes: sourceCheckboxes.length,
                    allLinks: allLinks.length,
                    anyRadios: anyRadios.length
                };
            }
            
            // Exécuter et retourner les résultats
            return disableAllFilters();
            """
            
            # Exécuter le script
            result = driver.execute_script(disable_filters_script)
            logger.info(f"Disabled filters: {result}")
            
            # Donner du temps au JavaScript pour actualiser la page
            time.sleep(3)
            
            # Désactiver explicitement les filtres un par un si nécessaire
            filter_buttons = driver.find_elements(By.CSS_SELECTOR, "button.fltr__btn-reset")
            for button in filter_buttons:
                try:
                    driver.execute_script("arguments[0].click();", button)
                    logger.info("Reset filter button clicked")
                    time.sleep(0.5)  # Petit délai pour laisser le temps au JavaScript de réagir
                except Exception as e:
                    logger.warning(f"Error clicking filter reset button: {e}")
            
            # Désactiver les sources (bouton "All")
            source_all_buttons = driver.find_elements(By.CSS_SELECTOR, "button.fltr__h-btn--all")
            for button in source_all_buttons:
                try:
                    driver.execute_script("arguments[0].click();", button)
                    logger.info("'All sources' button clicked")
                    time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Error clicking 'All sources' button: {e}")
                    
            # Désactiver les autres filtres qui pourraient être présents
            other_filter_buttons = driver.find_elements(By.CSS_SELECTOR, "button.col-12")
            for button in other_filter_buttons:
                if "Reset filters" in button.text or "Clear filters" in button.text:
                    try:
                        driver.execute_script("arguments[0].click();", button)
                        logger.info(f"Filter button clicked: {button.text}")
                        time.sleep(0.5)
                    except Exception as e:
                        logger.warning(f"Error clicking filter button: {e}")
                        
            # Attendre que la liste se mette à jour
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Error disabling filters: {e}")
            logger.debug(traceback.format_exc())
        
        # Find all species elements
        species_elements = driver.find_elements(By.CSS_SELECTOR, "a.lst__row-border")
        logger.info(f"Found {len(species_elements)} species elements")
        
        for i, element in enumerate(species_elements):
            try:
                # Get name (from the bold span)
                name_element = element.find_element(By.CSS_SELECTOR, "span.bold")
                name = name_element.text.strip()
                
                # Get source (from the last column or source tag)
                try:
                    # Try to find source in the source span/tag
                    source_element = element.find_element(By.CSS_SELECTOR, "span[title*='Source:']")
                    source = source_element.text.strip()
                except:
                    # Fallback: use the last column as source
                    columns = element.find_elements(By.CSS_SELECTOR, "span")
                    source = columns[-1].text.strip() if columns else "Unknown"
                
                # Get URL
                url = element.get_attribute("href")
                
                # Create and add species object
                species_data = SpecieBase(name=name, source=source, url=url)
                species.append(species_data)
                
                logger.info(f"Extracted metadata for species: {name} ({source})")
            except Exception as e:
                logger.warning(f"Failed to extract metadata for species at index {i}: {e}")
                logger.debug(traceback.format_exc())
        
        logger.info(f"Successfully extracted metadata for {len(species)} species")
        return species
    except Exception as e:
        logger.error(f"Error extracting species metadata: {e}")
        logger.debug(traceback.format_exc())
        return []


def extract_traits_data(driver: Any, wait: WebDriverWait) -> Dict[str, Any]:
    """
    Extract traits data from the currently displayed species page.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
    
    Returns:
        Dictionary containing traits data
    """
    traits = {}
    
    try:
        # Wait for traits content to load
        logger.info("Extracting traits data...")
        
        # Attendre que la page soit chargée
        wait.until(EC.presence_of_element_located((By.ID, "pagecontent")))
        
        # Récupérer l'élément de page principal
        page_content = driver.find_element(By.ID, "pagecontent")
        
        # 1. Extraire les données de l'en-tête (nom, source, etc.)
        try:
            header_info = {}
            header = page_content.find_element(By.TAG_NAME, "th")
            
            # Nom et source depuis les attributs data-*
            if header.get_attribute("data-name"):
                header_info["full_name"] = header.get_attribute("data-name")
            if header.get_attribute("data-source"):
                header_info["source_code"] = header.get_attribute("data-source")
                
            # Extraire les liens vers la source (livre)
            source_links = header.find_elements(By.CSS_SELECTOR, "a.stats__h-source-abbreviation, a.rd__stats-name-page")
            for link in source_links:
                if "page" in link.get_attribute("class"):
                    header_info["page"] = link.text.strip()
                elif "source" in link.get_attribute("class"):
                    header_info["source_abbr"] = link.text.strip()
                    if link.get_attribute("title"):
                        header_info["source_full"] = link.get_attribute("title")
            
            # Fusionner ces infos dans les traits
            traits.update(header_info)
            logger.debug("Extracted header information")
        except Exception as e:
            logger.warning(f"Failed to extract header information: {e}")
        
        # 2. Extraire les attributs de base (Ability Scores, Size, etc.) depuis la liste ul
        try:
            basic_info = {}
            ul_elements = page_content.find_elements(By.CSS_SELECTOR, "ul.rd__list-hang-notitle li")
            
            for li in ul_elements:
                try:
                    # Récupérer le nom et la valeur
                    name_elem = li.find_element(By.CSS_SELECTOR, "span.bold, span.rd__list-item-name")
                    name = name_elem.text.strip().rstrip(':')
                    
                    # Obtenir le texte complet puis enlever le nom pour avoir la valeur
                    full_text = li.text.strip()
                    if name in full_text:
                        value = full_text[full_text.find(name) + len(name):].strip()
                        if value.startswith(':'):
                            value = value[1:].strip()
                        
                        basic_info[name] = value
                        logger.debug(f"Extracted basic trait: {name}")
                except Exception as e:
                    logger.warning(f"Failed to extract basic trait item: {e}")
            
            # Ajouter ces infos de base
            traits.update(basic_info)
        except Exception as e:
            logger.warning(f"Failed to extract basic info list: {e}")
        
        # 3. Extraire tous les traits détaillés des div.rd__b--3
        try:
            # Trouver toutes les sections de traits
            trait_divs = page_content.find_elements(By.CSS_SELECTOR, "div.rd__b div.rd__b--3")
            
            for div in trait_divs:
                try:
                    # Récupérer le nom du trait de différentes façons
                    title = None
                    
                    # Méthode 1: chercher l'élément span.entry-title-inner
                    try:
                        title_element = div.find_element(By.CSS_SELECTOR, "span.entry-title-inner")
                        title = title_element.text.strip()
                    except:
                        pass
                    
                    # Méthode 2: utiliser l'attribut data-roll-name-ancestor
                    if not title:
                        try:
                            title = div.get_attribute("data-roll-name-ancestor")
                        except:
                            pass
                    
                    # Si on a trouvé un titre
                    if title:
                        # Récupérer tous les paragraphes
                        paragraphs = div.find_elements(By.TAG_NAME, "p")
                        description = "\n".join([p.text.strip() for p in paragraphs])
                        
                        # Ajouter au dictionnaire des traits
                        traits[title] = description
                        logger.debug(f"Extracted trait: {title}")
                except Exception as e:
                    logger.warning(f"Failed to extract individual trait: {e}")
        except Exception as e:
            logger.warning(f"Failed to extract detailed traits: {e}")
        
        # 4. Extraire des informations supplémentaires (ex: ability scores) de la racine de la page
        try:
            # Chercher les div.rd__b--1 et div.rd__b--2 qui peuvent contenir des informations importantes
            ability_divs = page_content.find_elements(By.CSS_SELECTOR, "div.rd__b--1, div.rd__b--2")
            for div in ability_divs:
                text = div.text.strip()
                
                # Analyser le texte pour déterminer quel type d'information il contient
                if "Ability Score" in text:
                    traits["Ability Score Increase"] = text
                    logger.debug("Extracted Ability Score Increase")
                # Ajouter d'autres conditions au besoin
        except Exception as e:
            logger.warning(f"Failed to extract additional information: {e}")
        
        # 5. Extraire toutes les autres balises tr de la table pagecontent
        try:
            # Trouver toutes les lignes de la table
            rows = page_content.find_elements(By.TAG_NAME, "tr")
            
            for i, row in enumerate(rows):
                # Ignorer les lignes d'en-tête que nous avons déjà traitées
                if i < 2:  # Généralement les 2 premières lignes
                    continue
                
                # Vérifier si la ligne contient des données utiles
                cells = row.find_elements(By.TAG_NAME, "td")
                if cells:
                    for cell in cells:
                        text = cell.text.strip()
                        if text and "Source:" not in text and len(text) > 5:  # Éviter les cellules vides ou inutiles
                            # Ajouter comme information supplémentaire numérotée
                            key = f"Additional_Info_{i}"
                            traits[key] = text
                            logger.debug(f"Extracted additional row data: {key}")
            
        except Exception as e:
            logger.warning(f"Failed to extract table rows: {e}")
        
        # Si aucun trait n'a été trouvé, capturer tout le contenu de la page comme fallback
        if not traits:
            try:
                content = page_content.text.strip()
                traits["full_page_content"] = content
                logger.debug("Captured full page content as fallback")
            except Exception as e:
                logger.error(f"Failed to capture page content: {e}")
        
        logger.info(f"Extracted {len(traits)} traits in total")
        return traits
    except Exception as e:
        logger.error(f"Error extracting traits data: {e}")
        logger.debug(traceback.format_exc())
        return {}


def extract_info_data(driver: Any, wait: WebDriverWait) -> Dict[str, Any]:
    """
    Extract info data from the 'Info' tab of a species.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
    
    Returns:
        Dictionary containing info data
    """
    info = {}
    
    try:
        # Look for the Info tab and click it
        info_tab = driver.find_element(By.XPATH, "//button[contains(text(), 'Info')]")
        driver.execute_script("arguments[0].click();", info_tab)
        logger.info("Clicked Info tab")
        
        # Wait for info content to load
        time.sleep(1)
        
        # Extract info sections
        info_sections = driver.find_elements(By.CSS_SELECTOR, "div.rd__b")
        
        for section in info_sections:
            try:
                # Get section title if present
                try:
                    title_element = section.find_element(By.CSS_SELECTOR, "span.entry-title-inner")
                    title = title_element.text.strip()
                except:
                    # If no title, use a generic one
                    title = f"Section {len(info) + 1}"
                
                # Get section content
                content_elements = section.find_elements(By.TAG_NAME, "p")
                content = "\n".join([el.text.strip() for el in content_elements])
                
                info[title] = content
                logger.debug(f"Extracted info section: {title}")
            except Exception as e:
                logger.warning(f"Error extracting individual info section: {e}")
        
        logger.info(f"Extracted {len(info)} info sections")
        return info
    except Exception as e:
        logger.error(f"Error extracting info data: {e}")
        logger.debug(traceback.format_exc())
        return {}


def extract_image_data(driver: Any, wait: WebDriverWait) -> Optional[SpecieImage]:
    """
    Extract image data from the 'Images' tab of a species.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
    
    Returns:
        SpecieImage object if image found, None otherwise
    """
    try:
        # Look for the Images tab and click it
        images_tab = driver.find_element(By.XPATH, "//button[contains(text(), 'Images')]")
        driver.execute_script("arguments[0].click();", images_tab)
        logger.info("Clicked Images tab")
        
        # Wait for image content to load
        time.sleep(1)
        
        # Look for the image link
        image_link = driver.find_element(By.CSS_SELECTOR, "a[href*='img/']")
        image_url = image_link.get_attribute("href")
        
        if image_url:
            logger.info(f"Found image URL: {image_url}")
            return SpecieImage(url=image_url)
        else:
            logger.warning("Image URL not found")
            return None
    except Exception as e:
        logger.info(f"No image tab or image found: {e}")
        return None


def process_specie(driver: Any, wait: WebDriverWait, specie: SpecieBase) -> Optional[SpecieData]:
    """
    Process a single species to extract all its data.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
        specie: SpecieBase object with basic species info
        
    Returns:
        SpecieData object with full species data if successful, None otherwise
    """
    try:
        # Navigate to species page
        logger.info(f"Processing species: {specie.name} ({specie.source})")
        driver.get(specie.url)
        
        # Wait for page to load
        logger.info("Waiting for species page to load...")
        try:
            # Wait for page content to be visible
            wait.until(EC.presence_of_element_located((By.ID, "pagecontent")))
            logger.info("Species page loaded")
        except TimeoutException:
            logger.warning("Timeout waiting for species page to load, continuing anyway")
        
        time.sleep(1)  # Give extra time for page to stabilize
        
        # Create full species data object
        full_data = SpecieData(
            name=specie.name,
            source=specie.source,
            url=specie.url
        )
        
        # Extract traits data (default tab)
        full_data.traits = extract_traits_data(driver, wait)
        
        # Save the data immediately after getting traits (in case other tabs fail)
        save_specie_data(full_data)
        
        # Try to extract info data if the tab exists
        try:
            info_tab = driver.find_element(By.XPATH, "//button[contains(text(), 'Info')]")
            if info_tab:
                full_data.info = extract_info_data(driver, wait)
                # Update saved data
                save_specie_data(full_data)
        except:
            logger.info(f"No Info tab found for {specie.name}")
        
        # Try to extract image data if the tab exists
        try:
            images_tab = driver.find_element(By.XPATH, "//button[contains(text(), 'Images')]")
            if images_tab:
                full_data.image = extract_image_data(driver, wait)
                
                # Download image if URL found
                if full_data.image and full_data.image.url:
                    # Generate file path
                    safe_name = sanitize_filename(f"{specie.name}_{specie.source}".lower())
                    image_path = os.path.join("Data", "Specie", "Images", f"{safe_name}.webp")
                    
                    # Download image
                    if download_image_sync(driver, full_data.image.url, image_path):
                        full_data.image.file_path = image_path
                        full_data.image.downloaded = True
                
                # Update saved data
                save_specie_data(full_data)
        except:
            logger.info(f"No Images tab found for {specie.name}")
        
        full_data.processed = True
        logger.info(f"Successfully processed species: {specie.name}")
        return full_data
    except Exception as e:
        logger.error(f"Error processing species {specie.name}: {e}")
        logger.debug(traceback.format_exc())
        return None


def save_specie_data(specie: SpecieData) -> bool:
    """
    Save species data to a JSON file.
    
    Args:
        specie: SpecieData object to save
        
    Returns:
        Boolean indicating success
    """
    try:
        # Generate filename
        safe_name = sanitize_filename(f"{specie.name}_{specie.source}".lower())
        filepath = os.path.join("Data", "Specie", "Json", f"{safe_name}.json")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Convert dataclass to dict and save as JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(specie), f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved species data to: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Error saving species data for {specie.name}: {e}")
        logger.debug(traceback.format_exc())
        return False


def scrape_species() -> bool:
    """
    Main function to scrape all species from 5e.tools website
    
    Returns:
        Boolean indicating overall success
    """
    logger.info("=" * 80)
    logger.info("Starting species scraper")
    logger.info("=" * 80)
    
    # Log system information
    os_info = get_os_info()
    logger.info(f"Operating System: {os_info.get('name', 'Unknown')} {os_info.get('version', 'Unknown')}")
    
    # Check package compatibility
    compatibility_ok, issues = check_dependency_compatibility()
    if not compatibility_ok:
        logger.warning("Dependency compatibility issues detected:")
        for issue in issues:
            logger.warning(f"  - {issue}")
    
    # Initialize browser management
    browser_setup = BrowserSetup(logger)
    browser_cleanup = BrowserCleanup(logger)
    cookie_handler = CookieHandler(logger)
    
    driver = None
    success = False
    
    try:
        # Get browser driver
        logger.info("Setting up browser driver...")
        driver = browser_setup.get_driver()
        
        # Register browser for cleanup
        browser_cleanup.register_browser(driver)
        
        # Set up wait instance
        wait = WebDriverWait(driver, 30)
        
        # Navigate to species page
        species_url = "https://5e.tools/races.html"
        logger.info(f"Navigating to species page: {species_url}")
        driver.get(species_url)
        
        # Wait for page to load and handle cookie consent
        time.sleep(3)
        logger.info("Handling cookie consent...")
        cookie_handler.handle_consent(driver, wait)
        
        # Extract species list
        logger.info("Extracting species metadata...")
        species_list = extract_species_metadata(driver, wait)
        
        if not species_list:
            logger.error("Failed to extract any species metadata")
            return False
        
        logger.info(f"Found {len(species_list)} species to process")
        
        # Save species list for reference
        try:
            species_list_path = os.path.join("Data", "Specie", "species_list.json")
            os.makedirs(os.path.dirname(species_list_path), exist_ok=True)
            with open(species_list_path, 'w', encoding='utf-8') as f:
                json.dump([asdict(s) for s in species_list], f, ensure_ascii=False, indent=2)
            logger.info(f"Saved species list to: {species_list_path}")
        except Exception as e:
            logger.error(f"Error saving species list: {e}")
        
        # Process each species
        processed_count = 0
        for i, specie in enumerate(species_list):
            try:
                logger.info(f"Processing species {i+1}/{len(species_list)}: {specie.name}")
                species_data = process_specie(driver, wait, specie)
                
                if species_data:
                    processed_count += 1
                    logger.info(f"Successfully processed: {specie.name} ({processed_count}/{len(species_list)})")
                else:
                    logger.warning(f"Failed to process: {specie.name}")
                
                # Add small delay between processing each species
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error processing species {specie.name}: {e}")
                logger.debug(traceback.format_exc())
        
        logger.info(f"Completed species scraping. Processed {processed_count}/{len(species_list)} species successfully.")
        success = processed_count > 0
        
    except Exception as e:
        logger.error(f"Unhandled error in species scraper: {e}")
        logger.debug(traceback.format_exc())
        success = False
    finally:
        # Ensure browser cleanup
        if driver:
            logger.info("Cleaning up browser...")
            ensure_browser_cleanup(driver, logger)
        
        logger.info("=" * 80)
        logger.info("Species scraper finished")
        logger.info("=" * 80)
        
        return success


if __name__ == "__main__":
    # Execute the main scraper function
    success = scrape_species()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
