import os
import time
import datetime
import threading
import subprocess
import logging
from get_schedule_models import get_today_models, get_tomorrow_models

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# 스위치 스크립트 경로 (컨테이너에서 마운트된 경로 기준)
SCRIPT_DIR = os.environ.get("SCRIPT_DIR", "/app/scripts")
SWITCH_SCRIPT = os.path.join(SCRIPT_DIR, "switch_models_and_ports.sh")

# 스케줄 CSV 경로 (마운트된 위치)
SCHEDULE_CSV = os.environ.get("SCHEDULE_CSV", "/app/schedule/schedule(day).csv")

# API 호출 베이스 (필요 시 사용)
API_BASE = os.environ.get("API_BASE", "http://localhost:5020")


def run_switch_script():
    """
    switch_models_and_ports.sh 스크립트를 실행하여
    A/B 페어 토글, 모델 교체, 포트 전환을 수행합니다.
    """
    try:
        logging.info("Switch script 실행: %s", SWITCH_SCRIPT)
        subprocess.run(["bash", SWITCH_SCRIPT], check=True)
        logging.info("Switch script 완료")
    except subprocess.CalledProcessError as e:
        logging.error("Switch script 오류: %s", e)


def scheduler_loop():
    """
    매일 자정에 run_switch_script() 호출.
    """
    while True:
        now = datetime.datetime.now()
        # 다음 자정 계산
        tomorrow = now + datetime.timedelta(days=1)
        next_midnight = datetime.datetime.combine(tomorrow.date(), datetime.time.min)
        sleep_seconds = (next_midnight - now).total_seconds()
        logging.info("다음 스위칭까지 대기: %.0f초", sleep_seconds)
        time.sleep(sleep_seconds)
        run_switch_script()


def start_scheduler():
    """
    컨테이너 시작 시 초기 스위칭 한 번 실행하고,
    스케줄러 스레드를 띄워 매일 자정 자동 실행합니다.
    """
    # 초기 실행
    run_switch_script()
    # 백그라운드 스레드 실행
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    logging.info("스케줄러 시작: 매일 자정에 자동 스위칭")


if __name__ == '__main__':
    start_scheduler()
    # 프로세스 유지
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logging.info("스케줄러 종료 요청됨")
