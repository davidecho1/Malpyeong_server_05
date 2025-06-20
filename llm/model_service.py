#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import signal
import os
import datetime
import psycopg2
import shutil
import tempfile
import datetime
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


import docker

GPU_TO_CONTAINER = {
    4: "llm4",
    5: "llm5",
    6: "llm6",
    7: "llm7",
}

def launch_vllm(model_path: str, port: int, gpu_id: int):
    import time
    import docker

    try:
        # 1) 도커 소켓 연결 및 컨테이너 획득
        docker_client = docker.DockerClient(base_url="unix:///var/run/docker.sock")
        container = docker_client.containers.get(GPU_TO_CONTAINER[gpu_id])

        # 2) 기존에 실행 중인 vLLM 있으면 종료
        check_cmd = f"pgrep -f 'vllm serve.*--port {port}'"
        exit_code, _ = container.exec_run(check_cmd)
        if exit_code == 0:
            # 포트 충돌 방지용으로 기존 프로세스 kill
            container.exec_run(f"pkill -f 'vllm serve.*--port {port}'", detach=True)

        # 3) 새 vLLM 실행 명령 문자열
        cmd = (
            f"vllm serve {model_path} --port {port} --host 0.0.0.0 --device cuda"
        )
        print(f"[CMD 확인] {cmd!r}")

        # 4) 컨테이너 내부에서 vLLM 백그라운드 실행 (nohup + & + tty)
#        container.exec_run(
#            ["/bin/bash", "-c", cmd],
#            detach=True
#        )
         # → 수정: nohup + & 로 완전 독립 실행, tty=True 로 PTY 할당
#        bg_cmd = f"nohup {cmd} > /tmp/vllm_{port}.log 2>&1 &"
#        container.exec_run(
#            ["/bin/bash", "-c", bg_cmd],
#            detach=True,
#            tty=False
#        )
        container.exec_run(["/bin/bash", "-lc", cmd], detach=True)
        print(f"[launch_vllm] detached 모드로 컨테이너 `{GPU_TO_CONTAINER[gpu_id]}` 에서 실행: {cmd}")
        # 5) 프로세스가 잘 떠 있는지 확인
        time.sleep(2)
        proc_check = container.exec_run(check_cmd)
        if proc_check.exit_code != 0:
            raise RuntimeError("vLLM serve 프로세스가 기동되지 않았습니다.")
        print(f"[DEBUG] vLLM 프로세스 확인:\n{proc_check.output.decode().strip()}")

    except Exception as e:
        raise RuntimeError(f"컨테이너 내 vLLM 실행 실패: {e}")


def download_repo_and_register_model(hf_repo_id: str):
    """
    Hugging Face repo를 다운로드하여 전용 디렉토리에 저장하고
    models 테이블에 경로를 등록합니다.
    """
    # team_name/model_name 형태 파싱
    team_name, model_name = hf_repo_id.split("/", 1)

    # 말평 아레나 전용 모델 저장 경로
    arena_root = "/data/MALP_ARENA_MODELS"
    os.makedirs(arena_root, exist_ok=True)  # 경로가 없으면 생성

    model_id_clean = hf_repo_id.replace("/", "--")
    arena_model_path = os.path.join(arena_root, model_id_clean)

    try:
        # 1. 임시 디렉토리에 모델 다운로드 (캐시 X) → /tmp 대신 /data 사용
        with tempfile.TemporaryDirectory(dir="/data") as tmp_cache:
            snapshot_path = snapshot_download(hf_repo_id, cache_dir=tmp_cache)

            # 기존 경로가 있으면 제거 후 덮어쓰기
            if os.path.exists(arena_model_path):
                shutil.rmtree(arena_model_path)

            # 복사할 경로는 snapshot 디렉토리까지 포함
            # 예: snapshot_path = /data/.../models--org--name/snapshots/xxx
            shutil.copytree(snapshot_path, arena_model_path)

        print(f"[DEBUG] snapshot_path: {snapshot_path}")
        print(f"[DEBUG] arena_model_path: {arena_model_path}")

        # 2. DB 등록
        conn = psycopg2.connect(DB_CONN_INFO)
        cur = conn.cursor()

        # 기존 모델 삭제 시도
        cur.execute("DELETE FROM models WHERE team_name = %s AND model_name = %s", (team_name, model_name))

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            INSERT INTO models (
                team_name, model_name, safetensors_path,
                model_state, downloaded_at, updated_at
            )
            VALUES (%s, %s, %s, 'idle', %s, %s)
        """, (team_name, model_name, arena_model_path, now_str, now_str))

        conn.commit()
        cur.close()
        conn.close()

        print(f"[등록 완료] {hf_repo_id} → {arena_model_path}")
        return arena_model_path

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
