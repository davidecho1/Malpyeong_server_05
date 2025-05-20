#!/usr/bin/env python
# -*- coding: utf-8 -*-

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import datetime
import psycopg2

from model_service import (
    download_repo_and_register_model,
    set_model_idle,
    set_model_serving,
    kill_vllm_process_by_port,
    launch_vllm
)

import subprocess



app = FastAPI()

# PostgreSQL 접속 정보 (DB 연결 함수로 관리)
DB_CONN_INFO = "dbname=malpyeong user=postgres password=!TeddySum host=127.0.0.1 port=5432"



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
        return {"msg": f"Downloaded to: {model_dir}"}
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

        # 2. 해당 포트에서 vllm 프로세스 종료
        kill_vllm_process_by_port(port)
        # 3. 새 모델 실행
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
    data = await request.json()
    user_id = data["user_id"]       # "team/model"
    gpu_id = data["gpu_id"]
    port = data["port"]             # 내부 포트 (5021~5024)
    external_port = data["external_port"]  # 외부 포트 (1111 또는 2222)

    try:
        team_name, model_name = user_id.split("/", 1)

        # 1. 외부 포트 연결 (iptables 사용)
        switch_external_port(external_port, port)

        # 2. DB 상태 업데이트
        set_model_serving(team_name, model_name, gpu_id)

        return {
            "msg": f"{user_id} → serving at GPU {gpu_id}, internal port {port}, external port {external_port}"
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
        port = 5021 + int(gpu_id) - 4
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
    data = await request.json()
    old = data["old"]  # "team/model"
    new = data["new"]  # "team/model"
    gpu_id = data["gpu_id"]
    port = data["port"]  # 내부 포트

    try:
        old_team, old_model = old.split("/", 1)
        new_team, new_model = new.split("/", 1)

        # 1. 기존 모델 idle 처리 + vllm 종료
        set_model_idle(old_team, old_model)
        kill_vllm_process_by_port(port)

        # 2. 새 모델 경로 조회 (다운로드 X)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT safetensors_path FROM models
            WHERE team_name = %s AND model_name = %s
        """, (new_team, new_model))
        result = cur.fetchone()
        cur.close()
        conn.close()

        if not result:
            raise ValueError(f"{new} 모델 경로를 DB에서 찾을 수 없습니다.")

        model_path = result[0]

        # 3. 새 모델 serve 실행
        launch_vllm(model_path, port, gpu_id)

        # 4. 상태 업데이트
        set_model_serving(new_team, new_model, gpu_id)

        return {
            "msg": f"{old} → idle, {new} → serving on GPU {gpu_id}, port {port}"
        }

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

        
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
