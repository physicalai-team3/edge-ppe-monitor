# 04. 4인 분업 계획

## 1. 역할 분담

> **눈 → 손 → 두뇌 → 관제실.** 눈이 사람을 보고, 손이 사진을 건네고, 두뇌가 보호구를 검사하고, 관제실이 위반을 기록·표시한다.

| | 👤 팀원 1 — **눈** (ESP32) | 👤 팀원 2 — **손** (ESP32) | 👤 팀원 3 — **두뇌** (Pi, 나) | 👤 팀원 4 — **관제실** (클라우드·웹) |
|---|---|---|---|---|
| 분리 단위 | 스케치 파일 `person_sensor.*` | 스케치 파일 `trigger.*`, `frame_uploader.*`, `ppe_cam.ino` | 컨테이너 `gateway`, `detector`, `cam-sim` | Supabase 프로젝트, 컨테이너 `web`, `cloud-seed` |
| 폴더/파일 | `firmware/ppe_cam/person_sensor.cpp`, `camera_pins.h`, `firmware/libraries/**` | `firmware/ppe_cam/` 나머지, `firmware/test/**`, `firmware/Dockerfile·build.sh·test.sh` | `pi/**` | `cloud/**`, `web/**` |
| 핵심 과제 | 카메라 초기화(XIAO 핀, PSRAM), Edge Impulse 사람 검출 FOMO 배포·이식, `poll()` 결과, VGA JPEG 촬영 | Wi-Fi·NTP, 트리거 상태 머신, HTTP POST(JPEG+헤더)·재시도, 응답 파싱 → LED, 하트비트 | 수신 API, YOLOv8 PPE ONNX 추론, 판정 규칙, 박스 그리기, outbox·Supabase 업로드, 쿨다운 | 테이블·RLS·Storage·Realtime 설정, 키 배포, 실시간 위반 대시보드, 통계, 장치 상태 |
| 계약 | [03 §2](03-contracts.md#2-esp32-내부-person_resulth--person_sensorh) **생산** | §2 소비, §3 **생산** | §3 소비, §4·§5 생산·소비, §6 **생산** | §6 **정의**(SQL) + 소비, §7 |
| 상대 없이 개발 | Edge Impulse `esp32_camera` 예제 → 시리얼 로그 `person=1 count=1 score=0.87 infer=180ms` | `PPE_SENSOR_STUB 1`: **BOOT 버튼 = 사람**, 고정 테스트 JPEG(`test_jpeg.h`) 전송 → 노트북에서 `--profile pi` + `DETECTOR_MODE=mock`으로 띄운 gateway | `cam-sim` + `DETECTOR_MODE=mock`, `CLOUD_ENABLED=false` | `cloud-seed`로 가짜 위반 INSERT → 웹 카드 확인 |
| 장비 | ESP32 1대 (주로 사용) | ESP32 1대 (1대뿐이면 아래 참고) | Raspberry Pi 5 | 노트북 |

**왜 이렇게 나눴나?**
- ESP32 2명: 팀원 1은 **"카메라와 모델"**만, 팀원 2는 **"네트워크와 언제 보낼지"**만 안다. 경계는 헤더 두 개(`person_result.h`, `person_sensor.h`)뿐이다.
- 팀원 3은 HTTP 요청 한 종류만 받고 Supabase에 한 종류만 쓴다. ESP32 코드도 웹 코드도 몰라도 된다.
- 팀원 4는 **DB 형식(SQL)의 주인**이다. 그래서 테이블을 먼저 만들어 팀원 3에게 키와 함께 넘겨주는 것이 오전 첫 번째 일이다.

**ESP32가 1대뿐이라면**: 오전(0:30–2:30)은 팀원 1이 보드를 쓰고, 팀원 2는 `trigger.cpp` + 단위 테스트(`fw` 컨테이너), `frame_uploader.cpp` 작성과 컴파일 확인까지 한다. 2:30 이후 팀원 2가 보드를 받아 stub로 실제 전송을 붙인다.

## 2. 타임라인 (하루)

| 시간 | 팀원 1 (눈) | 팀원 2 (손) | 팀원 3 (두뇌, Pi) | 팀원 4 (관제실) | 합류 |
|---|---|---|---|---|---|
| **0:00–0:30** | 함께: 문서 읽기, [03-contracts.md](03-contracts.md) 확정, 브랜치 생성, Pi IP·Supabase 키 공유 방법 정하기 | ← | ← | ← | ✅ **계약 동결** |
| 0:30–1:30 | Edge Impulse 사람 검출 FOMO 프로젝트 Clone → Arduino 라이브러리 → `firmware/libraries/`. IDE 설정 | IDE 설정, `fw` 이미지 빌드, `trigger.cpp` + `test.sh` 통과 | Pi에 Docker, `gateway` 수신 API + `detector` mock 모드, `cam-sim` → 응답 JSON 확인 | Supabase 프로젝트 생성, 마이그레이션 SQL 실행, **키 전달**(팀원 3: secret / 웹: publishable) | |
| 1:30–3:00 | 예제를 XIAO 핀으로 돌려 사람 검출 확인 → `person_sensor.cpp` 이식, VGA JPEG 촬영 | Wi-Fi·NTP, stub(BOOT 버튼) → 테스트 JPEG를 gateway에 POST, 응답 → LED | PPE ONNX 모델 준비·export, `detector` onnx 모드, `judge.py` + 테스트 | 웹: 최근 50건 목록, 서명 URL 사진, Realtime 구독. `cloud-seed`로 확인 | |
| **3:00–3:30** | **1차 통합**: ESP32(stub) → gateway(mock) → Supabase → 웹에 카드 | ← | ← | ← | ✅ **E2E 1차** |
| 3:30–5:00 | `PPE_SENSOR_STUB 0` 실제 모델 통합, 거리·조명 측정, 임계값 튜닝 | 재시도·타임아웃, 하트비트, 재접속(공유기 끄고 켜기) | outbox·재시도(인터넷 끊고 테스트), 쿨다운, 박스 그리기, 하트비트 → `devices` | 오늘 통계(종류별·장치별), 새 위반 알림(소리/토스트), 장치 온라인 표시 | |
| 5:00–6:00 | 팀원 2와 짝: 안전모 쓰고/벗고 실제 시나리오 | ← | 판정 임계값 튜닝, 추론 시간 측정 | 데모 화면 정리, README 실행법 보완 | |
| **6:00–7:00** | **2차 통합 + 데모 리허설** | ← | ← | ← | ✅ **데모** |

## 3. Git 협업 규칙

```
main ───────●───────────────●───────────────●   (0:30 계약, 3:00, 6:00 에만 merge)
           ╱│╲╲            ╱│╲╲
feat/esp32-vision ●──●     ●──●                 ← 팀원 1
feat/esp32-link    ●──●     ●──●                ← 팀원 2
feat/pi-gateway     ●──●──●──●──●               ← 팀원 3
feat/cloud-web       ●──●──●──●──●              ← 팀원 4
```

- **각자 자기 폴더/파일만 수정** (§1 표의 "폴더/파일" 행) → merge 충돌이 거의 없다.
- `.env`와 `firmware/ppe_cam/config.h`는 `.gitignore`에 있다. **절대 커밋하지 않는다.** 설정을 추가할 때는 `.env.example` / `config.example.h`에 추가한다.
- **Supabase secret 키는 채팅방에 붙여넣지 않는다.** 팀원 4가 팀원 3에게 직접(DM 등) 전달한다.
- `docs/03-contracts.md`, `shared/schemas/`, 계약 헤더(`person_result.h`, `person_sensor.h`), `cloud/supabase/migrations/` 수정은 `[contract] ...` 커밋 + 즉시 공유.
- `docker-compose.yml`은 자기 서비스 블록만 수정한다.

## 4. 각자 "완료" 기준

### 팀원 1 — 눈
- [ ] Edge Impulse 라이브러리가 `firmware/libraries/`에 커밋됨
- [ ] 부팅 로그에 PSRAM 인식, 카메라 초기화 성공
- [ ] 사람을 비추면 시리얼에 `person=1`, 없으면 `person=0`, 오검출 없음
- [ ] `poll()` 5fps 내외, `infer_ms` 기록
- [ ] `capture_jpeg()`이 VGA JPEG(60KB 이하)를 돌려주고 `release()` 후 메모리 누수 없음 (`ESP.getFreePsram()` 일정)
- [ ] 거리 1m / 2m / 3m 검출 여부 표

### 팀원 2 — 손
- [ ] `docker compose --profile firmware run --rm fw sh test.sh` 통과 (트리거 규칙)
- [ ] stub로 BOOT 버튼 → gateway 로그에 프레임 수신, 응답 `result`가 시리얼에 출력
- [ ] 사람이 계속 있으면 5초마다 재전송, 사라지면 멈춤
- [ ] Pi를 끄면 1회 재시도 후 포기, 보드가 멈추지 않음. Pi를 켜면 자동 복구
- [ ] `violation` 응답에 LED 3번 깜빡, Wi-Fi 끊김·전송 실패 시 1초 주기 깜빡
- [ ] 재시도 시 같은 `X-Frame-Seq`, 4xx는 재시도하지 않음 (gateway 로그로 확인)
- [ ] NTP 동기화 전에는 `X-Captured-At` 헤더를 보내지 않음

### 팀원 3 — 두뇌 (Pi)
- [ ] `curl`(03 §3.1)로 사진 POST → 200 + 응답 JSON이 스키마와 일치
- [ ] `detector` onnx 모드: 안전모 쓴 사진 `compliant`, 벗은 사진 `violation`
- [ ] `judge.py`, `dedup.py` 단위 테스트 통과 (`docker compose run --rm gateway pytest -q`)
- [ ] 에러 응답이 [03 §3.3](03-contracts.md#33-에러-응답) 표와 일치 (헤더 누락 → 422가 아니라 400 `missing_header`)
- [ ] 응답이 `shared/schemas/frame-response.schema.json`을 통과 (`duplicate`/`disabled`일 때 `violation_id: null`)
- [ ] 위반 시 Supabase Storage에 박스 그린 사진 + `violations` 행 1개
- [ ] 인터넷을 끊고 위반 3건 → 다시 연결하면 3건 모두 업로드, 중복 없음
- [ ] 같은 위반 30초 안 반복 시 `cloud:"duplicate"`

### 팀원 4 — 관제실
- [ ] 마이그레이션 SQL이 `cloud/supabase/migrations/`에 커밋되고 Supabase에 적용됨
- [ ] publishable 키로 `violations` insert가 **거부**됨 (RLS 확인)
- [ ] `cloud-seed` 실행 → 웹 새로고침 없이 카드가 추가됨 (Realtime)
- [ ] 카드에 사진·시각(한국 시간)·장치·위반 종류 표시, 오늘(KST 0시~) 위반 수 통계는 50건 피드와 별도 조회
- [ ] 새로고침·재구독 때 같은 위반 카드가 두 번 나오지 않음 (`id`로 중복 제거)
- [ ] (2차) 장치 온라인/오프라인 표시

## 5. 통합 체크리스트

### 1차 (3:00)
- [ ] ESP32(stub) BOOT 버튼 → gateway 로그 수신 → 응답 → ESP32 시리얼에 `result=...`
- [ ] `DETECTOR_MODE=mock`에서 위반 → Supabase 행 생성 → 웹 카드 표시
- [ ] 끝에서 끝까지 걸린 시간 측정 (버튼 → 웹 카드)

### 2차 (6:00)
- [ ] 실제 사람 검출(ESP32) + 실제 PPE 모델(Pi)
- [ ] 안전모 착용 → 웹에 아무것도 안 뜸 / 벗음 → 카드 1개 / 30초 안에 또 벗어도 카드 추가 안 됨
- [ ] Pi 인터넷 끊었다 연결 → 밀린 위반이 웹에 나타남

## 6. 데모 시나리오 (3분)

1. 웹 대시보드를 화면에 띄운다. 위반 0건.
2. 안전모·조끼를 착용한 사람이 카메라 앞에 선다 → ESP32 LED 1번, 웹 변화 없음 ("착용자는 기록하지 않는다").
3. 안전모를 벗는다 → 5초 안에 ESP32 LED 3번 → 웹에 빨간 박스 사진 카드 등장.
4. 조끼도 벗는다 → 새 카드(`no_helmet`, `no_vest`).
5. 비용 이야기: "오늘 하루 ESP32는 사람 있을 때만 N장 보냈고, 클라우드에는 위반 M장만 올라갔다" (gateway 로그 집계).
