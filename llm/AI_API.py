#!/usr/bin/env python
# -*- coding: utf-8 -*-

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import datetime
import psycopg2
import docker
import os

from llm.model_service import (
    download_repo_and_register_model,
    set_model_idle,
    set_model_serving,
    set_model_standby,
    kill_vllm_process_by_port
)
import subprocess

docker_client = docker.from_env()  # ← 추가: Docker 소켓 연결

# GPU 번호를 컨테이너 이름으로 매핑
GPU_TO_CONTAINER = {
    4: "llm4",
    5: "llm5",
    6: "llm6",
    7: "llm7"
}

app = FastAPI()

# PostgreSQL 접속 정보 (DB 연결 함수로 관리)
#DB_CONN_INFO = "dbname=malpyeong user=postgres password=!TeddySum host=192.168.242.203 port=5432"
# ========== 환경변수 기반 DB 접속 문자열 구성 ==========
DB_CONN_INFO = (
    f"dbname={os.getenv('DB_NAME','malpyeong')} "
    f"user={os.getenv('DB_USER','postgres')} "
    f"password={os.getenv('DB_PASSWORD','!TeddySum')} "
    f"host={os.getenv('DB_HOST','host.docker.internal')} "
    f"port={os.getenv('DB_PORT','5432')}"
)


def get_db_connection():
    return psycopg2.connect(DB_CONN_INFO)

def parse_user_id(user_id: str):
    try:
        return user_id.split("/", 1)
    except Exception:
        raise ValueError("user_id는 'team/model' 형식이어야 합니다.")



def switch_external_port(external_port: int, internal_port: int):
    """
    외부 포트(1111, 2222)를 내부 포트(5021~5024)로 iptables NAT 연결
    기존 연결은 제거 후 재설정
    """
    try:
        # 기존 연결 제거 (실패해도 무시)
        subprocess.run(
            ["iptables", "-t", "nat", "-D", "PREROUTING", "-p", "tcp", "--dport", str(external_port),
             "-j", "REDIRECT", "--to-port", str(internal_port)],
            stderr=subprocess.DEVNULL
        )
        # 새로운 연결 추가
        subprocess.run(
            ["iptables", "-t", "nat", "-A", "PREROUTING", "-p", "tcp", "--dport", str(external_port),
             "-j", "REDIRECT", "--to-port", str(internal_port)],
            check=True
        )
        print(f"[iptables] {external_port} → {internal_port} 연결 완료")
    except Exception as e:
        raise RuntimeError(f"[iptables] 연결 실패: {e}")


def is_duplicate_pair(a_model_id: int, b_model_id: int) -> bool:
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM evaluations
            WHERE (a_model_id = %s AND b_model_id = %s)
               OR (a_model_id = %s AND b_model_id = %s)
            LIMIT 1
        """, (a_model_id, b_model_id, b_model_id, a_model_id))
        exists = cur.fetchone()
        cur.close()
        conn.close()
        return exists is not None
    except Exception as e:
        print(f"[is_duplicate_pair] DB 오류: {e}")
        return True  # 에러 발생 시 중복으로 간주

@app.get("/ping")
async def ping():
    return {"msg": "pong"}

# 모델 다운로드
@app.post("/models/download")
async def models_download(request: Request):
    data = await request.json()
    repo_id = data.get("user_id")
    try:
        model_dir = download_repo_and_register_model(repo_id)
        return {"msg": f"Downloaded to: {model_dir} (actual path)"}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

# 모델 스탠바이
@app.post("/models/standby")
async def standby_model(request: Request):
    data = await request.json()
    user_id = data["user_id"]  # "team_name/model_name"
    gpu_id = data["gpu_id"]
    port = data["port"]

    try:
        team_name, model_name = user_id.split("/", 1)

        # 1. DB에서 model path 조회
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT safetensors_path FROM models
            WHERE team_name = %s AND model_name = %s
        """, (team_name, model_name))
        result = cur.fetchone()
        cur.close()
        conn.close()

        if not result:
            raise ValueError(f"모델 {user_id}의 경로가 DB에 없습니다.")

        model_path = result[0]

        # 1) 이전 vLLM 프로세스 종료 (컨테이너 내부에서)
        # 2) 새로운 vLLM serve 실행
        from llm.model_service import launch_vllm
        launch_vllm(model_path, port, gpu_id)
        # 4. 상태 업데이트
        set_model_standby(team_name, model_name, gpu_id)
        return {
            "msg": f"{user_id} → standby on GPU {gpu_id}, port {port} (path: {model_path})"
        }
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

