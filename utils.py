import os
import time
import shutil
import subprocess
from pathlib import Path

STEAM_CONFIG = Path("C:/Program Files (x86)/Steam/config")
DEPOTCACHE = STEAM_CONFIG / "depotcache"
STPLUGIN = STEAM_CONFIG / "stplug-in"

def copy_to_steam(game_folder):
    DEPOTCACHE.mkdir(parents=True, exist_ok=True)
    STPLUGIN.mkdir(parents=True, exist_ok=True)

    try:
        for file in Path(game_folder).iterdir():
            if file.is_file():
                if file.suffix == ".manifest":
                    shutil.copy2(file, DEPOTCACHE / file.name)
                elif file.suffix == ".lua":
                    shutil.copy2(file, STPLUGIN / file.name)
        return True
    except Exception:
        return False

def restart_steam():
    try:
        # ================== MATIKAN SEMUA PROSES STEAM ==================
        subprocess.run(
            ["taskkill", "/F", "/IM", "steam.exe", "/T"],
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        time.sleep(2)  # ✅ WAJIB! tunggu proses benar-benar mati

        # ================== CARI PATH STEAM DARI REGISTRY ==================
        import winreg

        steam_path = None
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"
            )
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            winreg.CloseKey(key)
        except:
            pass

        if steam_path:
            steam_exe = Path(steam_path) / "steam.exe"
        else:
            # fallback manual default
            steam_exe = Path("C:/Program Files (x86)/Steam/steam.exe")

        # ================== JALANKAN LAGI STEAM ==================
        if steam_exe.exists():
            subprocess.Popen(
                [str(steam_exe)],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            return True

        return False

    except Exception as e:
        print("Restart Steam Error:", e)
        return False
