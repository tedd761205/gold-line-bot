import os
import re
import requests
import urllib3
import yfinance as yf
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction
)

# 關閉 SSL 憑證警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

# 輔助函式：透過 yfinance 自動抓取國際金價與匯率並換算
def get_live_gold_prices():
    try:
        gold_futures = yf.Ticker("GC=F").history(period="1d")
        twd_rate = yf.Ticker("TWD=X").history(period="1d")

        if gold_futures.empty or twd_rate.empty:
            return None

        gold_usd = gold_futures["Close"].iloc[-1]
        usd_twd = twd_rate["Close"].iloc[-1]

        # 單位換算公式：1 盎司 = 31.1034768 公克，1 台錢 = 3.75 公克
        price_per_gram = (gold_usd * usd_twd) / 31.1034768
        price_per_mace = price_per_gram * 3.75

        # 銀樓實體參考價 (預估加減價邏輯)
        silver_sell_mace = price_per_mace + 250
        silver_buy_mace = price_per_mace - 500

        # 銀樓每公克換算價
        silver_sell_gram = silver_sell_mace / 3.75
        silver_buy_gram = silver_buy_mace / 3.75

        return {
            "sell_mace": int(round(silver_sell_mace)),
            "sell_gram": int(round(silver_sell_gram)),
            "buy_mace": int(round(silver_buy_mace)),
            "buy_gram": int(round(silver_buy_gram)),
            "intl_mace": int(round(price_per_mace)),
            "intl_gram": int(round(price_per_gram)),
            "gold_usd": gold_usd,
            "usd_twd": usd_twd
        }
    except Exception as e:
        print(f"取得即時金價錯誤: {e}")
        return None

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    
    # 1. 報價 (排版優化版)
    if user_msg == "報價":
        prices = get_live_gold_prices()
        if prices:
            reply_text = (
                "💰 【今日黃金牌價】\n"
                "───────────────\n"
                f"🔴 賣出（客買）：\n"
                f"   ${prices['sell_mace']:,} / 錢  |  ${prices['sell_gram']:,} / g\n\n"
                f"🟢 買入（客賣）：\n"
                f"   ${prices['buy_mace']:,} / 錢  |  ${prices['buy_gram']:,} / g\n"
                "───────────────\n"
                f"📈 國際：${prices['gold_usd']:,.1f} | 匯率：{prices['usd_twd']:.2f}\n"
                f"   • 國際換算：${prices['intl_mace']:,} 錢 (${prices['intl_gram']:,} g)\n"
                "───────────────\n"
                "💡 提示：輸入「買入 項鍊 1錢 10250」即可記錄交易！"
            )
        else:
            reply_text = (
                "💰 【今日黃金牌價】\n"
                "───────────────\n"
                "🔴 賣出（客買）：$10,250 / 錢  |  $2,733 / g\n"
                "🟢 買入（客賣）：$9,100 / 錢  |  $2,427 / g\n"
                "───────────────\n"
                "⚠️ 目前無法取得即時國際金價，已顯示預設參考價。\n"
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
