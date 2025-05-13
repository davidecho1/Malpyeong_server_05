#!/usr/bin/env python
# -*- coding: utf-8 -*-

import psycopg2

# DB 접속 정보 
DB_CONN_INFO = "dbname=malpyeong user=postgres password=!TeddySum host=127.0.0.1 port=5432"

def init_db():
    conn = psycopg2.connect(DB_CONN_INFO)
    cur = conn.cursor()

    # 기존 테이블 삭제 (종속관계 포함)
    cur.execute("DROP TABLE IF EXISTS evaluations CASCADE")
    cur.execute("DROP TABLE IF EXISTS models CASCADE")
    cur.execute("DROP TABLE IF EXISTS users CASCADE")

    # 1. users 테이블: 평가자, 일반 유저 등 계정 관리
    cur.execute("""
        CREATE TABLE users (
            user_id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(20) DEFAULT 'user'
        )
    """)

    # 2. models 테이블: 팀(또는 모델 제출자)별 모델 정보
    cur.execute("""
        CREATE TABLE models (
            model_id SERIAL PRIMARY KEY,
            team_name VARCHAR(100) NOT NULL,
            model_name VARCHAR(100) NOT NULL,
            safetensors_path TEXT,
            gpu_id INTEGER,
            model_state VARCHAR(20) DEFAULT 'idle',
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 3. evaluations 테이블: 평가 기록 저장 (평가자는 users 테이블 참조)
    cur.execute("""
        CREATE TABLE evaluations (
            evaluation_id SERIAL PRIMARY KEY,
            a_model_id INTEGER NOT NULL REFERENCES models(model_id),
            b_model_id INTEGER NOT NULL REFERENCES models(model_id),
            prompt TEXT,
            a_model_answer TEXT,
            b_model_answer TEXT,
            evaluation VARCHAR(20),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_id VARCHAR(50),
            evaluator_id INTEGER NOT NULL REFERENCES users(user_id),
            CONSTRAINT check_different_models CHECK (a_model_id <> b_model_id)
        )
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("DB 초기화 완료.")

if __name__ == "__main__":
    init_db()
