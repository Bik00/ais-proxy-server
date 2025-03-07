import json
import copy
import logging
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# Flask 애플리케이션 설정
app = Flask(__name__)
CORS(app)

# 로깅 설정 (DEBUG 레벨로 모든 로그 기록)
logging.basicConfig(level=logging.DEBUG)

# Inner Server의 ComfyUI 엔드포인트 URL
INNER_SERVER_URL = 'http://54.180.123.29:8188/prompt'

# 서버 시작 시 workflow 템플릿(sample.json)을 미리 로드
with open("sample.json", "r", encoding="utf-8") as f:
    sample_template = json.load(f)

@app.route('/generate', methods=['POST'])
def generate():
    # 클라이언트로부터 받은 JSON 페이로드
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "No payload received"}), 400

    # 긍정 프롬프트와 부정 프롬프트 추출
    positive_prompt = payload.get("prompt")
    negative_prompt = payload.get("negative_prompt", "watermark")
    if not negative_prompt:  # 빈 문자열이거나 None일 경우 "watermark"로 설정
        negative_prompt = "watermark"

    # 긍정 프롬프트가 없는 경우 에러 반환
    if not positive_prompt:
        return jsonify({"error": "No prompt provided in payload"}), 400

    # sample.json 템플릿의 깊은 복사본 생성
    sample = copy.deepcopy(sample_template)

    # 긍정 프롬프트 설정 (노드 "8")
    if "8" in sample and "inputs" in sample["8"] and "text" in sample["8"]["inputs"]:
        sample["8"]["inputs"]["text"] = positive_prompt
    else:
        return jsonify({"error": "Workflow template missing positive prompt configuration"}), 500

    # 부정 프롬프트 설정 (노드 "13")
    if "13" in sample and "inputs" in sample["13"] and "text" in sample["13"]["inputs"]:
        sample["13"]["inputs"]["text"] = negative_prompt
    else:
        return jsonify({"error": "Workflow template missing negative prompt configuration"}), 500

    # 요청 JSON 로그 기록
    app.logger.debug("Request to Inner Server: %s", json.dumps(sample, indent=2))

    # Inner Server로 요청 전송
    try:
        inner_response = requests.post(INNER_SERVER_URL, json=sample)
        inner_response.raise_for_status()  # HTTP 에러 발생 시 예외 발생
    except requests.exceptions.RequestException as e:
        app.logger.error("Failed to forward request to inner server: %s", str(e))
        return jsonify({"error": "Failed to forward request to inner server", "details": str(e)}), 500

    # Inner Server 응답 상태 확인
    if inner_response.status_code != 200:
        app.logger.error("Inner server error: %s", inner_response.text)
        return jsonify({"error": "Inner server error", "details": inner_response.text}), inner_response.status_code

    # 응답 JSON 로그 기록
    app.logger.debug("Inner Server response: %s", inner_response.text)

    # 성공 시 Inner Server 응답 반환
    return jsonify(inner_response.json()), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)