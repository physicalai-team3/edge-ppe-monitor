# pi/detector/models

`ppe.onnx`를 이 폴더에 둔다. **가중치 파일은 git에 올리지 않는다** (`.gitignore`). 팀원 3이 USB/드라이브로 Pi에 복사한다.

## 모델 준비 (팀원 3)

1. 안전모·조끼 클래스가 있는 **이미 학습된** YOLOv8 가중치를 받는다 (기본).
   - 예: Roboflow "Construction Site Safety" 류 데이터셋(Hardhat, NO-Hardhat, Safety Vest, NO-Safety Vest, Person …)으로 학습한 `yolov8n` 가중치
   - 노트북에 GPU가 없으므로 **노트북 CPU에서 학습하지 않는다** (수 시간 걸림). 추론은 Pi 5 CPU 기준이라 `n` 크기 모델만 쓴다.
   - 직접 학습이 꼭 필요하면 **Colab 등 GPU 환경**에서: `yolo detect train data=data.yaml model=yolov8n.pt imgsz=640 epochs=50` → `best.pt`만 받아온다
2. ONNX로 내보내기 (노트북 CPU로 충분, 1분 이내):

   ```bash
   pip install ultralytics
   yolo export model=best.pt format=onnx imgsz=640 opset=12 simplify=True
   ```

3. `best.onnx` → `pi/detector/models/ppe.onnx`로 복사.
4. 클래스 이름이 다르면 `pi/detector/app/labels.yaml`의 `model_classes`, `map`을 고친다.
5. 확인: `docker compose --profile pi up -d --build` → `docker compose logs detector`에서 모델 로드 로그, `curl http://localhost:8000/healthz`의 `detector`가 `ready`

모델이 아직 없으면 `.env`에 `DETECTOR_MODE=mock`.

## 기록 (측정 후 채우기)

| 모델 | 입력 | Pi 5 추론 시간 | 비고 |
|---|---|---|---|
| | 640 | ms | |
