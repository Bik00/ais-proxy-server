import json
import copy
import logging
import requests
import base64
import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.DEBUG)

INNER_SERVER_URL = 'http://54.180.123.29:8188/prompt'
INPUT_DIR = "/path/to/comfyui/input"  # ComfyUI input 폴더 경로로 수정 필요

with open("sample.json", "r", encoding="utf-8") as f:
    sample_template = json.load(f)

@app.route('/generate', methods=['POST'])
def generate():
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "No payload received"}), 400

    positive_prompt = payload.get("prompt")
    negative_prompt = payload.get("negative_prompt", "watermark")
    if not positive_prompt:
        return jsonify({"error": "No prompt provided in payload"}), 400
    if not negative_prompt:
        negative_prompt = "watermark"

    sample = copy.deepcopy(sample_template)

    sample["8"]["inputs"]["text"] = positive_prompt
    sample["13"]["inputs"]["text"] = negative_prompt

    init_images = payload.get("init_images", [])
    if init_images:
        image_data = base64.b64decode(init_images[0])
        image_filename = "uploaded_image.jpg"
        image_path = os.path.join(INPUT_DIR, image_filename)
        with open(image_path, "wb") as f:
            f.write(image_data)
        sample["1"]["inputs"]["image"] = image_filename

    # 파라미터를 워크플로우에 직접 설정
    sample["14"]["inputs"]["cfg"] = payload.get("cfg_scale", 8)
    sample["4"]["inputs"]["strength"] = payload.get("denoising_strength", 0.6)
    sample["14"]["inputs"]["sampler_name"] = "euler"  # 지원되는 샘플러로 수정

    comfy_payload = {"prompt": sample}

    app.logger.debug("Request to Inner Server: %s", json.dumps(comfy_payload, indent=2))

    try:
        inner_response = requests.post(INNER_SERVER_URL, json=comfy_payload)
        inner_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        app.logger.error("Failed to forward request to inner server: %s", str(e))
        return jsonify({"error": "Failed to forward request to inner server", "details": str(e)}), 500

    app.logger.debug("Inner Server response: %s", inner_response.text)
    return jsonify(inner_response.json()), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)