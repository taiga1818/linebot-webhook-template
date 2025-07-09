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
    reply = "🐾 画像をうまく解析できなかったにゃん。"

    try:
        message_content = line_bot_api.get_message_content(event.message.id)
        image_bytes = BytesIO(message_content.content)
        image_array = np.asarray(bytearray(image_bytes.read()), dtype=np.uint8)

        img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if img is None:
            reply = "💢 画像の読み込みに失敗したにゃん。"
        else:
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            red1 = cv2.inRange(hsv, (0, 100, 100), (10, 255, 255))
            red2 = cv2.inRange(hsv, (160, 100, 100), (180, 255, 255))
            red_mask = cv2.bitwise_or(red1, red2)

            total_pixels = red_mask.size if red_mask.size > 0 else 1  # ゼロ除算防止
            red_pixels = np.sum(red_mask > 0)
            red_ratio = red_pixels / total_pixels

            if red_ratio > 0.02:
                reply = "🔴 赤がありますね！"
            else:
                reply = "🟢 赤は見つかりませんでした。"

    except Exception as e:
        print("例外が発生しました:", str(e))
        reply = "⚠️ 画像処理中にエラーが発生したにゃん。"

    try:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )
    except Exception as e:
        print("返信エラー:", str(e))



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
