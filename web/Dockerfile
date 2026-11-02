# 👤 팀원 4 — 대시보드 정적 파일 (nginx). 시작할 때 환경 변수로 config.js 를 만든다
FROM nginx:1.27-alpine

COPY public/ /usr/share/nginx/html/
COPY 40-write-config.sh /docker-entrypoint.d/40-write-config.sh
RUN chmod +x /docker-entrypoint.d/40-write-config.sh
