import csv
import datetime
import logging
import psycopg2

from model_service import set_model_standby, set_model_serving, set_model_idle


# 로깅 설정
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# PostgreSQL 접속 정보 – 실제 환경에 맞게 수정하세요.
DB_CONN_INFO = "dbname=malpyeong user=postgres password=!TeddySum host=127.0.0.1 port=5432"

# GPU → 포트 매핑 (예시; 환경에 맞게 수정하세요)
GPU_PORT_MAP = {}

# 전역 변수: TEAM_CONFIG (CSV 파일의 한 행을 기반으로 업데이트됨)
TEAM_CONFIG = {
    "serving": [],
    "standby": []
}

def set_team_config_from_csv_row(row):
    """
    CSV 파일의 한 행(row)을 읽어 TEAM_CONFIG를 업데이트
      date, s1_user, s1_gpu, s2_user, s2_gpu, st1_user, st1_gpu, st2_user, st2_gpu
    """
    global TEAM_CONFIG
    try:
        serving = [
            {"user_id": row["s1_user"], "gpu": int(row["s1_gpu"])},
            {"user_id": row["s2_user"], "gpu": int(row["s2_gpu"])}
        ]
        standby = [
            {"user_id": row["st1_user"], "gpu": int(row["st1_gpu"])},
            {"user_id": row["st2_user"], "gpu": int(row["st2_gpu"])}
        ]
        TEAM_CONFIG = {"serving": serving, "standby": standby}
        logging.info("TEAM_CONFIG 업데이트됨: %s", TEAM_CONFIG)
    except Exception as e:
        logging.error("CSV 행 처리 중 오류: %s - %s", row, e)

def daily_model_switch():
    """
    TEAM_CONFIG에 기반하여 모델 상태를 전환
      - serving 상태 모델 → standby 전환
      - standby 상태 모델 → serving 전환
      - TEAM_CONFIG에 없는 모델은 idle 상태로 전환
    """
    global TEAM_CONFIG, GPU_PORT_MAP
    logging.info("daily_model_switch 시작: %s", datetime.datetime.now())
    try:
        # serving → standby 전환
        for s in TEAM_CONFIG["serving"]:
            user_id = s["user_id"]
            gpu_id  = s["gpu"]
            port = GPU_PORT_MAP.get(gpu_id)
            if port is None:
                logging.warning("GPU 포트 매핑 없음 (gpu=%s), %s 건너뜀", gpu_id, user_id)
                continue
            set_model_standby(user_id, gpu_id=gpu_id)
            restart_vllm_process(user_id, role='standby', default_port=port)
            logging.info("%s → standby (gpu=%s, port=%s)", user_id, gpu_id, port)

        # standby → serving 전환
        for st in TEAM_CONFIG["standby"]:
            user_id = st["user_id"]
            gpu_id  = st["gpu"]
            port = GPU_PORT_MAP.get(gpu_id)
            if port is None:
                logging.warning("GPU 포트 매핑 없음 (gpu=%s), %s 건너뜀", gpu_id, user_id)
                continue
            set_model_serving(user_id, gpu_id=gpu_id)
            restart_vllm_process(user_id, role='serving', default_port=port)
            logging.info("%s → serving (gpu=%s, port=%s)", user_id, gpu_id, port)

        # TEAM_CONFIG에 없는 모델은 idle로 전환
        active_users = {s["user_id"] for s in TEAM_CONFIG["serving"]} | {st["user_id"] for st in TEAM_CONFIG["standby"]}
        conn = psycopg2.connect(DB_CONN_INFO)
        cur = conn.cursor()
        # models 테이블의 팀 이름(team_name)을 사용 (CSV 파일의 s1_user 등과 대응됨)
        cur.execute("SELECT team_name FROM models")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        for (team_name,) in rows:
            if team_name not in active_users:
                set_model_idle(team_name)
                logging.info("%s → idle", team_name)
    except Exception as e:
        logging.error("daily_model_switch 실행 중 오류: %s", e)
    logging.info("daily_model_switch 종료: %s", datetime.datetime.now())

def start_scheduler(gpu_port_map, csv_config_path):
    """
    gpu_port_map: 예) {0:5021, 1:5022, 2:5023, 3:5024}
    csv_config_path: CSV 파일 경로 (예: "schedule(day).csv")
    
 
    CSV 파일에서 오늘 날짜(YYYY-MM-DD)와 일치하는 행을 찾아 TEAM_CONFIG를 업데이트
    daily_model_switch()를 즉시 호출.
    """
    global GPU_PORT_MAP
    GPU_PORT_MAP = gpu_port_map

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    logging.info("오늘 날짜: %s", today_str)
    
    try:
        with open(csv_config_path, mode="r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            found = False
            for row in reader:
                if row.get("date", "").strip() == today_str:
                    logging.info("오늘에 해당하는 CSV 행 발견: %s", row)
                    set_team_config_from_csv_row(row)
                    found = True
                    break
            if not found:
                logging.warning("오늘 날짜에 해당하는 CSV 행을 찾지 못했습니다.")
                return
    except Exception as e:
        logging.error("CSV 파일 처리 중 오류: %s", e)
        return

    daily_model_switch()

if __name__ == "__main__":
    # GPU → 포트 매핑 예시; 환경에 맞게 수정하세요.
    gpu_port_mapping = {0: 5021, 1: 5022, 2: 5023, 3: 5024}
    # CSV 파일 경로; 실제 경로로 수정하세요.
    csv_file_path = "schedule(day).csv"
    start_scheduler(gpu_port_mapping, csv_file_path)
