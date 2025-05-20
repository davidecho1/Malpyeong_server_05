#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import datetime
import psycopg2
from huggingface_hub import snapshot_download

DB_CONN_INFO = "dbname=malpyeong user=postgres password=!TeddySum host=192.168.242.203 port=5432"

def kill_vllm_process_by_port(port: int):
    """포트를 점유 중인 vllm 프로세스 종료"""
    try:
        result = subprocess.run(
            ["lsof", "-t", f"-i:{port}"], capture_output=True, text=True
        )
        pids = result.stdout.strip().split()
        for pid in pids:
            os.kill(int(pid), signal.SIGKILL)
        print(f"[kill_vllm] 종료된 PID들: {pids}")
    except Exception as e:
        raise RuntimeError(f"vLLM 종료 실패 (port={port}): {e}")

def launch_vllm(model_path: str, port: int, gpu_id: int):
    """새로운 모델로 vllm serve 실행"""
    try:
        cmd = [
            "vllm", "serve",
            "--model", model_path,
            "--port", str(port),
            "--device", str(gpu_id)
        ]
        subprocess.Popen(cmd, env=os.environ)
        print(f"[launch_vllm] 실행됨: {cmd}")
    except Exception as e:
        raise RuntimeError(f"vLLM 실행 실패: {e}")
        
def download_repo_and_register_model(hf_repo_id: str):
    """
    Hugging Face repo를 다운로드하고,
    디렉토리 경로를 models 테이블에 등록합니다.
    """
    # "team_name/model_name" 형식으로 받음
    team_name, model_name = hf_repo_id.split("/", 1)

    # 1. 모델 다운로드
    local_model_path = snapshot_download(repo_id=hf_repo_id)
    # 예: /root/.cache/huggingface/hub/models--deepseek-ai--deepseek-coder/snapshots/abc123/

    # 2. DB에 등록 (기존 동일 모델 있으면 삭제 후 삽입)
    try:
        conn = psycopg2.connect(DB_CONN_INFO)
        cur = conn.cursor()

        # 기존 모델 제거 (있으면)
        cur.execute("DELETE FROM models WHERE team_name = %s AND model_name = %s", (team_name, model_name))

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 3. 디렉토리 경로를 safetensors_path 필드에 저장
        cur.execute("""
            INSERT INTO models (
                team_name, model_name, safetensors_path,
                model_state, downloaded_at, updated_at
            )
            VALUES (%s, %s, %s, 'idle', %s, %s)
        """, (team_name, model_name, local_model_path, now_str, now_str))

        conn.commit()
        cur.close()
        conn.close()

        print(f"[등록 완료] {hf_repo_id} → {local_model_path}")
        return local_model_path

    except Exception as e:
        raise RuntimeError(f"DB 저장 중 오류: {e}")
        
def set_model_standby(team_name: str, model_name: str, gpu_id: int):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = psycopg2.connect(DB_CONN_INFO)
        cur = conn.cursor()
        cur.execute("""
            UPDATE models
            SET model_state = 'standby', gpu_id = %s, updated_at = %s
            WHERE team_name = %s AND model_name = %s
        """, (gpu_id, now_str, team_name, model_name))
        conn.commit()
        cur.close()
        conn.close()
        print(f"[set_model_standby] team_name={team_name}/{model_name}, gpu={gpu_id}, state=standby")
    except Exception as e:
        raise RuntimeError(f"set_model_standby 오류: {e}")

def set_model_serving(team_name: str, model_name: str, gpu_id: int):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = psycopg2.connect(DB_CONN_INFO)
        cur = conn.cursor()
        cur.execute("""
            UPDATE models
            SET model_state = 'serving', gpu_id = %s, updated_at = %s
            WHERE team_name = %s AND model_name = %s
        """, (gpu_id, now_str, team_name, model_name))
        conn.commit()
        cur.close()
        conn.close()
        print(f"[set_model_serving] team_name={team_name}/{model_name}, gpu={gpu_id}, state=serving")
    except Exception as e:
        raise RuntimeError(f"set_model_serving 오류: {e}")

def set_model_idle(team_name: str, model_name: str):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = psycopg2.connect(DB_CONN_INFO)
        cur = conn.cursor()
        cur.execute("""
            UPDATE models
            SET model_state = 'idle', gpu_id = NULL, updated_at = %s
            WHERE team_name = %s AND model_name = %s
        """, (now_str, team_name, model_name))
        conn.commit()
        cur.close()
        conn.close()
        print(f"[set_model_idle] team_name={team_name}/{model_name}, state=idle")
    except Exception as e:
        raise RuntimeError(f"set_model_idle 오류: {e}")

if __name__ == "__main__":
    # 테스트: 모델 카드 예시 (Hugging Face repo 형식)
    test_repo = "KYMEKAdavide/mnist_safetensors"
    download_repo_and_save_safetensors(test_repo)
