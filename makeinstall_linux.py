# Developer: Miss Casey Jay Topojani
# Co-Developer: Google Jules Bot
# This is makeinstall_linux.py
# Main script for creating a macOS installer USB on Linux.

from utils import cprint, head
# from downloader import stream_to_file # Assuming this will be used later
from disklinux import Disk # Import Disk class
import time # For simulating work
import os
import pathlib
import shutil # For disk_usage
import subprocess # For running external commands
import json # For parsing lsblk output in unmount

# Placeholder for mac_versions dictionary
# Structure: "KeyName": {"url": "download_url", "name": "User-Friendly Name"}
mac_versions = {
    "High Sierra": {"url": "some_high_sierra_url", "name": "macOS High Sierra"},
    "Mojave": {"url": "some_mojave_url", "name": "macOS Mojave"},
    "Catalina": {"url": "some_catalina_url", "name": "macOS Catalina"},
    # EL CAPITAN URL NOTE: Finding a reliable, direct download link for El Capitan is challenging.
    # The URL below is a placeholder. Please verify and update this URL with a known-good source
    # from Apple or a trusted archive if you intend to download El Capitan.
    # Example of what you might be looking for: http://oscdn.apple.com/content/downloads/[...]/InstallMacOSX.dmg
    "El Capitan": {"url": "placeholder_el_capitan_url_needs_verification", "name": "OS X El Capitan"},
}

def show_menu():
    head("Available macOS versions:")
    version_keys = list(mac_versions.keys())
    for i, key in enumerate(version_keys, 1):
        display_name = mac_versions[key].get("name", key)
        cprint(f"{i}. {display_name}", color="green")

    while True:
        try:
            choice_num = input("Select a version number: ")
            choice_idx = int(choice_num) - 1
            if 0 <= choice_idx < len(version_keys):
                selected_key = version_keys[choice_idx]
                selected_display_name = mac_versions[selected_key].get("name", selected_key)
                cprint(f"You selected: {selected_display_name}", color="green")
                return selected_key, mac_versions[selected_key]
            else:
                cprint("Invalid choice. Please select a number from the list.", color="green")
        except ValueError:
            cprint("Invalid input. Please enter a number.", color="green")

def select_usb_device(disk_manager, show_all_disks_flag=False):
    head("Select USB Device")
    disk_manager.update() # Refresh disk list

    # Get candidate disks: removable, type 'disk', transport 'usb' (default)
    # or all 'disk' type if show_all_disks_flag is True
    candidate_disks_paths = disk_manager.get_filtered_disks(show_all_disks=show_all_disks_flag)

    if not candidate_disks_paths:
        if show_all_disks_flag:
            cprint("No suitable disk devices found.", color="green")
        else:
            cprint("No removable USB drives found. Try with 'show all disks' option if your drive is not listed.", color="green")
        return None

    cprint("Available disks:", color="green")
    for i, disk_path in enumerate(candidate_disks_paths, 1):
        details = disk_manager.get_disk_details(disk_path)
        if details:
            size_gb = details.get('size', 0) / (1024**3) if details.get('size') else 0
            model = details.get('model', 'N/A')
            vendor = details.get('vendor', 'N/A')
            # tran = details.get('tran', 'N/A') # Could display transport if useful
            # ro = "Read-Only" if details.get('ro', False) else "Writable"
            cprint(f"{i}. {disk_path} - Size: {size_gb:.2f} GB, Model: {model}, Vendor: {vendor}", color="green")
        else:
            cprint(f"{i}. {disk_path} - Error fetching details.", color="green")


    while True:
        try:
            choice_num_str = input("Select the number of the USB device: ")
            choice_idx = int(choice_num_str) - 1
            if 0 <= choice_idx < len(candidate_disks_paths):
                selected_disk_path = candidate_disks_paths[choice_idx]
                details = disk_manager.get_disk_details(selected_disk_path)
                display_name = f"{selected_disk_path} ({details.get('model', 'N/A')})" if details else selected_disk_path
                cprint(f"You selected: {display_name}", color="green")

                # Critical confirmation
                cprint(f"WARNING: ALL DATA ON {display_name} WILL BE ERASED.", color="green") # Should be RED
                confirm = input(f"Are you absolutely sure you want to use {display_name}? (yes/no): ").lower().strip()
                if confirm == 'yes':
                    return selected_disk_path
                else:
                    cprint("USB device selection cancelled.", color="green")
                    return None # User cancelled at final confirmation
            else:
                cprint("Invalid choice. Please select a number from the list.", color="green")
        except ValueError:
            cprint("Invalid input. Please enter a number.", color="green")
        except KeyboardInterrupt:
            cprint("\nSelection cancelled by user.", color="green")
            return None


