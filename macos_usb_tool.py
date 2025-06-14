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
        if color == "red": print(f"ERROR: {text}")
        elif color == "yellow": print(f"WARNING: {text}")
        elif color == "header": print(f"\n--- {text} ---")
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
        self.u.cprint(f"  Starting download of '{os.path.basename(destination_path)}' from {url}", "green")
        self.u.cprint(f"  Target: {destination_path}", "green")
        try:
            pathlib.Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
            total_simulated_size = total_size_override if total_size_override else 100 * 1024 * 1024
            downloaded_size = 0; spinner_chars = ['|', '/', '-', '\\']
            for i in range(10):
                time.sleep(0.05); downloaded_size += total_simulated_size / 10
                percentage = min((downloaded_size / total_simulated_size) * 100, 100) if total_simulated_size > 0 else 100
                bar = '#' * int(40*percentage/100) + '-' * (40-int(40*percentage/100))
                sys.stdout.write(f"\r  Downloading... {spinner_chars[i % len(spinner_chars)]} [{bar}] {percentage:>6.2f}%"); sys.stdout.flush()
            with open(destination_path, 'wb') as f: f.write(b"Simulated: " + os.path.basename(destination_path).encode())
            sys.stdout.write('\n'); self.u.cprint(f"  Successfully simulated download to '{destination_path}'.", "green")
            return True
        except Exception as e:
            sys.stdout.write('\n'); self.u.cprint(f"  Error during simulated download for {destination_path}: {e}", "red")
            return False

# --- Catalog Manager ---
class CatalogManager:
    # (Content mostly unchanged - _parse_products, add_manual_product, _get_displayable_products, list_products, select_product, get_product_info)
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
            except Exception as e: self.u.cprint(f"Error loading/parsing cached catalog '{cache_path}': {e}. Will try fresh download.", "red")
        if force_refresh: self.u.cprint("Forcing refresh: Downloading catalog from Apple.", "green")
        else: self.u.cprint(f"No valid cache at '{cache_path}' or refresh forced. Downloading catalog from Apple.", "green")
        url = self.build_catalog_url(catalog_type, major_macos_version)
        self.u.cprint(f"Fetching from URL: {url}", "green")
        self.raw_catalog_content_bytes = self.d.get_content(url)
        if not self.raw_catalog_content_bytes: self.u.cprint(f"Failed to download catalog from {url}.", "red"); return False
        try:
            self.catalog_data = plistlib.loads(self.raw_catalog_content_bytes)
            self.u.cprint("Successfully parsed catalog from Apple.", "green"); self._save_catalog_to_cache(catalog_type, major_macos_version); self._parse_products(); return True
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
        except Exception as e: self.u.cprint(f"  Warn: Error parsing .dist for {product_id} at {distribution_url}: {e}", "yellow")
        return {}
    def _parse_products(self):
        self.products = {};
        if not self.catalog_data or 'Products' not in self.catalog_data or not isinstance(self.catalog_data['Products'], dict):
            self.u.cprint("Catalog data or 'Products' dictionary is invalid/missing.", "red"); return
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

