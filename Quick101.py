#!/usr/bin/env python3
"""

"""

import os
import sys
import json
import yaml
import ctypes
import subprocess
import threading
import time
import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum
import urllib.request
import urllib.error
import struct
import uuid
import ctypes.wintypes

# PyQt imports with fallback support
try:
    from PyQt6.QtWidgets import *
    from PyQt6.QtCore import *
    from PyQt6.QtGui import *
    from PyQt6.QtSvg import QSvgRenderer
    PyQt_Version = 6
except ImportError:
    try:
        from PyQt5.QtWidgets import *
        from PyQt5.QtCore import *
        from PyQt5.QtGui import *
        from PyQt5.QtSvg import QSvgRenderer
        PyQt_Version = 5
    except ImportError:
        print("PyQt5 or PyQt6 is required. Please install with:")
        print("pip install PyQt6")
        print("or")
        print("pip install PyQt5")
        sys.exit(1)

# --- BASE & APPDATA DIRECTORIES ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(__file__)

# --- APPDATA PERSISTENT DIRECTORY (keeps desktop clean & files hidden) ---
APPDATA_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'Quick101')
os.makedirs(APPDATA_DIR, exist_ok=True)

# --- PET WOW DATABASE ---
try:
    from pet_data import PET_DATABASE
except ImportError:
    try:
        _pdata_file = os.path.join(BASE_DIR, 'pets_data.json')
        with open(_pdata_file, 'r', encoding='utf-8') as _f:
            PET_DATABASE = json.load(_f)
    except Exception:
        PET_DATABASE = []

# Auto-migration: copy existing accounts/config from previous locations to APPDATA_DIR
for _search_loc in [
    BASE_DIR,
    os.path.join(os.path.expanduser('~'), 'Documents', 'code'),
    os.path.join(os.path.expanduser('~'), 'Downloads', 'Quick101'),
    os.path.join(os.path.expanduser('~'), 'Downloads', 'SyrupLauncher', 'SyrupLauncherSetup'),
    os.path.join(os.path.expanduser('~'), 'Downloads', 'SyrupLauncher', 'SyrupLauncherSetup', 'dist')
]:
    if not os.path.isdir(_search_loc):
        continue
    for _fname in ['accounts.yml', 'launcher_config.json']:
        _src = os.path.join(_search_loc, _fname)
        _dst = os.path.join(APPDATA_DIR, _fname)
        if os.path.isfile(_src) and not os.path.isfile(_dst):
            try:
                import shutil
                shutil.copy2(_src, _dst)
            except Exception:
                pass

# --- CONFIG & ACCOUNT FILES ---
CONFIG_FILE = os.path.join(APPDATA_DIR, 'launcher_config.json')
ACCOUNT_FILE = os.path.join(APPDATA_DIR, 'accounts.yml')
BACKGROUNDS_DIR = os.path.join(APPDATA_DIR, 'backgrounds')

# Ensure directories exist
os.makedirs(BACKGROUNDS_DIR, exist_ok=True)

# --- BACKGROUND LOGGING IN DOCUMENTS/Quick101_Logs ---
DOCUMENTS_DIR = os.path.join(os.path.expanduser('~'), 'Documents')
QUICK101_LOGS_DIR = os.path.join(DOCUMENTS_DIR, 'Quick101_Logs')
os.makedirs(QUICK101_LOGS_DIR, exist_ok=True)
CURRENT_LOG_FILE = os.path.join(QUICK101_LOGS_DIR, f"Quick101_{time.strftime('%Y-%m-%d')}.log")
_log_lock = threading.Lock()

def log_event(message: str, level: str = "INFO"):
    """Always generate logs in the background in Documents/Quick101_Logs/"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level.upper()}] {message}\n"
    print(entry.strip())
    try:
        with _log_lock:
            with open(CURRENT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry)
    except Exception:
        pass

def get_app_icon_path(prefer_ico: bool = True) -> Optional[str]:
    """Find the Quick101 icon path supporting both frozen PyInstaller and script modes"""
    search_dirs = []
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', '')
        if meipass:
            search_dirs.append(meipass)
        search_dirs.append(os.path.dirname(sys.executable))
    search_dirs.append(BASE_DIR)
    
    if prefer_ico:
        icon_names = ['Quick101.ico', 'Quick101.png']
    else:
        icon_names = ['Quick101.png', 'Quick101.ico']
        
    for d in search_dirs:
        if not d:
            continue
        for name in icon_names:
            p = os.path.join(d, name)
            if os.path.isfile(p):
                return p
    return None

def load_config() -> Dict:
    """Load launcher configuration with enhanced defaults"""
    default_config = {
        'theme_index': 0,
        'last_category': None,
        'wiz_path': r'C:/ProgramData/KingsIsle Entertainment/Wizard101/Bin/',
        'background_type': 'gradient',  # 'gradient', 'image', 'video', 'solid'
        'background_path': None,
        'background_opacity': 0.3,
        'auto_login_timeout': 300,  # 5 minutes in seconds
        'window_size': [1100, 800],
        'window_position': [100, 100],
        'animations_enabled': True,
        'blur_background': True,
        'theme_name': 'Monochrome B&W',
        'font_family': 'Segoe UI',
        'font_size': 10,
        'auto_save': True,
        'confirm_deletions': True,
        'show_status_bar': True,
        'auto_launch_delay': 1.0,
        'compact_mode': False,
        'compact_selected_account': None,
        'full_window_size': [1100, 800]
    }
    
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Migrate old combat_mode keys if present
                if 'combat_mode' in config and 'compact_mode' not in config:
                    config['compact_mode'] = config.pop('combat_mode')
                if 'combat_selected_account' in config and 'compact_selected_account' not in config:
                    config['compact_selected_account'] = config.pop('combat_selected_account')
                # Merge with defaults to ensure all keys exist
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
    return default_config

def save_config(cfg: Dict):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

# Load initial config
_cfg = load_config()

# --- YAML I/O for accounts ---
def load_yaml(fp: str) -> Dict:
    if not os.path.exists(fp):
        return {}
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error loading YAML {fp}: {e}")
        return {}

def save_yaml(data: Dict, fp: str):
    try:
        with open(fp, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, sort_keys=False)
    except Exception as e:
        print(f"Error saving YAML {fp}: {e}")

# --- ACCOUNT DATA LAYER ---
def load_accounts() -> Dict[str, Dict[str,Dict[str,str]]]:
    data = load_yaml(ACCOUNT_FILE)
    # Auto-detect steam mode if tagged in nickname
    for cat, accs in data.items():
        if isinstance(accs, dict):
            for nick, info in accs.items():
                if isinstance(info, dict):
                    if not info.get('steam') and any(s in nick.lower() for s in ['(steam)', '[steam]']):
                        info['steam'] = True
    return data

def save_accounts(data: Dict[str, Dict[str,Dict[str,str]]]):
    save_yaml(data, ACCOUNT_FILE)

def get_categories() -> List[str]:
    return list(load_accounts().keys())

def add_category(name: str):
    data = load_accounts()
    data.setdefault(name, {})
    save_accounts(data)

def delete_category(name: str):
    data = load_accounts()
    if name in data:
        del data[name]
        save_accounts(data)

def get_account_names(cat: str) -> List[str]:
    return list(load_accounts().get(cat, {}).keys())

def add_account(cat: str, nick: str, user: str, pwd: str, subtext: str = "", steam: bool = False):
    data = load_accounts()
    if not steam and any(s in nick.lower() for s in ['(steam)', '[steam]']):
        steam = True
    data.setdefault(cat, {})[nick] = {
        "username": user,
        "password": pwd,
        "subtext": subtext,
        "steam": bool(steam)
    }
    save_accounts(data)

def delete_account(cat: str, nick: str):
    data = load_accounts()
    if cat in data and nick in data[cat]:
        del data[cat][nick]
        save_accounts(data)

def load_account(cat: str, nick: str):
    data = load_accounts()
    acc = data.get(cat, {}).get(nick, {})
    if isinstance(acc, dict):
        if not acc.get('steam') and any(s in nick.lower() for s in ['(steam)', '[steam]']):
            acc['steam'] = True
    return nick, acc

# --- LAUNCH LOGIC WITH EXTENDED TIMEOUT & STEAM SUPPORT ---
class GameExecutable(Enum):
    WIZARD101 = "WizardGraphicalClient"

user32 = ctypes.windll.user32
WM_CHAR = 0x0102

WIZARD101_STEAM_APP_ID = "799960"

def ensure_steam_appid(game_path: str):
    """Ensure steam_appid.txt exists next to WizardGraphicalClient.exe with 799960 (Deimos-Wizard101 compatible)"""
    try:
        candidates = [game_path]
        bin_dir = os.path.join(game_path, "Bin")
        if os.path.isdir(bin_dir):
            candidates.append(bin_dir)
        for d in candidates:
            if not os.path.isdir(d):
                continue
            appid_file = os.path.join(d, "steam_appid.txt")
            needs_write = True
            if os.path.isfile(appid_file):
                try:
                    with open(appid_file, "r", encoding="utf-8") as f:
                        if f.read().strip() == WIZARD101_STEAM_APP_ID:
                            needs_write = False
                except Exception:
                    needs_write = True
            if needs_write:
                with open(appid_file, "w", encoding="utf-8") as f:
                    f.write(f"{WIZARD101_STEAM_APP_ID}\n")
                print(f"Verified steam_appid.txt at {appid_file}")
    except Exception as e:
        print(f"ensure_steam_appid error: {e}")

def send_chars(hwnd: int, text: str):
    """Send characters to window handle"""
    for ch in text:
        user32.SendMessageW(hwnd, WM_CHAR, ord(ch), 0)

def get_game_path() -> str:
    """Find Wizard101 installation path"""
    # First check if user has set a custom path
    custom_path = _cfg.get('wiz_path', '')
    if custom_path and os.path.exists(custom_path):
        # Check for both possible exe names
        for exe_name in [GameExecutable.WIZARD101.value + ".exe", "Wizard101.exe"]:
            exe_path = os.path.join(custom_path, exe_name)
            if os.path.exists(exe_path):
                return custom_path
    
    # Auto-detect common installation paths
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    candidates = [
        os.path.join(pf86, "Wizard101", "Bin"),
        os.path.join(pf, "Wizard101", "Bin"),
        os.path.join(r"C:\ProgramData", "KingsIsle Entertainment", "Wizard101", "Bin"),
        os.path.join(pf86, "Steam", "steamapps", "common", "Wizard101", "Bin"),
    ]
    
    # Check for both WizardGraphicalClient.exe and Wizard101.exe
    exe_names = [GameExecutable.WIZARD101.value + ".exe", "Wizard101.exe"]
    for d in candidates:
        for exe in exe_names:
            if os.path.isfile(os.path.join(d, exe)):
                return d
    raise FileNotFoundError("Wizard101 not found.")

ACTIVE_INSTANCES: Dict[str, subprocess.Popen] = {}

def is_account_already_running(nick: str) -> bool:
    """Check if an account is currently open either by active process or window title"""
    # 1. Tracked process check
    if nick in ACTIVE_INSTANCES:
        p = ACTIVE_INSTANCES[nick]
        if p and p.poll() is None:
            return True
        else:
            try:
                del ACTIVE_INSTANCES[nick]
            except KeyError:
                pass

    # 2. Window title check: Look for [{nick}]
    user32_dll = ctypes.windll.user32
    target_tag = f"[{nick}]"
    found = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int))
    def enum_check(h, l):
        buf = ctypes.create_unicode_buffer(256)
        user32_dll.GetWindowTextW(h, buf, 256)
        val = buf.value
        if val and target_tag in val and "Wizard" in val:
            found.append(h)
            return False
        return True

    try:
        user32_dll.EnumWindows(enum_check, 0)
    except Exception:
        pass

    return len(found) > 0


def kill_account_instance(nick: str) -> bool:
    """Terminate the Wizard101 instance corresponding to account nickname"""
    killed = False
    # 1. Kill tracked process
    if nick in ACTIVE_INSTANCES:
        p = ACTIVE_INSTANCES.pop(nick, None)
        if p and p.poll() is None:
            try:
                p.kill()
                killed = True
            except Exception:
                pass

    # 2. Find any window with [{nick}] and kill by PID
    user32_dll = ctypes.windll.user32
    target_tag = f"[{nick}]"
    pids_to_kill = set()
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int))
    def enum_kill(h, l):
        buf = ctypes.create_unicode_buffer(256)
        user32_dll.GetWindowTextW(h, buf, 256)
        if target_tag in buf.value:
            pid = ctypes.c_ulong()
            user32_dll.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if pid.value:
                pids_to_kill.add(pid.value)
        return True

    try:
        user32_dll.EnumWindows(enum_kill, 0)
    except Exception:
        pass

    for pid in pids_to_kill:
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], creationflags=0x08000000, capture_output=True)
            killed = True
        except Exception:
            pass

    return killed


def kill_all_wizard_instances():
    """Kill all WizardGraphicalClient.exe and Wizard101.exe processes"""
    ACTIVE_INSTANCES.clear()
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "WizardGraphicalClient.exe", "/IM", "Wizard101.exe"],
            creationflags=0x08000000,
            capture_output=True
        )
    except Exception as e:
        log_event(f"Error killing all instances: {e}", "ERROR")

def launch_with_credentials(user: str, pwd: str, nick: str, timeout: int = 10, is_steam: bool = False):
    """Launch Wizard101 with credentials (supporting Standalone and Steam modes)"""
    STANDALONE_PATH = r"C:/ProgramData/KingsIsle Entertainment/Wizard101/Bin/"
    STEAM_PATH = r"C:/Program Files (x86)/Steam/steamapps/common/Wizard101/Bin/"
    
    # Auto-detect steam mode from nickname if not explicitly flagged
    if not is_steam and any(tag in nick.lower() for tag in ['(steam)', '[steam]']):
        is_steam = True

    path = None
    # 1. Route based on account type
    if is_steam:
        if os.path.exists(STEAM_PATH):
            path = STEAM_PATH
    else:
        if os.path.exists(STANDALONE_PATH):
            path = STANDALONE_PATH
        
    # 2. Fall back to user-configured or auto-detected path if preferred is not found
    if not path:
        try:
            path = get_game_path()
        except FileNotFoundError as e:
            print(f"Error: {e}")
            return False
    
    try:
        # Try both exe names to find the correct one
        exe_path = None
        for exe_name in [GameExecutable.WIZARD101.value + ".exe", "Wizard101.exe"]:
            test_path = os.path.join(path, exe_name)
            if os.path.exists(test_path):
                exe_path = test_path
                break
        
        if not exe_path:
            print(f"Error: No Wizard101 executable found in {path}")
            return False
        
        # Build command arguments (CRITICAL: ONLY add -ST if account is actually Steam mode!)
        cmd_args = [exe_path]
        if is_steam:
            ensure_steam_appid(path)
            cmd_args.append("-ST")
            
        # Select login server based on configuration (US / Europe / Test Realm)
        server_choice = _cfg.get('server', 'US')
        if server_choice == 'Test Realm':
            server_host = "login.test.us.wizard101.com"
        elif server_choice == 'Europe':
            server_host = "login.eu.wizard101.com"
        else:
            server_host = "login.us.wizard101.com"
            
        cmd_args.extend(["-L", server_host, "12000"])
        log_event(f"Launching account '{nick}' | Server: {server_choice} ({server_host}) | Steam: {is_steam} | Exe: {exe_path}")
        
        proc = subprocess.Popen(
            cmd_args,
            cwd=path,
            creationflags=0x08000000
        )
        ACTIVE_INSTANCES[nick] = proc
        log_event(f"Started Wizard101 process with PID {proc.pid}")
        
        hwnd = None
        start = time.time()
        
        # Wait for window with configurable timeout
        while time.time() - start < timeout:
            handles = []
            
            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int))
            def enum(h, l):
                buf = ctypes.create_unicode_buffer(32)
                user32.GetClassNameW(h, buf, 32)
                if buf.value != "Wizard Graphical Client":
                    return True
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                if pid.value == proc.pid:
                    handles.append(h)
                    return False
                return True
            
            user32.EnumWindows(enum, 0)
            if handles:
                hwnd = handles[0]
                break
            time.sleep(0.1)  # Check every 100ms like OldLauncher
        
        if not hwnd:
            log_event(f"Timeout waiting for {nick} window (HWND not found after {timeout}s)", "WARNING")
            return False
        
        # Set custom window title
        user32.SetWindowTextW(hwnd, f"[{nick}] Wizard101")
        time.sleep(1)  # Give time for login screen like OldLauncher
        
        # Send credentials
        send_chars(hwnd, user)
        user32.SendMessageW(hwnd, WM_CHAR, 9, 0)  # Tab
        send_chars(hwnd, pwd)
        user32.SendMessageW(hwnd, WM_CHAR, 13, 0)  # Enter
        
        log_event(f"Successfully sent credentials for '{nick}' (HWND: {hwnd})")
        return True
        
    except Exception as e:
        log_event(f"Error launching {nick}: {e}", "ERROR")
        return False

## --- MODERN THEME SYSTEM (BLACK & WHITE WINFORMS EDITION) ---
class ModernThemes:
    THEMES = {
        0: {
            'name': 'Monochrome B&W',
            'primary': '#0A0A0A',
            'secondary': '#141414',
            'tertiary': '#1C1C1C',
            'card': '#141414',
            'card_hover': '#1C1C1C',
            'accent': '#FFFFFF',
            'accent_hover': '#E5E5E5',
            'accent_text': '#0A0A0A',
            'text_primary': '#FAFAFA',
            'text_secondary': '#969696',
            'text_muted': '#5F5F5F',
            'border': '#282828',
            'border_light': '#464646',
            'hover': '#1E1E1E',
            'danger_bg': '#1E1414',
            'danger_border': '#3D2020',
            'danger_text': '#FF8080',
            'danger_hover': '#2D1818',
            'success_bg': '#141F14',
            'success_border': '#244024',
            'success_text': '#86EFAC',
            'warning_bg': '#1F1A14',
            'warning_border': '#403424',
            'warning_text': '#FCD34D',
            'pill': '#1C1C1C',
        },
        1: {
            'name': 'Pure OLED Black',
            'primary': '#000000',
            'secondary': '#0F0F0F',
            'tertiary': '#171717',
            'card': '#0F0F0F',
            'card_hover': '#1A1A1A',
            'accent': '#FFFFFF',
            'accent_hover': '#EAEAEA',
            'accent_text': '#000000',
            'text_primary': '#FFFFFF',
            'text_secondary': '#A0A0A0',
            'text_muted': '#555555',
            'border': '#202020',
            'border_light': '#404040',
            'hover': '#171717',
            'danger_bg': '#1C1010',
            'danger_border': '#381818',
            'danger_text': '#FF7575',
            'danger_hover': '#281414',
            'success_bg': '#101C10',
            'success_border': '#183818',
            'success_text': '#7CEE9E',
            'warning_bg': '#1C1610',
            'warning_border': '#382A18',
            'warning_text': '#FCD34D',
            'pill': '#171717',
        },
        2: {
            'name': 'Dark Graphite',
            'primary': '#111215',
            'secondary': '#181A1E',
            'tertiary': '#22252B',
            'card': '#181A1E',
            'card_hover': '#22252B',
            'accent': '#FFFFFF',
            'accent_hover': '#E0E0E0',
            'accent_text': '#111215',
            'text_primary': '#F0F2F5',
            'text_secondary': '#9CA3AF',
            'text_muted': '#6B7280',
            'border': '#2B2F38',
            'border_light': '#4B5563',
            'hover': '#242831',
            'danger_bg': '#221417',
            'danger_border': '#442228',
            'danger_text': '#F87171',
            'danger_hover': '#331B20',
            'success_bg': '#132219',
            'success_border': '#20402E',
            'success_text': '#4ADE80',
            'warning_bg': '#221D13',
            'warning_border': '#443720',
            'warning_text': '#FBBF24',
            'pill': '#22252B',
        },
        3: {
            'name': 'Studio Slate',
            'primary': '#0F1117',
            'secondary': '#161922',
            'tertiary': '#1F2430',
            'card': '#161922',
            'card_hover': '#1F2430',
            'accent': '#FFFFFF',
            'accent_hover': '#E2E8F0',
            'accent_text': '#0F1117',
            'text_primary': '#F8FAFC',
            'text_secondary': '#94A3B8',
            'text_muted': '#64748B',
            'border': '#293040',
            'border_light': '#475569',
            'hover': '#212735',
            'danger_bg': '#241418',
            'danger_border': '#4A202A',
            'danger_text': '#FB7185',
            'danger_hover': '#351A22',
            'success_bg': '#11221B',
            'success_border': '#1D4534',
            'success_text': '#34D399',
            'warning_bg': '#241E13',
            'warning_border': '#4A3B20',
            'warning_text': '#FBBF24',
            'pill': '#1F2430',
        }
    }
    
    @classmethod
    def get_theme(cls, index: int) -> Dict[str, str]:
        return cls.THEMES.get(index % len(cls.THEMES), cls.THEMES[0])
    
    @classmethod
    def get_theme_names(cls) -> List[str]:
        return [theme['name'] for theme in cls.THEMES.values()]

# --- BACKGROUND MANAGER ---
class BackgroundManager(QObject):
    frame_ready = pyqtSignal(QPixmap) if PyQt_Version == 6 else pyqtSignal(QPixmap)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_bg = None
        self.video_thread = None
        self.is_playing = False
        
    def load_image_background(self, path: str, size: QSize, opacity: float = 0.7, blur: bool = True) -> QPixmap:
        """Load and process image background"""
        try:
            original_pixmap = QPixmap(path)
            if original_pixmap.isNull():
                return QPixmap()
            
            final_pixmap = QPixmap(size)
            final_pixmap.fill(QColor(self.parent().current_theme.get('primary', '#0A0A0A') if hasattr(self.parent(), 'current_theme') else '#0A0A0A'))
            
            scaled_pixmap = original_pixmap.scaled(
                size, 
                Qt.AspectRatioMode.KeepAspectRatioByExpanding if PyQt_Version == 6 else Qt.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation if PyQt_Version == 6 else Qt.SmoothTransformation
            )
            
            painter = QPainter(final_pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing if PyQt_Version == 6 else QPainter.Antialiasing)
            
            x = (size.width() - scaled_pixmap.width()) // 2
            y = (size.height() - scaled_pixmap.height()) // 2
            
            painter.drawPixmap(x, y, scaled_pixmap)
            
            if opacity < 1.0:
                overlay_color = QColor(10, 10, 10, int(255 * (1 - opacity)))
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop if PyQt_Version == 6 else QPainter.CompositionMode_SourceAtop)
                painter.fillRect(final_pixmap.rect(), overlay_color)
            
            painter.end()
            return final_pixmap
            
        except Exception as e:
            print(f"Error loading background image: {e}")
            return QPixmap()
    
    def create_gradient_background(self, color1: str, color2: str, size: QSize) -> QPixmap:
        """Create sleek monochrome gradient background matching Wizard101Calculator"""
        pixmap = QPixmap(size)
        painter = QPainter(pixmap)
        
        gradient = QLinearGradient(0, 0, 0, size.height())
        gradient.setColorAt(0, QColor(color1))
        # Smooth subtle shift into #0f0f0f at the bottom
        gradient.setColorAt(1, QColor(color2))
        
        painter.fillRect(pixmap.rect(), gradient)
        painter.end()
        return pixmap
    
    def create_solid_background(self, color: str, size: QSize) -> QPixmap:
        """Create solid monochrome background"""
        pixmap = QPixmap(size)
        pixmap.fill(QColor(color))
        return pixmap

# --- MAGIC FLOATING PARTICLES & COSMIC NEBULA BACKGROUND ---
class Particle:
    """A floating magical stardust/sparkle particle"""
    def __init__(self, w: float, h: float):
        self.reset(w, h, random_y=True)
        
    def reset(self, w: float, h: float, random_y: bool = False):
        self.x = random.uniform(0, max(w, 200))
        self.y = random.uniform(0, max(h, 200)) if random_y else h + random.uniform(5, 30)
        self.size = random.uniform(1.8, 4.8)
        self.vy = -random.uniform(0.35, 0.95)
        self.vx = random.uniform(-0.35, 0.35)
        self.base_alpha = random.uniform(70, 210)
        self.phase = random.uniform(0, math.pi * 2)
        self.phase_speed = random.uniform(0.04, 0.10)
        self.is_star = random.random() < 0.45
        
        # Unified magical starlight palette (consistent starlight silver & white)
        self.color = QColor(255, 255, 255)
        self.glow = QColor(210, 230, 255)

class MagicParticleWidget(QWidget):
    """Magical floating stardust, cosmic nebulae and constellation background for Quick101"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents if PyQt_Version == 6 else Qt.WA_TransparentForMouseEvents, True)
        self.particles = []
        self.num_particles = 95
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_particles)
        self.timer.start(25)  # ~40 FPS smooth animation
        
    def init_particles(self):
        w = float(max(self.width(), 800))
        h = float(max(self.height(), 600))
        self.particles = [Particle(w, h) for _ in range(self.num_particles)]
        
    def update_particles(self):
        w = float(max(self.width(), 100))
        h = float(max(self.height(), 100))
        if not self.particles:
            self.init_particles()
            
        for p in self.particles:
            p.y += p.vy
            p.x += p.vx + 0.15 * math.sin(p.phase * 0.5)
            p.phase += p.phase_speed
            
            if p.y < -25:
                p.reset(w, h, random_y=False)
            if p.x < -25:
                p.x = w + 15
            elif p.x > w + 25:
                p.x = -15
                
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing if PyQt_Version == 6 else QPainter.Antialiasing)
        
        w = float(self.width())
        h = float(self.height())
        
        # 1. Solid Uniform Dark Background (#0A0A0A)
        painter.fillRect(self.rect(), QColor(10, 10, 10))
        
        # 2. Constellation Lines between nearby particles (starlight silver)
        num = len(self.particles)
        for i in range(num):
            p1 = self.particles[i]
            for j in range(i + 1, min(i + 8, num)):
                p2 = self.particles[j]
                dx = p1.x - p2.x
                dy = p1.y - p2.y
                dist = math.hypot(dx, dy)
                if dist < 80.0:
                    line_alpha = int((1.0 - dist / 80.0) * 30)
                    pen = QPen(QColor(220, 235, 255, line_alpha), 1.0)
                    painter.setPen(pen)
                    painter.drawLine(QPointF(p1.x, p1.y), QPointF(p2.x, p2.y))
        
        # 3. Magic Particles & Stars
        for p in self.particles:
            alpha_val = int(p.base_alpha + 55 * math.sin(p.phase))
            alpha = max(15, min(245, alpha_val))
            
            p_col = QColor(p.color.red(), p.color.green(), p.color.blue(), alpha)
            p_glow = QColor(p.glow.red(), p.glow.green(), p.glow.blue(), alpha // 3)
            
            if p.is_star:
                r = p.size
                painter.setPen(Qt.PenStyle.NoPen if PyQt_Version == 6 else Qt.NoPen)
                painter.setBrush(QBrush(p_glow))
                painter.drawEllipse(QPointF(p.x, p.y), r * 2.2, r * 2.2)
                
                painter.setBrush(QBrush(p_col))
                # 4-pointed Star polygon
                pts = [
                    QPointF(p.x, p.y - r * 1.8),
                    QPointF(p.x + r * 0.45, p.y),
                    QPointF(p.x, p.y + r * 1.8),
                    QPointF(p.x - r * 0.45, p.y)
                ]
                painter.drawPolygon(QPolygonF(pts))
                pts2 = [
                    QPointF(p.x - r * 1.8, p.y),
                    QPointF(p.x, p.y + r * 0.45),
                    QPointF(p.x + r * 1.8, p.y),
                    QPointF(p.x, p.y - r * 0.45)
                ]
                painter.drawPolygon(QPolygonF(pts2))
            else:
                r = p.size * 0.9
                grad = QRadialGradient(p.x, p.y, r * 2.4)
                grad.setColorAt(0.0, p_col)
                grad.setColorAt(0.4, p_glow)
                grad.setColorAt(1.0, QColor(0, 0, 0, 0))
                
                painter.setPen(Qt.PenStyle.NoPen if PyQt_Version == 6 else Qt.NoPen)
                painter.setBrush(QBrush(grad))
                painter.drawEllipse(QPointF(p.x, p.y), r * 2.4, r * 2.4)
                
        painter.end()

# --- MODERN UI COMPONENTS (MONOCHROME B&W) ---
def create_vector_icon(name: str, color_hex: str = '#FAFAFA', size: int = 16) -> QIcon:
    """Create crisp, pixel-perfect monochrome vector icons using QPainter"""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent if PyQt_Version == 6 else Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing if PyQt_Version == 6 else QPainter.Antialiasing)
    col = QColor(color_hex)
    pen = QPen(col)
    p.setPen(pen)
    
    if name == 'launch':
        p.setBrush(QBrush(col))
        points = [QPointF(4, 2.5), QPointF(13, 8), QPointF(4, 13.5)]
        p.drawPolygon(QPolygonF(points))
    elif name == 'add':
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap if PyQt_Version == 6 else Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(8, 3, 8, 13)
        p.drawLine(3, 8, 13, 8)
    elif name == 'edit':
        pen.setWidth(1)
        p.setBrush(QBrush(col))
        points = [QPointF(3, 13), QPointF(4, 10), QPointF(11, 3), QPointF(13, 5), QPointF(6, 12), QPointF(3, 13)]
        p.drawPolygon(QPolygonF(points))
    elif name == 'delete':
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap if PyQt_Version == 6 else Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(4, 4, 12, 12)
        p.drawLine(12, 4, 4, 12)
    elif name == 'folder':
        p.setBrush(QBrush(col))
        pen.setWidth(1)
        p.drawRoundedRect(QRectF(2, 4, 12, 9), 2, 2)
        p.drawRoundedRect(QRectF(2, 2, 5, 3), 1, 1)
    elif name == 'steam':
        try:
            # Official Steam Logo SVG path
            steam_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}">
