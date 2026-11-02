# edge-ppe-monitor

**사람이 나타나면 찍고, 보호구를 안 썼을 때만 기록한다.**

XIAO ESP32S3 Sense가 사람을 감지해 사진을 찍고, Raspberry Pi 5가 딥러닝(YOLOv8)으로 **안전모·안전조끼 착용 여부**를 판별한다. **미착용 위반일 때만** 사진과 기록을 Supabase에 저장하고, 웹 대시보드에 실시간으로 뜬다.

```
[ESP32-S3] ──사진 1장(HTTP)──▶ [Raspberry Pi 5] ──위반만(HTTPS)──▶ [Supabase] ──실시간──▶ [웹 대시보드]
 사람 감지 + 촬영                안전모·조끼 판별                      사진 + 기록            위반 카드 표시
```

설계 문서: [docs/](docs/README.md) — 처음이라면 [01 아키텍처](docs/01-architecture.md) → [03 데이터 계약](docs/03-contracts.md) → [04 분업 계획](docs/04-team-plan.md) 순서로 읽는다.

## 1. 큰 흐름 — 어떻게 설계했나

> **"눈 → 손 → 두뇌 → 관제실"** 네 부분을 4명이 하나씩 맡고, 서로는 **약속한 데이터 형식**으로만 대화한다.

```
 👤 팀원 1 (눈)    👤 팀원 2 (손)          👤 팀원 3 (두뇌)                    👤 팀원 4 (관제실)
┌────────── ESP32 보드 ───────────┐   ┌──── Raspberry Pi 5 (Docker) ────┐   ┌──── Supabase + 웹 ────┐
│ 카메라 → 사람 있나? → 찰칵 → 전송 │──▶│ gateway ⇄ detector(YOLOv8)      │──▶│ DB·사진 저장 → 대시보드 │
└─────────────────────────────────┘   │ 판정 → 위반이면 업로드           │   └───────────────────────┘
                ◀── 판정 결과(LED) ────┘                                  │
```

한 장의 사진이 지나가는 길:

1. **감지 (ESP32)** — 작은 모델(Edge Impulse FOMO)로 "사람이 있나?"만 본다. 사람 없으면 아무것도 보내지 않는다.
2. **촬영·전송 (ESP32)** — 연속 2프레임 사람이 보이면 VGA 사진 1장을 찍어 Pi로 보낸다. 계속 있으면 5초마다 다시.
3. **판별 (Pi)** — YOLOv8 PPE 모델이 사람·안전모·조끼 박스를 찾고, 사람마다 "머리에 안전모? 몸통에 조끼?"를 확인한다.
4. **응답 (Pi → ESP32)** — 판정 결과를 바로 돌려줘 ESP32 LED로 현장에 경고한다.
5. **기록 (Pi → Supabase)** — **위반일 때만** 박스 그린 사진을 Storage에, 기록을 DB에 저장한다. 같은 위반은 30초에 한 번만.
6. **표시 (웹)** — Realtime으로 새 위반이 새로고침 없이 카드로 나타난다.

**왜 이렇게?** — 단계마다 데이터가 줄어드는 **3단 필터**다.

| 단계 | 버리는 것 | 효과 |
|---|---|---|
| ESP32 | 사람 없는 프레임 | 평소 전송량 0 |
| Pi | 보호구를 제대로 착용한 사진, 반복 위반 | 클라우드엔 "새 위반"만 |
| 클라우드 | — | 저장비·통신비 최소, 사람은 위반만 확인 |

ESP32는 작은 모델만 돌릴 수 있어 "사람 유무"까지만, 안전모·조끼처럼 작은 물체 판별은 연산이 넉넉한 Pi가 맡는다.

## 2. 컨테이너 분리

| 컨테이너 | 비유 | 하는 일 | 어디서 | 주인 |
|---|---|---|---|---|
| `gateway` | 🛂 검사관 | ESP32 사진 받기 → detector에 물어보기 → 판정 → 위반이면 업로드 | Pi | 팀원 3 |
| `detector` | 🔬 현미경 | YOLOv8 ONNX로 사람·안전모·조끼 박스 찾기 (내부 전용) | Pi | 팀원 3 |
| `web` | 🖥 관제 화면 | 대시보드 정적 파일 (nginx) | 노트북 | 팀원 4 |
| `cam-sim` | 🤖 대역 배우 | 보드 없이 진짜 ESP32와 같은 요청을 보냄 | Pi/노트북 | 팀원 3 |
| `cloud-seed` | 🤖 대역 배우 | Pi 없이 가짜 위반 1건을 Supabase에 올림 | 노트북 | 팀원 4 |
| `fw` | 🔧 공구 | 모두 같은 버전으로 펌웨어 컴파일·단위 테스트 | 노트북 | 팀원 2 |

ESP32 보드는 컨테이너가 아니다. 보드 안에서는 **파일**로 일을 나누고(팀원 1: `person_sensor.*`, 팀원 2: 나머지), 경계는 헤더 두 개다. Supabase도 컨테이너가 아니라 클라우드 프로젝트 하나다.

**나눈 기준**

