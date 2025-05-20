import subprocess
import time
import psycopg2

# PostgreSQL 접속 정보 (실제 환경에 맞게 수정하세요)
PG_HOST = "192.168.242.203"
PG_PORT = "5432"
PG_USER = "postgres"
PG_PASSWORD = "!TeddySum"

def is_postgresql_running():
    """PostgreSQL 서버에 접속이 가능한지 확인합니다."""
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user=PG_USER,
            password=PG_PASSWORD,
            host=PG_HOST,
            port=PG_PORT
        )
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False

def start_postgresql():
    """
    PostgreSQL 서비스를 systemctl을 통해 시작합니다.
    이 함수는 sudo 권한이 필요하며, 환경에 따라 서비스명이 다를 수 있습니다.
    """
    try:
        print("PostgreSQL 서버를 시작합니다...")
        subprocess.run(["sudo", "systemctl", "start", "postgresql"], check=True)
        # 서비스가 완전히 기동될 수 있도록 잠시 대기합니다.
        time.sleep(5)
    except Exception as e:
        print("PostgreSQL 서비스 시작에 실패했습니다:", e)

def create_database(dbname):
    """
    기본 'postgres' 데이터베이스에 연결하여 원하는 데이터베이스(dbname)를 생성합니다.
    이미 존재하면 메시지만 출력합니다.
    """
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user=PG_USER,
            password=PG_PASSWORD,
            host=PG_HOST,
            port=PG_PORT
        )
        conn.autocommit = True  # 데이터베이스 생성은 autocommit 모드에서 처리해야 합니다.
        cur = conn.cursor()
        # 데이터베이스 존재 여부 확인
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        if cur.fetchone():
            print(f"'{dbname}' 데이터베이스는 이미 존재합니다.")
        else:
            cur.execute(f"CREATE DATABASE {dbname};")
            print(f"'{dbname}' 데이터베이스가 성공적으로 생성되었습니다.")
        cur.close()
        conn.close()
    except Exception as e:
        print("데이터베이스 생성 중 오류 발생:", e)

def init_db():
    """
    'malpyeong' 데이터베이스에 접속하여 테이블 구조(users, models, evaluations)를 초기화합니다.
    
    - users 테이블: 평가자 및 일반 유저 관리
    - models 테이블: 팀(모델 제출자)별 모델 정보 저장
    - evaluations 테이블: 평가 기록 저장 (users 테이블을 참조)
    
    기존 테이블이 있다면 DROP 후 재생성합니다.
    """
    DB_CONN_INFO = f"dbname=malpyeong user={PG_USER} password={PG_PASSWORD} host={PG_HOST} port={PG_PORT}"
    try:
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
    except Exception as e:
        print("DB 초기화 중 오류 발생:", e)

if __name__ == "__main__":
    # PostgreSQL 실행 여부 확인
    if not is_postgresql_running():
        print("PostgreSQL 서버가 실행 중이 아닙니다. 시작을 시도합니다.")
        start_postgresql()

    # 다시 실행 여부 확인
    if is_postgresql_running():
        # 'malpyeong' 데이터베이스가 없으면 생성
        create_database("malpyeong")
        # 데이터베이스 테이블 구조 초기화 (users, models, evaluations)
        init_db()
    else:
        print("PostgreSQL 서버에 연결할 수 없습니다. DB 생성을 진행할 수 없습니다.")
