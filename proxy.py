import json
import copy
import logging
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.DEBUG)

INNER_SERVER_URL = 'http://54.180.123.29:8188'
PROMPT_ENDPOINT = f'{INNER_SERVER_URL}/prompt'

with open("sample.json", "r", encoding="utf-8") as f:
    sample_template = json.load(f)

def remove_data_prefix(image_data):
    prefix = "data:image/png;base64,"
    if image_data.startswith(prefix):
        return image_data[len(prefix):]
    return image_data

@app.route('/generate', methods=['POST'])
def generate():
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "페이로드가 없습니다"}), 400

    # 만약 'init_images' 필드가 있다면 각 이미지 데이터에서 접두어 제거
    if 'init_images' in payload and isinstance(payload['init_images'], list):
        processed_images = []
        for img in payload['init_images']:
            if isinstance(img, str):
                processed_images.append(remove_data_prefix(img))
            else:
                processed_images.append(img)
        payload['init_images'] = processed_images

    positive_prompt = payload.get("prompt")
    if not positive_prompt:
        return jsonify({"error": "프롬프트가 제공되지 않았습니다"}), 400
    negative_prompt = payload.get("negative_prompt", "watermark")

    # 워크플로우 템플릿 복사
    sample = copy.deepcopy(sample_template)
    sample["8"]["inputs"]["text"] = positive_prompt
    sample["13"]["inputs"]["text"] = negative_prompt

    # 초기 이미지 처리
    init_images = payload.get("init_images", [])
    if init_images:
        image_data_uri = init_images[0]
        if image_data_uri.startswith("data:"):
            # "data:image/png;base64," 부분 제거하고 base64 데이터만 추출
            base64_data = image_data_uri.split(",")[1]
        else:
            base64_data = image_data_uri

        # 워크플로우에 base64 이미지 데이터 설정
        sample["1"]["inputs"]["image"] = base64_data

    # 추가 설정 적용
    sample["14"]["inputs"]["cfg"] = payload.get("cfg_scale", 8)
    sample["4"]["inputs"]["strength"] = payload.get("denoising_strength", 0.6)
    sample["14"]["inputs"]["sampler_name"] = "euler"

    # ComfyUI로 전송할 페이로드 준비
    comfy_payload = {"prompt": sample}
    app.logger.debug("내부 서버 요청: %s", json.dumps(comfy_payload, indent=2))

    # Inner Server의 /prompt 엔드포인트로 요청 전송
    try:
        inner_response = requests.post(PROMPT_ENDPOINT, json=comfy_payload)
        inner_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        app.logger.error("내부 서버 요청 실패: %s", str(e))
        return jsonify({"error": "내부 서버 요청 실패", "details": str(e)}), 500

    app.logger.debug("내부 서버 응답: %s", inner_response.text)
    return jsonify(inner_response.json()), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)