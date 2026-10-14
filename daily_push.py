import os
import requests
import urllib3
import yfinance as yf

# 關閉 SSL 憑證警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# 1. 抓取黃金與匯率並計算價格 (更新版格式)
def get_gold_prices():
  try:
    # 抓取黃金期貨與美元兌台幣匯率
    gold_futures = yf.Ticker("GC=F").history(period="1d")
    twd_rate = yf.Ticker("TWD=X").history(period="1d")

    if gold_futures.empty or twd_rate.empty:
      return "❌ 無法取得黃金或匯率資料"

    gold_usd = gold_futures["Close"].iloc[-1]
    usd_twd = twd_rate["Close"].iloc[-1]

    # 單位換算公式：
    # 1 盎司 = 31.1034768 公克
    # 1 台錢 = 3.75 公克
    # 1 台兩 = 10 台錢 = 37.5 公克
    price_per_gram = (gold_usd * usd_twd) / 31.1034768
    price_per_mace = price_per_gram * 3.75
    price_per_tael = price_per_mace * 10

    # 銀樓實體參考價 (預估加減價邏輯)
    # 賣出參考價 (+256元/克 換算回台錢約 +250/台錢)
    silver_sell_mace = price_per_mace + 250
    # 買入參考價 (-544元/克 換算回台錢約 -500/台錢)
    silver_buy_mace = price_per_mace - 500

    msg = f"""每日黃金價格自動回報 (Yahoo Finance 數據源)：

【國際黃金與匯率】
------------------------------------------
‧ 國際金價： USD $ {gold_usd:,.1f} / 盎司
‧ 美元匯率： 1 美元 = {usd_twd:.2f} 台幣

【換算台幣價格 (約略值)】
------------------------------------------
‧ 每公克換算： NT$ {price_per_gram:,.1f} 元 / 公克
‧ 每台錢換算： NT$ {int(round(price_per_mace)):,} 元 / 台錢
‧ 每台兩換算： NT$ {int(round(price_per_tael)):,} 元 / 台兩

【銀樓實體參考價 (預估)】
------------------------------------------
‧ 銀樓賣出參考價： NT$ {int(round(silver_sell_mace)):,} 元 / 台錢
‧ 銀樓買入參考價： NT$ {int(round(silver_buy_mace)):,} 元 / 台錢

※ 註：1 台兩 = 10 台錢 = 37.5 公克。銀樓實體價含加工與損耗折價。
※ 資料來源：Yahoo Finance API (GC=F)"""

    return msg
  except Exception as e:
    return f"❌ 計算黃金價格發生錯誤: {str(e)}"


# 2. 抓取氣象資料
def get_weather_report():
  api_key = os.environ.get("CWA_API_KEY")
  if not api_key:
    return "❌ 找不到 CWA_API_KEY 環境變數"

  url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"
  cities = ["基隆市", "新北市"]
  target_districts = {"基隆市": ["信義區", "仁愛區"], "新北市": ["淡水區"]}

  weather_results = ["\n🌤️ 【各地即時天氣預報】"]

  for city in cities:
    params = {"Authorization": api_key, "format": "JSON", "locationName": city}
    response = requests.get(url, params=params, verify=False)

    if response.status_code != 200:
      continue

    data = response.json()
    locations = data.get("records", {}).get("location", [])

    for loc in locations:
      loc_name = loc.get("locationName")
      if loc_name in target_districts:
        weather_elements = loc.get("weatherElement", [])
        element_dict = {}
        for elem in weather_elements:
          name = elem.get("elementName")
          times = elem.get("time", [])
          if times:
            param = times[0].get("parameter", {})
            element_dict[name] = param.get("parameterName")

        wx = element_dict.get("Wx", "未知")
        pop = element_dict.get("PoP", "未知")
        min_t = element_dict.get("MinT", "未知")
        max_t = element_dict.get("MaxT", "未知")

        for dist in target_districts[loc_name]:
          weather_results.append(
              f"📍 {city}{dist}\n"
              f"   • 天氣: {wx}\n"
              f"   • 降雨機率: {pop}%\n"
              f"   • 氣溫: {min_t}°C ~ {max_t}°C"
          )

  return "\n".join(weather_results)


# 3. 發送 LINE 訊息
def send_line_message(message_text):
  access_token = os.environ.get("LINE_ACCESS_TOKEN")
  user_id = os.environ.get("LINE_USER_ID")

  if not access_token or not user_id:
    print("❌ 錯誤：找不到 LINE 相關環境變數")
    return

  url = "https://api.line.me/v2/bot/message/push"
  headers = {
      "Content-Type": "application/json",
      "Authorization": f"Bearer {access_token}",
  }

  payload = {
      "to": user_id,
      "messages": [{"type": "text", "text": message_text}],
  }

  response = requests.post(url, headers=headers, json=payload)
  if response.status_code == 200:
    print("✅ LINE 推播訊息成功！")
  else:
    print(f"❌ LINE 推播失敗: {response.text}")


if __name__ == "__main__":
  # 組合訊息
  gold_msg = get_gold_prices()
  weather_msg = get_weather_report()

  final_message = f"{gold_msg}\n{weather_msg}"

  print(final_message)
  # 執行發送
  send_line_message(final_message)
