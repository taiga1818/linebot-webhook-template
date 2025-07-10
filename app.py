from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, TextSendMessage
import os, cv2, numpy as np
from io import BytesIO
import requests
import traceback

app = Flask(__name__)

# 環境変数の確認
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

print("=== 環境変数確認 ===")
print(f"ACCESS_TOKEN: {'設定済み' if LINE_CHANNEL_ACCESS_TOKEN else '未設定'}")
print(f"SECRET: {'設定済み' if LINE_CHANNEL_SECRET else '未設定'}")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("❌ 環境変数が設定されていません")
    exit(1)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/", methods=["GET"])
def health_check():
    return "LINE Bot is running!"

@app.route("/webhook", methods=["POST"])
def webhook():
    print("=== Webhook受信 ===")
    try:
        signature = request.headers.get("X-Line-Signature")
        if not signature:
            print("❌ X-Line-Signatureヘッダーがありません")
            abort(400)
        
        body = request.get_data(as_text=True)
        print(f"Body length: {len(body)}")
        
        handler.handle(body, signature)
        print("✅ 処理完了")
        return "OK"
    except InvalidSignatureError:
        print("❌ Invalid signature")
        abort(400)
    except Exception as e:
        print(f"❌ Webhookエラー: {e}")
        traceback.print_exc()
        abort(500)

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    print("=== 画像処理開始 ===")
    message_content = None
    image_bytes = None
    img = None
    
    try:
        # 画像データ取得
        print("画像データ取得中...")
        message_content = line_bot_api.get_message_content(event.message.id)
        
        # BytesIOで画像データを読み込み（メモリ効率改善）
        image_data = b''
        for chunk in message_content.iter_content(chunk_size=8192):
            image_data += chunk
        
        print(f"画像データサイズ: {len(image_data)} bytes")
        
        # OpenCVで画像を読み込み
        print("OpenCV処理中...")
        image_array = np.frombuffer(image_data, dtype=np.uint8)
        img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        
        if img is None:
            print("❌ 画像の読み込みに失敗")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ 画像を読み込めませんでした")
            )
            return
        
        print(f"画像サイズ: {img.shape}")
        
        # 大きな画像の場合はリサイズ（メモリ節約）
        height, width = img.shape[:2]
        if width > 800 or height > 600:
            scale = min(800/width, 600/height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = cv2.resize(img, (new_width, new_height))
            print(f"リサイズ後: {img.shape}")
        
        # HSV変換
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # 赤検出
        red1 = cv2.inRange(hsv, (0, 100, 100), (10, 255, 255))
        red2 = cv2.inRange(hsv, (160, 100, 100), (180, 255, 255))
        red_mask = cv2.bitwise_or(red1, red2)
        red_ratio = np.sum(red_mask > 0) / red_mask.size
        
        # 緑検出
        green_mask = cv2.inRange(hsv, (40, 40, 40), (80, 255, 255))
        green_ratio = np.sum(green_mask > 0) / green_mask.size
        
        # 薄い黄色（嫌いな色）検出
        yellow_mask = cv2.inRange(hsv, (20, 60, 150), (35, 255, 255))
        yellow_ratio = np.sum(yellow_mask > 0) / yellow_mask.size
        
        print(f"色の検出結果: 赤={red_ratio:.4f}, 緑={green_ratio:.4f}, 黄={yellow_ratio:.4f}")
        
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
        
        print(f"返信メッセージ: {reply}")
        
        # 返信送信
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )
        
        print("✅ 画像処理完了")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ ネットワークエラー: {e}")
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ ネットワークエラーが発生したにゃん…")
            )
        except:
            print("❌ エラーメッセージの送信にも失敗")
            
    except cv2.error as e:
        print(f"❌ OpenCVエラー: {e}")
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ 画像処理でエラーが発生したにゃん…")
            )
        except:
            print("❌ エラーメッセージの送信にも失敗")
            
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        traceback.print_exc()
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ エラーが起きたにゃん…")
            )
        except:
            print("❌ エラーメッセージの送信にも失敗")
            
    finally:
        # メモリクリーンアップ
        if img is not None:
            del img
        if image_bytes is not None:
            del image_bytes
        if message_content is not None:
            del message_content
        print("=== メモリクリーンアップ完了 ===")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"=== サーバー起動 ===")
    print(f"Port: {port}")
    app.run(host="0.0.0.0", port=port, debug=True)
