import json
import logging
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS  # flask-cors 임포트

app = Flask(__name__)
CORS(app)  # 모든 도메인에 대해 CORS 허용. 필요시 resources 매개변수를 이용해 제한 가능.
logging.basicConfig(level=logging.DEBUG)

# Inner Server의 ComfyUI 엔드포인트 (수정 없이 그대로 사용)
INNER_SERVER_URL = 'http://54.180.123.29:8188/prompt'

# 워크플로우의 기본 샘플 파일 (sample.json)을 미리 로드합니다.
with open('sample.json', 'r', encoding='utf-8') as f:
    base_workflow = json.load(f)

@app.route('/generate', methods=['POST'])
def generate():
    # 클라이언트에서 전송한 JSON 데이터를 읽어옵니다.
    client_data = request.get_json()
    
    # 클라이언트에서 textarea로 입력한 프롬프트 값을 추출합니다.
    positive_prompt = client_data.get('positive', '').strip()
    negative_prompt = client_data.get('negative', '').strip()
    
    # 만약 두 프롬프트 모두 비어있다면, Inner Server에서는 "no prompts" 에러가 발생하므로
    # 기본값을 할당하거나 에러 응답을 반환합니다.
    if not positive_prompt and not negative_prompt:
        return jsonify({"error": "No prompts provided"}), 400
    
    # sample.json의 워크플로우를 복제하여 수정합니다.
    workflow = json.loads(json.dumps(base_workflow))
    
    # 긍정 프롬프트 업데이트 (키 "8")
    if '8' in workflow and 'inputs' in workflow['8']:
        workflow['8']['inputs']['text'] = positive_prompt if positive_prompt else "default positive prompt"
    
    # 부정 프롬프트 업데이트 (키 "13")
    if '13' in workflow and 'inputs' in workflow['13']:
        workflow['13']['inputs']['text'] = negative_prompt if negative_prompt else "default negative prompt"
    
    app.logger.debug("Inner Server에 전송할 payload: %s", json.dumps(workflow))
    
    headers = {'Content-Type': 'application/json'}
    try:
        inner_response = requests.post(INNER_SERVER_URL, headers=headers, json=workflow)
        inner_response.raise_for_status()
    except requests.RequestException as e:
        app.logger.error("Inner Server 전송 중 에러 발생: %s", e)
        return jsonify({"error": "Failed to communicate with Inner Server"}), 500
    
    return jsonify(inner_response.json())

if __name__ == '__main__':
    # 모든 주소에서 접속 가능하도록 설정하고 5000번 포트에서 실행합니다.
    app.run(host='0.0.0.0', port=5000)
