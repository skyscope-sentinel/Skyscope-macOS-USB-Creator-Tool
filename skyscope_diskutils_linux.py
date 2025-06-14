import subprocess
import json

# This Utils class is a stub for skyscope_diskutils_linux.py to be self-contained if used independently.
# In the main tool, CatalogManager will use the Utils instance from macos_usb_tool.py.
class _DiskUtilsStub:
    def cprint(self, text, color=None, **kwargs):
        if color == "red":
            print(f"ERROR (DiskUtils): {text}")
        elif color == "yellow":
            print(f"WARNING (DiskUtils): {text}")
        else:
            print(f"INFO (DiskUtils): {text}")

class Disk:
    def __init__(self, utils_instance=None):
        self.u = utils_instance if utils_instance else _DiskUtilsStub()
        self.disks = {}
        self.update()

    def update(self):
        self.disks = {}
        try:
            cmd = ["lsblk", "-J", "-b", "-o", "NAME,SIZE,MODEL,VENDOR,TYPE,RM,RO,TRAN,PATH,MOUNTPOINT,PKNAME,FSTYPE,LABEL,PARTLABEL"]
            process_result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(process_result.stdout)

            if 'blockdevices' not in data:
                self.u.cprint("Key 'blockdevices' not found in lsblk output.", color="red")
                return

            for device in data['blockdevices']:
                if device.get('type') == 'disk':
                    is_removable = device.get('rm', False)
                    disk_path = device.get('path', device.get('name'))
                    if not disk_path: continue

                    self.disks[disk_path] = {
                        'name': device.get('name'),
                        'path': disk_path,
                        'size': device.get('size'), # In bytes
                        'model': device.get('model', 'N/A'),
                        'vendor': device.get('vendor', 'N/A'),
                        'type': device.get('type'), # Should be 'disk'
                        'rm': is_removable,         # Boolean for removable
                        'ro': device.get('ro', False), # Boolean for read-only
                        'tran': device.get('tran', 'N/A'), # Transport type (usb, sata, etc.)
                        'mountpoint': device.get('mountpoint'), # Mountpoint of the disk itself (rare)
                        'pkname': device.get('pkname'),
                        'fstype': device.get('fstype'),
                        'label': device.get('label'),
                        'partlabel': device.get('partlabel'),
                        'children': device.get('children', []) # Partitions
                    }
        except subprocess.CalledProcessError as e:
            self.u.cprint(f"Executing lsblk failed: {e}\nStderr: {e.stderr}", color="red")
            self.disks = {}
        except FileNotFoundError:
            self.u.cprint("The 'lsblk' command was not found. Please ensure it is installed and in your PATH.", color="red")
            self.disks = {}
        except json.JSONDecodeError as e:
            self.u.cprint(f"Failed to parse lsblk JSON output: {e}", color="red")
            self.disks = {}
        except Exception as e:
            self.u.cprint(f"An unexpected error occurred while updating disk list: {e}", color="red")
            self.disks = {}

    def get_filtered_disks(self, show_all_disks=False, require_usb_transport=True):
        """
        Returns a list of disk device dictionaries, filtered for suitability.
        By default, filters for removable USB drives.
        """
        filtered_disk_info_list = []
        for path, info in self.disks.items():
            # Basic filter: must be a disk, must not be read-only (unless show_all includes RO)
            if info['type'] != 'disk':
                continue
            # if info.get('ro') and not show_all_disks: # Skip read-only unless showing all
            #     continue

            if show_all_disks:
                filtered_disk_info_list.append(info)
            else:
                is_usb = (info.get('tran', '').lower() == 'usb')
                if info.get('rm'): # Primarily select based on removable flag
                    if require_usb_transport:
                        if is_usb:
                            filtered_disk_info_list.append(info)
                    else: # Add removable disk even if not USB (e.g. SD cards)
                        filtered_disk_info_list.append(info)
                elif is_usb: # Also consider non-removable if it's explicitly USB (e.g. some external HDDs)
                     # This could be a toggle: "include non-removable USBs"
                     # For now, if require_usb_transport is True, it must be USB.
                     # If require_usb_transport is False, any rm=True is fine.
                     # This means non-removable USBs are only included if show_all_disks=True
                     pass

        # Sort by path for consistent ordering
        filtered_disk_info_list.sort(key=lambda x: x.get('path', ''))
        return filtered_disk_info_list

    def get_disk_details(self, disk_path):
        return self.disks.get(disk_path)

if __name__ == "__main__":
    # This allows testing skyscope_diskutils_linux.py independently
    u_stub = _DiskUtilsStub()
    disk_manager = Disk(utils_instance=u_stub)

    u_stub.cprint("\n--- All Disks Found by lsblk ---", "green")
    if not disk_manager.disks:
        u_stub.cprint("No disks found or an error occurred.", "yellow")
    else:
        for path, details in disk_manager.disks.items():
            size_gb = details.get('size', 0) / (1024**3) if details.get('size') else 0
            u_stub.cprint(f"  Path: {path}, Type: {details['type']}, RM: {details['rm']}, RO: {details['ro']}, Tran: {details['tran']}, Size: {size_gb:.2f}GB, Model: {details['model']}", "green")

    u_stub.cprint("\n--- Filtered Removable USB Disks (require_usb_transport=True) ---", "green")
    removable_usb_disks = disk_manager.get_filtered_disks(require_usb_transport=True)
    if not removable_usb_disks:
        u_stub.cprint("No removable USB disks found.", "yellow")
    else:
        for details in removable_usb_disks:
            size_gb = details.get('size', 0) / (1024**3) if details.get('size') else 0
            u_stub.cprint(f"  Path: {details['path']}, Size: {size_gb:.2f}GB, Model: {details['model']}", "green")

    u_stub.cprint("\n--- Filtered Removable Disks (any transport, require_usb_transport=False) ---", "green")
    removable_any_disks = disk_manager.get_filtered_disks(require_usb_transport=False)
    if not removable_any_disks:
        u_stub.cprint("No removable disks of any transport type found.", "yellow")
    else:
        for details in removable_any_disks:
            size_gb = details.get('size', 0) / (1024**3) if details.get('size') else 0
            u_stub.cprint(f"  Path: {details['path']}, Tran: {details['tran']}, Size: {size_gb:.2f}GB, Model: {details['model']}", "green")

    u_stub.cprint("\n--- All Disks (type='disk', show_all_disks=True) ---", "green")
    all_disks = disk_manager.get_filtered_disks(show_all_disks=True)
    if not all_disks:
        u_stub.cprint("No disks of type 'disk' found.", "yellow")
    else:
        for details in all_disks:
            size_gb = details.get('size', 0) / (1024**3) if details.get('size') else 0
            u_stub.cprint(f"  Path: {details['path']}, RM: {details['rm']}, Tran: {details['tran']}, Size: {size_gb:.2f}GB, Model: {details['model']}", "green")

```

Now, I'll modify `macos_usb_tool.py`.
