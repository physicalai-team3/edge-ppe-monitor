# 👤 팀원 3 — detector: YOLOv8 PPE ONNX 추론 (CPU)
# onnxruntime 은 aarch64(Pi 5) 휠을 제공한다
FROM python:3.11-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 9000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
