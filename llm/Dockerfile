FROM nvidia/cuda:12.2.0-runtime-ubuntu20.04

# 시스템 기본 패키지 설치
RUN apt-get update && apt-get install -y \
    python3 python3-pip git curl lsof \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && pip install --upgrade pip

# 작업 디렉토리 설정
WORKDIR /app

# 로컬 코드 및 requirements 복사
COPY . .

# 의존성 설치
RUN pip install -r requirements.txt

# vLLM Flask/serve API 실행
CMD ["python", "main.py"]
