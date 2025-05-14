#!/usr/bin/env python3
import os, uvicorn, logging
import os, sys, uvicorn, logging

# ──────────────────────────────────────────────────────────────
# 이 스크립트가 있는 llm/ 디렉터리를 모듈 검색 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# ──────────────────────────────────────────────────────────────

# 실제 vLLM 모델 서버 실행(예: FastAPI별도 엔드포인트 or vllm serve CLI)
from inference_api import inference_app  

logging.basicConfig(level=logging.INFO)

# 컨테이너 이름 끝자리로 GPU 번호 & 포트 결정
container_name = os.environ.get("CONTAINER_NAME", "llm0")
gpu_id = int(container_name[-1]) if container_name[-1].isdigit() else 0
GPU_PORT_MAP = {
        4: 5021,
        5: 5022,
        6: 5023,
        7: 5024
}

port = GPU_PORT_MAP[gpu_id]



logging.info(f"vLLM 서버 시작: GPU={gpu}, port={port}")
uvicorn.run(inference_app, host="0.0.0.0", port=port, reload=False)