# --- Main Application Class (SkyscopeTool) ---
class SkyscopeTool:
    def __init__(self):
        self.u = Utils()
        self.d = Downloader(self.u)
        self.cm = CatalogManager(self.u, self.d)
        self.main_download_cache_dir = DOWNLOAD_CACHE_DIR
        self.temp_dir_base = DOWNLOAD_CACHE_DIR / "temp_extractions"
        self.is_linux = sys.platform.startswith("linux")
        self.disk_mgr = None
        if self.is_linux:
            try:
                from skyscope_diskutils_linux import Disk as LinuxDiskManager
                self.disk_mgr = LinuxDiskManager(self.u)
                self.u.cprint("Linux Disk Manager initialized.", "green")
            except ImportError: self.u.cprint("LinuxDiskManager not found. USB creation disabled.", "yellow")
            except Exception as e: self.u.cprint(f"Error initializing LinuxDiskManager: {e}", "red")
        else: self.u.cprint("Non-Linux platform. USB creation disabled.", "yellow")
        self.show_all_removable_disks_toggle = False
        try:
            self.temp_dir_base.mkdir(parents=True, exist_ok=True)
        except OSError as e:
             self.u.cprint(f"Could not create base temp directory '{self.temp_dir_base}': {e}", "red")


    def display_main_menu(self):
        self.u.head("Skyscope macOS USB Creator Tool - Main Menu")
        self.u.cprint("1. Download macOS Installer", "green")
        self.u.cprint("2. Create macOS Bootable USB (Linux Only)", "green")
        self.u.cprint("H. Help / Explanations", "green")
        self.u.cprint("Q. Quit", "green")
        return input("Enter your choice: ").strip().lower()

    def _run_command(self, command_list, step_name="Command", check=False, shell=False, input_str=None):
        self.u.cprint(f"  Executing: {' '.join(command_list) if not shell else command_list}", "green")
        try:
            process_input = input_str.encode() if input_str else None
            result = subprocess.run(
                command_list, capture_output=True,
                text=(input_str is None), input=process_input,
                shell=shell, check=check
            )
            if not check and result.returncode != 0:
                 self.u.cprint(f"Warning: '{step_name}' (cmd: '{command_list[0]}') exited with {result.returncode}.", "yellow")
                 stdout = result.stdout.decode() if isinstance(result.stdout, bytes) else result.stdout
                 stderr = result.stderr.decode() if isinstance(result.stderr, bytes) else result.stderr
                 if stdout: self.u.cprint(f"  Stdout:\n{stdout.strip()}", "yellow")
                 if stderr: self.u.cprint(f"  Stderr:\n{stderr.strip()}", "yellow")
            return result
        except FileNotFoundError: self.u.cprint(f"Error: Utility '{command_list[0]}' not found.", "red"); return None
        except subprocess.CalledProcessError as e:
            self.u.cprint(f"Error during '{step_name}': Cmd '{e.cmd}' failed (code {e.returncode}).", "red")
            if e.stdout: self.u.cprint(f"  Stdout:\n{e.stdout.strip()}", "yellow")
            if e.stderr: self.u.cprint(f"  Stderr:\n{e.stderr.strip()}", "yellow")
            return None
        except Exception as e: self.u.cprint(f"Unexpected error running '{command_list[0]}': {e}", "red"); return None

    def _unmount_device_partitions(self, device_path):
        self.u.cprint(f"Attempting to unmount all partitions on '{device_path}' before partitioning...", "green")
        success_overall = True; cmd = ["lsblk", "-Jp", "-o", "NAME,MOUNTPOINT", device_path]
        lsblk_result = self._run_command(cmd, step_name="List Mountpoints", check=False)
        if not lsblk_result or lsblk_result.returncode != 0: self.u.cprint(f"Error listing mountpoints for '{device_path}'.", "red"); return False
        try:
            data = json.loads(lsblk_result.stdout); mountpoints_to_unmount = []
            for dev_info_top in data.get('blockdevices', []):
                if dev_info_top.get('name') == device_path:
                    if dev_info_top.get('mountpoint'): mountpoints_to_unmount.append(dev_info_top['mountpoint'])
                    for part_info in dev_info_top.get('children', []):
                        if part_info.get('mountpoint'): mountpoints_to_unmount.append(part_info['mountpoint'])
            mountpoints_to_unmount = sorted(list(set(mountpoints_to_unmount)), reverse=True)
            if not mountpoints_to_unmount: self.u.cprint(f"  No mounted partitions on '{device_path}'.", "green"); return True
            self.u.cprint(f"  Mounted: {', '.join(mountpoints_to_unmount)}. Unmounting...", "green")
            for mp in mountpoints_to_unmount:
                umount_result = self._run_command(["umount", "-lf", mp], f"Unmount '{mp}'", check=False)
                if not umount_result or umount_result.returncode != 0: self.u.cprint(f"  Warn: Failed to unmount '{mp}'.", "yellow"); success_overall = False
            if success_overall: self.u.cprint(f"  Unmounted all on '{device_path}'.", "green")
            else: self.u.cprint(f"  Warn: Some partitions on '{device_path}' may remain mounted.", "yellow")
            return success_overall
        except Exception as e: self.u.cprint(f"Error during unmount for '{device_path}': {e}", "red"); return False

    def prepare_usb_device(self, device_path, volume_name="macOS_Install", gpt_scheme=True):
        global selected_version_key_for_global_context
        version_display_name = volume_name
        if selected_version_key_for_global_context and selected_version_key_for_global_context in self.cm.products:
            version_display_name = self.cm.products[selected_version_key_for_global_context].get('title', volume_name)
        elif selected_version_key_for_global_context:
             version_display_name = selected_version_key_for_global_context

        self.u.head(f"Preparing USB Device: {device_path}")
        self.u.cprint(f"Targeting device: '{device_path}' for {version_display_name} installer.", "green")
        self.u.cprint(f"Partition scheme: {'GPT (UEFI)' if gpt_scheme else 'MBR (Legacy/BIOS)'}.", "green")
        self.u.cprint(f"Main HFS+ volume name will be: '{volume_name}'. EFI partition will be 'EFI'.", "green")

        if not self._unmount_device_partitions(device_path):
            self.u.cprint(f"Critical Error: Failed to unmount partitions on '{device_path}'. Aborting disk preparation.", "red")
            return False

        part_suffix1 = "p1" if "nvme" in device_path else "1"
        part_suffix2 = "p2" if "nvme" in device_path else "2"
        efi_part = device_path + part_suffix1
        hfs_part = device_path + part_suffix2

        if gpt_scheme:
            self.u.cprint(f"Step 1: Creating GPT partition table on '{device_path}'...", "green")
            if not self._run_command(["parted", "-s", device_path, "mklabel", "gpt"], "Create GPT label"): return False
            self.u.cprint(f"Step 2: Creating EFI System Partition (ESP) on '{efi_part}'...", "green")
            if not self._run_command(["parted", "-s", "-a", "optimal", device_path, "mkpart", "ESP", "fat32", "1MiB", "201MiB"], "Create ESP"): return False
            if not self._run_command(["mkfs.vfat", "-F32", "-n", "EFI", efi_part], f"Format {efi_part} as FAT32"): return False
            if not self._run_command(["parted", "-s", device_path, "set", "1", "boot", "on"], f"Set 'boot' flag on {efi_part}"): return False
            if not self._run_command(["parted", "-s", device_path, "set", "1", "esp", "on"], f"Set 'esp' flag on {efi_part}"): return False
            self.u.cprint(f"Step 3: Creating HFS+ partition for macOS installer on '{hfs_part}'...", "green")
            if not self._run_command(["parted", "-s", "-a", "optimal", device_path, "mkpart", "Apple_HFS", "hfs+", "201MiB", "100%"], "Create HFS+ partition"): return False
            if not self._run_command(["mkfs.hfsplus", "-J", "-v", volume_name, hfs_part], f"Format {hfs_part} as HFS+"): return False
        else: # MBR
            self.u.cprint(f"Step 1: Creating MBR (msdos) partition table on '{device_path}'...", "green")
            if not self._run_command(["parted", "-s", device_path, "mklabel", "msdos"], "Create MBR label"): return False
            self.u.cprint(f"Step 2: Creating FAT32 boot partition on '{efi_part}'...", "green")
            if not self._run_command(["parted", "-s", "-a", "optimal", device_path, "mkpart", "primary", "fat32", "1MiB", "201MiB"], "Create FAT32 (MBR)"): return False
            if not self._run_command(["mkfs.vfat", "-F32", "-n", "EFI", efi_part], f"Format {efi_part} as FAT32"): return False
            if not self._run_command(["parted", "-s", device_path, "set", "1", "boot", "on"], f"Set 'boot' flag on {efi_part}"): return False
            self.u.cprint(f"Step 3: Creating HFS+ partition for macOS installer on '{hfs_part}'...", "green")
            if not self._run_command(["parted", "-s", "-a", "optimal", device_path, "mkpart", "primary", "hfs+", "201MiB", "100%"], "Create HFS+ (MBR)"): return False
            if not self._run_command(["mkfs.hfsplus", "-J", "-v", volume_name, hfs_part], f"Format {hfs_part} as HFS+"): return False
            self.u.cprint(f"Step 4: Setting MBR partition type for '{hfs_part}' to AF (Apple HFS+)...", "green")
            fdisk_res = self._run_command(["fdisk", device_path], "Set MBR type", check=False, input_str=f"t\n2\naf\nw\n")
            if not fdisk_res or fdisk_res.returncode != 0: self.u.cprint(f"Warn: fdisk type setting for {hfs_part} may have issues.", "yellow")
        self.u.cprint(f"Step 5: Synchronizing disk changes with kernel for '{device_path}'...", "green")
        self._run_command(["sync"], "Sync buffers", check=False)
        if not self._run_command(["partprobe", device_path], f"Partprobe {device_path}", check=False):
            self._run_command(["blockdev", "--rereadpt", device_path], f"Blockdev rereadpt {device_path}", check=False)
        self.u.cprint(f"Disk '{device_path}' prepared successfully for {('GPT' if gpt_scheme else 'MBR')} scheme.", "green"); return True

    def _find_file_recursive(self, search_root_dir, filename_to_find):
        for root, _, files in os.walk(search_root_dir):
            if filename_to_find in files:
                return pathlib.Path(root) / filename_to_find
        return None

    def _extract_archive(self, archive_path, out_dir, step_name="Extract Archive"):
        self.u.cprint(f"  Extracting '{archive_path}' to '{out_dir}'...", "green")
        extract_cmd = ["7z", "x", str(archive_path), f"-o{str(out_dir)}", "-aoa"] # -aoa to overwrite
        result = self._run_command(extract_cmd, step_name, check=False)
        if result and result.returncode == 0:
            self.u.cprint(f"  Successfully extracted '{archive_path}'.", "green")
            return True
        else:
            self.u.cprint(f"  Error extracting '{archive_path}'. 7z exit code: {result.returncode if result else 'N/A'}", "red")
            if out_dir.exists():
                try:
                    extracted_items = list(out_dir.iterdir())
                    if not extracted_items:
                        self.u.cprint(f"  Output directory '{out_dir}' is empty after failed extraction.", "yellow")
                    else:
                        self.u.cprint(f"  Output directory '{out_dir}' contains items despite extraction error. Contents might be incomplete.", "yellow")
                except Exception as e_ls:
                    self.u.cprint(f"  Could not list contents of '{out_dir}' after failed extraction: {e_ls}", "yellow")
            return False

    def extract_macos_payload(self, downloaded_image_path_str, per_call_temp_base_dir_str):
        self.u.head(f"Extract macOS Payload from: {downloaded_image_path_str}")
        downloaded_image_path = pathlib.Path(downloaded_image_path_str)
        current_job_extract_dir = None
        final_payload_output_dir = None

        try:
            current_job_extract_dir = pathlib.Path(tempfile.mkdtemp(prefix="extract_job_", dir=per_call_temp_base_dir_str))
            self.u.cprint(f"  Created temporary working directory: {current_job_extract_dir}", "green")

            if not downloaded_image_path.exists():
                self.u.cprint(f"Error: Downloaded image '{downloaded_image_path}' not found.", "red")
                return None

            is_dmg = downloaded_image_path.name.lower().endswith(".dmg")
            is_pkg = downloaded_image_path.name.lower().endswith(".pkg")

            if is_pkg:
                self.u.cprint(f"Processing .pkg file: {downloaded_image_path.name}...", "green")
                pkg_contents_dir = current_job_extract_dir / "pkg_extracted"
                if not self._extract_archive(downloaded_image_path, pkg_contents_dir, "Extract PKG"):
                    return None

                app_path_search = list(pkg_contents_dir.glob("Install macOS*.app"))
                if app_path_search:
                    macos_app_path = app_path_search[0]
                    self.u.cprint(f"  Found .app bundle: '{macos_app_path.name}' within PKG.", "green")
                    shared_support_dmg = macos_app_path / "Contents" / "SharedSupport" / "SharedSupport.dmg"
                    if shared_support_dmg.exists():
                        self.u.cprint(f"  Found SharedSupport.dmg at: {shared_support_dmg}. Processing it...", "green")
                        return self.extract_macos_payload(str(shared_support_dmg), per_call_temp_base_dir_str)
                    install_esd_in_app = macos_app_path / "Contents" / "SharedSupport" / "InstallESD.dmg"
                    if install_esd_in_app.exists():
                        self.u.cprint(f"  Found InstallESD.dmg in .app at: {install_esd_in_app}. Processing it...", "green")
                        return self.extract_macos_payload(str(install_esd_in_app), per_call_temp_base_dir_str)
                    self.u.cprint(f"  No standard SharedSupport.dmg or InstallESD.dmg found within '{macos_app_path.name}'.", "yellow")

                install_esd_dmg_path = self._find_file_recursive(pkg_contents_dir, "InstallESD.dmg")
                if install_esd_dmg_path:
                    self.u.cprint(f"  Found InstallESD.dmg directly in PKG contents at: {install_esd_dmg_path}. Processing it...", "green")
                    return self.extract_macos_payload(str(install_esd_dmg_path), per_call_temp_base_dir_str)

                self.u.cprint("  Could not find a usable DMG (SharedSupport.dmg or InstallESD.dmg) within the PKG.", "red")
                return None

            elif is_dmg:
                self.u.cprint(f"Processing .dmg file: {downloaded_image_path.name}...", "green")
                dmg_contents_dir = current_job_extract_dir / "dmg_extracted"
                if not self._extract_archive(downloaded_image_path, dmg_contents_dir, f"Extract DMG {downloaded_image_path.name}"):
                    return None

                found_bsd_path = self._find_file_recursive(dmg_contents_dir, "BaseSystem.dmg")
                found_bsc_path = None
                if found_bsd_path:
                    found_bsc_path = found_bsd_path.parent / "BaseSystem.chunklist"
                    if not found_bsc_path.exists(): found_bsc_path = None

                if found_bsd_path and found_bsc_path:
                    self.u.cprint(f"  Found BaseSystem.dmg and BaseSystem.chunklist in: {found_bsd_path.parent}", "green")
                    final_payload_output_dir = pathlib.Path(tempfile.mkdtemp(prefix="final_payload_", dir=per_call_temp_base_dir_str))
                    shutil.copy2(found_bsd_path, final_payload_output_dir / "BaseSystem.dmg")
                    shutil.copy2(found_bsc_path, final_payload_output_dir / "BaseSystem.chunklist")
                    self.u.cprint(f"  Copied BaseSystem.dmg and .chunklist to stable temp dir: {final_payload_output_dir}", "green")
                    return str(final_payload_output_dir)

                dmg_name_lower = downloaded_image_path.name.lower()
                if "installesd.dmg" in dmg_name_lower or \
                   "installmacosx.dmg" in dmg_name_lower or \
                   (dmg_name_lower.startswith("macos_") and dmg_name_lower.endswith(".dmg")):
                    self.u.cprint(f"  Note: '{downloaded_image_path.name}' might be a direct bootable HFS+ image (BaseSystem.dmg not found).", "yellow")
                    self.u.cprint(f"  Copying original DMG as the final payload. This may need specific handling during USB writing.", "yellow")
                    final_payload_output_dir = pathlib.Path(tempfile.mkdtemp(prefix="final_direct_dmg_", dir=per_call_temp_base_dir_str))
                    shutil.copy2(downloaded_image_path, final_payload_output_dir / downloaded_image_path.name)
                    self.u.cprint(f"  Copied original DMG '{downloaded_image_path.name}' to stable temp dir: {final_payload_output_dir}", "green")
                    return str(final_payload_output_dir)

                if "installesd.dmg" not in dmg_name_lower :
                    nested_esd = self._find_file_recursive(dmg_contents_dir, "InstallESD.dmg")
                    if nested_esd:
                        self.u.cprint(f"  Found nested InstallESD.dmg at: {nested_esd}. Processing it recursively...", "green")
                        return self.extract_macos_payload(str(nested_esd), per_call_temp_base_dir_str)

                self.u.cprint(f"Error: Could not find 'BaseSystem.dmg' + '.chunklist', nor identify a direct-use DMG within '{downloaded_image_path.name}'.", "red")
                return None
            else:
                self.u.cprint(f"Error: Unsupported file type '{downloaded_image_path.suffix}'. Only .pkg and .dmg are supported.", "red")
                return None
        finally:
            if current_job_extract_dir and current_job_extract_dir.exists():
                self.u.cprint(f"  Cleaning up temporary job extraction directory: {current_job_extract_dir}", "green")
                shutil.rmtree(current_job_extract_dir, ignore_errors=True)
            # Note: final_payload_output_dir (if created) is NOT cleaned up here. Its path is returned.

    def write_macos_to_usb(self, extracted_payload_dir_str, target_hfs_partition_path_str, version_name):
        self.u.head(f"Writing macOS {version_name} to USB Partition: {target_hfs_partition_path_str}")

        extracted_payload_path = pathlib.Path(extracted_payload_dir_str)
        hfs_mount_point = None # Define before try
        success_flag = False

        try:
            hfs_mount_point = pathlib.Path(tempfile.mkdtemp(prefix="hfs_mount_", dir=self.temp_dir_base))
            self.u.cprint(f"  Temporary mount point for HFS+ partition: {hfs_mount_point}", "green")

            # Determine payload type from extracted_payload_dir_str
            base_system_dmg = extracted_payload_path / "BaseSystem.dmg"
            base_system_chunklist = extracted_payload_path / "BaseSystem.chunklist"

            # Check for single DMG file (e.g. InstallMacOSX.dmg for El Capitan)
            payload_files = list(extracted_payload_path.iterdir())
            direct_dmg_installer = None
            if len(payload_files) == 1 and payload_files[0].name.lower().endswith(".dmg"):
                # This assumes extract_macos_payload copied the original DMG into this dir
                if payload_files[0].name == "BaseSystem.dmg" and not (extracted_payload_path / "BaseSystem.chunklist").exists():
                    # If it's BaseSystem.dmg but no chunklist, treat as error for modern path
                     self.u.cprint(f"Error: Found BaseSystem.dmg but BaseSystem.chunklist is missing in {extracted_payload_path}.", "red")
                     return False # Or handle as a direct DMG if that's ever a case for BaseSystem.dmg
                elif payload_files[0].name != "BaseSystem.dmg": # It's some other DMG
                    direct_dmg_installer = payload_files[0]


            if direct_dmg_installer:
                self.u.cprint(f"  Found direct DMG installer: '{direct_dmg_installer.name}'.", "green")
                self.u.cprint(f"  This DMG will be written directly to '{target_hfs_partition_path_str}' using 'dd'.", "green")
                self.u.cprint("  The HFS+ partition should NOT be mounted for 'dd'.", "yellow")
                # No mounting needed for dd.

                dd_cmd = ["dd", f"if={str(direct_dmg_installer)}", f"of={target_hfs_partition_path_str}", "bs=4M", "status=progress", "conv=fsync"]
                if self._run_command(dd_cmd, "Write direct DMG to HFS+ partition", check=False):
                    self.u.cprint(f"  Successfully wrote '{direct_dmg_installer.name}' to '{target_hfs_partition_path_str}'.", "green")
                    success_flag = True
                else:
                    self.u.cprint(f"  Error writing '{direct_dmg_installer.name}' using 'dd'. USB may not be bootable.", "red")
                    success_flag = False # dd failed

            elif base_system_dmg.exists() and base_system_chunklist.exists():
                self.u.cprint(f"  Found BaseSystem.dmg and BaseSystem.chunklist in '{extracted_payload_path}'.", "green")
                self.u.cprint(f"  Mounting HFS+ partition '{target_hfs_partition_path_str}' to '{hfs_mount_point}'...", "green")
                mount_result = self._run_command(["mount", target_hfs_partition_path_str, str(hfs_mount_point)], "Mount HFS+ partition", check=False)
                if not mount_result or mount_result.returncode != 0:
                    self.u.cprint(f"  Error mounting HFS+ partition '{target_hfs_partition_path_str}'. Cannot copy files.", "red")
                    return False # Critical if we can't mount

                app_name = f"Install macOS {version_name}.app"
                app_path_on_usb = hfs_mount_point / app_name
                shared_support_dir = app_path_on_usb / "Contents" / "SharedSupport"

                self.u.cprint(f"  Creating installer app structure: '{shared_support_dir}'...", "green")
                try:
                    shared_support_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    self.u.cprint(f"  Error creating directory '{shared_support_dir}': {e}", "red")
                    return False

                self.u.cprint(f"  Copying 'BaseSystem.dmg' to '{shared_support_dir}'...", "green")
                shutil.copy2(base_system_dmg, shared_support_dir / "BaseSystem.dmg")
                self.u.cprint(f"  Copying 'BaseSystem.chunklist' to '{shared_support_dir}'...", "green")
                shutil.copy2(base_system_chunklist, shared_support_dir / "BaseSystem.chunklist")

                # TODO: Create a minimal Info.plist for the .app, copy other necessary files
                # For now, this is a simplified approach.
                self.u.cprint("  Copied BaseSystem.dmg and .chunklist to USB.", "green")
                self.u.cprint("  Note: A full installer app structure might require more files (Info.plist, etc.).", "yellow")
                success_flag = True

            else:
                self.u.cprint(f"Error: Unrecognized payload structure in '{extracted_payload_dir_str}'.", "red")
                self.u.cprint("  Expected either 'BaseSystem.dmg' + 'BaseSystem.chunklist', or a single direct-use .dmg file.", "red")
                return False # Payload not recognized

            return success_flag

        finally:
            if hfs_mount_point and hfs_mount_point.is_mount(): # Check if mounted before trying to unmount
                self.u.cprint(f"  Unmounting HFS+ partition '{hfs_mount_point}'...", "green")
                self._run_command(["sync"], "Sync before unmount", check=False)
                self._run_command(["umount", str(hfs_mount_point)], f"Unmount {hfs_mount_point}", check=False)
            if hfs_mount_point and hfs_mount_point.exists(): # Clean up mount point dir
                shutil.rmtree(hfs_mount_point, ignore_errors=True)

            # Clean up the directory that extract_macos_payload returned (final_payload_output_dir)
            if extracted_payload_path.exists():
                self.u.cprint(f"  Cleaning up source extracted payload directory: {extracted_payload_path}", "green")
                shutil.rmtree(extracted_payload_path, ignore_errors=True)


    def _select_usb_device(self):
        # (Content remains the same as previous version)
        if not self.is_linux or not self.disk_mgr:
            self.u.cprint("USB device selection is only available on Linux and requires the disk manager.", "red")
            return None
        self.u.head("Select Target USB Device for macOS Installer")
        self.u.cprint("WARNING: ALL DATA ON THE SELECTED USB DEVICE WILL BE PERMANENTLY ERASED!", "red")
        self.u.cprint("Please double-check the device path, size, and model before proceeding.", "red")
        self.disk_mgr.update()
        candidate_disks = self.disk_mgr.get_filtered_disks(
            show_all_disks=self.show_all_removable_disks_toggle,
            require_usb_transport=not self.show_all_removable_disks_toggle
        )
        if not candidate_disks:
            self.u.cprint("No suitable USB drives found. Ensure your USB drive is connected.", "yellow")
            if not self.show_all_removable_disks_toggle:
                 self.u.cprint("You can try toggling the 'show all removable disks' option if your USB drive is unusual.", "green")
            return None
        self.u.cprint("Available suitable disk devices:", "green")
        for i, disk_info in enumerate(candidate_disks):
            size_gb = disk_info.get('size', 0) / (1024**3) if disk_info.get('size') else 0
            model = disk_info.get('model', 'N/A')
            path = disk_info.get('path', 'N/A')
            self.u.cprint(f"  {i+1}. {path:<12} Model: {model:<25} Size: {size_gb:>6.2f} GB", "green")
        while True:
            try:
                choice_str = input("Enter number of the USB device (or 'B' to Back): ").strip().lower()
                if choice_str == 'b': return None
                choice_idx = int(choice_str) - 1
                if 0 <= choice_idx < len(candidate_disks):
                    selected_disk = candidate_disks[choice_idx]
                    selected_disk_path = selected_disk['path']
                    self.u.cprint(f"You selected: {selected_disk_path} - {selected_disk.get('model', 'N/A')} ({selected_disk.get('size',0)/(1024**3):.2f}GB)", "yellow")
                    confirm = input(f"Type 'ERASE-{selected_disk_path.split('/')[-1]}' to confirm selection and proceed with erasure: ").strip()
                    if confirm == f"ERASE-{selected_disk_path.split('/')[-1]}":
                        self.u.cprint(f"Confirmed selection for erasure: {selected_disk_path}", "red")
                        return selected_disk_path
                    else:
                        self.u.cprint("Confirmation failed. USB device selection cancelled.", "yellow")
                        return None
                else:
                    self.u.cprint(f"Invalid selection. Please enter a number between 1 and {len(candidate_disks)}.", "yellow")
            except ValueError:
                self.u.cprint("Invalid input. Please enter a number or 'B'.", "yellow")
            except Exception as e:
                self.u.cprint(f"An error occurred during USB selection: {e}", "red")
                return None
        return None

    def handle_download_menu(self):
        # (Content remains the same as previous version)
        self.u.head("Download macOS Installer")
        cat_type_choice = input("Select catalog type (1=PublicRelease, 2=Beta, 3=DeveloperSeed; default=1): ").strip()
        catalog_type = "publicrelease"
        if cat_type_choice == '2': catalog_type = "customerseed"
        elif cat_type_choice == '3': catalog_type = "developerbeta"
        try:
            major_version_input = input(f"Enter target major macOS version (e.g., 14 for Sonoma, 13 for Ventura; default=14): ").strip()
            major_version_target_os = int(major_version_input) if major_version_input else 14
            internal_major_version = major_version_target_os
            if 11 <= major_version_target_os <= 14:
                internal_major_version = major_version_target_os + 5
            elif major_version_target_os == 10:
                 internal_major_version = 15
            elif major_version_target_os > 19 or major_version_target_os < 8 :
                 self.u.cprint(f"Version {major_version_target_os} may not map to standard catalog strings correctly, using as is.", "yellow")
        except ValueError:
            self.u.cprint("Invalid version number. Defaulting to latest (Sonoma-era).", "yellow")
            internal_major_version = 19
        force_refresh_choice = input("Force refresh catalog from Apple? (y/N, default: N): ").lower().strip() or "n"
        force_refresh = True if force_refresh_choice == 'y' else False
        if self.cm.fetch_catalog(catalog_type=catalog_type, major_macos_version=internal_major_version, force_refresh=force_refresh):
            selected_product = self.cm.select_product(require_full_installer=True)
            if selected_product and selected_product not in ["BACK", "QUIT"]:
                self.u.head(f"Confirm Download: {selected_product['title']}")
                self.u.cprint(f"  Version: {selected_product['version']}, Build: {selected_product['build']}", "green")
                self.u.cprint(f"  Total Size: {selected_product['size_bytes'] / (1024**3) :.2f} GB", "green")
                confirm_download = input("Proceed with download? (Y/n, default: Y): ").lower().strip() or "y"
                if confirm_download == 'y':
                    self.main_download_cache_dir.mkdir(parents=True, exist_ok=True)
                    self.cm.download_product(selected_product, str(self.main_download_cache_dir))
                else:
                    self.u.cprint("Download cancelled by user.", "yellow")
            elif selected_product == "BACK":
                 self.u.cprint("Returning to main menu.", "green")
        else:
            self.u.cprint("Failed to load catalog. Cannot select product.", "red")

    def handle_create_usb_menu(self):
        self.u.head("Create macOS Bootable USB")
        if not self.is_linux or not self.disk_mgr:
            self.u.cprint("This feature is currently only supported on Linux and requires disk utilities.", "red")
            self.u.cprint("Please ensure you are on Linux and 'lsblk' is available.", "red")
            return

        selected_usb_path = self._select_usb_device()
        if not selected_usb_path:
            self.u.cprint("USB device selection cancelled or failed. Returning to main menu.", "yellow")
            return

        self.u.cprint(f"Selected USB device for macOS Installer: {selected_usb_path}", "green")

        self.u.cprint("Please select the macOS product you want to install to the USB.", "green")
        if not self.cm.products:
            self.u.cprint("No macOS products loaded. Please run 'Download macOS Installer' first to populate the catalog.", "yellow")
            fetch_now = input("Fetch catalog now? (y/N): ").lower().strip() or 'n'
            if fetch_now == 'y':
                if not self.cm.fetch_catalog():
                    self.u.cprint("Failed to fetch catalog. Cannot proceed.", "red")
                    return
            else: return

        selected_product = self.cm.select_product(require_full_installer=True)
        if not selected_product or selected_product in ["BACK", "QUIT"]:
            self.u.cprint("No macOS product selected for USB creation. Returning to main menu.", "yellow")
            return

        volume_name = selected_product['title'].replace(' ', '_')

        product_title_slug = selected_product.get('title', 'UnknownProduct').replace(' ', '_').replace('/', '_')
        assumed_installer_filename = "InstallAssistant.pkg"
        if selected_product['packages']:
             assumed_installer_filename = os.path.basename(urlparse(selected_product['packages'][0]['URL']).path)

        downloaded_image_path = self.main_download_cache_dir / product_title_slug / assumed_installer_filename

        if not downloaded_image_path.exists():
            self.u.cprint(f"Installer for {selected_product['title']} not found at: {downloaded_image_path}", "yellow")
            confirm_dl = input("Download it now? (Y/n): ").lower().strip() or 'y'
            if confirm_dl == 'y':
               if not self.cm.download_product(selected_product, str(self.main_download_cache_dir)):
                   self.u.cprint("Download failed. Cannot proceed with USB creation.", "red")
                   return
            else: self.u.cprint("Download declined. Cannot proceed.", "yellow"); return
        self.u.cprint(f"Using downloaded image: {downloaded_image_path}", "green")

        gpt_choice = input("Use GPT partitioning (recommended for UEFI)? (Y/n, default: Y): ").lower().strip() or "y"
        use_gpt = True if gpt_choice == 'y' else False
        self.u.cprint(f"Using {'GPT' if use_gpt else 'MBR'} partitioning scheme.", "green")

        if self.prepare_usb_device(selected_usb_path, volume_name=volume_name, gpt_scheme=use_gpt):
            self.u.cprint(f"USB device '{selected_usb_path}' prepared successfully for {selected_product['title']}.", "green")

            self.temp_dir_base.mkdir(parents=True, exist_ok=True)
            final_payload_dir_path_str = self.extract_macos_payload(str(downloaded_image_path), str(self.temp_dir_base))

            if final_payload_dir_path_str:
                self.u.cprint(f"macOS payload extracted to temporary location: {final_payload_dir_path_str}", "green")

                target_hfs_partition = selected_usb_path + ("p2" if "nvme" in selected_usb_path else "2")

                if self.write_macos_to_usb(final_payload_dir_path_str, target_hfs_partition, selected_product['title']):
                    self.u.cprint("Successfully wrote macOS content to USB.", "green")
                    # Next: Bootloader installation
                    self.u.cprint("Next step: Bootloader installation (not yet fully implemented).", "yellow")
                else:
                    self.u.cprint("Failed to write macOS content to USB.", "red")

                # Cleanup of final_payload_dir_path_str is handled within write_macos_to_usb's finally block
            else:
                self.u.cprint("Failed to extract macOS payload. Cannot proceed with USB creation.", "red")
        else:
            self.u.cprint(f"Failed to prepare USB device '{selected_usb_path}'. Check errors above.", "red")


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
                self.u.cprint("Help / Explanations feature not fully integrated here yet.", "yellow")
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

