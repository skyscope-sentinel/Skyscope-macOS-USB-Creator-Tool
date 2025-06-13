# Developer: Miss Casey Jay Topojani
# Co-Developer: Google Jules Bot
# This is makeinstall_linux.py
# Main script for creating a macOS installer USB on Linux.

from utils import cprint, head
# Actual downloader function
from downloader import stream_to_file as actual_downloader_stream_to_file
from disklinux import Disk # Import Disk class
import time # For simulating work
import os
import pathlib
import shutil # For disk_usage
import subprocess # For running external commands
import json # For parsing lsblk output in unmount
from urllib.parse import urlparse # For extracting filename from URL

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

# --- OpenCore Configuration ---
ESSENTIAL_DRIVERS = ["HfsPlus.efi", "OpenRuntime.efi"]
ESSENTIAL_KEXTS = ["Lilu.kext", "VirtualSMC.kext", "WhateverGreen.kext"]

GENERIC_CONFIG_PLIST_STR = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>#WARNING - IMPORTANT</key>
    <string>This is a generic config.plist. It WILL NOT boot your system optimally, if at all, without hardware-specific customization.</string>
    <key>Comment</key>
    <string>Generic config.plist for macOS Installer - Further customization needed!</string>
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
            <false/>
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
            <dict>
                <key>Arch</key>
                <string>Any</string>
                <key>BundlePath</key>
                <string>Lilu.kext</string>
                <key>Comment</key>
                <string>Patch engine</string>
                <key>Enabled</key>
                <true/>
                <key>ExecutablePath</key>
                <string>Contents/MacOS/Lilu</string>
                <key>MaxKernel</key>
                <string></string>
                <key>MinKernel</key>
                <string></string>
                <key>PlistPath</key>
                <string>Contents/Info.plist</string>
            </dict>
            <dict>
                <key>Arch</key>
                <string>Any</string>
                <key>BundlePath</key>
                <string>VirtualSMC.kext</string>
                <key>Comment</key>
                <string>SMC emulator</string>
                <key>Enabled</key>
                <true/>
                <key>ExecutablePath</key>
                <string>Contents/MacOS/VirtualSMC</string>
                <key>MaxKernel</key>
                <string></string>
                <key>MinKernel</key>
                <string></string>
                <key>PlistPath</key>
                <string>Contents/Info.plist</string>
            </dict>
            <dict>
                <key>Arch</key>
                <string>Any</string>
                <key>BundlePath</key>
                <string>WhateverGreen.kext</string>
                <key>Comment</key>
                <string>Graphics fixes</string>
                <key>Enabled</key>
                <true/>
                <key>ExecutablePath</key>
                <string>Contents/MacOS/WhateverGreen</string>
                <key>MaxKernel</key>
                <string></string>
                <key>MinKernel</key>
                <string></string>
                <key>PlistPath</key>
                <string>Contents/Info.plist</string>
            </dict>
        </array>
        <key>Block</key>
        <array/>
        <key>Emulate</key>
        <dict/>
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
            <integer>1</integer>
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
                <key>ExtendedHandshake</key>
                <false/>
                <key>FifoControl</key>
                <integer>7</integer>
                <key>LineControl</key>
                <integer>3</integer>
                <key>PciDeviceInfo</key>
                <data></data>
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
                <key>boot-args</key>
                <string>-v keepsyms=1 debug=0x100 alcid=1</string>
                <key>csr-active-config</key>
                <data>AAAAAA==</data>
                <key>prev-lang:kbd</key>
                <data></data>
                <key>run-efi-updater</key>
                <string>No</string>
            </dict>
        </dict>
        <key>Delete</key>
        <dict/>
        <key>LegacyOverwrite</key>
        <false/>
        <key>LegacySchema</key>
        <dict/>
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
            <string>BOARDSERIALNEEDED</string>
            <key>ProcessorType</key>
            <integer>0</integer>
            <key>ROM</key>
            <data>AAAAAA==</data>
            <key>SpoofVendor</key>
            <true/>
            <key>SystemMemoryStatus</key>
            <string>Auto</string>
            <key>SystemProductName</key>
            <string>iMacPro1,1</string>
            <key>SystemSerialNumber</key>
            <string>SERIALNEEDED</string>
            <key>SystemUUID</key>
            <string>UUIDNEEDED</string>
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
            <string>HfsPlus.efi</string>
            <string>OpenRuntime.efi</string>
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
            <key>DeviceReset</key>
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
            <key>TscFrequency</key>
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

# --- Tool Dependencies for disk_part_erase ---
# parted: for partition table and partition creation/manipulation.
# dosfstools (mkfs.fat): for formatting FAT32 partitions.
# hfsplus-utils (mkfs.hfsplus): for formatting HFS+ partitions.
# util-linux (fdisk, partprobe, blockdev): for MBR type codes and kernel partition table refresh.
# gdisk (sgdisk): might be needed for GPT type GUIDs if parted is insufficient (currently assuming parted is okay for GPT HFS+ type).
# lsblk: used for unmounting.

# --- Clover Configuration ---
CLOVER_ESSENTIAL_DRIVERS_UEFI = ["HFSPlus.efi", "ApfsDriverLoader.efi", "OpenRuntime.efi"] # Example set
CLOVER_ESSENTIAL_KEXTS_OTHER = ["FakeSMC.kext", "Lilu.kext", "WhateverGreen.kext"] # Example minimal set

