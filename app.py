from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

import os
import requests
from urllib.parse import quote
from linebot.models import TextSendMessage, FlexSendMessage
from io import BytesIO

from linebot import LineBotApi
from linebot.models import (
    RichMenu,
    RichMenuArea,
    RichMenuBounds,
    RichMenuSize,
    MessageAction,
    URIAction,
)

from linebot.models import (
    TextSendMessage,
    FlexSendMessage,
    RichMenuSize,
    RichMenuBounds,
    RichMenu,
    RichMenuArea,
    QuickReply,
    QuickReplyButton,
    MessageAction,
)

import requests
import json

from linebot.models import FlexSendMessage

session_store = {}  # { user_id: { "last_results": [...] } }


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
        "Coin_Count": "#8B4513",  # 咖啡色
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
                            "align": "start",  # ✅ 靠左
                        },
                        {
                            "type": "text",
                            "text": str(val),
                            "size": "sm",
                            "color": value_color,
                            "wrap": True,
                            "flex": 7,
                            "align": "start",  # ✅ 靠左
                        },
                    ],
                }
            )

    # ===== Flex bubble（頂部 hero 大圖）=====
    bubble = {
        "type": "bubble",
        "hero": {
            "type": "box",  # 用 box 包住 image，才能設定背景色
            "layout": "vertical",
            "backgroundColor": "#FFFFF0",
            "contents": [
                {
                    "type": "image",
                    "url": pic_url,
                    "size": "xl",  # hero 最大值
                    "aspectRatio": "4:3",  # 比 1:1 高
                    "aspectMode": "fit",  # 等比例縮小完整顯示
                    "action": {"type": "uri", "label": "查看原圖", "uri": pic_url},
                }
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#FFFFF0",
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
        "footer": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#FFFFF0",
        },
    }

    return FlexSendMessage(alt_text="錢幣詳細資訊", contents=bubble)


last_results = []

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
SECRET = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
API_TOKEN = os.getenv("API_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL")


# 可使用的 LINE 使用者 ID 列表（White List）
# 從 Vercel 的環境變數讀取
whitelist_str = os.getenv("LINE_WHITELIST", "")

# 轉成 set（自動去除空白）
whitelist = {uid.strip() for uid in whitelist_str.split(",") if uid.strip()}
# print(whitelist)

CHANNEL_ACCESS_TOKEN = (os.getenv("LINE_CHANNEL_ACCESS_TOKEN") or "").strip().strip('"')
CHANNEL_SECRET = (os.getenv("LINE_CHANNEL_SECRET") or "").strip().strip('"')

# 使用你的 Channel Access Token
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)

# 建立 Rich Menu
rich_menu = RichMenu(
    size=RichMenuSize(width=2500, height=843),  # 官方規格
    selected=False,  # 是否預設選單
    name="四格選單範例",  # 後台管理用名稱
    chat_bar_text="打開選單",  # 使用者點選時顯示的文字
    areas=[
        # 左1區塊
        RichMenuArea(
            bounds=RichMenuBounds(x=0, y=0, width=625, height=843),
            action=MessageAction(label="1", text="數量"),
        ),
        # 左2區塊
        RichMenuArea(
            bounds=RichMenuBounds(x=625, y=0, width=625, height=843),
            action=MessageAction(label="2", text="現狀"),
        ),
        # 左3區塊
        RichMenuArea(
            bounds=RichMenuBounds(x=1250, y=0, width=625, height=843),
            action=MessageAction(label="3", text="?"),
        ),
        # 左4區塊
        RichMenuArea(
            bounds=RichMenuBounds(x=1875, y=0, width=625, height=843),
            action=MessageAction(label="4", text="關於"),
        ),
    ],
)

rich_menu_id = line_bot_api.create_rich_menu(rich_menu=rich_menu)

# 透過網址下載圖片
image_url = (
    "https://hsue2000.synology.me/images/richmenu_1x4-1.png"  # 改成你的 CDN/圖床位置
)
response = requests.get(image_url)
image_data = BytesIO(response.content)

# 上傳圖片
line_bot_api.set_rich_menu_image(rich_menu_id, "image/png", image_data)

# 設為預設選單
line_bot_api.set_default_rich_menu(rich_menu_id)

