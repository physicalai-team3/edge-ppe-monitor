# 01. 아키텍처

## 1. 목표

공사장·공장 입구에 카메라를 달아 두고,

1. 사람이 나타나면 사진을 찍는다. (ESP32-S3)
2. 사진 속 사람마다 **안전모**와 **안전조끼**를 착용했는지 판정한다. (Raspberry Pi 5)
3. **미착용 위반일 때만** 사진과 기록을 클라우드에 실시간으로 남긴다. (Supabase)
4. 관리자는 웹 대시보드에서 위반을 실시간으로 본다. (Web)

### 기존 방식과 무엇이 다른가

| | 기존 CCTV | 이 프로젝트 |
|---|---|---|
| 감시 | 사람이 24시간 화면을 본다 | 엣지 단말이 1차 판단, 위반만 알림 |
| 전송 | 모든 영상을 서버로 상시 전송 | 사람이 있을 때만 사진 1장 → 위반일 때만 클라우드 |
| 비용 | 서버·통신비 큼 | 클라우드에는 위반 사진 몇 장뿐 |

## 2. 전체 구조

```
                       같은 공유기 (2.4GHz Wi-Fi)                                         인터넷
 ┌─────────────── XIAO ESP32S3 Sense ───────────────┐          ┌──────────── Raspberry Pi 5 ─────────────┐        ┌──────────── Supabase ───────────┐
 │                                                  │          │  docker compose --profile pi            │        │                                  │
 │  [person_sensor]  ──person_result_t──▶ [trigger] │          │                                          │        │  Storage  violation-images/      │
 │   카메라 + FOMO                         연속 감지 │  HTTP    │  ┌ gateway :8000 ────────────────────┐  │ HTTPS  │    <device>/<날짜>/<id>.jpg      │
 │   사람 검출, JPEG 촬영                   + 쿨다운 │  POST    │  │ 1 받기  /api/v1/frames            │  │ (위반  │                                  │
 │   👤 팀원 1 (눈)                            │     │  image/  │  │ 2 detector에 추론 요청 ──────────┐ │  │  만)   │  DB  public.violations           │
 │                                             ▼     │  jpeg    │  │ 3 판정 (사람별 안전모/조끼)       │ │  │ ─────▶ │      public.devices              │
 │                                    [frame_uploader]──────────▶│ │ 4 위반 → 박스 그린 사진          │ │  │        │                                  │
 │                                     Wi-Fi, HTTP, LED│ ◀────────│ │    → outbox(디스크) → 업로드 ────┼─┼──┼──────▶ │  Realtime (INSERT 알림)          │
 │                                     👤 팀원 2 (손)  │  JSON    │  └──────────────────────────────────┘ │  │        └───────────────┬──────────────────┘
 └──────────────────────────────────────────────────┘  판정결과  │  ┌ detector :9000 (내부 전용) ◀──────┘  │                        │ supabase-js
                                                                  │  │ YOLOv8 ONNX → 박스 목록           │                         ▼
 ┌ cam-sim (가짜 ESP32) ──────── 같은 HTTP ───────────────────────▶│  └──────────────────────────────────┘  │        ┌──────── web (nginx) ────────┐
 │ 👤 팀원 3이 보드 없이 테스트                                     │  👤 팀원 3 (두뇌)                         │        │ 실시간 위반 피드, 사진, 통계  │
 └─────────────────────────────────────────────────────────────────┘                                          │        │ 👤 팀원 4 (관제실)            │
                                                                                                               │        └──────────────────────────────┘
                                                                  ┌ cloud-seed (가짜 Pi) ── 위반 1건 INSERT ──┘  👤 팀원 4가 Pi 없이 테스트
```

## 3. 데이터 흐름 (한 장의 사진이 겪는 일)

