# 👤 팀원 3 — gateway: ESP32 사진 수신 → detector → 판정 → outbox → Supabase
# python:3.11-slim 은 amd64(노트북)·arm64(Pi 5) 모두 지원
FROM python:3.11-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