######################################################################


def show_loading_raw(user_id: str, seconds: int = 10):
    if not (user_id and user_id.startswith("U")):
        return
    seconds = max(5, min(int(seconds), 60))
    if seconds % 5 != 0:
        seconds = int(round(seconds / 5) * 5)
    requests.post(
        "https://api.line.me/v2/bot/chat/loading/start",
        headers={
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"chatId": user_id, "loadingSeconds": seconds},
        timeout=10,
    )


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        SECRET.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


ROWS_PER_PAGE = 10  # 每頁筆數


def safe_text(v, default="-"):
    # 把 None / 空白 轉成預設字元，並確保是 str
    s = "" if v is None else str(v)
    s = s.strip()
    return s if s else default


def build_list_bubble(
    rows,
    title,
    page,
    total_pages,
    row_action_prefix="編號",
    columns=("Serial_No", "Name", "Company", "Grade", "Material"),
    query_cmd="名稱",
    query_val="",
):
    # 標題列
    header = {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": [
            {
                "type": "text",
                "text": "名稱",
                "size": "xs",
                "weight": "bold",
                "flex": 4,
                "align": "center",
                "wrap": True,
            },
            {
                "type": "text",
                "text": "鑑定",
                "size": "xs",
                "weight": "bold",
                "flex": 2,
                "align": "center",
                "wrap": True,
            },
            {
                "type": "text",
                "text": "分數",
                "size": "xs",
                "weight": "bold",
                "flex": 3,
                "align": "center",
                "wrap": True,
            },
            {
                "type": "text",
                "text": "材質",
                "size": "xs",
                "weight": "bold",
                "flex": 3,
                "align": "center",
                "wrap": True,
            },
        ],
    }

    body = [
        {
            "type": "text",
            "text": f"{title}",
            "weight": "bold",
            "size": "md",
            "align": "center",
        },
        {
            "type": "text",
            "text": f"(第{page}/{total_pages}頁)",
            "weight": "bold",
            "size": "md",
            "align": "center",
        },
        {"type": "separator", "margin": "md"},
        header,
        {"type": "separator", "margin": "sm"},
    ]

    # 資料列
    for idx, d in enumerate(rows):
        serial_no = str(d.get(columns[0], ""))
        name = str(d.get(columns[1], ""))
        company = str(d.get(columns[2], ""))
        grade = str(d.get(columns[3], ""))
        material = str(d.get(columns[4], ""))

        body.append(
            {
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "backgroundColor": "#FFFFBB" if idx % 2 == 0 else "#E0FFFF",
                "contents": [
                    {
                        "type": "text",
                        "text": name,
                        "size": "sm",
                        "flex": 4,
                        "wrap": True,
                        "align": "start",
                    },
                    {
                        "type": "text",
                        "text": company,
                        "size": "sm",
                        "flex": 2,
                        "wrap": True,
                        "align": "center",
                    },
                    {
                        "type": "text",
                        "text": grade,
                        "size": "sm",
                        "flex": 3,
                        "wrap": True,
                        "align": "center",
                    },
                    {
                        "type": "text",
                        "text": material,
                        "size": "sm",
                        "flex": 3,
                        "wrap": True,
                        "align": "center",
                    },
                ],
                "action": {
                    "type": "message",
                    "label": "查詢詳情",
                    "text": f"{row_action_prefix} {serial_no}",
                },
                "paddingAll": "6px",
            }
        )
        body.append({"type": "separator", "margin": "sm"})

    # 分頁按鈕（把查詢種類與值帶回去）
    footer_contents = []
    if page > 1:
        footer_contents.append(
            {
                "type": "button",
                "style": "secondary",
                "height": "sm",
                "action": {
                    "type": "message",
                    "label": "⏮️ 上一頁",
                    "text": f"列表 {query_cmd} {query_val} {page-1}",
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
                    "label": "⏭️ 下一頁",
                    "text": f"列表 {query_cmd} {query_val} {page+1}",
                },
            }
        )

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body,
        },
    }
    if footer_contents:
        bubble["footer"] = {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": footer_contents,
        }
    return bubble


