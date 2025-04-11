import cv2
import yt_dlp
import easyocr
import numpy as np
import time
import platform
import redis
import json
from difflib import SequenceMatcher
import threading
import torch

# Check for CUDA
use_cuda = torch.cuda.is_available()
print("CUDA is available, using GPU acceleration for OCR." if use_cuda else "CUDA not available, using CPU.")

# Redis connection
r = redis.Redis(host='localhost', port=6379, db=0)

# GUI check
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

# YouTube URL
url = "https://www.youtube.com/live/jkP1Sw7M2iU"

# OCR reader
reader = easyocr.Reader(['en'], gpu=use_cuda)

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

def get_existing_signal():
    try:
        stored = r.get("signal_MAIN")
        if stored:
            return json.loads(stored)
    except Exception as e:
        print("Error fetching signal from Redis:", e)
    return None

def yt_main_loop():
    first_signal_set = False
    last_known_signal = {"text": "", "price": "", "coordinates": ""}
    
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

                # Crop the rightmost 25% of the frame
                height, width = frame.shape[:2]
                roi_start = int(width * 0.75)
                roi = frame[:, roi_start:width]

                # Convert the cropped region to grayscale
                gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

                # Run OCR on the cropped region
                results = reader.readtext(gray_roi)

                all_signals = []
                
                for (bbox, text, prob) in results:
                    # Adjust bounding box coordinates relative to the full frame
                    (tl, tr, br, bl) = bbox
                    tl = (int(tl[0] + roi_start), int(tl[1]))
                    br = (int(br[0] + roi_start), int(br[1]))
                    x1, y1 = tl
                    lower_text = text.lower().strip()

                    if is_trading_signal(lower_text):
                        all_signals.append((x1, y1, text))
                    elif any(fuzzy_match(lower_text, kw) for kw in SUPPLY_ZONE_KEYWORDS):
                        pass  # ignored: zone detection disabled
                    elif any(fuzzy_match(lower_text, kw) for kw in DEMAND_ZONE_KEYWORDS):
                        pass  # ignored: zone detection disabled

                last_signal_data = {"text": "", "price": "", "coordinates": ""}

                if not first_signal_set and all_signals:
                    all_signals.sort(key=lambda s: s[0], reverse=True)
                    _, _, rtext = all_signals[0]
                    last_signal_data = {
                        "text": rtext,
                        "price": "",
                        "coordinates": ""
                    }
                    first_signal_set = True
                elif all_signals:
                    all_signals.sort(key=lambda s: s[0], reverse=True)
                    _, _, rtext = all_signals[0]
                    last_signal_data = {
                        "text": rtext,
                        "price": "",
                        "coordinates": ""
                    }

                # Update only if new signal is found
                if last_signal_data.get("text"):
                    last_known_signal = last_signal_data

                # Clear zone detection data
                supply_zone_data = {"min": "", "max": ""}
                demand_zone_data = {"min": "", "max": ""}

                aggregated = {
                    "last_signal": {
                        "text": last_known_signal.get("text", ""),
                        "price": "",
                        "coordinates": ""
                    },
                    "supply_zone": supply_zone_data,
                    "demand_zone": demand_zone_data
                }

                # Compare with the existing signal in Redis to write only when changed
                existing = get_existing_signal()
                if not existing or existing.get("last_signal", {}).get("text", "") != aggregated.get("last_signal", {}).get("text", ""):
                    try:
                        r.set("signal_MAIN", json.dumps(aggregated))
                        r.set("signal", json.dumps(aggregated))
                        print("Updated Redis:", aggregated)
                    except Exception as e:
                        print("Redis update error:", e)
                else:
                    print("Signal unchanged; skipping Redis update.")

                if DISPLAY_GUI:
                    # Display the full frame with an overlay rectangle highlighting the ROI
                    disp_frame = cv2.resize(frame, (1366, 720))
                    cv2.rectangle(disp_frame, (roi_start, 0), (width, height), (0, 255, 0), 2)
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
            print("Exception in main loop:", e)
            time.sleep(5)
            if 'stream' in locals():
                stream.release()
            cv2.destroyAllWindows()

def run_in_thread():
    t = threading.Thread(target=yt_main_loop, name="YouTubeOCR")
    t.daemon = True
    t.start()
    return t

if __name__ == "__main__":
    yt_main_loop()
