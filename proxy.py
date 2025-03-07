import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# sample.json 템플릿 파일 로드
with open('sample.json', 'r', encoding='utf-8') as f:
    workflow_template = json.load(f)

# Inner Server의 ComfyUI 엔드포인트를 '/prompt'로 설정 (포트 번호 등은 inner server 설정에 맞게 조정)
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

    # 클라이언트에서 전달한 JSON 데이터 파싱
    data = request.get_json()
    positive_prompt = data.get('positive_prompt', '').strip()
    negative_prompt = data.get('negative_prompt', '').strip()

    # 템플릿 복사본을 생성하고 프롬프트 노드를 업데이트
    workflow = json.loads(json.dumps(workflow_template))
    if positive_prompt:
        workflow["8"]["inputs"]["text"] = positive_prompt
    if negative_prompt:
        workflow["13"]["inputs"]["text"] = negative_prompt

    # 고급 KSampler 노드("14")가 올바른 프롬프트 노드("8", "13")의 출력을 참조하도록 설정
    workflow["14"]["inputs"]["positive"] = ["8", 0]
    workflow["14"]["inputs"]["negative"] = ["13", 0]

    # 초기 이미지가 있는 경우 노드 "1" 업데이트
    if "init_images" in data and data["init_images"]:
        workflow["1"]["inputs"]["image"] = data["init_images"][0]

    app.logger.debug("업데이트된 워크플로우: %s", json.dumps(workflow, ensure_ascii=False))

    try:
        # '/prompt' 엔드포인트로 POST 요청 전송
        resp = requests.post(INNER_SERVER_URL, json=workflow)
        try:
            result = resp.json()
        except Exception as json_err:
            app.logger.error("JSON 파싱 오류: %s, 응답 내용: %s", str(json_err), resp.text)
            result = {"raw_response": resp.text}
        return jsonify(result), resp.status_code
    except Exception as e:
        app.logger.error("요청 전달 오류: %s", str(e))
        return jsonify({"error": "요청 전달에 실패했습니다."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
