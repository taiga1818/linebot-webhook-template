from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, TextSendMessage
import os, cv2, numpy as np
from io import BytesIO
import requests

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    try:
        message_content = line_bot_api.get_message_content(event.message.id)
        image_bytes = BytesIO(message_content.content)
        image_array = np.asarray(bytearray(image_bytes.read()), dtype=np.uint8)
        img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 赤検出
        red1 = cv2.inRange(hsv, (0, 100, 100), (10, 255, 255))
        red2 = cv2.inRange(hsv, (160, 100, 100), (180, 255, 255))
        red_mask = red1 + red2
        red_ratio = np.sum(red_mask > 0) / red_mask.size

        # 緑検出
        green_mask = cv2.inRange(hsv, (40, 40, 40), (80, 255, 255))
        green_ratio = np.sum(green_mask > 0) / green_mask.size

        # 薄い黄色（嫌いな色）検出
        yellow_mask = cv2.inRange(hsv, (20, 60, 150), (35, 255, 255))
        yellow_ratio = np.sum(yellow_mask > 0) / yellow_mask.size

        # 判定とメッセージ作成
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

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )

    except Exception as e:
        print(f"Error: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="⚠️ エラーが起きたにゃん…")
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
