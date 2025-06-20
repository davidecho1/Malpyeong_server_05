FROM nvidia/cuda:11.8.0-runtime-ubuntu20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=1

# 기본 패키지 설치
RUN apt-get update && apt-get install -y \
    python3 python3-pip git curl lsof iptables \
    && apt-get clean\
    && ln -s /usr/bin/python3 /usr/bin/python \
    && pip install --upgrade pip \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 코드 및 requirements 복사
COPY . .

# Python 의존성 설치
RUN pip install -r requirements.txt

# FastAPI + 스케줄러 실행
CMD ["python", "api_main.py"]
CMD ["tail", "-f", "/dev/null"]
