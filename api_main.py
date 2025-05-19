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
    # 1) GPU→포트 매핑
    gpu_port_map = {4: 5021, 5: 5022, 6: 5023, 7: 5024}

    # 2) CSV 스케줄 파일 위치 (루트의 schedule/day.csv)
    csv_path = os.environ.get(
        "SCHEDULE_CSV",
        os.path.join(os.getcwd(), "schedule", "day.csv")
    )

    # 3) 스케줄러 실행 (gpu_port_map, csv_path 두 인자 필수)
    start_scheduler(gpu_port_map, csv_path)

    logging.info("API + 스케줄러 시작: port=5020")
    uvicorn.run(app, host="0.0.0.0", port=5020, reload=False)


if __name__ == "__main__":
    main()
