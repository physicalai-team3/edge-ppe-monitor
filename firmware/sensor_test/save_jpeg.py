"""sensor_test 스케치의 'd' 명령으로 덤프한 JPEG 을 시리얼에서 받아 파일로 저장한다.

    pip install pyserial
    python save_jpeg.py COM5            # 1장 → capture_YYYYmmdd_HHMMSS.jpg
    python save_jpeg.py COM5 -n 5       # 5장

Arduino IDE 시리얼 모니터는 닫고 실행한다 (포트를 동시에 열 수 없음).
"""
import argparse
import base64
import datetime
import sys
import time

import serial


def grab_one(port: serial.Serial, timeout_s: float = 30.0) -> bytes:
    port.reset_input_buffer()
    port.write(b"d")
    deadline = time.monotonic() + timeout_s
    lines: list[str] = []
    started = False
    while time.monotonic() < deadline:
        raw = port.readline()
        if not raw:
            continue
        line = raw.decode("ascii", errors="ignore").strip()
        if line.startswith("---JPEG BEGIN"):
            started = True
            continue
        if line == "---JPEG END---":
            return base64.b64decode("".join(lines))
        if line == "capture failed":
            raise RuntimeError("보드에서 촬영 실패")
        if started:
            lines.append(line)
    raise TimeoutError("JPEG 덤프를 받지 못했습니다 (포트·보드 확인)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("port", help="예: COM5, /dev/ttyACM0")
    ap.add_argument("-n", type=int, default=1, help="저장할 장수")
    ap.add_argument("--baud", type=int, default=115200)
    args = ap.parse_args()

    with serial.Serial(args.port, args.baud, timeout=1) as port:
        time.sleep(0.5)
        for _ in range(args.n):
            data = grab_one(port)
            ok = data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"
            name = datetime.datetime.now().strftime("capture_%Y%m%d_%H%M%S_%f")[:-3] + ".jpg"
            with open(name, "wb") as f:
                f.write(data)
            print(f"{name}: {len(data)} bytes, markers {'OK' if ok else 'BAD'}")
            time.sleep(1.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
