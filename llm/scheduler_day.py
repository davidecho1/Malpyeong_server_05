#!/usr/bin/env python3
import os
import sys
import time
import datetime
import threading
import subprocess
import logging

# 스크립트 및 스케줄러 모듈 위치 (컨테이너 경로 기준)
SCRIPT_DIR = os.environ.get("SCRIPT_DIR", "/app/scripts")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from get_schedule_models import get_today_models, get_tomorrow_models

# 로깅 설정 (LOG_LEVEL 환경변수로 조정 가능)
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format='[%(levelname)s] %(message)s'
)

# switch script 경로
SWITCH_SCRIPT = os.path.join(SCRIPT_DIR, "switch_models_and_ports.sh")


def run_switch_script():
    """
    switch_models_and_ports.sh 스크립트를 실행하여
    A/B 페어 토글, 모델 교체, 포트 전환 수행
    """
    logging.info("Switch script 실행: %s", SWITCH_SCRIPT)
    try:
        subprocess.run(["bash", SWITCH_SCRIPT], check=True, env=os.environ)
        logging.info("Switch script 완료")
    except subprocess.CalledProcessError as e:
        logging.error("Switch script 오류: %s", e)


def scheduler_loop():
    """
    매일 자정(run at midnight)에 run_switch_script() 호출
    """
    while True:
        now = datetime.datetime.now()
        tomorrow = now + datetime.timedelta(days=1)
        next_midnight = datetime.datetime.combine(tomorrow.date(), datetime.time.min)
        sleep_seconds = (next_midnight - now).total_seconds()
        logging.info("다음 스위칭까지 대기: %.0f초", sleep_seconds)
        time.sleep(sleep_seconds)
        run_switch_script()


def start_scheduler():
    """
    초기 스위치 실행 후 데몬 스레드로 매일 자정 자동 스위칭 시작
    """
    # 초기 실행
    run_switch_script()
    # 백그라운드 스레드에서 일정 반복
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    logging.info("스케줄러 시작: 매일 자정 자동 스위칭")


if __name__ == '__main__':
    logging.info(
        "컨테이너 환경 확인: SCRIPT_DIR=%s, SCHEDULE_CSV=%s",
        SCRIPT_DIR,
        os.environ.get("SCHEDULE_CSV")
    )
    start_scheduler()
    try:
        # 메인 스레드 유지
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logging.info("스케줄러 종료 요청됨")
