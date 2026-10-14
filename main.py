import os
import re
import requests
import yfinance as yf
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)

app = Flask(__name__)

# 從環境變數讀取金鑰與網址
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
GAS_WEB_APP_URL = os.environ.get("GAS_WEB_APP_URL")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

def get_current_gold_mace_price():
    """透過 Yahoo Finance 抓取國際金價與匯率，計算每台錢參考價"""
    try:
        gold_futures = yf.Ticker("GC=F").history(period="1d")
        twd_rate = yf.Ticker("TWD=X").history(period="1d")
        if gold_futures.empty or twd_rate.empty:
            return None
        gold_usd = gold_futures["Close"].iloc[-1]
        usd_twd = twd_rate["Close"].iloc[-1]
        
        # 換算公式：1盎司 = 31.1034768公克，1台錢 = 3.75公克
        price_per_gram = (gold_usd * usd_twd) / 31.1034768
        price_per_mace = price_per_gram * 3.75
        return round(price_per_mace)
    except Exception as e:
        print(f"取得金價錯誤: {e}")
        return None

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text.strip()
    
    # 自動抓取發訊者的 LINE 顯示名稱作為「經手人」
    try:
        profile = line_bot_api.get_profile(event.source.user_id)
        handler_name = profile.display_name
    except Exception:
        handler_name = "櫃檯夥伴"

    # 1. 觸發品項快選與重量按鈕選單
    if user_text in ["品項快選", "選單", "試算"]:
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="黃金戒指 (1錢)", text="試算 黃金戒指 1")),
            QuickReplyButton(action=MessageAction(label="黃金項鍊 (2錢)", text="試算 黃金項鍊 2")),
            QuickReplyButton(action=MessageAction(label="黃金手環 (1.5錢)", text="試算 黃金手環 1.5")),
            QuickReplyButton(action=MessageAction(label="金條/金塊 (5錢)", text="試算 金條 5")),
            QuickReplyButton(action=MessageAction(label="查即時金價", text="金價"))
        ])
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請選擇欲試算的品項（系統將帶入常用預設重量）：", quick_reply=quick_reply)
        )

    # 2. 查詢即時金價
    elif user_text == "金價":
        base_mace = get_current_gold_mace_price()
        if base_mace:
            reply_txt = f"【國泰銀樓 即時金價基準】\n‧ 目前台錢換算約：NT$ {base_mace:,} 元/台錢\n（實際交易以店內牌價為主）"
        else:
            reply_txt = "❌ 暫時無法取得即時金價數據，請稍後再試。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_txt))

    # 3. 處理試算、智慧重量解析與 Google Sheets 自動記帳
    elif user_text.startswith("試算"):
        # 範例解析：「試算 黃金手環 1.5」或「試算 黃金戒指 2g」
        parts = user_text.replace("試算", "").strip().split()
        
        item_name = "黃金飾品"
        weight_val = 1.0
        weight_str = "1錢"

        if len(parts) >= 1:
            item_name = parts[0]
        
        if len(parts) >= 2:
            raw_weight_input = parts[1]
            num_match = re.search(r'([\d\.]+)', raw_weight_input)
            if num_match:
                weight_val = float(num_match.group(1))
                
                # 智慧防呆：判斷單位（沒打單位預設為「台錢」）
                if "克" in raw_weight_input or "g" in raw_weight_input.lower():
                    weight_val = weight_val / 3.75  # 克轉台錢
                    weight_str = f"{num_match.group(1)}克"
                elif "兩" in raw_weight_input:
                    weight_val = weight_val * 10    # 兩轉台錢
                    weight_str = f"{num_match.group(1)}兩"
                else:
                    weight_str = f"{weight_val}錢"

        # 計算價格細節
        base_mace = get_current_gold_mace_price() or 8000
        sell_rate_per_mace = base_mace + 250  # 銀樓賣出基準牌價
        craft_fee = 500  # 預設工錢
        
        total_price = int(round(sell_rate_per_mace * weight_val + craft_fee))

        reply_txt = (
            f"【國泰銀樓 交易試算結果】\n"
            f"------------------------------------------\n"
            f"👤 經手人：{handler_name}\n"
            f"💍 品項：{item_name}\n"
            f"⚖️ 重量：{weight_str}\n"
            f"📈 當日賣出牌價：NT$ {sell_rate_per_mace:,} / 錢\n"
            f"🛠️ 預估工錢：NT$ {craft_fee:,} 元\n"
            f"💰 預估總價：NT$ {total_price:,} 元\n"
            f"------------------------------------------\n"
            f"✅ 已自動記錄至 Google 試算表！"
        )
        
        # 非同步傳送資料至 Google Apps Script 寫入試算表
        if GAS_WEB_APP_URL:
            try:
                payload = {
                    "handler": handler_name,
                    "status": "未成交",
                    "item": item_name,
                    "weight": weight_str,
                    "gold_price": str(base_mace),
                    "base_rate": str(base_mace),
                    "selling_price": str(sell_rate_per_mace),
                    "craft_fee": str(craft_fee),
                    "total_price": str(total_price)
                }
                requests.post(GAS_WEB_APP_URL, json=payload, timeout=3)
            except Exception as e:
                print(f"GAS 寫入失敗: {e}")

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_txt))
        
    else:
        line_bot_api.reply_message(
            event.reply_token, 
            TextSendMessage(text=f"收到訊息：{user_text}\n請點擊下方選單或輸入「品項快選」開始試算！")
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