def build_list_page(all_rows, page=1, title="查詢結果", query_cmd="名稱", query_val=""):
    total = len(all_rows)
    total_pages = max(1, (total + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * ROWS_PER_PAGE
    page_rows = all_rows[start : start + ROWS_PER_PAGE]
    bubble = build_list_bubble(
        page_rows,
        title=title,
        page=page,
        total_pages=total_pages,
        query_cmd=query_cmd,
        query_val=query_val,
    )
    return FlexSendMessage(alt_text="查詢結果列表", contents=bubble)


from linebot.models import QuickReply, QuickReplyButton, MessageAction, TextSendMessage

import requests


@SECRET.add(MessageEvent, TextMessage)
def handle_message(event):

    # 讀取用戶的ID
    user_id = event.source.user_id
    # print("發訊息的用戶 ID:",user_id)

    if user_id:
        show_loading_raw(user_id, seconds=15)

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
                            "color": "#FF44AA",
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
                            "text": "版本: V1.0 (2025/8/24)",
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
                            "size": "md",
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
                                            "size": "sm",
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
                                            "size": "sm",
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
                                            "size": "sm",
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
                                            "size": "sm",
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
                                            "text": "♦️ 編號 [編號]",
                                            "weight": "bold",
                                            "size": "sm",
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
                                            "text": "♦️ 數量",
                                            "weight": "bold",
                                            "size": "sm",
                                            "color": "#000000",
                                            "flex": 6,
                                        },
                                        {
                                            "type": "text",
                                            "text": "查詢錢幣數量",
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
                                            "size": "sm",
                                            "color": "#000000",
                                            "flex": 6,
                                        },
                                        {
                                            "type": "text",
                                            "text": "查詢錢幣現狀",
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
        matched_countries = [
            ("未輸入", "📝     未輸入"),
            ("鑑定中", "🔍     鑑定中"),
            ("已返回", "🗒️     已返回"),
            ("已售出", "💰     已售出"),
            ("已贈送", "🎁     已贈送"),
            ("已換盒", "📦     已換盒"),
        ]

        # 把每個現況做成一顆按鈕（同一個 bubble 內垂直排列）

        buttons = []
        for raw_text, label_text in matched_countries:
            buttons.append(
                {
                    "type": "button",
                    "style": "primary",  # 或 "secondary"
                    "height": "sm",
                    "margin": "sm",
                    "action": {
                        "type": "message",
                        "label": label_text,  # 按鈕顯示：含 emoji
                        "text": f"查詢現狀 {raw_text}",  # 點了會送這句話回來
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

        val = user_text.replace("查詢現狀 ", "").strip()
        encoded = quote(val)
        api_url = f"{API_BASE_URL}?Coin_Kind={encoded}&like=1&token={API_TOKEN}"
        res = requests.get(api_url).json()  # 預期回傳 list[dict]

        if isinstance(res, list) and res:
            flex = build_list_page(
                res,
                page=1,
                title=f"查詢錢幣現狀：{val}",
                query_cmd="查詢現狀",
                query_val=val,
            )
            line_bot_api.reply_message(event.reply_token, flex)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="⚠️ 查無錢幣資料")
            )
        return

    # 列表頁
    # ① 第一次查詢（名稱 關鍵字）
    if user_text.startswith("名稱 "):
        val = user_text.replace("名稱 ", "").strip()
        encoded = quote(val)
        api_url = f"{API_BASE_URL}?Coin_Name={encoded}&like=1&token={API_TOKEN}"
        res = requests.get(api_url).json()  # 預期回傳 list[dict]

        if isinstance(res, list) and res:
            flex = build_list_page(
                res, page=1, title=f"名稱：{val}", query_cmd="名稱", query_val=val
            )
            line_bot_api.reply_message(event.reply_token, flex)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="⚠️ 查無錢幣資料")
            )
        return

    # ② 翻頁（列表 名稱 關鍵字 頁碼）
    elif user_text.startswith("列表 "):
        parts = user_text.split(" ", 3)  # ["列表", "名稱", "<val>", "<page>"]
        if len(parts) == 4:
            _, cmd, val, page_str = parts
            try:
                page = int(page_str)
            except ValueError:
                page = 1

            if cmd == "名稱":
                key = "Coin_Name"
            elif cmd == "國家":
                key = "Nation"
            elif cmd == "公司":
                key = "Company"
            elif cmd == "備註":
                key = "Note"
            elif cmd == "查詢現狀":
                key = "Coin_Kind"
            else:
                line_bot_api.reply_message(
                    event.reply_token, TextSendMessage(text="⚠️ 不支援的查詢類型")
                )
                return

            encoded = quote(val)
            api_url = f"{API_BASE_URL}?{key}={encoded}&like=1&token={API_TOKEN}"
            res = requests.get(api_url).json()

            if isinstance(res, list) and res:
                flex = build_list_page(
                    res,
                    page=page,
                    title=f"名稱：{val}",
                    query_cmd=cmd,
                    query_val=val,
                )
                line_bot_api.reply_message(event.reply_token, flex)
            else:
                line_bot_api.reply_message(
                    event.reply_token, TextSendMessage(text="⚠️ 查無錢幣資料")
                )
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="⚠️ 分頁參數不足，請重新查詢")
            )
        return

    elif user_text.startswith("國家 "):
        val = user_text.replace("國家 ", "").strip()
        encoded = quote(val)
        api_url = f"{API_BASE_URL}?Nation={encoded}&like=1&token={API_TOKEN}"
        res = requests.get(api_url).json()  # 預期回傳 list[dict]

        if isinstance(res, list) and res:
            flex = build_list_page(
                res, page=1, title=f"國家：{val}", query_cmd="國家", query_val=val
            )
            line_bot_api.reply_message(event.reply_token, flex)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="⚠️ 查無錢幣資料")
            )
        return

    elif user_text.startswith("公司 "):
        val = user_text.replace("公司 ", "").strip()
        encoded = quote(val)
        api_url = f"{API_BASE_URL}?Company={encoded}&like=1&token={API_TOKEN}"
        res = requests.get(api_url).json()  # 預期回傳 list[dict]

        if isinstance(res, list) and res:
            flex = build_list_page(
                res, page=1, title=f"公司{val}", query_cmd="公司", query_val=val
            )
            line_bot_api.reply_message(event.reply_token, flex)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="⚠️ 查無錢幣資料")
            )
        return

    elif user_text.startswith("備註 "):
        val = user_text.replace("備註 ", "").strip()
        encoded = quote(val)
        api_url = f"{API_BASE_URL}?Note={encoded}&like=1&token={API_TOKEN}"
        res = requests.get(api_url).json()  # 預期回傳 list[dict]

        if isinstance(res, list) and res:
            flex = build_list_page(
                res, page=1, title=f"備註{val}", query_cmd="備註", query_val=val
            )
            line_bot_api.reply_message(event.reply_token, flex)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="⚠️ 查無錢幣資料")
            )
        return

    elif user_text.startswith("編號 "):

        serial_no = user_text.replace("編號 ", "").strip()
        api_url = f"{API_BASE_URL}?Serial={serial_no}&token={API_TOKEN}"
        res = requests.get(api_url).json()
        if isinstance(res, list) and res:
            flex_msg = build_detail_flex(res[0])
            line_bot_api.reply_message(event.reply_token, flex_msg)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="⚠️ 查無錢幣資料")
            )
        # return

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
                                                "text": "📂 總筆數：",
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
                                                "text": "🗂️ 實    存：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(real),
                                                "size": "md",
                                                "color": "#FF5511",
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
                                                "text": "🗒️ 已返回：",
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
                                                "text": "🔍 鑑定中：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(identify),
                                                "size": "md",
                                                "color": "#AA7700",
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
                                                "text": "💰 已售出：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(sale),
                                                "size": "md",
                                                "color": "#FF00FF",
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
                                                "text": "🎁 已贈送：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(give),
                                                "size": "md",
                                                "color": "#FF00FF",
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
                                                "text": "📦 已換盒：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(changed),
                                                "size": "md",
                                                "color": "#FF00FF",
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
                                                "text": "📝 未輸入：",
                                                "size": "md",
                                                "color": "#000000",
                                                "weight": "bold",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": str(no_input),
                                                "size": "md",
                                                "color": "#9900FF",
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
            TextSendMessage(text=f"⚠️ 指令錯誤,請重新輸入!"),
        )
        return


if __name__ == "__main__":
    app.run(port=5000)
