"""Извлечение текста из PDF и изображений.

    uvicorn doc_text:app --app-dir service --port 8091

POST /extract — тело запроса: файл как есть (PDF, PNG, JPG).
Ответ: {"text": "...", "method": "pdf-text" | "ocr", "pages": N}

PDF с текстовым слоем читается напрямую, сканы распознаются tesseract (rus+eng).
Перед распознаванием скана удаляются линии таблицы: с ними tesseract теряет строки товаров.
"""

import io
import shutil

import cv2
import numpy as np
import pdfplumber
from fastapi import FastAPI, HTTPException, Request
from PIL import Image

MIN_TEXT_LENGTH = 50
OCR_DPI = 300
# Минимальная длина отрезка (px при 300 dpi), который считается линией таблицы, а не частью буквы
LINE_LENGTH = 60
# Режим сегментации tesseract: один блок текста — строки таблицы не разваливаются на колонки
TESSERACT_CONFIG = "--psm 6"

app = FastAPI(title="Doc text extractor")
HAS_OCR = shutil.which("tesseract") is not None


def remove_table_lines(image: Image.Image) -> Image.Image:
    gray = np.array(image.convert("L"))
    ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (LINE_LENGTH, 1)))
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, LINE_LENGTH)))
    text_only = cv2.subtract(ink, cv2.add(horizontal, vertical))
    return Image.fromarray(cv2.bitwise_not(text_only))


def ocr(images) -> str:
    if not HAS_OCR:
        raise HTTPException(501, "tesseract не установлен")
    import pytesseract

    return "\n".join(
        pytesseract.image_to_string(remove_table_lines(im), lang="rus+eng", config=TESSERACT_CONFIG) for im in images
    )


@app.post("/extract")
async def extract(request: Request):
    data = await request.body()
    if not data:
        raise HTTPException(400, "пустое тело запроса")

    if data[:4] == b"%PDF":
        try:
            pdf = pdfplumber.open(io.BytesIO(data))
        except Exception as e:
            raise HTTPException(422, f"не удалось открыть PDF: {e}") from e
        with pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            if len(text.strip()) >= MIN_TEXT_LENGTH:
                return {"text": text, "method": "pdf-text", "pages": len(pdf.pages)}
            images = [p.to_image(resolution=OCR_DPI).original for p in pdf.pages]
            return {"text": ocr(images), "method": "ocr", "pages": len(pdf.pages)}

    try:
        image = Image.open(io.BytesIO(data))
    except Exception:
        raise HTTPException(415, "поддерживаются PDF, PNG, JPG") from None
    return {"text": ocr([image]), "method": "ocr", "pages": 1}


@app.get("/health")
def health():
    return {"ok": True, "ocr": HAS_OCR}
