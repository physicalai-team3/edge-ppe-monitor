"""위반 사진에 박스 그리기 (docs/03-contracts.md §6.2)."""
import io

from PIL import Image, ImageDraw, ImageFont

from .judge import Judgement

COLOR_VIOLATOR = "#E5484D"   # 사람 박스: 위반자
COLOR_OK = "#30A46C"         # 사람 박스: 착용자
PERSON_WIDTH = 3
GEAR_WIDTH = 1
JPEG_QUALITY = 85
GEAR_CLASSES = ("helmet", "no_helmet", "vest", "no_vest")


def draw(image: bytes, detections: list[dict], judgement: Judgement) -> bytes:
    """원본 JPEG → 같은 해상도에 박스·라벨을 그린 JPEG."""
    img = Image.open(io.BytesIO(image)).convert("RGB")
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    for p in judgement.persons:
        color = COLOR_OK if p.helmet and p.vest else COLOR_VIOLATOR
        d.rectangle(p.box, outline=color, width=PERSON_WIDTH)

    for det in detections:
        if det["cls"] not in GEAR_CLASSES:
            continue
        color = COLOR_VIOLATOR if det["cls"].startswith("no_") else COLOR_OK
        x1, y1 = det["box"][:2]
        d.rectangle(det["box"], outline=color, width=GEAR_WIDTH)
        label = f"{det['cls']} {det['score']:.2f}"
        tx, ty = x1, max(0, y1 - 12)
        d.rectangle(d.textbbox((tx, ty), label, font=font), fill=color)
        d.text((tx, ty), label, fill="white", font=font)

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()
