#!/usr/bin/env python3
import os
import sys
import time
import datetime
import threading
import subprocess
import logging

# 로깅 설정
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format='[%(levelname)s] %(message)s'
)

# 스크립트 디렉터리 설정 (환경변수 우선, 없으면 프로젝트 scripts 폴더)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SCRIPT_DIR = os.environ.get("SCRIPT_DIR") or os.path.normpath(os.path.join(BASE_DIR, "..", "scripts"))
if not os.path.isdir(SCRIPT_DIR):
    logging.error("SCRIPT_DIR가 존재하지 않습니다: %s", SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

# 스케줄 모델 조회 함수
try:
    from get_schedule_models import get_today_models, get_tomorrow_models
except ImportError:
    logging.warning("get_schedule_models 모듈을 찾을 수 없습니다: %s", SCRIPT_DIR)
    def get_today_models(): return []
    def get_tomorrow_models(): return []

# 스위치 스크립트 경로
SWITCH_SCRIPT = os.path.join(SCRIPT_DIR, "switch_models_and_ports.sh")


def run_switch_script():
    """
    switch_models_and_ports.sh를 실행하여
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
    매일 자정에 run_switch_script 호출
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
    시작 시 스케줄 정보 로깅, 초기 스위치 실행,
    그 후 데몬 스레드에서 매일 자정 스위칭 반복
    """
    # 오늘/내일 모델 로깅
    try:
        today = get_today_models()
        logging.info("오늘 모델: %s", today)
        tomorrow = get_tomorrow_models()
        logging.info("내일 모델: %s", tomorrow)
    except Exception as e:
        logging.warning("스케줄 모델 조회 중 오류: %s", e)

    # 초기 스위치 한 번 수행
    run_switch_script()

    # 백그라운드 스레드 시작
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    logging.info("스케줄러 시작: 매일 자정 자동 스위칭")


if __name__ == '__main__':
    logging.info("스케줄러 시작 (스크립트 디렉토리: %s)", SCRIPT_DIR)
    start_scheduler()
    # 메인 스레드 대기
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logging.info("스케줄러 종료 요청됨")