The `write_macos_to_usb` method has been implemented in `macos_usb_tool.py`.

**Key Changes:**

1.  **`SkyscopeTool.write_macos_to_usb` Method (New)**:
    *   **Arguments**: Takes `extracted_payload_dir_str` (path to the directory containing `BaseSystem.dmg`/`.chunklist` or a direct-use DMG), `target_hfs_partition_path_str` (e.g., `/dev/sdb2`), and `version_name` (for naming the `.app` bundle).
    *   **Temporary Mount Point**: Creates a temporary mount point for the HFS+ partition using `tempfile.mkdtemp()`.
    *   **`try...finally` Block**: Ensures the HFS+ partition is unmounted, the temporary mount point directory is removed, and the `extracted_payload_dir_str` (which was created by `extract_macos_payload`) is also cleaned up.
    *   **Mount HFS+ Partition**: Attempts to mount the target HFS+ partition. If it fails, the method returns `False`.
    *   **Payload Type Determination**:
        *   Checks for `BaseSystem.dmg` and `BaseSystem.chunklist` in `extracted_payload_dir_str`.
        *   If not found, it checks if `extracted_payload_dir_str` contains a single `.dmg` file (heuristically identifying it as a direct-use installer DMG like El Capitan's `InstallMacOSX.dmg`).
    *   **Scenario 1 (BaseSystem.dmg + .chunklist)**:
        *   Creates the directory structure `Install macOS [VersionName].app/Contents/SharedSupport/` on the mounted HFS+ partition.
        *   Copies `BaseSystem.dmg` and `BaseSystem.chunklist` from `extracted_payload_dir_str` into this `SharedSupport` directory.
        *   Prints a note that a full installer might require more files (this is a simplified approach for now).
    *   **Scenario 2 (Direct-use DMG)**:
        *   **Important**: Unmounts the HFS+ partition *before* using `dd`, as `dd` operates on the raw partition device.
        *   Uses `dd` (via `self._run_command`) to write the DMG file directly to `target_hfs_partition_path_str`.
        *   If `dd` fails, it reports an error and returns `False`.
    *   **Unrecognized Payload**: If neither of the above payload types is recognized, an error is reported, and the method returns `False`.
    *   Returns `True` if the relevant write operation was successful.

2.  **Integration into `SkyscopeTool.handle_create_usb_menu`**:
    *   After `extract_macos_payload` successfully returns a `final_payload_dir_path_str`:
        *   The target HFS+ partition path (e.g., `/dev/sdb2`) is determined.
        *   `self.write_macos_to_usb()` is called with the payload directory, HFS+ partition path, and the selected product's title as `version_name`.
        *   Success or failure of `write_macos_to_usb` is reported.
    *   The cleanup of `final_payload_dir_path_str` is now explicitly handled by the `finally` block within `write_macos_to_usb`.

**Considerations and Potential Issues:**

*   **`dd` to a Formatted Partition**: If `disk_part_erase` formats the HFS+ partition, and then `write_macos_to_usb` (for a direct-use DMG scenario) `dd`s an image over it, the initial formatting was redundant for that specific scenario. This is generally acceptable as `dd` will overwrite it. The key is that the partition *exists* and has the correct type if needed by the bootloader or OS.
*   **Completeness of `BaseSystem.dmg` copy**: For modern installers, simply copying `BaseSystem.dmg` and `.chunklist` into a basic `.app` structure is a significant simplification of what Apple's `createinstallmedia` does. While this might be enough for some bootloaders to find and start the installer, it might lack other necessary components for a fully functional installer experience or for all macOS versions. This is noted in the code with comments.
*   **Error Handling in `dd`**: `dd` can be slow. The `_run_command` helper captures output but doesn't show live progress for `dd` unless `status=progress` is universally supported and its output handled (it usually prints to stderr). The current `stream_to_file` has a simulated progress bar, but `_run_command` does not for generic commands.

This implementation provides the core logic for getting the extracted macOS files onto the USB's HFS+ partition based on the type of payload identified. The next steps would be to refine this (if needed based on testing different macOS versions) and then integrate the bootloader installation.