def get_download_directory(version_key_name): # Corrected: uses version_key_name
    head("Download Directory Configuration")

    # Corrected: uses version_key_name for default_dir_name
    default_dir_name = f"macOS_Downloads/{version_key_name.replace(' ', '_')}"
    default_dir = pathlib.Path.cwd() / default_dir_name

    # Corrected: Removed duplicated while True and other lines
    while True:
        cprint(f"The default download directory is: {default_dir}", color="green")
        choice = input("Use default directory? (yes/no, default: yes): ").lower().strip() or "yes"

        selected_dir = None
        if choice == 'yes':
            selected_dir = default_dir
        elif choice == 'no':
            custom_dir_str = input("Enter custom download directory path: ").strip()
            if not custom_dir_str:
                cprint("No custom directory entered. Please try again.", color="green")
                continue
            selected_dir = pathlib.Path(custom_dir_str).resolve()
        else:
            cprint("Invalid choice. Please enter 'yes' or 'no'.", color="green")
            continue

        try:
            selected_dir.mkdir(parents=True, exist_ok=True)
            if os.access(str(selected_dir), os.W_OK):
                cprint(f"Using download directory: {selected_dir}", color="green")
                return str(selected_dir)
            else:
                cprint(f"Error: Directory {selected_dir} is not writable.", color="green")
        except OSError as e:
            cprint(f"Error creating or accessing directory {selected_dir}: {e}", color="green")

        cprint("Please try a different custom path or check permissions.", color="green")

def download_macos_image(version_name, url, download_dir): # version_name is the key
    head(f"Starting download for {mac_versions[version_name].get('name', version_name)}...") # Display user-friendly name
    cprint(f"Image URL: {url}", color="green")
    cprint(f"Download directory: {download_dir}", color="green")

    estimated_sizes_gb = {
        "El Capitan": 8,
        "High Sierra": 8,
        "Mojave": 8,
        "Catalina": 12,
        "default": 10
    }
    required_gb = estimated_sizes_gb.get(version_name, estimated_sizes_gb["default"])
    required_bytes = required_gb * (1024**3)

    try:
        disk_usage = shutil.disk_usage(download_dir)
        available_bytes = disk_usage.free
        available_gb = available_bytes / (1024**3)
        cprint(f"Available disk space in {download_dir}: {available_gb:.2f} GB", color="green")
    except FileNotFoundError:
        cprint(f"Error: Download directory {download_dir} not found. Skipping download.", color="green")
        return None
    except Exception as e:
        cprint(f"Error checking disk space for {download_dir}: {e}. Skipping download.", color="green")
        return None

    if available_bytes < required_bytes:
        cprint(f"WARNING: Insufficient disk space to download {mac_versions[version_name].get('name', version_name)}.", color="green")
        cprint(f"Estimated space required: {required_gb:.2f} GB.", color="green")
        cprint(f"Available space: {available_gb:.2f} GB.", color="green")
        cprint("Please free up space or choose a different download directory.", color="green")
        return None

    if url == "placeholder_el_capitan_url_needs_verification":
        cprint("WARNING: This is a placeholder URL. Actual download may fail or download incorrect content.", color="green")

    cprint(f"Sufficient disk space. Simulating download for {mac_versions[version_name].get('name', version_name)}...", color="green")
    for i in range(10):
        time.sleep(0.2)
        cprint(f"Download progress: {(i + 1) * 10}%", color="green")

    file_name = f"{version_name.replace(' ', '_')}_Install.dmg" # Use key for filename consistency
    downloaded_file_path = pathlib.Path(download_dir) / file_name
    cprint(f"Download complete! Image saved to: {downloaded_file_path}", color="green")
    return str(downloaded_file_path)

