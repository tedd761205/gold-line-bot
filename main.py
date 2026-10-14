import os
import requests
import re
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction
)

app = Flask(__name__)

# 讀取環境變數
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
    
    # -------------------------------------------------------------
    # 1. 按鈕 A：今日金價 💰
    # -------------------------------------------------------------
    if user_msg == "報價":
        reply_text = (
            "💰 【今日最新黃金牌價】\n"
            "───────────────\n"
            "🔴 賣出價（顧客買入）：$10,250 / 錢\n"
            "🟢 買入價（顧客賣出）：$9,100 / 錢\n"
            "───────────────\n"
            "💡 提示：點擊「買賣記帳」或輸入如「買入 項鍊 1錢 10250」即可自動記錄！"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # -------------------------------------------------------------
    # 2. 按鈕 B：買賣記帳 📝 (跳出記帳說明與 Quick Reply 指引)
    # -------------------------------------------------------------
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

    # -------------------------------------------------------------
    # 3. 按鈕 C：品項試算 🧮
    # -------------------------------------------------------------
    elif user_msg in ["試算", "品項快選"]:
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="戒指 (0.5錢)", text="買入 戒指 0.5錢 5125")),
            QuickReplyButton(action=MessageAction(label="項鍊 (1錢)", text="買入 項鍊 1錢 10250")),
            QuickReplyButton(action=MessageAction(label="手鍊 (2錢)", text="買入 手鍊 2錢 20500")),
            QuickReplyButton(action=MessageAction(label="金條 (1兩)", text="買入 金條 10錢 102500")),
        ])
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🧮 請選擇預設試算品項，或直接點選以下快選按鈕：", quick_reply=quick_reply)
        )
        return

    # -------------------------------------------------------------
    # 4. 按鈕 D：金價走勢 📈
    # -------------------------------------------------------------
    elif user_msg == "走勢":
        reply_text = (
            "📈 【國際黃金走勢與市場分析】\n"
            "───────────────\n"
            "近期金價維持高檔震盪，受避險需求與貨幣政策影響，整體呈現穩健上升趨勢。\n\n"
            "🔍 如需查看即時 K 線圖表，可關注各大金融數據平台。"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # -------------------------------------------------------------
    # 5. 按鈕 E：交易紀錄 📋
    # -------------------------------------------------------------
    elif user_msg in ["紀錄", "歷史紀錄"]:
        reply_text = "📋 記帳紀錄已同步儲存於 Google 試算表中，您可以隨時開啟雲端試算表查看完整帳目！"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # -------------------------------------------------------------
    # 6. 按鈕 F：門市導航 📍
    # -------------------------------------------------------------
    elif user_msg in ["地址", "門市地圖"]:
        reply_text = (
            "📍 【門市資訊與導航】\n"
            "───────────────\n"
            "🏛️ 門市名稱：金飾珠寶專賣店\n"
            "📞 服務電話：(02) 2345-6789\n"
            "⏰ 營業時間：10:30 - 21:00\n"
            "🗺️ Google 地圖：https://maps.google.com"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # -------------------------------------------------------------
    # 7. 自動解析記帳指令並傳送至 Google 試算表 (GAS)
    # -------------------------------------------------------------
    # 正則表達式匹配：判斷是否包含 買入/賣出，並擷取品項、重量、金額
    pattern = r'^(買入|賣出)\s+([^\s]+)\s+([^\s]+)\s+(\d+)$'
    match = re.match(pattern, user_msg)

    if match:
        type_str = match.group(1)   # 買入 或 賣出
        item_str = match.group(2)   # 品項（如：項鍊）
        weight_str = match.group(3) # 重量（如：1錢）
        amount_str = match.group(4) # 金額（如：10250）

        # 呼叫 Google Apps Script 寫入 Google Sheet
        if GAS_WEB_APP_URL:
            try:
                payload = {
                    "type": type_str,
                    "item": item_str,
                    "weight": weight_str,
                    "price": amount_str
                }
                res = requests.post(GAS_WEB_APP_URL, json=payload, timeout=5)
                
                reply_text = (
                    f"✅ 【記帳成功】\n"
                    f"───────────────\n"
                    f"• 類型：{type_str}\n"
                    f"• 品項：{item_str}\n"
                    f"• 重量：{weight_str}\n"
                    f"• 金額：${amount_str} 元\n"
                    f"───────────────\n"
                    f"已成功備份至 Google 試算表！"
                )
            except Exception as e:
                reply_text = f"⚠️ 記帳連線失敗，請檢查 GAS 部署設定：{str(e)}"
        else:
            reply_text = "⚠️ 未設定 GAS_WEB_APP_URL 環境變數，無法同步至試算表。"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # 預設非關鍵字回覆
    default_reply = f"收到訊息：「{user_msg}」\n點選下方圖文選單按鈕，可使用報價、試算或記帳功能喔！"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=default_reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
