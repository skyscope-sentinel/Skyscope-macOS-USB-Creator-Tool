import plistlib
import subprocess
import pathlib
import shutil
import json
from io import BytesIO
import datetime
import sys
import os
import tempfile
import time
from urllib.parse import urlparse

# --- Global Constants ---
SCRIPT_NAME_SLUG = "Skyscope_macOS_Creator"
DOWNLOAD_CACHE_DIR = pathlib.Path.home() / ".cache" / SCRIPT_NAME_SLUG / "downloads"
CATALOG_CACHE_DIR = pathlib.Path.home() / ".cache" / SCRIPT_NAME_SLUG / "catalogs"
selected_version_key_for_global_context = None


# --- Tool Dependencies ---
# (omitted for brevity, same as before)

# --- Utility Class ---
class Utils:
    def __init__(self):
        self.script_name_slug = SCRIPT_NAME_SLUG
    def cprint(self, text, color=None, **kwargs):
        # Basic color mapping
        if color == "red": print(f"ERROR: {text}")
        elif color == "yellow": print(f"WARNING: {text}")
        elif color == "header": print(f"\n--- {text} ---")
        elif color == "green": print(text)
        elif color == "cyan": print(text)
        else: print(text)
    def head(self, text, color="green"):
        print(f"\n{'='*10} {text} {'='*10}")

# --- Downloader Class (Stub for now) ---
class Downloader:
    def __init__(self, utils_instance):
        self.u = utils_instance
    def get_content(self, url):
        self.u.cprint(f"Simulating download (bytes) of: {url}", "green")
        if "sucatalog" in url: return self._get_sample_sucatalog_content()
        elif url.endswith(".dist"): return self._get_sample_dist_content(url)
        elif "api.github.com/repos/acidanthera/OpenCorePkg" in url:
            return json.dumps({
                "assets": [{"name": "OpenCore-0.9.7-RELEASE.zip", "browser_download_url": "https://example.com/OpenCore-0.9.7-RELEASE.zip"}]
            }).encode()
        elif "api.github.com/repos/CloverHackyColor/CloverBootloader" in url: # More specific asset names
            return json.dumps({
                "assets": [
                    {"name": "CloverV2-5155.tar.lzma", "browser_download_url": "https://example.com/CloverV2-5155.tar.lzma"},
                    {"name": "Clover-5155-X64.iso", "browser_download_url": "https://example.com/Clover-5155-X64.iso"},
                    {"name": "Clover.pkg", "browser_download_url": "https://example.com/Clover.pkg"}
                ]
            }).encode()
        self.u.cprint(f"  No stubbed content for URL: {url}", "yellow"); return None

    def get_string(self, url):
        content_bytes = self.get_content(url)
        if content_bytes:
            try: return content_bytes.decode('utf-8')
            except UnicodeDecodeError: self.u.cprint(f"Failed to decode content from {url} as UTF-8.", "red"); return None
        return None
    def _get_sample_sucatalog_content(self): return b"""<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>Products</key><dict><key>012-34567</key><dict><key>PostDate</key><date>2023-10-26T19:39:37Z</date><key>DistributionURL</key><string>https://example.com/012-34567.dist</string><key>Packages</key><array><dict><key>Size</key><integer>12000000000</integer><key>URL</key><string>https://example.com/InstallAssistant.pkg</string></dict></array><key>ExtendedMetaInfo</key><dict><key>InstallAssistantPackageIdentifiers</key><dict><key>OSInstall</key><string>com.apple.mpkg.OSInstall</string></dict></dict><key>BuildVersion</key><string>23B74</string><key>DisplayVersion</key><string>14.1</string><key>LocalizedDescriptions</key><dict><key>en</key><dict><key>Title</key><string>macOS Sonoma</string></dict></dict></dict></dict></dict></plist>"""
    def _get_sample_dist_content(self, url):
        if "012-34567" in url: return b"""<?xml version="1.0" encoding="utf-8"?><installer-script minSpecVersion="1.0"><title>macOS Sonoma from Dist</title><auxinfo><macOSProductBuildVersion>23B2074</macOSProductBuildVersion><macOSProductVersion>14.1.1</macOSProductVersion></auxinfo></installer-script>"""
        return b"<installer-script></installer-script>"
    def stream_to_file(self, url, destination_path, max_retries=3, initial_backoff=1, total_size_override=None):
        self.u.cprint(f"  Starting download of '{os.path.basename(str(destination_path))}' from {url}", "green")
        self.u.cprint(f"  Target: {destination_path}", "green")
        try:
            pathlib.Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
            # Simulate file download for bootloaders as well
            if "example.com/OpenCore" in url or "example.com/Clover" in url :
                 with open(destination_path, 'wb') as f: f.write(b"Simulated ZIP/PKG/ISO/TAR content for " + os.path.basename(str(destination_path)).encode())
            else: # Existing simulation for macOS installers
                total_simulated_size = total_size_override if total_size_override else 100 * 1024 * 1024
                downloaded_size = 0; spinner_chars = ['|', '/', '-', '\\']
                for i in range(10):
                    time.sleep(0.05); downloaded_size += total_simulated_size / 10
                    percentage = min((downloaded_size / total_simulated_size) * 100, 100) if total_simulated_size > 0 else 100
                    bar = '#' * int(40*percentage/100) + '-' * (40-int(40*percentage/100))
                    sys.stdout.write(f"\r  Downloading... {spinner_chars[i % len(spinner_chars)]} [{bar}] {percentage:>6.2f}%"); sys.stdout.flush()
                with open(destination_path, 'wb') as f: f.write(b"Simulated: " + os.path.basename(str(destination_path)).encode())
            sys.stdout.write('\n'); self.u.cprint(f"  Successfully simulated download to '{destination_path}'.", "green")
            return True
        except Exception as e:
            sys.stdout.write('\n'); self.u.cprint(f"  Error during simulated download for {destination_path}: {e}", "red")
            return False

