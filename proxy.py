#!/usr/bin/env python3
"""
Simple HTTP Proxy Server
Usage:
    python proxy.py

Note:
    이 프록시 서버는 기본 HTTP 요청만 처리합니다. (HTTPS CONNECT 요청은 지원하지 않습니다.)
"""

import socket
import threading
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

def handle_client(client_socket):
    try:
        request = client_socket.recv(4096)
        if not request:
            client_socket.close()
            return

        # 요청의 첫 번째 줄을 추출
        request_line = request.split(b'\n')[0]
        parts = request_line.split(b' ')
        if len(parts) < 2:
            client_socket.close()
            return

        url = parts[1]
        # 프로토콜(예: "http://") 제거
        http_pos = url.find(b'://')
        if http_pos != -1:
            url = url[(http_pos+3):]
        # 호스트명 종료 위치 찾기
        host_end = url.find(b'/')
        if host_end == -1:
            host_end = len(url)
        # 기본 포트 설정
        port = 80
        # 호스트와 포트가 함께 명시된 경우 처리
        if b':' in url[:host_end]:
            host_parts = url[:host_end].split(b':')
            host = host_parts[0]
            try:
                port = int(host_parts[1])
            except ValueError:
                port = 80
        else:
            host = url[:host_end]

        host_str = host.decode('utf-8')
        logging.info(f"Connecting to {host_str}:{port}")

        # 대상 서버에 연결
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_socket.connect((host_str, port))
        remote_socket.sendall(request)

        # 대상 서버로부터 데이터를 받아 클라이언트에 전달
        while True:
            data = remote_socket.recv(4096)
            if not data:
                break
            client_socket.sendall(data)

        remote_socket.close()
        client_socket.close()
    except Exception as e:
        logging.error(f"Error handling client: {e}")
        client_socket.close()

def main():
    bind_ip = '0.0.0.0'
    bind_port = 8888
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((bind_ip, bind_port))
    server.listen(5)
    logging.info(f"Proxy server listening on {bind_ip}:{bind_port}")

    try:
        while True:
            client_sock, addr = server.accept()
            logging.info(f"Accepted connection from {addr[0]}:{addr[1]}")
            client_handler = threading.Thread(target=handle_client, args=(client_sock,))
            client_handler.daemon = True
            client_handler.start()
    except KeyboardInterrupt:
        logging.info("Shutting down proxy server...")
        server.close()

if __name__ == '__main__':
    main()
