"""Электронные УПД: разбор XML в формате ФНС и загрузка входящих документов из Диадока (заглушка API)."""

import base64
import json
import os
import uuid

import httpx
import pytest

from conftest import SAMPLES

EXPECTED_XML = json.loads((SAMPLES / "expected_xml.json").read_text(encoding="utf-8"))
DIADOC_URL = os.environ.get("DIADOC_URL", "http://127.0.0.1:8092")


@pytest.fixture
def diadoc():
    with httpx.Client(base_url=DIADOC_URL, timeout=10) as client:
        client.post("/_test/reset").raise_for_status()
        yield client


def recognize(docs, name, content=None):
    body = content if content is not None else (SAMPLES / name).read_bytes()
    return docs.post("/recognize", params={"filename": name}, content=body)


@pytest.mark.parametrize("name", sorted(EXPECTED_XML))
def test_xml_upd_is_read_without_model(docs, name):
    expected = EXPECTED_XML[name]
    r = recognize(docs, name)
    assert r.status_code == 201, r.text
    body = r.json()
    data, document = body["data"], body["document"]

    assert body["extraction"] == "xml-fns"
    assert data["number"] == expected["number"]
    assert data["date"] == expected["date"]
    assert data["seller"]["inn"] == expected["seller_inn"]
    assert data["total"] == pytest.approx(expected["total"])
    for got, exp in zip(data["items"], expected["items"], strict=True):
        assert got["name"] == exp["name"]
        assert got["code"] == exp["code"]
        assert got["quantity"] == exp["quantity"]
        assert got["price"] == pytest.approx(exp["price"], abs=0.01)
        assert got["amount"] == pytest.approx(exp["amount"])

    # Электронный документ сходится до копейки, а товары сопоставляются по коду (артикулу)
    # или наименованию - замечаний быть не должно, кроме создания нового контрагента.
    notes = [n for n in body["notes"] if "Создан новый контрагент" not in n]
    assert notes == []
    assert document["posted"] is False
    assert document["incoming_number"] == expected["number"]
    assert document["supplier_inn"] == expected["seller_inn"]


def test_xml_upd_ip_seller_name(docs):
    data = recognize(docs, "upd_07_edo_ip_501.xml").json()["data"]
    assert data["seller"]["name"] == "ИП Петров Сергей Николаевич"
    assert data["seller"]["kpp"] == ""


def test_xml_that_is_not_upd(docs):
    r = recognize(docs, "other.xml", '<?xml version="1.0" encoding="utf-8"?><Заказ Номер="1"/>'.encode())
    assert r.status_code == 422
    assert any("не является УПД" in n for n in r.json()["notes"])

    r = recognize(docs, "broken.xml", b"<?xml version='1.0'?><a>")
    assert r.status_code == 422
    assert any("XML" in n for n in r.json()["notes"])


def diadoc_document(name, content=None):
    data = content if content is not None else (SAMPLES / name).read_bytes()
    return {
        "entity_id": str(uuid.uuid4()),
        "message_id": str(uuid.uuid4()),
        "number": name,
        "date": "18.10.2026",
        "file_name": name,
        "content_base64": base64.b64encode(data).decode(),
    }


def pull(docs):
    r = docs.post("/diadoc/pull")
    assert r.status_code == 200, r.text
    return r.json()


def test_diadoc_pull_loads_all_pages_once(docs, diadoc):
    pull(docs)  # догоняем отметку «загружено по» после прошлых запусков
    before = len(diadoc.get("/_test/requests").json())
    names = ["upd_06_edo.xml", "upd_07_edo_ip_501.xml", "upd_06_edo.xml"]
    diadoc.post("/_test/documents", json=[diadoc_document(n) for n in names]).raise_for_status()

    result = pull(docs)
    assert result["errors"] == []
    assert result["loaded"] == 3
    assert [d["incoming_number"] for d in result["documents"]] == ["1601", "44", "1601"]
    # три документа при странице заглушки в 2 - значит, была вторая страница
    requests = diadoc.get("/_test/requests").json()[before:]
    assert sum(r.startswith("GetDocuments") for r in requests) == 2

    again = pull(docs)
    assert again["loaded"] == 0
    assert again["errors"] == []


def test_diadoc_document_sent_again_is_skipped(docs, diadoc):
    pull(docs)
    doc = diadoc_document("upd_06_edo.xml")
    diadoc.post("/_test/documents", json=[doc]).raise_for_status()
    assert pull(docs)["loaded"] == 1

    # тот же документ (EntityId) снова появляется в выдаче, например после перевыставления
    diadoc.post("/_test/documents", json=[doc]).raise_for_status()
    result = pull(docs)
    assert result["loaded"] == 0
    assert result["skipped"] == 1


def test_diadoc_bad_document_is_retried(docs, diadoc):
    pull(docs)
    bad = diadoc_document("broken.xml", b"<?xml version='1.0'?><a>")
    good = diadoc_document("upd_07_edo_ip_501.xml")
    diadoc.post("/_test/documents", json=[bad, good]).raise_for_status()

    first = pull(docs)
    assert len(first["errors"]) == 1
    assert "broken.xml" in first["errors"][0]
    assert first["loaded"] == 1

    # отметка не сдвинулась дальше ошибочного документа: он запрашивается снова, хороший - пропускается
    second = pull(docs)
    assert len(second["errors"]) == 1
    assert second["loaded"] == 0
    assert second["skipped"] == 1
