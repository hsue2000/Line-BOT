from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
from dotenv import load_dotenv
import os
import requests
from urllib.parse import quote
from linebot.models import TextSendMessage, FlexSendMessage

from linebot.models import (
    TextSendMessage,
    FlexSendMessage,
    QuickReply,
    QuickReplyButton,
    MessageAction,
)

import requests
from linebot.models import FlexSendMessage


def check_image_url(url):
    """檢查圖片連結是否正常（回應 200）"""
    try:
        r = requests.head(url, timeout=3)  # 用 HEAD 請求比較快
        return r.status_code == 200
    except:
        return False


def build_detail_flex(data_dict):
    """
    將單筆 JSON 轉成表單樣式的 Flex bubble
    支援欄位名稱中文化 + 欄位過濾
    """

    # 欄位對照表（英文 → 中文）
    field_map = {
        "Serial_No": "鑑定編號",
        "Name": "錢幣名稱",
        "Company": "鑑定公司",
        "Grade": "鑑定分數",
        "Description": "錢幣描述",
        "Nation": "鑄造國家",
        "Coin_Year": "鑄造年份",
        "Coin_Count": "鑄造數量",
        "Material": "鑄造材質",
        "Coin_kind": "錢幣現狀",
        "Coin_Source": "錢幣來源",
        "Location": "收納位置",
        "Note": "備註說明",
        "Date": "建立日期",
    }

    # ✅ 白名單：只顯示這些欄位（順序就是顯示順序）
    allowed_fields = [
        "Serial_No",
        "Company",
        "Grade",
        "Description",
        "Nation",
        "Coin_Year",
        "Coin_Count",
        "Material",
        "Coin_kind",
        "Coin_Source",
        "Location",
        "Note",
        "Date",
    ]

    # 標題優先顯示名稱，其次序號
    title = str(data_dict.get("Name") or data_dict.get("Serial_No") or "詳細資訊")

    # ==== 處理圖片連結 ====
    serial_no = str(data_dict.get("Serial_No", "")).strip()
    main_base_url = "https://hsue2000.synology.me/Coin_PIC/"  # 主圖片網址（要改成你的）
    backup_url = "https://hsue2000.synology.me/Coin_PIC/NO_PIC.jpg"  # 備用圖片

    # 主圖 = base_url + Serial_No + .jpg
    main_url = f"{main_base_url}{serial_no}.jpg" if serial_no else ""

    if serial_no and check_image_url(main_url):
        pic_url = main_url
    else:
        pic_url = backup_url

    FIELD_COLOR_MAP = {
        "Grade": "#FF4500",  # 橘色
        "Coin_kind": "#9400D3",  # 紫色
        "Serial_No": "#000000",  # 黑色
        "Location": "#227700",  # 綠色
        "Company": "#FF44AA",  # 粉紅色
    }

    # ===== 欄位 rows =====
    rows = []
    for k in allowed_fields:
        val = data_dict.get(k, "")
        if str(val).strip():
            value_color = FIELD_COLOR_MAP.get(k, "#0000FF")  # 預設藍色
            rows.append(
                {
                    "type": "box",
                    "layout": "baseline",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": field_map.get(k, k),
                            "size": "sm",
                            "color": "#666666",
                            "flex": 3,
                            "weight": "bold",
                        },
                        {
                            "type": "text",
                            "text": str(val),
                            "size": "sm",
                            "color": value_color,
                            "wrap": True,
                            "flex": 7,
                        },
                    ],
                }
            )

    # ===== Flex bubble（頂部 hero 大圖）=====
    bubble = {
        "type": "bubble",
        "hero": {
            "type": "image",
            "url": pic_url,
            "size": "xl",  # hero 最大值
            "aspectRatio": "4:3",  # 比 1:1 高
            "aspectMode": "fit",  # 等比例縮小完整顯示
            "action": {"type": "uri", "label": "查看原圖", "uri": pic_url},
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "lg"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "spacing": "sm",
                    "contents": rows,
                },
            ],
        },
    }

    return FlexSendMessage(alt_text="詳細資訊", contents=bubble)


