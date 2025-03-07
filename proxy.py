import json
import time
import requests
import logging
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

# 로깅 설정 (DEBUG 레벨)
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s: %(message)s")

app = Flask(__name__)
CORS(app)  # 실제 운영 환경에서는 허용할 도메인을 제한하세요.

# Inner Server의 주소 (실제 IP/포트로 변경)
INNER_SERVER_URL = "http://54.180.123.29:8188"

# sample.json에 정의된 workflow 템플릿 불러오기
with open("sample.json", "r", encoding="utf-8") as f:
    base_workflow = json.load(f)

def save_payload_to_file(payload, filename="last_payload.json"):
    try:
        with open(filename, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2, ensure_ascii=False)
        logging.debug("Payload가 %s 파일로 저장되었습니다.", filename)
    except Exception as e:
        logging.error("Payload 파일 저장 실패: %s", e)

@app.route("/generate", methods=["POST"])
def generate_image():
    try:
        # 클라이언트 데이터 수신 및 검증
        client_data = request.get_json()
        if not client_data:
            logging.error("클라이언트 요청 데이터가 없습니다.")
            return jsonify({"error": "클라이언트 요청 데이터가 없습니다."}), 400

        logging.debug("클라이언트로부터 받은 데이터:\n%s", json.dumps(client_data, indent=2, ensure_ascii=False))

        # workflow 템플릿 deep copy 후 클라이언트 데이터 반영
        workflow = json.loads(json.dumps(base_workflow))

        # 1. 대상 이미지 (노드 "1")
        if "init_images" in client_data and client_data["init_images"]:
            image_data = client_data["init_images"][0]
            if not image_data.startswith("data:image"):
                image_data = "data:image/jpeg;base64," + image_data
            workflow["1"]["inputs"]["image"] = image_data

        # 2. 긍정 프롬프트 (노드 "8")
        if "prompt" in client_data:
            workflow["8"]["inputs"]["text"] = client_data["prompt"]
        # 디버그: 노드 "8"의 프롬프트 값 확인
        prompt_value = workflow["8"]["inputs"].get("text", "")
        if not prompt_value:
            logging.warning("노드 '8'의 prompt 값이 비어있습니다.")
        else:
            logging.debug("노드 '8' 프롬프트 값: %s", prompt_value)

        # 3. 부정 프롬프트 (노드 "13")
        if "negative_prompt" in client_data:
            workflow["13"]["inputs"]["text"] = client_data["negative_prompt"]

        # 4. img2img 파라미터 (노드 "14")
        if "steps" in client_data:
            workflow["14"]["inputs"]["steps"] = client_data["steps"]
        if "cfg_scale" in client_data:
            workflow["14"]["inputs"]["cfg"] = client_data["cfg_scale"]
        if "sampler_index" in client_data:
            workflow["14"]["inputs"]["sampler_name"] = client_data["sampler_index"]
        if "denoising_strength" in client_data:
            workflow["14"]["inputs"]["denoising_strength"] = client_data["denoising_strength"]

        # 5. 이미지 크기 (노드 "25")
        if "width" in client_data:
            workflow["25"]["inputs"]["width"] = client_data["width"]
        if "height" in client_data:
            workflow["25"]["inputs"]["height"] = client_data["height"]

        # 6. 체크포인트 설정 (노드 "23"와 "39")
        if "override_settings" in client_data and "sd_model_checkpoint" in client_data["override_settings"]:
            new_checkpoint = client_data["override_settings"]["sd_model_checkpoint"]
            workflow["23"]["inputs"]["ckpt_name"] = new_checkpoint
            workflow["39"]["inputs"]["ckpt_name"] = new_checkpoint

        # 디버그: 최종 payload 전체 출력 및 파일로 저장
        logging.debug("Inner Server로 전송할 workflow payload:\n%s", json.dumps(workflow, indent=2, ensure_ascii=False))
        save_payload_to_file(workflow)

        # Inner Server의 /prompt 엔드포인트에 workflow 전송
        prompt_url = f"{INNER_SERVER_URL}/prompt"
        post_resp = requests.post(prompt_url, json=workflow)
        logging.debug("POST 요청을 %s 에 전송합니다.", prompt_url)
        logging.debug("POST 응답 상태 코드: %s", post_resp.status_code)
        logging.debug("POST 응답 헤더: %s", post_resp.headers)
        logging.debug("POST 응답 본문: %s", post_resp.text)
        try:
            post_resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logging.error("POST 요청 오류: %s, 응답내용: %s", e, post_resp.text)
            return jsonify({
                "error": f"{post_resp.status_code} Client Error: {post_resp.reason} for url: {prompt_url}",
                "details": post_resp.text
            }), post_resp.status_code

        post_data = post_resp.json()
        logging.debug("POST 응답 (Inner Server /prompt):\n%s", json.dumps(post_data, indent=2, ensure_ascii=False))

        if "queue_id" not in post_data:
            logging.error("Inner Server 응답에 queue_id가 없음: %s", json.dumps(post_data, indent=2, ensure_ascii=False))
            return jsonify({"error": "Inner Server 응답에 queue_id가 없음", "details": post_data}), 500

        queue_id = post_data["queue_id"]

        # 폴링: /view_queue 엔드포인트를 통해 작업 상태 확인
        view_url = f"{INNER_SERVER_URL}/view_queue"
        max_poll_attempts = 30
        poll_attempts = 0

        while True:
            poll_resp = requests.get(view_url, params={"queue_id": queue_id})
            logging.debug("폴링 요청 URL: %s?queue_id=%s", view_url, queue_id)
            try:
                poll_resp.raise_for_status()
            except requests.exceptions.HTTPError as e:
                logging.error("폴링 요청 오류: %s, 응답내용: %s", e, poll_resp.text)
                return jsonify({
                    "error": f"Polling Error: {poll_resp.status_code}",
                    "details": poll_resp.text
                }), poll_resp.status_code

            poll_data = poll_resp.json()
            logging.debug("폴링 응답:\n%s", json.dumps(poll_data, indent=2, ensure_ascii=False))
            status = poll_data.get("status", "")

            if status == "done":
                outputs = poll_data.get("outputs", {})
                image_url = outputs.get("image_url")
                if image_url:
                    image_resp = requests.get(image_url)
                    try:
                        image_resp.raise_for_status()
                    except requests.exceptions.HTTPError as e:
                        logging.error("이미지 다운로드 오류: %s, 응답내용: %s", e, image_resp.text)
                        return jsonify({
                            "error": "이미지 다운로드 중 오류 발생",
                            "details": image_resp.text
                        }), image_resp.status_code
                    logging.debug("이미지 다운로드 완료.")
                    return Response(image_resp.content, mimetype="image/jpeg")
                else:
                    logging.debug("작업 출력: %s", json.dumps(outputs, indent=2, ensure_ascii=False))
                    return jsonify(outputs)
            elif status in ["pending", "processing"]:
                poll_attempts += 1
                if poll_attempts > max_poll_attempts:
                    logging.error("폴링 시간 초과, 최근 응답: %s", json.dumps(poll_data, indent=2, ensure_ascii=False))
                    return jsonify({"error": "폴링 시간 초과", "details": poll_data}), 504
                time.sleep(2)
            elif status == "error":
                logging.error("작업 오류 발생: %s", json.dumps(poll_data, indent=2, ensure_ascii=False))
                return jsonify({"error": "이미지 생성 중 오류 발생", "details": poll_data}), 500
            else:
                logging.error("알 수 없는 상태: %s", json.dumps(poll_data, indent=2, ensure_ascii=False))
                return jsonify({"error": "알 수 없는 상태", "details": poll_data}), 500

    except Exception as e:
        logging.exception("generate_image 함수에서 처리되지 않은 예외 발생:")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

