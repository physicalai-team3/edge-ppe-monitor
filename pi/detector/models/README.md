# pi/detector/models

`ppe.onnx`를 이 폴더에 둔다. **가중치 파일은 git에 올리지 않는다** (`.gitignore`). 팀원 3이 `scp`/USB로 Pi에 복사한다.

## 모델 선택

| 항목 | 선택 | 이유 |
|---|---|---|
| 모델 | **YOLOv8n** (가장 작은 크기) | Pi 5는 GPU 없이 CPU로만 추론. n 크기 640 입력이 1장에 수백 ms → gateway 4초 제한 안에 충분 |
| 데이터셋 | Roboflow **Construction Site Safety v30** (CC BY 4.0) | `Person` + 착용(`Hardhat`, `Safety Vest`) + **미착용(`NO-Hardhat`, `NO-Safety Vest`)** 클래스가 모두 있음. 미착용을 직접 검출하므로 위반 근거가 확실 |
| 형식 | **ONNX** | Pi에 PyTorch·ultralytics 없이 `onnxruntime`만으로 실행. 같은 파일이 노트북(amd64)·Pi(arm64)에서 동작 |

v30은 25 클래스(차량·장비 포함)지만, `labels.yaml`의 `map`에 있는 5개만 쓰고 나머지는 detector가 버린다.

## 왜 Google Colab에서 학습하나

딥러닝 학습은 수많은 행렬 계산을 수천 번 반복하는 작업이라 **GPU**가 있어야 현실적인 시간에 끝난다.

| 어디서 | 50 epoch 학습 시간 (약 3,000장, yolov8n) | 비고 |
|---|---|---|
| 팀 노트북 (CPU만) | 수 시간 ~ 하루 | 그동안 노트북을 다른 일에 못 씀 |
| Raspberry Pi 5 (CPU만) | 사실상 불가 | 메모리·속도 모두 부족. Pi는 **추론 전용** |
| **Google Colab (무료 T4 GPU)** | **약 30~60분** | 브라우저만 있으면 됨, 설치 불필요, 무료 |

- **학습(train)은 한 번, 추론(inference)은 매번.** 학습은 무거워서 GPU가 필요하지만, 학습이 끝난 모델로 사진 1장을 판별하는 추론은 가벼워서 Pi CPU로 충분하다.
- 그래서 **Colab(GPU)에서 학습 → ONNX로 변환 → Pi(CPU)에서 추론**으로 역할을 나눈다.
- 무료 Colab은 오래 방치하면 세션이 끊길 수 있으므로 결과를 **구글 드라이브에 저장**하고, 끊기면 `last.pt`에서 이어서 학습한다.

## 모델 준비 순서 (팀원 3)

1. **데이터셋**: Roboflow Universe → "Construction Site Safety" (Roboflow Universe Projects) → Download Dataset → 형식 **YOLOv8** → "Show download code" 복사. `api_key`는 공유 금지.
2. **Colab** (런타임 유형 **T4 GPU**):

   ```python
   from google.colab import drive; drive.mount('/content/drive')
   !pip install -q ultralytics roboflow
   # (Roboflow 다운로드 코드 붙여넣기 → dataset)
   !yolo detect train data={dataset.location}/data.yaml model=yolov8n.pt imgsz=640 epochs=50 batch=32 project=/content/drive/MyDrive/ppe name=yolov8n
   !yolo export model=/content/drive/MyDrive/ppe/yolov8n/weights/best.pt format=onnx imgsz=640 opset=12 simplify=True
   ```

   끊기면: `!yolo detect train resume model=/content/drive/MyDrive/ppe/yolov8n/weights/last.pt`
3. **검증**: ONNX 출력 모양이 `[1, 4+클래스 수, 8400]` (v30이면 `[1, 29, 8400]`)인지 확인.
4. `best.onnx` → `pi/detector/models/ppe.onnx`로 이름 바꿔 복사. Pi로는:

   ```powershell
   scp pi\detector\models\ppe.onnx <user>@<Pi IP>:~/edge-ppe-monitor/pi/detector/models/
   ```

5. 데이터셋 버전을 바꾸면 `data.yaml`의 `names` 순서대로 `pi/detector/app/labels.yaml`의 `model_classes`를 고친다 (ONNX 메타데이터에 names가 있으면 그걸 우선 사용).
6. 확인: `.env`에 `DETECTOR_MODE=onnx` → `docker compose --profile pi up -d --build` → `docker compose logs detector`에서 모델 로드 로그, `curl http://localhost:8000/healthz`의 `detector`가 `ready`

모델이 아직 없거나 `OnnxDetector`가 구현 전이면 `.env`에 `DETECTOR_MODE=mock`.

## 기록 (측정 후 채우기)

| 모델 | 데이터셋 | mAP50 (all / NO-Hardhat / NO-Safety Vest) | 입력 | Pi 5 추론 시간 | 비고 |
|---|---|---|---|---|---|
| **yolov8n (사용 중)** | Construction Site Safety v30, 50 epoch | 0.577 / 0.583 / 0.592 | 640 | 약 174ms (bus.jpg, 2~5번째 평균) | Colab T4. 5개 클래스 평균 0.681. 테스트 사진 25장 19/25, 노트북 CPU 57ms |
| yolov8s | 같음, 80 epoch (22에서 최고 → 42에서 조기 종료) | 0.586 / 0.598 / 0.637 | 640 | — | 5개 평균 0.687. 정밀도↑ 재현율↓. 테스트 사진 16/25, 노트북 CPU 160ms → **채택 안 함** |

테스트 사진 25장: 위키미디어 공용 사진(착용 9장, 위반 16장), 판정 규칙 D안(03 §5.2), `CONF_THRESHOLD` 0.2~0.4를 바꿔 봐도 n 0.4가 가장 좋았다.