# 모델 서빙
@app.post("/models/serve")
async def serve_model(request: Request):
    try:
        data = await request.json()
        print("[DEBUG] 수신 데이터:", data)
    except Exception as ex:
        print("[ERROR] JSON 파싱 실패:", str(ex))
        return JSONResponse(content={"error": "invalid json", "detail": str(ex)}, status_code=400)

    user_id = data["user_id"]
    gpu_id   = data["gpu_id"]
    port     = data["port"]
    external_port = data["external_port"]

    try:
        team_name, model_name = user_id.split("/", 1)
        conn = get_db_connection()
        cur  = conn.cursor()

        # ───────────────────────────────
        # 0) 같은 GPU에 묶여 있는 기존 serving 모델 조회
        # ───────────────────────────────
        cur.execute(
            "SELECT team_name, model_name FROM models "
            "WHERE gpu_id = %s AND model_state = 'serving'",
            (gpu_id,)
        )
        old = cur.fetchone()
        if old:
            old_team, old_model = old
            # 1) 기존 모델을 idle 상태로 전환
            set_model_idle(old_team, old_model)

        # ───────────────────────────────
        # 2) DB에서 새 모델 경로 조회
        # ───────────────────────────────
        cur.execute(
            "SELECT safetensors_path FROM models "
            "WHERE team_name = %s AND model_name = %s",
            (team_name, model_name)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            raise ValueError(f"모델 {user_id} 경로가 DB에 없습니다.")
        model_path = row[0]

        # ───────────────────────────────
        # 3) 프로세스 교체
        # ───────────────────────────────
        from llm.model_service import launch_vllm
        launch_vllm(model_path, port, gpu_id)

	# ───────────────────────────────
        # 3.5) 외부포트 → 내부포트 NAT 설정
        switch_external_port(external_port, port)
        # (이 함수가 내부적으로 iptables -t nat -D …, -A … 를 실행합니다)
 	# ───────────────────────────────

        # ───────────────────────────────
        # 4) 새 모델을 serving으로 표시
        # ───────────────────────────────
        set_model_serving(team_name, model_name, gpu_id)

        return {
            "msg": f"{user_id} → serving on GPU {gpu_id}, ports: internal {port}, external {external_port}"
        }

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)


    
@app.post("/models/idle")
async def idle_model(request: Request):
    data = await request.json()
    user_id = data["user_id"]  # 예: "deepseek/my-model"

    try:
        team_name, model_name = user_id.split("/", 1)

        # 1. 실행 중인 포트 조회
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT gpu_id FROM models
            WHERE team_name = %s AND model_name = %s
        """, (team_name, model_name))
        result = cur.fetchone()
        cur.close()
        conn.close()

        if not result:
            raise ValueError(f"{user_id} 상태 조회 실패")

        gpu_id = result[0]
        if gpu_id is None:
            print(f"[idle] {user_id}는 이미 idle 상태입니다.")
            return {"msg": f"{user_id} is already idle"}

        # 2. 포트는 gpu_id와 1:1로 매핑된다고 가정 (예: GPU 0 → 5021)
        if int(gpu_id) >= 4:
            port = 5021 + int(gpu_id) - 4
        else : 
            port = 5021 + int(gpu_id)
        # 3. vllm 종료
        kill_vllm_process_by_port(port)
        # 4. DB 상태 업데이트
        set_model_idle(team_name, model_name)
        return {"msg": f"{user_id} → idle (port {port} 종료 완료)"}

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

    
# 모델 스위치: 기존 serving → idle, 새 모델 → serving
@app.post("/models/switch")
async def switch_model(request: Request):
    """
    현재 외부 포트(1111, 2222)에 연결된 서빙 모델과 스탠바이 모델을 서로 교체
    DB 상태 업데이트 + iptables NAT 연결 재설정
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        updates = []

        for external_port, candidates in EXTERNAL_TO_INTERNAL_PORTS.items():
            # 후보 내부 포트: 2개 중 어떤 것이 serving인지 찾음
            serving_port = None
            standby_port = None
            for port in candidates:
                cur.execute("""
                    SELECT team_name, model_name, gpu_id FROM models
                    WHERE model_state = 'serving' AND safetensors_port = %s
                """, (port,))
                row = cur.fetchone()
                if row:
                    serving_port = port
                    serving_model = row
                else:
                    standby_port = port

            if serving_port is None or standby_port is None:
                raise RuntimeError(f"서빙/스탠바이 포트를 식별할 수 없음: {candidates}")

            # 1. 기존 serving → standby
            cur.execute("""
                UPDATE models SET model_state = 'standby'
                WHERE safetensors_port = %s
            """, (serving_port,))
            updates.append(("standby", *serving_model))

            # 2. standby → serving
            cur.execute("""
                UPDATE models SET model_state = 'serving'
                WHERE safetensors_port = %s
            """, (standby_port,))

            cur.execute("""
                SELECT team_name, model_name, gpu_id FROM models
                WHERE safetensors_port = %s
            """, (standby_port,))
            standby_model = cur.fetchone()
            updates.append(("serving", *standby_model))

            # 3. 외부 포트 NAT 재연결 (iptables)
            switch_external_port(external_port, standby_port)

        conn.commit()

        return {
            "msg": "모델 스위칭 완료",
            "details": updates
        }

    except Exception as e:
        conn.rollback()
        return JSONResponse(content={"error": str(e)}, status_code=500)

    finally:
        cur.close()
        conn.close()

        
@app.post("/eval/submit")
async def submit_evaluation(request: Request):
    data = await request.json()
    evaluator_id = data["evaluator_id"]
    a_name = data["a_model_name"]
    b_name = data["b_model_name"]
    prompt = data["prompt"]
    a_answer = data["a_model_answer"]
    b_answer = data["b_model_answer"]
    evaluation = data["evaluation"]
    session_id = data["session_id"]

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM models WHERE model_name = %s", (a_name,))
        a_model_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM models WHERE model_name = %s", (b_name,))
        b_model_id = cur.fetchone()[0]

        if is_duplicate_pair(a_model_id, b_model_id):
            return {"msg": "duplicate"}

        cur.execute(
            """
            INSERT INTO evaluations (
                evaluator_id, a_model_id, b_model_id,
                prompt, a_model_answer, b_model_answer,
                evaluation, session_id, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                evaluator_id, a_model_id, b_model_id,
                prompt, a_answer, b_answer,
                evaluation, session_id, datetime.datetime.now()
            ),
        )

        conn.commit()
        cur.close()
        conn.close()

        return {"msg": "submitted"}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5020, debug=True, use_reloader=False)    
