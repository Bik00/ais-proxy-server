import base64
import binascii
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/generate', methods=['POST'])
def generate():
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "No payload received"}), 400

    init_images = payload.get("init_images", [])
    if not init_images:
        return jsonify({"error": "No init_images provided"}), 400

    base64_image = init_images[0]
    try:
        # 패딩 보정: 길이를 4의 배수로 만듦
        missing_padding = len(base64_image) % 4
        if missing_padding:
            base64_image += '=' * (4 - missing_padding)
        image_data = base64.b64decode(base64_image)
        # 이후 이미지 처리 로직...
        return jsonify({"message": "Image processed successfully"})
    except binascii.Error as e:
        app.logger.error(f"Base64 decoding error: {str(e)}")
        return jsonify({"error": "Invalid base64 image data", "details": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)