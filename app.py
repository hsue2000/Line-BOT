from flask import Flask, request, abort

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
    FlexImage,
    FlexBubble,
    FlexText,
    FlexButton,
    FlexIcon,
    FlexBox,
    URIAction
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)
import json
import os

app = Flask(__name__)

configuration = Configuration(access_token=os.getenv('CHANNEL_ACCESS_TOKEN'))
Line_handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        Line_handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@Line_handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text=event.message.text
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        if text == 'information':
            line_flex_json = {
  "type": "bubble",
  "hero": {
    "type": "image",
    "url": "https://hsue2000.synology.me/images/qunma_b.png",
    "size": "full",
    "aspectRatio": "4:3",
    "aspectMode": "cover",
    "backgroundColor": "#000000"
  },
  "body": {
    "type": "box",
    "layout": "vertical",
    "contents": [
      {
        "type": "text",
        "text": "𝑸𝒖𝒏𝒎𝒂 𝑷𝒓𝒐 𝑨𝒖𝒕𝒐 𝑫𝒆𝒕𝒂𝒊𝒍𝒊𝒏𝒈",
        "weight": "bold",
        "size": "md"
      },
      {
        "type": "box",
        "layout": "baseline",
        "margin": "md",
        "contents": [
          {
            "type": "icon",
            "size": "sm",
            "url": "https://developers-resource.landpress.line.me/fx/img/review_gold_star_28.png"
          },
          {
            "type": "icon",
            "size": "sm",
            "url": "https://developers-resource.landpress.line.me/fx/img/review_gold_star_28.png"
          },
          {
            "type": "icon",
            "size": "sm",
            "url": "https://developers-resource.landpress.line.me/fx/img/review_gold_star_28.png"
          },
          {
            "type": "icon",
            "size": "sm",
            "url": "https://developers-resource.landpress.line.me/fx/img/review_gold_star_28.png"
          },
          {
            "type": "icon",
            "size": "sm",
            "url": "https://developers-resource.landpress.line.me/fx/img/review_gold_star_28.png"
          },
          {
            "type": "text",
            "text": "5.0",
            "size": "sm",
            "color": "#999999",
            "margin": "md",
            "flex": 0
          }
        ]
      },
      {
        "type": "box",
        "layout": "vertical",
        "margin": "lg",
        "spacing": "sm",
        "contents": [
          {
            "type": "box",
            "layout": "baseline",
            "spacing": "sm",
            "contents": [
              {
                "type": "text",
                "text": "Address:",
                "color": "#aaaaaa",
                "size": "sm",
                "flex": 3
              },
              {
                "type": "text",
                "text": "Tainan",
                "wrap": True,
                "color": "#666666",
                "size": "sm",
                "flex": 10
              }
            ]
          },
          {
            "type": "box",
            "layout": "baseline",
            "spacing": "sm",
            "contents": [
              {
                "type": "text",
                "text": "Time:",
                "color": "#aaaaaa",
                "size": "sm",
                "flex": 3
              },
              {
                "type": "text",
                "text": "09:00 - 19:00",
                "wrap": True,
                "color": "#666666",
                "size": "sm",
                "flex": 10
              }
            ]
          }
        ]
      }
    ]
  },
  "footer": {
    "type": "box",
    "layout": "horizontal",
    "contents": [
      {
        "type": "button",
        "action": {
          "type": "uri",
          "label": "Website",
          "uri": "https://hsue2000.synology.me/index.html"
        },
        "style": "primary",
        "margin": "md"
      },
      {
        "type": "button",
        "action": {
          "type": "uri",
          "label": "Facebook",
          "uri": "https://www.facebook.com/Qunma2012"
        },
        "style": "secondary",
        "margin": "md"
      }
    ]
  }
}
        
        line_flex_str=json.dumps(line_flex_json)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(alt_text= '資訊說明', contents=FlexContainer.from_json(line_flex_str))]
            )
        )   
       

if __name__ == "__main__":

    app.run()
