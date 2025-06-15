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
        elif color == "green": print(text) # Basic green
        elif color == "cyan": print(text) # Basic cyan
        else: print(text) # Default
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

# --- EFI Config Manager ---
class EFIConfigManager:
    def __init__(self, utils_instance):
        self.u = utils_instance
        self.opencore_configs = {
            "oc_sandybridge_generic": """
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>#WARNING - 1</key>
    <string>This is a generic Sandy Bridge Sample.plist</string>
    <key>#WARNING - 2</key>
    <string>Ensure you understand ALL settings before booting.</string>
    <key>ACPI</key>
    <dict>
        <key>Add</key>
        <array/>
        <key>Delete</key>
        <array/>
        <key>Patch</key>
        <array/>
        <key>Quirks</key>
        <dict>
            <key>FadtEnableReset</key>
            <false/>
            <key>NormalizeHeaders</key>
            <false/>
            <key>RebaseRegions</key>
            <false/>
            <key>ResetHwSig</key>
            <false/>
            <key>ResetLogoStatus</key>
            <true/>
            <key>SyncTableIds</key>
            <false/>
        </dict>
    </dict>
    <key>Booter</key>
    <dict>
        <key>MmioWhitelist</key>
        <array/>
        <key>Patch</key>
        <array/>
        <key>Quirks</key>
        <dict>
            <key>AllowRelocationBlock</key>
            <false/>
            <key>AvoidRuntimeDefrag</key>
            <true/>
            <key>DevirtualiseMmio</key>
            <false/>
            <key>DisableSingleUser</key>
            <false/>
            <key>DisableVariableWrite</key>
            <false/>
            <key>DiscardHibernateMap</key>
            <false/>
            <key>EnableSafeModeSlide</key>
            <true/>
            <key>EnableWriteUnprotector</key>
            <true/>
            <key>ForceBooterSignature</key>
            <false/>
            <key>ForceExitBootServices</key>
            <false/>
            <key>ProtectMemoryRegions</key>
            <false/>
            <key>ProtectSecureBoot</key>
            <false/>
            <key>ProtectUefiServices</key>
            <false/>
            <key>ProvideCustomSlide</key>
            <true/>
            <key>ProvideMaxSlide</key>
            <integer>0</integer>
            <key>RebuildAppleMemoryMap</key>
            <false/>
            <key>ResizeAppleGpuBars</key>
            <integer>-1</integer>
            <key>SetupVirtualMap</key>
            <true/>
            <key>SignalAppleOS</key>
            <false/>
            <key>SyncRuntimePermissions</key>
            <false/>
        </dict>
    </dict>
    <key>DeviceProperties</key>
    <dict>
        <key>Add</key>
        <dict/>
        <key>Delete</key>
        <dict/>
    </dict>
    <key>Kernel</key>
    <dict>
        <key>Add</key>
        <array>
            <!-- Essential Kexts will be added by the script -->
        </array>
        <key>Block</key>
        <array/>
        <key>Emulate</key>
        <dict>
            <key>Cpuid1Data</key>
            <data></data>
            <key>Cpuid1Mask</key>
            <data></data>
            <key>DummyPowerManagement</key>
            <true/>
            <key>MaxKernel</key>
            <string></string>
            <key>MinKernel</key>
            <string></string>
        </dict>
        <key>Force</key>
        <array/>
        <key>Patch</key>
        <array/>
        <key>Quirks</key>
        <dict>
            <key>AppleCpuPmCfgLock</key>
            <true/>
            <key>AppleXcpmCfgLock</key>
            <true/>
            <key>AppleXcpmExtraMsrs</key>
            <false/>
            <key>AppleXcpmForceBoost</key>
            <false/>
            <key>CustomPciSerialDevice</key>
            <false/>
            <key>CustomSMBIOSGuid</key>
            <false/>
            <key>DisableIoMapper</key>
            <true/>
            <key>DisableLinkeditJettison</key>
            <true/>
            <key>DisableRtcChecksum</key>
            <false/>
            <key>ExtendBTFeatureFlags</key>
            <false/>
            <key>ExternalDiskIcons</key>
            <false/>
            <key>ForceAquantiaEthernet</key>
            <false/>
            <key>ForceSecureBootScheme</key>
            <false/>
            <key>IncreasePciBarSize</key>
            <false/>
            <key>LapicKernelPanic</key>
            <false/>
            <key>LegacyCommpage</key>
            <false/>
            <key>PanicNoKextDump</key>
            <true/>
            <key>PowerTimeoutKernelPanic</key>
            <true/>
            <key>ProvideCurrentCpuInfo</key>
            <false/>
            <key>SetApfsTrimTimeout</key>
            <integer>-1</integer>
            <key>ThirdPartyDrives</key>
            <false/>
            <key>XhciPortLimit</key>
            <false/>
        </dict>
        <key>Scheme</key>
        <dict>
            <key>CustomKernel</key>
            <false/>
            <key>FuzzyMatch</key>
            <true/>
            <key>KernelArch</key>
            <string>Auto</string>
            <key>KernelCache</key>
            <string>Auto</string>
        </dict>
    </dict>
    <key>Misc</key>
    <dict>
        <key>BlessOverride</key>
        <array/>
        <key>Boot</key>
        <dict>
            <key>ConsoleAttributes</key>
            <integer>0</integer>
            <key>HibernateMode</key>
            <string>None</string>
            <key>HibernateSkipsPicker</key>
            <false/>
            <key>HideAuxiliary</key>
            <false/>
            <key>InstanceIdentifier</key>
            <string></string>
            <key>LauncherOption</key>
            <string>Disabled</string>
            <key>LauncherPath</key>
            <string>Default</string>
            <key>PickerAttributes</key>
            <integer>17</integer>
            <key>PickerAudioAssist</key>
            <false/>
            <key>PickerMode</key>
            <string>Builtin</string>
            <key>PickerVariant</key>
            <string>Auto</string>
            <key>PollAppleHotKeys</key>
            <false/>
            <key>ShowPicker</key>
            <true/>
            <key>TakeoffDelay</key>
            <integer>0</integer>
            <key>Timeout</key>
            <integer>5</integer>
        </dict>
        <key>Debug</key>
        <dict>
            <key>AppleDebug</key>
            <true/>
            <key>ApplePanic</key>
            <true/>
            <key>DisableWatchDog</key>
            <true/>
            <key>DisplayDelay</key>
            <integer>0</integer>
            <key>DisplayLevel</key>
            <integer>2147483650</integer>
            <key>LogModules</key>
            <string>*</string>
            <key>SysReport</key>
            <false/>
            <key>Target</key>
            <integer>67</integer>
        </dict>
        <key>Entries</key>
        <array/>
        <key>Security</key>
        <dict>
            <key>AllowSetDefault</key>
            <true/>
            <key>ApECID</key>
            <integer>0</integer>
            <key>AuthRestart</key>
            <false/>
            <key>BlacklistAppleUpdate</key>
            <true/>
            <key>DmgLoading</key>
            <string>Signed</string>
            <key>EnablePassword</key>
            <false/>
            <key>ExposeSensitiveData</key>
            <integer>6</integer>
            <key>HaltLevel</key>
            <integer>2147483648</integer>
            <key>PasswordHash</key>
            <data></data>
            <key>PasswordSalt</key>
            <data></data>
            <key>ScanPolicy</key>
            <integer>0</integer>
            <key>SecureBootModel</key>
            <string>Disabled</string>
            <key>Vault</key>
            <string>Optional</string>
        </dict>
        <key>Serial</key>
        <dict>
            <key>Custom</key>
            <dict>
                <key>BaudRate</key>
                <integer>115200</integer>
                <key>ClockRate</key>
                <integer>1843200</integer>
                <key>DetectCable</key>
                <false/>
                <key>ExtendedTxFifoSize</key>
                <integer>64</integer>
                <key>FifoControl</key>
                <integer>7</integer>
                <key>LineControl</key>
                <integer>3</integer>
                <key>PciDeviceInfo</key>
                <data>/w==</data>
                <key>RegisterAccessWidth</key>
                <integer>8</integer>
                <key>RegisterBase</key>
                <integer>1016</integer>
                <key>RegisterStride</key>
                <integer>1</integer>
                <key>UseHardwareFlowControl</key>
                <false/>
                <key>UseMmio</key>
                <false/>
            </dict>
            <key>Init</key>
            <false/>
            <key>Override</key>
            <false/>
        </dict>
        <key>Tools</key>
        <array/>
    </dict>
    <key>NVRAM</key>
    <dict>
        <key>Add</key>
        <dict>
            <key>4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14</key>
            <dict>
                <key>DefaultBackgroundColor</key>
                <data>AAAAAA==</data>
            </dict>
            <key>4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102</key>
            <dict>
                <key>rtc-blacklist</key>
                <data></data>
            </dict>
            <key>7C436110-AB2A-4BBB-A880-FE41995C9F82</key>
            <dict>
                <key>ForceDisplayRotationInEFI</key>
                <integer>0</integer>
                <key>SystemAudioVolume</key>
                <data>Rg==</data>
                <key>boot-args</key>
                <string>-v debug=0x100 keepsyms=1</string>
                <key>csr-active-config</key>
                <data>AAAAAA==</data>
                <key>prev-lang:kbd</key>
                <data>ZW4tVVM6MA==</data>
                <key>run-efi-updater</key>
                <string>No</string>
            </dict>
        </dict>
        <key>Delete</key>
        <dict>
            <key>4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14</key>
            <array>
                <string>DefaultBackgroundColor</string>
            </array>
            <key>4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102</key>
            <array>
                <string>rtc-blacklist</string>
            </array>
            <key>7C436110-AB2A-4BBB-A880-FE41995C9F82</key>
            <array>
                <string>boot-args</string>
                <string>ForceDisplayRotationInEFI</string>
            </array>
        </dict>
        <key>LegacyOverwrite</key>
        <false/>
        <key>LegacySchema</key>
        <dict>
            <key>7C436110-AB2A-4BBB-A880-FE41995C9F82</key>
            <array>
                <string>EFILoginHiDPI</string>
                <string>EFIBluetoothDelay</string>
                <string>LocationServicesEnabled</string>
                <string>SystemAudioVolume</string>
                <string>SystemAudioVolumeDB</string>
                <string>SystemAudioVolumeSaved</string>
                <string>bluetoothActiveControllerInfo</string>
                <string>bluetoothInternalControllerInfo</string>
                <string>flagstate</string>
                <string>fmm-computer-name</string>
                <string>fmm-mobileme-token-FMM</string>
                <string>fmm-mobileme-token-FMM-BridgeHasAccount</string>
                <string>nvda_drv</string>
                <string>prev-lang:kbd</string>
            </array>
            <key>8BE4DF61-93CA-11D2-AA0D-00E098032B8C</key>
            <array>
                <string>Boot0080</string>
                <string>Boot0081</string>
                <string>Boot0082</string>
                <string>BootNext</string>
                <string>BootOrder</string>
            </array>
        </dict>
        <key>WriteFlash</key>
        <true/>
    </dict>
    <key>PlatformInfo</key>
    <dict>
        <key>Automatic</key>
        <true/>
        <key>CustomMemory</key>
        <false/>
        <key>Generic</key>
        <dict>
            <key>AdviseFeatures</key>
            <false/>
            <key>MLB</key>
            <string>C0223030040F291A8</string>
            <key>MaxBIOSVersion</key>
            <false/>
            <key>ProcessorType</key>
            <integer>0</integer>
            <key>ROM</key>
            <data>ESIzRFVm</data>
            <key>SpoofVendor</key>
            <true/>
            <key>SystemMemoryStatus</key>
            <string>Auto</string>
            <key>SystemProductName</key>
            <string>iMac12,2</string>
            <key>SystemSerialNumber</key>
            <string>C02HHF2DHJQ0</string>
            <key>SystemUUID</key>
            <string>E4D22FE2-8246-4741-BA2A-CBD9924AB3A6</string>
        </dict>
        <key>UpdateDataHub</key>
        <true/>
        <key>UpdateNVRAM</key>
        <true/>
        <key>UpdateSMBIOS</key>
        <true/>
        <key>UpdateSMBIOSMode</key>
        <string>Create</string>
        <key>UseRawUuidEncoding</key>
        <false/>
    </dict>
    <key>UEFI</key>
    <dict>
        <key>APFS</key>
        <dict>
            <key>EnableJumpstart</key>
            <true/>
            <key>GlobalConnect</key>
            <false/>
            <key>HideVerbose</key>
            <true/>
            <key>JumpstartHotPlug</key>
            <false/>
            <key>MinDate</key>
            <integer>-1</integer>
            <key>MinVersion</key>
            <integer>-1</integer>
        </dict>
        <key>AppleInput</key>
        <dict>
            <key>AppleEvent</key>
            <string>Builtin</string>
            <key>CustomDelays</key>
            <false/>
            <key>GraphicsInputMirroring</key>
            <true/>
            <key>KeyInitialDelay</key>
            <integer>50</integer>
            <key>KeySubsequentDelay</key>
            <integer>5</integer>
            <key>PointerSpeedDiv</key>
            <integer>1</integer>
            <key>PointerSpeedMul</key>
            <integer>1</integer>
        </dict>
        <key>Audio</key>
        <dict>
            <key>AudioCodec</key>
            <integer>0</integer>
            <key>AudioDevice</key>
            <string>PciRoot(0x0)/Pci(0x1b,0x0)</string>
            <key>AudioOutMask</key>
            <integer>1</integer>
            <key>AudioSupport</key>
            <false/>
            <key>DisconnectHda</key>
            <false/>
            <key>MaximumGain</key>
            <integer>-15</integer>
            <key>MinimumAssistGain</key>
            <integer>-30</integer>
            <key>MinimumAudibleGain</key>
            <integer>-55</integer>
            <key>PlayChime</key>
            <string>Auto</string>
            <key>ResetTrafficClass</key>
            <false/>
            <key>SetupDelay</key>
            <integer>0</integer>
        </dict>
        <key>ConnectDrivers</key>
        <true/>
        <key>Drivers</key>
        <array>
            <!-- Essential Drivers will be added by the script -->
        </array>
        <key>Input</key>
        <dict>
            <key>KeyFiltering</key>
            <false/>
            <key>KeyForgetThreshold</key>
            <integer>5</integer>
            <key>KeySupport</key>
            <true/>
            <key>KeySupportMode</key>
            <string>Auto</string>
            <key>KeySwap</key>
            <false/>
            <key>PointerSupport</key>
            <false/>
            <key>PointerSupportMode</key>
            <string>ASUS</string>
            <key>TimerResolution</key>
            <integer>50000</integer>
        </dict>
        <key>Output</key>
        <dict>
            <key>ClearScreenOnModeSwitch</key>
            <false/>
            <key>ConsoleMode</key>
            <string></string>
            <key>DirectGopRendering</key>
            <false/>
            <key>ForceResolution</key>
            <false/>
            <key>GopPassThrough</key>
            <string>Disabled</string>
            <key>IgnoreTextInGraphics</key>
            <false/>
            <key>ProvideConsoleGop</key>
            <true/>
            <key>ReconnectGraphicsOnConnect</key>
            <false/>
            <key>ReconnectOnResChange</key>
            <false/>
            <key>ReplaceTabWithSpace</key>
            <false/>
            <key>Resolution</key>
            <string>Max</string>
            <key>SanitiseClearScreen</key>
            <false/>
            <key>TextRenderer</key>
            <string>BuiltinGraphics</string>
            <key>UIScale</key>
            <integer>-1</integer>
            <key>UgaPassThrough</key>
            <false/>
        </dict>
        <key>ProtocolOverrides</key>
        <dict>
            <key>AppleAudio</key>
            <false/>
            <key>AppleBootPolicy</key>
            <false/>
            <key>AppleDebugLog</key>
            <false/>
            <key>AppleEg2Info</key>
            <false/>
            <key>AppleFramebufferInfo</key>
            <false/>
            <key>AppleImageConversion</key>
            <false/>
            <key>AppleImg4Verification</key>
            <false/>
            <key>AppleKeyMap</key>
            <false/>
            <key>AppleRtcRam</key>
            <false/>
            <key>AppleSecureBoot</key>
            <false/>
            <key>AppleSmcIo</key>
            <false/>
            <key>AppleUserInterfaceTheme</key>
            <false/>
            <key>DataHub</key>
            <false/>
            <key>DeviceProperties</key>
            <false/>
            <key>FirmwareVolume</key>
            <true/>
            <key>HashServices</key>
            <false/>
            <key>OSInfo</key>
            <false/>
            <key>UnicodeCollation</key>
            <false/>
        </dict>
        <key>Quirks</key>
        <dict>
            <key>ActivateHpetSupport</key>
            <false/>
            <key>DisableSecurityPolicy</key>
            <false/>
            <key>EnableVectorAcceleration</key>
            <true/>
            <key>EnableVmx</key>
            <false/>
            <key>ExitBootServicesDelay</key>
            <integer>0</integer>
            <key>ForceOcWriteFlash</key>
            <false/>
            <key>ForgeUefiSupport</key>
            <false/>
            <key>IgnoreInvalidFlexRatio</key>
            <false/>
            <key>ReleaseUsbOwnership</key>
            <false/>
            <key>ReloadOptionRoms</key>
            <false/>
            <key>RequestBootVarRouting</key>
            <true/>
            <key>ResizeGpuBars</key>
            <integer>-1</integer>
            <key>TscSyncTimeout</key>
            <integer>0</integer>
            <key>UnblockFsConnect</key>
            <false/>
        </dict>
        <key>ReservedMemory</key>
        <array/>
    </dict>
</dict>
</plist>
""",
            "oc_ivybridge_generic": """
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>#WARNING - 1</key>
    <string>This is a generic Ivy Bridge Sample.plist</string>
    <key>#WARNING - 2</key>
    <string>Ensure you understand ALL settings before booting.</string>
    <key>ACPI</key>
    <dict>
        <key>Add</key>
        <array/>
        <key>Delete</key>
        <array/>
        <key>Patch</key>
        <array/>
        <key>Quirks</key>
        <dict>
            <key>FadtEnableReset</key>
            <false/>
            <key>NormalizeHeaders</key>
            <false/>
            <key>RebaseRegions</key>
            <false/>
            <key>ResetHwSig</key>
            <false/>
            <key>ResetLogoStatus</key>
            <true/>
            <key>SyncTableIds</key>
            <false/>
        </dict>
    </dict>
    <key>Booter</key>
    <dict>
        <key>MmioWhitelist</key>
        <array/>
        <key>Patch</key>
        <array/>
        <key>Quirks</key>
        <dict>
            <key>AllowRelocationBlock</key>
            <false/>
            <key>AvoidRuntimeDefrag</key>
            <true/>
            <key>DevirtualiseMmio</key>
            <false/>
            <key>DisableSingleUser</key>
            <false/>
            <key>DisableVariableWrite</key>
            <false/>
            <key>DiscardHibernateMap</key>
            <false/>
            <key>EnableSafeModeSlide</key>
            <true/>
            <key>EnableWriteUnprotector</key>
            <true/>
            <key>ForceBooterSignature</key>
            <false/>
            <key>ForceExitBootServices</key>
            <false/>
            <key>ProtectMemoryRegions</key>
            <false/>
            <key>ProtectSecureBoot</key>
            <false/>
            <key>ProtectUefiServices</key>
            <false/>
            <key>ProvideCustomSlide</key>
            <true/>
            <key>ProvideMaxSlide</key>
            <integer>0</integer>
            <key>RebuildAppleMemoryMap</key>
            <false/>
            <key>ResizeAppleGpuBars</key>
            <integer>-1</integer>
            <key>SetupVirtualMap</key>
            <true/>
            <key>SignalAppleOS</key>
            <false/>
            <key>SyncRuntimePermissions</key>
            <false/>
        </dict>
    </dict>
    <key>DeviceProperties</key>
    <dict>
        <key>Add</key>
        <dict/>
        <key>Delete</key>
        <dict/>
    </dict>
    <key>Kernel</key>
    <dict>
        <key>Add</key>
        <array>
            <!-- Essential Kexts will be added by the script -->
        </array>
        <key>Block</key>
        <array/>
        <key>Emulate</key>
        <dict>
            <key>Cpuid1Data</key>
            <data></data>
            <key>Cpuid1Mask</key>
            <data></data>
            <key>DummyPowerManagement</key>
            <false/> <!-- Ivy Bridge usually has native PM -->
            <key>MaxKernel</key>
            <string></string>
            <key>MinKernel</key>
            <string></string>
        </dict>
        <key>Force</key>
        <array/>
        <key>Patch</key>
        <array/>
        <key>Quirks</key>
        <dict>
            <key>AppleCpuPmCfgLock</key>
            <true/>
            <key>AppleXcpmCfgLock</key>
            <true/>
            <key>AppleXcpmExtraMsrs</key>
            <false/>
            <key>AppleXcpmForceBoost</key>
            <false/>
            <key>CustomPciSerialDevice</key>
            <false/>
            <key>CustomSMBIOSGuid</key>
            <false/>
            <key>DisableIoMapper</key>
            <true/>
            <key>DisableLinkeditJettison</key>
            <true/>
            <key>DisableRtcChecksum</key>
            <false/>
            <key>ExtendBTFeatureFlags</key>
            <false/>
            <key>ExternalDiskIcons</key>
            <false/>
            <key>ForceAquantiaEthernet</key>
            <false/>
            <key>ForceSecureBootScheme</key>
            <false/>
            <key>IncreasePciBarSize</key>
            <false/>
            <key>LapicKernelPanic</key>
            <false/>
            <key>LegacyCommpage</key>
            <false/>
            <key>PanicNoKextDump</key>
            <true/>
            <key>PowerTimeoutKernelPanic</key>
            <true/>
            <key>ProvideCurrentCpuInfo</key>
            <false/>
            <key>SetApfsTrimTimeout</key>
            <integer>-1</integer>
            <key>ThirdPartyDrives</key>
            <false/>
            <key>XhciPortLimit</key>
            <false/>
        </dict>
        <key>Scheme</key>
        <dict>
            <key>CustomKernel</key>
            <false/>
            <key>FuzzyMatch</key>
            <true/>
            <key>KernelArch</key>
            <string>Auto</string>
            <key>KernelCache</key>
            <string>Auto</string>
        </dict>
    </dict>
    <key>Misc</key>
    <dict>
        <key>BlessOverride</key>
        <array/>
        <key>Boot</key>
        <dict>
            <key>ConsoleAttributes</key>
            <integer>0</integer>
            <key>HibernateMode</key>
            <string>None</string>
            <key>HibernateSkipsPicker</key>
            <false/>
            <key>HideAuxiliary</key>
            <false/>
            <key>InstanceIdentifier</key>
            <string></string>
            <key>LauncherOption</key>
            <string>Disabled</string>
            <key>LauncherPath</key>
            <string>Default</string>
            <key>PickerAttributes</key>
            <integer>17</integer>
            <key>PickerAudioAssist</key>
            <false/>
            <key>PickerMode</key>
            <string>Builtin</string>
            <key>PickerVariant</key>
            <string>Auto</string>
            <key>PollAppleHotKeys</key>
            <false/>
            <key>ShowPicker</key>
            <true/>
            <key>TakeoffDelay</key>
            <integer>0</integer>
            <key>Timeout</key>
            <integer>5</integer>
        </dict>
        <key>Debug</key>
        <dict>
            <key>AppleDebug</key>
            <true/>
            <key>ApplePanic</key>
            <true/>
            <key>DisableWatchDog</key>
            <true/>
            <key>DisplayDelay</key>
            <integer>0</integer>
            <key>DisplayLevel</key>
            <integer>2147483650</integer>
            <key>LogModules</key>
            <string>*</string>
            <key>SysReport</key>
            <false/>
            <key>Target</key>
            <integer>67</integer>
        </dict>
        <key>Entries</key>
        <array/>
        <key>Security</key>
        <dict>
            <key>AllowSetDefault</key>
            <true/>
            <key>ApECID</key>
            <integer>0</integer>
            <key>AuthRestart</key>
            <false/>
            <key>BlacklistAppleUpdate</key>
            <true/>
            <key>DmgLoading</key>
            <string>Signed</string>
            <key>EnablePassword</key>
            <false/>
            <key>ExposeSensitiveData</key>
            <integer>6</integer>
            <key>HaltLevel</key>
            <integer>2147483648</integer>
            <key>PasswordHash</key>
            <data></data>
            <key>PasswordSalt</key>
            <data></data>
            <key>ScanPolicy</key>
            <integer>0</integer>
            <key>SecureBootModel</key>
            <string>Disabled</string>
            <key>Vault</key>
            <string>Optional</string>
        </dict>
        <key>Serial</key>
        <dict>
            <key>Custom</key>
            <dict>
                <key>BaudRate</key>
                <integer>115200</integer>
                <key>ClockRate</key>
                <integer>1843200</integer>
                <key>DetectCable</key>
                <false/>
                <key>ExtendedTxFifoSize</key>
                <integer>64</integer>
                <key>FifoControl</key>
                <integer>7</integer>
                <key>LineControl</key>
                <integer>3</integer>
                <key>PciDeviceInfo</key>
                <data>/w==</data>
                <key>RegisterAccessWidth</key>
                <integer>8</integer>
                <key>RegisterBase</key>
                <integer>1016</integer>
                <key>RegisterStride</key>
                <integer>1</integer>
                <key>UseHardwareFlowControl</key>
                <false/>
                <key>UseMmio</key>
                <false/>
            </dict>
            <key>Init</key>
            <false/>
            <key>Override</key>
            <false/>
        </dict>
        <key>Tools</key>
        <array/>
    </dict>
    <key>NVRAM</key>
    <dict>
        <key>Add</key>
        <dict>
            <key>4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14</key>
            <dict>
                <key>DefaultBackgroundColor</key>
                <data>AAAAAA==</data>
            </dict>
            <key>4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102</key>
            <dict>
                <key>rtc-blacklist</key>
                <data></data>
            </dict>
            <key>7C436110-AB2A-4BBB-A880-FE41995C9F82</key>
            <dict>
                <key>ForceDisplayRotationInEFI</key>
                <integer>0</integer>
                <key>SystemAudioVolume</key>
                <data>Rg==</data>
                <key>boot-args</key>
                <string>-v debug=0x100 keepsyms=1</string>
                <key>csr-active-config</key>
                <data>AAAAAA==</data>
                <key>prev-lang:kbd</key>
                <data>ZW4tVVM6MA==</data>
                <key>run-efi-updater</key>
                <string>No</string>
            </dict>
        </dict>
        <key>Delete</key>
        <dict>
            <key>4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14</key>
            <array>
                <string>DefaultBackgroundColor</string>
            </array>
            <key>4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102</key>
            <array>
                <string>rtc-blacklist</string>
            </array>
            <key>7C436110-AB2A-4BBB-A880-FE41995C9F82</key>
            <array>
                <string>boot-args</string>
                <string>ForceDisplayRotationInEFI</string>
            </array>
        </dict>
        <key>LegacyOverwrite</key>
        <false/>
        <key>LegacySchema</key>
        <dict>
            <key>7C436110-AB2A-4BBB-A880-FE41995C9F82</key>
            <array>
                <string>EFILoginHiDPI</string>
                <string>EFIBluetoothDelay</string>
                <string>LocationServicesEnabled</string>
                <string>SystemAudioVolume</string>
                <string>SystemAudioVolumeDB</string>
                <string>SystemAudioVolumeSaved</string>
                <string>bluetoothActiveControllerInfo</string>
                <string>bluetoothInternalControllerInfo</string>
                <string>flagstate</string>
                <string>fmm-computer-name</string>
                <string>fmm-mobileme-token-FMM</string>
                <string>fmm-mobileme-token-FMM-BridgeHasAccount</string>
                <string>nvda_drv</string>
                <string>prev-lang:kbd</string>
            </array>
            <key>8BE4DF61-93CA-11D2-AA0D-00E098032B8C</key>
            <array>
                <string>Boot0080</string>
                <string>Boot0081</string>
                <string>Boot0082</string>
                <string>BootNext</string>
                <string>BootOrder</string>
            </array>
        </dict>
        <key>WriteFlash</key>
        <true/>
    </dict>
    <key>PlatformInfo</key>
    <dict>
        <key>Automatic</key>
        <true/>
        <key>CustomMemory</key>
        <false/>
        <key>Generic</key>
        <dict>
            <key>AdviseFeatures</key>
            <false/>
            <key>MLB</key>
            <string>C0281234567890123</string> <!-- Change this -->
            <key>MaxBIOSVersion</key>
            <false/>
            <key>ProcessorType</key>
            <integer>0</integer>
            <key>ROM</key>
            <data>ESIzRFVm</data> <!-- Change this -->
            <key>SpoofVendor</key>
            <true/>
            <key>SystemMemoryStatus</key>
            <string>Auto</string>
            <key>SystemProductName</key>
            <string>iMac13,2</string> <!-- Common for Ivy Bridge -->
            <key>SystemSerialNumber</key>
            <string>C02TESTTESTTEST</string> <!-- Change this -->
            <key>SystemUUID</key>
            <string>GENERATED-NEW-UUID</string> <!-- Change this -->
        </dict>
        <key>UpdateDataHub</key>
        <true/>
        <key>UpdateNVRAM</key>
        <true/>
        <key>UpdateSMBIOS</key>
        <true/>
        <key>UpdateSMBIOSMode</key>
        <string>Create</string>
        <key>UseRawUuidEncoding</key>
        <false/>
    </dict>
    <key>UEFI</key>
    <dict>
        <key>APFS</key>
        <dict>
            <key>EnableJumpstart</key>
            <true/>
            <key>GlobalConnect</key>
            <false/>
            <key>HideVerbose</key>
            <true/>
            <key>JumpstartHotPlug</key>
            <false/>
            <key>MinDate</key>
            <integer>-1</integer>
            <key>MinVersion</key>
            <integer>-1</integer>
        </dict>
        <key>AppleInput</key>
        <dict>
            <key>AppleEvent</key>
            <string>Builtin</string>
            <key>CustomDelays</key>
            <false/>
            <key>GraphicsInputMirroring</key>
            <true/>
            <key>KeyInitialDelay</key>
            <integer>50</integer>
            <key>KeySubsequentDelay</key>
            <integer>5</integer>
            <key>PointerSpeedDiv</key>
            <integer>1</integer>
            <key>PointerSpeedMul</key>
            <integer>1</integer>
        </dict>
        <key>Audio</key>
        <dict>
            <key>AudioCodec</key>
            <integer>0</integer>
            <key>AudioDevice</key>
            <string>PciRoot(0x0)/Pci(0x1b,0x0)</string>
            <key>AudioOutMask</key>
            <integer>1</integer>
            <key>AudioSupport</key>
            <false/>
            <key>DisconnectHda</key>
            <false/>
            <key>MaximumGain</key>
            <integer>-15</integer>
            <key>MinimumAssistGain</key>
            <integer>-30</integer>
            <key>MinimumAudibleGain</key>
            <integer>-55</integer>
            <key>PlayChime</key>
            <string>Auto</string>
            <key>ResetTrafficClass</key>
            <false/>
            <key>SetupDelay</key>
            <integer>0</integer>
        </dict>
        <key>ConnectDrivers</key>
        <true/>
        <key>Drivers</key>
        <array>
            <!-- Essential Drivers will be added by the script -->
        </array>
        <key>Input</key>
        <dict>
            <key>KeyFiltering</key>
            <false/>
            <key>KeyForgetThreshold</key>
            <integer>5</integer>
            <key>KeySupport</key>
            <true/>
            <key>KeySupportMode</key>
            <string>Auto</string>
            <key>KeySwap</key>
            <false/>
            <key>PointerSupport</key>
            <false/>
            <key>PointerSupportMode</key>
            <string>ASUS</string>
            <key>TimerResolution</key>
            <integer>50000</integer>
        </dict>
        <key>Output</key>
        <dict>
            <key>ClearScreenOnModeSwitch</key>
            <false/>
            <key>ConsoleMode</key>
            <string></string>
            <key>DirectGopRendering</key>
            <false/>
            <key>ForceResolution</key>
            <false/>
            <key>GopPassThrough</key>
            <string>Disabled</string>
            <key>IgnoreTextInGraphics</key>
            <false/>
            <key>ProvideConsoleGop</key>
            <true/>
            <key>ReconnectGraphicsOnConnect</key>
            <false/>
            <key>ReconnectOnResChange</key>
            <false/>
            <key>ReplaceTabWithSpace</key>
            <false/>
            <key>Resolution</key>
            <string>Max</string>
            <key>SanitiseClearScreen</key>
            <false/>
            <key>TextRenderer</key>
            <string>BuiltinGraphics</string>
            <key>UIScale</key>
            <integer>-1</integer>
            <key>UgaPassThrough</key>
            <false/>
        </dict>
        <key>ProtocolOverrides</key>
        <dict>
            <key>AppleAudio</key>
            <false/>
            <key>AppleBootPolicy</key>
            <false/>
            <key>AppleDebugLog</key>
            <false/>
            <key>AppleEg2Info</key>
            <false/>
            <key>AppleFramebufferInfo</key>
            <false/>
            <key>AppleImageConversion</key>
            <false/>
            <key>AppleImg4Verification</key>
            <false/>
            <key>AppleKeyMap</key>
            <false/>
            <key>AppleRtcRam</key>
            <false/>
            <key>AppleSecureBoot</key>
            <false/>
            <key>AppleSmcIo</key>
            <false/>
            <key>AppleUserInterfaceTheme</key>
            <false/>
            <key>DataHub</key>
            <false/>
            <key>DeviceProperties</key>
            <false/>
            <key>FirmwareVolume</key>
            <true/>
            <key>HashServices</key>
            <false/>
            <key>OSInfo</key>
            <false/>
            <key>UnicodeCollation</key>
            <false/>
        </dict>
        <key>Quirks</key>
        <dict>
            <key>ActivateHpetSupport</key>
            <false/>
            <key>DisableSecurityPolicy</key>
            <false/>
            <key>EnableVectorAcceleration</key>
            <true/>
            <key>EnableVmx</key>
            <false/>
            <key>ExitBootServicesDelay</key>
            <integer>0</integer>
            <key>ForceOcWriteFlash</key>
            <false/>
            <key>ForgeUefiSupport</key>
            <false/>
            <key>IgnoreInvalidFlexRatio</key>
            <false/>
            <key>ReleaseUsbOwnership</key>
            <false/>
            <key>ReloadOptionRoms</key>
            <false/>
            <key>RequestBootVarRouting</key>
            <true/>
            <key>ResizeGpuBars</key>
            <integer>-1</integer>
            <key>TscSyncTimeout</key>
            <integer>0</integer>
            <key>UnblockFsConnect</key>
            <false/>
        </dict>
        <key>ReservedMemory</key>
        <array/>
    </dict>
</dict>
</plist>
""",
            "oc_haswell_generic": """
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>#WARNING - 1</key>
    <string>This is a generic Haswell Sample.plist</string>
    <key>#WARNING - 2</key>
    <string>Ensure you understand ALL settings before booting.</string>
    <key>ACPI</key>
    <dict>
        <key>Add</key>
        <array/>
        <key>Delete</key>
        <array/>
        <key>Patch</key>
        <array/>
        <key>Quirks</key>
        <dict>
            <key>FadtEnableReset</key>
            <false/>
            <key>NormalizeHeaders</key>
            <false/>
            <key>RebaseRegions</key>
            <false/>
            <key>ResetHwSig</key>
            <false/>
            <key>ResetLogoStatus</key>
            <true/>
            <key>SyncTableIds</key>
            <false/>
        </dict>
    </dict>
    <key>Booter</key>
    <dict>
        <key>MmioWhitelist</key>
        <array/>
        <key>Patch</key>
        <array/>
        <key>Quirks</key>
        <dict>
            <key>AllowRelocationBlock</key>
            <false/>
            <key>AvoidRuntimeDefrag</key>
            <true/>
            <key>DevirtualiseMmio</key>
            <true/> <!-- Haswell can benefit from this -->
            <key>DisableSingleUser</key>
            <false/>
            <key>DisableVariableWrite</key>
            <false/>
            <key>DiscardHibernateMap</key>
            <false/>
            <key>EnableSafeModeSlide</key>
            <true/>
            <key>EnableWriteUnprotector</key>
            <false/> <!-- Haswell usually does not need this -->
            <key>ForceBooterSignature</key>
            <false/>
            <key>ForceExitBootServices</key>
            <false/>
            <key>ProtectMemoryRegions</key>
            <false/>
            <key>ProtectSecureBoot</key>
            <false/>
            <key>ProtectUefiServices</key>
            <false/>
            <key>ProvideCustomSlide</key>
            <true/>
            <key>ProvideMaxSlide</key>
            <integer>0</integer>
            <key>RebuildAppleMemoryMap</key>
            <true/> <!-- Haswell can benefit from this -->
            <key>ResizeAppleGpuBars</key>
            <integer>-1</integer>
            <key>SetupVirtualMap</key>
            <true/>
            <key>SignalAppleOS</key>
            <false/>
            <key>SyncRuntimePermissions</key>
            <true/> <!-- Haswell can benefit from this -->
        </dict>
    </dict>
    <key>DeviceProperties</key>
    <dict>
        <key>Add</key>
        <dict/>
        <key>Delete</key>
        <dict/>
    </dict>
    <key>Kernel</key>
    <dict>
        <key>Add</key>
        <array>
            <!-- Essential Kexts will be added by the script -->
        </array>
        <key>Block</key>
        <array/>
        <key>Emulate</key>
        <dict>
            <key>Cpuid1Data</key>
            <data></data>
            <key>Cpuid1Mask</key>
            <data></data>
            <key>DummyPowerManagement</key>
            <false/>
            <key>MaxKernel</key>
            <string></string>
            <key>MinKernel</key>
            <string></string>
        </dict>
        <key>Force</key>
        <array/>
        <key>Patch</key>
        <array/>
        <key>Quirks</key>
        <dict>
            <key>AppleCpuPmCfgLock</key>
            <true/>
            <key>AppleXcpmCfgLock</key>
            <true/>
            <key>AppleXcpmExtraMsrs</key>
            <true/> <!-- Haswell typically needs this -->
            <key>AppleXcpmForceBoost</key>
            <false/>
            <key>CustomPciSerialDevice</key>
            <false/>
            <key>CustomSMBIOSGuid</key>
            <false/>
            <key>DisableIoMapper</key>
            <true/>
            <key>DisableLinkeditJettison</key>
            <true/>
            <key>DisableRtcChecksum</key>
            <false/>
            <key>ExtendBTFeatureFlags</key>
            <false/>
            <key>ExternalDiskIcons</key>
            <false/>
            <key>ForceAquantiaEthernet</key>
            <false/>
            <key>ForceSecureBootScheme</key>
            <false/>
            <key>IncreasePciBarSize</key>
            <false/>
            <key>LapicKernelPanic</key>
            <false/>
            <key>LegacyCommpage</key>
            <false/>
            <key>PanicNoKextDump</key>
            <true/>
            <key>PowerTimeoutKernelPanic</key>
            <true/>
            <key>ProvideCurrentCpuInfo</key>
            <false/>
            <key>SetApfsTrimTimeout</key>
            <integer>-1</integer>
            <key>ThirdPartyDrives</key>
            <false/>
            <key>XhciPortLimit</key>
            <false/>
        </dict>
        <key>Scheme</key>
        <dict>
            <key>CustomKernel</key>
            <false/>
            <key>FuzzyMatch</key>
            <true/>
            <key>KernelArch</key>
            <string>Auto</string>
            <key>KernelCache</key>
            <string>Auto</string>
        </dict>
    </dict>
    <key>Misc</key>
    <dict>
        <key>BlessOverride</key>
        <array/>
        <key>Boot</key>
        <dict>
            <key>ConsoleAttributes</key>
            <integer>0</integer>
            <key>HibernateMode</key>
            <string>None</string>
            <key>HibernateSkipsPicker</key>
            <false/>
            <key>HideAuxiliary</key>
            <false/>
            <key>InstanceIdentifier</key>
            <string></string>
            <key>LauncherOption</key>
            <string>Disabled</string>
            <key>LauncherPath</key>
            <string>Default</string>
            <key>PickerAttributes</key>
            <integer>17</integer>
            <key>PickerAudioAssist</key>
            <false/>
            <key>PickerMode</key>
            <string>Builtin</string>
            <key>PickerVariant</key>
            <string>Auto</string>
            <key>PollAppleHotKeys</key>
            <false/>
            <key>ShowPicker</key>
            <true/>
            <key>TakeoffDelay</key>
            <integer>0</integer>
            <key>Timeout</key>
            <integer>5</integer>
        </dict>
        <key>Debug</key>
        <dict>
            <key>AppleDebug</key>
            <true/>
            <key>ApplePanic</key>
            <true/>
            <key>DisableWatchDog</key>
            <true/>
            <key>DisplayDelay</key>
            <integer>0</integer>
            <key>DisplayLevel</key>
            <integer>2147483650</integer>
            <key>LogModules</key>
            <string>*</string>
            <key>SysReport</key>
            <false/>
            <key>Target</key>
            <integer>67</integer>
        </dict>
        <key>Entries</key>
        <array/>
        <key>Security</key>
        <dict>
            <key>AllowSetDefault</key>
            <true/>
            <key>ApECID</key>
            <integer>0</integer>
            <key>AuthRestart</key>
            <false/>
            <key>BlacklistAppleUpdate</key>
            <true/>
            <key>DmgLoading</key>
            <string>Signed</string>
            <key>EnablePassword</key>
            <false/>
            <key>ExposeSensitiveData</key>
            <integer>6</integer>
            <key>HaltLevel</key>
            <integer>2147483648</integer>
            <key>PasswordHash</key>
            <data></data>
            <key>PasswordSalt</key>
            <data></data>
            <key>ScanPolicy</key>
            <integer>0</integer>
            <key>SecureBootModel</key>
            <string>Disabled</string>
            <key>Vault</key>
            <string>Optional</string>
        </dict>
        <key>Serial</key>
        <dict>
            <key>Custom</key>
            <dict>
                <key>BaudRate</key>
                <integer>115200</integer>
                <key>ClockRate</key>
                <integer>1843200</integer>
                <key>DetectCable</key>
                <false/>
                <key>ExtendedTxFifoSize</key>
                <integer>64</integer>
                <key>FifoControl</key>
                <integer>7</integer>
                <key>LineControl</key>
                <integer>3</integer>
                <key>PciDeviceInfo</key>
                <data>/w==</data>
                <key>RegisterAccessWidth</key>
                <integer>8</integer>
                <key>RegisterBase</key>
                <integer>1016</integer>
                <key>RegisterStride</key>
                <integer>1</integer>
                <key>UseHardwareFlowControl</key>
                <false/>
                <key>UseMmio</key>
                <false/>
            </dict>
            <key>Init</key>
            <false/>
            <key>Override</key>
            <false/>
        </dict>
        <key>Tools</key>
        <array/>
    </dict>
    <key>NVRAM</key>
    <dict>
        <key>Add</key>
        <dict>
            <key>4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14</key>
            <dict>
                <key>DefaultBackgroundColor</key>
                <data>AAAAAA==</data>
            </dict>
            <key>4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102</key>
            <dict>
                <key>rtc-blacklist</key>
                <data></data>
            </dict>
            <key>7C436110-AB2A-4BBB-A880-FE41995C9F82</key>
            <dict>
                <key>ForceDisplayRotationInEFI</key>
                <integer>0</integer>
                <key>SystemAudioVolume</key>
                <data>Rg==</data>
                <key>boot-args</key>
                <string>-v debug=0x100 keepsyms=1</string>
                <key>csr-active-config</key>
                <data>AAAAAA==</data>
                <key>prev-lang:kbd</key>
                <data>ZW4tVVM6MA==</data>
                <key>run-efi-updater</key>
                <string>No</string>
            </dict>
        </dict>
        <key>Delete</key>
        <dict>
            <key>4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14</key>
            <array>
                <string>DefaultBackgroundColor</string>
            </array>
            <key>4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102</key>
            <array>
                <string>rtc-blacklist</string>
            </array>
            <key>7C436110-AB2A-4BBB-A880-FE41995C9F82</key>
            <array>
                <string>boot-args</string>
                <string>ForceDisplayRotationInEFI</string>
            </array>
        </dict>
        <key>LegacyOverwrite</key>
        <false/>
        <key>LegacySchema</key>
        <dict>
            <key>7C436110-AB2A-4BBB-A880-FE41995C9F82</key>
            <array>
                <string>EFILoginHiDPI</string>
                <string>EFIBluetoothDelay</string>
                <string>LocationServicesEnabled</string>
                <string>SystemAudioVolume</string>
                <string>SystemAudioVolumeDB</string>
                <string>SystemAudioVolumeSaved</string>
                <string>bluetoothActiveControllerInfo</string>
                <string>bluetoothInternalControllerInfo</string>
                <string>flagstate</string>
                <string>fmm-computer-name</string>
                <string>fmm-mobileme-token-FMM</string>
                <string>fmm-mobileme-token-FMM-BridgeHasAccount</string>
                <string>nvda_drv</string>
                <string>prev-lang:kbd</string>
            </array>
            <key>8BE4DF61-93CA-11D2-AA0D-00E098032B8C</key>
            <array>
                <string>Boot0080</string>
                <string>Boot0081</string>
                <string>Boot0082</string>
                <string>BootNext</string>
                <string>BootOrder</string>
            </array>
        </dict>
        <key>WriteFlash</key>
        <true/>
    </dict>
    <key>PlatformInfo</key>
    <dict>
        <key>Automatic</key>
        <true/>
        <key>CustomMemory</key>
        <false/>
        <key>Generic</key>
        <dict>
            <key>AdviseFeatures</key>
            <false/>
            <key>MLB</key>
            <string>C0242030040F291A8</string> <!-- Change this -->
            <key>MaxBIOSVersion</key>
            <false/>
            <key>ProcessorType</key>
            <integer>0</integer>
            <key>ROM</key>
            <data>ESIzRFVm</data> <!-- Change this -->
            <key>SpoofVendor</key>
            <true/>
            <key>SystemMemoryStatus</key>
            <string>Auto</string>
            <key>SystemProductName</key>
            <string>iMac14,2</string> <!-- Common for Haswell -->
            <key>SystemSerialNumber</key>
            <string>C02TESTHASWELL0</string> <!-- Change this -->
            <key>SystemUUID</key>
            <string>ANOTHER-GENERATED-UUID</string> <!-- Change this -->
        </dict>
        <key>UpdateDataHub</key>
        <true/>
        <key>UpdateNVRAM</key>
        <true/>
        <key>UpdateSMBIOS</key>
        <true/>
        <key>UpdateSMBIOSMode</key>
        <string>Create</string>
        <key>UseRawUuidEncoding</key>
        <false/>
    </dict>
    <key>UEFI</key>
    <dict>
        <key>APFS</key>
        <dict>
            <key>EnableJumpstart</key>
            <true/>
            <key>GlobalConnect</key>
            <false/>
            <key>HideVerbose</key>
            <true/>
            <key>JumpstartHotPlug</key>
            <false/>
            <key>MinDate</key>
            <integer>-1</integer>
            <key>MinVersion</key>
            <integer>-1</integer>
        </dict>
        <key>AppleInput</key>
        <dict>
            <key>AppleEvent</key>
            <string>Builtin</string>
            <key>CustomDelays</key>
            <false/>
            <key>GraphicsInputMirroring</key>
            <true/>
            <key>KeyInitialDelay</key>
            <integer>50</integer>
            <key>KeySubsequentDelay</key>
            <integer>5</integer>
            <key>PointerSpeedDiv</key>
            <integer>1</integer>
            <key>PointerSpeedMul</key>
            <integer>1</integer>
        </dict>
        <key>Audio</key>
        <dict>
            <key>AudioCodec</key>
            <integer>0</integer>
            <key>AudioDevice</key>
            <string>PciRoot(0x0)/Pci(0x1b,0x0)</string>
            <key>AudioOutMask</key>
            <integer>1</integer>
            <key>AudioSupport</key>
            <false/>
            <key>DisconnectHda</key>
            <false/>
            <key>MaximumGain</key>
            <integer>-15</integer>
            <key>MinimumAssistGain</key>
            <integer>-30</integer>
            <key>MinimumAudibleGain</key>
            <integer>-55</integer>
            <key>PlayChime</key>
            <string>Auto</string>
            <key>ResetTrafficClass</key>
            <false/>
            <key>SetupDelay</key>
            <integer>0</integer>
        </dict>
        <key>ConnectDrivers</key>
        <true/>
        <key>Drivers</key>
        <array>
            <!-- Essential Drivers will be added by the script -->
        </array>
        <key>Input</key>
        <dict>
            <key>KeyFiltering</key>
            <false/>
            <key>KeyForgetThreshold</key>
            <integer>5</integer>
            <key>KeySupport</key>
            <true/>
            <key>KeySupportMode</key>
            <string>Auto</string>
            <key>KeySwap</key>
            <false/>
            <key>PointerSupport</key>
            <false/>
            <key>PointerSupportMode</key>
            <string>ASUS</string>
            <key>TimerResolution</key>
            <integer>50000</integer>
        </dict>
        <key>Output</key>
        <dict>
            <key>ClearScreenOnModeSwitch</key>
            <false/>
            <key>ConsoleMode</key>
            <string></string>
            <key>DirectGopRendering</key>
            <false/>
            <key>ForceResolution</key>
            <false/>
            <key>GopPassThrough</key>
            <string>Disabled</string>
            <key>IgnoreTextInGraphics</key>
            <false/>
            <key>ProvideConsoleGop</key>
            <true/>
            <key>ReconnectGraphicsOnConnect</key>
            <false/>
            <key>ReconnectOnResChange</key>
            <false/>
            <key>ReplaceTabWithSpace</key>
            <false/>
            <key>Resolution</key>
            <string>Max</string>
            <key>SanitiseClearScreen</key>
            <false/>
            <key>TextRenderer</key>
            <string>BuiltinGraphics</string>
            <key>UIScale</key>
            <integer>-1</integer>
            <key>UgaPassThrough</key>
            <false/>
        </dict>
        <key>ProtocolOverrides</key>
        <dict>
            <key>AppleAudio</key>
            <false/>
            <key>AppleBootPolicy</key>
            <false/>
            <key>AppleDebugLog</key>
            <false/>
            <key>AppleEg2Info</key>
            <false/>
            <key>AppleFramebufferInfo</key>
            <false/>
            <key>AppleImageConversion</key>
            <false/>
            <key>AppleImg4Verification</key>
            <false/>
            <key>AppleKeyMap</key>
            <false/>
            <key>AppleRtcRam</key>
            <false/>
            <key>AppleSecureBoot</key>
            <false/>
            <key>AppleSmcIo</key>
            <false/>
            <key>AppleUserInterfaceTheme</key>
            <false/>
            <key>DataHub</key>
            <false/>
            <key>DeviceProperties</key>
            <false/>
            <key>FirmwareVolume</key>
            <true/>
            <key>HashServices</key>
            <false/>
            <key>OSInfo</key>
            <false/>
            <key>UnicodeCollation</key>
            <false/>
        </dict>
        <key>Quirks</key>
        <dict>
            <key>ActivateHpetSupport</key>
            <false/>
            <key>DisableSecurityPolicy</key>
            <false/>
            <key>EnableVectorAcceleration</key>
            <true/>
            <key>EnableVmx</key>
            <false/>
            <key>ExitBootServicesDelay</key>
            <integer>0</integer>
            <key>ForceOcWriteFlash</key>
            <false/>
            <key>ForgeUefiSupport</key>
            <false/>
            <key>IgnoreInvalidFlexRatio</key>
            <true/> <!-- Haswell may need this -->
            <key>ReleaseUsbOwnership</key>
            <false/>
            <key>ReloadOptionRoms</key>
            <false/>
            <key>RequestBootVarRouting</key>
            <true/>
            <key>ResizeGpuBars</key>
            <integer>-1</integer>
            <key>TscSyncTimeout</key>
            <integer>0</integer>
            <key>UnblockFsConnect</key>
            <false/>
        </dict>
        <key>ReservedMemory</key>
        <array/>
    </dict>
</dict>
</plist>
"""
        }
        self.clover_configs = {
            "clover_generic_intel": """
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>ACPI</key>
    <dict>
        <key>DSDT</key>
        <dict>
            <key>Fixes</key>
            <dict>
                <key>FixHPET</key>
                <true/>
                <key>FixShutdown</key>
                <true/>
            </dict>
            <key>Name</key>
            <string>DSDT.aml</string>
            <key>Patches</key>
            <array/>
        </dict>
        <key>SSDT</key>
        <dict>
            <key>DropOem</key>
            <false/>
            <key>Generate</key>
            <dict>
                <key>CStates</key>
                <false/>
                <key>PStates</key>
                <false/>
            </dict>
        </dict>
    </dict>
    <key>Boot</key>
    <dict>
        <key>Arguments</key>
        <string>-v debug=0x100 keepsyms=1 alcid=1</string>
        <key>DefaultVolume</key>
        <string>LastBootedVolume</string>
        <key>NeverHibernate</key>
        <true/>
        <key>Secure</key>
        <false/>
        <key>Timeout</key>
        <integer>5</integer>
        <key>XMPDetection</key>
        <string>Yes</string>
    </dict>
    <key>Devices</key>
    <dict>
        <key>Audio</key>
        <dict>
            <key>Inject</key>
            <string>1</string>
        </dict>
        <key>USB</key>
        <dict>
            <key>FixOwnership</key>
            <true/>
            <key>Inject</key>
            <true/>
        </dict>
    </dict>
    <key>GUI</key>
    <dict>
        <key>Mouse</key>
        <dict>
            <key>Enabled</key>
            <true/>
        </dict>
        <key>Scan</key>
        <dict>
            <key>Entries</key>
            <true/>
            <key>Legacy</key>
            <string>First</string>
            <key>Tool</key>
            <true/>
        </dict>
        <key>Theme</key>
        <string>embedded</string>
    </dict>
    <key>Graphics</key>
    <dict>
        <key>Inject</key>
        <dict>
            <key>ATI</key>
            <false/>
            <key>Intel</key>
            <true/> <!-- Generic, may need to be false if dGPU used -->
            <key>NVidia</key>
            <false/>
        </dict>
    </dict>
    <key>KernelAndKextPatches</key>
    <dict>
        <key>AppleIntelCPUPM</key>
        <true/> <!-- For Sandy/Ivy Bridge -->
        <key>AppleRTC</key>
        <true/>
        <key>KernelPm</key>
        <true/> <!-- For Haswell+ and some Ivy -->
        <key>KextsToPatch</key>
        <array/>
    </dict>
    <key>RtVariables</key>
    <dict>
        <key>BooterConfig</key>
        <string>0x28</string>
        <key>CsrActiveConfig</key>
        <string>0x67</string>
    </dict>
    <key>SMBIOS</key>
    <dict>
        <key>ProductName</key>
        <string>iMac14,2</string> <!-- Generic Haswell SMBIOS -->
        <key>Trust</key>
        <true/>
    </dict>
    <key>SystemParameters</key>
    <dict>
        <key>InjectKexts</key>
        <string>Yes</string>
        <key>InjectSystemID</key>
        <true/>
    </dict>
</dict>
</plist>
"""
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
        self.efi_cfg_mgr = EFIConfigManager(self.u) # Instantiate here
        self.d = Downloader(self.u)
        self.cm = CatalogManager(self.u, self.d)
        self.main_download_cache_dir = DOWNLOAD_CACHE_DIR
        self.temp_dir_base = DOWNLOAD_CACHE_DIR / "temp_extractions"
        self.is_linux = sys.platform.startswith("linux")
        self.disk_mgr = None

        # Define ESSENTIAL_LINUX_TOOLS and TOOL_TO_PACKAGE
        self.ESSENTIAL_LINUX_TOOLS = [
            "parted", "mkfs.vfat", "mkfs.hfsplus", "7z", "dd",
            "rsync", "lsblk", "fdisk", "umount", "mount",
            "blockdev", "partprobe", "sync"
        ]
        self.TOOL_TO_PACKAGE = {
            "parted": "parted",
            "mkfs.vfat": "dosfstools",
            "mkfs.hfsplus": "hfsprogs or hfsplus-tools",
            "7z": "p7zip-full or p7zip",
            "dd": "coreutils (usually pre-installed)",
            "rsync": "rsync",
            "lsblk": "util-linux (usually pre-installed)",
            "fdisk": "util-linux (usually pre-installed)",
            "umount": "util-linux (usually pre-installed)",
            "mount": "util-linux (usually pre-installed)",
            "blockdev": "util-linux (usually pre-installed)",
            "partprobe": "parted or util-linux",
            "sync": "coreutils (usually pre-installed)"
        }

        if self.is_linux:
            # Initialize LinuxDiskManager first, as _check_dependencies might not be strictly necessary
            # if the user isn't going to perform USB creation. However, for this tool's purpose,
            # it's better to check upfront.
            try:
                from skyscope_diskutils_linux import Disk as LinuxDiskManager
                self.disk_mgr = LinuxDiskManager(self.u)
                self.u.cprint("Linux Disk Manager initialized.", "green")
            except ImportError:
                self.u.cprint("LinuxDiskManager (skyscope_diskutils_linux.py) not found. USB creation will be disabled.", "red")
                self.is_linux = False # Disable USB functions if manager fails
            except Exception as e:
                self.u.cprint(f"Error initializing LinuxDiskManager: {e}", "red")
                self.is_linux = False # Disable USB functions if manager fails

            if self.is_linux: # If disk manager initialized, then check other tools
                self._check_dependencies() # This will sys.exit if critical tools are missing
        else:
            self.u.cprint("Non-Linux platform. USB creation functions will be disabled.", "yellow")

        # Bootloader specific constants
        self.OC_ESSENTIAL_DRIVERS = ["HfsPlus.efi", "OpenRuntime.efi"]
        self.OC_ESSENTIAL_KEXTS = ["Lilu.kext", "VirtualSMC.kext", "WhateverGreen.kext"] # Directory names
        self.OC_LEGACY_BOOT_FILES = {"boot0": "boot0", "boot1f32": "boot1f32"} # Generic name to actual filename
        self.OC_RELEASE_URL = "https://api.github.com/repos/acidanthera/OpenCorePkg/releases/latest"

        self.CLOVER_ESSENTIAL_DRIVERS_UEFI = ["HFSPlus.efi", "ApfsDriverLoader.efi", "VBoxHfs.efi"]
        self.CLOVER_ESSENTIAL_KEXTS_OTHER = ["FakeSMC.kext", "Lilu.kext", "WhateverGreen.kext"]
        self.CLOVER_LEGACY_BOOT_FILES = {"boot0": "boot0af", "boot1f32": "boot1f32alt"} # Common names
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
                missing_tools_map[tool] = self.TOOL_TO_PACKAGE.get(tool, "unknown_package")

        if missing_tools_map:
            self.u.cprint("\nError: The following essential tools are missing:", "red")
            for tool, pkg_suggestion in missing_tools_map.items():
                self.u.cprint(f"  - {tool} (Package suggestion: {pkg_suggestion})", "red")
            self.u.cprint("\nPlease install them using your system's package manager.", "yellow")
            self.u.cprint("Example for Debian/Ubuntu: sudo apt update && sudo apt install <package_name>", "yellow")
            self.u.cprint("Example for Fedora: sudo dnf install <package_name>", "yellow")
            self.u.cprint("\nThis tool cannot proceed without these dependencies for USB creation.", "red")
            input("Press Enter to exit.")
            sys.exit(1)
        else:
            self.u.cprint("\nAll essential tools found.", "green")
            time.sleep(1)
        return True


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
        if not self.is_linux or not self.disk_mgr: # Check if USB functions are enabled
            self.u.cprint("This feature is currently only supported on Linux and requires all dependencies.", "red")
            self.u.cprint("Please ensure you are on Linux and all tools listed by _check_dependencies are installed.", "red")
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

        # Determine EFI partition path (used later for bootloader)
        efi_partition_path = selected_usb_path + ("p1" if "nvme" in selected_usb_path else "1")

        if self.prepare_usb_device(selected_usb_path, volume_name=volume_name, gpt_scheme=use_gpt):
            self.u.cprint(f"USB device '{selected_usb_path}' prepared successfully for {selected_product['title']}.", "green")

            self.temp_dir_base.mkdir(parents=True, exist_ok=True)
            final_payload_dir_path_str = self.extract_macos_payload(str(downloaded_image_path), str(self.temp_dir_base))

            if final_payload_dir_path_str:
                self.u.cprint(f"macOS payload extracted to temporary location: {final_payload_dir_path_str}", "green")

                target_hfs_partition = selected_usb_path + ("p2" if "nvme" in selected_usb_path else "2")

                if self.write_macos_to_usb(final_payload_dir_path_str, target_hfs_partition, selected_product['title']):
                    self.u.cprint("Successfully wrote macOS content to USB.", "green")

                    # --- Bootloader Selection ---
                    self.u.head("Select Bootloader / EFI Setup")
                    self.u.cprint("1. Install OpenCore (Recommended for modern setups)", "green")
                    self.u.cprint("2. Install Clover (Legacy / Specific Hardware)", "green")
                    self.u.cprint("3. Use Custom EFI Folder (Provide your own)", "green")
                    self.u.cprint("S. Skip Bootloader Installation", "yellow")
                    self.u.cprint("Q. Quit to Main Menu", "yellow")

                    bootloader_choice = input("Enter your choice: ").strip().lower()

                    bootloader_installed_type = None # To track if OC/Clover generic was used
                    action_taken_by_bootloader_handler = False # Tracks if any choice in this menu led to an action

                    if bootloader_choice == '1':
                        self.u.cprint("OpenCore selected. Proceeding to OpenCore installation steps...", "green")
                        if self._handle_opencore_installation(efi_partition_path, selected_usb_path, use_gpt):
                            # If _handle_opencore_installation returns True, it implies a generic config was likely placed.
                            # The method itself now handles detailed user warnings.
                            bootloader_installed_type = "opencore"
                        action_taken_by_bootloader_handler = True
                    elif bootloader_choice == '2':
                        self.u.cprint("Clover selected. Proceeding to Clover installation steps...", "green")
                        if self._handle_clover_installation(efi_partition_path, selected_usb_path, use_gpt):
                            bootloader_installed_type = "clover"
                        action_taken_by_bootloader_handler = True
                    elif bootloader_choice == '3':
                        self.u.cprint("Custom EFI folder selected.", "green")
                        if self._handle_custom_efi_copy(efi_partition_path): # Pass the string path
                             bootloader_installed_type = "custom"
                        action_taken_by_bootloader_handler = True
                    elif bootloader_choice == 's':
                        self.u.cprint("Skipping bootloader installation. The USB will have macOS files but no bootloader from this script.", "yellow")
                        action_taken_by_bootloader_handler = True
                    elif bootloader_choice == 'q':
                        self.u.cprint("Quitting USB creation process and returning to main menu.", "yellow")
                        action_taken_by_bootloader_handler = True # User chose to quit this sub-process
                        # No sys.exit here, just return from this method to go back to main menu loop
                    else:
                        self.u.cprint("Invalid bootloader choice. Skipping bootloader installation.", "yellow")
                        action_taken_by_bootloader_handler = True

                    # --- Final Summary Message ---
                    # This message is displayed if a bootloader installation path (OC/Clover generic) was taken.
                    # The specific detailed warnings are now inside _handle_opencore_installation and _handle_clover_installation.
                    # This serves as a final general reminder if those paths were taken.
                    if bootloader_installed_type in ["opencore", "clover"]:
                        self.u.cprint("-" * 70, "yellow")
                        self.u.cprint("IMPORTANT REMINDER (Final Step):", "yellow")
                        self.u.cprint(f"The installed {bootloader_installed_type.title()} configuration is GENERIC.", "yellow")
                        self.u.cprint("You MUST review and customize the config.plist for your specific hardware", "yellow")
                        self.u.cprint("before attempting to boot from the USB drive.", "yellow")
                        self.u.cprint("Refer to the Dortania guides and other resources mentioned during the setup and in the Help section.", "yellow")
                        self.u.cprint("-" * 70, "yellow")
                    elif bootloader_installed_type == "custom":
                        self.u.cprint("Custom EFI folder was copied. Ensure it is correctly configured for your hardware.", "green")

                    self.u.cprint("\nUSB creation process complete!", "green")
                    # --- End Final Summary Message ---

                else:
                    self.u.cprint("Failed to write macOS content to USB.", "red")

                # Cleanup of final_payload_dir_path_str is handled within write_macos_to_usb's finally block
            else:
                self.u.cprint("Failed to extract macOS payload. Cannot proceed with USB creation.", "red")
        else:
            self.u.cprint(f"Failed to prepare USB device '{selected_usb_path}'. Check errors above.", "red")

    # --- Bootloader Handling Methods ---
    def _select_cpu_architecture_for_config(self, bootloader_type):
        self.u.head(f"Select CPU Architecture for {bootloader_type.title()} Generic Config")

        available_archs = self.efi_cfg_mgr.get_available_architectures(bootloader_type)
        if not available_archs:
            self.u.cprint(f"No generic {bootloader_type} configurations available.", "yellow")
            return None

        self.u.cprint("Available generic configurations:", "green")
        for i, arch_key in enumerate(available_archs):
            # Attempt to pretty print the key
            # e.g., "oc_sandybridge_generic" -> "OpenCore Sandy Bridge (Generic)"
            # e.g., "clover_generic_intel" -> "Clover Generic Intel"
            parts = arch_key.split('_')
            name = " ".join(p.title() for p in parts[1:])
            self.u.cprint(f"  {i+1}. {name}", "green")

        self.u.cprint("  S. Skip / Use Default (Sample.plist or bootloader default)", "yellow")
        self.u.cprint("  B. Back to previous menu", "yellow")

        while True:
            choice_str = input("Enter your choice: ").strip().lower()
            if choice_str == 'b':
                return "BACK"
            if choice_str == 's':
                self.u.cprint("Skipping selection of a specific generic config.", "yellow")
                return None # Indicates skip / use default
            try:
                choice_idx = int(choice_str) - 1
                if 0 <= choice_idx < len(available_archs):
                    selected_key = available_archs[choice_idx]
                    self.u.cprint(f"Selected architecture key: {selected_key}", "green")
                    return selected_key
                else:
                    self.u.cprint(f"Invalid selection. Please enter a number between 1 and {len(available_archs)}, or S/B.", "yellow")
            except ValueError:
                self.u.cprint("Invalid input. Please enter a number, S, or B.", "yellow")
        return None


    def _handle_opencore_installation(self, efi_partition_path, usb_device_path, gpt_scheme):
        self.u.head("OpenCore Installation")

        oc_download_dir = self.temp_dir_base / "opencore_download"
        oc_extract_dir = self.temp_dir_base / "opencore_extracted"
        efi_mount_point_path = None # Define before try for cleanup

        try:
            oc_download_dir.mkdir(parents=True, exist_ok=True)
            oc_extract_dir.mkdir(parents=True, exist_ok=True)

            # 1. Fetching OpenCore
            self.u.cprint("Fetching latest OpenCore release information...", "green")
            release_info_str = self.d.get_string(self.OC_RELEASE_URL)
            if not release_info_str:
                self.u.cprint("Failed to fetch OpenCore release info. Check internet or URL.", "red")
                return False

            oc_zip_url = None
            oc_zip_name = None
            try:
                release_data = json.loads(release_info_str)
                for asset in release_data.get("assets", []):
                    if asset.get("name", "").upper().endswith("-RELEASE.ZIP"): # Acidanthera uses uppercase
                        oc_zip_url = asset.get("browser_download_url")
                        oc_zip_name = asset.get("name")
                        break
                if not oc_zip_url:
                    self.u.cprint("Could not find RELEASE.zip in OpenCore release assets.", "red")
                    return False
            except json.JSONDecodeError:
                self.u.cprint("Failed to parse OpenCore release JSON.", "red")
                return False

            self.u.cprint(f"Found OpenCore release: {oc_zip_name}", "green")
            target_zip_path = oc_download_dir / oc_zip_name
            if not self.d.stream_to_file(oc_zip_url, str(target_zip_path)):
                self.u.cprint(f"Failed to download OpenCore ZIP from {oc_zip_url}.", "red")
                return False
            self.u.cprint(f"OpenCore downloaded to: {target_zip_path}", "green")

            # 2. Extracting OpenCore
            if not self._extract_archive(target_zip_path, oc_extract_dir, "OpenCore PKG"):
                self.u.cprint("Failed to extract OpenCore ZIP.", "red")
                return False

            source_efi_dir = oc_extract_dir / "X64" / "EFI"
            if not source_efi_dir.is_dir():
                self.u.cprint(f"Extracted OpenCore does not contain '{source_efi_dir}'.", "red")
                return False

            # 3. Mount EFI Partition
            efi_mount_point_path = pathlib.Path(tempfile.mkdtemp(prefix="efi_mount_", dir=str(self.temp_dir_base)))
            self.u.cprint(f"Mounting EFI partition '{efi_partition_path}' to '{efi_mount_point_path}'...", "green")
            mount_cmd = ["mount", efi_partition_path, str(efi_mount_point_path)]
            mount_result = self._run_command(mount_cmd, "Mount EFI partition", check=False)
            if not mount_result or mount_result.returncode != 0:
                self.u.cprint(f"Failed to mount EFI partition '{efi_partition_path}'.", "red")
                return False

            # 4. Install OpenCore Files
            target_efi_base = efi_mount_point_path / "EFI"
            target_oc_dir = target_efi_base / "OC"

            self.u.cprint(f"Copying base OpenCore EFI files from '{source_efi_dir}' to '{target_efi_base}'...", "green")
            shutil.copytree(source_efi_dir, target_efi_base, dirs_exist_ok=True)

            # Ensure essential Kexts and Drivers directories exist
            (target_oc_dir / "Drivers").mkdir(parents=True, exist_ok=True)
            (target_oc_dir / "Kexts").mkdir(parents=True, exist_ok=True)

            self.u.cprint("Copying essential OpenCore drivers...", "green")
            for driver_name in self.OC_ESSENTIAL_DRIVERS:
                source_driver = source_efi_dir / "OC" / "Drivers" / driver_name
                if source_driver.exists():
                    shutil.copy2(source_driver, target_oc_dir / "Drivers" / driver_name)
                    self.u.cprint(f"  Copied: {driver_name}", "green")
                else:
                    self.u.cprint(f"  Warning: Essential driver '{driver_name}' not found in OpenCore package.", "yellow")

            self.u.cprint("Copying essential OpenCore Kexts (directories)...", "green")
            for kext_dir_name in self.OC_ESSENTIAL_KEXTS:
                source_kext_dir = source_efi_dir / "OC" / "Kexts" / kext_dir_name
                if source_kext_dir.is_dir():
                    shutil.copytree(source_kext_dir, target_oc_dir / "Kexts" / kext_dir_name, dirs_exist_ok=True)
                    self.u.cprint(f"  Copied: {kext_dir_name}", "green")
                else:
                    self.u.cprint(f"  Warning: Essential Kext directory '{kext_dir_name}' not found in OpenCore package.", "yellow")

            sample_plist_path = target_oc_dir / "Sample.plist" # Default if no specific choice
            config_plist_path = target_oc_dir / "config.plist"

            # --- CPU Architecture Specific Config ---
            arch_key = self._select_cpu_architecture_for_config("opencore")

            if arch_key and arch_key != "BACK":
                config_plist_str = self.efi_cfg_mgr.get_config_plist("opencore", arch_key)
                if config_plist_str:
                    try:
                        with open(config_plist_path, "w", encoding="utf-8") as f:
                            f.write(config_plist_str)
                        self.u.cprint(f"Installed generic OpenCore config.plist for '{arch_key}'.", "green")
                        # Enhanced Warning Message
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
                else: # Should not happen if arch_key is from get_available_architectures
                    self.u.cprint(f"Could not find generic OpenCore config for '{arch_key}'. Using Sample.plist.", "yellow")
                    if sample_plist_path.exists(): shutil.copy2(sample_plist_path, config_plist_path)
                    else: self.u.cprint(f"Critical: Sample.plist also not found at {sample_plist_path}", "red")
            elif arch_key == "BACK": # User chose to go back from CPU selection
                 self.u.cprint("OpenCore installation cancelled by user during CPU architecture selection.", "yellow")
                 # Mount is handled in finally, but we should indicate failure
                 return False # Signal failure to proceed
            else: # User chose to skip (arch_key is None) or no configs were available
                self.u.cprint("Using default Sample.plist for OpenCore.", "yellow")
                if sample_plist_path.exists():
                    shutil.copy2(sample_plist_path, config_plist_path)
                    self.u.cprint(f"Copied '{sample_plist_path.name}' to '{config_plist_path.name}'.", "green")
                    self.u.cprint("IMPORTANT: This is a SAMPLE config.plist. It needs to be configured for your specific hardware!", "yellow")
                else:
                    self.u.cprint(f"Warning: '{sample_plist_path.name}' not found. Cannot create default config.plist.", "yellow")
            # --- End CPU Architecture Specific Config ---

            # 5. Legacy Boot Setup (if not gpt_scheme)
            if not gpt_scheme:
                self.u.cprint("Setting up OpenCore Legacy Boot (MBR)...", "green")
                legacy_boot_util_path = oc_extract_dir / "Utilities" / "LegacyBoot"
                boot0_file = legacy_boot_util_path / self.OC_LEGACY_BOOT_FILES["boot0"]
                boot1f32_file = legacy_boot_util_path / self.OC_LEGACY_BOOT_FILES["boot1f32"]

                if boot0_file.exists():
                    dd_mbr_cmd = ["dd", f"if={str(boot0_file)}", f"of={usb_device_path}", "bs=440", "count=1", "conv=fsync"]
                    if self._run_command(dd_mbr_cmd, "Write OpenCore MBR (boot0)"):
                         self.u.cprint(f"  Successfully wrote '{boot0_file.name}' to MBR of '{usb_device_path}'.", "green")
                    else: self.u.cprint(f"  Warning: Failed to write MBR for OpenCore on '{usb_device_path}'.", "yellow")
                else: self.u.cprint(f"  Warning: OpenCore MBR file '{boot0_file.name}' not found at '{legacy_boot_util_path}'.", "yellow")

                if boot1f32_file.exists():
                    dd_pbr_cmd = ["dd", f"if={str(boot1f32_file)}", f"of={efi_partition_path}", "conv=fsync"] # No bs/count, write whole file
                    if self._run_command(dd_pbr_cmd, "Write OpenCore PBR (boot1f32)"):
                        self.u.cprint(f"  Successfully wrote '{boot1f32_file.name}' to PBR of '{efi_partition_path}'.", "green")
                    else: self.u.cprint(f"  Warning: Failed to write PBR for OpenCore on '{efi_partition_path}'.", "yellow")
                else: self.u.cprint(f"  Warning: OpenCore PBR file '{boot1f32_file.name}' not found at '{legacy_boot_util_path}'.", "yellow")

            self.u.cprint("OpenCore installation completed.", "green")
            return True

        except Exception as e:
            self.u.cprint(f"An unexpected error occurred during OpenCore installation: {e}", "red")
            import traceback
            self.u.cprint(traceback.format_exc(), "yellow") # Print stack trace for debugging
            return False
        finally:
            # Cleanup
            if efi_mount_point_path and efi_mount_point_path.is_mount():
                self.u.cprint(f"Unmounting EFI partition '{efi_mount_point_path}'...", "green")
                self._run_command(["sync"], "Sync before unmount", check=False)
                umount_res = self._run_command(["umount", "-lf", str(efi_mount_point_path)], "Unmount EFI", check=False)
                if not umount_res or umount_res.returncode != 0:
                    self.u.cprint(f"  Warning: Could not unmount {efi_mount_point_path}. Manual check may be needed.", "yellow")
            if efi_mount_point_path and efi_mount_point_path.exists():
                shutil.rmtree(efi_mount_point_path, ignore_errors=True)

            if oc_download_dir.exists(): shutil.rmtree(oc_download_dir, ignore_errors=True)
            if oc_extract_dir.exists(): shutil.rmtree(oc_extract_dir, ignore_errors=True)
            self.u.cprint("OpenCore temporary files cleaned up.", "green")


    def _handle_clover_installation(self, efi_partition_path, usb_device_path, gpt_scheme):
        self.u.head("Clover Installation")

        clover_download_dir = self.temp_dir_base / "clover_download"
        clover_extract_dir = self.temp_dir_base / "clover_extracted"
        efi_mount_point_path = None # Define before try for cleanup
        clover_pkg_extract_path = None # For multi-stage extractions (e.g. PKG -> ISO -> EFI)

        try:
            clover_download_dir.mkdir(parents=True, exist_ok=True)
            clover_extract_dir.mkdir(parents=True, exist_ok=True)

            # 1. Fetching Clover
            self.u.cprint("Fetching latest Clover release information...", "green")
            release_info_str = self.d.get_string(self.CLOVER_RELEASE_URL)
            if not release_info_str:
                self.u.cprint("Failed to fetch Clover release info. Check internet or URL.", "red"); return False

            clover_asset_url = None
            clover_asset_name = None
            try:
                release_data = json.loads(release_info_str)
                # Prioritize direct EFI zips, then PKGs, then ISOs (as extraction gets complex)
                preferred_assets = []
                for asset in release_data.get("assets", []):
                    asset_name_lower = asset.get("name", "").lower()
                    if "clover" in asset_name_lower and asset_name_lower.endswith(".zip"): # e.g. CloverV2-5152.zip
                        preferred_assets.append({"url": asset.get("browser_download_url"), "name": asset.get("name"), "priority": 1})
                    elif asset_name_lower.endswith(".pkg"):
                        preferred_assets.append({"url": asset.get("browser_download_url"), "name": asset.get("name"), "priority": 2})
                    elif "clover" in asset_name_lower and asset_name_lower.endswith(".tar.xz") or asset_name_lower.endswith(".tar.lzma") or asset_name_lower.endswith(".7z"):
                         preferred_assets.append({"url": asset.get("browser_download_url"), "name": asset.get("name"), "priority": 0}) # Highest priority if it's a direct EFI archive

                if not preferred_assets and any(asset.get("name","").lower().endswith(".iso") for asset in release_data.get("assets",[])): # Fallback to ISO if nothing else
                     self.u.cprint("Warning: No direct ZIP/PKG/TAR found for Clover. Attempting ISO (extraction may be limited/fail).", "yellow")
                     for asset in release_data.get("assets", []):
                        asset_name_lower = asset.get("name", "").lower()
                        if "clover" in asset_name_lower and "x64.iso" in asset_name_lower: # Try to get X64 ISO
                            preferred_assets.append({"url": asset.get("browser_download_url"), "name": asset.get("name"), "priority": 3})
                            break
                     if not preferred_assets: # Still no X64 ISO, take any ISO
                        for asset in release_data.get("assets", []):
                            asset_name_lower = asset.get("name", "").lower()
                            if "clover" in asset_name_lower and asset_name_lower.endswith(".iso"):
                                preferred_assets.append({"url": asset.get("browser_download_url"), "name": asset.get("name"), "priority": 4})
                                break

                if preferred_assets:
                    preferred_assets.sort(key=lambda x: x["priority"])
                    clover_asset_url = preferred_assets[0]["url"]
                    clover_asset_name = preferred_assets[0]["name"]

                if not clover_asset_url:
                    self.u.cprint("Could not find a suitable Clover release asset (ZIP, PKG, TAR, or ISO).", "red"); return False
            except json.JSONDecodeError:
                self.u.cprint("Failed to parse Clover release JSON.", "red"); return False

            self.u.cprint(f"Found Clover release asset: {clover_asset_name}", "green")
            target_asset_path = clover_download_dir / clover_asset_name
            if not self.d.stream_to_file(clover_asset_url, str(target_asset_path)):
                self.u.cprint(f"Failed to download Clover asset from {clover_asset_url}.", "red"); return False
            self.u.cprint(f"Clover asset downloaded to: {target_asset_path}", "green")

            # 2. Extracting Clover - This can be multi-stage
            source_efi_dir_clover = None
            legacy_boot_source_dir = clover_extract_dir # Default for files like boot0af

            if clover_asset_name.lower().endswith((".zip", ".tar.xz", ".tar.lzma", ".7z")):
                if not self._extract_archive(target_asset_path, clover_extract_dir, "Clover Archive"):
                    self.u.cprint("Failed to extract Clover archive.", "red"); return False
                # Search for EFI folder, it might be nested
                search_paths = [clover_extract_dir, clover_extract_dir / "CloverV2", clover_extract_dir / "Clover"]
                for path_to_check in search_paths:
                    if (path_to_check / "EFI" / "CLOVER").is_dir() and (path_to_check / "EFI" / "BOOT").is_dir():
                        source_efi_dir_clover = path_to_check / "EFI"
                        legacy_boot_source_dir = path_to_check # Legacy boot files might be here
                        break
                if not source_efi_dir_clover: # Try one level deeper for some tarballs
                     for item in clover_extract_dir.iterdir():
                         if item.is_dir() and (item / "EFI" / "CLOVER").is_dir():
                             source_efi_dir_clover = item / "EFI"
                             legacy_boot_source_dir = item
                             break
            elif clover_asset_name.lower().endswith(".pkg"):
                clover_pkg_extract_path = clover_extract_dir / "pkg_extracted"
                if not self._extract_archive(target_asset_path, clover_pkg_extract_path, "Clover PKG"):
                    self.u.cprint("Failed to extract Clover PKG.", "red"); return False
                # PKG extraction might give an ISO or a folder structure.
                # Look for an ISO first (common for official Clover PKGs)
                iso_files = list(clover_pkg_extract_path.glob("*.iso")) # e.g. Clover.iso
                if not iso_files: iso_files = list(clover_pkg_extract_path.rglob("*.iso")) # recursive search

                if iso_files:
                    clover_iso_path = iso_files[0]
                    self.u.cprint(f"Found Clover ISO inside PKG: {clover_iso_path}", "green")
                    iso_extract_path = clover_extract_dir / "iso_extracted"
                    if not self._extract_archive(clover_iso_path, iso_extract_path, "Clover ISO from PKG"):
                        self.u.cprint("Failed to extract Clover ISO (from PKG).", "red"); return False
                    if (iso_extract_path / "EFI" / "CLOVER").is_dir(): # ISOs usually have EFI at root
                        source_efi_dir_clover = iso_extract_path / "EFI"
                        legacy_boot_source_dir = iso_extract_path # Legacy boot files often at ISO root
                    else: # Check for common Clover ISO structures like CDROOT/EFI
                        if (iso_extract_path / "CDROOT" / "EFI" / "CLOVER").is_dir():
                             source_efi_dir_clover = iso_extract_path / "CDROOT" / "EFI"
                             legacy_boot_source_dir = iso_extract_path / "CDROOT"
                else: # No ISO, check if EFI folder is directly in PKG payload
                    if (clover_pkg_extract_path / "EFI" / "CLOVER").is_dir():
                         source_efi_dir_clover = clover_pkg_extract_path / "EFI"
                         legacy_boot_source_dir = clover_pkg_extract_path
            elif clover_asset_name.lower().endswith(".iso"): # Direct ISO download
                 iso_extract_path = clover_extract_dir / "iso_extracted_direct"
                 if not self._extract_archive(target_asset_path, iso_extract_path, "Clover ISO Direct"):
                     self.u.cprint("Failed to extract Clover ISO (direct).", "red"); return False
                 if (iso_extract_path / "EFI" / "CLOVER").is_dir():
                     source_efi_dir_clover = iso_extract_path / "EFI"
                     legacy_boot_source_dir = iso_extract_path
                 elif (iso_extract_path / "CDROOT" / "EFI" / "CLOVER").is_dir(): # Some ISOs have CDROOT
                     source_efi_dir_clover = iso_extract_path / "CDROOT" / "EFI"
                     legacy_boot_source_dir = iso_extract_path / "CDROOT"


            if not source_efi_dir_clover or not source_efi_dir_clover.is_dir():
                self.u.cprint(f"Could not locate a usable Clover EFI directory after extraction from '{clover_asset_name}'. Structure might be unexpected.", "red")
                self.u.cprint(f"  Checked path hint: {source_efi_dir_clover if source_efi_dir_clover else 'N/A'}", "yellow")
                self.u.cprint(f"  Please inspect extracted contents in: {clover_extract_dir}", "yellow")
                return False
            self.u.cprint(f"Located Clover EFI source at: {source_efi_dir_clover}", "green")


            # 3. Mount EFI Partition
            efi_mount_point_path = pathlib.Path(tempfile.mkdtemp(prefix="efi_mount_", dir=str(self.temp_dir_base)))
            self.u.cprint(f"Mounting EFI partition '{efi_partition_path}' to '{efi_mount_point_path}'...", "green")
            mount_cmd = ["mount", efi_partition_path, str(efi_mount_point_path)]
            mount_result = self._run_command(mount_cmd, "Mount EFI partition", check=False)
            if not mount_result or mount_result.returncode != 0:
                self.u.cprint(f"Failed to mount EFI partition '{efi_partition_path}'.", "red"); return False

            # 4. Install Clover Files
            target_efi_root_on_usb = efi_mount_point_path / "EFI" # Clover's EFI goes into EFI/

            self.u.cprint(f"Copying Clover EFI files from '{source_efi_dir_clover}' to '{target_efi_root_on_usb}'...", "green")
            # shutil.copytree(source_efi_dir_clover, target_efi_root_on_usb, dirs_exist_ok=True) # This would create EFI/EFI/...
            # We need to copy contents of source_efi_dir_clover/* into target_efi_root_on_usb/
            for item in source_efi_dir_clover.iterdir():
                target_item_path = target_efi_root_on_usb / item.name
                if item.is_dir():
                    shutil.copytree(item, target_item_path, dirs_exist_ok=True)
                else:
                    target_efi_root_on_usb.mkdir(parents=True, exist_ok=True) # Ensure parent exists
                    shutil.copy2(item, target_item_path)

            target_clover_dir = target_efi_root_on_usb / "CLOVER"
            # Drivers (UEFI) - Clover paths can vary (drivers64UEFI, drivers/UEFI)
            clover_drivers_uefi_src_options = [
                source_efi_dir_clover / "CLOVER" / "drivers" / "UEFI",
                source_efi_dir_clover / "CLOVER" / "drivers64UEFI" # Older Clover
            ]
            clover_drivers_uefi_src = next((p for p in clover_drivers_uefi_src_options if p.is_dir()), None)
            target_drivers_uefi_dir = target_clover_dir / "drivers" / "UEFI" # Standardized target
            target_drivers_uefi_dir.mkdir(parents=True, exist_ok=True)

            if clover_drivers_uefi_src:
                self.u.cprint(f"Copying essential Clover UEFI drivers from {clover_drivers_uefi_src}...", "green")
                for driver_name in self.CLOVER_ESSENTIAL_DRIVERS_UEFI:
                    source_driver = clover_drivers_uefi_src / driver_name
                    if source_driver.exists():
                        shutil.copy2(source_driver, target_drivers_uefi_dir / driver_name)
                        self.u.cprint(f"  Copied: {driver_name}", "green")
                    else: self.u.cprint(f"  Warning: Essential UEFI driver '{driver_name}' not found in Clover package at '{clover_drivers_uefi_src}'.", "yellow")
            else: self.u.cprint("Warning: Standard Clover UEFI drivers source directory not found in package.", "yellow")

            # Kexts (Other)
            clover_kexts_other_src = source_efi_dir_clover / "CLOVER" / "kexts" / "Other"
            target_kexts_other_dir = target_clover_dir / "kexts" / "Other"
            target_kexts_other_dir.mkdir(parents=True, exist_ok=True)
            if clover_kexts_other_src.is_dir():
                self.u.cprint("Copying essential Clover Kexts (directories)...", "green")
                for kext_dir_name in self.CLOVER_ESSENTIAL_KEXTS_OTHER: # These are dir names
                    source_kext_dir = clover_kexts_other_src / kext_dir_name
                    if source_kext_dir.is_dir():
                        shutil.copytree(source_kext_dir, target_kexts_other_dir / kext_dir_name, dirs_exist_ok=True)
                        self.u.cprint(f"  Copied: {kext_dir_name}", "green")
                    else: self.u.cprint(f"  Warning: Essential Kext directory '{kext_dir_name}' not found in Clover package at '{clover_kexts_other_src}'.", "yellow")
            else: self.u.cprint(f"Warning: Clover kexts/Other source directory '{clover_kexts_other_src}' not found.", "yellow")

            # Config.plist
            config_plist_path_clover = target_clover_dir / "config.plist"
            # Check if base copy already included a config.plist (some Clover ZIPs might have it)
            # If not, or if user selects a specific arch, we overwrite.

            # --- CPU Architecture Specific Config ---
            arch_key_clover = self._select_cpu_architecture_for_config("clover")

            if arch_key_clover and arch_key_clover != "BACK":
                config_plist_str_clover = self.efi_cfg_mgr.get_config_plist("clover", arch_key_clover)
                if config_plist_str_clover:
                    try:
                        with open(config_plist_path_clover, "w", encoding="utf-8") as f:
                            f.write(config_plist_str_clover)
                        self.u.cprint(f"Installed generic Clover config.plist for '{arch_key_clover}'.", "green")
                        # Enhanced Warning Message for Clover
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
                else: # Should not happen
                    self.u.cprint(f"Could not find generic Clover config for '{arch_key_clover}'. Clover may use internal default.", "yellow")
            elif arch_key_clover == "BACK":
                self.u.cprint("Clover installation cancelled by user during CPU architecture selection.", "yellow")
                return False # Signal failure
            else: # User chose to skip or no specific configs available
                # Try to copy a sample if one was included in the Clover package and no config.plist exists yet
                if not config_plist_path_clover.exists():
                    sample_plist_path_clover_src = source_efi_dir_clover / "CLOVER" / "config.plist.sample"
                    if not sample_plist_path_clover_src.exists():
                         sample_plist_path_clover_src = source_efi_dir_clover / "CLOVER" / "config-sample.plist"

                    if sample_plist_path_clover_src.exists():
                        shutil.copy2(sample_plist_path_clover_src, config_plist_path_clover)
                        self.u.cprint(f"Copied sample Clover config to '{config_plist_path_clover.name}'.", "green")
                        self.u.cprint("IMPORTANT: This is a SAMPLE config. It needs to be configured for your specific hardware!", "yellow")
                    else:
                         self.u.cprint("No specific generic config chosen, and no sample found in Clover package.", "yellow")
                         self.u.cprint(f"'{config_plist_path_clover.name}' may be missing or using Clover's internal default.", "yellow")
                else:
                    self.u.cprint("Using existing config.plist found in Clover package or skipping specific generic config.", "yellow")

            # --- End CPU Architecture Specific Config ---

            # 5. Legacy Boot Setup
            if not gpt_scheme:
                self.u.cprint("Setting up Clover Legacy Boot (MBR)...", "green")
                # Legacy boot files are often at the root of the Clover distribution archive
                # legacy_boot_source_dir was determined during extraction
                boot0_file_name = self.CLOVER_LEGACY_BOOT_FILES["boot0"] # e.g. boot0af
                boot1f32_file_name = self.CLOVER_LEGACY_BOOT_FILES["boot1f32"] # e.g. boot1f32alt

                boot0_file = legacy_boot_source_dir / boot0_file_name
                if not boot0_file.exists() and boot0_file_name == "boot0af": # Fallback for boot0
                    boot0_file = legacy_boot_source_dir / "boot0ss"
                    if boot0_file.exists(): self.u.cprint(f"  Using fallback MBR boot file: boot0ss", "yellow")

                boot1f32_file = legacy_boot_source_dir / boot1f32_file_name

                if boot0_file.exists():
                    dd_mbr_cmd = ["dd", f"if={str(boot0_file)}", f"of={usb_device_path}", "bs=440", "count=1", "conv=fsync"] # Some Clover boot0 are 512b, bs=440 is safer for MBR code area
                    if self._run_command(dd_mbr_cmd, "Write Clover MBR"):
                         self.u.cprint(f"  Successfully wrote '{boot0_file.name}' to MBR of '{usb_device_path}'.", "green")
                    else: self.u.cprint(f"  Warning: Failed to write MBR for Clover on '{usb_device_path}'.", "yellow")
                else: self.u.cprint(f"  Warning: Clover MBR file ('{boot0_file_name}' or 'boot0ss') not found at '{legacy_boot_source_dir}'.", "yellow")

                if boot1f32_file.exists():
                    dd_pbr_cmd = ["dd", f"if={str(boot1f32_file)}", f"of={efi_partition_path}", "conv=fsync"]
                    if self._run_command(dd_pbr_cmd, "Write Clover PBR"):
                        self.u.cprint(f"  Successfully wrote '{boot1f32_file.name}' to PBR of '{efi_partition_path}'.", "green")
                    else: self.u.cprint(f"  Warning: Failed to write PBR for Clover on '{efi_partition_path}'.", "yellow")
                else: self.u.cprint(f"  Warning: Clover PBR file '{boot1f32_file.name}' not found at '{legacy_boot_source_dir}'.", "yellow")

            self.u.cprint("Clover installation attempt completed.", "green")
            return True

        except Exception as e:
            self.u.cprint(f"An unexpected error occurred during Clover installation: {e}", "red")
            import traceback
            self.u.cprint(traceback.format_exc(), "yellow")
            return False
        finally:
            if efi_mount_point_path and efi_mount_point_path.is_mount():
                self.u.cprint(f"Unmounting EFI partition '{efi_mount_point_path}'...", "green")
                self._run_command(["sync"], "Sync before unmount", check=False)
                umount_res = self._run_command(["umount", "-lf", str(efi_mount_point_path)], "Unmount EFI", check=False)
                if not umount_res or umount_res.returncode != 0:
                     self.u.cprint(f"  Warning: Could not unmount {efi_mount_point_path}. Manual check may be needed.", "yellow")
            if efi_mount_point_path and efi_mount_point_path.exists():
                shutil.rmtree(efi_mount_point_path, ignore_errors=True)

            if clover_download_dir.exists(): shutil.rmtree(clover_download_dir, ignore_errors=True)
            if clover_extract_dir.exists(): shutil.rmtree(clover_extract_dir, ignore_errors=True)
            # clover_pkg_extract_path is inside clover_extract_dir, so it's removed with parent
            self.u.cprint("Clover temporary files cleaned up.", "green")


    def _handle_custom_efi_copy(self, efi_partition_path_str):
        self.u.head("Custom EFI Setup")
        efi_mount_point_path = None # For finally block

        try:
            custom_efi_input_path_str = input("Please drag & drop your custom EFI folder here, or type the full path: ").strip()
            if not custom_efi_input_path_str:
                self.u.cprint("No path provided. Aborting custom EFI copy.", "yellow")
                return False

            custom_efi_input_path = pathlib.Path(custom_efi_input_path_str)

            if not custom_efi_input_path.exists() or not custom_efi_input_path.is_dir():
                self.u.cprint(f"Error: The provided path '{custom_efi_input_path_str}' is not a valid directory or does not exist.", "red")
                return False

            # Determine the actual source EFI directory to copy
            source_efi_to_copy = None
            if custom_efi_input_path.name.upper() == "EFI":
                source_efi_to_copy = custom_efi_input_path
            elif (custom_efi_input_path / "EFI").is_dir():
                source_efi_to_copy = custom_efi_input_path / "EFI"

            if not source_efi_to_copy or not source_efi_to_copy.is_dir():
                self.u.cprint(f"Error: Could not find an 'EFI' subfolder in '{custom_efi_input_path_str}', nor is the path itself an EFI folder.", "red")
                self.u.cprint("Please provide a path to a folder named 'EFI', or a folder that contains an 'EFI' subfolder.", "red")
                return False

            self.u.cprint(f"Validated custom EFI source: {source_efi_to_copy}", "green")

            # Mount EFI Partition
            efi_mount_point_path = pathlib.Path(tempfile.mkdtemp(prefix="efi_mount_", dir=str(self.temp_dir_base)))
            self.u.cprint(f"Mounting EFI partition '{efi_partition_path_str}' to '{efi_mount_point_path}'...", "green")
            mount_cmd = ["mount", efi_partition_path_str, str(efi_mount_point_path)]
            mount_result = self._run_command(mount_cmd, "Mount EFI partition for custom copy", check=False)
            if not mount_result or mount_result.returncode != 0:
                self.u.cprint(f"Failed to mount EFI partition '{efi_partition_path_str}'.", "red")
                return False

            # Copy EFI Folder
            target_efi_on_usb = efi_mount_point_path / "EFI"

            self.u.cprint(f"Preparing to copy custom EFI to '{target_efi_on_usb}'...", "green")
            if target_efi_on_usb.exists():
                self.u.cprint(f"Removing existing EFI folder at '{target_efi_on_usb}'...", "yellow")
                try:
                    shutil.rmtree(target_efi_on_usb)
                except OSError as e:
                    self.u.cprint(f"Error removing existing EFI folder '{target_efi_on_usb}': {e}", "red")
                    return False

            self.u.cprint(f"Copying '{source_efi_to_copy}' to '{target_efi_on_usb}'...", "green")
            try:
                shutil.copytree(source_efi_to_copy, target_efi_on_usb)
                self.u.cprint(f"Successfully copied custom EFI from '{source_efi_to_copy}' to '{target_efi_on_usb}'.", "green")
            except Exception as e:
                self.u.cprint(f"Error copying custom EFI folder: {e}", "red")
                return False

            return True

        except Exception as e:
            self.u.cprint(f"An unexpected error occurred during custom EFI copy: {e}", "red")
            import traceback
            self.u.cprint(traceback.format_exc(), "yellow")
            return False
        finally:
            if efi_mount_point_path: # Ensure it was defined
                if efi_mount_point_path.is_mount():
                    self.u.cprint(f"Unmounting EFI partition '{efi_mount_point_path}'...", "green")
                    self._run_command(["sync"], "Sync before unmount custom EFI", check=False)
                    umount_res = self._run_command(["umount", "-lf", str(efi_mount_point_path)], "Unmount EFI custom", check=False)
                    if not umount_res or umount_res.returncode != 0:
                         self.u.cprint(f"  Warning: Could not unmount {efi_mount_point_path} after custom EFI copy. Manual check may be needed.", "yellow")
                if efi_mount_point_path.exists(): # Mount point dir itself
                    shutil.rmtree(efi_mount_point_path, ignore_errors=True)
            self.u.cprint("Custom EFI copy process finished, temporary files cleaned up.", "green")

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

        self.u.cprint("\n--- Placeholder URLs / Generic Configs ---", "red") # Changed color to red for emphasis
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
