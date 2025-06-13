# This is disklinux.py
import subprocess
import json

class Disk:
    def __init__(self):
        self.disks = {}
        self.update() # Initial update

    def update(self):
        """
        Updates the list of disks using lsblk.
        Filters for type="disk" and rm=true (removable).
        """
        self.disks = {} # Reset disk list
        try:
            # -J for JSON, -b for bytes, -o for specified columns
            # Adding VENDOR,MODEL,RO (Read-Only), TRAN (Transport type) for more info
            cmd = ["lsblk", "-J", "-b", "-o", "NAME,SIZE,MODEL,VENDOR,TYPE,RM,RO,TRAN,PATH,MOUNTPOINT"]
            process_result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(process_result.stdout)

            if 'blockdevices' not in data:
                print("Error: 'blockdevices' key not found in lsblk output.")
                return

            for device in data['blockdevices']:
                # Filter for type == "disk"
                if device.get('type') == 'disk':
                    # Check if 'rm' (removable) flag is true (boolean true or integer 1)
                    # lsblk JSON output uses boolean true/false for 'rm'
                    is_removable = device.get('rm', False) # Default to False if 'rm' key is missing

                    # Store relevant information including type and rm status
                    # Key by PATH for uniqueness, e.g. /dev/sda
                    disk_path = device.get('path', device.get('name')) # Prefer 'path' if available
                    if not disk_path: # Should always have at least 'name'
                        continue

                    self.disks[disk_path] = {
                        'name': device.get('name'), # Short name like sda
                        'path': disk_path,        # Full path like /dev/sda
                        'size': device.get('size'),
                        'model': device.get('model', 'N/A'),
                        'vendor': device.get('vendor', 'N/A'),
                        'type': device.get('type'),
                        'rm': is_removable,
                        'ro': device.get('ro', False), # Read-only status
                        'tran': device.get('tran', 'N/A'), # Transport type (e.g., usb, sata)
                        'mountpoint': device.get('mountpoint'), # Primary mountpoint if any
                        'children': device.get('children', []) # Partitions
                    }
        except subprocess.CalledProcessError as e:
            print(f"Error executing lsblk: {e}")
            print(f"Stderr: {e.stderr}")
            self.disks = {} # Ensure disks is empty on error
        except FileNotFoundError:
            print("Error: lsblk command not found. Please ensure it is installed and in your PATH.")
            self.disks = {} # Ensure disks is empty
        except json.JSONDecodeError as e:
            print(f"Error parsing lsblk JSON output: {e}")
            self.disks = {}
        except Exception as e:
            print(f"An unexpected error occurred while updating disk list: {e}")
            self.disks = {}

    def get_filtered_disks(self, show_all_disks=False):
        """
        Returns a list of disk paths, filtered for removable USB drives
        unless show_all_disks is True.
        """
        filtered_disk_paths = []
        for path, info in self.disks.items():
            if show_all_disks:
                # When showing all, we might still want to exclude certain non-user-pluggable disks
                # For now, let's include all 'disk' type if show_all_disks is true
                if info['type'] == 'disk':
                    filtered_disk_paths.append(path)
            else:
                # Default filtering: removable, disk type, and typically USB transport
                if info['rm'] and info['type'] == 'disk' and (info['tran'] == 'usb' if info['tran'] else True):
                    filtered_disk_paths.append(path)
        return filtered_disk_paths

    def get_disk_details(self, disk_path):
        return self.disks.get(disk_path)

# Example Usage (for testing disklinux.py directly)
if __name__ == "__main__":
    print("Initializing Disk Manager...")
    disk_manager = Disk()
    print("\nAll Disks Found (after initial update):")
    if not disk_manager.disks:
        print("No disks found or an error occurred.")
    else:
        for path, details in disk_manager.disks.items():
            print(f"  Path: {path}, Type: {details['type']}, Removable: {details['rm']}, Size: {details['size'] / (1024**3):.2f}GB, Model: {details['model']}, Vendor: {details['vendor']}, Transport: {details['tran']}")

    print("\nFiltered Removable USB-like Disks:")
    removable_disks = disk_manager.get_filtered_disks()
    if not removable_disks:
        print("No removable USB-like disks found.")
    else:
        for disk_path in removable_disks:
            details = disk_manager.get_disk_details(disk_path)
            print(f"  Path: {disk_path}, Size: {details['size'] / (1024**3):.2f}GB, Model: {details['model']}")

    print("\nFiltered Disks (show_all_disks=True):")
    all_disks_それでも = disk_manager.get_filtered_disks(show_all_disks=True)
    if not all_disks_それでも:
        print("No disks found (show_all_disks=True).")
    else:
        for disk_path in all_disks_それでも:
            details = disk_manager.get_disk_details(disk_path)
            print(f"  Path: {disk_path}, Size: {details['size'] / (1024**3):.2f}GB, Model: {details['model']}, Removable: {details['rm']}, Type: {details['type']}")

    # Test case for a non-existent disk
    # print("\nDetails for /dev/nonexistentdisk:")
    # print(disk_manager.get_disk_details("/dev/nonexistentdisk"))