last_results = []

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
SECRET = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
API_TOKEN = os.getenv("API_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL")

# 可使用的 LINE 使用者 ID 列表（White List）

WHITELIST = set(os.getenv("WHITELIST", "").split(","))

# print(whitelist)


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        SECRET.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


def build_list_bubble(
    rows,
    title="查詢結果",
    page=1,
    total_pages=1,
    row_action_prefix="錢幣",
    columns=("Serial_No", "Name", "Company", "Grade"),
):
    # 欄位標題列（置中 + 背景色）
    header = {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "backgroundColor": "#E0E0E0",
        "contents": [
            {
                "type": "text",
                "text": "鑑定編號",
                "size": "xs",
                "weight": "bold",
                "flex": 3,
                "align": "center",
                "wrap": True,
            },
            {
                "type": "text",
                "text": "錢幣名稱",
                "size": "xs",
                "weight": "bold",
                "flex": 3,
                "align": "center",
                "wrap": True,
            },
            {
                "type": "text",
                "text": "鑑定公司",
                "size": "xs",
                "weight": "bold",
                "flex": 3,
                "align": "center",
                "wrap": True,
            },
            {
                "type": "text",
                "text": "鑑定分數",
                "size": "xs",
                "weight": "bold",
                "flex": 3,
                "align": "center",
                "wrap": True,
            },
        ],
    }

    body_contents = [
        {
            "type": "text",
            "text": f"{title} (第{page}/{total_pages}頁)",
            "weight": "bold",
            "size": "md",  # 標題稍微大
            "align": "center",
            "color": "#333333",
        },
        {"type": "separator", "margin": "md"},
        header,
        {"type": "separator", "margin": "sm"},
    ]

    # 資料列（文字小 + 交錯底色）
    for idx, d in enumerate(rows):
        serial = str(d.get(columns[0], ""))
        name = str(d.get(columns[1], ""))
        company = str(d.get(columns[2], ""))
        grade = str(d.get(columns[3], ""))

        row_box = {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "backgroundColor": "#FFFFBB" if idx % 2 == 0 else "#BBFFEE",  # 交錯底色
            "contents": [
                {
                    "type": "text",
                    "text": serial,
                    "size": "sm",
                    "flex": 3,
                    "wrap": True,
                    "align": "start",
                },
                {
                    "type": "text",
                    "text": name,
                    "size": "sm",
                    "flex": 3,
                    "wrap": True,
                    "align": "start",
                },
                {
                    "type": "text",
                    "text": company,
                    "size": "sm",
                    "flex": 3,
                    "wrap": True,
                    "align": "center",
                },
                {
                    "type": "text",
                    "text": grade,
                    "size": "sm",
                    "flex": 3,
                    "align": "end",
                    "wrap": True,
                    "align": "center",
                },
            ],
            "action": {
                "type": "message",
                "label": "查詢詳情",
                "text": f"{row_action_prefix} {serial}",
            },
            "paddingAll": "6px",
        }
        body_contents.append(row_box)
        body_contents.append({"type": "separator", "margin": "sm"})

    # 分頁按鈕
    footer_contents = []
    if page > 1:
        footer_contents.append(
            {
                "type": "button",
                "style": "secondary",
                "height": "sm",
                "action": {
                    "type": "message",
                    "label": "上一頁",
                    "text": f"列表 {page-1}",
                },
            }
        )
    if page < total_pages:
        footer_contents.append(
            {
                "type": "button",
                "style": "primary",
                "height": "sm",
                "action": {
                    "type": "message",
                    "label": "下一頁",
                    "text": f"列表 {page+1}",
                },
            }
        )

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body_contents,
        },
        "footer": (
            {
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "contents": footer_contents,
            }
            if footer_contents
            else None
        ),
    }
    return bubble


