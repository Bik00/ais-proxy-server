import json
import copy
import logging
import requests
import os
import base64
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.DEBUG)

# Proxy 서버의 로컬 임시 이미지 저장 디렉토리 (Proxy 서버에서 파일을 저장할 경로)
LOCAL_TEMP_DIR = '/home/ubuntu/temp_images'
if not os.path.exists(LOCAL_TEMP_DIR):
    os.makedirs(LOCAL_TEMP_DIR)

# Inner Server에서 이미지 파일을 읽어올 경로 (Windows 형식)
INNER_IMAGE_PATH_PREFIX = r"C:\temp_images"

# Inner Server의 ComfyUI 프롬프트 API 엔드포인트 (예시)
INNER_SERVER_URL = 'http://54.180.123.29:8188/prompt'

def save_base64_image(data_uri):
    """
    데이터 URI 형식의 base64 문자열을 받아서 로컬 TEMP 디렉토리에 이미지 파일로 저장한 후,
    Inner Server에서 접근 가능한 경로(예, "C:\temp_images\<파일명>")를 반환합니다.
    """
    # 데이터 URI 헤더 제거: "data:image/png;base64,AAA..." -> "AAA..."
    if ',' in data_uri:
        header, encoded = data_uri.split(',', 1)
    else:
        encoded = data_uri
        header = ''
    
    # 헤더를 참고하여 확장자 결정 (기본은 png)
    ext = 'png'
    if header:
        if 'image/jpeg' in header:
            ext = 'jpg'
        elif 'image/gif' in header:
            ext = 'gif'
        elif 'image/png' in header:
            ext = 'png'
    
    # 고유 파일명 생성
    filename = f"{uuid.uuid4()}.{ext}"
    local_filepath = os.path.join(LOCAL_TEMP_DIR, filename)
    
    # base64 디코딩 후 로컬 파일로 저장
    image_data = base64.b64decode(encoded)
    with open(local_filepath, 'wb') as f:
        f.write(image_data)
    
    # Inner Server에서 접근 가능한 파일 경로 (윈도우 경로 형식)
    inner_filepath = os.path.join(INNER_IMAGE_PATH_PREFIX, filename)
    return inner_filepath

with open("sample.json", "r", encoding="utf-8") as f:
    sample_template = json.load(f)

@app.route('/generate', methods=['POST'])
def generate():
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "페이로드가 없습니다"}), 400

        # payload 내의 "init_images"가 존재하면 각 항목이 base64 데이터인지 확인 후 파일 저장
        if 'init_images' in payload and isinstance(payload['init_images'], list):
            new_init_images = []
            for item in payload['init_images']:
                if isinstance(item, str) and item.startswith('data:image'):
                    # base64 데이터를 저장하고, Inner Server에서 읽을 수 있는 파일 경로로 대체
                    inner_path = save_base64_image(item)
                    new_init_images.append(inner_path)
                else:
                    new_init_images.append(item)
            payload['init_images'] = new_init_images

        app.logger.debug("Modified payload: %s", json.dumps(payload))

        headers = {'Content-Type': 'application/json'}

        positive_prompt = payload.get("prompt")
        if not positive_prompt:
            return jsonify({"error": "프롬프트가 제공되지 않았습니다"}), 400
        negative_prompt = payload.get("negative_prompt", "watermark")

        # 워크플로우 템플릿 복사
        sample = copy.deepcopy(sample_template)
        sample["8"]["inputs"]["text"] = positive_prompt
        sample["13"]["inputs"]["text"] = negative_prompt

        # 추가 설정 적용
        sample["14"]["inputs"]["cfg"] = payload.get("cfg_scale", 8)
        sample["4"]["inputs"]["strength"] = payload.get("denoising_strength", 0.6)
        sample["14"]["inputs"]["sampler_name"] = "euler"

        # ComfyUI로 전송할 페이로드 준비
        comfy_payload = {"prompt": sample}
        app.logger.debug("내부 서버 요청: %s", json.dumps(comfy_payload, indent=2))

        # Inner Server의 /prompt 엔드포인트로 요청 전송
        try:
            inner_response = requests.post(INNER_SERVER_URL, json=comfy_payload, headers=headers)
            inner_response.raise_for_status()
        except requests.exceptions.RequestException as e:
            app.logger.error("내부 서버 요청 실패: %s", str(e))
            return jsonify({"error": "내부 서버 요청 실패", "details": str(e)}), 500

        app.logger.debug("내부 서버 응답: %s", inner_response.text)
        return jsonify(inner_response.json()), 200
    except Exception as e:
        app.logger.exception("Error processing request")
        return jsonify({
            "details": str(e),
            "error": "내부 서버 요청 실패"
        }), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)