<path fill="{color_hex}" d="M11.979 0C5.678 0 .511 4.86.022 11.037l6.432 2.658c.545-.371 1.203-.59 1.912-.59.063 0 .125.004.188.006l2.861-4.142V8.91c0-2.495 2.028-4.524 4.524-4.524 2.494 0 4.524 2.03 4.524 4.524s-2.03 4.524-4.524 4.524h-.105l-4.076 2.911c0 .052.005.105.005.159 0 1.875-1.515 3.396-3.39 3.396-1.635 0-3.016-1.173-3.331-2.727L.436 14.819C1.654 20.076 6.364 24 11.979 24c6.627 0 12-5.373 12-12S18.606 0 11.979 0zM7.559 18.344l-1.635-.676c.307.572.84 1.011 1.487 1.196.938.27 1.929-.115 2.441-.893l-1.748-.722c-.147.67-.545 1.095-.545 1.095zm8.384-6.985c-1.393 0-2.527-1.134-2.527-2.528s1.134-2.527 2.527-2.527 2.528 1.134 2.528 2.527c0 1.394-1.135 2.528-2.528 2.528zm-6.28 4.797l1.79.74c.264-.541.229-1.196-.135-1.674-.363-.477-.975-.689-1.564-.539l-.091.973z"/>
</svg>'''
            renderer = QSvgRenderer(QByteArray(steam_svg.encode('utf-8')))
            renderer.render(p)
        except Exception:
            pen.setWidth(1)
            p.setBrush(QBrush(col))
            p.drawEllipse(QRectF(2.5, 7.5, 5, 5))
            p.drawEllipse(QRectF(8.5, 3, 4.5, 4.5))
            pen.setWidth(2)
            p.setPen(pen)
            p.drawLine(5, 9, 10, 5)
    elif name == 'standalone':
        pen.setWidth(1)
        p.setBrush(Qt.BrushStyle.NoBrush if PyQt_Version == 6 else Qt.NoBrush)
        p.drawRoundedRect(QRectF(2, 3, 12, 9), 1, 1)
        p.drawLine(5, 14, 11, 14)
        p.drawLine(8, 12, 8, 14)
    elif name == 'setup':
        pen.setWidthF(1.5)
        p.setPen(pen)
        p.drawLine(4, 12, 11, 5)
        p.drawLine(8, 3, 13, 8)
        p.setBrush(QBrush(col))
        points = [QPointF(11, 5), QPointF(13, 2), QPointF(14, 5)]
        p.drawPolygon(QPolygonF(points))
    elif name in ('compact', 'combat'):
        pen.setWidthF(1.5)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(2, 2, 12, 12), 2, 2)
        p.setBrush(QBrush(col))
        p.drawRoundedRect(QRectF(4, 5, 8, 6), 1, 1)
    elif name == 'settings':
        pen.setWidthF(1.5)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush if PyQt_Version == 6 else Qt.NoBrush)
        p.drawEllipse(QRectF(4.5, 4.5, 7, 7))
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            x1 = 8 + 4.5 * math.cos(rad)
            y1 = 8 + 4.5 * math.sin(rad)
            x2 = 8 + 6.8 * math.cos(rad)
            y2 = 8 + 6.8 * math.sin(rad)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    elif name == 'pet':
        # Paw print: large central pad + 3 small toe pads
        p.setBrush(QBrush(col))
        pen.setWidth(0)
        p.setPen(pen)
        p.drawEllipse(QRectF(4.5, 7.5, 7, 6))   # main pad
        p.drawEllipse(QRectF(2.0, 4.5, 3.5, 3))  # left toe
        p.drawEllipse(QRectF(5.5, 2.5, 3.0, 3))  # middle toe
        p.drawEllipse(QRectF(9.5, 4.5, 3.5, 3))  # right toe
    elif name == 'damage':
        # Lightning bolt
        p.setBrush(QBrush(col))
        pen.setWidth(0)
        p.setPen(pen)
        bolt = [QPointF(10, 2), QPointF(5.5, 9), QPointF(8.5, 9), QPointF(6, 14), QPointF(10.5, 7), QPointF(7.5, 7)]
        p.drawPolygon(QPolygonF(bolt))
    p.end()
    return QIcon(pix)

class ModernButton(QPushButton):
    def __init__(self, text: str, style: str = 'secondary', icon_name: Optional[str] = None, parent=None):
        super().__init__(text, parent)
        self.style_type = style
        self.icon_name = icon_name
        self.theme = ModernThemes.get_theme(_cfg.get('theme_index', 0))
        self.setCursor(Qt.CursorShape.PointingHandCursor if PyQt_Version == 6 else Qt.PointingHandCursor)
        self.apply_style()
        
    def apply_style(self):
        """Apply modern monochrome styling matching Wizard101Calculator"""
        border_color = self.theme.get('border', '#282828')
        border_light = self.theme.get('border_light', '#464646')
        
        if self.style_type == 'primary':
            # High-impact inverted white button (like Wizard101Calculator highlight action)
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: #FFFFFF;
                    color: #0A0A0A;
                    border: 1px solid #FFFFFF;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: bold;
                    font-size: 11px;
                    letter-spacing: 0.5px;
                    min-height: 22px;
                }}
                QPushButton:hover {{
                    background-color: #E5E5E5;
                    border-color: #E5E5E5;
                }}
                QPushButton:pressed {{
                    background-color: #CCCCCC;
                    border-color: #CCCCCC;
                }}
                QPushButton:disabled {{
                    background-color: #282828;
                    color: #666666;
                    border-color: #282828;
                }}
            """)
        elif self.style_type == 'danger':
            # Dark crimson tinted button
            danger_bg = self.theme.get('danger_bg', '#1E1414')
            danger_border = self.theme.get('danger_border', '#3D2020')
            danger_text = self.theme.get('danger_text', '#FF8080')
            danger_hover = self.theme.get('danger_hover', '#2D1818')
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {danger_bg};
                    color: {danger_text};
                    border: 1px solid {danger_border};
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 600;
                    font-size: 11px;
                    min-height: 20px;
                }}
                QPushButton:hover {{
                    background-color: {danger_hover};
                    border-color: #552828;
                    color: #FFA0A0;
                }}
                QPushButton:pressed {{
                    background-color: #181010;
                }}
                QPushButton:disabled {{
                    background-color: #181414;
                    color: #664444;
                    border-color: #281818;
                }}
            """)
        else:  # secondary / default
            # Sleek dark monochrome button (#1a1a1a) matching Wizard101Calculator
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: #1A1A1A;
                    color: {self.theme.get('text_primary', '#FAFAFA')};
                    border: 1px solid {border_color};
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 600;
                    font-size: 11px;
                    min-height: 20px;
                }}
                QPushButton:hover {{
                    background-color: #262626;
                    border-color: {border_light};
                    color: #FFFFFF;
                }}
                QPushButton:pressed {{
                    background-color: #141414;
                    border-color: #333333;
                }}
                QPushButton:disabled {{
                    background-color: #141414;
                    color: {self.theme.get('text_muted', '#5F5F5F')};
                    border-color: #202020;
                }}
            """)
        
        # Apply monochrome vector icon if configured
        if self.icon_name:
            if self.style_type == 'primary':
                icon_color = '#0A0A0A'
            elif self.style_type == 'danger':
                icon_color = self.theme.get('danger_text', '#FF8080')
            else:
                icon_color = self.theme.get('text_primary', '#FAFAFA')
            self.setIcon(create_vector_icon(self.icon_name, icon_color, 16))
            self.setIconSize(QSize(16, 16))

class ModernComboBox(QComboBox):
    """Styled combo box matching the monochrome black & white theme"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = ModernThemes.get_theme(_cfg.get('theme_index', 0))
        self.setCursor(Qt.CursorShape.PointingHandCursor if PyQt_Version == 6 else Qt.PointingHandCursor)
        self.apply_style()
    
    def apply_style(self):
        border_color = self.theme.get('border', '#282828')
        border_light = self.theme.get('border_light', '#464646')
        text_color = self.theme.get('text_primary', '#FAFAFA')
        
        self.setStyleSheet(f"""
            QComboBox {{
                background-color: #101010;
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
                min-height: 22px;
            }}
            QComboBox:hover {{
                border-color: {border_light};
                background-color: #161616;
            }}
            QComboBox:focus {{
                border-color: #707070;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 26px;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #888888;
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #141414;
                color: #FAFAFA;
                selection-background-color: #262626;
                selection-color: #FFFFFF;
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 12px;
                border-radius: 4px;
                margin: 1px;
                min-height: 20px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #1E1E1E;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #282828;
            }}
        """)

class AccountItemDelegate(QStyledItemDelegate):
    """Custom delegate for rendering account items with subtext in sleek Monochrome B&W card style"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing if PyQt_Version == 6 else QPainter.Antialiasing)
        
        text = index.data(Qt.ItemDataRole.DisplayRole if PyQt_Version == 6 else Qt.DisplayRole)
        if not text:
            painter.restore()
            return
        
        # Inset card rectangle
        card_rect = option.rect.adjusted(3, 3, -3, -3)
        
        list_widget = self.parent()
        is_selected = False
        if hasattr(list_widget, 'selected_rows'):
            is_selected = index.row() in list_widget.selected_rows
        
        # Monochrome card colors matching Wizard101Calculator
        if is_selected:
            bg_color = QColor(36, 36, 36)
            border_color = QColor(100, 100, 100)
        elif option.state & (QStyle.StateFlag.State_MouseOver if PyQt_Version == 6 else QStyle.State_MouseOver):
            bg_color = QColor(26, 26, 26)
            border_color = QColor(60, 60, 60)
        else:
            bg_color = QColor(20, 20, 20)
            border_color = QColor(40, 40, 40)
        
        # Draw card container
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(card_rect, 6, 6)
        
        # Left white accent indicator on selection
        if is_selected:
            painter.setPen(Qt.PenStyle.NoPen if PyQt_Version == 6 else Qt.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            indicator_rect = QRect(card_rect.left() + 1, card_rect.top() + 6, 3, card_rect.height() - 12)
            painter.drawRoundedRect(indicator_rect, 1.5, 1.5)
        
        lines = text.split('\n')
        main_text = lines[0]
        subtext = lines[1] if len(lines) > 1 else ""
        
        font_main = QFont("Segoe UI", 10)
        font_main.setBold(True)
        
        font_sub = QFont("Segoe UI", 9)
        font_sub.setBold(False)
        
        left_pad = card_rect.left() + 14
        content_width = card_rect.width() - 28
        
        # Check if Steam account
        is_steam = bool(index.data(Qt.ItemDataRole.UserRole + 1 if PyQt_Version == 6 else Qt.UserRole + 1))
        if is_steam:
            steam_icon = create_vector_icon('steam', '#FAFAFA', 16)
            icon_pix = steam_icon.pixmap(16, 16)
            icon_y = card_rect.top() + (8 if subtext else int((card_rect.height() - 16) / 2))
            painter.drawPixmap(left_pad, icon_y, icon_pix)
            left_pad += 22
            content_width -= 22
        
        if subtext:
            painter.setFont(font_main)
            painter.setPen(QColor(255, 255, 255))
            main_rect = QRect(left_pad, card_rect.top() + 7, content_width, 18)
            painter.drawText(main_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter if PyQt_Version == 6 else Qt.AlignLeft | Qt.AlignVCenter, main_text)
            
            painter.setFont(font_sub)
            painter.setPen(QColor(150, 150, 150))
            sub_rect = QRect(left_pad, card_rect.top() + 27, content_width, 16)
            painter.drawText(sub_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter if PyQt_Version == 6 else Qt.AlignLeft | Qt.AlignVCenter, subtext)
        else:
            painter.setFont(font_main)
            painter.setPen(QColor(255, 255, 255))
            main_rect = QRect(left_pad, card_rect.top(), content_width, card_rect.height())
            painter.drawText(main_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter if PyQt_Version == 6 else Qt.AlignLeft | Qt.AlignVCenter, main_text)
        
        painter.restore()
    
    def sizeHint(self, option, index):
        text = index.data(Qt.ItemDataRole.DisplayRole if PyQt_Version == 6 else Qt.DisplayRole)
        if not text:
            return QSize(200, 46)
        lines = text.split('\n')
        if len(lines) > 1:
            return QSize(200, 54)
        return QSize(200, 44)

class ModernListWidget(QListWidget):
    """Styled list widget with modern appearance and toggle selection"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = ModernThemes.get_theme(_cfg.get('theme_index', 0))
        self.apply_style()
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection if PyQt_Version == 6 else QAbstractItemView.NoSelection)
        self.setItemDelegate(AccountItemDelegate(self))
        self.selected_rows = set()
        self.last_click_time = 0
        self.click_delay = 200
        self.itemDoubleClicked.connect(self.ignore_multi_click)
        self.itemActivated.connect(self.ignore_multi_click)
        self.itemPressed.connect(self.ignore_multi_click)
        self.itemClicked.connect(self.ignore_multi_click)
        self.setMouseTracking(True)
        self.setSpacing(2)
        
    def throttled_toggle_selection(self, item):
        current_time = time.time() * 1000
        if current_time - self.last_click_time < self.click_delay:
            return
        self.last_click_time = current_time
        self.toggle_item_selection(item)
    
    def toggle_item_selection(self, item):
        row = self.row(item)
        if row in self.selected_rows:
            self.selected_rows.remove(row)
        else:
            self.selected_rows.add(row)
        self.viewport().update()
    
    def ignore_multi_click(self, item):
        pass
    
    def mousePressEvent(self, event):
        if event.button() == (Qt.MouseButton.LeftButton if PyQt_Version == 6 else Qt.LeftButton):
            item = self.itemAt(event.pos())
            if item:
                self.throttled_toggle_selection(item)
    
    def get_selected_items(self):
        items = []
        for row in self.selected_rows:
            item = self.item(row)
            if item:
                items.append(item)
        return items
    
    def clear_selection_custom(self):
        self.selected_rows.clear()
        self.viewport().update()
        
    def apply_style(self):
        border_color = self.theme.get('border', '#282828')
        self.setStyleSheet(f"""
            QListWidget {{
                background-color: #0E0E0E;
                color: #FAFAFA;
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 6px;
                font-size: 11px;
                outline: none;
            }}
            QListWidget::item {{
                border: none;
                background: transparent;
                padding: 0px;
                margin: 1px 0px;
            }}
        """)

class AccountDialog(QDialog):
    """Modern dialog for adding/editing accounts"""
    
    def __init__(self, parent=None, category: str = "", account_data: dict = None):
        super().__init__(parent)
        self.category = category
        self.account_data = account_data or {}
        self.theme = ModernThemes.get_theme(_cfg.get('theme_index', 0))
        self.username_visible = False
        self.password_visible = False
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Add Account" if not self.account_data else "Edit Account")
        self.setModal(True)
        self.setFixedSize(450, 400)
        
        # Apply theme
        border_color = self.theme.get('border', '#282828')
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #141414;
                color: #FAFAFA;
                border: 1px solid {border_color};
            }}
            QLabel {{
                color: #FAFAFA;
                font-weight: 600;
                font-size: 11px;
            }}
            QLineEdit {{
                background-color: #101010;
                color: #FFFFFF;
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 8px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: #707070;
            }}
            QCheckBox {{
                color: #969696;
                font-size: 10px;
                font-weight: 500;
            }}
            QCheckBox::indicator {{
                width: 15px;
                height: 15px;
                border-radius: 3px;
                border: 1px solid {border_color};
                background-color: #101010;
            }}
            QCheckBox::indicator:checked {{
                background-color: #FFFFFF;
                border-color: #FFFFFF;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("Add New Account" if not self.account_data else "Edit Account")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF; letter-spacing: 0.5px; margin-bottom: 4px;")
        layout.addWidget(title)
        
        # Category display
        cat_label = QLabel(f"CATEGORY: {self.category.upper()}")
        cat_label.setStyleSheet("color: #5F5F5F; font-size: 10px; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 8px;")
        layout.addWidget(cat_label)
        
        # Form
        form_layout = QFormLayout()
        
        # Nickname
        self.nickname_edit = QLineEdit()
        self.nickname_edit.setPlaceholderText("Account nickname")
        form_layout.addRow("Nickname:", self.nickname_edit)
        
        # Username with show/hide
        username_container = QWidget()
        username_layout = QVBoxLayout(username_container)
        username_layout.setContentsMargins(0, 0, 0, 0)
        username_layout.setSpacing(5)
        
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Wizard101 username")
        if not self.account_data:  # Only show for new accounts
            self.username_edit.setEchoMode(QLineEdit.EchoMode.Normal if PyQt_Version == 6 else QLineEdit.Normal)
        else:  # Hide by default for existing accounts
            self.username_edit.setEchoMode(QLineEdit.EchoMode.Password if PyQt_Version == 6 else QLineEdit.Password)
        username_layout.addWidget(self.username_edit)
        
        # Show username checkbox (only for edit mode)
        if self.account_data:
            self.show_username_cb = QCheckBox("Show Username")
            self.show_username_cb.stateChanged.connect(self.toggle_username_visibility)
            username_layout.addWidget(self.show_username_cb)
        
        form_layout.addRow("Username:", username_container)
        
        # Password with show/hide
        password_container = QWidget()
        password_layout = QVBoxLayout(password_container)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(5)
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password if PyQt_Version == 6 else QLineEdit.Password)
        self.password_edit.setPlaceholderText("Wizard101 password")
        password_layout.addWidget(self.password_edit)
        
        # Show password checkbox (always available)
        self.show_password_cb = QCheckBox("Show Password")
        self.show_password_cb.stateChanged.connect(self.toggle_password_visibility)
        password_layout.addWidget(self.show_password_cb)
        
        form_layout.addRow("Password:", password_container)
        
        layout.addLayout(form_layout)
        
        # Fill existing data
        if self.account_data:
            self.nickname_edit.setText(list(self.account_data.keys())[0])
            account_info = list(self.account_data.values())[0]
            self.username_edit.setText(account_info.get('username', ''))
            self.password_edit.setText(account_info.get('password', ''))
        
        # Buttons
        button_layout = QHBoxLayout()
        
        cancel_btn = ModernButton("Cancel", "secondary")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = ModernButton("Save", "primary")
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
    
    def toggle_username_visibility(self, state):
        """Toggle username field visibility"""
        if state == 2:  # Checked
            self.username_edit.setEchoMode(QLineEdit.EchoMode.Normal if PyQt_Version == 6 else QLineEdit.Normal)
            self.username_visible = True
        else:  # Unchecked
            self.username_edit.setEchoMode(QLineEdit.EchoMode.Password if PyQt_Version == 6 else QLineEdit.Password)
            self.username_visible = False
    
    def toggle_password_visibility(self, state):
        """Toggle password field visibility"""
        if state == 2:  # Checked
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Normal if PyQt_Version == 6 else QLineEdit.Normal)
            self.password_visible = True
        else:  # Unchecked
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Password if PyQt_Version == 6 else QLineEdit.Password)
            self.password_visible = False
    
    def get_account_data(self):
        return {
            'nickname': self.nickname_edit.text().strip(),
            'username': self.username_edit.text().strip(),
            'password': self.password_edit.text().strip()
        }

class FirstTimeSetupDialog(QDialog):
    """Modern First Time Setup wizard for Quick101"""
    
    STANDALONE_PATH = r"C:/ProgramData/KingsIsle Entertainment/Wizard101/Bin/"
    STEAM_PATH = r"C:/Program Files (x86)/Steam/steamapps/common/Wizard101/Bin/"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = ModernThemes.get_theme(_cfg.get('theme_index', 0))
        self.password_visible = False
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Quick101 - First Time Setup")
        self.setModal(True)
        self.setFixedSize(520, 680)
        
        icon_path = get_app_icon_path(prefer_ico=True)
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        border_color = self.theme.get('border', '#282828')
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #121212;
                color: #FAFAFA;
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
            QLabel {{
                color: #FAFAFA;
                font-size: 11px;
            }}
            QLineEdit {{
                background-color: #161616;
                color: #FFFFFF;
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: #707070;
            }}
            QRadioButton {{
                color: #FAFAFA;
                font-size: 11px;
                font-weight: 500;
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: 15px;
                height: 15px;
                border-radius: 7px;
                border: 1px solid {border_color};
                background-color: #161616;
            }}
            QRadioButton::indicator:checked {{
                background-color: #FFFFFF;
                border-color: #FFFFFF;
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 11px;
                border: 1px solid {border_color};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
                background-color: #161616;
                color: #FFFFFF;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 1px 6px;
                background-color: #161616;
                color: #FFFFFF;
            }}
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(12)
        
        # Header with Wizard Hat logo
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)
        
        logo_label = QLabel()
        icon_path = get_app_icon_path(prefer_ico=False)
        if icon_path and os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatio if PyQt_Version == 6 else Qt.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation if PyQt_Version == 6 else Qt.SmoothTransformation)
            logo_label.setPixmap(pix)
        header_layout.addWidget(logo_label)
        
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        welcome_title = QLabel("WELCOME TO QUICK101")
        welcome_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF; letter-spacing: 1.5px;")
        welcome_sub = QLabel("First-Time Setup: Set your installation path, category & first account.")
        welcome_sub.setStyleSheet("font-size: 10px; color: #969696;")
        welcome_sub.setWordWrap(True)
        title_box.addWidget(welcome_title)
        title_box.addWidget(welcome_sub)
        header_layout.addLayout(title_box)
        main_layout.addLayout(header_layout)
        
        # Section 1: Installation Path
        path_group = QGroupBox("1. WIZARD101 CLIENT")
        path_box = QVBoxLayout(path_group)
        path_box.setContentsMargins(14, 14, 14, 14)
        path_box.setSpacing(8)
        
        self.radio_standalone = QRadioButton("Standalone Client (KingsIsle)")
        self.radio_steam = QRadioButton("Steam Client")
        
        current_p = _cfg.get('wiz_path', '')
        if "steam" in current_p.lower():
            self.radio_steam.setChecked(True)
        else:
            self.radio_standalone.setChecked(True)
            
        path_box.addWidget(self.radio_standalone)
        path_box.addWidget(self.radio_steam)
        main_layout.addWidget(path_group)
        
        # Section 2: Server Selection
        server_group = QGroupBox("2. SERVER REGION")
        server_box = QHBoxLayout(server_group)
        server_box.setContentsMargins(14, 14, 14, 14)
        server_box.setSpacing(20)
        
        self.radio_srv_us = QRadioButton("US Server (United States)")
        self.radio_srv_eu = QRadioButton("Europe Server (EU)")
        
        current_server = _cfg.get('server', 'US')
        if current_server == 'Europe':
            self.radio_srv_eu.setChecked(True)
        else:
            self.radio_srv_us.setChecked(True)
            
        server_box.addWidget(self.radio_srv_us)
        server_box.addWidget(self.radio_srv_eu)
        server_box.addStretch()
        main_layout.addWidget(server_group)
        
        # Section 3: Category
        cat_group = QGroupBox("3. FIRST CATEGORY")
        cat_box = QVBoxLayout(cat_group)
        cat_box.setContentsMargins(14, 14, 14, 14)
        cat_box.setSpacing(6)
        
        cat_desc = QLabel("Category name to group your accounts:")
        cat_desc.setStyleSheet("color: #777777; font-size: 10px;")
        cat_box.addWidget(cat_desc)
        
        self.cat_edit = QLineEdit()
        self.cat_edit.setText("Main")
        self.cat_edit.setPlaceholderText("e.g. Main, PvP, Farming...")
        cat_box.addWidget(self.cat_edit)
        main_layout.addWidget(cat_group)
        
        # Section 4: Account
        acc_group = QGroupBox("4. FIRST ACCOUNT")
        acc_box = QVBoxLayout(acc_group)
        acc_box.setContentsMargins(14, 14, 14, 14)
        acc_box.setSpacing(8)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(6)
        
        self.nick_edit = QLineEdit()
        self.nick_edit.setPlaceholderText("e.g. MainWizard")
        form_layout.addRow("Nickname:", self.nick_edit)
        
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("Wizard101 username")
        form_layout.addRow("Username:", self.user_edit)
        
        pwd_container = QWidget()
        pwd_layout = QHBoxLayout(pwd_container)
        pwd_layout.setContentsMargins(0, 0, 0, 0)
        pwd_layout.setSpacing(6)
        
        self.pwd_edit = QLineEdit()
        self.pwd_edit.setEchoMode(QLineEdit.EchoMode.Password if PyQt_Version == 6 else QLineEdit.Password)
        self.pwd_edit.setPlaceholderText("Wizard101 password")
        pwd_layout.addWidget(self.pwd_edit)
        
        self.show_pwd_cb = QCheckBox("Show")
        self.show_pwd_cb.stateChanged.connect(self.toggle_password)
        pwd_layout.addWidget(self.show_pwd_cb)
        
        form_layout.addRow("Password:", pwd_container)
        
        self.subtext_edit = QLineEdit()
        self.subtext_edit.setPlaceholderText("e.g. Level 170 Death (Optional)")
        form_layout.addRow("Subtext:", self.subtext_edit)
        
        self.first_steam_cb = QCheckBox("Launch via Steam (Steam Mode)")
        self.first_steam_cb.setChecked(self.radio_steam.isChecked())
        self.first_steam_cb.setStyleSheet("color: #FAFAFA; font-size: 11px; margin-top: 4px;")
        form_layout.addRow("", self.first_steam_cb)
        
        self.radio_steam.toggled.connect(lambda checked: self.first_steam_cb.setChecked(checked))
        
        acc_box.addLayout(form_layout)
        main_layout.addWidget(acc_group)
        
        # Section 4: Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()
        
        skip_btn = ModernButton("Skip Setup", "secondary")
        skip_btn.clicked.connect(self.reject)
        btn_layout.addWidget(skip_btn)
        
        save_btn = ModernButton("Finish and Get Started", "primary", icon_name="launch")
        save_btn.setFixedHeight(38)
        save_btn.clicked.connect(self.finish_setup)
        btn_layout.addWidget(save_btn)
        
        main_layout.addLayout(btn_layout)
        
    def toggle_password(self, state):
        if state == 2:
            self.pwd_edit.setEchoMode(QLineEdit.EchoMode.Normal if PyQt_Version == 6 else QLineEdit.Normal)
        else:
            self.pwd_edit.setEchoMode(QLineEdit.EchoMode.Password if PyQt_Version == 6 else QLineEdit.Password)
            
    def finish_setup(self):
        # 1. Update path
        if self.radio_steam.isChecked():
            _cfg['wiz_path'] = self.STEAM_PATH
        else:
            _cfg['wiz_path'] = self.STANDALONE_PATH

        # 2. Update server
        if hasattr(self, 'radio_srv_eu') and self.radio_srv_eu.isChecked():
            _cfg['server'] = 'Europe'
        else:
            _cfg['server'] = 'US'
            
        category = self.cat_edit.text().strip() or "Main"
        nickname = self.nick_edit.text().strip()
        username = self.user_edit.text().strip()
        password = self.pwd_edit.text().strip()
        subtext = self.subtext_edit.text().strip()
        
        add_category(category)
        if nickname and username and password:
            add_account(category, nickname, username, password, subtext, steam=self.first_steam_cb.isChecked())
            
        _cfg['first_time_setup_completed'] = True
        _cfg['last_category'] = category
        save_config(_cfg)
        if self.parent() and hasattr(self.parent(), 'update_status'):
            self.parent().update_status(f"Setup completed. Server: {_cfg['server']}")
        self.accept()

# --- CUSTOM TITLEBAR & SETTINGS DIALOG ---
class CustomTitleBar(QWidget):
    """Sleek Frameless Titlebar with native Windows window controls and draggable area"""
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.drag_position = None
        self.setFixedHeight(32)
        self.setObjectName("CustomTitleBar")
        self.setStyleSheet("""
            QWidget#CustomTitleBar {
                background-color: transparent;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Draggable spacer spanning the full width
        layout.addStretch()
        
        # Original Windows 11 / 10 Titlebar Buttons
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(0)
        
        btn_style = """
            QPushButton {
                background: transparent;
                color: #C0C0C0;
                border: none;
                font-family: 'Segoe MDL2 Assets', 'Segoe UI Symbol', 'Segoe UI', Arial, sans-serif;
                font-size: 10px;
                width: 46px;
                height: 32px;
            }
            QPushButton:hover {
                background-color: #2D2D2D;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #3D3D3D;
            }
        """
        
        close_style = """
            QPushButton {
                background: transparent;
                color: #C0C0C0;
                border: none;
                font-family: 'Segoe MDL2 Assets', 'Segoe UI Symbol', 'Segoe UI', Arial, sans-serif;
                font-size: 10px;
                width: 46px;
                height: 32px;
            }
            QPushButton:hover {
                background-color: #E81123;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #F1707A;
                color: #FFFFFF;
            }
        """
        
        # \uE921 is the native Windows minimize glyph (horizontal line)
        self.min_btn = QPushButton("\uE921")
        self.min_btn.setStyleSheet(btn_style)
        self.min_btn.setToolTip("Minimize")
        self.min_btn.clicked.connect(self.parent_window.showMinimized)
        controls_layout.addWidget(self.min_btn)
        
        # \uE922 is the native Windows maximize glyph (square)
        self.max_btn = QPushButton("\uE922")
        self.max_btn.setStyleSheet(btn_style)
        self.max_btn.setToolTip("Maximize")
        self.max_btn.clicked.connect(self.parent_window.toggle_maximize)
        controls_layout.addWidget(self.max_btn)
        
        # \uE8BB is the native Windows close glyph (X)
        self.close_btn = QPushButton("\uE8BB")
        self.close_btn.setStyleSheet(close_style)
        self.close_btn.setToolTip("Close")
        self.close_btn.clicked.connect(self.parent_window.close)
        controls_layout.addWidget(self.close_btn)
        
        layout.addLayout(controls_layout)

    def mousePressEvent(self, event):
        if event.button() == (Qt.MouseButton.LeftButton if PyQt_Version == 6 else Qt.LeftButton):
            self.drag_position = (event.globalPosition().toPoint() if PyQt_Version == 6 else event.globalPos()) - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if (event.buttons() == (Qt.MouseButton.LeftButton if PyQt_Version == 6 else Qt.LeftButton)) and self.drag_position:
            pos = event.globalPosition().toPoint() if PyQt_Version == 6 else event.globalPos()
            self.parent_window.move(pos - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == (Qt.MouseButton.LeftButton if PyQt_Version == 6 else Qt.LeftButton):
            self.parent_window.toggle_maximize()

# --- AUTO UPDATER VIA GITHUB ---
APP_VERSION = "2.6"
DEFAULT_GITHUB_REPO = "VaniMoe/Quick101"

def apply_update(new_exe_path: str) -> bool:
    """Replace the running EXE with the newly downloaded one. Returns True on success."""
    target_exe = sys.executable if getattr(sys, 'frozen', False) else os.path.join(os.path.expanduser('~'), 'Documents', 'code', 'Quick101.exe')
    log_event(f"Applying update: replacing {target_exe} with {new_exe_path}")
    try:
        import shutil
        shutil.copy2(new_exe_path, target_exe)
        log_event("Update applied successfully. Awaiting manual restart.")
        try:
            os.remove(new_exe_path)
        except Exception:
            pass
        return True
    except Exception as e:
        log_event(f"Failed to replace EXE: {e}", "ERROR")
        return False

class GitHubUpdater(QObject):
    update_available = pyqtSignal(str, str, str)  # version, body, download_url
    no_update = pyqtSignal(str)                   # current_version
    check_failed = pyqtSignal(str)                # error message
    download_progress = pyqtSignal(int)           # percent
    download_finished = pyqtSignal(str)           # new exe path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def check_updates_async(self, notify_if_no_update: bool = False):
        """Check for updates in a daemon thread"""
        def worker():
            repo = _cfg.get('github_repo', DEFAULT_GITHUB_REPO).strip()
            if not repo or '/' not in repo:
                if notify_if_no_update:
                    self.check_failed.emit("Please enter a valid GitHub repository in format 'owner/repo'.")
                return
                
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            log_event(f"Checking for updates on GitHub: {url}...")
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': f'Quick101-Updater-{APP_VERSION}',
                    'Accept': 'application/vnd.github.v3+json'
                })
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode('utf-8'))
                        tag_name = data.get('tag_name', '').lstrip('v')
                        body = data.get('body', 'No release notes provided.')
                        
                        download_url = None
                        for asset in data.get('assets', []):
                            if asset.get('name', '').lower().endswith('.exe'):
                                download_url = asset.get('browser_download_url')
                                break
                        if not download_url and data.get('assets'):
                            download_url = data['assets'][0].get('browser_download_url')
                            
                        if self._is_newer_version(tag_name, APP_VERSION):
                            log_event(f"New update found: v{tag_name} (Current: v{APP_VERSION})")
                            self.update_available.emit(tag_name, body, download_url or "")
                        else:
                            log_event(f"Quick101 is up to date (v{APP_VERSION})")
                            if notify_if_no_update:
                                self.no_update.emit(APP_VERSION)
            except urllib.error.HTTPError as e:
                log_event(f"Update check HTTP error: {e.code} - {e.reason}", "WARNING")
                if notify_if_no_update:
                    if e.code == 404:
                        self.check_failed.emit(f"Repository '{repo}' not found or has no releases published on GitHub yet.")
                    else:
                        self.check_failed.emit(f"GitHub returned error {e.code}: {e.reason}")
            except Exception as e:
                log_event(f"Update check error: {e}", "WARNING")
                if notify_if_no_update:
                    self.check_failed.emit(f"Could not connect to GitHub: {e}")
                    
        threading.Thread(target=worker, daemon=True).start()

    def _is_newer_version(self, latest: str, current: str) -> bool:
        try:
            def parse_ver(v):
                parts = []
                for p in v.replace('v', '').split('.'):
                    digits = ''.join(c for c in p if c.isdigit())
                    if digits:
                        parts.append(int(digits))
                return parts
            return parse_ver(latest) > parse_ver(current)
        except Exception:
            return latest.strip() != current.strip()

    def download_and_install_update(self, download_url: str):
        """Download new executable and relaunch via batch updater"""
        def dl_worker():
            try:
                dest_exe = os.path.join(APPDATA_DIR, "Quick101_Update.exe")
                log_event(f"Downloading update from {download_url} to {dest_exe}...")
                
                req = urllib.request.Request(download_url, headers={
                    'User-Agent': f'Quick101-Updater-{APP_VERSION}'
                })
                with urllib.request.urlopen(req, timeout=45) as resp:
                    total_size = int(resp.headers.get('Content-Length', 0))
                    downloaded = 0
                    block_size = 65536
                    with open(dest_exe, 'wb') as f:
                        while True:
                            chunk = resp.read(block_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = int((downloaded / total_size) * 100)
                                self.download_progress.emit(percent)
                                
                self.download_finished.emit(dest_exe)
            except Exception as e:
                log_event(f"Update download failed: {e}", "ERROR")
                self.check_failed.emit(f"Download failed: {e}")
                
        threading.Thread(target=dl_worker, daemon=True).start()

class UpdateDialog(QDialog):
    """Modern Dialog presenting available update and download progress"""
    def __init__(self, parent, version: str, notes: str, download_url: str, updater: 'GitHubUpdater'):
        super().__init__(parent)
        self.version = version
        self.notes = notes
        self.download_url = download_url
        self.updater = updater
        self.setWindowTitle(f"Quick101 - Update Available (v{version})")
        self.setFixedSize(480, 360)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #0E0E0E;
                color: #FAFAFA;
                border: 1px solid #282828;
                border-radius: 8px;
            }
            QLabel {
                color: #FAFAFA;
            }
            QTextEdit, QTextBrowser {
                background-color: #141414;
                color: #D0D0D0;
                border: 1px solid #282828;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Segoe UI';
                font-size: 11px;
            }
            QProgressBar {
                background-color: #1A1A1A;
                border: 1px solid #333333;
                border-radius: 4px;
                height: 16px;
                text-align: center;
                color: #FFFFFF;
                font-size: 10px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #FFFFFF;
                border-radius: 3px;
            }
        """)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        title = QLabel(f"New Update Ready! (v{self.version})")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF; letter-spacing: 0.5px;")
        layout.addWidget(title)
        
        current_lbl = QLabel(f"A new update for Quick101 is ready to download. (Installed: v{APP_VERSION})")
        current_lbl.setStyleSheet("color: #86EFAC; font-size: 11px;")
        layout.addWidget(current_lbl)

        link_lbl = QLabel('<a href="https://github.com/VaniMoe/Quick101/releases/latest" style="color: #60A5FA; text-decoration: underline;">Open GitHub Releases Page & Download</a>')
        link_lbl.setOpenExternalLinks(True)
        link_lbl.setStyleSheet("font-size: 11px;")
        layout.addWidget(link_lbl)
        
        notes_label = QLabel("Changelog / Release Notes:")
        notes_label.setStyleSheet("color: #A0A0A0; font-size: 11px; font-weight: 600; margin-top: 4px;")
        layout.addWidget(notes_label)
        
        self.notes_view = QTextBrowser()
        self.notes_view.setReadOnly(True)
        self.notes_view.setOpenExternalLinks(True)
        if hasattr(self.notes_view, 'setMarkdown'):
            self.notes_view.setMarkdown(self.notes or "No release notes provided.")
        else:
            self.notes_view.setPlainText(self.notes or "No release notes provided.")
        layout.addWidget(self.notes_view)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #86EFAC; font-size: 11px;")
        self.status_lbl.hide()
        layout.addWidget(self.status_lbl)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.gh_btn = ModernButton("Download (GitHub)", "secondary", icon_name="launch")
        self.gh_btn.clicked.connect(self.open_release_page)
        btn_layout.addWidget(self.gh_btn)
        
        btn_layout.addStretch()
        
        self.cancel_btn = ModernButton("Later", "secondary")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        if self.download_url:
            self.action_btn = ModernButton("Direct Update", "primary")
            self.action_btn.clicked.connect(self.start_update)
        else:
            self.action_btn = ModernButton("Open on GitHub", "primary")
            self.action_btn.clicked.connect(self.open_release_page)
        btn_layout.addWidget(self.action_btn)
        
        layout.addLayout(btn_layout)
        
        # Connect updater signals
        if self.updater:
            self.updater.download_progress.connect(self.on_download_progress)
            self.updater.download_finished.connect(self.on_download_finished)
            self.updater.check_failed.connect(self.on_download_failed)

    def start_update(self):
        self.action_btn.setEnabled(False)
        self.action_btn.setText("Downloading...")
        self.cancel_btn.setEnabled(False)
        if hasattr(self, 'gh_btn'):
            self.gh_btn.setEnabled(False)
        self.progress_bar.show()
        self.status_lbl.setText("Downloading update from GitHub...")
        self.status_lbl.show()
        self.updater.download_and_install_update(self.download_url)

    def on_download_progress(self, percent: int):
        self.progress_bar.setValue(percent)
        self.status_lbl.setText(f"Download in progress: {percent}%")

    def on_download_finished(self, new_exe_path: str):
        self.progress_bar.setValue(100)
        success = apply_update(new_exe_path)
        if success:
            self.status_lbl.setText("Update installed! Please restart Quick101.")
            self.status_lbl.setStyleSheet("color: #86EFAC; font-size: 11px;")
            self.action_btn.setText("Close")
            self.action_btn.setEnabled(True)
            self.action_btn.clicked.disconnect()
            self.action_btn.clicked.connect(self.accept)
            self.cancel_btn.hide()
            QMessageBox.information(
                self, "Update Installed",
                "The update has been downloaded and installed.\n\n"
                "Please close and reopen Quick101 to use the new version."
            )
        else:
            self.status_lbl.setText("Failed to replace the EXE. Is Quick101 running or write-protected?")
            self.status_lbl.setStyleSheet("color: #FFA0A0; font-size: 11px;")
            self.action_btn.setEnabled(True)
            self.action_btn.setText("Retry")
            self.cancel_btn.setEnabled(True)
            if hasattr(self, 'gh_btn'):
                self.gh_btn.setEnabled(True)

    def on_download_failed(self, err: str):
        self.status_lbl.setText(f"Update failed: {err}")
        self.status_lbl.setStyleSheet("color: #FFA0A0; font-size: 11px;")
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Retry")
        self.cancel_btn.setEnabled(True)
        if hasattr(self, 'gh_btn'):
            self.gh_btn.setEnabled(True)

    def open_release_page(self):
        import webbrowser
        webbrowser.open("https://github.com/VaniMoe/Quick101/releases/latest")
        self.accept()

class AccountAlreadyOpenDialog(QDialog):
    """Custom warning popup when an account is already running"""
    def __init__(self, parent=None, nickname=""):
        super().__init__(parent)
        self.setWindowTitle("Account Already Open")
        self.setFixedWidth(420)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #0E0E0E;
                color: #FAFAFA;
                border: 1px solid #282828;
                border-radius: 8px;
            }
            QLabel {
                color: #E0E0E0;
            }
        """)
        self.setup_ui(nickname)

    def setup_ui(self, nickname):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        warn_icon = QLabel("⚠️")
        warn_icon.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        header_layout.addWidget(warn_icon)
        
        title_lbl = QLabel("ACCOUNT ALREADY OPEN")
        title_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #F59E0B; letter-spacing: 1px; background: transparent; border: none;")
        header_layout.addWidget(title_lbl, 1)
        layout.addLayout(header_layout)

        # Message Card
        msg_card = QFrame()
        msg_card.setStyleSheet("""
            QFrame {
                background-color: #141414;
                border: 1px solid #262626;
                border-radius: 6px;
                padding: 12px;
            }
        """)
        msg_layout = QVBoxLayout(msg_card)
        msg_layout.setContentsMargins(12, 12, 12, 12)
        
        msg_lbl = QLabel(f"The account <b><font color='#F59E0B'>{nickname}</font></b> is already open.<br><br>Open anyway?")
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet("font-size: 13px; color: #EDEDED; background: transparent; border: none;")
        msg_layout.addWidget(msg_lbl)
        layout.addWidget(msg_card)

        # Buttons: Skip Account, Open Anyway
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        skip_btn = ModernButton("Skip Account", "secondary")
        skip_btn.setFixedHeight(36)
        skip_btn.clicked.connect(self.reject)
        btn_layout.addWidget(skip_btn)

        yes_btn = ModernButton("Open Anyway", "primary")
        yes_btn.setFixedHeight(36)
        yes_btn.clicked.connect(self.accept)
        btn_layout.addWidget(yes_btn)

        layout.addLayout(btn_layout)

class SettingsDialog(QDialog):
    """Settings Dialog for Quick101 (All English)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Quick101 - Settings")
        self.setFixedWidth(460)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #0E0E0E;
                color: #FAFAFA;
                border: 1px solid #282828;
                border-radius: 8px;
            }
            QGroupBox {
                color: #FAFAFA;
                font-size: 11px;
                font-weight: 700;
                border: 1px solid #242424;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                background-color: #0E0E0E;
                color: #A0A0A0;
                letter-spacing: 1px;
            }
            QRadioButton {
                color: #E0E0E0;
                font-size: 12px;
                padding: 4px;
            }
        """)
        self.updater = GitHubUpdater(self)
        self.updater.update_available.connect(self.on_update_found)
        self.updater.no_update.connect(self.on_no_update)
        self.updater.check_failed.connect(self.on_update_error)
        self.setup_ui()

    def run_first_setup(self):
        self.accept()
        if self.parent_window and hasattr(self.parent_window, 'open_first_time_setup'):
            self.parent_window.open_first_time_setup()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        
        # Title
        title_label = QLabel("SETTINGS")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF; letter-spacing: 2px;")
        layout.addWidget(title_label)
        
        # 1. Server Selection
        server_group = QGroupBox("SERVER SELECTION")
        server_layout = QVBoxLayout(server_group)
        server_layout.setSpacing(8)
        
        self.radio_us = QRadioButton("US Server (login.us.wizard101.com)")
        self.radio_eu = QRadioButton("Europe Server (login.eu.wizard101.com)")
        self.radio_test = QRadioButton("Test Realm (login.test.us.wizard101.com)")
        
        current_server = _cfg.get('server', 'US')
        if current_server == 'Test Realm':
            self.radio_test.setChecked(True)
        elif current_server == 'Europe':
            self.radio_eu.setChecked(True)
        else:
            self.radio_us.setChecked(True)
            
        server_layout.addWidget(self.radio_us)
        server_layout.addWidget(self.radio_eu)
        server_layout.addWidget(self.radio_test)
        layout.addWidget(server_group)
        
        # 2. First-Time Setup Wizard
        setup_group = QGroupBox("FIRST-TIME SETUP")
        setup_layout = QVBoxLayout(setup_group)
        setup_layout.setSpacing(8)
        
        setup_wizard_btn = ModernButton("Run Setup Wizard", "secondary", icon_name="setup")
        setup_wizard_btn.setToolTip("Rerun the first-time setup assistant to detect game directories and configure server region")
        setup_wizard_btn.clicked.connect(self.run_first_setup)
        setup_layout.addWidget(setup_wizard_btn)
        layout.addWidget(setup_group)
        
        # 3. Logs
        logs_group = QGroupBox("LOG FILES")
        logs_layout = QVBoxLayout(logs_group)
        logs_layout.setSpacing(8)
        
        quick101_log_btn = ModernButton("Open Quick101 Logs Folder", "secondary", icon_name="folder")
        quick101_log_btn.setToolTip("Open Documents/Quick101_Logs folder containing launcher logs")
        quick101_log_btn.clicked.connect(self.open_quick101_logs)
        logs_layout.addWidget(quick101_log_btn)
        
        log_btn = ModernButton("Open Wizard101 Game Log", "secondary", icon_name="folder")
        log_btn.setToolTip("Open folder containing WizardClient.log")
        log_btn.clicked.connect(self.open_logs)
        logs_layout.addWidget(log_btn)
        layout.addWidget(logs_group)
        
        # 3. Auto Update (GitHub)
        update_group = QGroupBox(f"AUTO UPDATE (v{APP_VERSION})")
        update_layout = QVBoxLayout(update_group)
        update_layout.setSpacing(8)
        
        repo_layout = QHBoxLayout()
        repo_lbl = QLabel("GitHub Repo:")
        repo_lbl.setStyleSheet("color: #A0A0A0; font-size: 11px;")
        repo_layout.addWidget(repo_lbl)
        
        self.repo_edit = QLineEdit(_cfg.get('github_repo', DEFAULT_GITHUB_REPO))
        self.repo_edit.setPlaceholderText("owner/repo (e.g. Shuwa/Quick101)")
        self.repo_edit.setStyleSheet("""
            QLineEdit {
                background-color: #141414;
                color: #FFFFFF;
                border: 1px solid #303030;
                border-radius: 5px;
                padding: 6px;
                font-size: 11px;
            }
        """)
        repo_layout.addWidget(self.repo_edit, 1)
        update_layout.addLayout(repo_layout)
        
        check_update_btn = ModernButton("Check for Updates", "secondary", icon_name="setup")
        check_update_btn.clicked.connect(self.check_updates_now)
        update_layout.addWidget(check_update_btn)
        layout.addWidget(update_group)
        
        # 4. Management & Reset
        mgmt_group = QGroupBox("MANAGEMENT & RESET")
        mgmt_layout = QVBoxLayout(mgmt_group)
        mgmt_layout.setSpacing(8)
        
        clear_acc_btn = ModernButton("Clear Accounts", "danger", icon_name="delete")
        clear_acc_btn.setToolTip("Delete all saved accounts")
        clear_acc_btn.clicked.connect(self.clear_accounts)
        mgmt_layout.addWidget(clear_acc_btn)
        
        reset_cfg_btn = ModernButton("Reset Settings", "danger")
        reset_cfg_btn.setToolTip("Reset all launcher configuration to default")
        reset_cfg_btn.clicked.connect(self.reset_settings)
        mgmt_layout.addWidget(reset_cfg_btn)
        layout.addWidget(mgmt_group)
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()
        
        save_btn = ModernButton("Save and Close", "primary")
        save_btn.clicked.connect(self.save_and_close)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)

    def open_logs(self):
        possible_paths = [
            r"C:\ProgramData\KingsIsle Entertainment\Wizard101\Bin\WizardClient.log",
            r"C:\Program Files (x86)\Steam\steamapps\common\Wizard101\Bin\WizardClient.log",
            r"C:\ProgramData\KingsIsle Entertainment\Wizard101\Bin",
            r"C:\Program Files (x86)\Steam\steamapps\common\Wizard101\Bin",
            APPDATA_DIR
        ]
        opened = False
        for p in possible_paths:
            if os.path.isfile(p):
                subprocess.Popen(['explorer', f'/select,{os.path.normpath(p)}'])
                opened = True
                break
            elif os.path.isdir(p):
                os.startfile(p)
                opened = True
                break
        if not opened:
            QMessageBox.information(self, "Logs", "No Wizard101 log files found on this computer.")

    def clear_accounts(self):
        reply = QMessageBox.question(
            self, "Clear Accounts",
            "Are you sure you want to delete all saved accounts?\nThis action cannot be undone.",
            (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) if PyQt_Version == 6 else (QMessageBox.Yes | QMessageBox.No)
        )
        if reply == (QMessageBox.StandardButton.Yes if PyQt_Version == 6 else QMessageBox.Yes):
            save_accounts({})
            if self.parent_window:
                self.parent_window.load_categories()
                self.parent_window.update_status("All accounts have been deleted.")
            QMessageBox.information(self, "Accounts Cleared", "All accounts were successfully deleted.")

    def reset_settings(self):
        reply = QMessageBox.question(
            self, "Reset Settings",
            "Are you sure you want to reset all launcher settings to default?",
            (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) if PyQt_Version == 6 else (QMessageBox.Yes | QMessageBox.No)
        )
        if reply == (QMessageBox.StandardButton.Yes if PyQt_Version == 6 else QMessageBox.Yes):
            global _cfg
            default_config = {
                'theme_index': 0,
                'last_category': None,
                'wiz_path': r'C:/ProgramData/KingsIsle Entertainment/Wizard101/Bin/',
                'background_type': 'gradient',
                'background_path': None,
                'background_opacity': 0.3,
                'auto_login_timeout': 300,
                'window_size': [1100, 800],
                'window_position': [100, 100],
                'animations_enabled': True,
                'blur_background': True,
                'theme_name': 'Monochrome B&W',
                'font_family': 'Segoe UI',
                'font_size': 10,
                'auto_save': True,
                'confirm_deletions': True,
                'show_status_bar': True,
                'auto_launch_delay': 1.0,
                'compact_mode': False,
                'first_time_setup_completed': True,
                'server': 'US'
            }
            _cfg.clear()
            _cfg.update(default_config)
            save_config(_cfg)
            if self.parent_window:
                self.parent_window.update_wizard_path_display()
                self.parent_window.update_status("Settings have been reset to default.")
            QMessageBox.information(self, "Reset Complete", "All settings were reset to default values.")

    def open_quick101_logs(self):
        os.makedirs(QUICK101_LOGS_DIR, exist_ok=True)
        try:
            os.startfile(QUICK101_LOGS_DIR)
        except Exception as e:
            QMessageBox.warning(self, "Logs Folder", f"Could not open logs folder: {e}")

    def check_updates_now(self):
        repo = self.repo_edit.text().strip() or DEFAULT_GITHUB_REPO
        _cfg['github_repo'] = repo
        self.updater.check_updates_async(notify_if_no_update=True)

    def on_update_found(self, version: str, notes: str, download_url: str):
        dlg = UpdateDialog(self, version, notes, download_url, self.updater)
        dlg.exec()

    def on_no_update(self, version: str):
        QMessageBox.information(self, "Quick101 Up to Date", f"Quick101 is already up to date!\n\nCurrent version: v{version}")

    def on_update_error(self, err: str):
        QMessageBox.warning(self, "Update Check", f"Could not check for updates:\n\n{err}")

    def save_and_close(self):
        if self.radio_test.isChecked():
            _cfg['server'] = 'Test Realm'
        elif self.radio_eu.isChecked():
            _cfg['server'] = 'Europe'
        else:
            _cfg['server'] = 'US'
        _cfg['github_repo'] = self.repo_edit.text().strip() or DEFAULT_GITHUB_REPO
        save_config(_cfg)
        if self.parent_window:
            self.parent_window.update_status(f"Server set to: {_cfg['server']}")
        self.accept()

# --- PET CALCULATOR DIALOG ---
class PetCalculatorDialog(QDialog):
    """Wizard101 Pet Stat Calculator — based on petcalc.weebly.com formulas"""

    HOW_TO_USE = (
        "How to Use the Pet Calculator\n\n"
        "1. Look up your pet's maximum stats in-game:\n"
        "   Strength, Intellect, Agility, Will, and Power.\n\n"
        "2. Enter those maximum values into the five fields\n"
        "   on the left side of the calculator.\n\n"
        "3. The right side will instantly show the values\n"
        "   each talent will give once your pet is fully\n"
        "   trained with max snacks.\n\n"
        "Example: If Spell-Proof shows 10.14%, your pet\n"
        "will grant 10% resist (rounds down if < .5).\n\n"
        "Note: Values ending in .5 or higher are rounded\n"
        "UP by the game; lower values round DOWN.\n"
        "Critical and Block stats may deviate slightly."
    )

    # Talent formulas (inputs: strength, intellect, agility, will, power)
    TALENTS = [
        # (display_name, unit, lambda)
        # ── Damage ──────────────────────────────────────────────────
        ("Any School Dealer",           "%",   lambda s,i,a,w,p: ((2*s + 2*w + p) * 0.0075) / 100),
        ("Any School Giver / Pain-Giver","%",  lambda s,i,a,w,p: ((2*s + 2*w + p) / 200) / 100),
        ("Any School Boon / Pain-Bringer","%", lambda s,i,a,w,p: ((2*s + 2*w + p) / 400) / 100),
        # ── Armor Piercing ───────────────────────────────────────────
        ("Piercer",                     "%",   lambda s,i,a,w,p: ((2*s + 2*a + p) * 0.0015) / 100),
        ("Breaker (Armor)",             "%",   lambda s,i,a,w,p: ((2*s + 2*a + p) / 400) / 100),
        # ── Defense ─────────────────────────────────────────────────
        ("Spell-Proof",                 "%",   lambda s,i,a,w,p: ((2*s + 2*a + p) / 125) / 100),
        ("Spell-Defying",               "%",   lambda s,i,a,w,p: ((2*s + 2*a + p) / 250) / 100),
        ("Ward",                        "%",   lambda s,i,a,w,p: ((2*s + 2*a + p) * 0.012) / 100),
        # ── Critical ────────────────────────────────────────────────
        ("Crit Striker",                "",    lambda s,i,a,w,p: (2*a + 2*w + p) * 0.024),
        ("Crit Hitter",                 "",    lambda s,i,a,w,p: (2*a + 2*w + p) * 0.02),
        ("School Assailant",            "",    lambda s,i,a,w,p: (2*a + 2*w + p) / 40),
        ("School Striker",              "",    lambda s,i,a,w,p: (2*a + 2*w + p) * 0.02),
        # ── Block ────────────────────────────────────────────────────
        ("Defender",                    "",    lambda s,i,a,w,p: (2*i + 2*w + p) * 0.024),
        ("Blocker",                     "",    lambda s,i,a,w,p: (2*i + 2*w + p) * 0.02),
        # ── Accuracy ─────────────────────────────────────────────────
        ("Sniper",                      "%",   lambda s,i,a,w,p: ((2*i + 2*a + p) * 0.0075) / 100),
        ("Sharp Shot",                  "%",   lambda s,i,a,w,p: ((2*i + 2*a + p) / 200) / 100),
        ("Eagle Eye",                   "%",   lambda s,i,a,w,p: ((2*i + 2*a + p) / 400) / 100),
        # ── Utility ──────────────────────────────────────────────────
        ("Stun Resist",                 "%",   lambda s,i,a,w,p: ((2*s + 2*i + p) / 250) / 100),
        ("Stun Recalibration",          "%",   lambda s,i,a,w,p: ((2*s + 2*i + p) / 125) / 100),
        ("Lively",                      "%",   lambda s,i,a,w,p: ((2*i + 2*a + p) * 0.0065) / 100),
        ("Healer",                      "%",   lambda s,i,a,w,p: ((2*s + 2*w + p) * 0.003) / 100),
        ("Medic",                       "%",   lambda s,i,a,w,p: ((2*s + 2*w + p) * 0.0065) / 100),
        ("Healthy",                     "%",   lambda s,i,a,w,p: ((2*i + 2*a + p) * 0.003) / 100),
    ]

    _FIELD_STYLE = """
        QSpinBox {
            background-color: #141414;
            color: #FAFAFA;
            border: 1px solid #2A2A2A;
            border-radius: 5px;
            padding: 4px 8px;
            font-size: 12px;
        }
        QSpinBox:focus { border: 1px solid #606060; }
        QSpinBox::up-button, QSpinBox::down-button { width: 0; }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick101 — Pet Stat Calculator")
        self.setModal(True)
        self.setMinimumWidth(720)
        self.setStyleSheet("""
            QDialog {
                background-color: #0E0E0E;
                color: #FAFAFA;
                border: 1px solid #282828;
                border-radius: 8px;
            }
            QLabel { color: #FAFAFA; }
            QGroupBox {
                color: #FAFAFA;
                font-size: 11px;
                font-weight: 700;
                border: 1px solid #242424;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
            QTableWidget {
                background-color: #0A0A0A;
                color: #FAFAFA;
                border: 1px solid #242424;
                border-radius: 5px;
                gridline-color: #1E1E1E;
                font-size: 11px;
            }
            QTableWidget::item { padding: 4px 8px; }
            QTableWidget::item:selected {
                background-color: #2A2A2A;
                color: #FFFFFF;
            }
            QHeaderView::section {
                background-color: #141414;
                color: #909090;
                border: none;
                border-bottom: 1px solid #282828;
                padding: 5px 8px;
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
            }
            QScrollBar:vertical {
                background: #0E0E0E;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #333333;
                border-radius: 4px;
            }
        """)
        self._build_ui()
        self._recalculate()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # ── Title row ────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title_lbl = QLabel("Pet Stat Calculator")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        title_row.addWidget(title_lbl)
        title_row.addStretch()

        how_btn = ModernButton("How to Use", "secondary")
        how_btn.clicked.connect(self._show_how_to_use)
        title_row.addWidget(how_btn)
        root.addLayout(title_row)

        sub_lbl = QLabel("Enter your pet's maximum stats below — results update instantly.")
        sub_lbl.setStyleSheet("color: #686868; font-size: 11px;")
        root.addWidget(sub_lbl)

        # ── Stat inputs ──────────────────────────────────────────────
        stats_group = QGroupBox("PET STATS (MAX VALUES)")
        stats_layout = QHBoxLayout(stats_group)
        stats_layout.setContentsMargins(14, 20, 14, 14)
        stats_layout.setSpacing(16)

        self._inputs = {}
        stat_defs = [
            ("Strength",  "STR", 0, 500),
            ("Intellect", "INT", 0, 500),
            ("Agility",   "AGI", 0, 500),
            ("Will",      "WIL", 0, 500),
            ("Power",     "PWR", 0, 500),
        ]
        for name, short, mn, mx in stat_defs:
            col = QVBoxLayout()
            col.setSpacing(4)
            lbl = QLabel(name)
            lbl.setStyleSheet("font-size: 10px; color: #808080; font-weight: 600;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter if PyQt_Version == 6 else Qt.AlignCenter)
            col.addWidget(lbl)

            spin = QSpinBox()
            spin.setRange(mn, mx)
            spin.setFixedWidth(78)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter if PyQt_Version == 6 else Qt.AlignCenter)
            spin.setStyleSheet(self._FIELD_STYLE)
            spin.valueChanged.connect(self._recalculate)
            col.addWidget(spin)
            self._inputs[name] = spin
            stats_layout.addLayout(col)

        stats_layout.addStretch()
        root.addWidget(stats_group)

        # ── Results table ────────────────────────────────────────────
        results_group = QGroupBox("TALENT VALUES AT MAX STATS")
        results_layout = QVBoxLayout(results_group)
        results_layout.setContentsMargins(14, 20, 14, 14)

        self._table = QTableWidget(len(self.TALENTS), 3)
        self._table.setHorizontalHeaderLabels(["Talent", "Value", "Note"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch if PyQt_Version == 6 else QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed if PyQt_Version == 6 else QHeaderView.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed if PyQt_Version == 6 else QHeaderView.Fixed)
        self._table.setColumnWidth(1, 90)
        self._table.setColumnWidth(2, 200)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers if PyQt_Version == 6 else QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows if PyQt_Version == 6 else QTableWidget.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(self._table.styleSheet() + "QTableWidget { alternate-background-color: #0E0E0E; }")

        for row, (name, unit, _) in enumerate(self.TALENTS):
            name_item = QTableWidgetItem(name)
            name_item.setForeground(QColor("#DADADA"))
            self._table.setItem(row, 0, name_item)

            val_item = QTableWidgetItem("—")
            val_item.setTextAlignment((Qt.AlignmentFlag.AlignRight if PyQt_Version == 6 else Qt.AlignRight) | (Qt.AlignmentFlag.AlignVCenter if PyQt_Version == 6 else Qt.AlignVCenter))
            val_item.setForeground(QColor("#86EFAC"))
            self._table.setItem(row, 1, val_item)

            note_item = QTableWidgetItem("")
            note_item.setForeground(QColor("#686868"))
            self._table.setItem(row, 2, note_item)

        results_layout.addWidget(self._table)
        root.addWidget(results_group)

        # ── Bottom buttons ───────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        reset_btn = ModernButton("Reset", "secondary")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        close_btn = ModernButton("Close", "primary")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    def _get_stats(self):
        return (
            self._inputs["Strength"].value(),
            self._inputs["Intellect"].value(),
            self._inputs["Agility"].value(),
            self._inputs["Will"].value(),
            self._inputs["Power"].value(),
        )

    def _recalculate(self):
        s, i, a, w, p = self._get_stats()
        all_zero = (s == i == a == w == p == 0)
        for row, (name, unit, fn) in enumerate(self.TALENTS):
            if all_zero:
                self._table.item(row, 1).setText("—")
                self._table.item(row, 2).setText("")
                continue
            raw = fn(s, i, a, w, p)
            if unit == "%":
                pct = raw * 100
                # Game rounds .5+ up, below .5 down
                rounded = math.floor(pct + 0.5)
                self._table.item(row, 1).setText(f"{pct:.3f}%")
                note = f"→ {rounded}% in-game"
                # Colour-code: green if clean round, yellow if close
                diff = abs(pct - rounded)
                col = "#86EFAC" if diff < 0.05 else ("#FDE68A" if diff < 0.4 else "#FCA5A5")
                self._table.item(row, 1).setForeground(QColor(col))
                self._table.item(row, 2).setText(note)
            else:
                rounded = math.floor(raw + 0.5)
                self._table.item(row, 1).setText(f"{raw:.2f}")
                self._table.item(row, 2).setText(f"→ {rounded} in-game")
                self._table.item(row, 1).setForeground(QColor("#93C5FD"))

    def _reset(self):
        for spin in self._inputs.values():
            spin.blockSignals(True)
            spin.setValue(0)
            spin.blockSignals(False)
        self._recalculate()

    def _show_how_to_use(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("How to Use — Pet Calculator")
        dlg.setModal(True)
        dlg.setFixedWidth(420)
        dlg.setStyleSheet("""
            QDialog { background-color: #0E0E0E; color: #FAFAFA; border: 1px solid #282828; border-radius: 8px; }
            QLabel { color: #DADADA; }
        """)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("How to Use")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title)

        body = QLabel(self.HOW_TO_USE)
        body.setWordWrap(True)
        body.setStyleSheet("font-size: 11px; color: #C0C0C0; line-height: 1.6;")
        layout.addWidget(body)

        note = QLabel("Formula source: petcalc.weebly.com by @mxdup")
        note.setStyleSheet("font-size: 10px; color: #505050; font-style: italic;")
        layout.addWidget(note)

        ok_btn = ModernButton("Got it!", "primary")
        ok_btn.clicked.connect(dlg.accept)
        layout.addWidget(ok_btn)
        dlg.exec()



# --- PET WOW RETURNER DIALOG ---
class PetWoWReturnerDialog(QDialog):
    """Wizard101 Pet Return Chance Calculator & Pet Tome
    Based on petbodyw101.vercel.app formulas and pet wow factors"""

    SCHOOL_COLORS = {
        "Fire": "#EF4444",
        "Ice": "#38BDF8",
        "Storm": "#A855F7",
        "Life": "#22C55E",
        "Myth": "#FACC15",
        "Death": "#94A3B8",
        "Balance": "#FB923C",
    }

    HOW_TO_USE = (
        "Wizard101 Pet Hatching & Wow Factor Guide\n\n"
        "1. Pet Wow Factor (Hidden Stat)\n"
        "Every pet has a hidden 'Wow Factor' (0 to 10) assigned by KingsIsle.\n"
        "• LOWER wow factor = HIGHER chance of receiving that body back.\n"
        "• HIGHER wow factor = LOWER chance (rarer body).\n\n"
        "2. Standard Hatching Odds Formula:\n"
        "   Pet 1 Chance = (11 - Pet1.WowFactor) / (22 - (Pet1.WowFactor + Pet2.WowFactor)) * 100\n"
        "   Pet 2 Chance = (11 - Pet2.WowFactor) / (22 - (Pet1.WowFactor + Pet2.WowFactor)) * 100\n\n"
        "3. Exclusive Pet Body Logic (Crucial Rule!):\n"
        "• Placing an Exclusive Pet on the RIGHT slot in a Self-Hatch will\n"
        "  ALWAYS return the body on the LEFT (100% chance for Pet 1)!\n"
        "  Even if the left body is also Exclusive, Retired, or Unhatchable.\n"
        "• If you WANT the Exclusive body back, you MUST place it on the LEFT\n"
        "  in a self-hatch, or use it as your selected pet in Kiosk hatches.\n\n"
        "Data source: petbodyw101.vercel.app"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick101 — Pet WoW Returner")
        self.setModal(True)
        self.resize(880, 680)
        self.setMinimumSize(800, 600)
        self._pets = PET_DATABASE if 'PET_DATABASE' in globals() and PET_DATABASE else []
        self._pet_map = {p["name"]: p for p in self._pets}
        self._pet_names = sorted(list(self._pet_map.keys()), key=lambda s: s.lower())

        self.setStyleSheet("""
            QDialog {
                background-color: #0E0E0E;
                color: #FAFAFA;
                border: 1px solid #282828;
                border-radius: 8px;
            }
            QLabel { color: #FAFAFA; }
            QTabWidget::pane {
                border: 1px solid #242424;
                background: #0E0E0E;
                border-radius: 6px;
                top: -1px;
            }
            QTabBar::tab {
                background: #141414;
                color: #888888;
                border: 1px solid #242424;
                border-bottom: none;
                padding: 8px 18px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #1F1F1F;
                color: #FAFAFA;
                border-bottom: 2px solid #3B82F6;
            }
            QTabBar::tab:hover:!selected {
                background: #181818;
                color: #C0C0C0;
            }
            QGroupBox {
                color: #FAFAFA;
                font-size: 11px;
                font-weight: 700;
                border: 1px solid #242424;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
            QLineEdit, QComboBox {
                background-color: #141414;
                color: #FAFAFA;
                border: 1px solid #2A2A2A;
                border-radius: 5px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #606060;
            }
            QComboBox QAbstractItemView {
                background-color: #161616;
                color: #FAFAFA;
                border: 1px solid #333333;
                selection-background-color: #2A2A2A;
                selection-color: #FFFFFF;
                outline: none;
            }
            QTableWidget {
                background-color: #0A0A0A;
                color: #FAFAFA;
                border: 1px solid #242424;
                border-radius: 5px;
                gridline-color: #1C1C1C;
                font-size: 11px;
            }
            QTableWidget::item { padding: 4px 8px; }
            QTableWidget::item:selected {
                background-color: #262626;
                color: #FFFFFF;
            }
            QHeaderView::section {
                background-color: #141414;
                color: #909090;
                border: none;
                border-bottom: 1px solid #282828;
                padding: 6px 8px;
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
            }
            QScrollBar:vertical {
                background: #0E0E0E;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #333333;
                border-radius: 4px;
            }
        """)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        # Title bar
        title_row = QHBoxLayout()
        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        title_lbl = QLabel("Wizard101 Pet WoW Returner")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        v_title.addWidget(title_lbl)
        sub_lbl = QLabel("Pet body return odds & hatching calculator (petbodyw101.vercel.app)")
        sub_lbl.setStyleSheet("color: #707070; font-size: 11px;")
        v_title.addWidget(sub_lbl)
        title_row.addLayout(v_title)
        title_row.addStretch()

        help_btn = ModernButton("How to Use", "secondary")
        help_btn.clicked.connect(self._show_how_to_use)
        title_row.addWidget(help_btn)
        root.addLayout(title_row)

        # Tabs
        self.tabs = QTabWidget()
        self._tab_calc = QWidget()
        self._tab_tome = QWidget()

        self._build_calc_tab()
        self._build_tome_tab()

        self.tabs.addTab(self._tab_calc, "Return Chance Calculator")
        self.tabs.addTab(self._tab_tome, f"Pet Tome ({len(self._pets)} Pets)")
        root.addWidget(self.tabs)

        # Footer
        footer_row = QHBoxLayout()
        db_info = QLabel(f"Database: {len(self._pets)} pets loaded from petbodyw101.vercel.app")
        db_info.setStyleSheet("color: #555555; font-size: 10px;")
        footer_row.addWidget(db_info)
        footer_row.addStretch()
        close_btn = ModernButton("Close", "primary")
        close_btn.clicked.connect(self.accept)
        footer_row.addWidget(close_btn)
        root.addLayout(footer_row)

    def _build_calc_tab(self):
        layout = QVBoxLayout(self._tab_calc)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        # Slots row: Pet 1, Swap button, Pet 2
        slots_layout = QHBoxLayout()
        slots_layout.setSpacing(12)

        # Pet 1 Card
        self.p1_box = QGroupBox("PET 1 (LEFT SLOT / YOUR PET)")
        p1_l = QVBoxLayout(self.p1_box)
        p1_l.setSpacing(8)
        self.combo1 = QComboBox()
        self._setup_combobox(self.combo1)
        self.combo1.currentTextChanged.connect(self._on_pet1_changed)
        p1_l.addWidget(self.combo1)
        self.card1_details = QLabel("Select a pet above to view stats")
        self.card1_details.setStyleSheet("font-size: 11px; color: #888888; padding: 6px;")
        p1_l.addWidget(self.card1_details)
        slots_layout.addWidget(self.p1_box)

        # Swap button
        swap_col = QVBoxLayout()
        swap_col.addStretch()
        self.swap_btn = ModernButton("⇄ Swap", "secondary")
        self.swap_btn.setToolTip("Swap Left and Right pet slots")
        self.swap_btn.clicked.connect(self._swap_pets)
        swap_col.addWidget(self.swap_btn)
        swap_col.addStretch()
        slots_layout.addLayout(swap_col)

        # Pet 2 Card
        self.p2_box = QGroupBox("PET 2 (RIGHT SLOT / OTHER OR KIOSK)")
        p2_l = QVBoxLayout(self.p2_box)
        p2_l.setSpacing(8)
        self.combo2 = QComboBox()
        self._setup_combobox(self.combo2)
        self.combo2.currentTextChanged.connect(self._on_pet2_changed)
        p2_l.addWidget(self.combo2)
        self.card2_details = QLabel("Select a pet above to view stats")
        self.card2_details.setStyleSheet("font-size: 11px; color: #888888; padding: 6px;")
        p2_l.addWidget(self.card2_details)
        slots_layout.addWidget(self.p2_box)

        layout.addLayout(slots_layout)

        # Results Card
        self.results_group = QGroupBox("RETURN ODDS CALCULATION")
        res_l = QVBoxLayout(self.results_group)
        res_l.setContentsMargins(16, 16, 16, 16)
        res_l.setSpacing(12)

        self.odds_display = QHBoxLayout()
        self.odds_lbl_1 = QLabel("Pet 1: —")
        self.odds_lbl_1.setStyleSheet("font-size: 20px; font-weight: bold; color: #888888;")
        self.odds_lbl_2 = QLabel("Pet 2: —")
        self.odds_lbl_2.setStyleSheet("font-size: 20px; font-weight: bold; color: #888888;")
        align_r = Qt.AlignmentFlag.AlignRight if PyQt_Version == 6 else Qt.AlignRight
        self.odds_lbl_2.setAlignment(align_r)
        self.odds_display.addWidget(self.odds_lbl_1)
        self.odds_display.addStretch()
        self.odds_display.addWidget(self.odds_lbl_2)
        res_l.addLayout(self.odds_display)

        self.rule_banner = QLabel("Please select both pets to calculate hatching return chances.")
        self.rule_banner.setWordWrap(True)
        self.rule_banner.setStyleSheet("""
            background-color: #141414;
            color: #C0C0C0;
            border: 1px solid #282828;
            border-radius: 6px;
            padding: 10px 14px;
            font-size: 11px;
            line-height: 1.4;
        """)
        res_l.addWidget(self.rule_banner)
        layout.addWidget(self.results_group)
        layout.addStretch()

    def _setup_combobox(self, combo):
        combo.setEditable(True)
        insert_mode = QComboBox.InsertPolicy.NoInsert if PyQt_Version == 6 else QComboBox.NoInsert
        combo.setInsertPolicy(insert_mode)
        combo.addItem("-- Select or type pet name --", "")
        for name in self._pet_names:
            combo.addItem(name, name)
        completer = QCompleter(self._pet_names, combo)
        case_mode = Qt.CaseSensitivity.CaseInsensitive if PyQt_Version == 6 else Qt.CaseInsensitive
        match_mode = Qt.MatchFlag.MatchContains if PyQt_Version == 6 else Qt.MatchContains
        completer.setCaseSensitivity(case_mode)
        completer.setFilterMode(match_mode)
        combo.setCompleter(completer)

    def _format_pet_card(self, pet):
        if not pet:
            return "Select a pet above to view stats"
        school = pet.get("school", "Unknown")
        color = self.SCHOOL_COLORS.get(school, "#FAFAFA")
        wf = pet.get("wowFactor")
        wf_str = f"<b>{wf} / 10</b>" if wf is not None else "<i>Unknown</i>"
        egg = pet.get("eggName", "Unknown")
        exclusive = pet.get("exclusive", False)
        unhatchable = pet.get("unhatchable", False)
        retired = pet.get("retired", False)
        special = pet.get("specialBody", False)

        excl_tag = "<span style='color: #F59E0B; font-weight: bold;'>Yes (Special Rules)</span>" if exclusive else "<span style='color: #10B981;'>No</span>"
        tags = []
        if unhatchable:
            tags.append("<span style='color: #EF4444;'>Unhatchable</span>")
        if retired:
            tags.append("<span style='color: #94A3B8;'>Retired</span>")
        if special:
            tags.append("<span style='color: #A855F7;'>Special Body</span>")
        extra_tags = " · ".join(tags) if tags else "Standard Body"

        return (
            f"<div style='line-height: 1.5;'>"
            f"School: <b style='color: {color};'>● {school}</b><br>"
            f"Wow Factor: {wf_str}<br>"
            f"Egg Type: <span style='color: #C0C0C0;'>{egg}</span><br>"
            f"Exclusive: {excl_tag}<br>"
            f"Status: <span style='font-size: 10px;'>{extra_tags}</span>"
            f"</div>"
        )

    def _on_pet1_changed(self, text):
        pet = self._pet_map.get(text.strip())
        self.card1_details.setText(self._format_pet_card(pet))
        self._recalculate()

    def _on_pet2_changed(self, text):
        pet = self._pet_map.get(text.strip())
        self.card2_details.setText(self._format_pet_card(pet))
        self._recalculate()

    def _swap_pets(self):
        t1 = self.combo1.currentText()
        t2 = self.combo2.currentText()
        self.combo1.blockSignals(True)
        self.combo2.blockSignals(True)
        self.combo1.setCurrentText(t2)
        self.combo2.setCurrentText(t1)
        self.combo1.blockSignals(False)
        self.combo2.blockSignals(False)
        self._on_pet1_changed(self.combo1.currentText())
        self._on_pet2_changed(self.combo2.currentText())

    def _recalculate(self):
        p1 = self._pet_map.get(self.combo1.currentText().strip())
        p2 = self._pet_map.get(self.combo2.currentText().strip())

        if not p1 or not p2:
            self.odds_lbl_1.setText("Pet 1: —")
            self.odds_lbl_1.setStyleSheet("font-size: 20px; font-weight: bold; color: #888888;")
            self.odds_lbl_2.setText("Pet 2: —")
            self.odds_lbl_2.setStyleSheet("font-size: 20px; font-weight: bold; color: #888888;")
            self.rule_banner.setText("Please select both pets to calculate hatching return chances.")
            self.rule_banner.setStyleSheet("background-color: #141414; color: #888888; border: 1px solid #242424; border-radius: 6px; padding: 10px 14px; font-size: 11px;")
            return

        # Exclusive rule: Placing Exclusive pet on Right slot (Pet 2) ALWAYS returns Left pet (Pet 1)
        if p2.get("exclusive"):
            self.odds_lbl_1.setText(f"{p1['name']}: 100%")
            self.odds_lbl_1.setStyleSheet("font-size: 20px; font-weight: bold; color: #22C55E;")
            self.odds_lbl_2.setText(f"{p2['name']}: 0%")
            self.odds_lbl_2.setStyleSheet("font-size: 20px; font-weight: bold; color: #EF4444;")
            self.rule_banner.setText(
                "⚠️ <b>EXCLUSIVE BODY RULE:</b> Pet 2 is an <b>Exclusive Pet</b> placed on the Right slot!\n"
                "In a self-hatch, placing an exclusive body on the Right ALWAYS returns the Left body (100% chance for Pet 1), "
                "even if the left body is also Exclusive, Retired, or Unhatchable."
            )
            self.rule_banner.setStyleSheet("background-color: #241408; color: #F59E0B; border: 1px solid #78350F; border-radius: 6px; padding: 10px 14px; font-size: 11px;")
            return

        wf1 = p1.get("wowFactor")
        wf2 = p2.get("wowFactor")
        if wf1 is None or wf2 is None:
            self.odds_lbl_1.setText("Unknown")
            self.odds_lbl_2.setText("Unknown")
            self.rule_banner.setText("Wow Factor is unknown for one or both selected pets. Cannot calculate exact odds.")
            self.rule_banner.setStyleSheet("background-color: #1E1212; color: #F87171; border: 1px solid #7F1D1D; border-radius: 6px; padding: 10px 14px; font-size: 11px;")
            return

        denom = 22 - (wf1 + wf2)
        if denom <= 0:
            c1, c2 = 50, 50
        else:
            c1 = round((11 - wf1) / denom * 100)
            c2 = round((11 - wf2) / denom * 100)

        # Color coding: higher chance is green, lower is red/orange
        if c1 > c2:
            col1 = "#22C55E"
            col2 = "#EF4444"
        elif c2 > c1:
            col1 = "#EF4444"
            col2 = "#22C55E"
        else:
            col1 = "#F59E0B"
            col2 = "#F59E0B"

        self.odds_lbl_1.setText(f"{p1['name']}: {c1}%")
        self.odds_lbl_1.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {col1};")
        self.odds_lbl_2.setText(f"{p2['name']}: {c2}%")
        self.odds_lbl_2.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {col2};")

        self.rule_banner.setText(
            f"<b>Hatching Formula:</b><br>"
            f"• <b>Pet 1 ({p1['name']}):</b> (11 - {wf1}) / (22 - ({wf1} + {wf2})) = <b>{c1}%</b><br>"
            f"• <b>Pet 2 ({p2['name']}):</b> (11 - {wf2}) / (22 - ({wf1} + {wf2})) = <b>{c2}%</b><br>"
            f"<i>Remember: Lower Wow Factor = Higher chance of being returned!</i>"
        )
        self.rule_banner.setStyleSheet("background-color: #0E1A12; color: #86EFAC; border: 1px solid #14532D; border-radius: 6px; padding: 10px 14px; font-size: 11px;")

    def _build_tome_tab(self):
        layout = QVBoxLayout(self._tab_tome)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.tome_search = QLineEdit()
        self.tome_search.setPlaceholderText("Search pets by name...")
        self.tome_search.textChanged.connect(self._filter_tome)
        filter_row.addWidget(self.tome_search, 2)

        self.tome_school_filter = QComboBox()
        self.tome_school_filter.addItem("All Schools", "")
        for s in ["Fire", "Ice", "Storm", "Life", "Myth", "Death", "Balance"]:
            self.tome_school_filter.addItem(s, s)
        self.tome_school_filter.currentTextChanged.connect(self._filter_tome)
        filter_row.addWidget(self.tome_school_filter, 1)

        self.tome_wow_filter = QComboBox()
        self.tome_wow_filter.addItem("All Wow Factors", "")
        for i in range(11):
            self.tome_wow_filter.addItem(f"Wow Factor {i}", i)
        self.tome_wow_filter.currentTextChanged.connect(self._filter_tome)
        filter_row.addWidget(self.tome_wow_filter, 1)

        self.tome_excl_filter = QComboBox()
        self.tome_excl_filter.addItem("All Bodies", "")
        self.tome_excl_filter.addItem("Exclusive Only", "exclusive")
        self.tome_excl_filter.addItem("Non-Exclusive", "non-exclusive")
        self.tome_excl_filter.currentTextChanged.connect(self._filter_tome)
        filter_row.addWidget(self.tome_excl_filter, 1)

        layout.addLayout(filter_row)

        # Action bar: selection buttons + count
        action_row = QHBoxLayout()
        self.tome_count_lbl = QLabel(f"Showing {len(self._pets)} of {len(self._pets)} pets")
        self.tome_count_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        action_row.addWidget(self.tome_count_lbl)
        action_row.addStretch()

        set_p1_btn = ModernButton("Use as Pet 1", "secondary")
        set_p1_btn.clicked.connect(lambda: self._use_selected_pet(1))
        action_row.addWidget(set_p1_btn)

        set_p2_btn = ModernButton("Use as Pet 2", "secondary")
        set_p2_btn.clicked.connect(lambda: self._use_selected_pet(2))
        action_row.addWidget(set_p2_btn)
        layout.addLayout(action_row)

        # Tome Table
        self.tome_table = QTableWidget(0, 8)
        headers = ["Pet Name", "School", "Wow Factor", "Egg Name", "Exclusive", "Unhatchable", "Retired", "Special Body"]
        self.tome_table.setHorizontalHeaderLabels(headers)
        stretch_mode = QHeaderView.ResizeMode.Stretch if PyQt_Version == 6 else QHeaderView.Stretch
        resize_mode = QHeaderView.ResizeMode.ResizeToContents if PyQt_Version == 6 else QHeaderView.ResizeToContents
        self.tome_table.horizontalHeader().setSectionResizeMode(0, stretch_mode)
        for col in range(1, 8):
            self.tome_table.horizontalHeader().setSectionResizeMode(col, resize_mode)
        self.tome_table.verticalHeader().setVisible(False)
        no_edit = QTableWidget.EditTrigger.NoEditTriggers if PyQt_Version == 6 else QTableWidget.NoEditTriggers
        sel_row = QTableWidget.SelectionBehavior.SelectRows if PyQt_Version == 6 else QTableWidget.SelectRows
        sel_single = QTableWidget.SelectionMode.SingleSelection if PyQt_Version == 6 else QTableWidget.SingleSelection
        self.tome_table.setEditTriggers(no_edit)
        self.tome_table.setSelectionBehavior(sel_row)
        self.tome_table.setSelectionMode(sel_single)
        self.tome_table.setAlternatingRowColors(True)
        self.tome_table.doubleClicked.connect(lambda: self._use_selected_pet(1))
        layout.addWidget(self.tome_table)

        self._populate_tome_table(self._pets)

    def _populate_tome_table(self, pet_list):
        self.tome_table.setRowCount(len(pet_list))
        align_c = Qt.AlignmentFlag.AlignCenter if PyQt_Version == 6 else Qt.AlignCenter
        for row, p in enumerate(pet_list):
            name_item = QTableWidgetItem(p["name"])
            name_item.setForeground(QColor("#FAFAFA"))

            school = p.get("school", "")
            school_item = QTableWidgetItem(school)
            school_color = self.SCHOOL_COLORS.get(school, "#C0C0C0")
            school_item.setForeground(QColor(school_color))

            wf = p.get("wowFactor")
            wf_item = QTableWidgetItem(str(wf) if wf is not None else "—")
            wf_item.setTextAlignment(align_c)
            if wf is not None:
                wf_col = "#86EFAC" if wf <= 4 else ("#FDE68A" if wf <= 7 else "#FCA5A5")
                wf_item.setForeground(QColor(wf_col))

            egg_item = QTableWidgetItem(p.get("eggName", ""))
            egg_item.setForeground(QColor("#A0A0A0"))

            excl_item = QTableWidgetItem("Yes" if p.get("exclusive") else "No")
            excl_item.setTextAlignment(align_c)
            excl_item.setForeground(QColor("#F59E0B" if p.get("exclusive") else "#686868"))

            unhatch_item = QTableWidgetItem("Yes" if p.get("unhatchable") else "No")
            unhatch_item.setTextAlignment(align_c)
            unhatch_item.setForeground(QColor("#EF4444" if p.get("unhatchable") else "#686868"))

            ret_item = QTableWidgetItem("Yes" if p.get("retired") else "No")
            ret_item.setTextAlignment(align_c)
            ret_item.setForeground(QColor("#94A3B8" if p.get("retired") else "#686868"))

            spec_item = QTableWidgetItem("Yes" if p.get("specialBody") else "No")
            spec_item.setTextAlignment(align_c)
            spec_item.setForeground(QColor("#A855F7" if p.get("specialBody") else "#686868"))

            self.tome_table.setItem(row, 0, name_item)
            self.tome_table.setItem(row, 1, school_item)
            self.tome_table.setItem(row, 2, wf_item)
            self.tome_table.setItem(row, 3, egg_item)
            self.tome_table.setItem(row, 4, excl_item)
            self.tome_table.setItem(row, 5, unhatch_item)
            self.tome_table.setItem(row, 6, ret_item)
            self.tome_table.setItem(row, 7, spec_item)

        self.tome_count_lbl.setText(f"Showing {len(pet_list)} of {len(self._pets)} pets")

    def _filter_tome(self):
        query = self.tome_search.text().strip().lower()
        school = self.tome_school_filter.currentData()
        wf = self.tome_wow_filter.currentData()
        excl = self.tome_excl_filter.currentData()

        filtered = []
        for p in self._pets:
            if query and query not in p["name"].lower():
                continue
            if school and p.get("school") != school:
                continue
            if wf != "" and wf is not None and p.get("wowFactor") != wf:
                continue
            if excl == "exclusive" and not p.get("exclusive"):
                continue
            if excl == "non-exclusive" and p.get("exclusive"):
                continue
            filtered.append(p)

        self._populate_tome_table(filtered)

    def _use_selected_pet(self, slot=1):
        selected_rows = self.tome_table.selectedItems()
        if not selected_rows:
            return
        row = self.tome_table.currentRow()
        pet_name = self.tome_table.item(row, 0).text()
        if slot == 1:
            self.combo1.setCurrentText(pet_name)
        else:
            self.combo2.setCurrentText(pet_name)
        self.tabs.setCurrentIndex(0)

    def _show_how_to_use(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("How to Use — Pet WoW Returner")
        dlg.setModal(True)
        dlg.setFixedWidth(460)
        dlg.setStyleSheet("QDialog { background-color: #0E0E0E; color: #FAFAFA; border: 1px solid #282828; border-radius: 8px; } QLabel { color: #DADADA; }")
        l = QVBoxLayout(dlg)
        l.setContentsMargins(22, 22, 22, 22)
        l.setSpacing(14)
        t = QLabel("Pet Hatching & Wow Factor Guide")
        t.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF;")
        l.addWidget(t)
        b = QLabel(self.HOW_TO_USE)
        b.setWordWrap(True)
        b.setStyleSheet("font-size: 11px; color: #C0C0C0; line-height: 1.6;")
        l.addWidget(b)
        src = QLabel("Data and logic source: petbodyw101.vercel.app")
        src.setStyleSheet("font-size: 10px; color: #606060; font-style: italic;")
        l.addWidget(src)
        btn = ModernButton("Got it!", "primary")
        btn.clicked.connect(dlg.accept)
        l.addWidget(btn)
        dlg.exec()


# --- WIZARD101 PROCESS INSTANCE COUNTER ---
def count_wizard101_instances() -> int:
    """Count currently running Wizard101 game instances via Toolhelp32Snapshot"""
    try:
        TH32CS_SNAPPROCESS = 0x00000002
        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", ctypes.wintypes.DWORD),
                ("cntUsage", ctypes.wintypes.DWORD),
                ("th32ProcessID", ctypes.wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", ctypes.wintypes.DWORD),
                ("cntThreads", ctypes.wintypes.DWORD),
                ("th32ParentProcessID", ctypes.wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", ctypes.wintypes.DWORD),
                ("szExeFile", ctypes.c_char * 260)
            ]
        kernel32 = ctypes.windll.kernel32
        hSnapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if hSnapshot == -1:
            return 0
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        count = 0
        if kernel32.Process32First(hSnapshot, ctypes.byref(pe)):
            while True:
                exe_name = pe.szExeFile.decode("utf-8", errors="ignore").lower()
                if "wizardgraphicalclient" in exe_name or exe_name == "wizard101.exe":
                    count += 1
                if not kernel32.Process32Next(hSnapshot, ctypes.byref(pe)):
                    break
        kernel32.CloseHandle(hSnapshot)
        return count
    except Exception:
        return 0


# --- DISCORD RICH PRESENCE MANAGER ---
DISCORD_CLIENT_ID = "1548457677896552479"
DISCORD_PUBLIC_KEY = "a54892bf21252ecb833eaf099df7e0f202d161a535d8ad41655f404c0974a560"

class DiscordRPCManager:
    """Manages Discord Rich Presence via local IPC pipe in a background daemon thread"""
    def __init__(self, client_id=DISCORD_CLIENT_ID):
        self.client_id = client_id
        self.pipe = None
        self._connected = False
        self._running = False
        self.start_time = int(time.time())
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._close_pipe()

    def _connect_pipe(self):
        for i in range(10):
            pipe_name = rf"\\.\pipe\discord-ipc-{i}"
            try:
                self.pipe = open(pipe_name, "w+b")
                self._connected = True
                self._handshake()
                return True
            except (FileNotFoundError, PermissionError, OSError):
                continue
        return False

    def _send(self, op, payload):
        if not self.pipe:
            return
        data = json.dumps(payload).encode("utf-8")
        header = struct.pack("<II", op, len(data))
        self.pipe.write(header + data)
        self.pipe.flush()

    def _read(self):
        if not self.pipe:
            return None, None
        try:
            header = self.pipe.read(8)
            if len(header) < 8:
                return None, None
            op, length = struct.unpack("<II", header)
            data = self.pipe.read(length)
            return op, json.loads(data.decode("utf-8"))
        except Exception:
            return None, None

    def _handshake(self):
        self._send(0, {"v": 1, "client_id": self.client_id})
        self._read()

    def _close_pipe(self):
        if self.pipe:
            try:
                self._send(2, {})
                self.pipe.close()
            except Exception:
                pass
            self.pipe = None
        self._connected = False

    def _update_presence(self):
        if not self._connected:
            if not self._connect_pipe():
                return

        instances = count_wizard101_instances()
        details = "In Launcher"
        if instances == 0:
            state = "Ready to Launch"
        elif instances == 1:
            state = "1 Instance Open"
        else:
            state = f"{instances} Instances Open"

        buttons = [
            {
                "label": "Download Launcher",
                "url": "https://github.com/VaniMoe/Quick101/releases/latest"
            }
        ]

        activity = {
            "details": details,
            "state": state,
            "timestamps": {"start": self.start_time},
            "assets": {
                "large_text": "Quick101 - Wizard101 Launcher"
            },
            "buttons": buttons
        }

        payload = {
            "cmd": "SET_ACTIVITY",
            "args": {
                "pid": os.getpid(),
                "activity": activity
            },
            "nonce": str(uuid.uuid4())
        }

        try:
            self._send(1, payload)
            self._read()
        except Exception:
            self._close_pipe()

    def _loop(self):
        while self._running:
            try:
                self._update_presence()
            except Exception:
                pass
            for _ in range(12):
                if not self._running:
                    break
                time.sleep(1)


# --- DAMAGE CALCULATOR DIALOG ---
def _calc_boost(val: float) -> float:
    if val == 1:
        return 1.0
    r = val / 100.0
    return 1.0 + r if r != 0 else 0.0

def _calculate_damage_core(base_dmg, wizard_pct, wizard_flat, personal_aura, global_aura, enemy_boost, blades, traps) -> int:
    n = float(base_dmg)
    # 1. Wizard %
    if wizard_pct:
        n *= _calc_boost(wizard_pct)
    n = math.floor(n)
    
    # 2. Wizard Flat
    if wizard_flat:
        n += math.floor(wizard_flat)
        
    # 3. Personal Aura
    if personal_aura:
        n *= _calc_boost(personal_aura)
        n = math.floor(n)
        
    # 4. Blades (in order)
    for b in blades:
        if b:
            n *= _calc_boost(b)
            n = math.floor(n)
            
    # 5. Global Aura
    if global_aura:
        n *= _calc_boost(global_aura)
        n = math.floor(n)
        
    # 6. Traps (in reverse order as applied in game)
    for t in reversed(traps):
        if t:
            n *= _calc_boost(t)
            n = math.floor(n)
            
    # 7. Enemy internal boost
    if enemy_boost:
        n *= _calc_boost(enemy_boost)
        
    return math.floor(n)

class ChipButton(QPushButton):
    def __init__(self, text, remove_callback, is_trap=False, parent=None):
        super().__init__(f"{text} ✕", parent)
        cursor_ptr = Qt.CursorShape.PointingHandCursor if PyQt_Version == 6 else Qt.PointingHandCursor
        self.setCursor(cursor_ptr)
        if is_trap:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #31182A;
                    color: #F472B6;
                    border: 1px solid #EC4899;
                    border-radius: 12px;
                    padding: 3px 8px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #7F1D1D;
                    color: #FCA5A5;
                    border-color: #EF4444;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #1E293B;
                    color: #93C5FD;
                    border: 1px solid #3B82F6;
                    border-radius: 12px;
                    padding: 3px 8px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #7F1D1D;
                    color: #FCA5A5;
                    border-color: #EF4444;
                }
            """)
        self.clicked.connect(remove_callback)

class DamageCalculatorDialog(QDialog):
    """Wizard101 Damage Calculator — based on wizard101calculator.com formulas"""
    HOW_TO_USE = (
        "Wizard101 Damage Calculator Guide\n\n"
        "1. Select your Card Type:\n"
        "   • Single: One base damage number (e.g. 500)\n"
        "   • Min-Max: Damage range (e.g. 450 - 520)\n"
        "   • Damage Per Pip (DPP): Base × Pips + Enchant\n"
        "   • DoT: Initial Hit + Damage over 3 rounds\n\n"
        "2. Enter your Wizard Stats:\n"
        "   • Damage % from gear\n"
        "   • Flat Damage from jewels/gear\n"
        "   • Personal Aura % (e.g. 25% Frenzy)\n"
        "   • Global Bubble % (e.g. 25% Wyldfire)\n"
        "   • Enemy Internal Boost % (if applicable)\n\n"
        "3. Add Blades and Traps:\n"
        "   • Use quick buttons (+35%, +45%, Trap +40%, Potent Trap +50%, Feint +70%, Mass/Item +75%, Potent Feint +80%) or custom %\n"
        "   • Click any chip to remove it\n\n"
        "Order of calculation matches in-game order:\n"
        "Base → Gear % → Flat → Aura → Blades → Bubble → Traps → Enemy Boost.\n\n"
        "Formula source: wizard101calculator.com"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick101 — Wizard101 Damage Calculator")
        self.setModal(True)
        self.resize(880, 720)
        self.setMinimumSize(800, 620)

        self._blades: List[float] = []
        self._traps: List[float] = []

        self.setStyleSheet("""
            QDialog {
                background-color: #0E0E0E;
                color: #FAFAFA;
                border: 1px solid #282828;
                border-radius: 8px;
            }
            QLabel { color: #FAFAFA; }
            QGroupBox {
                color: #FAFAFA;
                font-size: 11px;
                font-weight: 700;
                border: 1px solid #242424;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #141414;
                color: #FAFAFA;
                border: 1px solid #2A2A2A;
                border-radius: 5px;
                padding: 5px 8px;
                font-size: 12px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 1px solid #606060;
            }
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 0;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background: #0E0E0E;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #333333;
                border-radius: 4px;
            }
        """)

        self._build_ui()
        self._recalculate()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        # Title bar
        title_row = QHBoxLayout()
        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        title_lbl = QLabel("Wizard101 Damage Calculator")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        v_title.addWidget(title_lbl)
        sub_lbl = QLabel("Exact in-game spell damage calculation (wizard101calculator.com)")
        sub_lbl.setStyleSheet("color: #707070; font-size: 11px;")
        v_title.addWidget(sub_lbl)
        title_row.addLayout(v_title)
        title_row.addStretch()

        help_btn = ModernButton("How to Use", "secondary")
        help_btn.clicked.connect(self._show_how_to_use)
        title_row.addWidget(help_btn)
        root.addLayout(title_row)

        # Main scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 1. Mode Selector
        mode_box = QGroupBox("CARD DAMAGE TYPE")
        mode_l = QHBoxLayout(mode_box)
        mode_l.setSpacing(12)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Single Damage",
            "Min - Max Damage",
            "Damage Per Pip (DPP)",
            "Damage + Over 3 Rounds (DoT)"
        ])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_l.addWidget(QLabel("Spell Mode:"))
        mode_l.addWidget(self.mode_combo, 1)

        # Critical Multiplier
        mode_l.addWidget(QLabel("Critical Multiplier:"))
        self.crit_combo = QComboBox()
        self.crit_combo.addItems(["2.0x", "1.9x", "1.8x", "1.7x", "1.6x", "1.5x", "1.4x", "1.3x", "1.25x"])
        self.crit_combo.currentIndexChanged.connect(self._recalculate)
        mode_l.addWidget(self.crit_combo)
        layout.addWidget(mode_box)

        # 2. Card Damage Inputs (Stacked Widget)
        self.inputs_box = QGroupBox("CARD BASE DAMAGE")
        in_l = QVBoxLayout(self.inputs_box)
        self.card_stack = QStackedWidget()

        # Page 0: Single
        p0 = QWidget()
        p0_l = QHBoxLayout(p0)
        p0_l.addWidget(QLabel("Base Card Damage:"))
        self.single_dmg = QSpinBox()
        self.single_dmg.setRange(0, 99999)
        self.single_dmg.setValue(500)
        self.single_dmg.valueChanged.connect(self._recalculate)
        p0_l.addWidget(self.single_dmg)
        p0_l.addStretch()
        self.card_stack.addWidget(p0)

        # Page 1: Min-Max
        p1 = QWidget()
        p1_l = QHBoxLayout(p1)
        p1_l.addWidget(QLabel("Min Damage:"))
        self.min_dmg = QSpinBox()
        self.min_dmg.setRange(0, 99999)
        self.min_dmg.setValue(450)
        self.min_dmg.valueChanged.connect(self._recalculate)
        p1_l.addWidget(self.min_dmg)
        p1_l.addWidget(QLabel("Max Damage:"))
        self.max_dmg = QSpinBox()
        self.max_dmg.setRange(0, 99999)
        self.max_dmg.setValue(520)
        self.max_dmg.valueChanged.connect(self._recalculate)
        p1_l.addWidget(self.max_dmg)
        p1_l.addStretch()
        self.card_stack.addWidget(p1)

        # Page 2: DPP
        p2 = QWidget()
        p2_l = QHBoxLayout(p2)
        p2_l.addWidget(QLabel("Damage per Pip:"))
        self.dpp_dmg = QSpinBox()
        self.dpp_dmg.setRange(0, 99999)
        self.dpp_dmg.setValue(100)
        self.dpp_dmg.valueChanged.connect(self._recalculate)
        p2_l.addWidget(self.dpp_dmg)
        p2_l.addWidget(QLabel("Total Pips:"))
        self.dpp_pips = QSpinBox()
        self.dpp_pips.setRange(1, 14)
        self.dpp_pips.setValue(7)
        self.dpp_pips.valueChanged.connect(self._recalculate)
        p2_l.addWidget(self.dpp_pips)
        p2_l.addWidget(QLabel("Enchant (Flat):"))
        self.dpp_enchant = QSpinBox()
        self.dpp_enchant.setRange(0, 9999)
        self.dpp_enchant.setValue(0)
        self.dpp_enchant.valueChanged.connect(self._recalculate)
        p2_l.addWidget(self.dpp_enchant)
        p2_l.addStretch()
        self.card_stack.addWidget(p2)

        # Page 3: DoT
        p3 = QWidget()
        p3_l = QHBoxLayout(p3)
        p3_l.addWidget(QLabel("Initial Hit:"))
        self.dot_hit = QSpinBox()
        self.dot_hit.setRange(0, 99999)
        self.dot_hit.setValue(100)
        self.dot_hit.valueChanged.connect(self._recalculate)
        p3_l.addWidget(self.dot_hit)
        p3_l.addWidget(QLabel("Damage Over 3 Rounds:"))
        self.dot_over = QSpinBox()
        self.dot_over.setRange(0, 99999)
        self.dot_over.setValue(600)
        self.dot_over.valueChanged.connect(self._recalculate)
        p3_l.addWidget(self.dot_over)
        p3_l.addStretch()
        self.card_stack.addWidget(p3)

        in_l.addWidget(self.card_stack)
        layout.addWidget(self.inputs_box)

        # 3. Wizard Stats & Auras
        stats_box = QGroupBox("WIZARD STATS & AURAS")
        stats_l = QGridLayout(stats_box)
        stats_l.setSpacing(10)

        stats_l.addWidget(QLabel("Wizard Damage % (Gear):"), 0, 0)
        self.stat_pct = QSpinBox()
        self.stat_pct.setRange(0, 500)
        self.stat_pct.setValue(150)
        self.stat_pct.valueChanged.connect(self._recalculate)
        stats_l.addWidget(self.stat_pct, 0, 1)

        stats_l.addWidget(QLabel("Wizard Flat Damage (Gear/Jewel):"), 0, 2)
        self.stat_flat = QSpinBox()
        self.stat_flat.setRange(0, 500)
        self.stat_flat.setValue(30)
        self.stat_flat.valueChanged.connect(self._recalculate)
        stats_l.addWidget(self.stat_flat, 0, 3)

        stats_l.addWidget(QLabel("Personal Aura % (e.g. Frenzy):"), 1, 0)
        self.stat_aura = QSpinBox()
        self.stat_aura.setRange(-100, 200)
        self.stat_aura.setValue(25)
        self.stat_aura.valueChanged.connect(self._recalculate)
        stats_l.addWidget(self.stat_aura, 1, 1)

        stats_l.addWidget(QLabel("Global Aura / Bubble %:"), 1, 2)
        self.stat_bubble = QSpinBox()
        self.stat_bubble.setRange(-100, 200)
        self.stat_bubble.setValue(0)
        self.stat_bubble.valueChanged.connect(self._recalculate)
        stats_l.addWidget(self.stat_bubble, 1, 3)

        stats_l.addWidget(QLabel("Enemy Internal Boost %:"), 2, 0)
        self.stat_enemy = QSpinBox()
        self.stat_enemy.setRange(-100, 200)
        self.stat_enemy.setValue(0)
        self.stat_enemy.valueChanged.connect(self._recalculate)
        stats_l.addWidget(self.stat_enemy, 2, 1)

        layout.addWidget(stats_box)

        # 4. Blades
        blades_box = QGroupBox("BLADES (POSITIVE MODIFIERS)")
        blades_l = QVBoxLayout(blades_box)
        b_add_row = QHBoxLayout()
        self.blade_input = QSpinBox()
        self.blade_input.setRange(-100, 200)
        self.blade_input.setValue(35)
        b_add_row.addWidget(self.blade_input)
        add_b_btn = ModernButton("+ Add Blade", "secondary")
        add_b_btn.clicked.connect(self._add_custom_blade)
        b_add_row.addWidget(add_b_btn)

        # Quick blade buttons
        cursor_ptr = Qt.CursorShape.PointingHandCursor if PyQt_Version == 6 else Qt.PointingHandCursor
        for val in [30, 35, 40, 45, 50]:
            qb = QPushButton(f"+{val}%")
            qb.setCursor(cursor_ptr)
            qb.setStyleSheet("background-color: #1A1A1A; color: #D0D0D0; border: 1px solid #333333; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
            qb.clicked.connect(lambda _, v=val: self._add_blade(v))
            b_add_row.addWidget(qb)

        clear_b_btn = QPushButton("Clear All")
        clear_b_btn.setCursor(cursor_ptr)
        clear_b_btn.setStyleSheet("background-color: #2D1515; color: #F87171; border: 1px solid #7F1D1D; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        clear_b_btn.clicked.connect(self._clear_blades)
        b_add_row.addWidget(clear_b_btn)
        b_add_row.addStretch()
        blades_l.addLayout(b_add_row)

        self.blades_chip_layout = QHBoxLayout()
        self.blades_chip_layout.setSpacing(6)
        self.blades_empty_lbl = QLabel("No blades added. Use buttons above to add.")
        self.blades_empty_lbl.setStyleSheet("color: #606060; font-size: 11px; font-style: italic;")
        self.blades_chip_layout.addWidget(self.blades_empty_lbl)
        self.blades_chip_layout.addStretch()
        blades_l.addLayout(self.blades_chip_layout)
        layout.addWidget(blades_box)

        # 5. Traps
        traps_box = QGroupBox("TRAPS (NEGATIVE MODIFIERS)")
        traps_l = QVBoxLayout(traps_box)
        t_add_row = QHBoxLayout()
        self.trap_input = QSpinBox()
        self.trap_input.setRange(-100, 200)
        self.trap_input.setValue(70)
        t_add_row.addWidget(self.trap_input)
        add_t_btn = ModernButton("+ Add Trap", "secondary")
        add_t_btn.clicked.connect(self._add_custom_trap)
        t_add_row.addWidget(add_t_btn)

        # Quick trap buttons
        for val, label in [(25, "+25%"), (30, "+30%"), (35, "+35%"), (40, "+40% School"), (50, "+50% Potent"), (70, "+70% Feint"), (75, "+75% Mass / Item"), (80, "+80% Potent Feint")]:
            qt = QPushButton(label)
            qt.setCursor(cursor_ptr)
            qt.setStyleSheet("background-color: #1A1A1A; color: #D0D0D0; border: 1px solid #333333; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
            qt.clicked.connect(lambda _, v=val: self._add_trap(v))
            t_add_row.addWidget(qt)

        clear_t_btn = QPushButton("Clear All")
        clear_t_btn.setCursor(cursor_ptr)
        clear_t_btn.setStyleSheet("background-color: #2D1515; color: #F87171; border: 1px solid #7F1D1D; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        clear_t_btn.clicked.connect(self._clear_traps)
        t_add_row.addWidget(clear_t_btn)
        t_add_row.addStretch()
        traps_l.addLayout(t_add_row)

        self.traps_chip_layout = QHBoxLayout()
        self.traps_chip_layout.setSpacing(6)
        self.traps_empty_lbl = QLabel("No traps added. Use buttons above to add.")
        self.traps_empty_lbl.setStyleSheet("color: #606060; font-size: 11px; font-style: italic;")
        self.traps_chip_layout.addWidget(self.traps_empty_lbl)
        self.traps_chip_layout.addStretch()
        traps_l.addLayout(self.traps_chip_layout)
        layout.addWidget(traps_box)

        # 6. Results Box
        res_box = QGroupBox("CALCULATED DAMAGE OUTPUT")
        res_l = QVBoxLayout(res_box)
        res_l.setContentsMargins(16, 16, 16, 16)
        res_l.setSpacing(10)

        out_row = QHBoxLayout()
        v_norm = QVBoxLayout()
        v_norm.setSpacing(2)
        lbl_n = QLabel("NORMAL DAMAGE")
        lbl_n.setStyleSheet("font-size: 10px; font-weight: bold; color: #94A3B8;")
        v_norm.addWidget(lbl_n)
        self.res_normal_lbl = QLabel("0")
        self.res_normal_lbl.setStyleSheet("font-size: 26px; font-weight: bold; color: #FAFAFA;")
        v_norm.addWidget(self.res_normal_lbl)
        out_row.addLayout(v_norm)

        out_row.addStretch()

        align_r = Qt.AlignmentFlag.AlignRight if PyQt_Version == 6 else Qt.AlignRight
        v_crit = QVBoxLayout()
        v_crit.setSpacing(2)
        v_crit.setAlignment(align_r)
        lbl_c = QLabel("CRITICAL DAMAGE")
        lbl_c.setStyleSheet("font-size: 10px; font-weight: bold; color: #F59E0B;")
        lbl_c.setAlignment(align_r)
        v_crit.addWidget(lbl_c)
        self.res_crit_lbl = QLabel("0")
        self.res_crit_lbl.setStyleSheet("font-size: 26px; font-weight: bold; color: #FBBF24;")
        self.res_crit_lbl.setAlignment(align_r)
        v_crit.addWidget(self.res_crit_lbl)
        out_row.addLayout(v_crit)
        res_l.addLayout(out_row)

        self.res_sub_lbl = QLabel("")
        self.res_sub_lbl.setStyleSheet("font-size: 12px; color: #86EFAC; font-weight: 600;")
        res_l.addWidget(self.res_sub_lbl)

        layout.addWidget(res_box)

        scroll.setWidget(container)
        root.addWidget(scroll)

        # Footer Buttons
        f_row = QHBoxLayout()
        reset_btn = ModernButton("Reset Defaults", "secondary")
        reset_btn.clicked.connect(self._reset_defaults)
        f_row.addWidget(reset_btn)
        f_row.addStretch()
        close_btn = ModernButton("Close", "primary")
        close_btn.clicked.connect(self.accept)
        f_row.addWidget(close_btn)
        root.addLayout(f_row)

    def _on_mode_changed(self, idx):
        self.card_stack.setCurrentIndex(idx)
        self._recalculate()

    def _add_blade(self, val):
        self._blades.append(float(val))
        self._refresh_chips()
        self._recalculate()

    def _add_custom_blade(self):
        val = self.blade_input.value()
        if val != 0:
            self._add_blade(val)

    def _remove_blade(self, idx):
        if 0 <= idx < len(self._blades):
            self._blades.pop(idx)
            self._refresh_chips()
            self._recalculate()

    def _clear_blades(self):
        self._blades.clear()
        self._refresh_chips()
        self._recalculate()

    def _add_trap(self, val):
        self._traps.append(float(val))
        self._refresh_chips()
        self._recalculate()

    def _add_custom_trap(self):
        val = self.trap_input.value()
        if val != 0:
            self._add_trap(val)

    def _remove_trap(self, idx):
        if 0 <= idx < len(self._traps):
            self._traps.pop(idx)
            self._refresh_chips()
            self._recalculate()

    def _clear_traps(self):
        self._traps.clear()
        self._refresh_chips()
        self._recalculate()

    def _refresh_chips(self):
        while self.blades_chip_layout.count():
            item = self.blades_chip_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self._blades:
            self.blades_empty_lbl = QLabel("No blades added. Use buttons above to add.")
            self.blades_empty_lbl.setStyleSheet("color: #606060; font-size: 11px; font-style: italic;")
            self.blades_chip_layout.addWidget(self.blades_empty_lbl)
        else:
            for idx, b in enumerate(self._blades):
                chip = ChipButton(f"+{int(b)}%" if b > 0 else f"{int(b)}%", lambda _, i=idx: self._remove_blade(i), is_trap=False)
                self.blades_chip_layout.addWidget(chip)
        self.blades_chip_layout.addStretch()

        while self.traps_chip_layout.count():
            item = self.traps_chip_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self._traps:
            self.traps_empty_lbl = QLabel("No traps added. Use buttons above to add.")
            self.traps_empty_lbl.setStyleSheet("color: #606060; font-size: 11px; font-style: italic;")
            self.traps_chip_layout.addWidget(self.traps_empty_lbl)
        else:
            for idx, t in enumerate(self._traps):
                chip = ChipButton(f"+{int(t)}%" if t > 0 else f"{int(t)}%", lambda _, i=idx: self._remove_trap(i), is_trap=True)
                self.traps_chip_layout.addWidget(chip)
        self.traps_chip_layout.addStretch()

    def _get_crit_mult(self):
        txt = self.crit_combo.currentText().replace("x", "")
        try:
            return float(txt)
        except ValueError:
            return 2.0

    def _recalculate(self):
        mode = self.mode_combo.currentIndex()
        w_pct = self.stat_pct.value()
        w_flat = self.stat_flat.value()
        aura = self.stat_aura.value()
        bubble = self.stat_bubble.value()
        enemy = self.stat_enemy.value()
        crit_m = self._get_crit_mult()

        if mode == 0:  # Single
            base = self.single_dmg.value()
            dmg = _calculate_damage_core(base, w_pct, w_flat, aura, bubble, enemy, self._blades, self._traps)
            crit = math.floor(dmg * crit_m)
            self.res_normal_lbl.setText(f"{dmg:,}")
            self.res_crit_lbl.setText(f"{crit:,}")
            self.res_sub_lbl.setText("")

        elif mode == 1:  # Min-Max
            b_min = self.min_dmg.value()
            b_max = self.max_dmg.value()
            d_min = _calculate_damage_core(b_min, w_pct, w_flat, aura, bubble, enemy, self._blades, self._traps)
            d_max = _calculate_damage_core(b_max, w_pct, w_flat, aura, bubble, enemy, self._blades, self._traps)
            c_min = math.floor(d_min * crit_m)
            c_max = math.floor(d_max * crit_m)
            self.res_normal_lbl.setText(f"{d_min:,} – {d_max:,}")
            self.res_crit_lbl.setText(f"{c_min:,} – {c_max:,}")
            self.res_sub_lbl.setText(f"Average: ~{math.floor((d_min + d_max)/2):,} (Crit: ~{math.floor((c_min + c_max)/2):,})")

        elif mode == 2:  # DPP
            pips = self.dpp_pips.value()
            per_pip = self.dpp_dmg.value()
            enchant = self.dpp_enchant.value()
            base = per_pip * pips + enchant
            dmg = _calculate_damage_core(base, w_pct, w_flat, aura, bubble, enemy, self._blades, self._traps)
            crit = math.floor(dmg * crit_m)
            self.res_normal_lbl.setText(f"{dmg:,}")
            self.res_crit_lbl.setText(f"{crit:,}")
            self.res_sub_lbl.setText(f"Base card: {per_pip} × {pips} pips + {enchant} enchant = {base} base dmg")

        elif mode == 3:  # DoT
            hit = self.dot_hit.value()
            over = self.dot_over.value()
            d_hit = _calculate_damage_core(hit, w_pct, w_flat, aura, bubble, enemy, self._blades, self._traps)
            d_over = _calculate_damage_core(over, w_pct, w_flat, aura, bubble, enemy, self._blades, self._traps)
            per_rnd = math.floor(d_over / 3)
            c_hit = math.floor(d_hit * crit_m)
            c_per_rnd = math.floor(per_rnd * crit_m)
            total_norm = d_hit + (per_rnd * 3)
            total_crit = c_hit + (c_per_rnd * 3)

            self.res_normal_lbl.setText(f"Hit: {d_hit:,} | +{per_rnd:,}/rnd")
            self.res_crit_lbl.setText(f"Hit: {c_hit:,} | +{c_per_rnd:,}/rnd")
            self.res_sub_lbl.setText(f"Total Normal: {total_norm:,}  ·  Total Critical: {total_crit:,}")

    def _reset_defaults(self):
        self.single_dmg.setValue(500)
        self.min_dmg.setValue(450)
        self.max_dmg.setValue(520)
        self.dpp_dmg.setValue(100)
        self.dpp_pips.setValue(7)
        self.dpp_enchant.setValue(0)
        self.dot_hit.setValue(100)
        self.dot_over.setValue(600)
        self.stat_pct.setValue(150)
        self.stat_flat.setValue(30)
        self.stat_aura.setValue(25)
        self.stat_bubble.setValue(0)
        self.stat_enemy.setValue(0)
        self.crit_combo.setCurrentIndex(0)
        self._clear_blades()
        self._clear_traps()
        self._recalculate()

    def _show_how_to_use(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("How to Use — Damage Calculator")
        dlg.setModal(True)
        dlg.setFixedWidth(460)
        dlg.setStyleSheet("QDialog { background-color: #0E0E0E; color: #FAFAFA; border: 1px solid #282828; border-radius: 8px; } QLabel { color: #DADADA; }")
        l = QVBoxLayout(dlg)
        l.setContentsMargins(22, 22, 22, 22)
        l.setSpacing(14)
        t = QLabel("Damage Calculator Guide")
        t.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF;")
        l.addWidget(t)
        b = QLabel(self.HOW_TO_USE)
        b.setWordWrap(True)
        b.setStyleSheet("font-size: 11px; color: #C0C0C0; line-height: 1.6;")
        l.addWidget(b)
        src = QLabel("Formula source: wizard101calculator.com")
        src.setStyleSheet("font-size: 10px; color: #606060; font-style: italic;")
        l.addWidget(src)
        btn = ModernButton("Got it!", "primary")
        btn.clicked.connect(dlg.accept)
        l.addWidget(btn)
        dlg.exec()


# --- MAIN MODERN LAUNCHER ---
class Quick101Launcher(QMainWindow):
   
    
    def __init__(self):
        super().__init__()
        self.bg_manager = BackgroundManager(self)
        self.current_theme = ModernThemes.get_theme(_cfg.get('theme_index', 0))
        
        # Launch throttling to prevent spam clicking "Run Selected"
        self.last_launch_time = 0
        self.launch_delay = 2000  # 2 seconds minimum between launches
        
        self.setup_ui()
        self.apply_theme()
        self.load_categories()
        self.update_wizard_path_display()
        self.apply_background()
        
        # Trigger First Time Setup if not completed or fresh install
        if not _cfg.get('first_time_setup_completed', False) or self.is_first_run():
            QTimer.singleShot(350, self.open_first_time_setup)
            
        # Auto-updater in background
        self.updater = GitHubUpdater(self)
        self.updater.update_available.connect(self.show_update_dialog)
        QTimer.singleShot(2500, lambda: self.updater.check_updates_async(notify_if_no_update=False))
        
        # Activate Compact Mode immediately if enabled in settings (persists across restart)
        if _cfg.get('compact_mode', False):
            QTimer.singleShot(0, lambda: self.switch_to_compact_mode(save=False))

        # Discord Rich Presence
        try:
            self.discord_rpc = DiscordRPCManager()
            self.discord_rpc.start()
        except Exception as e:
            log_event(f"Discord RPC init failed: {e}", "WARNING")
            self.discord_rpc = None
        
    def show_update_dialog(self, version: str, notes: str, download_url: str):
        """Display dialog when a new GitHub release is available"""
        dlg = UpdateDialog(self, version, notes, download_url, self.updater)
        dlg.exec()
        
    def is_first_run(self) -> bool:
        """Check if launcher has no configured accounts yet"""
        acc_data = load_yaml(ACCOUNT_FILE)
        if not acc_data:
            return True
        categories = list(acc_data.keys())
        if len(categories) == 0:
            return True
        if len(categories) == 1 and categories[0] == 'Default':
            accounts = acc_data['Default']
            if not accounts or (len(accounts) == 1 and 'Sample' in accounts):
                return True
        return False
        
    def open_first_time_setup(self):
        """Open First Time Setup wizard"""
        dialog = FirstTimeSetupDialog(self)
        if dialog.exec() == (QDialog.DialogCode.Accepted if PyQt_Version == 6 else QDialog.Accepted):
            self.load_categories()
            self.update_wizard_path_display()
            self.update_status("First Time Setup completed!")
        
    def setup_ui(self):
        """Setup the main user interface with custom frameless top bar"""
        self.setWindowTitle("Quick101")
        
        # Frameless window - custom sleek title bar without OS title/icon
        self.setWindowFlags(self.windowFlags() | (Qt.WindowType.FramelessWindowHint if PyQt_Version == 6 else Qt.FramelessWindowHint))
        
        # Window icon
        icon_path = get_app_icon_path(prefer_ico=True)
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Central widget
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        central_widget.setStyleSheet("""
            QWidget#CentralWidget {
                background-color: #0A0A0A;
                border: 1px solid #242424;
            }
        """)
        self.setCentralWidget(central_widget)
        
        # Magic Particle Background
        self.magic_particles = MagicParticleWidget(central_widget)
        self.magic_particles.setGeometry(0, 0, self.width(), self.height())
        self.magic_particles.lower()
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Custom Titlebar: no title, no icon, Create by Vani, Settings button, and window controls
        self.title_bar = CustomTitleBar(self)
        main_layout.addWidget(self.title_bar)
        
        # Mode Stack: Index 0 = Full Launcher, Index 1 = Compact Mode
        self.mode_stack = QStackedWidget()
        main_layout.addWidget(self.mode_stack)
        
        # --- Page 0: Full Launcher ---
        self.full_widget = QWidget()
        full_layout = QVBoxLayout(self.full_widget)
        full_layout.setSpacing(0)
        full_layout.setContentsMargins(0, 0, 0, 0)
        self.create_header(full_layout)
        self.create_main_content(full_layout)
        self.create_status_bar()
        self.mode_stack.addWidget(self.full_widget)
        
        # --- Page 1: Compact Mode ---
        self.compact_widget = self.create_compact_container()
        self.mode_stack.addWidget(self.compact_widget)
        
        # Window geometry & initial mode
        if _cfg.get('compact_mode', False):
            self.mode_stack.setCurrentIndex(1)
            self.setMinimumSize(340, 400)
            self.setMaximumSize(460, 480)
            self.resize(360, 410)
            if hasattr(self, 'status_bar') and self.status_bar:
                self.status_bar.hide()
        else:
            self.setMinimumSize(900, 700)
            size = _cfg.get('window_size', [1100, 800])
            pos = _cfg.get('window_position', [100, 100])
            self.resize(size[0], size[1])
            self.move(pos[0], pos[1])
        
    def create_compact_container(self) -> QWidget:
        """Create the ultra-clean, minimal Compact Mode widget with 1 custom dropdown, 1 Launch button, and expand button"""
        compact_widget = QWidget()
        compact_widget.setObjectName("CompactContainer")
        compact_layout = QVBoxLayout(compact_widget)
        compact_layout.setContentsMargins(22, 14, 22, 14)
        compact_layout.setSpacing(10)
        
        # Header: Mini brand logo + Title + Compact Mode badge
        header = QHBoxLayout()
        header.setSpacing(10)
        
        logo = QLabel()
        logo.setFixedSize(28, 28)
        logo.setScaledContents(True)
        icon_path = get_app_icon_path(prefer_ico=False)
        if icon_path and os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio if PyQt_Version == 6 else Qt.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation if PyQt_Version == 6 else Qt.SmoothTransformation)
            logo.setPixmap(pix)
        header.addWidget(logo)
        
        title = QLabel("QUICK101")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF; letter-spacing: 2px;")
        header.addWidget(title)
        
        badge = QLabel("COMPACT")
        badge.setStyleSheet("background-color: #222222; color: #FAFAFA; font-size: 9px; font-weight: bold; padding: 3px 8px; border-radius: 4px; border: 1px solid #383838; letter-spacing: 1px;")
        header.addWidget(badge)
        header.addStretch()
        compact_layout.addLayout(header)
        
        # Compact Card Container
        card = QWidget()
        card.setObjectName("CompactCard")
        card.setMinimumHeight(154)
        card.setStyleSheet("""
            QWidget#CompactCard {
                background-color: #121212;
                border: 1px solid #282828;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 16)
        card_layout.setSpacing(10)
        
        # 1. Custom-designed Dropdown
        dropdown_label = QLabel("ACCOUNT")
        dropdown_label.setFixedHeight(14)
        dropdown_label.setStyleSheet("color: #707070; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        card_layout.addWidget(dropdown_label)
        
        self.compact_account_combo = QComboBox()
        self.compact_account_combo.setObjectName("CompactCombo")
        self.compact_account_combo.setFixedHeight(40)
        self.compact_account_combo.setStyleSheet("""
            QComboBox#CompactCombo {
                background-color: #181818;
                color: #FFFFFF;
                border: 1px solid #323232;
                border-radius: 6px;
                padding: 0px 14px;
                font-size: 12px;
                font-weight: 600;
                font-family: 'Segoe UI';
            }
            QComboBox#CompactCombo:hover {
                border: 1px solid #606060;
                background-color: #1D1D1D;
            }
            QComboBox#CompactCombo:focus {
                border: 1px solid #909090;
            }
            QComboBox#CompactCombo::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 34px;
                border-left: 1px solid #2A2A2A;
                background-color: #181818;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QComboBox#CompactCombo::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #FFFFFF;
                width: 0px;
                height: 0px;
            }
            QComboBox#CompactCombo QAbstractItemView {
                background-color: #141414;
                color: #FAFAFA;
                border: 1px solid #333333;
                border-radius: 6px;
                selection-background-color: #282828;
                selection-color: #FFFFFF;
                outline: none;
                padding: 4px;
                font-size: 12px;
            }
            QComboBox#CompactCombo QAbstractItemView::item {
                min-height: 30px;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QComboBox#CompactCombo QAbstractItemView::item:hover {
                background-color: #222222;
                color: #FFFFFF;
            }
            QComboBox#CompactCombo QAbstractItemView::item:selected {
                background-color: #2E2E2E;
                color: #FFFFFF;
            }
        """)
        card_layout.addWidget(self.compact_account_combo)
        
        # 2. Launch Button (large, bold, responsive)
        self.compact_start_btn = QPushButton("LAUNCH")
        self.compact_start_btn.setFixedHeight(44)
        self.compact_start_btn.setCursor(Qt.CursorShape.PointingHandCursor if PyQt_Version == 6 else Qt.PointingHandCursor)
        self.compact_start_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #000000;
                border: none;
                border-radius: 6px;
                font-family: 'Segoe UI';
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 2px;
            }
            QPushButton:hover {
                background-color: #E2E2E2;
            }
            QPushButton:pressed {
                background-color: #B5B5B5;
            }
            QPushButton:disabled {
                background-color: #404040;
                color: #888888;
            }
        """)
        self.compact_start_btn.clicked.connect(self.launch_compact_account)
        card_layout.addWidget(self.compact_start_btn)
        
        compact_layout.addWidget(card)
        compact_layout.addStretch()
        
        # 3. Bottom Button to show full launcher
        self.compact_full_launcher_btn = QPushButton("Show Full Launcher")
        self.compact_full_launcher_btn.setFixedHeight(34)
        self.compact_full_launcher_btn.setCursor(Qt.CursorShape.PointingHandCursor if PyQt_Version == 6 else Qt.PointingHandCursor)
        self.compact_full_launcher_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #808080;
                border: 1px solid #282828;
                border-radius: 6px;
                font-family: 'Segoe UI';
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #181818;
                color: #FFFFFF;
                border-color: #484848;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
        """)
        self.compact_full_launcher_btn.clicked.connect(self.switch_to_full_mode)
        compact_layout.addWidget(self.compact_full_launcher_btn)

        # 4. Made by Vani footer
        compact_footer = QHBoxLayout()
        compact_footer.setContentsMargins(0, 4, 0, 0)
        compact_footer.addStretch()
        
        c_made_by = QLabel("Made by")
        c_made_by.setStyleSheet("color: #606060; font-size: 10px;")
        compact_footer.addWidget(c_made_by)
        
        c_vani = QPushButton("Vani")
        c_vani.setCursor(Qt.CursorShape.PointingHandCursor if PyQt_Version == 6 else Qt.PointingHandCursor)
        c_vani.setToolTip("Open Discord Chat with Vani (ID: 622454645742108692)")
        c_vani.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #A78BFA;
                border: none;
                font-size: 10px;
                font-weight: bold;
                padding: 0px 2px;
                text-decoration: underline;
            }
            QPushButton:hover {
                color: #C4B5FD;
            }
        """)
        c_vani.clicked.connect(self.open_vani_discord)
        compact_footer.addWidget(c_vani)
        compact_layout.addLayout(compact_footer)
        
        return compact_widget
        
    def populate_compact_accounts(self):
        """Populate compact mode dropdown with accounts and official Steam vector icons"""
        if not hasattr(self, 'compact_account_combo'):
            return
            
        self.compact_account_combo.clear()
        self.compact_account_combo.setIconSize(QSize(16, 16))
        acc_data = load_yaml(ACCOUNT_FILE)
        if not acc_data:
            self.compact_account_combo.addItem("No accounts found", None)
            return
            
        last_saved = _cfg.get('compact_selected_account', None)
        selected_idx = 0
        idx = 0
        
        for category, accounts in acc_data.items():
            if not isinstance(accounts, dict):
                continue
            for nick, acc_info in accounts.items():
                is_steam = acc_info.get('steam', False) if isinstance(acc_info, dict) else False
                cat_tag = f"  [{category}]" if len(acc_data) > 1 else ""
                display_label = f"{nick}{cat_tag}"
                item_icon = create_vector_icon('steam', '#FAFAFA', 16) if is_steam else QIcon()
                self.compact_account_combo.addItem(item_icon, display_label, (category, nick))
                if last_saved and [category, nick] == list(last_saved):
                    selected_idx = idx
                idx += 1
                
        if self.compact_account_combo.count() > 0:
            self.compact_account_combo.setCurrentIndex(selected_idx)
            
    def launch_compact_account(self):
        """Launch selected account from Compact Mode with Steam support"""
        current_data = self.compact_account_combo.currentData()
        if not current_data:
            QMessageBox.warning(self, "No Account", "Please configure an account first in Full Launcher.")
            return
            
        category, nickname = current_data
        _cfg['compact_selected_account'] = [category, nickname]
        save_config(_cfg)
        
        # Check throttling
        current_time = time.time() * 1000
        if current_time - self.last_launch_time < self.launch_delay:
            return
        self.last_launch_time = current_time
        
        _, account_data = load_account(category, nickname)
        if not account_data or 'username' not in account_data:
            QMessageBox.critical(self, "Error", f"Account data for {nickname} not found!")
            return

        if is_account_already_running(nickname):
            dlg = AccountAlreadyOpenDialog(self, nickname)
            if dlg.exec() != (QDialog.DialogCode.Accepted if PyQt_Version == 6 else QDialog.Accepted):
                return
            
        timeout = _cfg.get('auto_login_timeout', 10)
        is_steam = account_data.get('steam', False) if isinstance(account_data, dict) else False
        
        self.compact_start_btn.setText("STARTING...")
        self.compact_start_btn.setEnabled(False)
        
        def run_launch():
            launch_with_credentials(
                account_data['username'], account_data['password'], nickname, timeout, is_steam=is_steam
            )
            QTimer.singleShot(1500, self.reset_compact_start_btn)
            
        threading.Thread(target=run_launch, daemon=True).start()
        
    def reset_compact_start_btn(self):
        """Reset compact start button text and enabled state"""
        self.compact_start_btn.setText("LAUNCH")
        self.compact_start_btn.setEnabled(True)
        
    def switch_to_compact_mode(self, save: bool = True):
        """Switch to ultra-compact Compact Mode (persisted across restart)"""
        if self.mode_stack.currentIndex() == 0:
            _cfg['full_window_size'] = [self.width(), self.height()]
            
        if save:
            _cfg['compact_mode'] = True
            save_config(_cfg)
            
        self.populate_compact_accounts()
        self.mode_stack.setCurrentIndex(1)
        
        # Hide status bar in compact mode
        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.hide()
            
        # Set compact constraints and resize
        self.setMinimumSize(340, 400)
        self.setMaximumSize(460, 480)
        self.resize(360, 410)
        
    def switch_to_full_mode(self, save: bool = True):
        """Switch to full launcher view"""
        if save:
            _cfg['compact_mode'] = False
            save_config(_cfg)
            
        self.mode_stack.setCurrentIndex(0)
        
        # Show status bar in full mode
        if hasattr(self, 'status_bar') and self.status_bar and _cfg.get('show_status_bar', True):
            self.status_bar.show()
            
        # Remove compact constraints and restore full size
        self.setMaximumSize(16777215, 16777215)
        self.setMinimumSize(900, 700)
        full_size = _cfg.get('full_window_size', [1100, 800])
        self.resize(full_size[0], full_size[1])
        
    def create_header(self, parent_layout):
        """Create sleek custom Navbar for Quick101 with wizard hat brand logo and nav items"""
        navbar_widget = QWidget()
        navbar_widget.setFixedHeight(64)
        navbar_widget.setObjectName("Quick101Navbar")
        navbar_widget.setStyleSheet("""
            QWidget#Quick101Navbar {
                background-color: #0A0A0A;
                border-bottom: 1px solid #1E1E1E;
            }
        """)
        navbar_layout = QHBoxLayout(navbar_widget)
        navbar_layout.setContentsMargins(20, 0, 20, 0)
        navbar_layout.setSpacing(14)
        
        # Left brand group: Wizard Hat Icon + QUICK101 Title
        brand_group = QHBoxLayout()
        brand_group.setSpacing(10)
        
        logo_label = QLabel()
        logo_label.setFixedSize(36, 36)
        logo_label.setScaledContents(True)
        icon_path = get_app_icon_path(prefer_ico=False)
        if icon_path and os.path.exists(icon_path):
            logo_pix = QPixmap(icon_path).scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio if PyQt_Version == 6 else Qt.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation if PyQt_Version == 6 else Qt.SmoothTransformation)
            logo_label.setPixmap(logo_pix)
        brand_group.addWidget(logo_label)
        
        title_label = QLabel("QUICK101")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF; letter-spacing: 2px;")
        brand_group.addWidget(title_label)
        
        navbar_layout.addLayout(brand_group)
        navbar_layout.addStretch()
        
        # Right Navbar Navigation & Actions
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)
        
        compact_btn = ModernButton("Compact Mode", "secondary", icon_name="compact")
        compact_btn.clicked.connect(self.switch_to_compact_mode)
        nav_layout.addWidget(compact_btn)
        
        settings_btn = ModernButton("Settings", "secondary", icon_name="settings")
        settings_btn.clicked.connect(self.open_settings_dialog)
        nav_layout.addWidget(settings_btn)
        
        navbar_layout.addLayout(nav_layout)
        parent_layout.addWidget(navbar_widget)
    
    def create_main_content(self, parent_layout):
        """Create the main content area"""
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 16, 20, 20)
        content_layout.setSpacing(16)
        
        # Left panel - Categories and Accounts
        left_panel = self.create_left_panel()
        content_layout.addWidget(left_panel, 2)
        
        # Right panel - Controls
        right_panel = self.create_right_panel()
        content_layout.addWidget(right_panel, 1)
        
        parent_layout.addWidget(content_widget)
    
    def create_left_panel(self):
        """Create the left panel with categories and accounts in sleek monochrome"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        
        # Categories section
        cat_group = QGroupBox("CATEGORIES")
        cat_layout = QVBoxLayout(cat_group)
        cat_layout.setContentsMargins(14, 16, 14, 14)
        
        # Category selector
        cat_select_layout = QHBoxLayout()
        cat_select_layout.setSpacing(8)
        self.category_combo = ModernComboBox()
        self.category_combo.currentTextChanged.connect(self.on_category_changed)
        cat_select_layout.addWidget(self.category_combo, 1)
        
        add_cat_btn = ModernButton("Add", "secondary", icon_name="add")
        add_cat_btn.clicked.connect(self.show_add_category_inline)
        add_cat_btn.setFixedWidth(85)
        cat_select_layout.addWidget(add_cat_btn)
        
        del_cat_btn = ModernButton("Delete", "danger", icon_name="delete")
        del_cat_btn.clicked.connect(self.show_delete_category_inline)
        del_cat_btn.setFixedWidth(85)
        cat_select_layout.addWidget(del_cat_btn)
        
        cat_layout.addLayout(cat_select_layout)
        
        # Inline category operations
        self.cat_operations_widget = QWidget()
        self.cat_operations_layout = QVBoxLayout(self.cat_operations_widget)
        self.cat_operations_layout.setContentsMargins(0, 8, 0, 4)
        self.cat_operations_widget.hide()
        cat_layout.addWidget(self.cat_operations_widget)
        
        layout.addWidget(cat_group)
        
        # Accounts section
        self.acc_group = QGroupBox("ACCOUNTS")
        self.update_accounts_glassmorphism()
        acc_layout = QVBoxLayout(self.acc_group)
        acc_layout.setContentsMargins(14, 16, 14, 14)
        
        self.account_list = ModernListWidget()
        self.account_list.itemDoubleClicked.connect(self.launch_selected_accounts)
        acc_layout.addWidget(self.account_list)
        
        # Inline account operations
        self.acc_operations_widget = QWidget()
        self.acc_operations_layout = QVBoxLayout(self.acc_operations_widget)
        self.acc_operations_layout.setContentsMargins(0, 8, 0, 4)
        self.acc_operations_widget.hide()
        acc_layout.addWidget(self.acc_operations_widget)
        
        layout.addWidget(self.acc_group)
        return panel
    
    def create_right_panel(self):
        """Create the right panel with controls"""
        panel = QWidget()
        panel.setMaximumWidth(360)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        
        # Account management
        mgmt_group = QGroupBox("ACCOUNT MANAGEMENT")
        mgmt_layout = QVBoxLayout(mgmt_group)
        mgmt_layout.setContentsMargins(14, 16, 14, 14)
        mgmt_layout.setSpacing(8)
        
        add_acc_btn = ModernButton("Add Account", "secondary", icon_name="add")
        add_acc_btn.clicked.connect(self.show_add_account_inline)
        mgmt_layout.addWidget(add_acc_btn)
        
        edit_acc_btn = ModernButton("Edit Account", "secondary", icon_name="edit")
        edit_acc_btn.clicked.connect(self.show_edit_account_inline)
        mgmt_layout.addWidget(edit_acc_btn)
        
        del_acc_btn = ModernButton("Delete Account", "danger", icon_name="delete")
        del_acc_btn.clicked.connect(self.show_delete_account_inline)
        mgmt_layout.addWidget(del_acc_btn)
        
        layout.addWidget(mgmt_group)
        
        # Launch controls
        launch_group = QGroupBox("LAUNCH CONTROLS")
        launch_layout = QVBoxLayout(launch_group)
        launch_layout.setContentsMargins(14, 16, 14, 14)
        launch_layout.setSpacing(8)
        
        launch_sel_btn = ModernButton("LAUNCH SELECTED", "primary", icon_name="launch")
        launch_sel_btn.setFixedHeight(44)
        launch_sel_btn.clicked.connect(self.launch_selected_accounts)
        launch_layout.addWidget(launch_sel_btn)
        
        kill_layout = QHBoxLayout()
        kill_layout.setSpacing(8)
        
        kill_sel_btn = ModernButton("Kill Selected", "danger", icon_name="delete")
        kill_sel_btn.setToolTip("Terminate running Wizard101 instance for selected account(s)")
        kill_sel_btn.clicked.connect(self.kill_selected_instances)
        kill_layout.addWidget(kill_sel_btn, 1)
        
        kill_all_btn = ModernButton("Kill All", "danger", icon_name="delete")
        kill_all_btn.setToolTip("Terminate ALL running Wizard101 instances")
        kill_all_btn.clicked.connect(self.kill_all_instances)
        kill_layout.addWidget(kill_all_btn, 1)
        
        launch_layout.addLayout(kill_layout)
        
        layout.addWidget(launch_group)
        
        # Wizard101 Path section
        path_group = QGroupBox("WIZARD101 PATH")
        path_layout = QVBoxLayout(path_group)
        path_layout.setContentsMargins(14, 16, 14, 14)
        path_layout.setSpacing(8)
        
        # Path display
        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("font-size: 10px; padding: 8px; background-color: #101010; border: 1px solid #282828; border-radius: 6px; color: #FAFAFA;")
        path_layout.addWidget(self.path_label)
        
        # Path selection buttons: Standalone, Steam, Browse
        path_btn_layout = QHBoxLayout()
        path_btn_layout.setSpacing(6)
        
        self.standalone_btn = ModernButton("Standalone", "secondary", icon_name="standalone")
        self.standalone_btn.clicked.connect(self.select_standalone_path)
        path_btn_layout.addWidget(self.standalone_btn, 1)
        
        self.steam_btn = ModernButton("Steam", "secondary", icon_name="steam")
        self.steam_btn.clicked.connect(self.select_steam_path)
        path_btn_layout.addWidget(self.steam_btn, 1)
        
        custom_btn = ModernButton("Custom", "secondary", icon_name="folder")
        custom_btn.clicked.connect(self.browse_wizard_path)
        path_btn_layout.addWidget(custom_btn, 1)
        
        path_layout.addLayout(path_btn_layout)
        
        layout.addWidget(path_group)
        
        # Hidden info_label kept for internal setText() calls (category display etc.)
        self.info_label = QLabel("")
        self.info_label.hide()

        # Tools panel
        tools_group = QGroupBox("TOOLS")
        tools_layout = QVBoxLayout(tools_group)
        tools_layout.setContentsMargins(14, 16, 14, 14)
        tools_layout.setSpacing(8)

        pet_calc_btn = ModernButton("Pet Calculator", "secondary", icon_name="pet")
        pet_calc_btn.clicked.connect(self.open_pet_calculator)
        tools_layout.addWidget(pet_calc_btn)

        pet_wow_btn = ModernButton("Pet WoW Returner", "secondary", icon_name="pet")
        pet_wow_btn.clicked.connect(self.open_pet_wow_returner)
        tools_layout.addWidget(pet_wow_btn)

        dmg_calc_btn = ModernButton("Damage Calculator", "secondary", icon_name="damage")
        dmg_calc_btn.clicked.connect(self.open_damage_calculator)
        tools_layout.addWidget(dmg_calc_btn)

        layout.addWidget(tools_group)
        layout.addStretch()
        return panel
    
    def create_status_bar(self):
        """Create the status bar with Made by Vani on the bottom right"""
        if _cfg.get('show_status_bar', True):
            self.status_bar = self.statusBar()
            self.status_bar.showMessage("Ready")
            
            # Permanent "Made by Vani" on the bottom right
            credits_widget = QWidget()
            credits_layout = QHBoxLayout(credits_widget)
            credits_layout.setContentsMargins(0, 0, 10, 0)
            credits_layout.setSpacing(4)
            
            made_by_label = QLabel("Made by")
            made_by_label.setStyleSheet("color: #707070; font-size: 11px; font-weight: 500;")
            credits_layout.addWidget(made_by_label)
            
            vani_btn = QPushButton("Vani")
            vani_btn.setCursor(Qt.CursorShape.PointingHandCursor if PyQt_Version == 6 else Qt.PointingHandCursor)
            vani_btn.setToolTip("Open Discord Chat with Vani (ID: 622454645742108692)")
            vani_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #A78BFA;
                    border: none;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 0px 2px;
                    text-decoration: underline;
                }
                QPushButton:hover {
                    color: #C4B5FD;
                }
                QPushButton:pressed {
                    color: #8B5CF6;
                }
            """)
            vani_btn.clicked.connect(self.open_vani_discord)
            credits_layout.addWidget(vani_btn)
            
            self.status_bar.addPermanentWidget(credits_widget)
    
    def apply_theme(self):
        """Apply the monochrome theme to all UI elements matching Wizard101Calculator"""
        bg_primary = self.current_theme.get('primary', '#0A0A0A')
        card_bg = self.current_theme.get('secondary', '#141414')
        border_col = self.current_theme.get('border', '#282828')
        border_light = self.current_theme.get('border_light', '#464646')
        text_col = self.current_theme.get('text_primary', '#FAFAFA')
        text_muted = self.current_theme.get('text_muted', '#5F5F5F')
        
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {bg_primary};
                color: {text_col};
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 11px;
                letter-spacing: 0.5px;
                border: 1px solid {border_col};
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
                background-color: {card_bg};
                color: #FFFFFF;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 1px 8px;
                color: #FFFFFF;
                background-color: {card_bg};
                border-radius: 3px;
            }}
            QLabel {{
                color: {text_col};
            }}
            QStatusBar {{
                background-color: #0A0A0A;
                color: {text_muted};
                border-top: 1px solid #1E1E1E;
                font-size: 10px;
                padding: 2px 8px;
            }}
            QScrollBar:vertical {{
                border: none;
                background: #0A0A0A;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: #282828;
                min-height: 25px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {border_light};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)
        
        # Update child components with new theme
        if hasattr(self, 'theme_combo'):
            self.theme_combo.theme = self.current_theme
            self.theme_combo.apply_style()
        if hasattr(self, 'category_combo'):
            self.category_combo.theme = self.current_theme
            self.category_combo.apply_style()
        if hasattr(self, 'account_list'):
            self.account_list.theme = self.current_theme
            self.account_list.apply_style()
        
        for widget in self.findChildren(ModernButton):
            widget.theme = self.current_theme
            widget.apply_style()
        
        for widget in self.findChildren(ModernComboBox):
            widget.theme = self.current_theme
            widget.apply_style()
        
        for widget in self.findChildren(ModernListWidget):
            widget.theme = self.current_theme
            widget.apply_style()
        
        if hasattr(self, 'acc_group'):
            self.update_accounts_glassmorphism()
    
    def update_accounts_glassmorphism(self):
        """Update styling for the accounts section in monochrome design"""
        card_bg = self.current_theme.get('secondary', '#141414')
        border_col = self.current_theme.get('border', '#282828')
        self.acc_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 11px;
                letter-spacing: 0.5px;
                border: 1px solid {border_col};
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
                background-color: {card_bg};
                color: #FFFFFF;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 1px 8px;
                color: #FFFFFF;
                background-color: {card_bg};
                border-radius: 3px;
            }}
        """)
    
    def apply_background(self):
        """Apply the selected background"""
        bg_type = _cfg.get('background_type', 'gradient')
        bg_path = _cfg.get('background_path')
        
        # Create background label if it doesn't exist
        if not hasattr(self, 'background_label'):
            self.background_label = QLabel(self)
            self.background_label.setScaledContents(True)
            self.background_label.lower()  # Send to back
            self.background_label.setGeometry(0, 0, self.width(), self.height())
        
        if bg_type == 'image' and bg_path and os.path.exists(bg_path):
            try:
                pixmap = self.bg_manager.load_image_background(bg_path, self.size(), 
                                                             _cfg.get('background_opacity', 0.7))
                if not pixmap.isNull():
                    self.background_label.setPixmap(pixmap)
                    self.background_label.show()
                    # Make central widget background transparent
                    self.centralWidget().setStyleSheet("background: transparent;")
                else:
                    self._apply_default_background()
            except Exception as e:
                print(f"Error applying image background: {e}")
                self._apply_default_background()
        else:
            self._apply_default_background()
    
    def _apply_default_background(self):
        """Apply default solid uniform background"""
        if hasattr(self, 'background_label'):
            pixmap = QPixmap(self.size())
            pixmap.fill(QColor(10, 10, 10))
            self.background_label.setPixmap(pixmap)
            self.background_label.show()
        
        # Ensure central widget background stays solid uniform #0A0A0A
        if self.centralWidget():
            self.centralWidget().setStyleSheet("""
                QWidget#CentralWidget {
                    background-color: #0A0A0A;
                    border: 1px solid #242424;
                }
            """)
    
    def on_theme_changed(self, theme_name: str):
        """Handle theme change"""
        for i, theme in ModernThemes.THEMES.items():
            if theme['name'] == theme_name:
                _cfg['theme_index'] = i
                save_config(_cfg)
                self.current_theme = theme
                self.apply_theme()
                self.apply_background()
                break
    
    def load_categories(self):
        """Load categories into the combo box"""
        self.category_combo.clear()
        categories = get_categories()
        self.category_combo.addItems(categories)
        
        # Select last used category
        last_cat = _cfg.get('last_category')
        if last_cat and last_cat in categories:
            self.category_combo.setCurrentText(last_cat)
        
        self.refresh_accounts()
        self.populate_compact_accounts()
    
    def on_category_changed(self, category: str):
        """Handle category selection change"""
        _cfg['last_category'] = category
        save_config(_cfg)
        self.refresh_accounts()
    
    def refresh_accounts(self):
        """Refresh the account list"""
        self.account_list.clear()
        self.account_list.clear_selection_custom()
        category = self.category_combo.currentText()
        
        if category:
            accounts_data = load_accounts().get(category, {})
            for account_name in accounts_data.keys():
                # Create custom item with subtext and Steam tag
                item = QListWidgetItem()
                
                # Get account data
                account_info = accounts_data[account_name]
                subtext = account_info.get('subtext', '')
                is_steam = account_info.get('steam', False) if isinstance(account_info, dict) else False
                
                # Create display text (clean, icon is rendered by delegate)
                if subtext:
                    display_text = f"{account_name}\n{subtext}"
                else:
                    display_text = account_name
                    
                item.setText(display_text)
                item.setData(Qt.ItemDataRole.UserRole if PyQt_Version == 6 else Qt.UserRole, account_name)  # Store original name
                item.setData(Qt.ItemDataRole.UserRole + 1 if PyQt_Version == 6 else Qt.UserRole + 1, is_steam)  # Store steam flag
                
                self.account_list.addItem(item)
            
            self.info_label.setText(f"Category: {category}\nAccounts: {len(accounts_data)}")
        else:
            self.info_label.setText("No category selected")
        
        self.populate_compact_accounts()
    
    def clear_all_operations(self):
        """Clear all inline operation widgets"""
        self.cat_operations_widget.hide()
        self.acc_operations_widget.hide()
        # Clear any existing widgets
        for i in reversed(range(self.cat_operations_layout.count())):
            self.cat_operations_layout.itemAt(i).widget().setParent(None)
        for i in reversed(range(self.acc_operations_layout.count())):
            self.acc_operations_layout.itemAt(i).widget().setParent(None)
    
    def show_add_category_inline(self):
        """Show inline add category form"""
        self.clear_all_operations()
        
        # Create form
        form_widget = QWidget()
        form_widget.setStyleSheet("""
            QWidget {
                background-color: #141414;
                border: 1px solid #464646;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(8)
        
        # Title
        title = QLabel("ADD NEW CATEGORY")
        title.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 11px; letter-spacing: 0.5px; margin-bottom: 2px;")
        form_layout.addWidget(title)
        
        # Input
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter category name...")
        name_input.setStyleSheet("""
            QLineEdit {
                background-color: #101010;
                color: #FFFFFF;
                border: 1px solid #282828;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #707070;
            }
        """)
        form_layout.addWidget(name_input)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        save_btn = ModernButton("Save", "primary")
        def save_category():
            name = name_input.text().strip()
            if name:
                add_category(name)
                self.load_categories()
                self.category_combo.setCurrentText(name)
                self.update_status(f"Added category: {name}")
                self.clear_all_operations()
        save_btn.clicked.connect(save_category)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = ModernButton("Cancel", "secondary")
        cancel_btn.clicked.connect(self.clear_all_operations)
        btn_layout.addWidget(cancel_btn)
        
        form_layout.addLayout(btn_layout)
        
        self.cat_operations_layout.addWidget(form_widget)
        self.cat_operations_widget.show()
        name_input.setFocus()
    
    def show_delete_category_inline(self):
        """Show inline delete category confirmation"""
        category = self.category_combo.currentText()
        if not category:
            self.update_status("No category selected to delete")
            return
        
        self.clear_all_operations()
        
        # Create confirmation
        confirm_widget = QWidget()
        confirm_widget.setStyleSheet("""
            QWidget {
                background-color: #1A1212;
                border: 1px solid #4A2020;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        confirm_layout = QVBoxLayout(confirm_widget)
        confirm_layout.setSpacing(8)
        
        # Warning
        warning = QLabel(f"Delete category '{category}' and all its accounts?")
        warning.setStyleSheet("font-weight: bold; color: #FFA0A0; font-size: 11px; margin-bottom: 2px;")
        warning.setWordWrap(True)
        confirm_layout.addWidget(warning)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        delete_btn = ModernButton("Delete", "danger")
        def confirm_delete():
            delete_category(category)
            self.load_categories()
            self.update_status(f"Deleted category: {category}")
            self.clear_all_operations()
        delete_btn.clicked.connect(confirm_delete)
        btn_layout.addWidget(delete_btn)
        
        cancel_btn = ModernButton("Cancel", "secondary")
        cancel_btn.clicked.connect(self.clear_all_operations)
        btn_layout.addWidget(cancel_btn)
        
        confirm_layout.addLayout(btn_layout)
        
        self.cat_operations_layout.addWidget(confirm_widget)
        self.cat_operations_widget.show()
    
    def show_add_account_inline(self):
        """Show inline add account form"""
        category = self.category_combo.currentText()
        if not category:
            self.update_status("Please select a category first")
            return
        
        self.clear_all_operations()
        
        # Create form
        form_widget = QWidget()
        form_widget.setStyleSheet("""
            QWidget {
                background-color: #141414;
                border: 1px solid #464646;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(6)
        
        # Title
        title = QLabel(f"ADD ACCOUNT TO '{category.upper()}'")
        title.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 11px; letter-spacing: 0.5px; margin-bottom: 4px;")
        form_layout.addWidget(title)
        
        # Input style
        input_style = """
            QLineEdit {
                background-color: #101010;
                color: #FFFFFF;
                border: 1px solid #282828;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 11px;
                margin: 2px 0;
            }
            QLineEdit:focus {
                border-color: #707070;
            }
        """
        
        # Inputs
        nickname_input = QLineEdit()
        nickname_input.setPlaceholderText("Account nickname...")
        nickname_input.setStyleSheet(input_style)
        form_layout.addWidget(nickname_input)
        
        username_input = QLineEdit()
        username_input.setPlaceholderText("Wizard101 username...")
        username_input.setStyleSheet(input_style)
        form_layout.addWidget(username_input)
        
        password_input = QLineEdit()
        password_input.setPlaceholderText("Wizard101 password...")
        password_input.setEchoMode(QLineEdit.EchoMode.Password if PyQt_Version == 6 else QLineEdit.Password)
        password_input.setStyleSheet(input_style)
        form_layout.addWidget(password_input)
        
        subtext_input = QLineEdit()
        subtext_input.setPlaceholderText("Subtext (optional) - leave blank if not needed...")
        subtext_input.setStyleSheet(input_style)
        form_layout.addWidget(subtext_input)
        
        # Show password & Steam checkboxes
        cb_row = QHBoxLayout()
        cb_row.setSpacing(12)
        
        show_pass_cb = QCheckBox("Show Password")
        show_pass_cb.setStyleSheet("color: #969696; font-size: 10px; margin: 4px 0;")
        def toggle_pass():
            if show_pass_cb.isChecked():
                password_input.setEchoMode(QLineEdit.EchoMode.Normal if PyQt_Version == 6 else QLineEdit.Normal)
            else:
                password_input.setEchoMode(QLineEdit.EchoMode.Password if PyQt_Version == 6 else QLineEdit.Password)
        show_pass_cb.stateChanged.connect(toggle_pass)
        cb_row.addWidget(show_pass_cb)
        
        steam_cb = QCheckBox("Launch via Steam (Steam Mode)")
        steam_cb.setStyleSheet("color: #FAFAFA; font-size: 10px; font-weight: 500; margin: 4px 0;")
        cb_row.addWidget(steam_cb)
        
        form_layout.addLayout(cb_row)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        save_btn = ModernButton("Save", "primary")
        def save_account():
            nickname = nickname_input.text().strip()
            username = username_input.text().strip()
            password = password_input.text().strip()
            subtext = subtext_input.text().strip()
            
            if not all([nickname, username, password]):
                self.update_status("Nickname, username, and password are required (subtext is optional)")
                return
            
            add_account(category, nickname, username, password, subtext, steam=steam_cb.isChecked())
            self.refresh_accounts()
            self.update_status(f"Added account: {nickname}")
            self.clear_all_operations()
        save_btn.clicked.connect(save_account)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = ModernButton("Cancel", "secondary")
        cancel_btn.clicked.connect(self.clear_all_operations)
        btn_layout.addWidget(cancel_btn)
        
        form_layout.addLayout(btn_layout)
        
        self.acc_operations_layout.addWidget(form_widget)
        self.acc_operations_widget.show()
        nickname_input.setFocus()
    
    def show_edit_account_inline(self):
        """Show inline edit account form"""
        selected_items = self.account_list.get_selected_items()
        if not selected_items:
            self.update_status("Please select an account to edit")
            return
        
        # Use the first selected item for editing
        current_item = selected_items[0]
        
        category = self.category_combo.currentText()
        nickname = current_item.data(Qt.ItemDataRole.UserRole if PyQt_Version == 6 else Qt.UserRole)
        
        # Load existing data
        _, account_data = load_account(category, nickname)
        
        self.clear_all_operations()
        
        # Create form with compact layout
        form_widget = QWidget()
        form_widget.setStyleSheet("""
            QWidget {
                background-color: #141414;
                border: 1px solid #464646;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(6)  # Reduced spacing
        
        # Title
        title = QLabel(f"EDIT ACCOUNT: {nickname.upper()}")
        title.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 11px; letter-spacing: 0.5px; margin-bottom: 4px;")
        form_layout.addWidget(title)
        
        # Input style
        input_style = """
            QLineEdit {
                background-color: #101010;
                color: #FFFFFF;
                border: 1px solid #282828;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border-color: #707070;
            }
        """
        
        # Compact grid layout for inputs
        input_grid = QWidget()
        grid_layout = QGridLayout(input_grid)
        grid_layout.setSpacing(6)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        
        # Inputs with labels
        lbl_nick = QLabel("Nickname:")
        lbl_nick.setStyleSheet("color: #969696; font-size: 10px; font-weight: bold;")
        grid_layout.addWidget(lbl_nick, 0, 0)
        nickname_input = QLineEdit()
        nickname_input.setText(nickname)
        nickname_input.setStyleSheet(input_style)
        grid_layout.addWidget(nickname_input, 0, 1)
        
        lbl_user = QLabel("Username:")
        lbl_user.setStyleSheet("color: #969696; font-size: 10px; font-weight: bold;")
        grid_layout.addWidget(lbl_user, 1, 0)
        username_input = QLineEdit()
        username_input.setText(account_data.get('username', ''))
        username_input.setEchoMode(QLineEdit.EchoMode.Password if PyQt_Version == 6 else QLineEdit.Password)
        username_input.setStyleSheet(input_style)
        grid_layout.addWidget(username_input, 1, 1)
        
        lbl_pass = QLabel("Password:")
        lbl_pass.setStyleSheet("color: #969696; font-size: 10px; font-weight: bold;")
        grid_layout.addWidget(lbl_pass, 2, 0)
        password_input = QLineEdit()
        password_input.setText(account_data.get('password', ''))
        password_input.setEchoMode(QLineEdit.EchoMode.Password if PyQt_Version == 6 else QLineEdit.Password)
        password_input.setStyleSheet(input_style)
        grid_layout.addWidget(password_input, 2, 1)
        
        lbl_sub = QLabel("Subtext:")
        lbl_sub.setStyleSheet("color: #969696; font-size: 10px; font-weight: bold;")
        grid_layout.addWidget(lbl_sub, 3, 0)
        subtext_input = QLineEdit()
        subtext_input.setText(account_data.get('subtext', ''))
        subtext_input.setPlaceholderText("Optional - leave blank if not needed...")
        subtext_input.setStyleSheet(input_style)
        grid_layout.addWidget(subtext_input, 3, 1)
        
        form_layout.addWidget(input_grid)
        
        # Show checkboxes in horizontal layout
        cb_layout = QHBoxLayout()
        cb_layout.setSpacing(12)
        
        show_user_cb = QCheckBox("Show User")
        show_user_cb.setStyleSheet("color: #969696; font-size: 9px;")
        def toggle_user():
            if show_user_cb.isChecked():
                username_input.setEchoMode(QLineEdit.EchoMode.Normal if PyQt_Version == 6 else QLineEdit.Normal)
            else:
                username_input.setEchoMode(QLineEdit.EchoMode.Password if PyQt_Version == 6 else QLineEdit.Password)
        show_user_cb.stateChanged.connect(toggle_user)
        cb_layout.addWidget(show_user_cb)
        
        show_pass_cb = QCheckBox("Show Pass")
        show_pass_cb.setStyleSheet("color: #969696; font-size: 9px;")
        def toggle_pass():
            if show_pass_cb.isChecked():
                password_input.setEchoMode(QLineEdit.EchoMode.Normal if PyQt_Version == 6 else QLineEdit.Normal)
            else:
                password_input.setEchoMode(QLineEdit.EchoMode.Password if PyQt_Version == 6 else QLineEdit.Password)
        show_pass_cb.stateChanged.connect(toggle_pass)
        cb_layout.addWidget(show_pass_cb)
        
        edit_steam_cb = QCheckBox("Launch via Steam")
        is_steam = account_data.get('steam', False) if isinstance(account_data, dict) else False
        edit_steam_cb.setChecked(bool(is_steam))
        edit_steam_cb.setStyleSheet("color: #FAFAFA; font-size: 9px; font-weight: 500;")
        cb_layout.addWidget(edit_steam_cb)
        
        form_layout.addLayout(cb_layout)
        
        # Compact buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        save_btn = ModernButton("Save", "primary")
        save_btn.setFixedHeight(32)
        def save_account():
            new_nickname = nickname_input.text().strip()
            username = username_input.text().strip()
            password = password_input.text().strip()
            subtext = subtext_input.text().strip()
            
            if not all([new_nickname, username, password]):
                self.update_status("Nickname, username, and password are required (subtext is optional)")
                return
            
            # Delete old account if nickname changed
            if new_nickname != nickname:
                delete_account(category, nickname)
            
            add_account(category, new_nickname, username, password, subtext, steam=edit_steam_cb.isChecked())
            self.refresh_accounts()
            self.update_status(f"Updated account: {new_nickname}")
            self.clear_all_operations()
        save_btn.clicked.connect(save_account)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = ModernButton("Cancel", "secondary")
        cancel_btn.setFixedHeight(32)
        cancel_btn.clicked.connect(self.clear_all_operations)
        btn_layout.addWidget(cancel_btn)
        
        form_layout.addLayout(btn_layout)
        
        self.acc_operations_layout.addWidget(form_widget)
        self.acc_operations_widget.show()
    
    def show_delete_account_inline(self):
        """Show inline delete account confirmation"""
        selected_items = self.account_list.get_selected_items()
        if not selected_items:
            self.update_status("Please select account(s) to delete")
            return
        
        self.clear_all_operations()
        
        # Create confirmation
        confirm_widget = QWidget()
        confirm_widget.setStyleSheet("""
            QWidget {
                background-color: #1A1212;
                border: 1px solid #4A2020;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        confirm_layout = QVBoxLayout(confirm_widget)
        confirm_layout.setSpacing(8)
        
        # Warning
        account_names = [item.data(Qt.ItemDataRole.UserRole if PyQt_Version == 6 else Qt.UserRole) for item in selected_items]
        if len(account_names) == 1:
            warning_text = f"Delete account '{account_names[0]}'?"
        else:
            warning_text = f"Delete {len(account_names)} selected accounts?"
        
        warning = QLabel(warning_text)
        warning.setStyleSheet("font-weight: bold; color: #FFA0A0; font-size: 11px; margin-bottom: 2px;")
        warning.setWordWrap(True)
        confirm_layout.addWidget(warning)
        
        # Show account names if multiple
        if len(account_names) > 1:
            names_label = QLabel(", ".join(account_names))
            names_label.setStyleSheet("color: #D0D0D0; font-size: 10px;")
            names_label.setWordWrap(True)
            confirm_layout.addWidget(names_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        delete_btn = ModernButton("Delete", "danger")
        def confirm_delete():
            category = self.category_combo.currentText()
            for item in selected_items:
                account_name = item.data(Qt.ItemDataRole.UserRole if PyQt_Version == 6 else Qt.UserRole)
                delete_account(category, account_name)
            
            self.refresh_accounts()
            self.update_status(f"Deleted {len(selected_items)} account(s)")
            self.clear_all_operations()
        delete_btn.clicked.connect(confirm_delete)
        btn_layout.addWidget(delete_btn)
        
        cancel_btn = ModernButton("Cancel", "secondary")
        cancel_btn.clicked.connect(self.clear_all_operations)
        btn_layout.addWidget(cancel_btn)
        
        confirm_layout.addLayout(btn_layout)
        
        self.acc_operations_layout.addWidget(confirm_widget)
        self.acc_operations_widget.show()
    
    def launch_selected_accounts(self):
        """Launch selected accounts with throttling"""
        # Check throttling to prevent spam clicking
        current_time = time.time() * 1000  # Convert to milliseconds
        if current_time - self.last_launch_time < self.launch_delay:
            self.update_status(f"Please wait {int((self.launch_delay - (current_time - self.last_launch_time))/1000)} seconds before launching again")
            return
        
        selected_items = self.account_list.get_selected_items()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select account(s) to launch.")
            return

        # Check if any account is already open
        accounts_to_launch = []
        for item in selected_items:
            nickname = item.data(Qt.ItemDataRole.UserRole if PyQt_Version == 6 else Qt.UserRole)
            if is_account_already_running(nickname):
                dlg = AccountAlreadyOpenDialog(self, nickname)
                if dlg.exec() == (QDialog.DialogCode.Accepted if PyQt_Version == 6 else QDialog.Accepted):
                    accounts_to_launch.append(item)
                else:
                    self.update_status(f"Skipped already running account: {nickname}")
            else:
                accounts_to_launch.append(item)

        if not accounts_to_launch:
            return
        
        # Update throttle time
        self.last_launch_time = current_time
        
        category = self.category_combo.currentText()
        timeout = _cfg.get('auto_login_timeout', 10)  # Default 10 seconds like OldLauncher
        
        def launch_worker():
            # Launch all accounts simultaneously in separate threads
            threads = []
            
            for item in accounts_to_launch:
                # Get original account name from UserRole data
                nickname = item.data(Qt.ItemDataRole.UserRole if PyQt_Version == 6 else Qt.UserRole)
                _, account_data = load_account(category, nickname)
                is_steam = account_data.get('steam', False) if isinstance(account_data, dict) else False
                
                # Create individual thread for each account
                def launch_account(username, password, nick, steam_mode):
                    success = launch_with_credentials(username, password, nick, timeout, is_steam=steam_mode)
                    if success:
                        self.update_status(f"Launched: {nick}" + (" [Steam]" if steam_mode else ""))
                    else:
                        self.update_status(f"Failed to launch: {nick}")
                
                account_thread = threading.Thread(
                    target=launch_account,
                    args=(account_data['username'], account_data['password'], nickname, is_steam),
                    daemon=True
                )
                threads.append(account_thread)
                account_thread.start()
            
            # Wait for all launches to complete
            for thread in threads:
                thread.join()
        
        # Launch all accounts simultaneously
        thread = threading.Thread(target=launch_worker, daemon=True)
        thread.start()
        
        self.update_status(f"Launching {len(accounts_to_launch)} account(s)...")

    def kill_selected_instances(self):
        """Kill running Wizard101 instance(s) for selected account(s)"""
        selected_items = self.account_list.get_selected_items()
        if not selected_items:
            QMessageBox.information(self, "Kill Instances", "Please select account(s) in the list to terminate.")
            return
            
        killed_any = False
        for item in selected_items:
            nickname = item.data(Qt.ItemDataRole.UserRole if PyQt_Version == 6 else Qt.UserRole)
            if kill_account_instance(nickname):
                killed_any = True
                self.update_status(f"Terminated instance for: {nickname}")
                
        if not killed_any:
            self.update_status("No running instance found for selected account(s)")

    def kill_all_instances(self):
        """Kill all running Wizard101 instances"""
        kill_all_wizard_instances()
        self.update_status("All Wizard101 instances terminated")
    
    STANDALONE_PATH = r"C:/ProgramData/KingsIsle Entertainment/Wizard101/Bin/"
    STEAM_PATH = r"C:/Program Files (x86)/Steam/steamapps/common/Wizard101/Bin/"
    
    def select_standalone_path(self):
        """Set Wizard101 path to KingsIsle Standalone installation"""
        _cfg['wiz_path'] = self.STANDALONE_PATH
        save_config(_cfg)
        self.update_wizard_path_display()
        self.update_status("Wizard101 path set to Standalone Launcher")
        
    def select_steam_path(self):
        """Set Wizard101 path to Steam installation"""
        _cfg['wiz_path'] = self.STEAM_PATH
        save_config(_cfg)
        self.update_wizard_path_display()
        self.update_status("Wizard101 path set to Steam")
        
    def browse_wizard_path(self):
        """Browse for Wizard101 installation path"""
        current_path = _cfg.get('wiz_path', '')
        if not current_path or not os.path.exists(current_path):
            try:
                current_path = get_game_path()
            except:
                current_path = ''
        
        path = QFileDialog.getExistingDirectory(
            self, "Select Wizard101 Installation Directory",
            current_path
        )
        
        if path:
            path = path.replace("\\", "/")
            if not path.endswith("/"):
                path += "/"
            
            # Validate that this looks like a Wizard101 directory
            valid_exe = None
            for exe_name in ["WizardGraphicalClient.exe", "Wizard101.exe"]:
                exe_path = os.path.join(path, exe_name)
                if os.path.exists(exe_path):
                    valid_exe = exe_name
                    break
            
            if valid_exe:
                _cfg['wiz_path'] = path
                save_config(_cfg)
                self.update_wizard_path_display()
                self.update_status(f"Wizard101 path updated: {path}")
            else:
                QMessageBox.warning(
                    self, "Invalid Path", 
                    "The selected directory does not contain WizardGraphicalClient.exe or Wizard101.exe.\n"
                    "Please select the correct Wizard101 installation directory."
                )

    def open_appdata_dir(self):
        """Open the Quick101 data directory in Windows Explorer"""
        try:
            os.startfile(APPDATA_DIR)
            self.update_status(f"Opened AppData: {APPDATA_DIR}")
        except Exception:
            try:
                subprocess.Popen(['explorer', APPDATA_DIR])
                self.update_status(f"Opened AppData: {APPDATA_DIR}")
            except Exception as e:
                QMessageBox.information(self, "AppData Directory", f"Configuration & account files are saved in:\n{APPDATA_DIR}")
    
    def update_wizard_path_display(self):
        """Update the Wizard101 path display with clean source tag and no emojis"""
        if hasattr(self, 'path_label'):
            current_path = _cfg.get('wiz_path', '')
            norm_curr = os.path.normpath(current_path).lower() if current_path else ''
            norm_standalone = os.path.normpath(self.STANDALONE_PATH).lower()
            norm_steam = os.path.normpath(self.STEAM_PATH).lower()
            
            source_tag = "[CUSTOM]"
            if norm_curr == norm_standalone:
                source_tag = "[STANDALONE]"
            elif norm_curr == norm_steam:
                source_tag = "[STEAM]"
                
            if current_path and os.path.exists(current_path):
                # Check if either exe exists
                found_exe = None
                for exe_name in ["WizardGraphicalClient.exe", "Wizard101.exe"]:
                    exe_path = os.path.join(current_path, exe_name)
                    if os.path.exists(exe_path):
                        found_exe = exe_name
                        break
                
                if found_exe:
                    self.path_label.setText(f"{source_tag} {current_path}\n({found_exe})")
                    self.path_label.setStyleSheet("font-size: 10px; padding: 8px; background-color: #141F14; border: 1px solid #203820; border-radius: 6px; color: #86EFAC;")
                else:
                    self.path_label.setText(f"{source_tag} {current_path}\n(No Wizard101 exe found)")
                    self.path_label.setStyleSheet("font-size: 10px; padding: 8px; background-color: #1E1414; border: 1px solid #3D2020; border-radius: 6px; color: #FF8080;")
            else:
                try:
                    auto_path = get_game_path()
                    self.path_label.setText(f"[AUTO] {auto_path}")
                    self.path_label.setStyleSheet("font-size: 10px; padding: 8px; background-color: #1F1A14; border: 1px solid #403424; border-radius: 6px; color: #FCD34D;")
                except:
                    self.path_label.setText("Wizard101 not found - Click Standalone, Steam or Browse")
                    self.path_label.setStyleSheet("font-size: 10px; padding: 8px; background-color: #1E1414; border: 1px solid #3D2020; border-radius: 6px; color: #FF8080;")
    
    def show_background_settings(self):
        """Show background settings dialog"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Image",
            _cfg.get('background_path', ''),
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )
        
        if file_path:
            _cfg['background_type'] = 'image'
            _cfg['background_path'] = file_path
            save_config(_cfg)
            self.apply_background()
            self.update_status("Background updated")
    
    def remove_background(self):
        """Remove custom background and return to default gradient"""
        _cfg['background_type'] = 'gradient'
        _cfg['background_path'] = None
        save_config(_cfg)
        self._apply_default_background()
        self.update_status("Background removed - using default gradient")
    
    def update_status(self, message: str):
        """Update status message"""
        if hasattr(self, 'status_bar'):
            self.status_bar.showMessage(message, 5000)  # Show for 5 seconds
        print(f"Status: {message}")  # Also log to console

    # --- TOOLS ---
    def open_pet_calculator(self):
        """Open Pet Calculator tool"""
        dlg = PetCalculatorDialog(self)
        dlg.exec()

    def open_pet_wow_returner(self):
        """Open Pet WoW Returner tool"""
        dlg = PetWoWReturnerDialog(self)
        dlg.exec()

    def open_damage_calculator(self):
        """Open Damage Calculator tool"""
        dlg = DamageCalculatorDialog(self)
        dlg.exec()

    def open_settings_dialog(self):
        """Open custom settings dialog with server selection, logs, clear accounts, and reset"""
        dialog = SettingsDialog(self)
        dialog.exec()

    def open_vani_discord(self):
        """Open Discord direct message with Vani (ID: 622454645742108692)"""
        discord_uri = "discord://discord.com/users/622454645742108692"
        web_url = "https://discord.com/users/622454645742108692"
        opened = False
        try:
            opened = QDesktopServices.openUrl(QUrl(discord_uri))
        except Exception:
            pass
        if not opened:
            try:
                import webbrowser
                webbrowser.open(web_url)
            except Exception as e:
                print(f"Could not open Discord: {e}")

    def toggle_maximize(self):
        """Toggle maximize and normal window state"""
        if self.isMaximized():
            self.showNormal()
            if hasattr(self, 'title_bar') and hasattr(self.title_bar, 'max_btn'):
                self.title_bar.max_btn.setText("\uE922")
                self.title_bar.max_btn.setToolTip("Maximize")
        else:
            self.showMaximized()
            if hasattr(self, 'title_bar') and hasattr(self.title_bar, 'max_btn'):
                self.title_bar.max_btn.setText("\uE923")
                self.title_bar.max_btn.setToolTip("Restore")

    def closeEvent(self, event):
        """Handle application closing"""
        # Save window geometry and compact_mode state
        if hasattr(self, 'mode_stack') and self.mode_stack.currentIndex() == 0:
            _cfg['window_size'] = [self.width(), self.height()]
            _cfg['full_window_size'] = [self.width(), self.height()]
            _cfg['compact_mode'] = False
        else:
            _cfg['compact_mode'] = True
        _cfg['window_position'] = [self.x(), self.y()]
        save_config(_cfg)

        if hasattr(self, 'discord_rpc') and self.discord_rpc:
            try:
                self.discord_rpc.stop()
            except Exception:
                pass
        
        event.accept()
    
    def resizeEvent(self, event):
        """Handle window resize"""
        super().resizeEvent(event)
        # Update magic particles size
        if hasattr(self, 'magic_particles'):
            self.magic_particles.setGeometry(0, 0, self.width(), self.height())
        # Update background label size
        if hasattr(self, 'background_label'):
            self.background_label.setGeometry(0, 0, self.width(), self.height())
        # Reapply background on resize
        QTimer.singleShot(100, self.apply_background)

def main():
    """Main application entry point"""
    # Set Windows AppUserModelID BEFORE QApplication is created
    # This is essential for Windows to group taskbar icons and display the custom favicon
    try:
        myappid = f'quick101.launcher.app.v{APP_VERSION}'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        print(f"AppUserModelID error: {e}")

    app = QApplication(sys.argv)
    app.setApplicationName("Quick101")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Quick101")
    
    # Set application-wide icon
    icon_path = get_app_icon_path(prefer_ico=True)
    png_path = get_app_icon_path(prefer_ico=False)
    app_icon = QIcon()
    if icon_path and os.path.exists(icon_path):
        app_icon.addFile(icon_path)
    if png_path and os.path.exists(png_path) and png_path != icon_path:
        app_icon.addFile(png_path)
        
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
        print(f"Set application icon from: {icon_path or png_path}")
    else:
        print("No icon file found!")
    
    # Set application style and modern typography matching Wizard101Calculator
    app.setStyle('Fusion')
    app_font = QFont("Segoe UI", 10)
    app.setFont(app_font)
    
    # Create and show main window
    launcher = Quick101Launcher()
    if not app_icon.isNull():
        launcher.setWindowIcon(app_icon)
    
    launcher.show()
    
    # Apply Windows 11 Immersive Dark Mode matching Wizard101Calculator (Win11Dwm)
    try:
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dark_val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            int(launcher.winId()), DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark_val), ctypes.sizeof(dark_val)
        )
    except Exception:
        pass
    
    # Windows-specific taskbar icon setup
    def setup_windows_icon():
        try:
            hwnd = int(launcher.winId())
            ico_file = get_app_icon_path(prefer_ico=True)
            hicon_large = None
            hicon_small = None
            
            # Method 1: Load directly from multi-resolution .ico file
            if ico_file and os.path.exists(ico_file):
                try:
                    abs_ico = os.path.abspath(ico_file)
                    hicon_large = ctypes.windll.user32.LoadImageW(
                        None, abs_ico, 1, 32, 32, 0x00000010  # IMAGE_ICON, LR_LOADFROMFILE
                    )
                    hicon_small = ctypes.windll.user32.LoadImageW(
                        None, abs_ico, 1, 16, 16, 0x00000010
                    )
                except Exception as e:
                    print(f"LoadImageW error: {e}")
            
            # Method 2: Extract from executable if frozen
            if (not hicon_large or not hicon_small) and getattr(sys, 'frozen', False):
                try:
                    h1 = ctypes.c_void_p()
                    h2 = ctypes.c_void_p()
                    if ctypes.windll.shell32.ExtractIconExW(sys.executable, 0, ctypes.byref(h1), ctypes.byref(h2), 1) > 0:
                        if not hicon_large and h1.value:
                            hicon_large = h1.value
                        if not hicon_small and h2.value:
                            hicon_small = h2.value
                except Exception as e:
                    print(f"ExtractIconExW error: {e}")
            
            # Send WM_SETICON to window handle
            if hicon_large:
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon_large)  # WM_SETICON, ICON_LARGE (32x32/taskbar)
            if hicon_small:
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon_small)  # WM_SETICON, ICON_SMALL (16x16/titlebar)
                
            # Set window class icon (GCLP_HICON = -14, GCLP_HICONSM = -34)
            try:
                set_class = getattr(ctypes.windll.user32, 'SetClassLongPtrW', None) or getattr(ctypes.windll.user32, 'SetClassLongW')
                if hicon_large:
                    set_class(hwnd, -14, hicon_large)
                if hicon_small:
                    set_class(hwnd, -34, hicon_small)
            except Exception:
                pass
                
            ctypes.windll.user32.UpdateWindow(hwnd)
        except Exception as e:
            print(f"Windows icon setup failed: {e}")
    
    QTimer.singleShot(50, setup_windows_icon)
    
    # Center window on first run
    if _cfg.get('window_position') == [100, 100]:
        screen = app.primaryScreen().geometry()
        launcher.move(
            (screen.width() - launcher.width()) // 2,
            (screen.height() - launcher.height()) // 2
        )
    
    return app.exec()

if __name__ == '__main__':
    sys.exit(main())