def build_list_carousel(data, page=1, rows_per_bubble=10, title="查詢錢幣結果"):
    total_pages = (len(data) + rows_per_bubble - 1) // rows_per_bubble
    start_idx = (page - 1) * rows_per_bubble
    page_data = data[start_idx : start_idx + rows_per_bubble]

    bubble = build_list_bubble(
        page_data, title=title, page=page, total_pages=total_pages
    )
    return FlexSendMessage(alt_text="查詢錢幣結果列表", contents=bubble)


from linebot.models import QuickReply, QuickReplyButton, MessageAction, TextSendMessage

import requests


@SECRET.add(MessageEvent, TextMessage)
def handle_message(event):

    # 讀取用戶的ID
    user_id = event.source.user_id
    # print("發訊息的用戶 ID:",user_id)

    url = f"https://hsue2000.synology.me/api/search.php?token={API_TOKEN}"
    data = {"action": "GET_COUNT"}

    response = requests.post(url, data=data)

    # 檢查是否為白名單成員
    if user_id not in whitelist:
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text="⚠️ 未授權你使用本機器人!")
        )
        return

    user_text = event.message.text.strip()

    if user_text == "關於":

        flex_message = FlexSendMessage(
            alt_text="關於機器人",
            contents={
                "type": "bubble",
                "backgroundColor": "#FFF9C4",  # ✅ 整個泡泡背景
                "hero": {
                    "type": "image",
                    "url": "https://hsue2000.synology.me/images/KenKen.png",  # 🖼️ 替換為作者頭像圖片 URL
                    "size": "full",
                    "backgroundColor": "#E0FFFF",  # ✅ 修改這裡為你想要的底色
                    "aspectRatio": "1:1",
                    "aspectMode": "cover",
                    "size": "100px",  # ✅ 縮小頭像尺寸
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#E0FFFF",  # ✅ 修改這裡為你想要的底色
                    "spacing": "md",
                    "contents": [
                        {
                            "type": "text",
                            "text": "『HSUE錢幣查詢機器人』",
                            "weight": "bold",
                            "size": "lg",
                            "color": "#0000CD",
                            "align": "center",
                        },
                        {
                            "type": "text",
                            "text": "Ken Hsu Coin Collection",
                            "weight": "bold",
                            "size": "lg",
                            "color": "#009FCC",
                            "align": "center",
                        },
                        {
                            "type": "text",
                            "text": "Ken Hsu",
                            "size": "md",
                            "weight": "bold",
                            "color": "#333333",
                            "align": "center",
                        },
                        {
                            "type": "text",
                            "text": "版本: V1.0 (2025/8/9)",
                            "size": "sm",
                            "weight": "bold",
                            "wrap": True,
                            "color": "#E47011",
                            "align": "center",
                        },
                        {
                            "type": "text",
                            "text": "(C)2025 Ken Hsu. All Rights Reserved.",
                            "size": "sm",
                            "weight": "bold",
                            "wrap": True,
                            "color": "#4E0DE7",
                            "align": "center",
                        },
                    ],
                },
            },
        )
        line_bot_api.reply_message(event.reply_token, flex_message)
        return

    elif user_text == "?" or user_text == "？":
        flex_message = FlexSendMessage(
            alt_text="查詢指令",
            contents={
                "type": "bubble",
                "size": "mega",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#F5F5F5",
                    "contents": [
                        {
                            "type": "image",
                            "url": "https://hsue2000.synology.me/images/head3.png",  # 圖片 URL (必須 HTTPS)
                            "size": "sm",
                            "aspect_ratio": "1:1",
                            "aspect_mode": "cover",
                        },
                        {
                            "type": "text",
                            "text": "本機器人可使用的指令列表",
                            "weight": "bold",
                            "size": "lg",
                            "align": "center",
                        },
                        {"type": "separator", "margin": "md"},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "contents": [
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "♦️ 名稱 [關鍵字]",
                                            "weight": "bold",
                                            "color": "#000000",
                                            "flex": 6,
                                        },
                                        {
                                            "type": "text",
                                            "text": "查詢錢幣名稱",
                                            "weight": "bold",
                                            "size": "sm",
                                            "color": "#007AFF",
                                            "flex": 6,
                                            "wrap": True,
                                        },
                                    ],
                                },
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    f"contents": [
                                        {
                                            "type": "text",
                                            "text": "♦️ 國家 [關鍵字]",
                                            "weight": "bold",
                                            "color": "#000000",
                                            "flex": 6,
                                        },
                                        {
                                            "type": "text",
                                            "text": "查詢鑄造國家",
                                            "weight": "bold",
                                            "size": "sm",
                                            "color": "#007AFF",
                                            "flex": 6,
                                            "wrap": True,
                                        },
                                    ],
                                },
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "♦️ 公司 [關鍵字]",
                                            "weight": "bold",
                                            "color": "#000000",
                                            "flex": 6,
                                        },
                                        {
                                            "type": "text",
                                            "text": "查詢鑑定公司",
                                            "weight": "bold",
                                            "size": "sm",
                                            "color": "#007AFF",
                                            "flex": 6,
                                            "wrap": True,
                                        },
                                    ],
                                },
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "♦️ 備註 [關鍵字]",
                                            "weight": "bold",
                                            "color": "#000000",
                                            "flex": 6,
                                        },
                                        {
                                            "type": "text",
                                            "text": "查詢備註內容",
                                            "weight": "bold",
                                            "size": "sm",
                                            "color": "#007AFF",
                                            "flex": 6,
                                            "wrap": True,
                                        },
                                    ],
                                },
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "♦️ 現狀",
                                            "weight": "bold",
                                            "color": "#000000",
                                            "flex": 6,
                                        },
                                        {
                                            "type": "text",
                                            "text": "選擇項目後查詢",
                                            "weight": "bold",
                                            "size": "sm",
                                            "color": "#007AFF",
                                            "flex": 6,
                                            "wrap": True,
                                        },
                                    ],
                                },
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "♦️ 錢幣 [編號]",
                                            "weight": "bold",
                                            "color": "#000000",
                                            "flex": 6,
                                        },
                                        {
                                            "type": "text",
                                            "text": "查詢錢幣編號",
                                            "weight": "bold",
                                            "size": "sm",
                                            "color": "#007AFF",
                                            "flex": 6,
                                            "wrap": True,
                                        },
                                    ],
                                },
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "♦️ 關於",
                                            "weight": "bold",
                                            "color": "#000000",
                                            "flex": 6,
                                        },
                                        {
                                            "type": "text",
                                            "text": "作者資訊",
                                            "weight": "bold",
                                            "size": "sm",
                                            "color": "#007AFF",
                                            "flex": 6,
                                            "wrap": True,
                                        },
                                    ],
                                },
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "♦️ ? 或 ？",
                                            "weight": "bold",
                                            "color": "#000000",
                                            "flex": 6,
                                        },
                                        {
                                            "type": "text",
                                            "text": "顯示本指令列表",
                                            "weight": "bold",
                                            "size": "sm",
                                            "color": "#007AFF",
                                            "flex": 6,
                                            "wrap": True,
                                        },
                                    ],
                                },
                            ],
                        },
                    ],
                },
            },
        )
        line_bot_api.reply_message(event.reply_token, flex_message)
        return  # 必要：避免往下繼續跑

    # print(user_text)
    # 1) 使用者輸入「現狀」→ 回覆候選清單（用 bubble / carousel）
    if user_text == "現狀":

        # TODO: 這裡改成你的查詢（依 keyword 找到候選現狀）
        matched_countries = ["未輸入", "鑑定中", "已返回", "已售出", "已贈送", "已換盒"]

        # 把每個現況做成一顆按鈕（同一個 bubble 內垂直排列）

        buttons = []
        for name in matched_countries:
            buttons.append(
                {
                    "type": "button",
                    "style": "primary",  # 或 "secondary"
                    "height": "sm",
                    "margin": "sm",
                    "action": {
                        "type": "message",
                        "label": name,  # 按鈕上顯示的文字
                        "text": f"查詢現狀 {name}",  # 點了會送這句話回來
                    },
                }
            )

        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": "請選擇錢幣現狀",
                        "weight": "bold",
                        "size": "lg",
                        "align": "center",
                    },
                    {"type": "separator", "margin": "md"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": buttons,
                    },
                ],
            },
        }

        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(alt_text="請選擇錢幣現狀", contents=bubble),
        )
        return

    # 2) 使用者點了其中一個 → 送出「查詢現狀 XX」→ 這裡才真的去查資料庫
    elif user_text.startswith("查詢現狀 "):
        Coin_Kind = user_text.replace("查詢現狀 ", "").strip()

        # TODO: 這裡改成你的 API / DB 查詢
        # 例如：api_url = f"{API_BASE_URL}?Nation={quote(country)}&like=1&token={API_TOKEN}"
        # res = requests.get(api_url).json()

        encoded_serial = quote(Coin_Kind)
        api_url = f"{API_BASE_URL}?Coin_Kind={encoded_serial}&like=1&token={API_TOKEN}"
        res = requests.get(api_url).json()

        last_results = res  # 這裡 res 是 API 回傳的 list

        if isinstance(res, list) and res:
            flex_msg = build_list_carousel(res, page=1)
            line_bot_api.reply_message(event.reply_token, flex_msg)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="查無錢幣資料")
            )
        return

    # 列表頁
    elif user_text.startswith("名稱 "):
        serial_value = user_text.replace("名稱 ", "").strip()
        encoded_serial = quote(serial_value)
        api_url = f"{API_BASE_URL}?Coin_Name={encoded_serial}&like=1&token={API_TOKEN}"
        res = requests.get(api_url).json()

        last_results = res  # 這裡 res 是 API 回傳的 list

        if isinstance(res, list) and res:
            flex_msg = build_list_carousel(res, page=1)
            line_bot_api.reply_message(event.reply_token, flex_msg)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="查無錢幣資料")
            )
        return

    elif user_text.startswith("國家 "):
        serial_value = user_text.replace("國家 ", "").strip()
        encoded_serial = quote(serial_value)
        api_url = f"{API_BASE_URL}?Nation={encoded_serial}&like=1&token={API_TOKEN}"
        res = requests.get(api_url).json()

        last_results = res  # 這裡 res 是 API 回傳的 list

        if isinstance(res, list) and res:
            flex_msg = build_list_carousel(res, page=1)
            line_bot_api.reply_message(event.reply_token, flex_msg)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="查無錢幣資料")
            )
        return

    elif user_text.startswith("公司 "):
        serial_value = user_text.replace("公司 ", "").strip()
        encoded_serial = quote(serial_value)
        api_url = f"{API_BASE_URL}?Company={encoded_serial}&like=1&token={API_TOKEN}"
        res = requests.get(api_url).json()

        last_results = res  # 這裡 res 是 API 回傳的 list

        if isinstance(res, list) and res:
            flex_msg = build_list_carousel(res, page=1)
            line_bot_api.reply_message(event.reply_token, flex_msg)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="查無錢幣資料")
            )
        return

    elif user_text.startswith("備註 "):
        serial_value = user_text.replace("備註 ", "").strip()
        encoded_serial = quote(serial_value)
        api_url = f"{API_BASE_URL}?Note={encoded_serial}&like=1&token={API_TOKEN}"
        res = requests.get(api_url).json()

        last_results = res  # 這裡 res 是 API 回傳的 list

        if isinstance(res, list) and res:
            flex_msg = build_list_carousel(res, page=1)
            line_bot_api.reply_message(event.reply_token, flex_msg)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="查無錢幣資料")
            )
        return

    elif user_text.startswith("錢幣 "):

        serial_no = user_text.replace("錢幣 ", "").strip()
        api_url = f"{API_BASE_URL}?Serial={serial_no}&token={API_TOKEN}"
        res = requests.get(api_url).json()
        if isinstance(res, list) and res:
            flex_msg = build_detail_flex(res[0])
            line_bot_api.reply_message(event.reply_token, flex_msg)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="查無錢幣資料")
            )
        return

    elif user_text == "數量":
        # 傳送查詢代碼給 PHP
        php_url = f"{API_BASE_URL}?token={API_TOKEN}"
        response = requests.post(php_url, data={"action": "GET_COUNT"})

        if response.status_code == 200:
            result = response.json()

            total = result.get("total", "無資料")
            real = result.get("real", "無資料")
            retn = result.get("retn", "無資料")
            identify = result.get("identify", "無資料")
            sale = result.get("sale", "無資料")
            give = result.get("give", "無資料")
            changed = result.get("changed", "無資料")
            no_input = result.get("no_input", "無資料")

            flex_message = FlexSendMessage(
                alt_text="📊 錢幣數量統計",
                contents={
                    "type": "bubble",
                    "size": "mega",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#E0FCE0",
                        "contents": [
                            {
                                "type": "text",
                                "text": "📊 錢幣數量統計",
                                "weight": "bold",
                                "size": "xl",
                                "align": "center",
                                "margin": "md",
                                "color": "#333333",
                            },
                            {"type": "separator", "margin": "md"},
                            {
                                "type": "box",
                                "layout": "vertical",
                                "spacing": "sm",
                                "margin": "md",
                                "contents": [
                                    {
                                        "type": "box",
                                        "layout": "baseline",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "🔴 總筆數：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(total),
                                                "size": "md",
                                                "color": "#0000FF",
                                                "flex": 1,
                                            },
                                        ],
                                    },
                                    {
                                        "type": "box",
                                        "layout": "baseline",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "🔴 實    存：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(real),
                                                "size": "md",
                                                "color": "#0000FF",
                                                "flex": 1,
                                            },
                                        ],
                                    },
                                    {
                                        "type": "box",
                                        "layout": "baseline",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "🔴 已返回：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(retn),
                                                "size": "md",
                                                "color": "#0000FF",
                                                "flex": 1,
                                            },
                                        ],
                                    },
                                    {
                                        "type": "box",
                                        "layout": "baseline",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "🔴 鑑定中：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(identify),
                                                "size": "md",
                                                "color": "#0000FF",
                                                "flex": 1,
                                            },
                                        ],
                                    },
                                    {
                                        "type": "box",
                                        "layout": "baseline",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "🔴 已售出：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(sale),
                                                "size": "md",
                                                "color": "#0000FF",
                                                "flex": 1,
                                            },
                                        ],
                                    },
                                    {
                                        "type": "box",
                                        "layout": "baseline",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "🔴 已贈送：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(give),
                                                "size": "md",
                                                "color": "#0000FF",
                                                "flex": 1,
                                            },
                                        ],
                                    },
                                    {
                                        "type": "box",
                                        "layout": "baseline",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "🔴 已換盒：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(changed),
                                                "size": "md",
                                                "color": "#0000FF",
                                                "flex": 1,
                                            },
                                        ],
                                    },
                                    {
                                        "type": "box",
                                        "layout": "baseline",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "🔴 未輸入：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(no_input),
                                                "size": "md",
                                                "color": "#0000FF",
                                                "flex": 1,
                                            },
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                },
            )

        line_bot_api.reply_message(event.reply_token, flex_message)
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"❌ 查詢失敗，HTTP 錯誤碼：{response.status_code}"),
        )
        return


if __name__ == "__main__":
    app.run(port=5000)


