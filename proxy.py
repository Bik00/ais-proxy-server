import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# sample.json 템플릿 파일 로드
with open('sample.json', 'r', encoding='utf-8') as f:
    workflow_template = json.load(f)

# Inner Server의 ComfyUI 엔드포인트 (기본 포트 8188 사용)
INNER_SERVER_URL = 'http://54.180.123.29:8188/prompt'

@app.route('/generate', methods=['POST', 'OPTIONS'])
def generate():
    # CORS 프리플라이트 처리
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    # 클라이언트 전송 데이터 파싱
    data = request.get_json()
    positive_prompt = data.get('positive_prompt', '').strip()
    negative_prompt = data.get('negative_prompt', '').strip()

    # 템플릿 복사본 생성 및 업데이트
    workflow = json.loads(json.dumps(workflow_template))
    if positive_prompt:
        workflow["8"]["inputs"]["text"] = positive_prompt
    if negative_prompt:
        workflow["13"]["inputs"]["text"] = negative_prompt

    # 고급 KSampler 노드가 올바른 프롬프트 노드를 참조하도록 수정
    workflow["14"]["inputs"]["positive"] = ["8", 0]
    workflow["14"]["inputs"]["negative"] = ["13", 0]

    # 초기 이미지가 있다면 반영
    if "init_images" in data and data["init_images"]:
        workflow["1"]["inputs"]["image"] = data["init_images"][0]

    app.logger.debug("업데이트된 워크플로우: %s", json.dumps(workflow, ensure_ascii=False))

    try:
        # Inner Server에 POST 요청 (ComfyUI가 기대하는 형식으로 래핑)
        payload = {"prompt": workflow}
        resp = requests.post(INNER_SERVER_URL, json=payload)

        # 응답 상태 코드 확인
        if resp.status_code == 200:
            try:
                result = resp.json()
                return jsonify(result), 200
            except json.JSONDecodeError as json_err:
                app.logger.error("JSON 파싱 오류: %s, 응답 내용: %s", str(json_err), resp.text)
                return jsonify({"error": "응답을 JSON으로 파싱할 수 없습니다.", "raw_response": resp.text}), 500
        else:
            app.logger.error("Internal Server Error: %s %s", resp.status_code, resp.text)
            return jsonify({"error": f"Internal Server Error: {resp.status_code}", "raw_response": resp.text}), resp.status_code
    except requests.exceptions.RequestException as e:
        app.logger.error("요청 전달 오류: %s", str(e))
        return jsonify({"error": "요청 전달에 실패했습니다."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)