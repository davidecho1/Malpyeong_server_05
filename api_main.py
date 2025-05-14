import os, sys

# ──────────────────────────────────────────────────────────────
# llm/ 폴더를 Python 모듈 검색 경로에 최우선으로 추가
sys.path.insert(0, os.path.join(os.getcwd(), "llm"))
# ──────────────────────────────────────────────────────────────

import uvicorn
import logging
from AI_API import app
from scheduler_day import start_scheduler

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def main():
    # 1) 스케줄러: 한 번 실행 + 매일 자정 자동 실행
    start_scheduler()
    # 2) FastAPI 앱 띄우기 (호스트 0.0.0.0, 포트 5020)
    logging.info("API + 스케줄러 시작: port=5020")
    uvicorn.run(app, host="0.0.0.0", port=5020, reload=False)

if __name__ == "__main__":
    main()
