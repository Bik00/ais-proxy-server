import json
import copy
import logging
import requests
import base64
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import binascii

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.DEBUG)

INNER_SERVER_URL = 'http://54.180.123.29:8188/prompt'
INPUT_DIR = "/path/to/comfyui/input"  # 실제 경로로 수정 필요

with open("sample.json", "r", encoding="utf-8") as f:
    sample_template = json.load(f)

@app.route('/generate', methods=['POST'])
def generate():
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "페이로드가 없습니다"}), 400

    positive_prompt = payload.get("prompt")
    if not positive_prompt:
        return jsonify({"error": "프롬프트가 제공되지 않았습니다"}), 400
    negative_prompt = payload.get("negative_prompt", "watermark")

    sample = copy.deepcopy(sample_template)
    sample["8"]["inputs"]["text"] = positive_prompt
    sample["13"]["inputs"]["text"] = negative_prompt

    init_images = payload.get("init_images", [])
    if init_images:
        image_data_uri = init_images[0]
        if image_data_uri.startswith("data:"):
            base64_data = image_data_uri.split(",")[1]
        else:
            base64_data = image_data_uri

        # 데이터 유효성 검증
        if len(base64_data) % 4 != 0:
            app.logger.error("base64 데이터 길이가 4의 배수가 아님")
            return jsonify({"error": "잘못된 base64 데이터 길이"}), 400

        try:
            image_data = base64.b64decode(base64_data)
        except binascii.Error as e:
            app.logger.error("Base64 디코딩 오류: %s", str(e))
            return jsonify({"error": "잘못된 base64 데이터", "details": str(e)}), 400

        image_filename = "uploaded_image.jpg"
        image_path = os.path.join(INPUT_DIR, image_filename)
        with open(image_path, "wb") as f:
            f.write(image_data)
        sample["1"]["inputs"]["image"] = image_filename

    sample["14"]["inputs"]["cfg"] = payload.get("cfg_scale", 8)
    sample["4"]["inputs"]["strength"] = payload.get("denoising_strength", 0.6)
    sample["14"]["inputs"]["sampler_name"] = "euler"

    comfy_payload = {"prompt": sample}
    app.logger.debug("내부 서버 요청: %s", json.dumps(comfy_payload, indent=2))

    try:
        inner_response = requests.post(INNER_SERVER_URL, json=comfy_payload)
        inner_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        app.logger.error("내부 서버 요청 실패: %s", str(e))
        return jsonify({"error": "내부 서버 요청 실패", "details": str(e)}), 500

    app.logger.debug("내부 서버 응답: %s", inner_response.text)
    return jsonify(inner_response.json()), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)