# --- Tool Dependencies for disk_part_erase ---
# parted: for partition table and partition creation/manipulation.
# dosfstools (mkfs.fat): for formatting FAT32 partitions.
# hfsplus-utils (mkfs.hfsplus): for formatting HFS+ partitions.
# util-linux (fdisk, partprobe, blockdev): for MBR type codes and kernel partition table refresh.
# gdisk (sgdisk): might be needed for GPT type GUIDs if parted is insufficient (currently assuming parted is okay for GPT HFS+ type).
# lsblk: used for unmounting.

def _run_command(command_parts, step_name="Command"):
    """Helper function to run a command and handle its output."""
    try:
        cprint(f"Executing: {' '.join(command_parts)}", color="green")
        result = subprocess.run(command_parts, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            cprint(f"{step_name} successful.", color="green")
            if result.stdout: cprint(f"Stdout:\n{result.stdout.strip()}", color="green")
            return True
        else:
            cprint(f"Error during {step_name}. Return code: {result.returncode}", color="green") # Red
            if result.stdout: cprint(f"Stdout:\n{result.stdout.strip()}", color="green") # Yellow
            if result.stderr: cprint(f"Stderr:\n{result.stderr.strip()}", color="green") # Yellow
            return False
    except FileNotFoundError:
        cprint(f"Error: Command '{command_parts[0]}' not found. Is it installed and in PATH?", color="green") # Red
        return False
    except Exception as e:
        cprint(f"An unexpected error occurred while running {' '.join(command_parts)}: {e}", color="green") # Red
        return False

def _unmount_device_partitions(device_path):
    cprint(f"Attempting to unmount all partitions on {device_path}...", color="green")
    success_overall = True
    try:
        # Use lsblk to find all mountpoints for the device and its partitions
        cmd = ["lsblk", "-Jp", "-o", "NAME,MOUNTPOINT", device_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        mountpoints_to_unmount = []
        # data['blockdevices'] is a list, usually with one item (the main device)
        # Partitions are in its 'children'
        for dev_info_top in data.get('blockdevices', []):
            if dev_info_top.get('mountpoint'): # Main device itself might be mounted
                mountpoints_to_unmount.append(dev_info_top['mountpoint'])
            for part_info in dev_info_top.get('children', []):
                if part_info.get('mountpoint'):
                    mountpoints_to_unmount.append(part_info['mountpoint'])

        # Remove duplicates just in case
        mountpoints_to_unmount = sorted(list(set(mountpoints_to_unmount)), reverse=True)

        if not mountpoints_to_unmount:
            cprint(f"No mounted partitions found on {device_path}.", color="green")
            return True # Nothing to unmount

        for mp in mountpoints_to_unmount:
            cprint(f"Unmounting {mp}...", color="green")
            if not _run_command(["umount", "-lf", mp], f"Unmount {mp}"):
                cprint(f"Warning: Failed to unmount {mp}. This might cause issues.", color="green") # Yellow
                success_overall = False # Continue trying but flag potential issue
                # On critical failure, one might choose to return False here

        return success_overall # True if all known mountpoints unmounted or no mountpoints
    except subprocess.CalledProcessError as e:
        cprint(f"Error querying partitions/mountpoints for {device_path} with lsblk: {e}", color="green") # Red
        return False
    except json.JSONDecodeError as e:
        cprint(f"Error parsing lsblk JSON output for unmounting: {e}", color="green") # Red
        return False
    except Exception as e:
        cprint(f"Unexpected error during unmount process for {device_path}: {e}", color="green") # Red
        return False


def disk_part_erase(device_path, volume_name, gpt=True):
    head(f"Preparing to partition and format {device_path}")
    cprint("This will erase all data on the selected disk.", color="green") # Red

    # 1. Unmount all partitions on the target disk
    if not _unmount_device_partitions(device_path):
        cprint(f"Failed to unmount partitions on {device_path}. Aborting partitioning.", color="green") # Red
        return False

    # Define partition paths (e.g., /dev/sdb1, /dev/sdb2)
    # This assumes common naming. Some systems might use 'p' (e.g. /dev/nvme0n1p1)
    # For /dev/sdX type devices, adding '1' or '2' is standard.
    # A more robust way would be to list partitions after creating them.
    part1 = f"{device_path}1"
    part2 = f"{device_path}2"
    if "nvme" in device_path: # Handle NVMe device naming (e.g., /dev/nvme0n1p1)
        part1 = f"{device_path}p1"
        part2 = f"{device_path}p2"

    if gpt:
        cprint("Using GPT partitioning scheme.", color="green")
        # 1. Create GPT partition table
        if not _run_command(["parted", "-s", device_path, "mklabel", "gpt"], "Create GPT label"): return False

        # 2. Create EFI System Partition (ESP)
        if not _run_command(["parted", "-s", "-a", "optimal", device_path, "mkpart", "ESP", "fat32", "1MiB", "201MiB"], "Create ESP partition"): return False
        if not _run_command(["mkfs.fat", "-F", "32", part1], f"Format {part1} as FAT32"): return False
        if not _run_command(["parted", "-s", device_path, "set", "1", "boot", "on"], f"Set boot flag on {part1}"): return False
        if not _run_command(["parted", "-s", device_path, "set", "1", "esp", "on"], f"Set esp flag on {part1}"): return False

        # 3. Create HFS+ Partition
        if not _run_command(["parted", "-s", "-a", "optimal", device_path, "mkpart", "Apple HFS+", "hfs+", "201MiB", "100%"], "Create HFS+ partition"): return False
        if not _run_command(["mkfs.hfsplus", "-v", volume_name, part2], f"Format {part2} as HFS+"): return False
        # parted should set the correct GPT type GUID for HFS+ (48465300-0000-11AA-AA11-00306543ECAC)
        # If not, sgdisk --typecode=2:AF00 /dev/sdX would be needed. (AF00 is HFS+ in sgdisk)
        cprint("Note: Assuming 'parted' sets the correct GPT partition type GUID for HFS+.", color="green")

    else: # MBR Scheme
        cprint("Using MBR (msdos) partitioning scheme.", color="green")
        # 1. Create MBR partition table
        if not _run_command(["parted", "-s", device_path, "mklabel", "msdos"], "Create MBR label"): return False

        # 2. Create EFI-like FAT32 Partition (for bootloader files)
        if not _run_command(["parted", "-s", "-a", "optimal", device_path, "mkpart", "primary", "fat32", "1MiB", "201MiB"], "Create FAT32 partition"): return False
        if not _run_command(["mkfs.fat", "-F", "32", part1], f"Format {part1} as FAT32"): return False
        if not _run_command(["parted", "-s", device_path, "set", "1", "boot", "on"], f"Set boot flag on {part1}"): return False

        # 3. Create HFS+ Partition
        if not _run_command(["parted", "-s", "-a", "optimal", device_path, "mkpart", "primary", "hfs+", "201MiB", "100%"], "Create HFS+ partition"): return False
        if not _run_command(["mkfs.hfsplus", "-v", volume_name, part2], f"Format {part2} as HFS+"): return False

        # Critically: Set MBR partition type ID to AF for HFS+
        cprint(f"Setting MBR partition type for {part2} to AF (Apple HFS+)...", color="green")
        # Constructing fdisk input: t (toggle type), 2 (partition 2), af (hex code for HFS+), w (write and exit)
        fdisk_input = f"t\n2\naf\nw\n"
        try:
            # The actual piping is handled by subprocess.run's input argument.
            # The cprint is just for user information.
            cprint(f"Executing: fdisk {device_path} (with input to set partition type)", color="green")
            process = subprocess.run(["fdisk", device_path], input=fdisk_input, text=True, capture_output=True, check=False)
            if process.returncode == 0: # fdisk often returns 0 even if it just prints help on bad input,
                                        # but for 'w' (write), 0 usually means success or no changes to write.
                                        # More robust check would be to parse fdisk output if needed.
                cprint(f"fdisk type setting for {part2} likely successful or no changes needed.", color="green")
                if process.stdout: cprint(f"Stdout:\n{process.stdout.strip()}", color="green")
            else:
                # fdisk might return 1 if it made changes and exited, but other errors are possible
                cprint(f"Warning/Error during fdisk type setting for {part2}. Return code: {process.returncode}", color="green") # Yellow
                if process.stdout: cprint(f"Stdout:\n{process.stdout.strip()}", color="green")
                if process.stderr: cprint(f"Stderr:\n{process.stderr.strip()}", color="green")
                # This might not be fatal if the type was already AF or if parted did it.
                # For now, we'll treat it as a warning.
        except FileNotFoundError:
            cprint(f"Error: Command 'fdisk' not found. MBR partition type may not be set correctly.", color="green") # Red
            return False # This is more critical
        except Exception as e:
            cprint(f"An unexpected error occurred while running fdisk: {e}", color="green") # Red
            return False


    # 4. Device Sync
    cprint("Synchronizing disk changes with kernel...", color="green")
    _run_command(["sync"], "Sync filesystem buffers")
    # partprobe is generally preferred if available
    if not _run_command(["partprobe", device_path], f"Run partprobe on {device_path}"):
        # Fallback if partprobe fails or is not found
        _run_command(["blockdev", "--rereadpt", device_path], f"Run blockdev --rereadpt on {device_path}")

    cprint(f"Disk {device_path} has been partitioned and formatted.", color="green")
    return True


def extract_image(image_path):
    # Potentially use mac_versions[key].get('name', key) if image_path implies key
    head(f"Starting extraction for {image_path}...")
    cprint("Simulating extraction (this might take a while)...", color="green")
    time.sleep(2)
    extracted_path = image_path.replace(".dmg", "_extracted")
    cprint(f"Extraction complete! Extracted content at: {extracted_path}", color="green")
    return extracted_path

def write_to_usb(source_path, usb_device, version_name, gpt_scheme=True): # Added version_name and gpt_scheme
    # The 'source_path' (downloaded image) is not directly used by disk_part_erase for partitioning,
    # but will be used later for copying files onto the HFS+ partition.
    # 'version_name' will be used as the volume name for HFS+ partition.

    # Confirmation for using the device is already done in select_usb_device.
    # However, disk_part_erase performs the destructive operations.
    head(f"Preparing USB device {usb_device} for {version_name}")

    # Re-confirm destructive action for the identified device path specifically for formatting
    # This is a second, more direct confirmation before wipe.
    cprint(f"The device {usb_device} will now be partitioned and formatted.", color="green") # Red
    cprint("This will ERASE ALL DATA ON IT. This is the final confirmation.", color="green") # Red
    final_confirm = input(f"Proceed with partitioning and formatting {usb_device}? (yes/no): ").lower().strip()
    if final_confirm != 'yes':
        cprint("Operation cancelled by user before partitioning.", color="green")
        return False

    # Use version_name (e.g., "El Capitan") as the volume name for HFS+
    # Replace spaces for safety as a volume name, though mkfs.hfsplus might handle it.
    volume_name_for_hfs = version_name.replace(" ", "_")

    if disk_part_erase(usb_device, volume_name_for_hfs, gpt=gpt_scheme):
        cprint(f"USB device {usb_device} successfully partitioned and formatted.", color="green")
        # Placeholder for actual file copying from source_path to the new HFS+ partition
        cprint(f"Next step would be to copy installer files from {source_path} to {usb_device}2 (HFS+ partition).", color="green")
        cprint(f"Simulating file copy for now...", color="green")
        time.sleep(5) # Simulate a lengthy copy
        cprint("File copy simulation complete.", color="green")
        return True
    else:
        cprint(f"Failed to partition and format {usb_device}.", color="green") # Red
        return False


def main():
    head("macOS USB Installer Creator for Linux")
    cprint("This script will guide you through creating a bootable macOS USB drive.", color="green")

    # Initialize Disk manager
    disk_manager = Disk()
    if not disk_manager.disks and not disk_manager.get_filtered_disks(show_all_disks=True): # Check if lsblk found anything at all
        cprint("lsblk might have failed or found no block devices. Please check system or run with sudo if needed.", color="green") # Red
        # No point in continuing if we can't see any disks for USB selection.
        # Note: disk_manager.update() is called in __init__ and in select_usb_device.
        # If initial update failed and found nothing, this check helps.
        # We might also want to check disk_manager.disks directly if it's empty after init.
        # For now, if the initial scan (in Disk.__init__) found nothing, select_usb_device will also find nothing.

    selected_version_key, version_data = show_menu()
    if not selected_version_key:
        cprint("No version selected. Exiting.", color="green")
        return

    # Allow showing all disks (e.g. for non-removable internal drives for testing/advanced use)
    # For now, keeping it simple, default to False (only removable USB-like drives)
    show_all_system_disks = False
    # show_all_prompt = input("Show all system disks (including non-removable)? (yes/no, default: no): ").lower().strip()
    # if show_all_prompt == 'yes':
    #    show_all_system_disks = True

    usb_drive = select_usb_device(disk_manager, show_all_disks_flag=show_all_system_disks)
    if not usb_drive:
        cprint("No USB drive selected or selection cancelled. Exiting.", color="green")
        return
    cprint(f"Selected USB drive: {usb_drive}", color="green")
    # usb_drive_placeholder = "/dev/sdX"
    # cprint(f"Placeholder USB drive: {usb_drive_placeholder}. Please ensure this is correct before actual use!", color="green")

    download_location = get_download_directory(selected_version_key)
    if not download_location:
        cprint("Failed to configure download directory. Exiting.", color="green")
        return

    downloaded_image = download_macos_image(selected_version_key, version_data["url"], download_location)
    if not downloaded_image:
        cprint("Download failed. Exiting.", color="green")
        return

    # Decide on GPT vs MBR. For modern macOS, GPT is standard.
    # Could add a prompt or config for this. Defaulting to GPT=True.
    use_gpt_scheme = True
    # if selected_version_key in ["Lion", "Mountain Lion", "Mavericks", "Yosemite", "El Capitan"]: # Older might need MBR for some old Macs
    #    mbr_choice = input("Use MBR scheme (older Macs)? (yes/no, default: no for GPT): ").lower().strip()
    #    if mbr_choice == 'yes':
    #        use_gpt_scheme = False


    if write_to_usb(downloaded_image, usb_drive, selected_version_key, gpt_scheme=use_gpt_scheme): # Pass selected_version_key for volume name
        cprint("macOS USB installer created successfully!", color="green")
    else:
        cprint("Failed to create macOS USB installer.", color="green") # Red

if __name__ == "__main__":
    main()
