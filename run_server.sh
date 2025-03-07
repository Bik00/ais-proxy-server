#!/bin/bash

# 5000 포트를 사용 중인 프로세스의 PID를 찾아 종료
PID=$(lsof -t -i:5000)
if [ -n "$PID" ]; then
  kill -9 $PID
  echo "Killed process $PID using port 5000"
fi

# 기존 output.log 삭제
rm -rf output.log

# proxy.py를 백그라운드에서 실행하고 로그를 output.log에 기록
nohup python proxy.py > output.log 2>&1 &

# output.log를 실시간으로 모니터링
tail -f output.log
