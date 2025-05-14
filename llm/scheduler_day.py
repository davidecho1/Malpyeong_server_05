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

from get_schedule_models import get_today_models, get_tomorrow_models

# switch script 경로
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
    매일 자정(run at midnight)에 run_switch_script 호출
    """
    while True:
        now = datetime.datetime.now()
        tomorrow = now + datetime.timedelta(days=1)
        next_midnight = datetime.datetime.combine(tomorrow.date(), datetime.time.min)
        sleep_seconds = (next_midnight - now).total_seconds()
        logging.info("다음 스위칭까지 대기: %.0f초", sleep_seconds)
        time.sleep(sleep_seconds)
        run_switch_script()


def start_scheduler(gpu_port_map, csv_config_path):
    """
    gpu_port_map: {gpu_id: port}, (start_scheduler가 main.py에서 전달되는 매핑)
    csv_config_path: CSV 스케줄 파일 경로 (start_scheduler가 main.py에서 전달)

    초기 스위치 실행 후 백그라운드 스레드로 매일 자정 스위칭 수행
    """
    # 전달받은 매개변수 로깅
    logging.info("start_scheduler 호출: GPU_PORT_MAP=%s, CSV_PATH=%s", gpu_port_map, csv_config_path)

    # 오늘/내일 모델 정보 로깅 (get_schedule_models 사용)
    try:
        today = get_today_models(csv_path=csv_config_path) if 'get_today_models' in globals() else []
        logging.info("오늘 모델: %s", today)
        tomorrow = get_tomorrow_models(csv_path=csv_config_path) if 'get_tomorrow_models' in globals() else []
        logging.info("내일 모델: %s", tomorrow)
    except Exception as e:
        logging.warning("스케줄 모델 조회 중 오류: %s", e)

    # 초기 switch 실행
    run_switch_script()

    # 백그라운드 스레드 시작
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    logging.info("스케줄러 시작: 매일 자정 자동 스위칭")


if __name__ == '__main__':
    logging.info("스케줄러 시작 (스크립트 디렉토리: %s)", SCRIPT_DIR)
    # 기본 매핑과 CSV 경로
    default_map = {0:5021,1:5022,2:5023,3:5024}
    default_csv = os.environ.get("SCHEDULE_CSV", os.path.normpath(os.path.join(BASE_DIR, "..", "schedule", "schedule(day).csv")))
    start_scheduler(default_map, default_csv)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logging.info("스케줄러 종료 요청됨")
