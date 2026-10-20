import json
import os
from pathlib import Path

import httpx
import pytest

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8081/warehouse/hs")
API_KEY = os.environ.get("API_KEY", "api-test-token")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("MODEL", "qwen2.5-coder:7b")

SAMPLES = Path(__file__).parent / "samples"
EXPECTED = json.loads((SAMPLES / "expected.json").read_text(encoding="utf-8"))

# Номенклатура, с которой сопоставляются строки тестовых документов
NOMENCLATURE = [
    ("RD-CABLE", "Кабель ВВГнг 3х2,5"),
    ("RD-QF16", "Автоматический выключатель 16А"),
    ("RD-SOCKET", "Розетка накладная"),
    ("RD-DUCT", "Кабель-канал 25х16"),
    ("RD-LAMP", "Лампа светодиодная 10Вт"),
]


@pytest.fixture(scope="session")
def nomenclature():
    items = [{"sku": sku, "name": name, "quantity": 1} for sku, name in NOMENCLATURE]
    r = httpx.post(f"{BASE_URL}/api/receipts", json={"items": items}, headers={"X-Api-Key": API_KEY}, timeout=60)
    assert r.status_code == 201, r.text


@pytest.fixture(scope="session")
def unload_model():
    yield
    # модель не держим в памяти после прогона
    try:
        httpx.post(f"{OLLAMA_URL}/api/generate", json={"model": MODEL, "keep_alive": 0}, timeout=30)
    except httpx.HTTPError:
        pass


@pytest.fixture(scope="session")
def docs(nomenclature, unload_model):
    with httpx.Client(base_url=f"{BASE_URL}/docs", headers={"X-Api-Key": API_KEY}, timeout=900) as client:
        yield client
