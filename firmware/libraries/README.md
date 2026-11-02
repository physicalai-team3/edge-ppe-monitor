# firmware/libraries

Arduino 스케치북의 `libraries` 폴더다. Arduino IDE의 **스케치북 위치를 `firmware/`로** 지정하면 IDE가 이 폴더의 라이브러리를 자동으로 찾는다. `fw` 컨테이너도 이 폴더를 쓴다(`--libraries libraries`).

## Edge Impulse 사람 검출 라이브러리 (팀원 1)

1. Edge Impulse에서 사람 검출 FOMO 공개 프로젝트를 Clone 하거나, 직접 `person` 라벨로 학습한다 (입력 96×96 grayscale 권장).
2. Deployment → **Arduino library** → 빌드(int8, EON) → zip 다운로드.
3. **이 폴더에 압축 해제하고 커밋**한다.

```
firmware/libraries/
└── Person_detection_-_FOMO_inferencing/   ← 예시. 실제 이름은 내보낸 zip 에 따라 다름
    ├── library.properties
    ├── examples/esp32/esp32_camera/
    └── src/Person_detection_-_FOMO_inferencing.h
```

압축 해제 후 `firmware/ppe_cam/person_sensor.cpp`의 `#include <...inferencing.h>`를 실제 헤더 이름으로 맞춘다.

## ArduinoJson (각자 설치, 커밋하지 않음)

Arduino IDE 라이브러리 관리자에서 **ArduinoJson 7.x** (Benoit Blanchon)를 설치한다. `fw` 컨테이너에는 이미 설치되어 있다.
