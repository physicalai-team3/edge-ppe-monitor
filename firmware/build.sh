#!/bin/sh
# 컨테이너 안에서 스케치를 컴파일한다:  docker compose --profile firmware run --rm fw
# 추가 옵션은 그대로 전달된다 (예: ... run --rm fw sh build.sh --verbose)
set -e
cd /firmware

if [ ! -f ppe_cam/config.h ]; then
    echo "[build] ppe_cam/config.h 가 없어 config.example.h 로 만듭니다 (Wi-Fi 값은 직접 채우세요)"
    cp ppe_cam/config.example.h ppe_cam/config.h
fi

# 보드 XIAO_ESP32S3 + OPI PSRAM (Arduino IDE 의 도구 메뉴와 같은 설정)
FQBN="esp32:esp32:XIAO_ESP32S3:PSRAM=opi"

arduino-cli compile \
    --fqbn "$FQBN" \
    --libraries libraries \
    --output-dir build \
    ppe_cam "$@"

echo "[build] OK -> firmware/build/"
