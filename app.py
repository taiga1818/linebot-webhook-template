from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, TextSendMessage
import os, cv2, numpy as np
from io import BytesIO
import requests, traceback, threading

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

@app.route("/", methods=["GET"])
def health_check():
    return "LINE Bot is running!"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        signature = request.headers.get("X-Line-Signature")
        if not signature:
            abort(400)
        body = request.get_data(as_text=True)
        handler.handle(body, signature)
        return "OK"
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print(f"Webhook Error: {e}")
        traceback.print_exc()
        abort(500)

def process_image_async(event, image_data):
    try:
        image_array = np.frombuffer(image_data, dtype=np.uint8)
        img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if img is None:
            raise Exception("画像読み込み失敗")

        if img.shape[1] > 600 or img.shape[0] > 450:
            scale = min(600/img.shape[1], 450/img.shape[0])
            img = cv2.resize(img, (int(img.shape[1]*scale), int(img.shape[0]*scale)))

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        red1 = cv2.inRange(hsv, (0, 100, 100), (10, 255, 255))
        red2 = cv2.inRange(hsv, (160, 100, 100), (180, 255, 255))
        red_mask = cv2.bitwise_or(red1, red2)
        red_ratio = np.sum(red_mask > 0) / red_mask.size

        green_mask = cv2.inRange(hsv, (40, 40, 40), (80, 255, 255))
        green_ratio = np.sum(green_mask > 0) / green_mask.size

        yellow_mask = cv2.inRange(hsv, (20, 60, 150), (35, 255, 255))
        yellow_ratio = np.sum(yellow_mask > 0) / yellow_mask.size

        if yellow_ratio > 0.02:
            reply = "⚠️ 僕の嫌いな色があるにゃん。"
        elif red_ratio > 0.02 and green_ratio > 0.02:
            reply = "🔴赤も🟢緑もありますにゃん！"
        elif red_ratio > 0.02:
            reply = "🔴赤がありますにゃん！"
        elif green_ratio > 0.02:
            reply = "🟢緑がありますにゃん！"
        else:
            reply = "🔍赤も緑も見つからないにゃん。"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
    except Exception as e:
        print(f"Async Error: {e}")
        traceback.print_exc()
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ エラーが起きたにゃん…"))
        except:
            print("Reply failed")

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    try:
        message_content = line_bot_api.get_message_content(event.message.id)
        image_data = b''.join(chunk for chunk in message_content.iter_content(8192))
        threading.Thread(target=process_image_async, args=(event, image_data)).start()
    except Exception as e:
        print(f"Handle Error: {e}")
