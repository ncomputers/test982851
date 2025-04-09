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

# === Firebase Setup (embedded JSON) ===
firebase_cred_dict = {
    "type": "service_account",
    "project_id": "alg1-457f6",
    "private_key_id": "3cd134d21c1c26de2357f8581e3ffc85e2ee39de",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCt2wmvh4TOZrJQ\ntSC+iFUAk7Ymw+W70CmckO4ku4RULt4YFQ/6jLlhqRdZDoM61Ed0NzuIQBeys3XH\ng7GO54ybicdtcWcZmufpr1cT3tCOK40q8zFJlW3FLB5oS3cEHN1st2I4EhNfHzoc\n6UZVdxnEgju+wqdGRu0ousaVpRCBkAeVNU9Z6uBlfiTpAYcbqRwG6I5nAOcXEwq3\nrtra7l2bA0R7s+ZutIy/v9q3nhJoapMOeEdMccjrfQSnFiMAWwW45ZxUD72PGa3Z\n+YjUxh7IbKqmW+MiVhKjAj4vkwmbtLhfLLlZwFsQsjHuONdybXoKZtEv6tzitek4\nfb/dpqs7AgMBAAECggEABEm9ucheAkwMNyLJm3dRj4kMnEGxrWNxwbL/r1oNEO6d\niDIx3N1SseDJKby5iBXk4r8oAJM1c33vUfriua88B1sAtTAJSttqnYadxbVknplW\nMXUI1zWMNod4nKkPCiGyII46kHHxa+f2s1bZvFnXcLGFOafFwdTAnKYyJ8WY6Q7/\nuycPNV5lA0VYmM4sp7x/HMFyOsvM2isyykaxlrpB3dmbLWxUxrh+X9pjgjysZUsf\nJgeLmEtpEvz4F9ezNV0Jx+Iy4QPGH48hQ+IbVd/pvQBq+bATA/z6hTMDOc7nYhVo\nET8M8O1nxYAg63p/NGlV5N54vxIkRsWQBwfvltdU2QKBgQDVty7HOo7UU8LkWw2S\n3wpI92ZW5LCNL1OYnFicQKRs6fwKDUfA2BQOZZy5YWXsaBTe3IMcq9KVW2kcMsiF\nfv2l5tz5rhc6JoY8ApDWmlSZThNb3LNv//rKPYZr0ULT4lojVqHYU18XwK7zMzYM\nPz9lu8t2CVXUH8ZamgFvt0pmyQKBgQDQQO0I1Vc0L3hNYpmiejw8DyPx3DvJY6Kj\ni19uM3nheH5F7gyFZWS2swBHPfWYQyu+f0VxLoYJGmZFOkKrOeufoCjwWs8WXlTR\n7KrITvi09Lhoyq9SltHrP/8sMyQtm1PwMKPJsIClvva5nH1d6RDAw66QdofrL413\nTrqyzInP4wKBgBvNnwpQNfCtjPdEWTm4RpBDj07SpZ1YgNmjzWtWhY2dyypLnAAc\nnE9bLM55O1dMGxr7ORtrxxOjNsNyX9/uK3V/2VOqMF9iT6hS9SDWJxdiruYOilGR\nzcCtzGUOblE+a1eZl6ibAA4JBTmiee+R8t97VPbgNAhKsfVrf7BW+hjxAoGAYfhZ\nSpGKz7sRPl6HZj9Y/Owmfc6ctbZQud2ETISc7uxPgzhk3ZCAm86D7//+/N2Ew759\n/avkVH395M1utbyu0052U/R0fdJs1sEe6tLz/7Us1+eaKSFYqfJWagW5HFd5WoKX\nWvfU3aSDz3gGJlrRjc3A3qdUc9jQFXONMzY0Ev8CgYEAnZpIy8JKPf672qVEigDf\nXc5/DBczhn4CEUTKLQlZmdiCs95F1uUIsxIGiWaqCKfuNltE0ZOA+A+XblhGh+0S\nxtDAMctuq8RQqtkle6pceXvL/E/wjePf+bsytPxAyhfqKlXWyF1tg+HBr6HUMvjl\nI9tU2e96S0Ouwb5FaTYYAuw=\n-----END PRIVATE KEY-----\n",
    "client_email": "firebase-adminsdk-fbsvc@alg1-457f6.iam.gserviceaccount.com",
    "client_id": "104992658115730968345",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40alg1-457f6.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com"
}

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