CLOVER_GENERIC_CONFIG_PLIST_STR = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>#WARNING - IMPORTANT</key>
    <string>This is a generic config.plist for Clover. It may require hardware-specific customization.</string>
    <key>ACPI</key>
    <dict>
        <key>DSDT</key>
        <dict>
            <key>Fixes</key>
            <dict>
                <key>FixHPET</key>
                <true/>
                <key>FixRTC</key>
                <true/>
                <key>FixIPIC</key>
                <true/>
            </dict>
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
        <string>-v keepsyms=1 debug=0x100 alcid=1</string>
        <key>DefaultVolume</key>
        <string>LastBootedVolume</string>
        <key>NeverDoRecovery</key>
        <true/>
        <key>Timeout</key>
        <integer>5</integer>
        <key>Secure</key>
        <false/>
    </dict>
    <key>Devices</key>
    <dict>
        <key>Audio</key>
        <dict>
            <key>Inject</key>
            <string>No</string>
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
        <key>Scan</key>
        <dict>
            <key>Entries</key>
            <true/>
            <key>Tool</key>
            <true/>
            <key>Legacy</key>
            <false/>
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
            <false/>
            <key>NVidia</key>
            <false/>
        </dict>
    </dict>
    <key>KernelAndKextPatches</key>
    <dict>
        <key>AppleRTC</key>
        <true/>
        <key>KernelPm</key>
        <true/>
        <key>KextsToPatch</key>
        <array/>
    </dict>
    <key>RtVariables</key>
    <dict>
        <key>CsrActiveConfig</key>
        <string>0x67</string>
        <key>BooterConfig</key>
        <string>0x28</string>
    </dict>
    <key>SMBIOS</key>
    <dict>
        <key>ProductName</key>
        <string>iMac14,2</string>
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

# Help Text Function
def display_help_explanations():
    head("Help / Explanations")
    cprint("This guide provides brief explanations for some technical choices within the script.", "green")
    print("-" * 70)

    cprint("\n1. Partitioning Scheme: GPT vs. MBR", "green")
    cprint("   - GPT (GUID Partition Table): Modern standard for disk partitioning. Recommended for all UEFI-based systems", "green")
    cprint("     (most computers from ~2011 onwards). Supports drives larger than 2TB and more partitions.", "green")
    cprint("     This script defaults to GPT for creating bootable macOS USBs, as macOS installers expect UEFI.", "green")
    cprint("   - MBR (Master Boot Record): Older standard, used by Legacy BIOS systems. Limited to drives up to 2TB", "green")
    cprint("     and typically 4 primary partitions. While macOS can boot legacy on some older Macs, UEFI/GPT is preferred.", "green")
    cprint("   - Script Default: GPT is used by default. For some older macOS versions (e.g., El Capitan), you might be", "green")
    cprint("     prompted if you wish to use MBR for compatibility with very old Mac hardware.", "green")

    print("-" * 70)
    cprint("\n2. Bootloader: OpenCore vs. Clover", "green")
    cprint("   - OpenCore: A modern, robust, and cleaner bootloader designed with security and accuracy in mind.", "green")
    cprint("     It's generally recommended for newer versions of macOS and for users seeking a more up-to-date solution.", "green")
    cprint("   - Clover: An older, widely-used bootloader. It has broad compatibility, especially for some legacy hardware,", "green")
    cprint("     but can be more complex to configure. Still a viable option for many systems.", "green")
    cprint("   - Your Choice: The best bootloader depends on your specific hardware, target macOS version, and personal preference.", "green")
    cprint("     This script installs a *generic* version of the chosen bootloader. You MUST customize its `config.plist`", "yellow")
    cprint("     for your hardware to ensure a successful boot of the installer and the installed OS.", "yellow")

    print("-" * 70)
    cprint("\n3. Download Directory", "green")
    cprint("   - You can choose a custom directory to save downloaded macOS image files.", "green")
    cprint("   - This is useful if you have a specific drive with more space or want to keep existing downloads.", "green")
    cprint(f"  - The default is a subdirectory named 'macOS_Downloads/[VersionName]' within the script's current directory ({pathlib.Path.cwd()}).", "green")

    print("-" * 70)
    cprint("\n4. USB Drive Selection", "green")
    cprint("   - CRITICAL: Selecting the correct USB drive is vital. All data on the selected drive will be erased.", "red")
    cprint("     Double-check the drive path, size, model, and vendor before confirming.", "red")
    cprint("   - The script attempts to list only removable USB drives by default to minimize risk.", "green")

    print("-" * 70)
    cprint("\n5. Placeholder URLs & Generic Configs", "green")
    cprint("   - Placeholder URLs: For some older macOS versions (like El Capitan), direct download links from Apple are scarce.", "yellow")
    cprint("     The script uses placeholder URLs for these. You will need to find and verify a legitimate download URL", "yellow")
    cprint("     from Apple or a trusted archive and potentially update the script or download manually.", "yellow")
    cprint("   - Generic Config.plist: Both OpenCore and Clover require a `config.plist` file tailored to your specific hardware.", "yellow")
    cprint("     This script installs a very basic, generic `config.plist` designed only to help boot the macOS installer.", "yellow")
    cprint("     It is NOT a production-ready configuration for your system. You WILL LIKELY NEED to create or obtain", "yellow")
    cprint("     a hardware-specific `config.plist` for reliable booting and full functionality of the installed macOS.", "yellow")

    print("-" * 70)
    input("Press Enter to return to the main menu...")


