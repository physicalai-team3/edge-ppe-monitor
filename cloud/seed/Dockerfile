# 👤 팀원 4 — 가짜 Pi: 샘플 위반 1건을 Supabase 에 업로드 (Pi 없이 웹 개발)
FROM python:3.11-slim

WORKDIR /srv
RUN pip install --no-cache-dir supabase==2.10.0 pillow==11.0.0
COPY seed.py .

CMD ["python", "seed.py"]
