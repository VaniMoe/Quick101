# Quick101

<p align="center">
  <img src="Quick101.png" width="96" height="96" alt="Quick101 Logo" />
</p>

<p align="center">
  <strong>Fast, sleek, and modern multi-account launcher for Wizard101.</strong>
</p>

---

## ✨ Features

- **Multi-Account Quick Launch**: Save and organize multiple Wizard101 accounts categorized by your playstyle. Launch single accounts or entire teams with one click.
- **Steam & Standalone Support**: Native support for both KingsIsle Standalone and Steam installations with official Steam vector badges in the account list.
- **Server Routing**: Switch between US Server (`login.us.wizard101.com`), Europe Server (`login.eu.wizard101.com`), and Test Realm (`login.test.us.wizard101.com`) with a single click.
- **Compact & Full Modes**: Switch seamlessly between a minimal one-click Compact popup and the comprehensive full dashboard with category management.
- **Modern Dark UI**: Frameless Windows 11 design with interactive particle effects, crisp typography, and fluid transitions.
- **Background Logging**: Continuous background logging to `Documents/Quick101_Logs/` for debugging and transparency.
- **GitHub Auto-Update**: Automatic release checking and one-click self-updating directly from GitHub.

---

## 🚀 Installation & Running

### Requirements
- Windows 10 / 11
- Python 3.10+ (if running from source)

### Running from Source
```bash
# Install dependencies
pip install PyQt6 PyYAML Pillow

# Launch Quick101
python Quick101.py
```

### Building the Standalone Executable
You can run the included `Quick101Setup.bat` or build via PyInstaller:
```bash
pip install pyinstaller PyQt6 PyYAML Pillow
pyinstaller --clean Quick101.spec
```
The compiled executable will be generated at `dist/Quick101.exe`.

---

## ⚙️ Configuration
Credentials and settings are securely stored in `%APPDATA%\Quick101\`:
- `accounts.yml`: Encrypted/managed account storage
- `launcher_config.json`: User preferences, paths, and server configuration

---

## 👤 Credits & Support
Created by **Vani**  
Discord: `622454645742108692`