# --- Catalog Manager (Content largely unchanged) ---
class CatalogManager:
    def __init__(self, utils_instance, downloader_instance):
        self.u = utils_instance; self.d = downloader_instance; self.catalog_data = None
        self.products = {}; self.raw_catalog_content_bytes = None
        self.catalog_base_url = "https://swscan.apple.com/content/catalogs/others/"
        self.catalog_suffixes = {"publicrelease": "", "customerseed": "beta", "publicbeta": "beta", "developerbeta": "seed", "developersseed": "seed"}
        self.mac_os_names_url = { 8: "mountainlion", 9: "mavericks", 10: "yosemite", 11: "elcapitan", 12: "sierra", 13: "highsierra", 14: "mojave", 15: "catalina" }
        try: CATALOG_CACHE_DIR.mkdir(parents=True, exist_ok=True); DOWNLOAD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e: self.u.cprint(f"Could not create cache directories: {e}", "red")
    def _get_cache_path(self, catalog_type, major_macos_version): return CATALOG_CACHE_DIR / f"cached_{catalog_type}_{major_macos_version}.plist"
    def build_catalog_url(self, catalog_type="publicrelease", major_macos_version=19):
        catalog_suffix_str = self.catalog_suffixes.get(catalog_type.lower(), "")
        version_parts = []
        for i in range(major_macos_version, 7, -1):
            if i > 15: version_parts.append(str(i))
            else: version_parts.append(f"10.{i}")
        if catalog_suffix_str and version_parts:
            if "." in version_parts[0]: version_parts[0] = version_parts[0] + catalog_suffix_str
            else: version_parts[0] = version_parts[0] + catalog_suffix_str
        version_string_for_url = "-".join(version_parts)
        older_os_map_to_internal_ver = {v: k for k, v in self.mac_os_names_url.items()}
        processed_older_names = set()
        for i in range(min(major_macos_version,15), 7, -1):
            name_in_map = self.mac_os_names_url.get(i)
            if name_in_map: processed_older_names.add(name_in_map)
        older_os_names_to_append = ["mountainlion", "lion", "snowleopard", "leopard"]
        for name in older_os_names_to_append:
            if name not in processed_older_names and ( (name == "mountainlion" and major_macos_version >= 8) or \
                                                       (name == "lion" and major_macos_version >= 7) or \
                                                       (name == "snowleopard" and major_macos_version >=6) or \
                                                       (name == "leopard" and major_macos_version >=5) ):
                 internal_ver_for_name = older_os_map_to_internal_ver.get(name)
                 if internal_ver_for_name and (f"10.{internal_ver_for_name}" in version_parts or str(internal_ver_for_name) in version_parts):
                     continue
                 if any(vp.startswith("10.") for vp in version_parts) and name in ["mountainlion","lion","snowleopard","leopard"]:
                      if not any(name_part for name_part in older_os_names_to_append if name_part in version_string_for_url):
                         version_string_for_url += f"-{name}"
                 elif not any(name_part for name_part in older_os_names_to_append if name_part in version_string_for_url):
                      version_string_for_url += f"-{name}"
        filename = f"index-{version_string_for_url}.merged-1.sucatalog"
        return self.catalog_base_url + filename
    def _save_catalog_to_cache(self, catalog_type, major_macos_version):
        if not self.raw_catalog_content_bytes: self.u.cprint("No catalog content to save.", "yellow"); return False
        cache_path = self._get_cache_path(catalog_type, major_macos_version)
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, 'wb') as f: f.write(self.raw_catalog_content_bytes)
            self.u.cprint(f"Catalog saved to cache: {cache_path}", "green"); return True
        except IOError as e: self.u.cprint(f"Error saving catalog to cache '{cache_path}': {e}", "red")
        return False
    def fetch_catalog(self, catalog_type="publicrelease", major_macos_version=19, force_refresh=False):
        self.u.cprint(f"Fetching macOS software update catalog...", "green")
        self.u.cprint(f"  Type: {catalog_type}, Target Major Version (internal): {major_macos_version}", "green")
        self.catalog_data = None; self.products = {}; self.raw_catalog_content_bytes = None
        cache_path = self._get_cache_path(catalog_type, major_macos_version)

        if not force_refresh and cache_path.exists():
            self.u.cprint(f"Attempting to load catalog from cache: {cache_path}", "green")
            try:
                with open(cache_path, 'rb') as f: self.raw_catalog_content_bytes = f.read()
                self.catalog_data = plistlib.loads(self.raw_catalog_content_bytes)
                self.u.cprint("Successfully parsed catalog from cache.", "green"); self._parse_products(); return True
            except plistlib.InvalidFileException as e:
                 self.u.cprint(f"Cached catalog '{cache_path}' is invalid: {e}. Will try fresh download.", "red")
            except Exception as e: self.u.cprint(f"Error loading/parsing cached catalog '{cache_path}': {e}. Will try fresh download.", "red")

        if force_refresh: self.u.cprint("Forcing refresh: Downloading catalog from Apple.", "green")
        else: self.u.cprint(f"No valid cache at '{cache_path}' or refresh forced. Downloading catalog from Apple.", "green")

        url = self.build_catalog_url(catalog_type, major_macos_version)
        self.u.cprint(f"Fetching from URL: {url}", "green")
        self.raw_catalog_content_bytes = self.d.get_content(url)
        if not self.raw_catalog_content_bytes: self.u.cprint(f"Failed to download catalog from {url}. Check URL or network.", "red"); return False

        try:
            self.catalog_data = plistlib.loads(self.raw_catalog_content_bytes)
            self.u.cprint("Successfully parsed catalog from Apple.", "green")
            if not self._save_catalog_to_cache(catalog_type, major_macos_version):
                self.u.cprint("Warning: Could not save downloaded catalog to cache.", "yellow")
            self._parse_products(); return True
        except plistlib.InvalidFileException as e:
            self.u.cprint(f"Downloaded catalog from {url} is invalid: {e}", "red")
        except Exception as e: self.u.cprint(f"Error parsing downloaded catalog: {e}", "red")

        self.catalog_data = None; self.products = {}; self.raw_catalog_content_bytes = None; return False
    def _get_extended_product_info_from_dist(self, product_id, distribution_url):
        if not distribution_url: return {}
        dist_content_bytes = self.d.get_content(distribution_url)
        if not dist_content_bytes: self.u.cprint(f"  Failed to download .dist for {product_id}.", "yellow"); return {}
        try:
            dist_data = plistlib.loads(dist_content_bytes); extended_info = {}
            if isinstance(dist_data.get("auxinfo"), dict):
                if "macOSProductBuildVersion" in dist_data["auxinfo"]: extended_info["build"] = dist_data["auxinfo"]["macOSProductBuildVersion"]
                if "macOSProductVersion" in dist_data["auxinfo"]: extended_info["version"] = dist_data["auxinfo"]["macOSProductVersion"]
            if isinstance(dist_data.get("title"), str): extended_info["dist_title"] = dist_data["title"]
            elif isinstance(dist_data.get("choice"), dict) and isinstance(dist_data["choice"].get("title"), str): extended_info["dist_title"] = dist_data["choice"]["title"]
            if not extended_info.get("version") and isinstance(dist_data.get("choice"), dict) and dist_data["choice"].get("versStr"): extended_info["version"] = dist_data["choice"]["versStr"]
            return extended_info
        except plistlib.InvalidFileException as e:
            self.u.cprint(f"  Warn: .dist file for {product_id} at {distribution_url} is invalid XML/plist: {e}", "yellow")
        except Exception as e: self.u.cprint(f"  Warn: Error parsing .dist for {product_id} at {distribution_url}: {e}", "yellow")
        return {}
    def _parse_products(self):
        self.products = {};
        if not self.catalog_data or 'Products' not in self.catalog_data or not isinstance(self.catalog_data['Products'], dict):
            self.u.cprint("Catalog data or 'Products' dictionary is invalid/missing for parsing.", "red"); return
        raw_products = self.catalog_data['Products']
        self.u.cprint(f"Found {len(raw_products)} products. Parsing details (may fetch .dist files)...", "green")
        for product_id, product_data in raw_products.items():
            if not isinstance(product_data, dict): self.u.cprint(f"Skipping invalid product data for ID '{product_id}'.", "yellow"); continue
            try:
                title = "Unknown Title"
                if isinstance(product_data.get('LocalizedDescriptions'), dict):
                    lang_pack = product_data['LocalizedDescriptions'].get('en', list(product_data['LocalizedDescriptions'].values())[0] if product_data['LocalizedDescriptions'] else {})
                    if isinstance(lang_pack, dict): title = lang_pack.get('Title', "Unknown Title")
                current_product_info = {
                    "id": product_id, "title": title,
                    "version": product_data.get("DisplayVersion", "N/A"),
                    "build": product_data.get("BuildVersion", "N/A"),
                    "date": product_data.get("PostDate", datetime.date(1900,1,1)).strftime('%Y-%m-%d') if isinstance(product_data.get("PostDate"), datetime.date) else str(product_data.get("PostDate")),
                    "distribution_url": product_data.get("DistributionURL"),
                    "packages": product_data.get("Packages", []),
                    "size_bytes": sum(pkg.get("Size", 0) for pkg in product_data.get("Packages", []) if isinstance(pkg, dict)),
                    "is_full_installer": isinstance(product_data.get("ExtendedMetaInfo"), dict) and isinstance(product_data["ExtendedMetaInfo"].get("InstallAssistantPackageIdentifiers"), dict) and "OSInstall" in product_data["ExtendedMetaInfo"]["InstallAssistantPackageIdentifiers"],
                    "smd_url": product_data.get("ServerMetadataURL"), "is_manual_entry": False
                }
                if current_product_info["distribution_url"]:
                    dist_info = self._get_extended_product_info_from_dist(product_id, current_product_info["distribution_url"])
                    if dist_info.get("build"): current_product_info["build"] = dist_info["build"]
                    if dist_info.get("version"): current_product_info["version"] = dist_info["version"]
                    if dist_info.get("dist_title") and current_product_info["title"] == "Unknown Title": current_product_info["title"] = dist_info["dist_title"]
                self.products[product_id] = current_product_info
            except Exception as e: self.u.cprint(f"Error processing product '{product_id}': {e}. Skipping.", "yellow")
        self.u.cprint(f"Finished parsing. Processed {len(self.products)} products.", "green")
    def add_manual_product(self, product_id, title, version, build, date_str, url, size_gb, is_full_installer=True):
        if product_id in self.products: self.u.cprint(f"Product ID '{product_id}' exists. Manual entry overwrites.", "yellow")
        self.products[product_id] = {
            "id": product_id, "title": title, "version": version, "build": build, "date": date_str,
            "distribution_url": url,
            "packages": [{"URL": url, "Size": int(size_gb * (1024**3))} if url else []],
            "size_bytes": int(size_gb * (1024**3)),
            "is_full_installer": is_full_installer, "is_manual_entry": True, "smd_url": None
        }
        self.u.cprint(f"Manually added product: {title} (ID: {product_id})", "green")
    def _get_displayable_products(self, require_full_installer=True, search_term=None):
        if not self.products: return []
        filtered_list = [info for info in self.products.values() if not (require_full_installer and not info.get("is_full_installer"))]
        if search_term:
            st_lower = search_term.lower()
            filtered_list = [info for info in filtered_list if st_lower in info.get('title','').lower() or st_lower in info.get('build','').lower() or st_lower in info.get('version','').lower()]
        filtered_list.sort(key=lambda p: (p.get('date', '0000-00-00'), p.get('title', '')), reverse=True)
        return filtered_list
    def list_products(self, require_full_installer=True, search_term=None):
        product_list = self._get_displayable_products(require_full_installer, search_term)
        if not product_list:
            self.u.cprint(f"No products found matching criteria.", "yellow"); return
        self.u.cprint("Available macOS Installers:", "green")
        for i, prod in enumerate(product_list):
            size_gb = prod['size_bytes'] / (1024**3) if prod['size_bytes'] else 0
            manual_tag = " [Manually Added]" if prod.get("is_manual_entry") else ""
            self.u.cprint(f"  {i+1}. {prod['title']} | Ver: {prod['version']} | Build: {prod['build']} | Date: {prod['date']} | Size: {size_gb:.2f}GB{manual_tag}", "yellow" if manual_tag else "green")
    def select_product(self, require_full_installer=True):
        self.u.head("Select macOS Product")
        product_list = self._get_displayable_products(require_full_installer=require_full_installer)
        if not product_list: self.u.cprint(f"No products to select.", "yellow"); return None
        self.u.cprint("Please select a macOS product:", "green")
        for i, prod in enumerate(product_list):
            size_gb = prod['size_bytes'] / (1024**3); manual_tag = " [Manually Added]" if prod.get("is_manual_entry") else ""
            color = "yellow" if prod.get("is_manual_entry") else "green"
            self.u.cprint(f"  {i+1}. {prod['title']}{manual_tag}", color)
            self.u.cprint(f"       Ver: {prod['version']}, Build: {prod['build']}, Date: {prod['date']}, Size: {size_gb:.2f}GB", color)
        while True:
            try:
                choice_str = input("Enter product number (or 'B' to Back, 'Q' to Quit): ").strip()
                if choice_str.lower() == 'b': return "BACK"
                if choice_str.lower() == 'q': self.u.cprint("Exiting.", "yellow"); sys.exit(0)
                selected_product = product_list[int(choice_str) - 1]
                self.u.cprint(f"Selected: {selected_product['title']}", "green"); return selected_product
            except (ValueError, IndexError): self.u.cprint(f"Invalid selection. Enter number from 1 to {len(product_list)}.", "yellow")
            except Exception as e: self.u.cprint(f"Selection error: {e}", "red"); return None
    def download_product(self, product_info, download_dir_base_str):
        if not product_info or not isinstance(product_info, dict): self.u.cprint("Invalid product info for download.", "red"); return False
        title_slug = product_info.get('title', 'UnknownProduct').replace(' ', '_').replace('/', '_')
        prod_dl_dir = pathlib.Path(download_dir_base_str) / title_slug
        try: prod_dl_dir.mkdir(parents=True, exist_ok=True); self.u.cprint(f"Download dir for '{product_info.get('title')}': {prod_dl_dir}", "green")
        except OSError as e: self.u.cprint(f"Error creating download dir '{prod_dl_dir}': {e}", "red"); return False
        packages = product_info.get('packages', [])
        if not packages: self.u.cprint(f"No packages for '{product_info.get('title')}'.", "yellow"); return True
        all_ok = True
        for i, pkg_info in enumerate(packages):
            if not isinstance(pkg_info, dict) or 'URL' not in pkg_info: self.u.cprint(f"Skipping invalid package {i+1}.", "yellow"); all_ok=False; continue
            pkg_url = pkg_info['URL']; pkg_fname = os.path.basename(urlparse(pkg_url).path) or f"package_{i+1}.pkg"
            target_fp = prod_dl_dir / pkg_fname
            self.u.cprint(f"Downloading pkg {i+1}/{len(packages)}: '{pkg_fname}'...", "green")
            if not self.d.stream_to_file(url=pkg_url, destination_path=str(target_fp), total_size_override=pkg_info.get('Size')):
                self.u.cprint(f"Failed to download '{pkg_fname}'.", "red"); all_ok=False
            else: self.u.cprint(f"Package '{pkg_fname}' downloaded.", "green")
        if all_ok: self.u.cprint(f"All packages for '{product_info.get('title')}' downloaded to {prod_dl_dir}.", "green")
        else: self.u.cprint(f"Some packages for '{product_info.get('title')}' failed. Check logs.", "red")
        return all_ok
    def get_product_info(self, product_id): return self.products.get(product_id)

