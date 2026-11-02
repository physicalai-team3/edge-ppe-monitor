# 👤 팀원 3 — 가짜 ESP32: shared/samples/*.jpg 를 진짜 ESP32 와 같은 형식으로 gateway 에 POST
FROM python:3.11-slim

WORKDIR /srv
RUN pip install --no-cache-dir httpx==0.28.1 pillow==11.0.0
COPY sim.py .

CMD ["python", "sim.py"]
