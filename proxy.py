import json
import requests
import logging
from flask import Flask, request, jsonify

app = Flask(__name__)

# 로깅 설정: 디버그 레벨 활성화
logging.basicConfig(level=logging.DEBUG)

# sample.json 템플릿 파일 로드
with open('sample.json', 'r', encoding='utf-8') as f:
    workflow_template = json.load(f)

# Inner Server의 ComfyUI 엔드포인트 '/prompt' (포트 번호 등은 inner server 설정에 맞게 조정)
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

    # 클라이언트 데이터 파싱
    try:
        data = request.get_json()
    except Exception as e:
        app.logger.error("요청 JSON 파싱 실패: %s", str(e))
        return jsonify({"error": "요청 JSON 파싱 실패"}), 400

    positive_prompt = data.get('positive_prompt', '').strip()
    negative_prompt = data.get('negative_prompt', '').strip()

    # 샘플 워크플로우 복사 및 프롬프트 노드 업데이트
    workflow = json.loads(json.dumps(workflow_template))
    if positive_prompt:
        workflow["8"]["inputs"]["text"] = positive_prompt
    if negative_prompt:
        workflow["13"]["inputs"]["text"] = negative_prompt

    # 고급 KSampler 노드가 올바른 프롬프트 노드("8", "13")의 출력을 참조하도록 설정
    workflow["14"]["inputs"]["positive"] = ["8", 0]
    workflow["14"]["inputs"]["negative"] = ["13", 0]

    # 초기 이미지가 있을 경우 반영
    if "init_images" in data and data["init_images"]:
        workflow["1"]["inputs"]["image"] = data["init_images"][0]

    # inner server로 전송할 payload를 문자열로 기록
    payload = json.dumps(workflow, ensure_ascii=False)
    app.logger.debug("Inner Server에 전송할 payload: %s", payload)

    try:
        # inner server의 '/prompt' 엔드포인트로 POST 요청 전송
        resp = requests.post(INNER_SERVER_URL, json=workflow)
        app.logger.debug("Inner Server 응답 상태: %s", resp.status_code)
        app.logger.debug("Inner Server 응답 헤더: %s", resp.headers)
        app.logger.debug("Inner Server 응답 본문: %s", resp.text)

        if resp.status_code != 200:
            app.logger.error("Inner Server 반환 에러 코드: %s", resp.status_code)
            return jsonify({
                "error": "Inner Server에서 에러 발생",
                "status_code": resp.status_code,
                "response": resp.text
            }), resp.status_code

        try:
            result = resp.json()
        except Exception as json_err:
            app.logger.error("응답 JSON 파싱 오류: %s", str(json_err))
            result = {"raw_response": resp.text}
        return jsonify(result), resp.status_code

    except Exception as e:
        app.logger.error("Inner Server 요청 전달 중 예외 발생: %s", str(e))
        return jsonify({"error": "요청 전달에 실패했습니다.", "exception": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