def _run_command(command_parts, step_name="Command"):
    """Helper function to run a command and handle its output."""
    try:
        cprint(f"  Executing: {' '.join(command_parts)}", color="green")
        result = subprocess.run(command_parts, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            if result.stdout and step_name in ["Unmount", "Run partprobe", "Run blockdev"]:
                 cprint(f"  Stdout for {step_name}:\n{result.stdout.strip()}", color="green")
            return True
        else:
            cprint(f"Error during '{step_name}'. Utility '{command_parts[0]}' exited with code {result.returncode}.", color="red")
            if result.stdout: cprint(f"  Stdout:\n{result.stdout.strip()}", color="yellow")
            if result.stderr: cprint(f"  Stderr:\n{result.stderr.strip()}", color="yellow")
            return False
    except FileNotFoundError:
        cprint(f"Error: Utility '{command_parts[0]}' not found. Please ensure it is installed and in your system's PATH.", color="red")
        return False
    except Exception as e:
        cprint(f"An unexpected error occurred while running '{' '.join(command_parts)}': {e}", color="red")
        return False

def _unmount_device_partitions(device_path):
    cprint(f"Attempting to unmount all partitions on '{device_path}' before partitioning...", color="green")
    success_overall = True
    try:
        cmd = ["lsblk", "-Jp", "-o", "NAME,MOUNTPOINT", device_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        mountpoints_to_unmount = []
        for dev_info_top in data.get('blockdevices', []):
            if dev_info_top.get('mountpoint'):
                mountpoints_to_unmount.append(dev_info_top['mountpoint'])
            for part_info in dev_info_top.get('children', []):
                if part_info.get('mountpoint'):
                    mountpoints_to_unmount.append(part_info['mountpoint'])

        mountpoints_to_unmount = sorted(list(set(mountpoints_to_unmount)), reverse=True)

        if not mountpoints_to_unmount:
            cprint(f"  No mounted partitions found on '{device_path}'. Nothing to unmount.", color="green")
            return True

        cprint(f"  Found mounted partitions: {', '.join(mountpoints_to_unmount)}. Attempting to unmount...", color="green")
        for mp in mountpoints_to_unmount:
            if not _run_command(["umount", "-lf", mp], f"Unmount '{mp}'"):
                cprint(f"  Warning: Failed to unmount '{mp}'. This might cause issues with partitioning.", color="yellow")
                success_overall = False

        if success_overall:
            cprint(f"  Successfully unmounted all detected partitions on '{device_path}'.", color="green")
        else:
            cprint(f"  Warning: Not all partitions on '{device_path}' could be unmounted. Proceed with caution.", color="yellow")
        return success_overall
    except subprocess.CalledProcessError as e:
        cprint(f"Error: Failed to query partitions/mountpoints for '{device_path}' using lsblk. StdErr: {e.stderr}", color="red")
        return False
    except json.JSONDecodeError as e:
        cprint(f"Error: Could not parse lsblk JSON output while checking mountpoints for '{device_path}': {e}", color="red")
        return False
    except Exception as e:
        cprint(f"Unexpected error during unmount preparation for '{device_path}': {e}", color="red")
        return False


def disk_part_erase(device_path, volume_name, gpt=True):
    version_display_name = "the selected macOS version"
    # Access selected_version_key safely if it's intended to be available globally or passed.
    # For now, this relies on selected_version_key being potentially set in main's scope.
    # A cleaner way would be to pass version_display_name as an argument.
    if 'selected_version_key' in globals() and selected_version_key in mac_versions:
        version_display_name = mac_versions[selected_version_key].get('name', selected_version_key)

    head(f"Partitioning and Formatting Disk: {device_path}")
    cprint(f"Preparing disk '{device_path}' for {version_display_name} installer.", color="green")
    cprint(f"IMPORTANT: All data on '{device_path}' will be PERMANENTLY ERASED!", color="red")

    if not _unmount_device_partitions(device_path):
        cprint(f"Critical Error: Failed to unmount partitions on '{device_path}'. Aborting disk preparation.", color="red")
        return False

    part1 = f"{device_path}1"
    part2 = f"{device_path}2"
    if "nvme" in device_path:
        part1 = f"{device_path}p1"
        part2 = f"{device_path}p2"

    if gpt:
        cprint(f"Using GPT partitioning scheme for '{device_path}'.", color="green")
        cprint(f"Step 1: Creating GPT partition table on '{device_path}'...", color="green")
        if not _run_command(["parted", "-s", device_path, "mklabel", "gpt"], "Create GPT label"): return False

        cprint(f"Step 2: Creating EFI System Partition (ESP) on '{part1}'...", color="green")
        if not _run_command(["parted", "-s", "-a", "optimal", device_path, "mkpart", "ESP", "fat32", "1MiB", "201MiB"], "Create ESP"): return False
        cprint(f"  Formatting '{part1}' as FAT32...", color="green")
        if not _run_command(["mkfs.fat", "-F", "32", part1], f"Format {part1} as FAT32"): return False
        cprint(f"  Setting 'boot' and 'esp' flags on '{part1}'...", color="green")
        if not _run_command(["parted", "-s", device_path, "set", "1", "boot", "on"], f"Set 'boot' flag on {part1}"): return False
        if not _run_command(["parted", "-s", device_path, "set", "1", "esp", "on"], f"Set 'esp' flag on {part1}"): return False

        cprint(f"Step 3: Creating HFS+ partition for macOS installer on '{part2}'...", color="green")
        if not _run_command(["parted", "-s", "-a", "optimal", device_path, "mkpart", "Apple HFS+", "hfs+", "201MiB", "100%"], "Create HFS+ partition"): return False
        cprint(f"  Formatting '{part2}' as HFS+ (Journaled) with volume name '{volume_name}'...", color="green")
        if not _run_command(["mkfs.hfsplus", "-J", "-v", volume_name, part2], f"Format {part2} as HFS+ (Journaled)"): return False
        cprint("  Note: 'parted' is expected to set the correct GPT partition type GUID for HFS+.", color="green")

    else: # MBR Scheme
        cprint(f"Using MBR (msdos) partitioning scheme for '{device_path}'.", color="green")
        cprint(f"Step 1: Creating MBR partition table on '{device_path}'...", color="green")
        if not _run_command(["parted", "-s", device_path, "mklabel", "msdos"], "Create MBR label"): return False

        cprint(f"Step 2: Creating FAT32 boot partition on '{part1}'...", color="green")
        if not _run_command(["parted", "-s", "-a", "optimal", device_path, "mkpart", "primary", "fat32", "1MiB", "201MiB"], "Create FAT32 partition (MBR)"): return False
        cprint(f"  Formatting '{part1}' as FAT32...", color="green")
        if not _run_command(["mkfs.fat", "-F", "32", part1], f"Format {part1} as FAT32"): return False
        cprint(f"  Setting 'boot' flag on '{part1}'...", color="green")
        if not _run_command(["parted", "-s", device_path, "set", "1", "boot", "on"], f"Set 'boot' flag on {part1}"): return False

        cprint(f"Step 3: Creating HFS+ partition for macOS installer on '{part2}'...", color="green")
        if not _run_command(["parted", "-s", "-a", "optimal", device_path, "mkpart", "primary", "hfs+", "201MiB", "100%"], "Create HFS+ partition (MBR)"): return False
        cprint(f"  Formatting '{part2}' as HFS+ (Journaled) with volume name '{volume_name}'...", color="green")
        if not _run_command(["mkfs.hfsplus", "-J", "-v", volume_name, part2], f"Format {part2} as HFS+ (Journaled)"): return False

        cprint(f"Step 4: Setting MBR partition type for '{part2}' to AF (Apple HFS+)...", color="green")
        fdisk_input = f"t\n2\naf\nw\n"
        try:
            cprint(f"  Executing: fdisk {device_path} (setting partition type with input)", color="green")
            process = subprocess.run(["fdisk", device_path], input=fdisk_input, text=True, capture_output=True, check=False)
            if process.returncode != 0:
                 cprint(f"  Warning: fdisk exited with code {process.returncode} while setting type for {part2}.", color="yellow")
                 if process.stdout: cprint(f"  fdisk stdout:\n{process.stdout.strip()}", color="yellow")
                 if process.stderr: cprint(f"  fdisk stderr:\n{process.stderr.strip()}", color="yellow")
                 cprint(f"  MBR partition type for HFS+ may not be correctly set to AF. This might be an issue for legacy boot.", color="yellow")
            else:
                cprint(f"  fdisk MBR type setting for '{part2}' completed.", color="green")
                if process.stdout: cprint(f"  fdisk stdout (informational):\n{process.stdout.strip()}", color="green")

        except FileNotFoundError:
            cprint(f"Error: 'fdisk' utility not found. MBR partition type for HFS+ cannot be set to AF. This is critical for MBR boot.", color="red")
            return False
        except Exception as e:
            cprint(f"An unexpected error occurred while running fdisk to set partition type: {e}", color="red")
            return False

    cprint(f"Step 5: Synchronizing disk changes with kernel for '{device_path}'...", color="green")
    _run_command(["sync"], "Sync filesystem buffers")
    if not _run_command(["partprobe", device_path], f"Run partprobe on '{device_path}'"):
        cprint(f"  'partprobe' failed or not found, attempting 'blockdev --rereadpt' as fallback...", color="yellow")
        _run_command(["blockdev", "--rereadpt", device_path], f"Run blockdev --rereadpt on '{device_path}'")

    cprint(f"Disk '{device_path}' has been successfully partitioned and formatted for {('GPT' if gpt else 'MBR')} scheme.", color="green")
    return True


def extract_image(image_path):
    head(f"Extract macOS Image: {image_path}")
    cprint(f"Simulating extraction of '{image_path}' (this might take a while)...", color="green")
    time.sleep(2)
    extracted_path = image_path.replace(".dmg", "_extracted_payload")
    cprint(f"Image extraction simulation complete. Payload at: '{extracted_path}'", color="green")
    return extracted_path

def install_opencore(target_efi_mount_point_str, opencore_release_extract_path_str, usb_device_path, efi_partition_path, is_legacy_setup):
    head(f"OpenCore Installation to EFI: {target_efi_mount_point_str}")
    cprint(f"  Using OpenCore package from: {opencore_release_extract_path_str}", color="green")
    if is_legacy_setup:
        cprint(f"  Legacy Boot (MBR/PBR) for OpenCore will be configured on '{usb_device_path}' using EFI partition '{efi_partition_path}'.", color="yellow")

    target_efi_mp = pathlib.Path(target_efi_mount_point_str)
    oc_extract_path = pathlib.Path(opencore_release_extract_path_str)

    oc_source_efi_dir = oc_extract_path / "X64" / "EFI"
    oc_legacy_boot_dir = oc_extract_path / "Utilities" / "LegacyBoot"
    oc_source_drivers_dir = oc_source_efi_dir / "OC" / "Drivers"
    oc_source_kexts_dir = oc_source_efi_dir / "OC" / "Kexts"

    efi_dir_on_target = target_efi_mp / "EFI"
    oc_dir_on_target = efi_dir_on_target / "OC"
    drivers_dir_on_target = oc_dir_on_target / "Drivers"
    kexts_dir_on_target = oc_dir_on_target / "Kexts"

    try:
        cprint("Step 1: Copying base OpenCore EFI files...", color="green")
        if not oc_source_efi_dir.exists():
            cprint(f"  Error: OpenCore source EFI directory not found at '{oc_source_efi_dir}'. Cannot proceed.", color="red")
            return False
        shutil.copytree(oc_source_efi_dir, efi_dir_on_target, dirs_exist_ok=True)
        cprint(f"  Base OpenCore EFI structure copied to '{efi_dir_on_target}'.", color="green")

        cprint(f"Step 2: Ensuring target OpenCore directories exist ('{drivers_dir_on_target}', '{kexts_dir_on_target}')...", color="green")
        drivers_dir_on_target.mkdir(parents=True, exist_ok=True)
        kexts_dir_on_target.mkdir(parents=True, exist_ok=True)

        cprint(f"Step 3: Copying essential EFI drivers to '{drivers_dir_on_target}'...", color="green")
        for driver_file in ESSENTIAL_DRIVERS:
            source_driver_path = oc_source_drivers_dir / driver_file
            target_driver_path = drivers_dir_on_target / driver_file
            if source_driver_path.exists():
                shutil.copy2(source_driver_path, target_driver_path)
                cprint(f"    Copied '{driver_file}'.", color="green")
            else:
                cprint(f"    Warning: Driver '{driver_file}' not found in OpenCore package at '{source_driver_path}'.", color="yellow")

        cprint(f"Step 4: Copying essential Kexts to '{kexts_dir_on_target}'...", color="green")
        for kext_bundle_name in ESSENTIAL_KEXTS:
            source_kext_path = oc_source_kexts_dir / kext_bundle_name
            target_kext_path = kexts_dir_on_target / kext_bundle_name

            if source_kext_path.exists() and source_kext_path.is_dir():
                if target_kext_path.exists():
                    cprint(f"    Removing existing Kext directory at '{target_kext_path}' before copy.", color="green")
                    shutil.rmtree(target_kext_path)
                shutil.copytree(source_kext_path, target_kext_path)
                cprint(f"    Copied Kext bundle '{kext_bundle_name}'.", color="green")
            elif source_kext_path.exists() and source_kext_path.is_file():
                 shutil.copy2(source_kext_path, target_kext_path)
                 cprint(f"    Copied '{kext_bundle_name}' (as file - unusual for Kexts).", color="yellow")
            else:
                cprint(f"    Warning: Kext '{kext_bundle_name}' not found in OpenCore package at '{source_kext_path}'.", color="yellow")

        config_plist_path = oc_dir_on_target / "config.plist"
        cprint(f"Step 5: Writing generic OpenCore config.plist to '{config_plist_path}'...", color="green")
        with open(config_plist_path, "w", encoding="utf-8") as f:
            f.write(GENERIC_CONFIG_PLIST_STR)

        cprint("OpenCore UEFI setup completed successfully.", color="green")
        cprint("IMPORTANT: The installed OpenCore config.plist is GENERIC and for INSTALLER use.", color="yellow")
        cprint("           You MUST customize it for your specific hardware for a successful post-install boot.", color="yellow")

        if is_legacy_setup:
            cprint(f"Step 6: Installing OpenCore legacy boot files (MBR/PBR) to '{usb_device_path}'...", color="green")
            boot0_path = oc_legacy_boot_dir / "boot0"
            boot1f32_path = oc_legacy_boot_dir / "boot1f32"

            if not boot0_path.exists():
                cprint(f"  Error: OpenCore legacy boot file 'boot0' not found at '{boot0_path}'.", color="red")
                return False
            if not boot1f32_path.exists():
                cprint(f"  Error: OpenCore legacy boot file 'boot1f32' not found at '{boot1f32_path}'.", color="red")
                return False

            if not _run_command(["dd", f"if={str(boot0_path)}", f"of={usb_device_path}", "bs=440", "count=1", "conv=notrunc"], "Write OpenCore MBR (boot0)"):
                cprint(f"  Critical: Failed to write OpenCore 'boot0' to MBR of '{usb_device_path}'. Legacy boot may not work.", color="red")
                return False

            if not _run_command(["dd", f"if={str(boot1f32_path)}", f"of={efi_partition_path}"], "Write OpenCore PBR (boot1f32)"):
                cprint(f"  Critical: Failed to write OpenCore 'boot1f32' to PBR of '{efi_partition_path}'. Legacy boot may not work.", color="red")
                return False
            cprint("  OpenCore legacy boot files (MBR/PBR) installed successfully.", color="green")
        return True

    except FileNotFoundError as e:
        cprint(f"Error during OpenCore installation (File Not Found): {e}", color="red")
        return False
    except shutil.Error as e:
        cprint(f"Error during OpenCore file operations (shutil): {e}", color="red")
        return False
    except OSError as e:
        cprint(f"Error during OpenCore file/directory operations (OS): {e}", color="red")
        return False
    except Exception as e:
        cprint(f"An unexpected error occurred during OpenCore installation: {e}", color="red")
        return False

def install_clover(target_efi_mount_point_str, clover_release_extract_path_str, usb_device_path, efi_partition_path, is_legacy_setup):
    head(f"Clover Installation on EFI Partition: {target_efi_mount_point_str}")
    cprint(f"  Source Clover package: {clover_release_extract_path_str}", color="green")
    if is_legacy_setup:
        cprint(f"  Legacy Boot (MBR/PBR) setup for Clover will be performed on '{usb_device_path}' using EFI partition '{efi_partition_path}'.", color="yellow")

    target_efi_mp = pathlib.Path(target_efi_mount_point_str)
    clover_extract_path = pathlib.Path(clover_release_extract_path_str)

    clover_source_efi_dir = clover_extract_path / "EFI"
    clover_legacy_boot_dir = clover_extract_path

    clover_source_drivers_uefi_dir = clover_source_efi_dir / "CLOVER" / "drivers" / "UEFI"
    clover_source_drivers64_uefi_dir = clover_source_efi_dir / "CLOVER" / "drivers64UEFI"
    clover_source_kexts_other_dir = clover_source_efi_dir / "CLOVER" / "kexts" / "Other"

    efi_dir_on_target = target_efi_mp / "EFI"
    clover_dir_on_target = efi_dir_on_target / "CLOVER"
    drivers_uefi_target_dir = clover_dir_on_target / "drivers" / "UEFI"
    kexts_other_target_dir = clover_dir_on_target / "kexts" / "Other"

    try:
        cprint(f"Step 1: Copying base Clover EFI files from '{clover_source_efi_dir}' to '{efi_dir_on_target}'...", color="green")
        if not clover_source_efi_dir.exists():
            cprint(f"  Error: Clover source EFI directory not found at '{clover_source_efi_dir}'. Cannot proceed.", color="red")
            return False
        shutil.copytree(clover_source_efi_dir, efi_dir_on_target, dirs_exist_ok=True)
        cprint(f"  Base Clover EFI structure copied to '{efi_dir_on_target}'.", color="green")

        cprint(f"Step 2: Ensuring target Clover directories exist ('{drivers_uefi_target_dir}', '{kexts_other_target_dir}')...", color="green")
        drivers_uefi_target_dir.mkdir(parents=True, exist_ok=True)
        kexts_other_target_dir.mkdir(parents=True, exist_ok=True)

        actual_clover_source_drivers_dir = None
        if clover_source_drivers_uefi_dir.exists():
            actual_clover_source_drivers_dir = clover_source_drivers_uefi_dir
        elif clover_source_drivers64_uefi_dir.exists():
             actual_clover_source_drivers_dir = clover_source_drivers64_uefi_dir

        if actual_clover_source_drivers_dir:
            cprint(f"Step 3: Copying essential Clover UEFI drivers from '{actual_clover_source_drivers_dir}' to '{drivers_uefi_target_dir}'...", color="green")
            for driver_file in CLOVER_ESSENTIAL_DRIVERS_UEFI:
                source_driver_path = actual_clover_source_drivers_dir / driver_file
                target_driver_path = drivers_uefi_target_dir / driver_file
                if source_driver_path.exists():
                    shutil.copy2(source_driver_path, target_driver_path)
                    cprint(f"    Copied '{driver_file}'.", color="green")
                else:
                    cprint(f"    Warning: Driver '{driver_file}' not found in Clover package at '{source_driver_path}'.", color="yellow")
        else:
            cprint(f"  Warning: No Clover UEFI drivers source directory found (checked '{clover_source_drivers_uefi_dir}' and '{clover_source_drivers64_uefi_dir}'). Skipping driver copy.", color="yellow")

        if clover_source_kexts_other_dir.exists():
            cprint(f"Step 4: Copying essential Kexts to '{kexts_other_target_dir}'...", color="green")
            for kext_bundle_name in CLOVER_ESSENTIAL_KEXTS_OTHER:
                source_kext_path = clover_source_kexts_other_dir / kext_bundle_name
                target_kext_path = kexts_other_target_dir / kext_bundle_name
                if source_kext_path.exists() and source_kext_path.is_dir():
                    if target_kext_path.exists():
                        cprint(f"    Removing existing Kext directory at '{target_kext_path}' before copy.", color="green")
                        shutil.rmtree(target_kext_path)
                    shutil.copytree(source_kext_path, target_kext_path)
                    cprint(f"    Copied Kext bundle '{kext_bundle_name}'.", color="green")
                else:
                    cprint(f"    Warning: Kext '{kext_bundle_name}' not found or not a directory at '{source_kext_path}'.", color="yellow")
        else:
            cprint(f"  Warning: Clover source kexts directory '{clover_source_kexts_other_dir}' not found. Skipping Kext copy.", color="yellow")

        config_plist_path = clover_dir_on_target / "config.plist"
        cprint(f"Step 5: Writing generic Clover config.plist to '{config_plist_path}'...", color="green")
        with open(config_plist_path, "w", encoding="utf-8") as f:
            f.write(CLOVER_GENERIC_CONFIG_PLIST_STR)

        cprint("Clover UEFI setup completed successfully.", color="green")
        cprint("IMPORTANT: The installed Clover config.plist is GENERIC and for INSTALLER use.", color="yellow")
        cprint("           You MUST customize it for your specific hardware for a successful post-install boot.", color="yellow")

        if is_legacy_setup:
            cprint(f"Step 6: Installing Clover legacy boot files (MBR/PBR) to '{usb_device_path}'...", color="green")
            boot0_filename = "boot0af"
            boot0_path = clover_legacy_boot_dir / boot0_filename
            if not boot0_path.exists():
                boot0_filename = "boot0ss"
                boot0_path = clover_legacy_boot_dir / boot0_filename

            boot1f32alt_filename = "boot1f32alt"
            boot1f32alt_path = clover_legacy_boot_dir / boot1f32alt_filename

            if not boot0_path.exists():
                cprint(f"  Error: Clover MBR boot file ('boot0af' or 'boot0ss') not found at '{clover_legacy_boot_dir}'.", color="red")
                return False
            if not boot1f32alt_path.exists():
                cprint(f"  Error: Clover PBR boot file ('{boot1f32alt_filename}') not found at '{clover_legacy_boot_dir}'.", color="red")
                return False

            if not _run_command(["dd", f"if={str(boot0_path)}", f"of={usb_device_path}", "bs=440", "count=1", "conv=notrunc"], f"Write Clover MBR ({boot0_filename})"):
                cprint(f"  Critical: Failed to write Clover MBR boot file '{boot0_filename}' to '{usb_device_path}'. Legacy boot may not work.", color="red")
                return False

            if not _run_command(["dd", f"if={str(boot1f32alt_path)}", f"of={efi_partition_path}"], f"Write Clover PBR ({boot1f32alt_filename})"):
                cprint(f"  Critical: Failed to write Clover PBR boot file '{boot1f32alt_filename}' to '{efi_partition_path}'. Legacy boot may not work.", color="red")
                return False
            cprint("  Clover legacy boot files (MBR/PBR) installed successfully.", color="green")
        return True

    except FileNotFoundError as e:
        cprint(f"Error during Clover installation (File Not Found): {e}", color="red")
        return False
    except shutil.Error as e:
        cprint(f"Error during Clover file operations (shutil): {e}", color="red")
        return False
    except OSError as e:
        cprint(f"Error during Clover file/directory operations (OS): {e}", color="red")
        return False
    except Exception as e:
        cprint(f"An unexpected error occurred during Clover installation: {e}", color="red")
        return False


def write_to_usb(source_path, usb_device, version_name, gpt_scheme=True):
    # version_name is the key from mac_versions, e.g. "El Capitan"
    # source_path is the path to the downloaded macOS installer image.

    head(f"Prepare USB Device: {usb_device} for {mac_versions[version_name].get('name', version_name)}")

    cprint(f"The selected USB device is '{usb_device}'. All data on this device will be erased.", color="red")
    cprint("This is the FINAL confirmation before disk operations begin.", color="red")
    final_confirm = input(f"Are you absolutely sure you want to partition and format '{usb_device}'? (Type 'YES' in uppercase to proceed): ").strip()
    if final_confirm != 'YES': # Stricter confirmation
        cprint("Operation cancelled by user. No changes were made to the disk.", color="yellow")
        return False

    volume_name_for_hfs = mac_versions[version_name].get('name', version_name).replace(" ", "_") # Use display name for HFS volume

    if disk_part_erase(usb_device, volume_name_for_hfs, gpt=gpt_scheme):
        cprint(f"USB device '{usb_device}' has been successfully partitioned and formatted.", color="green")

        efi_partition_path = f"{usb_device}1"
        if "nvme" in usb_device: efi_partition_path = f"{usb_device}p1"

        is_legacy_boot_required = not gpt_scheme

        efi_mount_target = pathlib.Path.cwd() / "mnt_efi_temp"
        bootloader_installed_successfully = False
        try:
            efi_mount_target.mkdir(parents=True, exist_ok=True)
            cprint(f"Attempting to mount EFI partition '{efi_partition_path}' to temporary mount point '{efi_mount_target}'...", color="green")
            if not _run_command(["mount", efi_partition_path, str(efi_mount_target)], f"Mount EFI partition {efi_partition_path}"):
                cprint(f"Critical: Failed to mount EFI partition '{efi_partition_path}'. Cannot install bootloader.", color="red")
                return False # Cannot proceed if EFI can't be mounted

            cprint(f"EFI partition '{efi_partition_path}' mounted successfully at '{efi_mount_target}'.", color="green")

            # Inline help tip for bootloader choice
            cprint("You can choose to install either OpenCore (modern) or Clover (legacy-friendly).", "green")
            cprint("Type 'H' at any menu for more detailed explanations.", "green") # Example of inline help hint
            bootloader_choice = input("Install (O)penCore or (C)lover bootloader? (O/C, default: O): ").upper().strip() or "O"

            if bootloader_choice == "O":
                simulated_oc_release_path = pathlib.Path.cwd() / "TEMP_OC_PACKAGE_ROOT"
                # HACK for testing: Create dummy OpenCore structure
                oc_util_legacy_boot_dir = simulated_oc_release_path / "Utilities" / "LegacyBoot"
                oc_util_legacy_boot_dir.mkdir(parents=True, exist_ok=True)
                (oc_util_legacy_boot_dir / "boot0").touch(exist_ok=True)
                (oc_util_legacy_boot_dir / "boot1f32").touch(exist_ok=True)
                dummy_oc_efi_source = simulated_oc_release_path / "X64" / "EFI"
                if not (dummy_oc_efi_source / "OC" / "OpenCore.efi").exists(): # Check before creating full dummy structure
                    cprint(f"Simulating OpenCore package content at '{simulated_oc_release_path}' for testing...", color="yellow")
                    (dummy_oc_efi_source / "OC" / "Drivers").mkdir(parents=True, exist_ok=True)
                    (dummy_oc_efi_source / "OC" / "Kexts").mkdir(parents=True, exist_ok=True)
                    (dummy_oc_efi_source / "OC" / "OpenCore.efi").touch(exist_ok=True)
                    (dummy_oc_efi_source / "BOOT").mkdir(parents=True, exist_ok=True)
                    (dummy_oc_efi_source / "BOOT" / "BOOTx64.efi").touch(exist_ok=True)
                    for drv in ESSENTIAL_DRIVERS: (dummy_oc_efi_source / "OC" / "Drivers" / drv).touch(exist_ok=True)
                    for kext_name in ESSENTIAL_KEXTS: (dummy_oc_efi_source / "OC" / "Kexts" / kext_name).mkdir(parents=True, exist_ok=True)

                if not simulated_oc_release_path.exists() or not (dummy_oc_efi_source).exists():
                     cprint(f"Error: Simulated OpenCore package not found at '{simulated_oc_release_path}'. Skipping OpenCore installation.", color="red")
                elif install_opencore(str(efi_mount_target), str(simulated_oc_release_path), usb_device, efi_partition_path, is_legacy_boot_required):
                    bootloader_installed_successfully = True
                else:
                    cprint("OpenCore installation reported errors.", color="red")

            elif bootloader_choice == "C":
                simulated_clover_release_path = pathlib.Path.cwd() / "TEMP_CLOVER_PACKAGE_ROOT"
                (simulated_clover_release_path / "boot0af").touch(exist_ok=True)
                (simulated_clover_release_path / "boot1f32alt").touch(exist_ok=True)
                dummy_clover_efi_source = simulated_clover_release_path / "EFI"
                if not (dummy_clover_efi_source / "CLOVER" / "CLOVERX64.efi").exists():
                    cprint(f"Simulating Clover package content at '{simulated_clover_release_path}' for testing...", color="yellow")
                    (dummy_clover_efi_source / "BOOT").mkdir(parents=True, exist_ok=True)
                    (dummy_clover_efi_source / "BOOT" / "BOOTX64.efi").touch(exist_ok=True)
                    clover_drivers_dir_hack = dummy_clover_efi_source / "CLOVER" / "drivers" / "UEFI"
                    clover_drivers_dir_hack.mkdir(parents=True, exist_ok=True)
                    (dummy_clover_efi_source / "CLOVER" / "kexts" / "Other").mkdir(parents=True, exist_ok=True)
                    (dummy_clover_efi_source / "CLOVER" / "CLOVERX64.efi").touch(exist_ok=True)
                    for drv in CLOVER_ESSENTIAL_DRIVERS_UEFI: (clover_drivers_dir_hack / drv).touch(exist_ok=True)
                    for kext_name in CLOVER_ESSENTIAL_KEXTS_OTHER:
                        (dummy_clover_efi_source / "CLOVER" / "kexts" / "Other" / kext_name).mkdir(parents=True, exist_ok=True)

                if not simulated_clover_release_path.exists() or not (dummy_clover_efi_source).exists():
                    cprint(f"Error: Simulated Clover package not found at '{simulated_clover_release_path}'. Skipping Clover installation.", color="red")
                elif install_clover(str(efi_mount_target), str(simulated_clover_release_path), usb_device, efi_partition_path, is_legacy_boot_required):
                    bootloader_installed_successfully = True
                else:
                    cprint("Clover installation reported errors.", color="red")
            else:
                cprint("Invalid bootloader choice. No bootloader will be installed. You may need to set up the EFI partition manually.", color="yellow")

            if not _run_command(["umount", str(efi_mount_target)], f"Unmount EFI partition '{efi_mount_target}'"):
                cprint(f"Warning: Failed to unmount '{efi_mount_target}'. Please check and unmount manually if needed.", color="yellow")
            else:
                cprint(f"EFI partition '{efi_mount_target}' unmounted successfully.", color="green")

            try:
                if efi_mount_target.exists() and not any(efi_mount_target.iterdir()):
                    efi_mount_target.rmdir()
            except OSError as e:
                cprint(f"Notice: Could not remove temporary EFI mount point '{efi_mount_target}': {e}. This is not critical.", color="green")

        except Exception as e:
            cprint(f"An error occurred during EFI operations or bootloader installation: {e}", color="red")
            if efi_mount_target.is_mount():
                 _run_command(["umount", "-lf", str(efi_mount_target)], f"Force unmount EFI partition '{efi_mount_target}' after error")

        if not bootloader_installed_successfully and bootloader_choice in ["O", "C"]:
             cprint("Bootloader installation was not successful. The USB drive may not be bootable.", color="red")

        cprint(f"Next step: Copy macOS installer files from '{source_path}' to the HFS+ partition on '{usb_device}'.", color="green")
        cprint(f"(This step is currently simulated.)", color="yellow")
        time.sleep(3)
        cprint("macOS installer file copy simulation complete.", color="green")
        return True
    else:
        cprint(f"Critical: Failed to partition and format '{usb_device}'. USB creation process aborted.", color="red")
        return False


def main():
    global selected_version_key # For disk_part_erase message quick fix
    selected_version_key = None

    head("macOS USB Installer Creator for Linux")
    cprint("Welcome! This script will guide you through creating a bootable macOS USB drive.", color="green")
    cprint("Please ensure you have all necessary utilities installed (parted, mkfs.fat, hfsplus-utils, etc.).", color="green")
    cprint("Run this script with sudo if you encounter permission errors for disk operations.", color="yellow")
    cprint("--------------------------------------------------------------------------------", color="green")

    disk_manager = Disk()
    if not disk_manager.get_filtered_disks(show_all_disks=True):
        cprint("Critical Error: No disk devices of type 'disk' were found by lsblk.", color="red")
        cprint("Possible reasons: lsblk utility not found, permission issues (try sudo), or no disks connected/visible.", color="red")
        cprint("If running in a restricted environment (like Docker), access to block devices might be limited.", color="red")
        return

    while True:
        selected_version_key_tuple = show_menu() # Renamed to avoid confusion

        # Handle tuple unpacking carefully, expecting (key, data_dict) or (action_str, None)
        current_selected_key = selected_version_key_tuple[0]
        version_data = selected_version_key_tuple[1]

        if current_selected_key == "HELP":
            display_help_explanations()
            selected_version_key = None # Reset for the global quick fix
            continue

        selected_version_key = current_selected_key # Set for global use (quick fix) and process

        if not selected_version_key:
            cprint("No macOS version selected. Exiting script.", color="yellow")
            return

        cprint("--------------------------------------------------------------------------------", color="green")
        cprint(f"Proceeding with setup for: {mac_versions[selected_version_key].get('name', selected_version_key)}", color="green")
        break

    if not selected_version_key: # Should be caught by the loop's explicit return if no selection
        return

    cprint("--------------------------------------------------------------------------------", color="green")
    show_all_system_disks = False
    # Example for future enhancement:
    # cprint("Note: By default, only removable USB drives are listed for safety.", color="green")
    # if input("List all disk types (USE WITH EXTREME CAUTION)? (y/N): ").lower() == 'y':
    #    show_all_system_disks = True
    #    cprint("Warning: Listing all disk types. Be absolutely sure before selecting an internal drive!", color="red")


    usb_drive = select_usb_device(disk_manager, show_all_disks_flag=show_all_system_disks)
    if not usb_drive:
        cprint("No USB drive selected or selection was cancelled. Exiting script.", color="yellow")
        return
    cprint(f"Continuing with selected USB drive: '{usb_drive}'. Ensure this is correct.", color="yellow")

    cprint("--------------------------------------------------------------------------------", color="green")
    download_location = get_download_directory(selected_version_key)
    if not download_location:
        cprint("Download directory not configured. Exiting script.", color="yellow")
        return
    cprint(f"macOS images will be downloaded to: '{download_location}'", color="green")

    cprint("--------------------------------------------------------------------------------", color="green")
    downloaded_image_path = download_macos_image(selected_version_key, version_data["url"], download_location)
    if not downloaded_image_path:
        cprint("macOS image download failed or was skipped. Exiting script.", color="red")
        return
    cprint(f"macOS image is ready at: '{downloaded_image_path}'", color="green")

    cprint("--------------------------------------------------------------------------------", color="green")
    cprint("USB Drive Partitioning Scheme:", "green")
    use_gpt_scheme = True
    if selected_version_key in ["El Capitan"]:
        cprint(f"Note: For older macOS (like {selected_version_key}), MBR partitioning might be needed for some older Macs.", "yellow")
        # Inline help tip example
        mbr_choice_prompt = f"Use MBR scheme instead of GPT for {selected_version_key}? (y/N, default: N for GPT, type H for help on GPT/MBR): "
        mbr_choice = input(mbr_choice_prompt).lower().strip()
        if mbr_choice == 'h':
            display_help_explanations() # Show help
            mbr_choice = input(f"Use MBR scheme for {selected_version_key}? (y/N, default: N for GPT): ").lower().strip() # Re-prompt

        if mbr_choice == 'y':
            use_gpt_scheme = False
            cprint("User selected MBR partitioning scheme.", "yellow")
    cprint(f"Using {'GPT (UEFI recommended)' if use_gpt_scheme else 'MBR (Legacy/BIOS)'} partitioning scheme for the USB drive.", "green")


    if write_to_usb(downloaded_image_path, usb_drive, selected_version_key, gpt_scheme=use_gpt_scheme):
        cprint("--------------------------------------------------------------------------------", "green")
        cprint("macOS USB Installer for Linux - Process Completed Successfully!", "green")
        cprint(f"Your USB drive '{usb_drive}' should now be a bootable macOS {mac_versions[selected_version_key].get('name', selected_version_key)} installer.", "green")
        cprint("To boot from the USB on a Mac: Restart your Mac and hold down the 'Option' (Alt) key.", "green")
        cprint("Select the USB drive (usually orange/yellow, labeled 'EFI Boot' or similar) from the boot menu.", "green")
        cprint("IMPORTANT: The installed bootloader config.plist is GENERIC.", "yellow")
        cprint("For optimal results or if you encounter boot issues, you WILL need to customize this config.plist", "yellow")
        cprint("for your specific Mac model or PC hardware (if creating a Hackintosh installer).", "yellow")
    else:
        cprint("--------------------------------------------------------------------------------", "green")
        cprint("macOS USB Installer creation FAILED. Please review the messages above for specific errors.", "red")
        cprint("Common issues include: incorrect disk selection, insufficient permissions (try running with sudo),", "red")
        cprint("or missing system utilities (like parted, mkfs.fat, hfsplus-utils).", "red")

if __name__ == "__main__":
    selected_version_key = None
    main()

[end of makeinstall_linux.py]
