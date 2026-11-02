# 👤 팀원 4 — 가짜 Pi: 계약 형식의 위반을 Supabase 에 업로드 (Pi 없이 웹 개발)
# 시나리오: docker compose --profile seed run --rm cloud-seed python seed.py <one|types|burst|retry|late|edges|noimage|devices|live|clean>
FROM python:3.11-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY seed.py test_seed.py ./

CMD ["python", "seed.py"]
