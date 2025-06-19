#!/usr/bin/env python3
import os
import sys
import logging
import time
import subprocess
# 이 스크립트 파일이 있는 llm/ 디렉터리를 모듈 검색 경로에 추가
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# 컨테이너 이름 끝자리로 GPU 번호 추출
container_name = os.environ.get("CONTAINER_NAME", "llm4")
gpu_id = int(container_name[-1]) if container_name[-1].isdigit() else 4

# GPU별 포트 매핑
port_map = {
    4: 5021,
    5: 5022,
    6: 5023,
    7: 5024,
}
port = port_map.get(gpu_id, 5021)
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logging.info("LLM 컨테이너 유휴 모드 진입: API 호출로 vLLM serve를 실행합니다")
# 컨테이너는 계속 살아있기만 하면 됨
try:
    while True:
        time.sleep(3600)
except KeyboardInterrupt:
    logging.info("serve_main 종료")
