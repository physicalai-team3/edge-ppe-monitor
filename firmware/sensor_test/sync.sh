#!/bin/sh
# ../ppe_cam 의 센서 파일을 이 테스트 스케치 폴더로 복사한다 (Arduino 는 다른 폴더의 .cpp 를 빌드하지 않음).
# 복사본은 .gitignore 에 있다. 원본(../ppe_cam)만 고치고, 고친 뒤에는 다시 실행한다.
#   Windows: Git Bash 에서  sh firmware/sensor_test/sync.sh
#   컴파일:  docker compose --profile firmware run --rm fw sh sensor_test/sync.sh --build
set -e
cd "$(dirname "$0")"
SRC=../ppe_cam

if [ ! -f "$SRC/config.h" ]; then
    echo "[sync] $SRC/config.h 가 없습니다. config.example.h 를 복사해 만들고 PPE_SENSOR_STUB 0 으로 설정하세요" >&2
    exit 1
fi

for f in person_sensor.cpp person_sensor.h person_result.h camera_pins.h config.h; do
    cp "$SRC/$f" "./$f"
done
echo "[sync] copied sensor files from $SRC"

if [ "$1" = "--build" ]; then
    cd ..
    arduino-cli compile \
        --fqbn "esp32:esp32:XIAO_ESP32S3:PSRAM=opi" \
        --libraries libraries \
        --output-dir build/sensor_test \
        sensor_test
    echo "[sync] build OK -> firmware/build/sensor_test/"
fi
