import cv2
import yt_dlp
import easyocr
import numpy as np
import time
import platform
import threading
from difflib import SequenceMatcher
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# === Firebase Setup (from local JSON file) ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(BASE_DIR, "testapi.json")
with open(cred_path, "r") as f:
    firebase_cred_dict = json.load(f)

cred = credentials.Certificate(firebase_cred_dict)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://alg1-457f6-default-rtdb.firebaseio.com/',
})

# === GUI Check ===
DISPLAY_GUI = True
if platform.system().lower() in ["linux", "darwin"]:
    DISPLAY_GUI = False

def test_imshow():
    try:
        cv2.imshow("Test", np.zeros((10, 10), dtype=np.uint8))
        cv2.waitKey(1)
        cv2.destroyAllWindows()
        return True
    except cv2.error:
        return False

if not test_imshow():
    print("cv2.imshow not supported. Disabling GUI.")
    DISPLAY_GUI = False

# === YouTube URL ===
url = "https://www.youtube.com/live/jkP1Sw7M2iU"

# === OCR Reader ===
reader = easyocr.Reader(['en'], gpu=False)

# === Helper Classes ===
class YouTubeStream:
    def __init__(self, url):
        self.url = url
        self.cap = None

    def connect(self):
        ydl_opts = {'format': 'best[ext=mp4]/bestvideo+bestaudio/best'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(self.url, download=False)
            direct_url = info_dict["url"]
        self.cap = cv2.VideoCapture(direct_url)

    def read_frame(self):
        if not self.cap or not self.cap.isOpened():
            self.connect()
        ret, frame = self.cap.read()
        return ret, frame

    def release(self):
        if self.cap:
            self.cap.release()

def is_trading_signal(text):
    txt = text.lower()
    return any(k in txt for k in ["buy signal", "short signal", "take profit"])

def fuzzy_match(text, keyword, threshold=0.7):
    return SequenceMatcher(None, text.lower(), keyword.lower()).ratio() >= threshold

SUPPLY_ZONE_KEYWORDS = ["supply zone", "sup zone", "suply zone", "supply zo", "sup zo"]
DEMAND_ZONE_KEYWORDS = ["demand zone", "dem zone", "d zone", "dem zo", "dmd zone"]

# === Main Loop ===
def yt_main_loop():
    prev_aggregated = None
    first_signal_set = False
    last_known_signal = {"text": "", "price": "AUTO", "coordinates": "X:Y"}

    while True:
        try:
            stream = YouTubeStream(url)
            stream.connect()
            print("Connected to stream.")
            retry_count = 0

            while True:
                ret, frame = stream.read_frame()
                if not ret or frame is None:
                    retry_count += 1
                    if retry_count >= 5:
                        print("Stream error encountered. Restarting stream...")
                        break
                    time.sleep(5)
                    continue
                else:
                    retry_count = 0

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                results = reader.readtext(gray)

                all_signals = []

                for (bbox, text, prob) in results:
                    (tl, _, br, _) = bbox
                    x1, y1 = map(int, tl)
                    _, y2 = map(int, br)
                    lower_text = text.lower().strip()

                    if is_trading_signal(lower_text):
                        all_signals.append((x1, y1, text))

                last_signal_data = {"text": "", "price": "AUTO", "coordinates": "X:Y"}

                if not first_signal_set and all_signals:
                    all_signals.sort(key=lambda s: s[0], reverse=True)
                    _, _, rtext = all_signals[0]
                    last_signal_data = {"text": rtext, "price": "AUTO", "coordinates": "X:Y"}
                    first_signal_set = True
                elif all_signals:
                    all_signals.sort(key=lambda s: s[0], reverse=True)
                    _, _, rtext = all_signals[0]
                    last_signal_data = {"text": rtext, "price": "AUTO", "coordinates": "X:Y"}

                if last_signal_data.get("text"):
                    last_known_signal = last_signal_data

                aggregated = {
                    "last_signal": last_known_signal,
                    "supply_zone": {"min": "AUTO", "max": "AUTO"},
                    "demand_zone": {"min": "AUTO", "max": "AUTO"}
                }

                if aggregated != prev_aggregated:
                    try:
                        db.reference("signal_MAIN").set(aggregated)
                        db.reference("signal").set(aggregated)
                        print("✅ Updated Firebase:", aggregated)
                        prev_aggregated = aggregated
                    except Exception as e:
                        print("❌ Firebase update error:", e)

                if DISPLAY_GUI:
                    disp_frame = cv2.resize(frame, (1366, 720))
                    cv2.imshow("YouTube Live Stream - Signal Detection", disp_frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        stream.release()
                        cv2.destroyAllWindows()
                        return

                time.sleep(10)

            stream.release()
            cv2.destroyAllWindows()
            time.sleep(5)

        except Exception as e:
            print("❌ Exception in main loop:", e)
            time.sleep(5)
            if 'stream' in locals():
                stream.release()
            cv2.destroyAllWindows()

if __name__ == "__main__":
    yt_main_loop()
