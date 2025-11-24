import json
import os
import dashscope
from dashscope import MultiModalConversation
import requests

# 设置 DashScope API URL（中国大陆区域）
dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'

messages = [
    {
        "role": "user",
        "content": [
            {"text": "A pixel art style fantasy landscape with a castle on a hill under a starry night sky."}
        ]
    }
]

# 替换为你的 API key
api_key = "sk-f01dd484841f41999c97d9ec6ddb1c7c"

response = MultiModalConversation.call(
    api_key=api_key,
    model="qwen-image-plus",
    messages=messages,
    result_format='message',
    stream=False,
    watermark=False,
    prompt_extend=True,
    negative_prompt='',
    size='1328*1328'
)

if response.status_code == 200:
    print("success")
    print(json.dumps(response, ensure_ascii=False, indent=2))

    try:
        image_url = response["output"]["choices"][0]["message"]["content"][0]["image"]
        print(f"\n image URL: {image_url}")
    except Exception as e:
        print(e)
        exit()

    print("downloading...")
    try:
        img_data = requests.get(image_url).content
        output_path = "output.png"

        with open(output_path, "wb") as f:
            f.write(img_data)

        print(f"saved to local: {output_path}")

    except Exception as e:
        print("❌ failed to download image.")
        print(e)

else:
    print(f"HTTP返回码：{response.status_code}")
    print(f"错误码：{response.code}")
    print(f"错误信息：{response.message}")
    print("请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code")