| 단계 | 어디서 | 무엇을 | 데이터 크기 | 계약 |
|---|---|---|---|---|
| ① 감지 | ESP32 (팀원 1) | 96×96 흑백으로 줄여 FOMO 사람 검출, 5fps 내외 | 결과 구조체 수십 바이트 | [03 §2](03-contracts.md#2-esp32-내부-person_resulth--person_sensorh) |
| ② 트리거 | ESP32 (팀원 2) | 연속 2프레임 사람 → 촬영 결정. 계속 있으면 5초마다 다시 | — | [03 §2](03-contracts.md#2-esp32-내부-person_resulth--person_sensorh) |
| ③ 촬영 | ESP32 (팀원 1) | VGA(640×480) JPEG 1장 | 약 20~60KB | [03 §2](03-contracts.md#2-esp32-내부-person_resulth--person_sensorh) |
| ④ 전송 | ESP32 (팀원 2) → Pi | `POST /api/v1/frames` (body = JPEG, 메타는 헤더) | 약 20~60KB | [03 §3](03-contracts.md#3-esp32--pi-gateway-http) |
| ⑤ 추론 | Pi `detector` (팀원 3) | YOLOv8 PPE 모델 → 박스 목록 | JSON 1~2KB | [03 §4](03-contracts.md#4-gateway--detector-pi-내부-http) |
| ⑥ 판정 | Pi `gateway` (팀원 3) | 사람마다 안전모/조끼 확인 → `violation` / `compliant` / `no_person` | — | [03 §5](03-contracts.md#5-판정-규칙-gateway) |
| ⑦ 응답 | Pi → ESP32 | 판정 결과 JSON → ESP32 LED | 200B | [03 §3](03-contracts.md#3-esp32--pi-gateway-http) |
| ⑧ 저장 | Pi → Supabase | **위반만**: 박스 그린 사진 → Storage, 기록 → `violations` | 약 50KB + 1행 | [03 §6](03-contracts.md#6-pi--supabase-db--storage) |
| ⑨ 표시 | Supabase → 웹 | Realtime INSERT 알림 → 카드 추가, 사진은 서명 URL | — | [03 §7](03-contracts.md#7-supabase--web) |

**버려지는 것**: 사람 없는 프레임(ESP32에서), 보호구를 다 착용한 사진(Pi에서), 30초 안에 같은 장치에서 반복된 같은 위반(Pi에서). 클라우드에는 "새 위반"만 남는다.

## 4. 왜 이렇게 나눴나

### 4.1 ESP32는 "사람 있음"만 판단한다

- ESP32-S3에서 돌아가는 모델은 96×96 입력의 FOMO 정도가 한계다. 안전모·조끼처럼 작은 물체를 구분하기엔 해상도가 부족하다.
- 대신 "사람이 있나?"는 충분히 판단할 수 있다. 이것만으로 **사람 없는 시간의 전송을 0으로** 만든다.
- 판단에 쓰는 저해상도 이미지와 전송하는 고해상도 JPEG는 다르다. 검출은 작게, 전송은 크게.

### 4.2 Pi가 "보호구 착용"을 판단한다

- Raspberry Pi 5(4코어 Cortex-A76)에서 YOLOv8n ONNX(640 입력)는 CPU만으로 1장에 수백 ms 수준이다. 사진이 몇 초에 1장 오므로 충분하다.
- 판정 결과를 ESP32에 바로 돌려주므로 현장에서 LED(또는 부저)로 즉시 경고할 수 있다.

### 4.3 클라우드는 "위반 기록"만 받는다

- Storage에 사진, DB에 기록 한 줄. Realtime으로 웹이 바로 받는다.
- 웹은 서버 코드 없이 정적 페이지 + supabase-js만으로 만든다.

### 4.4 통신 방식 선택

| 구간 | 선택 | 이유 |
|---|---|---|
| ESP32 → Pi | **HTTP POST, body = JPEG 그대로** | 사진 전송에 가장 단순. multipart를 ESP32에서 조립할 필요 없이 메타데이터는 헤더(`X-*`)로 보낸다. 응답으로 판정을 바로 받는다 |
| gateway → detector | HTTP (compose 내부망) | 컨테이너 간 가장 단순한 경계. `detector`만 따로 `curl`로 테스트 가능 |
| Pi → Supabase | supabase-py (HTTPS REST) | Storage 업로드 + DB upsert. secret 키는 Pi에만 |
| Supabase → Web | supabase-js (REST + Realtime WebSocket) | 폴링 없이 INSERT 즉시 수신 |

> MQTT를 쓰지 않는 이유: 사진처럼 큰 바이너리를 보내고 **결과를 바로 돌려받는** 요청-응답 구조에는 HTTP가 맞다. 브로커 컨테이너도 하나 줄어든다.

## 5. 판정 개요

자세한 규칙은 [03 §5](03-contracts.md#5-판정-규칙-gateway). 요약하면:

```
detector 결과: person, helmet, vest, no_helmet, no_vest 박스들
        │
        ▼
사람 박스마다:
  머리 영역(위 35%)에 helmet 있음?   no_helmet 있으면 → ❌ 안전모
  몸통 영역(20~75%)에 vest 있음?     no_vest 있으면   → ❌ 조끼
        │
        ▼
사람 0명            → no_person
모두 착용           → compliant
한 명이라도 미착용  → violation  →  30초 쿨다운 확인  →  outbox → Supabase
```

## 6. 상태와 실패 처리

| 상황 | 동작 | 담당 |
|---|---|---|
| ESP32 Wi-Fi 끊김 | 재접속 시도, 그동안 촬영·전송 안 함 (사진을 보드에 쌓지 않는다) | 팀원 2 |
| Pi 응답 없음 / 5xx | 500ms 후 1회 재시도(같은 순번) 후 버림, 다음 트리거를 기다림. LED 1초 주기 깜빡임 | 팀원 2 |
| 카메라 초기화 실패 | `PS_CAMERA_INIT` 반환, 재부팅 루프 금지. 하트비트에 `last_error` | 팀원 1·2 |
| detector 준비 안 됨 / 4초 넘게 응답 없음 | gateway가 503 응답, ESP32는 1회 재시도 | 팀원 3 |
| 인터넷/Supabase 끊김 | outbox에 쌓아두고 백그라운드 재시도. ESP32 응답은 `cloud:"queued"`로 바로 감 | 팀원 3 |
| 같은 위반 반복 | 장치별·위반종류별 30초 쿨다운 → `cloud:"duplicate"` | 팀원 3 |
| 웹 새로고침 | Realtime 구독 후 최근 50건·오늘 통계 다시 조회, `id`로 중복 카드 제거 | 팀원 4 |

## 7. 폴더 구조

**폴더 = 주인.** 최상위 폴더 하나가 한 명(또는 ESP32는 두 명)의 영역이다. 공동 소유는 `shared/`, `docs/03-contracts.md`, 계약 헤더뿐이다.

```
edge-ppe-monitor/
├── README.md                     전원
├── docker-compose.yml            전원 (서비스 블록별 주인은 주석 참고)
├── .env.example                  전원 (각자 자기 섹션만 추가)
├── docs/                         전원. 03-contracts.md 는 공동 소유 [contract]
│
├── shared/                       공동 소유 [contract]
│   ├── schemas/                  JSON Schema: 구간별 데이터 형식
│   └── samples/                  테스트용 사진 (cam-sim, cloud-seed 가 사용)
│
├── firmware/                     👤 팀원 1·2 — ESP32 (Arduino)
│   ├── Dockerfile, build.sh      컴파일 확인용 fw 컨테이너 (팀원 2)
│   ├── libraries/                Edge Impulse 라이브러리 (팀원 1)
│   ├── test/                     trigger 단위 테스트 (팀원 2)
│   └── ppe_cam/                  스케치
│       ├── person_result.h       [contract] 결과 구조체
│       ├── person_sensor.h       [contract] 카메라·검출 API
│       ├── person_sensor.cpp     팀원 1: 카메라 + FOMO + JPEG 촬영
│       ├── camera_pins.h         팀원 1
│       ├── person_sensor_stub.cpp 팀원 2: BOOT 버튼 = 사람 (모델 없이 개발)
│       ├── trigger.h/.cpp        팀원 2: 연속 감지·쿨다운 판단
│       ├── frame_uploader.h/.cpp 팀원 2: Wi-Fi·HTTP 전송·하트비트
│       ├── ppe_cam.ino           팀원 2: setup/loop 조립
│       └── config.example.h      팀원 1·2 (각자 섹션)
│
├── pi/                           👤 팀원 3 — Raspberry Pi 5
│   ├── gateway/                  받기·판정·outbox·Supabase 업로드 (FastAPI)
│   ├── detector/                 YOLOv8 ONNX 추론 (FastAPI)
│   │   └── models/               ppe.onnx 를 여기에 (git 제외)
│   └── cam-sim/                  가짜 ESP32
│
├── cloud/                        👤 팀원 4 — Supabase
│   ├── supabase/migrations/      테이블·RLS·Storage·Realtime SQL
│   └── seed/                     가짜 Pi (위반 1건 INSERT)
│
└── web/                          👤 팀원 4 — 대시보드 (nginx 정적 페이지)
    └── public/                   index.html, app.js, style.css
```

## 8. 하드웨어 메모

| 장비 | 메모 |
|---|---|
| XIAO ESP32S3 Sense | 카메라 OV2640/OV3660, **PSRAM(OPI) 필수**. Arduino IDE: 보드 `XIAO_ESP32S3`, PSRAM `OPI PSRAM`. Wi-Fi는 **2.4GHz만** |
| Raspberry Pi 5 | 64bit Raspberry Pi OS + Docker. 고정 IP(또는 DHCP 예약) 권장 — ESP32 `config.h`에 이 IP를 넣는다 |
| 같은 네트워크 | ESP32와 Pi는 같은 공유기에. 학교/회사 Wi-Fi는 기기 간 통신(AP isolation)이 막혀 있을 수 있다 → 휴대폰 핫스팟 대안 |
