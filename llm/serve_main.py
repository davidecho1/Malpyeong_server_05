#!/usr/bin/env python3
import os
import sys
import logging
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

logging.info(f"vLLM 서버 시작: GPU={gpu_id}, port={port}")

# 환경변수로 GPU 지정
os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

cmd = [
    "vllm", "serve",
    "--port", str(port),
    "--device", "cuda",  # 고정값
]
logging.info("실행 명령: " + " ".join(cmd))

# 서빙 프로세스를 이 컨테이너의 메인 프로세스로 실행
subprocess.run(cmd, check=True, env=os.environ)
