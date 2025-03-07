import json
import copy  # 추가: copy 모듈 임포트
import logging
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS  # flask-cors 임포트

app = Flask(__name__)
CORS(app)  # 모든 도메인에 대해 CORS 허용. 필요시 resources 매개변수를 이용해 제한 가능.
logging.basicConfig(level=logging.DEBUG)

# Inner Server의 ComfyUI 엔드포인트 (수정 없이 그대로 사용)
INNER_SERVER_URL = 'http://54.180.123.29:8188/prompt'

# 서버 시작 시에 workflow 템플릿 파일(sample.json)을 미리 로드합니다.
with open("sample.json", "r", encoding="utf-8") as f:
    sample_template = json.load(f)

@app.route('/generate', methods=['POST'])
def generate():
    # 클라이언트로부터 JSON payload를 받습니다.
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "No payload received"}), 400

    # payload 내에 "prompt" 키의 값을 추출합니다.
    positive_prompt = payload.get("prompt")
    negative_prompt = payload.get("negative_prompt")
    if not positive_prompt:
        return jsonify({"error": "No prompt provided in payload"}), 400

    # sample_template의 깊은 복사본을 만들어 요청별로 수정합니다.
    sample = copy.deepcopy(sample_template)

    # sample.json의 단계 "8" (긍정 프롬프트)의 "inputs"의 "text" 필드를 업데이트합니다.
    if "8" in sample and "inputs" in sample["8"]:
        sample["8"]["inputs"]["text"] = positive_prompt
    else:
        return jsonify({"error": "Workflow template missing positive prompt configuration"}), 500
    if "13" in sample and "inputs" in sample["13"]:
        sample["13"]["inputs"]["text"] = negative_prompt

    # 수정된 workflow를 내부 서버(ComfyUI)의 엔드포인트로 전달합니다.
    inner_server_url = "http://54.180.123.29:8188/prompt"
    try:
        inner_response = requests.post(inner_server_url, json=sample)
    except Exception as e:
        return jsonify({"error": "Failed to forward request to inner server", "details": str(e)}), 500

    # 내부 서버의 응답 상태에 따라 적절하게 전달합니다.
    if inner_response.status_code != 200:
        return jsonify({"error": "Inner server error", "details": inner_response.text}), inner_response.status_code

    return jsonify(inner_response.json()), 200

if __name__ == '__main__':
    # 개발용 서버로 실행 (운영 환경에서는 production WSGI 서버 사용 권장)
    app.run(host="0.0.0.0", port=5000)
