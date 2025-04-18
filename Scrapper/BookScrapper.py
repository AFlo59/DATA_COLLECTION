import os
import re
import json
import time
import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict, field
import traceback
import sys
from datetime import datetime
import shutil
import winreg

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
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
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
        import sys
        print("Failed to import modules. Check your project structure and Python path.")
        print(f"Current sys.path: {sys.path}")
        sys.exit(1)

# ===== Setup directories =====
setup_directories(["Logs/Books", "Data/Books"])

# ===== Get configuration =====
config = get_config()

# ===== Logging configuration =====
logger = get_logger("BookScrapper", log_dir="Logs/Books", clean_logs=True)

# Gérer l'encodage Windows pour éviter les erreurs avec caractères spéciaux
import sys
if sys.platform == 'win32':
    # Configuration pour éviter les erreurs d'encodage dans la console Windows
    import codecs
    try:
        # Essayer de configurer l'encodage UTF-8 pour la console Windows
        codecs.register_error('strict', codecs.replace_errors)
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass  # Si ça échoue, on continue quand même

# ===== Data classes =====
@dataclass
class BookMetadata:
    """Class representing a book's metadata"""
    name: str
    type: str
    publication_date: str
    url: str
    source: Optional[str] = None
    is_legacy: bool = False
    download_path: Optional[str] = None
    download_success: bool = False


@dataclass
class BooksData:
    """Class representing all books metadata"""
    books: List[BookMetadata] = field(default_factory=list)
    scrape_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    total_books: int = 0
    successful_downloads: int = 0


# ===== Helpers =====
def sanitize_filename(name: str) -> str:
    """
    Convert a string to a safe filename.
    
    Args:
        name: String to sanitize
        
    Returns:
        Sanitized string for use as filename
    """
    # Replace disallowed characters with underscores
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", name)
    # Replace multiple spaces with a single space
    sanitized = re.sub(r'\s+', " ", sanitized)
    # Trim leading/trailing spaces
    return sanitized.strip()


def extract_year_from_title(title: str) -> Tuple[str, Optional[str]]:
    """
    Extract the year from a book title that may contain (YYYY) format.
    
    Args:
        title: Book title possibly containing year in parentheses
        
    Returns:
        Tuple containing cleaned title and year (or None if not found)
    """
    # Look for pattern like "Title (2014)" or similar
    match = re.search(r'(.+)\s*\((\d{4})\)', title)
    if match:
        return match.group(1).strip(), match.group(2)
    return title, None


def parse_date(date_text: str) -> str:
    """
    Parse a date string and return it in a standardized format.
    
    Args:
        date_text: Date text to parse (e.g., "Aug 19th, 2014")
        
    Returns:
        Standardized date string (YYYY-MM-DD) or original if parsing fails
    """
    try:
        # Try to parse date with various formats
        formats = [
            "%b %dst, %Y",  # Aug 1st, 2014
            "%b %dnd, %Y",  # Aug 2nd, 2014
            "%b %drd, %Y",  # Aug 3rd, 2014
            "%b %dth, %Y",  # Aug 4th, 2014
            "%B %dst, %Y",  # August 1st, 2014
            "%B %dnd, %Y",  # August 2nd, 2014
            "%B %drd, %Y",  # August 3rd, 2014
            "%B %dth, %Y",  # August 4th, 2014
        ]
        
        # Remove any ordinal indicators for consistent parsing
        cleaned_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_text)
        
        # Try each format
        for fmt in formats:
            cleaned_fmt = re.sub(r'%(d)(st|nd|rd|th)', r'%\1', fmt)
            try:
                dt = datetime.strptime(cleaned_date, cleaned_fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
                
        return date_text  # Return original if parsing fails
    except Exception as e:
        logger.warning(f"Error parsing date '{date_text}': {e}")
        return date_text


def wait_and_click(driver: Any, element_or_selector: Any, timeout: int = 10, by: By = By.CSS_SELECTOR) -> bool:
    """
    Wait for an element to be clickable and click it.
    
    Args:
        driver: Browser driver instance
        element_or_selector: Element or selector to click
        timeout: Maximum time to wait in seconds
        by: Selector type if a string is provided
        
    Returns:
        Boolean indicating success
    """
    try:
        # If a string selector is provided, find the element
        if isinstance(element_or_selector, str):
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, element_or_selector))
            )
        else:
            # If an element is provided, wait for it to be clickable
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable(element_or_selector)
            )
        
        # Try direct click
        try:
            element.click()
            logger.debug(f"Successfully clicked element using regular click")
            return True
        except Exception as e1:
            logger.debug(f"Direct click failed, trying JavaScript click: {e1}")
            
            # Try JavaScript click as fallback
            try:
                driver.execute_script("arguments[0].click();", element)
                logger.debug(f"Successfully clicked element using JavaScript")
                return True
            except Exception as e2:
                logger.warning(f"JavaScript click also failed: {e2}")
                return False
                
    except Exception as e:
        logger.warning(f"Failed to click element: {e}")
        return False


