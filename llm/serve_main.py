#!/usr/bin/env python3
import os
import uvicorn
import logging

# 실제 vLLM 모델 서버 실행(예: FastAPI별도 엔드포인트 or vllm serve CLI)
from inference_api import inference_app  

logging.basicConfig(level=logging.INFO)

# 컨테이너 이름 끝자리로 GPU 번호 & 포트 결정
name = os.environ.get("CONTAINER_NAME", "llm0")
gpu  = int(name[-1])
port_map = {0:5021, 1:5022, 2:5023, 3:5024}
port = port_map[gpu]

logging.info(f"vLLM 서버 시작: GPU={gpu}, port={port}")
uvicorn.run(inference_app, host="0.0.0.0", port=port, reload=False)
