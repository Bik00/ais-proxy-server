import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# sample.json 템플릿 파일을 로드합니다.
with open('sample.json', 'r', encoding='utf-8') as f:
    workflow_template = json.load(f)

# Inner Server의 ComfyUI 엔드포인트 (필요에 따라 수정하세요)
INNER_SERVER_URL = 'http://54.180.123.29:8000/generate'

@app.route('/generate', methods=['POST', 'OPTIONS'])
def generate():
    # CORS 프리플라이트 요청 처리
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    # 클라이언트에서 전송한 JSON 데이터 파싱
    data = request.get_json()

    # 클라이언트가 전달한 프롬프트 값(텍스트)을 가져옵니다.
    positive_prompt = data.get('positive_prompt', '').strip()
    negative_prompt = data.get('negative_prompt', '').strip()

    # 템플릿 복사본을 생성합니다.
    workflow = json.loads(json.dumps(workflow_template))

    # 노드 "8"(긍정 프롬프트)와 "13"(부정 프롬프트)의 텍스트를 업데이트합니다.
    if positive_prompt:
        workflow["8"]["inputs"]["text"] = positive_prompt
    if negative_prompt:
        workflow["13"]["inputs"]["text"] = negative_prompt

    # 고급 KSampler 노드("14")가 프롬프트 노드 "8"과 "13"의 출력을 사용하도록 설정합니다.
    workflow["14"]["inputs"]["positive"] = ["8", 0]
    workflow["14"]["inputs"]["negative"] = ["13", 0]

    # 초기 이미지가 있다면 노드 "1"에 반영 (필요시 확장)
    if "init_images" in data and data["init_images"]:
        workflow["1"]["inputs"]["image"] = data["init_images"][0]

    app.logger.debug("업데이트된 워크플로우: %s", json.dumps(workflow, ensure_ascii=False))

    # Inner Server의 ComfyUI로 업데이트된 워크플로우를 전달합니다.
    try:
        resp = requests.post(INNER_SERVER_URL, json=workflow)
        # 응답이 JSON인지 시도합니다.
        try:
            result = resp.json()
        except Exception as json_err:
            app.logger.error("JSON 파싱 오류: %s, 응답 내용: %s", str(json_err), resp.text)
            # JSON 파싱에 실패하면, 응답 텍스트를 그대로 반환합니다.
            result = {"raw_response": resp.text}
        return jsonify(result), resp.status_code
    except Exception as e:
        app.logger.error("요청 전달 오류: %s", str(e))
        return jsonify({"error": "요청 전달에 실패했습니다."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