def get_windows_download_folder() -> str:
    """
    Get the default Windows downloads folder path.
    
    Returns:
        Path to the default downloads folder
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                         r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders') as key:
            download_folder = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')[0]
            return download_folder
    except Exception as e:
        logger.warning(f"Could not get Windows download folder: {e}")
        return os.path.join(os.path.expanduser("~"), "Downloads")


def configure_download_settings(driver: Any) -> bool:
    """
    Configure browser settings to ensure downloads go to the right place.
    
    Args:
        driver: Browser driver instance
        
    Returns:
        Boolean indicating success
    """
    download_dir = os.path.abspath(os.path.join("Data", "Books"))
    logger.info(f"Configuring download directory to: {download_dir}")
    
    success = False
    
    # Ensure download directory exists
    os.makedirs(download_dir, exist_ok=True)
    
    # Méthode 1: Utiliser Chrome DevTools Protocol (CDP)
    try:
        logger.info("Configuring download settings using CDP...")
        # For undetected_chromedriver / selenium 4+
        params = {
            "behavior": "allow",
            "downloadPath": download_dir
        }
        
        if hasattr(driver, "execute_cdp_cmd"):
            driver.execute_cdp_cmd("Page.setDownloadBehavior", params)
            success = True
            logger.info("Successfully configured download path using CDP")
    except Exception as e:
        logger.warning(f"CDP configuration failed: {e}")
    
    # Méthode 2: Essayer de modifier directement les préférences
    if not success:
        try:
            logger.info("Trying to modify Chrome preferences...")
            if hasattr(driver, "profile") and hasattr(driver.profile, "default_preferences"):
                driver.profile.default_preferences["download.default_directory"] = download_dir
                success = True
                logger.info("Successfully modified Chrome preferences")
        except Exception as e:
            logger.warning(f"Failed to modify Chrome preferences: {e}")
    
    # Méthode 3: Utiliser JavaScript pour configurer les téléchargements
    try:
        logger.info("Trying JavaScript approach to configure downloads...")
        driver.execute_script("""
            window.addEventListener('beforeunload', function() {
                const dlDir = arguments[0];
                if (window.chrome && chrome.downloads && chrome.downloads.setShelfEnabled) {
                    chrome.downloads.setShelfEnabled(false);
                    chrome.downloads.downloadPath = dlDir;
                }
            });
        """, download_dir)
        logger.info("Added JavaScript download handler")
    except Exception as e:
        logger.warning(f"JavaScript download configuration failed: {e}")
    
    # Retourner succès basé sur au moins une méthode réussie
    return success


def wait_for_download(directory: str, timeout: int = 120) -> Optional[str]:
    """
    Wait for a markdown file download to complete in the specified directory.
    
    Args:
        directory: Directory to monitor for downloads
        timeout: Maximum time to wait in seconds
        
    Returns:
        Path to downloaded file or None if timeout
    """
    start_time = time.time()
    
    # Trouver également le dossier de téléchargement par défaut de Windows
    default_download_folder = get_windows_download_folder()
    logger.info(f"Monitoring download directory: {directory}")
    logger.info(f"Also checking Windows default download folder: {default_download_folder}")
    
    # Get initial list of .md files
    initial_files_dir = set([f for f in os.listdir(directory) if f.endswith('.md')])
    initial_files_default = set()
    
    if os.path.exists(default_download_folder):
        try:
            initial_files_default = set([f for f in os.listdir(default_download_folder) if f.endswith('.md')])
        except Exception as e:
            logger.warning(f"Error accessing default download folder: {e}")
    
    logger.info(f"Initial MD files in target: {len(initial_files_dir)}, in default: {len(initial_files_default)}")
    
    # Ajouter un compteur pour limiter les logs
    log_interval = 10  # Log toutes les 10 secondes
    last_log_time = 0
    
    while time.time() - start_time < timeout:
        elapsed = time.time() - start_time
        
        # Limiter les logs pour éviter de spammer
        if time.time() - last_log_time > log_interval:
            logger.info(f"Still waiting for download... ({int(elapsed)}s elapsed)")
            last_log_time = time.time()
        
        # Check for new .md files in target directory
        try:
            current_files_dir = set([f for f in os.listdir(directory) if f.endswith('.md')])
            new_files_dir = current_files_dir - initial_files_dir
            
            if new_files_dir:
                # Get the most recently modified file
                newest_file = max(new_files_dir, key=lambda f: os.path.getmtime(os.path.join(directory, f)))
                file_path = os.path.join(directory, newest_file)
                file_size = os.path.getsize(file_path)
                
                # Si le fichier est vide ou très petit, attendre qu'il grossisse
                if file_size < 100:  # Moins de 100 octets
                    logger.info(f"Found new file but it's too small ({file_size} bytes), waiting for download to complete")
                    time.sleep(1)
                    continue
                
                logger.info(f"Download completed in target directory: {file_path} ({file_size} bytes)")
                return file_path
                
            # Check also in default Windows download folder
            if os.path.exists(default_download_folder):
                current_files_default = set([f for f in os.listdir(default_download_folder) if f.endswith('.md')])
                new_files_default = current_files_default - initial_files_default
                
                if new_files_default:
                    newest_file = max(new_files_default, key=lambda f: os.path.getmtime(os.path.join(default_download_folder, f)))
                    default_path = os.path.join(default_download_folder, newest_file)
                    file_size = os.path.getsize(default_path)
                    
                    # Vérifier également la taille ici
                    if file_size < 100:
                        logger.info(f"Found new file in default folder but it's too small ({file_size} bytes), waiting")
                        time.sleep(1)
                        continue
                    
                    # Copier le fichier vers notre cible
                    target_path = os.path.join(directory, newest_file)
                    logger.info(f"Found download in Windows download folder: {default_path} ({file_size} bytes)")
                    logger.info(f"Copying to target location: {target_path}")
                    
                    try:
                        shutil.copy2(default_path, target_path)
                        logger.info("File copied successfully")
                        return target_path
                    except Exception as e:
                        logger.error(f"Error copying file: {e}")
                        return default_path
        except Exception as e:
            logger.warning(f"Error checking for downloads: {e}")
        
        # Vérifier si le navigateur est toujours en cours de téléchargement
        if elapsed > 30 and elapsed % 30 < 1:  # Toutes les 30 secondes environ
            logger.info("Checking browser download status...")
            
            # Réinitialiser le timeout pour éviter de bloquer indéfiniment
            if elapsed > 60:  # Si plus d'une minute s'est écoulée
                logger.warning("Download is taking too long, considering it failed")
                return None
        
        # Short delay before checking again
        time.sleep(1)
    
    logger.warning(f"Download timeout after {timeout} seconds")
    
    # Dernier essai pour chercher dans les répertoires
    try:
        logger.info("Performing one final check for downloaded files...")
        
        # Vérifier le répertoire cible une dernière fois
        current_files_dir = set([f for f in os.listdir(directory) if f.endswith('.md')])
        new_files_dir = current_files_dir - initial_files_dir
        
        if new_files_dir:
            newest_file = max(new_files_dir, key=lambda f: os.path.getmtime(os.path.join(directory, f)))
            return os.path.join(directory, newest_file)
            
        # Vérifier également le répertoire de téléchargement par défaut
        if os.path.exists(default_download_folder):
            current_files_default = set([f for f in os.listdir(default_download_folder) if f.endswith('.md')])
            new_files_default = current_files_default - initial_files_default
            
            if new_files_default:
                newest_file = max(new_files_default, key=lambda f: os.path.getmtime(os.path.join(default_download_folder, f)))
                default_path = os.path.join(default_download_folder, newest_file)
                
                # Copier le fichier vers notre cible
                target_path = os.path.join(directory, newest_file)
                logger.info(f"Found download in Windows download folder after timeout: {default_path}")
                logger.info(f"Copying to target location: {target_path}")
                
                try:
                    shutil.copy2(default_path, target_path)
                    logger.info("File copied successfully after timeout")
                    return target_path
                except Exception as e:
                    logger.error(f"Error copying file after timeout: {e}")
                    return default_path
    except Exception as e:
        logger.warning(f"Error during final check: {e}")
        
    return None


def extract_book_metadata(book_element: Any, driver: Any = None) -> Optional[BookMetadata]:
    """
    Extract metadata from a book element in the list.
    
    Args:
        book_element: Element representing a book in the list
        driver: Browser driver instance for JavaScript execution
        
    Returns:
        BookMetadata object or None if extraction fails
    """
    try:
        # Get URL (href attribute)
        url = book_element.get_attribute('href')
        
        # Essayons d'abord de comprendre la structure en loggant tout le texte
        full_text = book_element.text.strip()
        # Remplacer le caractère spécial [ʟ] qui cause des problèmes d'encodage
        full_text = full_text.replace('[ʟ]', '[L]')
        logger.info(f"Book element full text: {full_text}")
        
        # Analyser plus intelligemment le texte pour extraire les métadonnées
        # La structure habituelle est: Type (Legacy) | Title (Year) | Date
        text_parts = full_text.split('\n')
        text_parts = [part.strip() for part in text_parts if part.strip()]
        
        # Log les parties du texte pour débogage
        logger.info(f"Text parts after splitting: {text_parts}")
        
        book_type = ""
        book_title = ""
        publication_date = ""
        
        # Extraire les métadonnées selon le nombre de parties trouvées
        if len(text_parts) >= 3:
            # Format typique avec 3 parties distinctes
            book_type = text_parts[0]
            book_title = text_parts[1]
            publication_date = text_parts[2]
        elif len(text_parts) == 2:
            # Essayer d'extraire en supposant: Type | Title+Date
            book_type = text_parts[0]
            
            # Le titre et la date peuvent être dans la seconde partie
            second_part = text_parts[1]
            date_match = re.search(r'(\w+\s+\d+(?:st|nd|rd|th)?,\s+\d{4})', second_part)
            if date_match:
                publication_date = date_match.group(1)
                book_title = second_part.replace(publication_date, '').strip()
            else:
                book_title = second_part
        elif len(text_parts) == 1:
            # Dernière tentative avec un seul bloc de texte
            text = text_parts[0]
            
            # Chercher une date au format "MMM DD, YYYY"
            date_match = re.search(r'(\w+\s+\d+(?:st|nd|rd|th)?,\s+\d{4})', text)
            if date_match:
                publication_date = date_match.group(1)
                text = text.replace(publication_date, '')
            
            # Chercher un titre avec année entre parenthèses
            title_match = re.search(r'([^()]+\(\d{4}\))', text)
            if title_match:
                book_title = title_match.group(1).strip()
                text = text.replace(book_title, '')
            
            # Le reste pourrait être le type
            book_type = text.strip()
            
            # Si on n'a toujours pas de titre mais un type long
            if not book_title and len(book_type) > 20:
                parts = book_type.split(' ', 1)
                if len(parts) > 1:
                    book_type = parts[0]
                    book_title = parts[1]
        
        # Remplacer tous les caractères [ʟ] par [L] pour éviter les problèmes d'encodage
        book_type = book_type.replace('[ʟ]', '[L]')
        book_title = book_title.replace('[ʟ]', '[L]')
        
        # Vérifier si nous avons un marqueur legacy
        is_legacy = '[L]' in book_type or '[ʟ]' in book_type
        book_type = book_type.replace('[L]', '').strip()
        
        # Nettoyer le titre s'il contient encore des éléments du type
        if is_legacy and ('[L]' in book_title or '[ʟ]' in book_title):
            book_title = book_title.replace('[L]', '').replace('[ʟ]', '').strip()
        
        # Vérifier si le titre est plus long que le type (inversion possible)
        if len(book_type) > len(book_title) and "Handbook" in book_type:
            # Probablement une inversion titre/type
            temp = book_title
            book_title = book_type
            book_type = temp
        
        # Log les valeurs extraites pour débogage
        logger.info(f"Extracted directly: Type='{book_type}', Title='{book_title}', Date='{publication_date}'")
        
        # Extract year from title if present
        title, year = extract_year_from_title(book_title)
        logger.info(f"After title processing: Title='{title}', Year='{year}'")
        
        # Traiter le cas où publication_date est vide
        if not publication_date or publication_date.strip() == '':
            if year:
                publication_date = f"{year}-01-01"  # Utiliser l'année du titre si disponible
                logger.info(f"Using year from title for publication date: {publication_date}")
            else:
                publication_date = "Unknown"
                logger.info("Using 'Unknown' as publication date")
        
        # Create metadata object
        metadata = BookMetadata(
            name=title,
            type=book_type,
            publication_date=parse_date(publication_date),
            url=url,
            is_legacy=is_legacy
        )
        
        logger.info(f"Final metadata: {metadata.name} ({metadata.type}) - {metadata.publication_date}")
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting book metadata: {e}")
        logger.debug(traceback.format_exc())
        return None


def download_book_as_markdown(driver: Any, book: BookMetadata) -> bool:
    """
    Download a book as markdown.
    
    Args:
        driver: Browser driver instance
        book: BookMetadata object
        
    Returns:
        Boolean indicating success
    """
    try:
        # Create safe filename for the download
        year = book.publication_date.split("-")[0] if "-" in book.publication_date else ""
        
        # Générer deux formats possibles de noms de fichiers
        safe_name_underscore = sanitize_filename(f"{book.name}_{year}")
        safe_name_parentheses = sanitize_filename(f"{book.name} ({year})")
        
        # Différentes possibilités de chemins de fichiers
        possible_filenames = [
            f"{safe_name_underscore}.md",
            f"{safe_name_parentheses}.md",
            f"{sanitize_filename(book.name)}.md"
        ]
        
        # Chemin de base pour les livres
        books_dir = os.path.join("Data", "Books")
        absolute_books_dir = os.path.abspath(books_dir)
        
        # Vérifier si un des fichiers existe déjà
        logger.info(f"Checking for existing files with possible names:")
        for filename in possible_filenames:
            filepath = os.path.join(books_dir, filename)
            abs_filepath = os.path.join(absolute_books_dir, filename)
            logger.info(f"  - Checking: {abs_filepath}")
            
            if os.path.exists(filepath) or os.path.exists(abs_filepath):
                existing_path = abs_filepath if os.path.exists(abs_filepath) else filepath
                logger.info(f"File already exists at {existing_path}, marking as downloaded")
                book.download_path = existing_path
                book.download_success = True
                return True
        
        # Si aucun des fichiers n'a été trouvé, utiliser le format avec parenthèses
        # car c'est celui qui semble être actuellement utilisé
        download_path = os.path.normpath(os.path.join(books_dir, f"{safe_name_parentheses}.md"))
        book.download_path = download_path
        
        # Vérifier également dans le dossier de téléchargement par défaut
        default_download_folder = get_windows_download_folder()
        
        # Vérifier chaque format dans le dossier de téléchargement par défaut
        for filename in possible_filenames:
            default_path = os.path.join(default_download_folder, filename)
            logger.info(f"Checking default downloads for: {default_path}")
            
            if os.path.exists(default_path):
                logger.info(f"File already exists in default download folder: {default_path}")
                logger.info(f"Copying to: {download_path}")
                try:
                    # S'assurer que le dossier de destination existe
                    os.makedirs(os.path.dirname(download_path), exist_ok=True)
                    shutil.copy2(default_path, download_path)
                    book.download_success = True
                    return True
                except Exception as e:
                    logger.warning(f"Failed to copy existing file: {e}")
        
        # Si le fichier n'existe pas, procéder au téléchargement
        logger.info(f"File not found, proceeding with download to: {download_path}")
        
        # Configure download settings before navigating to book page
        configure_download_settings(driver)
        
        # 2. Cliquer sur le livre (navigation vers l'URL)
        if not book.url.startswith("http"):
            # Convert relative URL to absolute
            base_url = "https://5e.tools/"
            full_url = base_url + book.url
        else:
            full_url = book.url
            
        logger.info(f"Navigating to book URL: {full_url}")
        driver.get(full_url)
        
        # 3. Attendre que le message "Loading..." disparaisse
        logger.info("Waiting for loading message to disappear...")
        try:
            WebDriverWait(driver, 30).until_not(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span.initial-message"))
            )
            logger.info("Book content loaded successfully")
        except TimeoutException:
            logger.warning("Timeout waiting for book content to load, continuing anyway")
        
        # Attendre un peu plus pour s'assurer que tout est chargé
        time.sleep(5)
        
        # Vérifier à nouveau si l'un des fichiers possibles est apparu après navigation
        for filename in possible_filenames:
            filepath = os.path.join(books_dir, filename)
            abs_filepath = os.path.join(absolute_books_dir, filename)
            
            if os.path.exists(filepath) or os.path.exists(abs_filepath):
                existing_path = abs_filepath if os.path.exists(abs_filepath) else filepath
                logger.info(f"File appeared at {existing_path} after navigation, no need to download")
                book.download_path = existing_path
                book.download_success = True
                return True
        
        # 4. Cliquer sur le bouton d'options
        logger.info("Clicking options button...")
        options_button_found = False
        
        # Essayer différents sélecteurs pour le bouton d'options
        options_selectors = [
            "button.ve-btn-default[title='Other Options']",
            "button.ve-btn.ve-btn-xs.ve-btn-default",
            "button.ve-btn-default",
            "span.glyphicon.glyphicon-option-vertical"
        ]
        
        for selector in options_selectors:
            try:
                options_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                logger.info(f"Found {len(options_elements)} potential options buttons with selector: {selector}")
                
                for element in options_elements:
                    try:
                        # Utiliser JavaScript pour cliquer (plus fiable)
                        driver.execute_script("arguments[0].click();", element)
                        logger.info(f"Clicked options button with selector: {selector}")
                        options_button_found = True
                        time.sleep(2)  # Attendre que le menu s'affiche
                        break
                    except Exception as e:
                        logger.debug(f"Click failed on element: {e}")
            except Exception as e:
                logger.debug(f"Selector failed: {selector} - {e}")
                
            if options_button_found:
                break
        
        if not options_button_found:
            # Essayer via JavaScript en dernier recours
            try:
                result = driver.execute_script("""
                    // Chercher par titre
                    let btn = document.querySelector('button[title="Other Options"]');
                    if (btn) { btn.click(); return true; }
                    
                    // Chercher par icône
                    btn = document.querySelector('.glyphicon-option-vertical');
                    if (btn) { 
                        // Cliquer sur le bouton parent si c'est une icône
                        if (btn.tagName !== 'BUTTON') {
                            btn = btn.closest('button');
                        }
                        if (btn) { btn.click(); return true; }
                    }
                    
                    // Chercher par classe
                    btn = document.querySelector('.ve-btn-default');
                    if (btn) { btn.click(); return true; }
                    
                    return false;
                """)
                
                if result:
                    logger.info("Found and clicked options button via JavaScript")
                    options_button_found = True
                    time.sleep(2)
            except Exception as e:
                logger.error(f"JavaScript click failed: {e}")
        
        if not options_button_found:
            logger.error("Could not find or click options button")
            return False
        
        # 5. Cliquer sur "Download Book as Markdown"
        logger.info("Looking for 'Download Book as Markdown' option...")
        download_clicked = False
        
        # Essayer d'abord par XPath pour le texte exact
        try:
            download_buttons = driver.find_elements(By.XPATH, "//div[contains(text(), 'Download Book as Markdown')]")
            if download_buttons:
                logger.info(f"Found {len(download_buttons)} download buttons by exact text")
                for btn in download_buttons:
                    try:
                        driver.execute_script("arguments[0].click();", btn)
                        logger.info("Clicked download button via exact text match")
                        download_clicked = True
                        break
                    except Exception as e:
                        logger.debug(f"Click failed: {e}")
        except Exception as e:
            logger.warning(f"XPath search failed: {e}")
        
        # Essayer par sélecteur CSS + vérification de texte
        if not download_clicked:
            try:
                menu_buttons = driver.find_elements(By.CSS_SELECTOR, "div.ui-ctx__btn, div.w-100.ui-ctx__btn, div.ui-ctx__inner div")
                logger.info(f"Found {len(menu_buttons)} menu buttons")
                
                for btn in menu_buttons:
                    try:
                        btn_text = btn.text.strip()
                        logger.info(f"Button text: '{btn_text}'")
                        
                        if "Download Book as Markdown" in btn_text or "Download" in btn_text:
                            driver.execute_script("arguments[0].click();", btn)
                            logger.info(f"Clicked button with text: '{btn_text}'")
                            download_clicked = True
                            break
                    except Exception as e:
                        logger.debug(f"Button processing failed: {e}")
            except Exception as e:
                logger.warning(f"Menu button search failed: {e}")
        
        # JavaScript en dernier recours si aucun bouton n'a été trouvé
        if not download_clicked:
            try:
                result = driver.execute_script("""
                    // Function to check if an element contains download text
                    function containsDownloadText(elem) {
                        return elem.textContent && (
                            elem.textContent.includes('Download Book as Markdown') || 
                            (elem.textContent.includes('Download') && elem.textContent.includes('Markdown'))
                        );
                    }
                    
                    // Try finding by text content
                    const allElements = document.querySelectorAll('div, span, button, a');
                    for (const elem of allElements) {
                        if (containsDownloadText(elem)) {
                            console.log('Found by text content:', elem.textContent);
                            elem.click();
                            return 'Found by text content';
                        }
                    }
                    
                    // Look specifically at menu items
                    const menuItems = document.querySelectorAll('.ui-ctx__btn, .ui-ctx__inner div');
                    for (const item of menuItems) {
                        if (item.textContent && item.textContent.includes('Download')) {
                            console.log('Found by partial match:', item.textContent);
                            item.click();
                            return 'Found by partial match';
                        }
                    }
                    
                    return false;
                """)
                
                if result:
                    logger.info(f"JavaScript download approach succeeded: {result}")
                    download_clicked = True
            except Exception as e:
                logger.error(f"JavaScript download attempt failed: {e}")
        
        # Attendre le téléchargement
        logger.info("Waiting for download to start...")
        
        # Comme le clic peut avoir fonctionné même si nous ne l'avons pas détecté, attendre de toute façon
        time.sleep(3)
        
        # Vérifier fréquemment si le fichier est apparu après avoir cliqué
        start_time = time.time()
        max_check_time = 60  # Attendre maximum 60 secondes
        
        # Chercher le fichier dans plusieurs endroits, avec différentes variations du chemin
        possible_paths = []
        
        # Ajouter tous les chemins possibles pour tous les formats de noms de fichiers
        for filename in possible_filenames:
            # Chemins absolus basés sur le répertoire Data/Books
            possible_paths.append(os.path.join(absolute_books_dir, filename))
            # Chemins relatifs basés sur Data/Books
            possible_paths.append(os.path.join(books_dir, filename))
            # Chemins dans le répertoire de téléchargement par défaut
            possible_paths.append(os.path.join(default_download_folder, filename))
        
        # Journaliser tous les chemins que nous vérifions
        logger.info("Checking following paths for downloaded file:")
        for i, path in enumerate(possible_paths):
            logger.info(f"  Path {i+1}: {path}")
        
        while time.time() - start_time < max_check_time:
            # Vérifier toutes les variations de chemins
            for path in possible_paths:
                if os.path.exists(path):
                    file_size = os.path.getsize(path)
                    if file_size > 100:  # S'assurer que le fichier n'est pas vide
                        logger.info(f"File found at {path} ({file_size} bytes)")
                        
                        # Si ce n'est pas le chemin cible, copier le fichier
                        if not path.startswith(absolute_books_dir) and not path.startswith(books_dir):
                            try:
                                logger.info(f"Copying from {path} to {download_path}")
                                # S'assurer que le répertoire existe
                                os.makedirs(os.path.dirname(download_path), exist_ok=True)
                                shutil.copy2(path, download_path)
                                book.download_path = download_path
                            except Exception as e:
                                logger.error(f"Error copying file: {e}")
                                # Utiliser le chemin où le fichier a été trouvé
                                book.download_path = path
                        else:
                            book.download_path = path
                        
                        book.download_success = True
                        logger.info(f"Successfully downloaded: {book.name}")
                        return True
            
            # Pause brève avant la prochaine vérification
            time.sleep(2)
            
            # Log périodique pour éviter de spammer
            elapsed = time.time() - start_time
            if int(elapsed) % 10 == 0:
                logger.info(f"Still waiting for file to appear... ({int(elapsed)}s elapsed)")
                # Liste les fichiers dans le répertoire cible pour débogage
                if os.path.exists(absolute_books_dir):
                    files = os.listdir(absolute_books_dir)
                    logger.info(f"Files in {absolute_books_dir}: {files}")
                # Liste les fichiers dans le répertoire de téléchargement par défaut
                if os.path.exists(default_download_folder):
                    default_files = [f for f in os.listdir(default_download_folder) if f.endswith('.md')]
                    if default_files:
                        logger.info(f"MD files in default download folder: {default_files}")
        
        logger.warning(f"Download timeout after {max_check_time} seconds")
        
        # Faire une dernière vérification plus approfondie
        logger.info("Performing final deep search for downloaded file...")
        
        # Dernier effort: vérifier si des fichiers MD existent dans les répertoires et contiennent le nom du livre
        target_dirs = [books_dir, absolute_books_dir, default_download_folder]
        book_name_lower = book.name.lower()
        
        for target_dir in target_dirs:
            if not os.path.exists(target_dir):
                continue
                
            try:
                md_files = [f for f in os.listdir(target_dir) if f.endswith('.md')]
                for md_file in md_files:
                    # Si le nom du fichier contient le nom du livre, c'est probablement ce que nous cherchons
                    if book_name_lower in md_file.lower():
                        file_path = os.path.join(target_dir, md_file)
                        logger.info(f"Found probable match by book name: {file_path}")
                        
                        if target_dir != absolute_books_dir and target_dir != books_dir:
                            try:
                                # Copier vers le répertoire cible
                                shutil.copy2(file_path, download_path)
                                book.download_path = download_path
                            except Exception as e:
                                logger.error(f"Error copying file: {e}")
                                book.download_path = file_path
                        else:
                            book.download_path = file_path
                        
                        book.download_success = True
                        return True
            except Exception as e:
                logger.warning(f"Error checking directory {target_dir}: {e}")
        
        return False
            
    except Exception as e:
        logger.error(f"Error downloading book as markdown: {e}")
        logger.debug(traceback.format_exc())
        return False


def save_metadata(books_data: BooksData) -> None:
    """
    Save metadata for all books.
    
    Args:
        books_data: BooksData object containing metadata for all books
    """
    try:
        # Calculate statistics
        books_data.total_books = len(books_data.books)
        books_data.successful_downloads = sum(1 for book in books_data.books if book.download_success)
        
        # Convert to dictionary
        data_dict = asdict(books_data)
        
        # Save to JSON file
        output_path = os.path.join("Data", "Books", "MetadataBooks.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Saved metadata for {books_data.total_books} books to {output_path}")
        logger.info(f"Successfully downloaded {books_data.successful_downloads}/{books_data.total_books} books")
        
    except Exception as e:
        logger.error(f"Error saving metadata: {e}")
        logger.debug(traceback.format_exc())


def navigate_to_all_books(driver: Any, wait: WebDriverWait) -> bool:
    """
    Navigate to the 'All Books' page.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
        
    Returns:
        Boolean indicating success
    """
    logger.info("Attempting to navigate back to the 'All Books' page...")
    
    # Vérifier d'abord si nous sommes sur une page de livre spécifique ou déjà sur la liste
    try:
        # Vérifier si nous sommes sur une page de livre en cherchant le titre h1
        book_title_elements = driver.find_elements(By.CSS_SELECTOR, "h1.page__title")
        if book_title_elements:
            current_page_title = book_title_elements[0].text
            logger.info(f"Currently on a book page: '{current_page_title}'")
            
            # Nous devons revenir à la liste des livres
            is_on_book_page = True
        else:
            # Vérifier si nous sommes déjà sur la page de liste des livres
            books_container = driver.find_elements(By.CSS_SELECTOR, "div.list.list--stats.books")
            if books_container:
                logger.info("Already on the books list page, no need to navigate")
                time.sleep(2)  # Attendre que la page soit complètement chargée
                return True
            
            # Si nous ne sommes ni sur une page de livre ni sur la liste, situation inconnue
            logger.warning("Not on a book page or books list, trying to navigate to books list")
            is_on_book_page = False
    except Exception as e:
        logger.debug(f"Error detecting current page: {e}")
        is_on_book_page = False
    
    # Méthode 1: Si nous sommes sur une page de livre, chercher directement le lien "All Books"
    if is_on_book_page:
        try:
            # Les liens "All Books" ont souvent un caractère spécial et apparaissent en haut de la page
            logger.info("Looking for 'Back to All Books' link...")
            
            # Chercher par XPath avec les variations possibles du lien
            xpaths = [
                "//span[contains(text(), 'All Books')]",
                "//a[contains(text(), 'All Books')]",
                "//span[@class='bold' and contains(text(), 'All Books')]",
                "//a[@href='books.html']"
            ]
            
            for xpath in xpaths:
                all_books_elements = driver.find_elements(By.XPATH, xpath)
                if all_books_elements:
                    logger.info(f"Found {len(all_books_elements)} 'All Books' elements with xpath: {xpath}")
                    
                    # Essayer de cliquer sur le premier élément trouvé
                    try:
                        # Essayer de trouver le parent <a> pour un clic plus fiable
                        try:
                            parent_link = all_books_elements[0].find_element(By.XPATH, "./ancestor::a")
                            logger.info("Clicking on parent link")
                            driver.execute_script("arguments[0].click();", parent_link)
                        except Exception:
                            # Sinon, cliquer directement sur l'élément
                            logger.info("Clicking directly on element")
                            driver.execute_script("arguments[0].click();", all_books_elements[0])
                        
                        logger.info("Clicked on 'All Books' element, waiting for page to load...")
                        time.sleep(5)
                        
                        # Vérifier que nous sommes bien arrivés sur la liste des livres
                        books_container = driver.find_elements(By.CSS_SELECTOR, "div.list.list--stats.books")
                        if books_container:
                            logger.info("Successfully navigated to books list")
                            return True
                    except Exception as click_e:
                        logger.warning(f"Error clicking on element: {click_e}")
        except Exception as e:
            logger.warning(f"Error finding 'All Books' link: {e}")
    
    # Méthode 2: Utiliser un JavaScript plus complet pour trouver et cliquer sur le lien
    try:
        logger.info("Trying JavaScript to find and click 'All Books' link...")
        result = driver.execute_script("""
            // Rechercher tous les éléments qui pourraient être le lien "All Books"
            const allElements = document.querySelectorAll('a, span');
            
            // Chercher par texte
            for (const elem of allElements) {
                if (elem.textContent.includes('All Books')) {
                    console.log('Found by text:', elem.textContent);
                    
                    // Si c'est un lien, cliquer dessus
                    if (elem.tagName === 'A') {
                        elem.click();
                        return 'Clicked A element';
                    }
                    
                    // Chercher un lien parent
                    const parentLink = elem.closest('a');
                    if (parentLink) {
                        parentLink.click();
                        return 'Clicked parent A element';
                    }
                    
                    // Sinon, cliquer sur l'élément lui-même
                    elem.click();
                    return 'Clicked directly on element';
                }
            }
            
            return false;
        """)
        
        if result:
            logger.info(f"JavaScript navigation succeeded: {result}")
            time.sleep(5)
            
            # Vérifier que nous sommes bien sur la liste des livres
            books_container = driver.find_elements(By.CSS_SELECTOR, "div.list.list--stats.books")
            if books_container:
                logger.info("Successfully navigated to books list via JavaScript")
                return True
    except Exception as e:
        logger.warning(f"JavaScript navigation failed: {e}")
    
    # Méthode 3: Navigation directe vers books.html comme dernier recours
    logger.warning("Could not find or click 'All Books' link, navigating directly to books.html")
    try:
        driver.get('https://5e.tools/books.html')
        time.sleep(5)
        
        # Vérifier que nous sommes bien sur la liste des livres
        books_container = driver.find_elements(By.CSS_SELECTOR, "div.list.list--stats.books")
        if books_container:
            logger.info("Successfully navigated to books list via direct URL")
            return True
        else:
            logger.error("Navigation to books.html did not lead to books container")
            # Dernière tentative: recharger la page
            driver.refresh()
            time.sleep(5)
            return True
    except Exception as e:
        logger.error(f"Error navigating to books.html: {e}")
        return False


def process_book_one_by_one(driver: Any, wait: WebDriverWait, books_data: BooksData) -> bool:
    """
    Process books one by one: click on book, extract metadata, download, return to list.
    
    Args:
        driver: Browser driver instance
        wait: WebDriverWait instance
        books_data: BooksData object to store book information
        
    Returns:
        Boolean indicating overall success
    """
    try:
        # Attendre que la liste des livres se charge
        logger.info("Waiting for book list to load...")
        
        # Attendre que le conteneur de liste soit présent
        try:
            books_container = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.list.list--stats.books"))
            )
            logger.info("Found books container")
            
            # Attendre que le contenu se charge
            time.sleep(3)
            
            # 1. Rechercher les éléments de livre UNIQUEMENT dans ce conteneur
            logger.info("Searching for book elements ONLY within the books container...")
            
            # Obtenir le HTML du conteneur pour débogage
            container_html = driver.execute_script("return arguments[0].outerHTML;", books_container)
            # Remplacer les caractères spéciaux pour éviter les erreurs d'encodage
            container_html = container_html.replace('[ʟ]', '[L]')
            logger.debug(f"Books container HTML: {container_html[:500]}...")
            
            # Utiliser JavaScript pour sélectionner uniquement les livres directs (pas les chapitres)
            book_elements = driver.execute_script("""
                const container = arguments[0];
                // Chercher uniquement les éléments qui sont des enfants directs
                // et qui semblent être des livres (avec des spans pour type, titre, date)
                return Array.from(container.querySelectorAll('a.lst__row-border, a.lst__row'))
                    .filter(elem => {
                        // Vérifier que c'est un livre et pas un chapitre ou autre
                        const spans = elem.querySelectorAll('span');
                        // Un livre doit avoir au moins 3 spans (type, titre, date)
                        if (spans.length < 3) return false;
                        
                        // Vérifier si l'élément contient un titre de livre reconnaissable
                        const text = elem.textContent.toLowerCase();
                        const isLikelyBook = text.includes('handbook') || 
                                           text.includes('guide') || 
                                           text.includes('manual') ||
                                           text.includes('adventure') ||
                                           text.includes('monster') ||
                                           text.includes('campaign') ||
                                           text.includes('dungeon');
                        
                        return isLikelyBook;
                    });
            """, books_container)
            
            if not book_elements or len(book_elements) == 0:
                logger.warning("No books found with initial filtering, trying looser criteria...")
                book_elements = driver.execute_script("""
                    const container = arguments[0];
                    // Utiliser des critères moins stricts, mais toujours limiter aux liens
                    return Array.from(container.querySelectorAll('a.lst__row-border, a.lst__row'))
                        .filter(elem => {
                            // Tout élément ayant au moins 2 spans pourrait être un livre
                            return elem.querySelectorAll('span').length >= 2;
                        });
                """, books_container)
            
            if not book_elements or len(book_elements) == 0:
                logger.error("Could not find any book elements after multiple attempts")
                return False
                
            # Afficher chaque livre trouvé pour débogage
            book_texts = driver.execute_script("""
                return Array.from(arguments[0]).map(elem => {
                    // Remplacer les caractères spéciaux qui posent problème
                    return elem.textContent.trim().replace('[ʟ]', '[L]');
                });
            """, book_elements)
            
            logger.info(f"Found {len(book_elements)} potential book elements.")
            logger.info("Book titles found:")
            for i, text in enumerate(book_texts[:20]):  # Limiter à 20 pour éviter de spammer le log
                logger.info(f"  Book {i+1}: {text}")
            
            if len(book_texts) > 20:
                logger.info(f"  ... and {len(book_texts) - 20} more")
            
            # S'assurer que nous avons un nombre raisonnable de livres
            if len(book_elements) > 50:
                logger.warning(f"Unusually high number of books: {len(book_elements)}. Limiting to first 50.")
                book_elements = book_elements[:50]
            
        except Exception as e:
            logger.error(f"Error finding book elements: {e}")
            logger.debug(traceback.format_exc())
            return False
        
        # Créer ou charger le fichier JSON
        json_path = os.path.join("Data", "Books", "MetadataBooks.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    if "books" in existing_data and existing_data["books"]:
                        logger.info(f"Found {len(existing_data['books'])} existing books in metadata file")
                        books_data.books = [BookMetadata(**book) for book in existing_data["books"]]
                        books_data.total_books = existing_data.get("total_books", len(books_data.books))
                        books_data.successful_downloads = existing_data.get("successful_downloads", 0)
            except Exception as e:
                logger.warning(f"Error loading existing metadata: {e}")
        
        # Traiter chaque livre
        total_books = len(book_elements)
        for i in range(total_books):
            try:
                # Retourner à la liste des livres si ce n'est pas le premier livre
                if i > 0:
                    logger.info(f"Returning to book list for book {i+1}/{total_books}")
                    if not navigate_to_all_books(driver, wait):
                        logger.error(f"Failed to navigate back to book list for book {i+1}")
                        continue
                    
                    # Rafraîchir les éléments de livre
                    try:
                        books_container = wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.list.list--stats.books"))
                        )
                        
                        # Ré-extraire les éléments après navigation
                        book_elements = driver.execute_script("""
                            const container = arguments[0];
                            return Array.from(container.querySelectorAll('a.lst__row-border, a.lst__row'))
                                .filter(elem => elem.querySelectorAll('span').length >= 3);
                        """, books_container)
                        
                        if not book_elements or len(book_elements) == 0:
                            logger.error("Could not refresh book elements, trying alternate approach")
                            # Essayer un sélecteur plus simple comme dernier recours
                            book_elements = books_container.find_elements(By.CSS_SELECTOR, "a")
                            
                            if not book_elements or len(book_elements) == 0:
                                logger.error("Still could not find book elements, aborting current book")
                                continue
                    except Exception as e:
                        logger.error(f"Error refreshing book elements: {e}")
                        logger.debug(traceback.format_exc())
                        continue
                
                # S'assurer que l'index est valide
                if i >= len(book_elements):
                    logger.error(f"Book index {i} is out of range for {len(book_elements)} books")
                    continue
                
                current_book = book_elements[i]
                # Afficher le texte complet de l'élément pour débogage
                book_text = driver.execute_script("return arguments[0].textContent.trim().replace('[ʟ]', '[L]');", current_book)
                logger.info(f"Processing book {i+1}/{total_books}: {book_text}")
                
                # 1. Extraire les métadonnées
                try:
                    # Faire défiler jusqu'à l'élément pour qu'il soit visible
                    driver.execute_script("arguments[0].scrollIntoView(true);", current_book)
                    time.sleep(1)
                    
                    # Vérifier si ce livre a déjà été traité
                    book_url = current_book.get_attribute('href')
                    
                    # Extraire d'abord les métadonnées pour faire une vérification plus précise
                    metadata = extract_book_metadata(current_book, driver)
                    if not metadata:
                        logger.warning(f"Could not extract metadata for book {i+1}, skipping")
                        continue
                    
                    logger.info(f"Extracted metadata for book: {metadata.name} ({metadata.type})")
                    
                    # Vérifier si ce livre (nom et date) existe déjà dans les métadonnées
                    similar_book_exists = False
                    for existing_book in books_data.books:
                        # Vérifier le nom ET la date de publication
                        if existing_book.name == metadata.name and existing_book.publication_date == metadata.publication_date:
                            logger.info(f"Book '{metadata.name}' ({metadata.publication_date}) already processed, skipping")
                            similar_book_exists = True
                            break
                    
                    if similar_book_exists:
                        continue
                    
                    # 2. Cliquer sur le livre et télécharger
                    success = download_book_as_markdown(driver, metadata)
                    metadata.download_success = success
                    
                    if success:
                        logger.info(f"Successfully downloaded book: {metadata.name}")
                    else:
                        # Vérifier si le fichier existe déjà mais n'a pas été détecté par la fonction de téléchargement
                        year = metadata.publication_date.split("-")[0] if "-" in metadata.publication_date else ""
                        target_dir = os.path.join("Data", "Books")
                        
                        # Vérifier toutes les variations possibles du nom de fichier
                        patterns = [
                            f"{metadata.name}_{year}.md",
                            f"{metadata.name} ({year}).md",
                            f"{metadata.name}.md"
                        ]
                        
                        for pattern in patterns:
                            file_path = os.path.join(target_dir, pattern)
                            abs_file_path = os.path.abspath(file_path)
                            
                            if os.path.exists(abs_file_path):
                                logger.info(f"Found existing file with pattern: {abs_file_path}")
                                metadata.download_path = abs_file_path
                                metadata.download_success = True
                                success = True
                                break
                        
                        if not success:
                            logger.warning(f"Failed to download book: {metadata.name} and no existing file found")
                    
                    # Ajouter aux données et sauvegarder
                    books_data.books.append(metadata)
                    books_data.total_books = len(books_data.books)
                    books_data.successful_downloads = sum(1 for book in books_data.books if book.download_success)
                    
                    # Sauvegarder après chaque livre
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(asdict(books_data), f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"Saved metadata to JSON. Books: {books_data.total_books}, Successful: {books_data.successful_downloads}")
                    
                except Exception as e:
                    logger.error(f"Error processing book {i+1}: {e}")
                    logger.debug(traceback.format_exc())
            
            except Exception as e:
                logger.error(f"Critical error processing book {i+1}: {e}")
                logger.debug(traceback.format_exc())
        
        return True
    
    except Exception as e:
        logger.error(f"Error in process_book_one_by_one: {e}")
        logger.debug(traceback.format_exc())
        return False


def main() -> None:
    """Main function to run the book scraper"""
    # Log system information
    try:
        os_info = get_os_info()
        logger.info(f"Running on: {os_info['system']} {os_info['release']}")
    except Exception as e:
        logger.error(f"Could not get OS info: {e}")
    
    # Check package compatibility
    is_compatible, warnings = check_dependency_compatibility()
    if not is_compatible:
        logger.warning("Some package compatibility issues detected:")
        for warning in warnings:
            logger.warning(f"  {warning}")
    
    if not SELENIUM_AVAILABLE:
        logger.error("Selenium is not available. Please install it with 'pip install selenium'")
        return
    
    # Initialize browser management modules
    browser_setup = BrowserSetup(logger)
    browser_cleanup = BrowserCleanup(logger)
    cookie_handler = CookieHandler(logger)
    driver = None
    
    # Initialize books data container
    books_data = BooksData()
    
    try:
        # Get driver
        driver = browser_setup.get_driver()
        
        # Register browser for automatic cleanup
        browser_cleanup.register_browser(driver)
        
        # Configure browser settings from config
        timeout = config.get("browser.page_load_timeout", 120)  # Increased timeout
        driver.set_page_load_timeout(timeout)
        
        # Configurer les préférences de téléchargement avant toute navigation
        configure_download_settings(driver)
        
        # Navigate to target page - start with books.html
        driver.get('https://5e.tools/books.html')  # Changé pour accéder à la page de liste des livres
        logger.info("Loading books page...")
        time.sleep(10)  # Augmenter le temps d'attente initial à 10 secondes
        
        # Handle cookie consent if present
        if cookie_handler.handle_consent(driver):
            logger.info("Cookie consent handled.")
            time.sleep(2)  # Attendre après avoir traité les cookies
        
        # Reconfigurer les préférences de téléchargement après consentement des cookies
        configure_download_settings(driver)
        
        # Créer WebDriverWait une seule fois
        wait = WebDriverWait(driver, 30)
        
        # Naviguer vers "All Books" pour la première fois
        if not navigate_to_all_books(driver, wait):
            logger.warning("Could not navigate to All Books initially, but will try to continue")
        
        # Traiter les livres un par un
        process_book_one_by_one(driver, wait, books_data)
        
        # Assurer que les données finales sont sauvegardées
        save_metadata(books_data)
        
        logger.info("Book scraping completed")
        
    except Exception as e:
        logger.error(f"Main error: {e}")
        logger.debug(traceback.format_exc())
    finally:
        # Save metadata even if an error occurred
        if books_data and books_data.books:
            save_metadata(books_data)
            
        # Clean up browser with enhanced method
        if driver:
            ensure_browser_cleanup(driver, logger)


if __name__ == "__main__":
    main() 
    main() 