import os
import json
import requests
import dashscope
from dashscope import MultiModalConversation

# Use the key from the user's test file
API_KEY = "sk-f01dd484841f41999c97d9ec6ddb1c7c"
dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'

def generate_pixel_art_spell_icon(description: str, output_path: str) -> bool:
    """
    Generates a pixel art style spell icon based on the description.
    Returns True if successful, False otherwise.
    """
    print(f"[ImageGen] Generating icon for: {description}...")
    
    # Construct a prompt that enforces pixel art style
    prompt = f"A pixel art style icon for a magic spell representing '{description}'. The icon should be suitable for a retro video game, clean pixel art, 64x64 style, on a dark background or transparent if possible."

    messages = [
        {
            "role": "user",
            "content": [
                {"text": prompt}
            ]
        }
    ]

    try:
        response = MultiModalConversation.call(
            api_key=API_KEY,
            model="qwen-image-plus",
            messages=messages,
            result_format='message',
            stream=False,
            watermark=False,
            prompt_extend=True,
            negative_prompt='photorealistic, blurry, low quality, text, watermark',
            size='1328*1328' # Updated to match allowed sizes for qwen-image-plus
        )

        if response.status_code == 200:
            try:
                image_url = response["output"]["choices"][0]["message"]["content"][0]["image"]
                print(f"[ImageGen] Image URL: {image_url}")
                
                print("[ImageGen] Downloading...")
                img_data = requests.get(image_url).content
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

                with open(output_path, "wb") as f:
                    f.write(img_data)

                print(f"[ImageGen] Saved to: {output_path}")
                return True

            except Exception as e:
                print(f"[ImageGen] Failed to parse response or download: {e}")
                return False
        else:
            print(f"[ImageGen] API Error: {response.code} - {response.message}")
            return False

    except Exception as e:
        print(f"[ImageGen] Exception: {e}")
        return False
