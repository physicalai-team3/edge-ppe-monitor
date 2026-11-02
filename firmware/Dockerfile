# 펌웨어 컴파일 확인용 도구 컨테이너 (업로드는 노트북의 Arduino IDE 에서)
# 팀 전원이 같은 버전으로 컴파일되는지 확인한다. 버전을 바꿀 때는 docs/02-containers.md 도 같이 수정.
FROM debian:bookworm-slim

ARG ARDUINO_CLI_VERSION=1.1.1
ARG ESP32_CORE_VERSION=2.0.17
ARG ARDUINOJSON_VERSION=7.2.1

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl python3 python3-serial g++ \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh \
    | BINDIR=/usr/local/bin sh -s ${ARDUINO_CLI_VERSION}

RUN arduino-cli config init --additional-urls https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json \
 && arduino-cli core update-index \
 && arduino-cli core install esp32:esp32@${ESP32_CORE_VERSION} \
 && arduino-cli lib install "ArduinoJson@${ARDUINOJSON_VERSION}"

WORKDIR /firmware