1. **한 기능 = 한 컨테이너 = 한 주인.** 각자 자기 폴더만 수정해서 충돌이 없다.
2. **gateway와 detector를 나눈 이유.** 무거운 딥러닝(onnxruntime)과 가벼운 웹 처리를 분리했다. 모델을 바꾸거나 `DETECTOR_MODE=mock`으로 바꿔 끼워도 gateway는 그대로고, detector만 따로 테스트할 수 있다.
3. **어디서 도는지로 프로필 분리.** `docker-compose.yml` 하나에서 `--profile pi`(Pi), `--profile web`(노트북)처럼 골라 띄운다.
4. **남의 작업이 안 끝나도 개발할 수 있다.**

   | 없는 것 | 대신 쓰는 가짜 | 덕분에 |
   |---|---|---|
   | ESP32 보드 | `cam-sim` | 팀원 3이 보드 없이 Pi 개발 |
   | PPE 모델 | `DETECTOR_MODE=mock` | 팀원 3이 모델 없이 판정·업로드 개발 |
   | 사람 검출 모델 | BOOT 버튼 = 사람 (stub) | 팀원 2가 모델 없이 전송 개발 |
   | Pi | `cloud-seed` | 팀원 4가 Pi 없이 웹 개발 |
   | Supabase | `CLOUD_ENABLED=false` | 팀원 3이 클라우드 없이 판정 개발 |

## 3. 폴더 설계

**최상위 폴더 = 주인.** 공동 소유는 `docs/03-contracts.md`, `shared/`, 계약 파일뿐이다.

```
edge-ppe-monitor/
├── docs/                 설계 문서 (03-contracts.md 는 공동 소유)
├── shared/               [공동] 데이터 형식(JSON Schema) + 테스트 사진
├── firmware/             👤 팀원 1·2 — ESP32 (Arduino)
│   └── ppe_cam/
│       ├── person_result.h, person_sensor.h   [공동] 두 사람의 경계
│       ├── person_sensor.cpp, camera_pins.h   팀원 1: 카메라 + 사람 검출 + 촬영
│       └── trigger.*, frame_uploader.*, ppe_cam.ino   팀원 2: 언제 보낼지 + Wi-Fi·HTTP
├── pi/                   👤 팀원 3 — Raspberry Pi 5
│   ├── gateway/          받기·판정·outbox·업로드
│   ├── detector/         YOLOv8 ONNX 추론 (models/ 에 ppe.onnx)
│   └── cam-sim/          가짜 ESP32
├── cloud/                👤 팀원 4 — Supabase
│   ├── supabase/migrations/   [공동] 테이블·권한·Storage SQL
│   └── seed/             가짜 Pi
├── web/                  👤 팀원 4 — 대시보드
├── docker-compose.yml    프로필: pi / sim / web / seed / firmware
└── .env.example          설정 템플릿 (.env 는 커밋 금지)
```

- **계약이 먼저, 구현은 나중.** 구간마다 주고받는 데이터를 [03-contracts.md](docs/03-contracts.md)에 먼저 정하고, `shared/schemas/`(JSON), 헤더(C), SQL로 고정했다.
- **비밀은 폴더 밖.** Wi-Fi 비밀번호(`config.h`), Supabase 키(`.env`), 모델 가중치(`*.onnx`)는 `.gitignore`. 예시 파일(`*.example*`)만 커밋한다.

## 4. 주고받는 데이터 (요약)

| 구간 | 방식 | 내용 |
|---|---|---|
| ESP32 내부 | C 구조체 | `person_result_t` (사람 유무·수·점수), `jpeg_frame_t` (사진) |
| ESP32 → Pi | `POST /api/v1/frames` | body = JPEG, 헤더 = 장치 ID·키·순번·사람 수 |
| Pi → ESP32 | JSON 응답 | `result`(violation/compliant/no_person), `violations`, `cloud` |
| gateway → detector | `POST /v1/detect` | JPEG → 박스 목록 (`person`, `helmet`, `no_helmet`, `vest`, `no_vest`) |
| Pi → Supabase | Storage + DB | 박스 그린 사진 + `violations` 1행 (위반만) |
| Supabase → 웹 | supabase-js | 최근 50건 조회 + Realtime INSERT 구독 + 서명 URL |

자세한 필드: [docs/03-contracts.md](docs/03-contracts.md)

## 5. 빠른 시작

```bash
cp .env.example .env                                    # 값 채우기

# 팀원 3 — Pi
docker compose --profile pi up -d --build
curl http://localhost:8000/healthz
docker compose --profile pi --profile sim up --build    # 가짜 ESP32 와 함께

# 팀원 4 — 웹 / 클라우드
docker compose --profile web up --build                 # http://localhost:8080
docker compose --profile seed run --rm cloud-seed       # 가짜 위반 1건

# 팀원 1·2 — 펌웨어
docker compose --profile firmware run --rm fw           # 컴파일 확인
docker compose --profile firmware run --rm fw sh test.sh
```

자세한 실행·네트워크 체크리스트: [docs/02-containers.md](docs/02-containers.md)
