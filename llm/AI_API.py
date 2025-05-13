#!/usr/bin/env python
# -*- coding: utf-8 -*-

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import datetime
import psycopg2

from model_service import (
    download_repo_and_register_model,
    set_model_idle,
    set_model_standby,
    set_model_serving
)


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
    user_id = data["user_id"]
    gpu_id = data["gpu_id"]
    port = data["port"]
    try:
        set_model_standby(user_id, gpu_id, port)
        return {"msg": f"{user_id} → standby at GPU {gpu_id}, port {port}"}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)
    
# 모델 서빙
@app.post("/models/serve")
async def serve_model(request: Request):
    data = await request.json()
    user_id = data["user_id"]
    gpu_id = data["gpu_id"]
    port = data["port"]
    try:
        set_model_serving(user_id, gpu_id, port)
        return {"msg": f"{user_id} → serving at GPU {gpu_id}, port {port}"}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)
    
# 모델 idle    
@app.post("/models/idle")
async def idle_model(request: Request):
    data = await request.json()
    user_id = data["user_id"]
    try:
        set_model_idle(user_id)
        return {"msg": f"{user_id} → idle"}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)
    
# 모델 스위치: 기존 serving → idle, 새 모델 → serving
@app.post("/models/switch")
async def switch_model(request: Request):
    data = await request.json()
    old_model = data["old"]
    new_model = data["new"]
    gpu_id = data["gpu_id"]
    port = data["port"]
    try:
        set_model_idle(old_model)
        set_model_serving(new_model, gpu_id, port)
        return {"msg": f"{old_model} → idle, {new_model} → serving"}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

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