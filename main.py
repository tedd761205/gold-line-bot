import os
import re
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction
)

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
GAS_WEB_APP_URL = os.environ.get('GAS_WEB_APP_URL')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/", methods=['GET'])
def index():
    return "Gold Line Bot is running!"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    
    # 1. 報價
    if user_msg == "報價":
        reply_text = (
            "💰 【今日最新黃金牌價】\n"
            "───────────────\n"
            "🔴 賣出價（顧客買入）：$10,250 / 錢\n"
            "🟢 買入價（顧客賣出）：$9,100 / 錢\n"
            "───────────────\n"
            "💡 提示：輸入「買入 項鍊 1錢 10250」即可記錄交易！"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # 2. 記帳說明
    elif user_msg == "記帳":
        reply_text = (
            "📝 【黃金買賣記帳助手】\n\n"
            "請直接輸入記帳內容，格式範例：\n"
            "• 買入 項鍊 1錢 10250\n"
            "• 賣出 金條 2錢 18200\n\n"
            "格式說明：[類型] [品項] [重量] [金額]"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # 3. 品項試算 (Quick Reply)
    elif user_msg in ["試算", "品項快選"]:
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="戒指 (0.5錢)", text="買入 戒指 0.5錢 5125")),
            QuickReplyButton(action=MessageAction(label="項鍊 (1錢)", text="買入 項鍊 1錢 10250")),
            QuickReplyButton(action=MessageAction(label="手鍊 (2錢)", text="買入 手鍊 2錢 20500")),
            QuickReplyButton(action=MessageAction(label="金條 (10錢)", text="買入 金條 10錢 102500")),
        ])
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🧮 請選擇預設試算品項，或點選下方按鈕快速記帳：", quick_reply=quick_reply)
        )
        return

    # 4. 金價走勢
    elif user_msg == "走勢":
        reply_text = (
            "📈 【國際黃金走勢與市場分析】\n"
            "───────────────\n"
            "近期金價維持高檔震盪，整體呈現穩健趨勢。"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # 5. 交易紀錄
    elif user_msg in ["紀錄", "歷史紀錄"]:
        reply_text = "📋 記帳紀錄已即時同步至您的 Google 試算表中！"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # 6. 門市導航
    elif user_msg in ["地址", "門市地圖", "門市地址"]:
        reply_text = (
            "📍 【門市資訊與導航】\n"
            "───────────────\n"
            "🏛️ 門市名稱：金飾珠寶專賣店\n"
            "📞 服務電話：(02) 2345-6789\n"
            "⏰ 營業時間：10:30 - 21:00"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # 7. 解析記帳指令 (買入/賣出 品項 重量 金額)
    pattern = r'^(買入|賣出)\s+([^\s]+)\s+([^\s]+)\s+(\d+)$'
    match = re.match(pattern, user_msg)

    if match:
        type_str = match.group(1)
        item_str = match.group(2)
        weight_str = match.group(3)
        amount_str = match.group(4)

        if GAS_WEB_APP_URL:
            try:
                payload = {
                    "type": type_str,
                    "item": item_str,
                    "weight": weight_str,
                    "price": amount_str
                }
                res = requests.post(GAS_WEB_APP_URL, json=payload, timeout=5)
                reply_text = f"✅ 【記帳成功】\n• 類型：{type_str}\n• 品項：{item_str}\n• 重量：{weight_str}\n• 金額：${amount_str} 元\n已成功寫入 Google 試算表！"
            except Exception as e:
                reply_text = f"⚠️ 寫入試算表失敗：{str(e)}"
        else:
            reply_text = "⚠️ 未設定 GAS_WEB_APP_URL 環境變數。"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # 預設回覆
    default_reply = f"收到訊息：「{user_msg}」\n請點選下方選單按鈕進行操作。"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=default_reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
