import json
import copy
import logging
import requests
import os
import base64
import uuid
import time
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.DEBUG)

LOCAL_TEMP_DIR = '/home/ubuntu/temp_images'
if not os.path.exists(LOCAL_TEMP_DIR):
    os.makedirs(LOCAL_TEMP_DIR)

INNER_IMAGE_PATH_PREFIX = r"C:\temp_images"
INNER_SERVER_URL = 'http://13.125.242.189:8188/prompt'
INNER_SERVER_HISTORY_URL = 'http://13.125.242.189:8188/history'  # History 엔드포인트 추가

def save_base64_image(data_uri):
    if ',' in data_uri:
        header, encoded = data_uri.split(',', 1)
    else:
        encoded = data_uri
        header = ''
    
    ext = 'png'
    if header:
        if 'image/jpeg' in header:
            ext = 'jpg'
        elif 'image/gif' in header:
            ext = 'gif'
        elif 'image/png' in header:
            ext = 'png'
    
    filename = f"{uuid.uuid4()}.{ext}"
    local_filepath = os.path.join(LOCAL_TEMP_DIR, filename)
    image_data = base64.b64decode(encoded)
    with open(local_filepath, 'wb') as f:
        f.write(image_data)
    
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

        if 'init_images' in payload and isinstance(payload['init_images'], list):
            new_init_images = []
            for item in payload['init_images']:
                if isinstance(item, str) and item.startswith('data:image'):
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

        sample = copy.deepcopy(sample_template)
        sample["8"]["inputs"]["text"] = positive_prompt
        sample["13"]["inputs"]["text"] = negative_prompt
        sample["14"]["inputs"]["cfg"] = payload.get("cfg_scale", 8)
        sample["4"]["inputs"]["strength"] = payload.get("denoising_strength", 0.6)
        sample["14"]["inputs"]["sampler_name"] = "euler"

        comfy_payload = {"prompt": sample}
        app.logger.debug("내부 서버 요청: %s", json.dumps(comfy_payload, indent=2))

        inner_response = requests.post(INNER_SERVER_URL, json=comfy_payload, headers=headers)
        inner_response.raise_for_status()
        data = inner_response.json()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            return jsonify({"error": "prompt_id를 받지 못했습니다."}), 500

        # /history 엔드포인트를 통해 결과 폴링
        timeout = 60
        poll_interval = 2
        elapsed = 0
        while elapsed < timeout:
            history_response = requests.get(f"{INNER_SERVER_HISTORY_URL}/{prompt_id}")
            if history_response.status_code == 200:
                history_data = history_response.json()
                if prompt_id in history_data and "outputs" in history_data[prompt_id]:
                    # 이미지 파일 경로 추출 (ComfyUI는 파일명을 반환)
                    outputs = history_data[prompt_id]["outputs"]
                    for node_id, output in outputs.items():
                        if "images" in output:
                            images = output["images"]
                            if images:
                                # Inner Server에서 생성된 이미지 파일을 읽어 Base64로 변환
                                image_results = []
                                for image_info in images:
                                    image_path = image_info.get("filename")
                                    full_image_path = os.path.join(r"C:\StabilityMatrix\Packages\ComfyUI\output", image_path)
                                    if os.path.exists(full_image_path):
                                        with open(full_image_path, "rb") as f:
                                            image_data = base64.b64encode(f.read()).decode('utf-8')
                                            image_results.append(f"data:image/png;base64,{image_data}")
                                if image_results:
                                    return jsonify({"images": image_results})
            time.sleep(poll_interval)
            elapsed += poll_interval

        return jsonify({"error": "이미지 생성이 시간 내에 완료되지 않았습니다.", "prompt_id": prompt_id}), 504

    except Exception as e:
        app.logger.exception("Error processing request")
        return jsonify({"details": str(e), "error": "내부 서버 요청 실패"}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)