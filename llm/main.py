import uvicorn
from AI_API import app
from scheduler_day import start_scheduler
import os

def main():
    # 컨테이너 이름에서 GPU 번호 추출
    container_name = os.environ.get("CONTAINER_NAME", "llm0")
    gpu_id = int(container_name[-1]) if container_name[-1].isdigit() else 0

    GPU_PORT_MAP = {
        0: 5021,
        1: 5022,
        2: 5023,
        3: 5024
    }

    port = GPU_PORT_MAP[gpu_id]

    # 스케줄러 실행
    csv_path = os.environ.get("SCHEDULE_CSV", "../schedule/schedule(day).csv")
    start_scheduler(GPU_PORT_MAP, csv_path)

    print(f"[main] Starting FastAPI server on port {port} for GPU {gpu_id} (container: {container_name})...")

    # FastAPI 앱 실행
    uvicorn.run(app, host="0.0.0.0", port=5020, reload=False)

if __name__ == "__main__":
    main()