# --- EFI Config Manager (Content from previous step, assumed correct and truncated for brevity) ---
class EFIConfigManager:
    def __init__(self, utils_instance):
        self.u = utils_instance
        self.opencore_configs = {
            "oc_sandybridge_generic": """<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>#WARNING - 1</key><string>This is a generic Sandy Bridge Sample.plist</string><key>#WARNING - 2</key><string>Ensure you understand ALL settings before booting.</string><!-- ... (rest of Sandy Bridge plist) ... --></dict></plist>""",
            "oc_ivybridge_generic": """<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>#WARNING - 1</key><string>This is a generic Ivy Bridge Sample.plist</string><!-- ... (rest of Ivy Bridge plist) ... --></dict></plist>""",
            "oc_haswell_generic": """<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>#WARNING - 1</key><string>This is a generic Haswell Sample.plist</string><!-- ... (rest of Haswell plist) ... --></dict></plist>"""
        }
        self.clover_configs = {
            "clover_generic_intel": """<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>Boot</key><dict><key>Arguments</key><string>-v debug=0x100 keepsyms=1 alcid=1</string><!-- ... (rest of Clover plist) ... --></dict></dict></plist>"""
        }

    def get_config_plist(self, bootloader_type, architecture_key):
        self.u.cprint(f"Looking for config: {bootloader_type}, {architecture_key}", "green")
        if bootloader_type == "opencore":
            return self.opencore_configs.get(architecture_key)
        elif bootloader_type == "clover":
            return self.clover_configs.get(architecture_key)
        return None

    def get_available_architectures(self, bootloader_type):
        if bootloader_type == "opencore":
            return list(self.opencore_configs.keys())
        elif bootloader_type == "clover":
            return list(self.clover_configs.keys())
        return []

