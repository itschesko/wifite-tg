# wifite-tg

<p align="center">
  <img src="https://github.com/user-attachments/assets/3caf8688-8f2c-4393-88fc-5984c7a05536" width="900">
</p>

**wifite-tg** is a telegram messenger bot wrapper for [Wifite2](https://github.com/derv82/wifite2), designed for quick and stealthy Wi-Fi scans during Red Team engagements. It features an auto-updatable wifite terminal in chat with the bot, takes user messages as input for operating wifite, gives the ability to parse captured handshakes in a hashcat format and to ping bot running machine's geolocation.

> **⚠️ Disclaimer**<br>
> This tool is intended strictly for **authorized use only.** It is designed for red teamers and security researchers with **explicit written permission** to perform security assessments.


> The developer assumes no liability for misuse, data theft, or any illegal activity conducted with this tool.<br>
> **Any use for unauthorized testing or criminal activity is strictly prohibited.**
---

## Installation

1. [Wifite2](https://github.com/derv82/wifite2) and [hcxtools](https://github.com/ZerBea/hcxtools) have to be already installed on your machine
2. Wifite2 should be in your $PATH as `wifite`, if not, make a symlink to a correct wifite2 location
   
   ```
   sudo ln -s /opt/wifite2/Wifite.py /usr/local/bin/wifite
   ```
3. Clone this repository
4. Patch wifite source<br>
### Find methods `get_terminal_height()` and `get_terminal_width()` in following files:
- `[$WIFITE_DIR]/wifite/util/color.py`
- `[$WIFITE_DIR]/wifite/util/scanner.py`
### Update methods code with the following:
```python
@staticmethod
def get_terminal_height():
    import os
    try:
        rows, columns = os.popen('stty size', 'r').read().split()
    except ValueError:
        rows, columns = 24, 80
    return int(rows)

@staticmethod
def get_terminal_width():
    import os
    try:
        rows, columns = os.popen('stty size', 'r').read().split()
    except ValueError:
        rows, columns = 24, 80
    return int(columns)

```

---

## Usage

The safest way to supply arguments is to store them in environmental variables.

**NOTE: THE BOT `/hashes` COMMAND TRIES TO FIND FILES IN THE SCRIPT $PWD FOLDER, SO KEEP THAT IN MIND**

> I strongly suggest to use raspberry pi with internal wifi module + external wifi module capable of monitoring mode, make the script provided below run at startup to prevent your raspberry pi from connecting to your wifi from external antenna and break the internet (It accesses the internet from interface `wlan0`, runs wifite on `wlan1`)

### Make a startup script - wifite-tg.sh
```bash
#!/bin/bash
ifconfig wlan1 down
export WIFITE_TOKEN="TELEGRAM_BOT_TOKEN"
export WIFITE_USER_ID="TELEGRAM_USER_ID"
export WIFITE_GOOGLE_KEY="GOOGLE_API_KEY"
export WIFITE_IFACE="wlan0"
cd /opt/wifite-tg/
python3 wifite-tg.py
```


![help](https://github.com/user-attachments/assets/2188215c-ab2c-43e0-9d65-bea895530d11)
---

## Bot Usage

**1. Bot commands are next:**
   ```
   /wifite - Launch Wifite
   /hashes - Parse captured hashes (./hs/* directory) and wifite cracked wifi list (./cracked.txt)
   /geo - Ask bot to send it's geolocation
   ```
  <img width="700" alt="1" src="https://github.com/user-attachments/assets/9e4c5f33-85d7-4f94-812e-820d12441784" />

<br><br>

**2. When **wifite** is running, the bot will auto-refresh wifite output in message every 5 seconds, to force refresh it press [🔃 Refresh] button**


<img width="500" alt="2" src="https://github.com/user-attachments/assets/a5dadc4c-04e2-41af-8468-98bc5a410591" />
<br><br>

**3. To send `Ctrl+C` to wifite, click on **[⏹ Stop]** button, keep in mind that sometimes wifite acts weird and doesn't interrupt the scan or interrupts it with a delay, so press that button, wait for about 3 seconds and then **[🔃 Refresh]** the output to check if it really did interrupt the scan**

**4. Once the scan is paused, if there are too many access points in the output and you don't see them all, you can press **[📊 Parse Table]** to parse the final wifite table**

**5. To stop the attack, press **[⏹ Stop]**, then look at the output and send the option that you want to choose (C for continue, s for skip, e for exit)**

<img width="500" alt="3" src="https://github.com/user-attachments/assets/caca2815-1322-412f-be39-0470c2e79cf7" /><br><br>

**6. To parse wifite cracked.txt and handhshakes, send **/hashes** command or press on the **[📄 Export Hashes]** button.**

<img width="500" alt="4" src="https://github.com/user-attachments/assets/108eb913-474b-45c0-8550-43387588fb83" /><br><br>
<img width="500" alt="5" src="https://github.com/user-attachments/assets/ce3a2465-e365-46c6-aaaf-7fb38dc54db5" /><br><br>

---
## Acknowledgements
This project wouldn't have been possible without the inspiration and contributions of the following tools and projects:

1. [ZerBea/hcxtools](https://github.com/ZerBea/hcxtools)
2. [Wifite2](https://github.com/derv82/wifite2)
3. [aircrack-ng](https://github.com/aircrack-ng/aircrack-ng)
4. [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI)

---

## License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.

