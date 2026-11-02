// 이 파일을 같은 폴더에 config.h 로 복사해서 값을 채운다. (config.h 는 git에 올라가지 않음)
// 새 설정 항목을 추가할 때는 이 example 파일에도 추가해서 커밋한다.
#pragma once

// ── 네트워크 (팀원 2) ─────────────────────────────────────
#define PPE_WIFI_SSID         "your-2.4GHz-ssid"   // _5G 가 붙은 이름 X
#define PPE_WIFI_PASS         "your-password"
#define PPE_GATEWAY_HOST      "192.168.0.20"       // Pi IP (Pi 에서 hostname -I). localhost X
#define PPE_GATEWAY_PORT      8000
#define PPE_DEVICE_KEY        "change-me"          // .env 의 DEVICE_API_KEY 와 같게
#define PPE_DEVICE_ID         "xiao-01"            // 팀원 1 보드 xiao-01, 팀원 2 보드 xiao-02 (^[a-z0-9-]{1,32}$)
#define PPE_FW_VERSION        "0.1.0"
#define PPE_HTTP_TIMEOUT_MS   5000                 // 시도당. 실패 시 500ms 후 1회 재시도 (docs/03-contracts.md §3.4)
#define PPE_HEARTBEAT_MS      30000

// ── 사람 센서 (팀원 1) ────────────────────────────────────
// 1: person_sensor_stub.cpp 사용 (BOOT 버튼을 누르고 있으면 사람 있음, 모델/카메라 불필요)
// 0: person_sensor.cpp 사용 (Edge Impulse 라이브러리가 firmware/libraries/ 에 있어야 함)
#define PPE_SENSOR_STUB       1
#define PPE_PERSON_THRESHOLD  0.5f                 // 이 점수 미만은 사람으로 치지 않음
#define PPE_JPEG_QUALITY      12                   // 0~63, 낮을수록 고화질·큰 파일 (VGA 60KB 목표, 512KB 상한)
#define PPE_SENSOR_LOG        1                    // 1: 프레임마다 시리얼에 결과 출력
#define PPE_SENSOR_PROFILE    0                    // 1: poll() 단계별 시간(디코드·리사이즈·추론) 출력
#define PPE_SENSOR_DECODE_DIV 4                    // 검출용 축소 디코드 1/N (4: 검출 안정 3.2fps [기본], 8: 빠르나 검출 약함 6.6fps)

// ── 트리거 (팀원 2) ───────────────────────────────────────
#define PPE_TRIGGER_FRAMES    2                    // 연속 N프레임 사람 → 촬영
#define PPE_RESEND_MS         5000                 // 사람이 계속 있으면 N ms 마다 재촬영
#define PPE_ABSENT_MS         2000                 // 마지막 검출 후 N ms → 대기 상태

// ── 보드 핀 (XIAO ESP32S3 Sense) ─────────────────────────
#define PPE_LED_PIN           21                   // 사용자 LED, active-low (LOW = 켜짐)
#define PPE_BOOT_PIN          0                    // BOOT 버튼 (누르면 LOW)
