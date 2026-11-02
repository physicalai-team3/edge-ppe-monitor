#!/bin/sh
# nginx 공식 이미지가 시작 전에 실행한다. 브라우저에 노출해도 되는 값만 넣는다 (secret 키 금지)
set -e
cat > /usr/share/nginx/html/config.js <<EOF
window.PPE_CONFIG = {
  SUPABASE_URL: "${SUPABASE_URL}",
  SUPABASE_PUBLISHABLE_KEY: "${SUPABASE_PUBLISHABLE_KEY}",
  SUPABASE_BUCKET: "${SUPABASE_BUCKET:-violation-images}"
};
EOF
echo "[web] config.js written (url=${SUPABASE_URL})"