# --- Main Application Class (SkyscopeTool) ---
class SkyscopeTool:
    def __init__(self):
        self.u = Utils()
        self.efi_cfg_mgr = EFIConfigManager(self.u)
        self.d = Downloader(self.u)
        self.cm = CatalogManager(self.u, self.d)
        self.main_download_cache_dir = DOWNLOAD_CACHE_DIR
        self.temp_dir_base = DOWNLOAD_CACHE_DIR / "temp_extractions"
        self.is_linux = sys.platform.startswith("linux")
        self.disk_mgr = None

        self.ESSENTIAL_LINUX_TOOLS = [
            "parted", "mkfs.vfat", "mkfs.hfsplus", "7z", "dd",
            "rsync", "lsblk", "fdisk", "umount", "mount",
            "blockdev", "partprobe", "sync"
        ]
        self.TOOL_TO_PACKAGE = {
            "parted": "parted", "mkfs.vfat": "dosfstools",
            "mkfs.hfsplus": "hfsprogs or hfsplus-tools", "7z": "p7zip-full or p7zip",
            "dd": "coreutils (usually pre-installed)", "rsync": "rsync",
            "lsblk": "util-linux (usually pre-installed)", "fdisk": "util-linux (usually pre-installed)",
            "umount": "util-linux (usually pre-installed)", "mount": "util-linux (usually pre-installed)",
            "blockdev": "util-linux (usually pre-installed)", "partprobe": "parted or util-linux",
            "sync": "coreutils (usually pre-installed)"
        }

        if self.is_linux:
            try:
                from skyscope_diskutils_linux import Disk as LinuxDiskManager # Ensure this import is correct
                self.disk_mgr = LinuxDiskManager(self.u)
                self.u.cprint("Linux Disk Manager initialized.", "green")
                self._check_dependencies()
            except ImportError:
                self.u.cprint("LinuxDiskManager (skyscope_diskutils_linux.py) not found. USB creation will be disabled.", "red")
                self.is_linux = False
            except Exception as e:
                self.u.cprint(f"Error initializing LinuxDiskManager: {e}", "red")
                self.is_linux = False
        else:
            self.u.cprint("Non-Linux platform. USB creation functions will be disabled.", "yellow")

        self.OC_ESSENTIAL_DRIVERS = ["HfsPlus.efi", "OpenRuntime.efi"]
        self.OC_ESSENTIAL_KEXTS = ["Lilu.kext", "VirtualSMC.kext", "WhateverGreen.kext"]
        self.OC_LEGACY_BOOT_FILES = {"boot0": "boot0", "boot1f32": "boot1f32"}
        self.OC_RELEASE_URL = "https://api.github.com/repos/acidanthera/OpenCorePkg/releases/latest"
        self.CLOVER_ESSENTIAL_DRIVERS_UEFI = ["HFSPlus.efi", "ApfsDriverLoader.efi", "VBoxHfs.efi"]
        self.CLOVER_ESSENTIAL_KEXTS_OTHER = ["FakeSMC.kext", "Lilu.kext", "WhateverGreen.kext"]
        self.CLOVER_LEGACY_BOOT_FILES = {"boot0": "boot0af", "boot1f32": "boot1f32alt"}
        self.CLOVER_RELEASE_URL = "https://api.github.com/repos/CloverHackyColor/CloverBootloader/releases/latest"
        self.OC_LITTLE_TRANSLATED_URL = "https://github.com/5T33Z0/OC-Little-Translated"

        self.show_all_removable_disks_toggle = False
        try:
            self.temp_dir_base.mkdir(parents=True, exist_ok=True)
        except OSError as e:
             self.u.cprint(f"Could not create base temp directory '{self.temp_dir_base}': {e}", "red")

    def _check_dependencies(self):
        if not self.is_linux:
            return True

        self.u.head("Checking System Dependencies")
        missing_tools_map = {}

        for tool in self.ESSENTIAL_LINUX_TOOLS:
            tool_path = shutil.which(tool)
            if tool_path:
                self.u.cprint(f"  Checking for '{tool}'... Found ({tool_path})", "green")
            else:
                self.u.cprint(f"  Checking for '{tool}'... NOT FOUND", "red")
                missing_tools_map[tool] = self.TOOL_TO_PACKAGE.get(tool, "package_name_unknown")

        if missing_tools_map:
            self.u.cprint("\nError: The following essential tools are missing:", "red")
            for tool, pkg_suggestion in missing_tools_map.items():
                self.u.cprint(f"  - {tool} (Suggested package: {pkg_suggestion})", "red")
            self.u.cprint("\nPlease install them using your system's package manager.", "yellow")
            self.u.cprint("Example for Debian/Ubuntu: sudo apt update && sudo apt install <package_name>", "yellow")
            self.u.cprint("Example for Fedora: sudo dnf install <package_name>", "yellow")
            self.u.cprint("\nThis tool cannot proceed with USB creation features without these dependencies.", "red")
            input("Press Enter to exit.")
            sys.exit(1)
        else:
            self.u.cprint("\nAll essential tools found.", "green")
            time.sleep(1)
        return True

    def _mount_efi_partition(self, efi_partition_path_str, purpose_desc="EFI operations"):
        """Helper to mount an EFI partition. Returns mount point Path object or None."""
        efi_mount_point = None # Initialize to ensure it's defined in finally if tempfile.mkdtemp fails
        try:
            efi_mount_point = pathlib.Path(tempfile.mkdtemp(prefix="efi_mount_", dir=str(self.temp_dir_base)))
            self.u.cprint(f"Attempting to mount EFI partition '{efi_partition_path_str}' for {purpose_desc} at '{efi_mount_point}'...", "green")
            mount_cmd = ["mount", efi_partition_path_str, str(efi_mount_point)]
            mount_result = self._run_command(mount_cmd, f"Mount EFI for {purpose_desc}", check=False)
            if not mount_result or mount_result.returncode != 0:
                self.u.cprint(f"Failed to mount EFI partition '{efi_partition_path_str}'.", "red")
                # Attempt cleanup even on failure to mount
                if efi_mount_point and efi_mount_point.exists():
                    shutil.rmtree(efi_mount_point, ignore_errors=True)
                return None
            return efi_mount_point
        except Exception as e:
            self.u.cprint(f"Error creating temp mount point or mounting for {purpose_desc}: {e}", "red")
            if efi_mount_point and efi_mount_point.exists():
                 shutil.rmtree(efi_mount_point, ignore_errors=True)
            return None


    def _unmount_and_cleanup_efi_mount_point(self, efi_mount_point_path, purpose_desc="EFI operations"):
        """Helper to unmount and clean up an EFI mount point."""
        if efi_mount_point_path and efi_mount_point_path.is_mount(): # Check if it's a valid path and mounted
            self.u.cprint(f"Unmounting EFI partition for {purpose_desc} at '{efi_mount_point_path}'...", "green")
            self._run_command(["sync"], "Sync before unmount", check=False)
            # Force unmount (-l) and allow lazy unmount (-f) if busy, though ideally it shouldn't be.
            umount_res = self._run_command(["umount", "-lf", str(efi_mount_point_path)], f"Unmount EFI for {purpose_desc}", check=False)
            if not umount_res or umount_res.returncode != 0:
                 self.u.cprint(f"  Warning: Could not unmount {efi_mount_point_path}. Manual check may be needed.", "yellow")

        if efi_mount_point_path and efi_mount_point_path.exists(): # Check if path itself exists before trying to remove
            try:
                shutil.rmtree(efi_mount_point_path, ignore_errors=False) # Set ignore_errors=False to see potential issues
                self.u.cprint(f"Temporary mount point {efi_mount_point_path} removed.", "green")
            except Exception as e:
                 self.u.cprint(f"  Warning: Could not remove temporary mount point {efi_mount_point_path}: {e}", "yellow")
        elif efi_mount_point_path: # Path was given but doesn't exist
             self.u.cprint(f"Temporary mount point {efi_mount_point_path} did not exist for cleanup.", "yellow")


    # --- Refactored OpenCore Helper Methods ---
    def _fetch_and_extract_opencore(self, oc_download_dir, oc_extract_dir):
        """Fetches and extracts OpenCore. Returns path to X64/EFI or None."""
        self.u.cprint("Fetching latest OpenCore release information...", "green")
        release_info_str = self.d.get_string(self.OC_RELEASE_URL)
        if not release_info_str:
            self.u.cprint("Failed to fetch OpenCore release info. Check internet or URL.", "red"); return None

        oc_zip_url, oc_zip_name = None, None
        try:
            release_data = json.loads(release_info_str)
            for asset in release_data.get("assets", []):
                if asset.get("name", "").upper().endswith("-RELEASE.ZIP"):
                    oc_zip_url = asset.get("browser_download_url")
                    oc_zip_name = asset.get("name")
                    break
            if not oc_zip_url:
                self.u.cprint("Could not find RELEASE.zip in OpenCore release assets.", "red"); return None
        except json.JSONDecodeError as e:
            self.u.cprint(f"Failed to parse OpenCore release JSON: {e}", "red"); return None

        self.u.cprint(f"Found OpenCore release: {oc_zip_name}", "green")
        target_zip_path = oc_download_dir / oc_zip_name
        if not self.d.stream_to_file(oc_zip_url, str(target_zip_path)):
            self.u.cprint(f"Failed to download OpenCore ZIP from {oc_zip_url}.", "red"); return None
        self.u.cprint(f"OpenCore downloaded to: {target_zip_path}", "green")

        if not self._extract_archive(target_zip_path, oc_extract_dir, "OpenCore PKG"):
            self.u.cprint("Failed to extract OpenCore ZIP.", "red"); return None

        source_x64_efi_dir = oc_extract_dir / "X64" / "EFI"
        if not source_x64_efi_dir.is_dir():
            self.u.cprint(f"Extracted OpenCore does not contain '{source_x64_efi_dir}'.", "red"); return None
        return source_x64_efi_dir

    def _install_opencore_efi_files(self, target_efi_base_on_usb, source_x64_efi_dir):
        """Copies OpenCore EFI files, essential drivers, kexts, and handles config.plist."""
        target_oc_dir = target_efi_base_on_usb / "OC"
        self.u.cprint(f"Copying base OpenCore EFI files from '{source_x64_efi_dir}' to '{target_efi_base_on_usb}'...", "green")
        try:
            shutil.copytree(source_x64_efi_dir, target_efi_base_on_usb, dirs_exist_ok=True)
            (target_oc_dir / "Drivers").mkdir(parents=True, exist_ok=True)
            (target_oc_dir / "Kexts").mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.u.cprint(f"Error setting up base OpenCore directories: {e}", "red"); return False

        self.u.cprint("Copying essential OpenCore drivers...", "green")
        for driver_name in self.OC_ESSENTIAL_DRIVERS:
            source_driver = source_x64_efi_dir / "OC" / "Drivers" / driver_name
            if source_driver.exists():
                try: shutil.copy2(source_driver, target_oc_dir / "Drivers" / driver_name)
                except Exception as e: self.u.cprint(f"  Error copying driver {driver_name}: {e}", "yellow")
                else: self.u.cprint(f"  Copied: {driver_name}", "green")
            else: self.u.cprint(f"  Warning: Essential driver '{driver_name}' not found in OpenCore package.", "yellow")

        self.u.cprint("Copying essential OpenCore Kexts (directories)...", "green")
        for kext_dir_name in self.OC_ESSENTIAL_KEXTS:
            source_kext_dir = source_x64_efi_dir / "OC" / "Kexts" / kext_dir_name
            if source_kext_dir.is_dir():
                try: shutil.copytree(source_kext_dir, target_oc_dir / "Kexts" / kext_dir_name, dirs_exist_ok=True)
                except Exception as e: self.u.cprint(f"  Error copying Kext {kext_dir_name}: {e}", "yellow")
                else: self.u.cprint(f"  Copied: {kext_dir_name}", "green")
            else: self.u.cprint(f"  Warning: Essential Kext directory '{kext_dir_name}' not found in OpenCore package.", "yellow")

        sample_plist_path = target_oc_dir / "Sample.plist"
        config_plist_path = target_oc_dir / "config.plist"
        arch_key = self._select_cpu_architecture_for_config("opencore")

        if arch_key == "BACK": # User chose to go back
             self.u.cprint("OpenCore config selection cancelled by user.", "yellow")
             return False # Indicate cancellation/failure to proceed with this part

        if arch_key: # User selected a specific architecture
            config_plist_str = self.efi_cfg_mgr.get_config_plist("opencore", arch_key)
            if config_plist_str:
                try:
                    with open(config_plist_path, "w", encoding="utf-8") as f: f.write(config_plist_str)
                    self.u.cprint(f"Installed generic OpenCore config.plist for '{arch_key}'.", "green")
                    self.u.cprint("-" * 70, "yellow")
                    self.u.cprint("IMPORTANT: A GENERIC OpenCore config.plist has been installed!", "yellow")
                    self.u.cprint("This is a basic template and WILL REQUIRE CUSTOMIZATION for your specific hardware.", "yellow")
                    self.u.cprint("Without proper customization, your system may NOT boot or may have issues.", "red")
                    self.u.cprint("Please consult detailed guides to correctly configure it:", "yellow")
                    self.u.cprint("  - Dortania's OpenCore Install Guide: https://dortania.github.io/OpenCore-Install-Guide/", "green")
                    self.u.cprint(f"  - OC-Little Translated (Advanced): {self.OC_LITTLE_TRANSLATED_URL}", "green")
                    self.u.cprint("Key areas to check: SMBIOS (PlatformInfo), ACPI, DeviceProperties, Kernel (Quirks, Kexts).", "yellow")
                    self.u.cprint("-" * 70, "yellow")
                except IOError as e:
                    self.u.cprint(f"Error writing generic config.plist: {e}", "red")
                    self.u.cprint("Falling back to Sample.plist if available.", "yellow")
                    if sample_plist_path.exists(): shutil.copy2(sample_plist_path, config_plist_path)
                    else: self.u.cprint(f"Critical: Sample.plist also not found at {sample_plist_path}", "red")
            else:
                self.u.cprint(f"Could not find generic OpenCore config for '{arch_key}'. Using Sample.plist if available.", "yellow")
                if sample_plist_path.exists(): shutil.copy2(sample_plist_path, config_plist_path)
                else: self.u.cprint(f"Critical: Sample.plist also not found at {sample_plist_path}", "red")
        else: # User chose to skip (arch_key is None) or no configs were available initially
            self.u.cprint("Using default Sample.plist for OpenCore (if found).", "yellow")
            if sample_plist_path.exists():
                shutil.copy2(sample_plist_path, config_plist_path)
                self.u.cprint(f"Copied '{sample_plist_path.name}' to '{config_plist_path.name}'.", "green")
                self.u.cprint("IMPORTANT: This is a SAMPLE config.plist. It needs to be configured for your specific hardware!", "yellow")
            else: self.u.cprint(f"Warning: '{sample_plist_path.name}' not found. Cannot create default config.plist.", "yellow")
        return True

    def _setup_opencore_legacy_boot(self, usb_device_path, efi_partition_path, oc_extract_dir, gpt_scheme):
        if gpt_scheme: return True

        self.u.cprint("Setting up OpenCore Legacy Boot (MBR)...", "green")
        legacy_boot_util_path = oc_extract_dir / "Utilities" / "LegacyBoot"
        boot0_file_info = self.OC_LEGACY_BOOT_FILES.get("boot0")
        boot1f32_file_info = self.OC_LEGACY_BOOT_FILES.get("boot1f32")

        if not boot0_file_info or not boot1f32_file_info:
            self.u.cprint("Legacy boot file names not defined in constants.", "red"); return False

        boot0_file = legacy_boot_util_path / boot0_file_info
        boot1f32_file = legacy_boot_util_path / boot1f32_file_info

        all_dd_ok = True
        if boot0_file.exists():
            dd_mbr_cmd = ["dd", f"if={str(boot0_file)}", f"of={usb_device_path}", "bs=440", "count=1", "conv=fsync"]
            mbr_res = self._run_command(dd_mbr_cmd, "Write OpenCore MBR (boot0)")
            if mbr_res and mbr_res.returncode == 0:
                 self.u.cprint(f"  Successfully wrote '{boot0_file.name}' to MBR of '{usb_device_path}'.", "green")
            else: self.u.cprint(f"  Warning: Failed to write MBR for OpenCore on '{usb_device_path}'.", "yellow"); all_dd_ok = False
        else: self.u.cprint(f"  Warning: OpenCore MBR file '{boot0_file.name}' not found at '{legacy_boot_util_path}'.", "yellow")

        if boot1f32_file.exists():
            dd_pbr_cmd = ["dd", f"if={str(boot1f32_file)}", f"of={efi_partition_path}", "conv=fsync"]
            pbr_res = self._run_command(dd_pbr_cmd, "Write OpenCore PBR (boot1f32)")
            if pbr_res and pbr_res.returncode == 0:
                self.u.cprint(f"  Successfully wrote '{boot1f32_file.name}' to PBR of '{efi_partition_path}'.", "green")
            else: self.u.cprint(f"  Warning: Failed to write PBR for OpenCore on '{efi_partition_path}'.", "yellow"); all_dd_ok = False
        else: self.u.cprint(f"  Warning: OpenCore PBR file '{boot1f32_file.name}' not found at '{legacy_boot_util_path}'.", "yellow")
        return all_dd_ok

    # --- Main OpenCore Handler ---
    def _handle_opencore_installation(self, efi_partition_path, usb_device_path, gpt_scheme):
        self.u.head("OpenCore Installation")
        oc_download_dir = self.temp_dir_base / "opencore_download"
        oc_extract_dir = self.temp_dir_base / "opencore_extracted"
        efi_mount_point = None
        success = False
        try:
            oc_download_dir.mkdir(parents=True, exist_ok=True)
            oc_extract_dir.mkdir(parents=True, exist_ok=True)

            source_x64_efi_dir = self._fetch_and_extract_opencore(oc_download_dir, oc_extract_dir)
            if not source_x64_efi_dir: return False # Error messages handled in helper

            efi_mount_point = self._mount_efi_partition(efi_partition_path, "OpenCore Installation")
            if not efi_mount_point: return False # Error messages handled in helper

            target_efi_base_on_usb = efi_mount_point / "EFI"
            if not self._install_opencore_efi_files(target_efi_base_on_usb, source_x64_efi_dir):
                # This implies user might have cancelled at CPU arch selection, or a file write error occurred.
                # Error messages (or cancellation message) handled in helper.
                return False

            if not self._setup_opencore_legacy_boot(usb_device_path, efi_partition_path, oc_extract_dir, gpt_scheme):
                self.u.cprint("OpenCore Legacy Boot setup encountered issues. UEFI booting might still work.", "yellow")

            self.u.cprint("OpenCore installation process completed.", "green")
            success = True
        except Exception as e:
            self.u.cprint(f"An unexpected error occurred during OpenCore installation: {e}", "red")
            import traceback; self.u.cprint(traceback.format_exc(), "yellow")
            success = False
        finally:
            self._unmount_and_cleanup_efi_mount_point(efi_mount_point, "OpenCore Installation")
            try:
                if oc_download_dir.exists(): shutil.rmtree(oc_download_dir)
                if oc_extract_dir.exists(): shutil.rmtree(oc_extract_dir)
                self.u.cprint("OpenCore temporary resources cleaned up.", "green")
            except Exception as e:
                self.u.cprint(f"Error cleaning up OpenCore temporary directories: {e}", "yellow")
        return success

    # --- Refactored Clover Helper Methods ---
    def _fetch_and_extract_clover_package(self, clover_download_dir, clover_extract_dir):
        """Fetches, downloads, and extracts Clover. Returns (source_efi_dir, legacy_boot_source_dir) or (None, None)."""
        self.u.cprint("Fetching latest Clover release information...", "green")
        release_info_str = self.d.get_string(self.CLOVER_RELEASE_URL)
        if not release_info_str:
            self.u.cprint("Failed to fetch Clover release info. Check internet or URL.", "red"); return None, None

        clover_asset_url, clover_asset_name = None, None
        try:
            release_data = json.loads(release_info_str)
            preferred_assets = []
            for asset in release_data.get("assets", []):
                asset_name_lower = asset.get("name", "").lower()
                if "clover" in asset_name_lower and asset_name_lower.endswith((".tar.lzma", ".tar.xz", ".7z")):
                    preferred_assets.append({"url": asset.get("browser_download_url"), "name": asset.get("name"), "priority": 0})
                elif "clover" in asset_name_lower and asset_name_lower.endswith(".zip"):
                    preferred_assets.append({"url": asset.get("browser_download_url"), "name": asset.get("name"), "priority": 1})
                elif asset_name_lower.endswith(".pkg"):
                    preferred_assets.append({"url": asset.get("browser_download_url"), "name": asset.get("name"), "priority": 2})
                elif "clover" in asset_name_lower and "x64.iso" in asset_name_lower: # Prioritize X64 ISO
                    preferred_assets.append({"url": asset.get("browser_download_url"), "name": asset.get("name"), "priority": 3})
                elif "clover" in asset_name_lower and asset_name_lower.endswith(".iso"): # Any other ISO
                    preferred_assets.append({"url": asset.get("browser_download_url"), "name": asset.get("name"), "priority": 4})

            if not preferred_assets:
                self.u.cprint("Could not find a suitable Clover release asset (ZIP, PKG, TAR, ISO).", "red"); return None, None

            preferred_assets.sort(key=lambda x: x["priority"])
            clover_asset_url = preferred_assets[0]["url"]
            clover_asset_name = preferred_assets[0]["name"]
        except json.JSONDecodeError as e:
            self.u.cprint(f"Failed to parse Clover release JSON: {e}", "red"); return None, None

        self.u.cprint(f"Found Clover release asset: {clover_asset_name}", "green")
        target_asset_path = clover_download_dir / clover_asset_name
        if not self.d.stream_to_file(clover_asset_url, str(target_asset_path)):
            self.u.cprint(f"Failed to download Clover asset from {clover_asset_url}.", "red"); return None, None
        self.u.cprint(f"Clover asset downloaded to: {target_asset_path}", "green")

        # Extraction Logic
        source_efi_dir_clover = None
        legacy_boot_source_dir = clover_extract_dir
        temp_extraction_subdirs = [] # Keep track of dirs created by nested extractions

        try:
            if clover_asset_name.lower().endswith((".zip", ".tar.xz", ".tar.lzma", ".7z")):
                if not self._extract_archive(target_asset_path, clover_extract_dir, "Clover Archive"):
                    self.u.cprint("Failed to extract Clover archive.", "red"); return None, None
                search_paths = [clover_extract_dir, clover_extract_dir / "CloverV2", clover_extract_dir / "Clover"]
                for path_to_check in search_paths:
                    if (path_to_check / "EFI" / "CLOVER").is_dir() and (path_to_check / "EFI" / "BOOT").is_dir():
                        source_efi_dir_clover = path_to_check / "EFI"; legacy_boot_source_dir = path_to_check; break
                if not source_efi_dir_clover:
                     for item in clover_extract_dir.iterdir():
                         if item.is_dir() and (item / "EFI" / "CLOVER").is_dir():
                             source_efi_dir_clover = item / "EFI"; legacy_boot_source_dir = item; break
            elif clover_asset_name.lower().endswith(".pkg"):
                pkg_extract_base = clover_extract_dir / "pkg_extracted"
                temp_extraction_subdirs.append(pkg_extract_base)
                if not self._extract_archive(target_asset_path, pkg_extract_base, "Clover PKG"):
                    self.u.cprint("Failed to extract Clover PKG.", "red"); return None, None

                iso_files = list(pkg_extract_base.rglob("*.iso")) # Recursive search for ISO
                if iso_files:
                    clover_iso_path = iso_files[0]
                    self.u.cprint(f"Found Clover ISO inside PKG: {clover_iso_path}", "green")
                    iso_extract_path = clover_extract_dir / "iso_from_pkg_extracted"
                    temp_extraction_subdirs.append(iso_extract_path)
                    if not self._extract_archive(clover_iso_path, iso_extract_path, "Clover ISO from PKG"):
                        self.u.cprint("Failed to extract Clover ISO (from PKG).", "red"); return None, None

                    if (iso_extract_path / "EFI" / "CLOVER").is_dir():
                        source_efi_dir_clover = iso_extract_path / "EFI"; legacy_boot_source_dir = iso_extract_path
                    elif (iso_extract_path / "CDROOT" / "EFI" / "CLOVER").is_dir(): # Common for some bootable ISOs
                        source_efi_dir_clover = iso_extract_path / "CDROOT" / "EFI"; legacy_boot_source_dir = iso_extract_path / "CDROOT"
                elif (pkg_extract_base / "EFI" / "CLOVER").is_dir(): # EFI folder directly in PKG payload
                     source_efi_dir_clover = pkg_extract_base / "EFI"; legacy_boot_source_dir = pkg_extract_base
            elif clover_asset_name.lower().endswith(".iso"): # Direct ISO download
                 iso_extract_path = clover_extract_dir / "iso_extracted_direct"
                 temp_extraction_subdirs.append(iso_extract_path)
                 if not self._extract_archive(target_asset_path, iso_extract_path, "Clover ISO Direct"):
                     self.u.cprint("Failed to extract Clover ISO (direct).", "red"); return None, None
                 if (iso_extract_path / "EFI" / "CLOVER").is_dir():
                     source_efi_dir_clover = iso_extract_path / "EFI"; legacy_boot_source_dir = iso_extract_path
                 elif (iso_extract_path / "CDROOT" / "EFI" / "CLOVER").is_dir():
                     source_efi_dir_clover = iso_extract_path / "CDROOT" / "EFI"; legacy_boot_source_dir = iso_extract_path / "CDROOT"

            if not source_efi_dir_clover or not source_efi_dir_clover.is_dir():
                self.u.cprint(f"Could not locate a usable Clover EFI directory after extraction from '{clover_asset_name}'. Structure might be unexpected.", "red")
                self.u.cprint(f"  Please inspect extracted contents in: {clover_extract_dir}", "yellow"); return None, None

            self.u.cprint(f"Located Clover EFI source at: {source_efi_dir_clover}", "green")
            return source_efi_dir_clover, legacy_boot_source_dir
        except Exception as e:
            self.u.cprint(f"Error during Clover fetch/extraction: {e}", "red")
            import traceback; self.u.cprint(traceback.format_exc(), "yellow")
            return None, None
        # Note: Cleanup of temp_extraction_subdirs is not handled here; parent extract_dir cleanup should suffice.


    def _install_clover_efi_files(self, target_efi_root_on_usb, source_efi_dir_clover):
        """Copies Clover EFI files, essential drivers, kexts, and handles config.plist."""
        self.u.cprint(f"Copying Clover EFI files from '{source_efi_dir_clover}' to '{target_efi_root_on_usb}'...", "green")
        try:
            for item in source_efi_dir_clover.iterdir(): # Copy contents of source_efi_dir_clover to target_efi_root_on_usb
                target_item_path = target_efi_root_on_usb / item.name
                if item.is_dir(): shutil.copytree(item, target_item_path, dirs_exist_ok=True)
                else:
                    target_efi_root_on_usb.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target_item_path)
        except OSError as e:
            self.u.cprint(f"Error copying base Clover EFI files: {e}", "red"); return False

        target_clover_dir = target_efi_root_on_usb / "CLOVER"
        clover_drivers_uefi_src_options = [
            source_efi_dir_clover / "CLOVER" / "drivers" / "UEFI",
            source_efi_dir_clover / "CLOVER" / "drivers64UEFI"
        ]
        clover_drivers_uefi_src = next((p for p in clover_drivers_uefi_src_options if p.is_dir()), None)
        target_drivers_uefi_dir = target_clover_dir / "drivers" / "UEFI"
        try: target_drivers_uefi_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e: self.u.cprint(f"Error creating Clover drivers dir: {e}", "red"); return False

        if clover_drivers_uefi_src:
            self.u.cprint(f"Copying essential Clover UEFI drivers from {clover_drivers_uefi_src}...", "green")
            for driver_name in self.CLOVER_ESSENTIAL_DRIVERS_UEFI:
                source_driver = clover_drivers_uefi_src / driver_name
                if source_driver.exists():
                    try: shutil.copy2(source_driver, target_drivers_uefi_dir / driver_name)
                    except Exception as e: self.u.cprint(f"  Error copying Clover driver {driver_name}: {e}", "yellow")
                    else: self.u.cprint(f"  Copied: {driver_name}", "green")
                else: self.u.cprint(f"  Warning: Essential UEFI driver '{driver_name}' not found in Clover package at '{clover_drivers_uefi_src}'.", "yellow")
        else: self.u.cprint("Warning: Standard Clover UEFI drivers source directory not found in package.", "yellow")

        clover_kexts_other_src = source_efi_dir_clover / "CLOVER" / "kexts" / "Other"
        target_kexts_other_dir = target_clover_dir / "kexts" / "Other"
        try: target_kexts_other_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e: self.u.cprint(f"Error creating Clover kexts dir: {e}", "red"); return False

        if clover_kexts_other_src.is_dir():
            self.u.cprint("Copying essential Clover Kexts (directories)...", "green")
            for kext_dir_name in self.CLOVER_ESSENTIAL_KEXTS_OTHER:
                source_kext_dir = clover_kexts_other_src / kext_dir_name
                if source_kext_dir.is_dir():
                    try: shutil.copytree(source_kext_dir, target_kexts_other_dir / kext_dir_name, dirs_exist_ok=True)
                    except Exception as e: self.u.cprint(f"  Error copying Clover Kext {kext_dir_name}: {e}", "yellow")
                    else: self.u.cprint(f"  Copied: {kext_dir_name}", "green")
                else: self.u.cprint(f"  Warning: Essential Kext directory '{kext_dir_name}' not found in Clover package at '{clover_kexts_other_src}'.", "yellow")
        else: self.u.cprint(f"Warning: Clover kexts/Other source directory '{clover_kexts_other_src}' not found.", "yellow")

        config_plist_path_clover = target_clover_dir / "config.plist"
        arch_key_clover = self._select_cpu_architecture_for_config("clover")

        if arch_key_clover == "BACK": self.u.cprint("Clover config selection cancelled.", "yellow"); return False

        if arch_key_clover :
            config_plist_str_clover = self.efi_cfg_mgr.get_config_plist("clover", arch_key_clover)
            if config_plist_str_clover:
                try:
                    with open(config_plist_path_clover, "w", encoding="utf-8") as f: f.write(config_plist_str_clover)
                    self.u.cprint(f"Installed generic Clover config.plist for '{arch_key_clover}'.", "green")
                    self.u.cprint("-" * 70, "yellow")
                    self.u.cprint("IMPORTANT: A GENERIC Clover config.plist has been installed!", "yellow")
                    self.u.cprint("This is a basic template and WILL REQUIRE CUSTOMIZATION for your specific hardware.", "yellow")
                    self.u.cprint("Without proper customization, your system may NOT boot or may have issues.", "red")
                    self.u.cprint("Please consult detailed Clover guides and Hackintosh community resources.", "yellow")
                    self.u.cprint("  - Search for 'Clover Bootloader guide' and your hardware specifics.", "green")
                    self.u.cprint("Key areas to check: SMBIOS, ACPI, Devices (Properties), Graphics, KernelAndKextPatches.", "yellow")
                    self.u.cprint("-" * 70, "yellow")
                except IOError as e:
                    self.u.cprint(f"Error writing generic Clover config.plist: {e}", "red")
                    self.u.cprint("Clover may use its internal default or require manual setup.", "yellow")
            else: self.u.cprint(f"Could not find generic Clover config for '{arch_key_clover}'. Clover may use internal default.", "yellow")
        else: # User skipped or no specific configs available
            if not config_plist_path_clover.exists(): # Only copy sample if no config.plist was part of base EFI
                sample_plist_clover_src_options = [
                    source_efi_dir_clover / "CLOVER" / "config.plist.sample",
                    source_efi_dir_clover / "CLOVER" / "config-sample.plist"
                ]
                sample_plist_clover_src = next((p for p in sample_plist_clover_src_options if p.exists()), None)
                if sample_plist_clover_src:
                    try: shutil.copy2(sample_plist_clover_src, config_plist_path_clover)
                    except Exception as e: self.u.cprint(f"Error copying sample Clover config: {e}", "yellow")
                    else: self.u.cprint(f"Copied sample Clover config to '{config_plist_path_clover.name}'. IMPORTANT: Customize it!", "yellow")
                else: self.u.cprint(f"No generic config chosen, and no sample config.plist found in Clover package. '{config_plist_path_clover.name}' may be missing.", "yellow")
            else: self.u.cprint("Using existing config.plist from Clover package or skipping generic config selection.", "yellow")
        return True

    def _setup_clover_legacy_boot(self, usb_device_path, efi_partition_path, legacy_boot_source_dir, gpt_scheme):
        if gpt_scheme: return True
        self.u.cprint("Setting up Clover Legacy Boot (MBR)...", "green")

        boot0_file_name = self.CLOVER_LEGACY_BOOT_FILES.get("boot0", "boot0af")
        boot1f32_file_name = self.CLOVER_LEGACY_BOOT_FILES.get("boot1f32", "boot1f32alt")

        boot0_file = legacy_boot_source_dir / boot0_file_name
        if not boot0_file.exists() and boot0_file_name == "boot0af": # Fallback for boot0
            boot0_file = legacy_boot_source_dir / "boot0ss"
            if boot0_file.exists(): self.u.cprint(f"  Using fallback MBR boot file: boot0ss", "yellow")

        boot1f32_file = legacy_boot_source_dir / boot1f32_file_name
        all_dd_ok = True

        if boot0_file.exists():
            # Some Clover boot0 files are 512 bytes, bs=440 is safer for MBR code area only.
            # However, to be safe and ensure full compatibility with various boot0 versions,
            # it might be better to write the full 512 bytes if the file is that size,
            # or stick to 440 if that's what Clover's own installer scripts do.
            # For now, using bs=440 as it's a common practice.
            dd_mbr_cmd = ["dd", f"if={str(boot0_file)}", f"of={usb_device_path}", "bs=440", "count=1", "conv=fsync"]
            mbr_res = self._run_command(dd_mbr_cmd, "Write Clover MBR")
            if mbr_res and mbr_res.returncode == 0:
                 self.u.cprint(f"  Successfully wrote '{boot0_file.name}' to MBR of '{usb_device_path}'.", "green")
            else: self.u.cprint(f"  Warning: Failed to write MBR for Clover on '{usb_device_path}'.", "yellow"); all_dd_ok = False
        else: self.u.cprint(f"  Warning: Clover MBR file ('{boot0_file_name}' or 'boot0ss') not found at '{legacy_boot_source_dir}'.", "yellow")

        if boot1f32_file.exists():
            dd_pbr_cmd = ["dd", f"if={str(boot1f32_file)}", f"of={efi_partition_path}", "conv=fsync"]
            pbr_res = self._run_command(dd_pbr_cmd, "Write Clover PBR")
            if pbr_res and pbr_res.returncode == 0:
                self.u.cprint(f"  Successfully wrote '{boot1f32_file.name}' to PBR of '{efi_partition_path}'.", "green")
            else: self.u.cprint(f"  Warning: Failed to write PBR for Clover on '{efi_partition_path}'.", "yellow"); all_dd_ok = False
        else: self.u.cprint(f"  Warning: Clover PBR file '{boot1f32_file.name}' not found at '{legacy_boot_source_dir}'.", "yellow")
        return all_dd_ok

    # --- Main Clover Handler ---
    def _handle_clover_installation(self, efi_partition_path, usb_device_path, gpt_scheme):
        self.u.head("Clover Installation")
        clover_download_dir = self.temp_dir_base / "clover_download"
        clover_extract_dir = self.temp_dir_base / "clover_extracted"
        efi_mount_point = None
        success = False
        try:
            clover_download_dir.mkdir(parents=True, exist_ok=True)
            clover_extract_dir.mkdir(parents=True, exist_ok=True)

            source_efi_dir_clover, legacy_boot_source_dir = self._fetch_and_extract_clover_package(clover_download_dir, clover_extract_dir)
            if not source_efi_dir_clover:
                self.u.cprint("Failed to fetch or extract Clover package.", "red"); return False

            efi_mount_point = self._mount_efi_partition(efi_partition_path, "Clover Installation")
            if not efi_mount_point: return False

            target_efi_root_on_usb = efi_mount_point / "EFI"
            if not self._install_clover_efi_files(target_efi_root_on_usb, source_efi_dir_clover):
                self.u.cprint("Clover EFI file installation did not fully complete (possibly user cancellation or error).", "yellow")
                return False

            if not self._setup_clover_legacy_boot(usb_device_path, efi_partition_path, legacy_boot_source_dir, gpt_scheme):
                 self.u.cprint("Clover Legacy Boot setup encountered issues. UEFI booting might still work.", "yellow")

            self.u.cprint("Clover installation process completed.", "green")
            success = True
        except Exception as e:
            self.u.cprint(f"An unexpected error occurred during Clover installation: {e}", "red")
            import traceback; self.u.cprint(traceback.format_exc(), "yellow")
            success = False
        finally:
            self._unmount_and_cleanup_efi_mount_point(efi_mount_point, "Clover Installation")
            try:
                if clover_download_dir.exists(): shutil.rmtree(clover_download_dir, ignore_errors=True)
                if clover_extract_dir.exists(): shutil.rmtree(clover_extract_dir, ignore_errors=True)
                self.u.cprint("Clover temporary resources cleaned up.", "green")
            except Exception as e:
                self.u.cprint(f"Error cleaning up Clover temporary directories: {e}", "yellow")

        return success

    def _handle_custom_efi_copy(self, efi_partition_path_str):
        self.u.head("Custom EFI Setup")
        efi_mount_point_path = None

        try:
            custom_efi_input_path_str = input("Please drag & drop your custom EFI folder here, or type the full path: ").strip()
            if not custom_efi_input_path_str:
                self.u.cprint("No path provided. Aborting custom EFI copy.", "yellow"); return False

            custom_efi_input_path = pathlib.Path(custom_efi_input_path_str)

            if not custom_efi_input_path.exists() or not custom_efi_input_path.is_dir():
                self.u.cprint(f"Error: The provided path '{custom_efi_input_path_str}' is not a valid directory or does not exist.", "red"); return False

            source_efi_to_copy = None
            if custom_efi_input_path.name.upper() == "EFI": source_efi_to_copy = custom_efi_input_path
            elif (custom_efi_input_path / "EFI").is_dir(): source_efi_to_copy = custom_efi_input_path / "EFI"

            if not source_efi_to_copy or not source_efi_to_copy.is_dir():
                self.u.cprint(f"Error: Could not find an 'EFI' subfolder in '{custom_efi_input_path_str}', nor is the path itself an EFI folder.", "red")
                self.u.cprint("Please provide a path to a folder named 'EFI', or a folder that contains an 'EFI' subfolder.", "red"); return False

            self.u.cprint(f"Validated custom EFI source: {source_efi_to_copy}", "green")

            efi_mount_point_path = self._mount_efi_partition(efi_partition_path_str, "Custom EFI Copy")
            if not efi_mount_point_path: return False

            target_efi_on_usb = efi_mount_point_path / "EFI"
            self.u.cprint(f"Preparing to copy custom EFI to '{target_efi_on_usb}'...", "green")
            if target_efi_on_usb.exists():
                self.u.cprint(f"Removing existing EFI folder at '{target_efi_on_usb}'...", "yellow")
                try: shutil.rmtree(target_efi_on_usb)
                except OSError as e: self.u.cprint(f"Error removing existing EFI folder '{target_efi_on_usb}': {e}", "red"); return False

            self.u.cprint(f"Copying '{source_efi_to_copy}' to '{target_efi_on_usb}'...", "green")
            try: shutil.copytree(source_efi_to_copy, target_efi_on_usb)
            except Exception as e: self.u.cprint(f"Error copying custom EFI folder: {e}", "red"); return False

            self.u.cprint(f"Successfully copied custom EFI from '{source_efi_to_copy}' to '{target_efi_on_usb}'.", "green")
            return True
        except Exception as e:
            self.u.cprint(f"An unexpected error occurred during custom EFI copy: {e}", "red")
            import traceback; self.u.cprint(traceback.format_exc(), "yellow")
            return False
        finally:
            self._unmount_and_cleanup_efi_mount_point(efi_mount_point_path, "Custom EFI Copy")
            self.u.cprint("Custom EFI copy process finished.", "green")

    # --- End Bootloader Handling Methods ---

    def display_help_explanations(self):
        self.u.head("Help / Explanations")

        self.u.cprint("\n--- GPT (GUID Partition Table) vs MBR (Master Boot Record) ---", "yellow")
        self.u.cprint("  GPT: Modern standard, required for UEFI booting (most modern systems). Recommended.", "green")
        self.u.cprint("  MBR: Older standard, for legacy BIOS booting. Choose if your system doesn't support UEFI.", "green")

        self.u.cprint("\n--- OpenCore vs Clover ---", "yellow")
        self.u.cprint("  OpenCore: Newer, more robust, generally recommended for modern macOS versions & hardware.", "green")
        self.u.cprint("            Requires more careful setup but offers better system stability and compatibility.", "green")
        self.u.cprint("  Clover:   Older, widely used, might be easier for some legacy systems or specific hardware.", "green")
        self.u.cprint("            Can be less 'vanilla' than OpenCore.", "green")

        self.u.cprint("\n--- Placeholder URLs / Generic Configs ---", "red")
        self.u.cprint("  IMPORTANT: This tool may use placeholder URLs for some older macOS versions if official", "yellow")
        self.u.cprint("             direct download links are not readily available or easily discoverable via Apple's", "yellow")
        self.u.cprint("             software update catalogs for direct package downloads. These require manual verification.", "yellow")
        self.u.cprint("  CRITICAL: Generic config.plist files (for OpenCore/Clover) provided by this tool are", "red")
        self.u.cprint("            EXTREMELY BASIC starting points. They WILL NOT WORK correctly on most systems", "red")
        self.u.cprint("            without SIGNIFICANT, HARDWARE-SPECIFIC CUSTOMIZATION.", "red")
        self.u.cprint("            You MUST consult detailed guides like:", "yellow")
        self.u.cprint("              - Dortania's OpenCore Install Guide: https://dortania.github.io/OpenCore-Install-Guide/", "green")
        self.u.cprint(f"              - OC-Little Translated (Advanced OC): {self.OC_LITTLE_TRANSLATED_URL}", "green")
        self.u.cprint("              - Relevant Clover guides (search the Hackintosh community for your hardware).", "green")
        self.u.cprint("            Failure to customize your config.plist WILL LIKELY lead to boot failures or hardware instability.", "red")


        self.u.cprint("\n--- Download Directory ---", "yellow")
        self.u.cprint(f"  Installers are downloaded to subfolders within: {str(self.main_download_cache_dir)}", "green")
        self.u.cprint("  You can choose a custom base directory if preferred during the download process.", "green")

        self.u.cprint("\n--- USB Drive Selection ---", "yellow")
        self.u.cprint("  The tool lists removable USB drives. Double-check size and model.", "green")
        self.u.cprint("  WARNING: THE SELECTED USB DRIVE WILL BE COMPLETELY ERASED!", "red")
        self.u.cprint("  A strict confirmation (typing 'ERASE-[device_name]') is required.", "red")

        input("\nPress Enter to return to the main menu...")


    def run(self):
        global selected_version_key_for_global_context
        selected_version_key_for_global_context = None

        while True:
            choice = self.display_main_menu()
            if choice == '1':
                self.handle_download_menu()
            elif choice == '2':
                self.handle_create_usb_menu()
            elif choice == 'h':
                self.display_help_explanations()
            elif choice == 'q':
                self.u.cprint("Exiting Skyscope macOS USB Creator Tool. Goodbye!", "green")
                break
            else:
                self.u.cprint("Invalid choice, please try again.", "yellow")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    tool = SkyscopeTool()
    tool.run()

```

[end of macos_usb_tool.py]
