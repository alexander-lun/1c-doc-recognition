"""Тесты сервиса извлечения текста — без 1С и без модели."""

import shutil

import pytest
from fastapi.testclient import TestClient

from conftest import SAMPLES
from doc_text import app

client = TestClient(app)
pytestmark = pytest.mark.service


def test_pdf_with_text_layer():
    r = client.post("/extract", content=(SAMPLES / "upd_01.pdf").read_bytes())
    assert r.status_code == 200
    body = r.json()
    assert body["method"] == "pdf-text"
    assert "7701234560" in body["text"]
    assert "13 420,00" in body["text"]


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="нет tesseract")
def test_scan_goes_to_ocr():
    r = client.post("/extract", content=(SAMPLES / "upd_05_scan.pdf").read_bytes())
    assert r.status_code == 200
    body = r.json()
    assert body["method"] == "ocr"
    text = body["text"]
    assert "3310" in text
    assert "7701234560" in text
    # строки таблицы читаются целиком
    assert "Розетка накладная белая" in text
    assert "1 180,00" in text
    assert "17 980,00" in text


def test_empty_body():
    assert client.post("/extract").status_code == 400


def test_unsupported_file():
    assert client.post("/extract", content="просто текст".encode()).status_code == 415


def test_broken_pdf():
    assert client.post("/extract", content=b"%PDF-1.4 broken").status_code == 422
