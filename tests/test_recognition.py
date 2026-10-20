import httpx
import pytest

from conftest import API_KEY, BASE_URL, EXPECTED, SAMPLES


def recognize(docs, name):
    return docs.post("/recognize", params={"filename": name}, content=(SAMPLES / name).read_bytes())


def test_requires_api_key():
    r = httpx.post(f"{BASE_URL}/docs/recognize", content=b"%PDF")
    assert r.status_code == 401


def test_empty_body(docs):
    assert docs.post("/recognize").status_code == 400


def test_not_a_document(docs):
    r = docs.post("/recognize", params={"filename": "note.txt"}, content="просто текст".encode())
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False
    assert body["document"] is None
    assert any("HTTP 415" in n for n in body["notes"])


@pytest.mark.llm
@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_sample_is_recognized(docs, name):
    expected = EXPECTED[name]
    r = recognize(docs, name)
    assert r.status_code == 201, r.text
    body = r.json()
    data, document = body["data"], body["document"]

    assert body["extraction"] == expected["extraction"]
    assert data["number"] == expected["number"]
    assert data["date"] == expected["date"]
    assert data["total"] == pytest.approx(expected["total"], abs=0.01)
    assert len(data["items"]) == len(expected["items"])
    for got, exp in zip(data["items"], expected["items"], strict=True):
        assert got["quantity"] == pytest.approx(exp["quantity"])
        assert got["price"] == pytest.approx(exp["price"], abs=0.01)
        assert got["amount"] == pytest.approx(exp["amount"], abs=0.01)

    # черновик: не проводится автоматически
    assert document["posted"] is False
    assert document["incoming_number"] == expected["number"]
    assert document["amount"] == pytest.approx(expected["total"], abs=0.01)

    notes = " | ".join(body["notes"])
    assert "не совпадает с итогом" not in notes
    assert "количество × цена" not in notes

    if expected["seller_inn"] and name != "upd_03_bad_inn.pdf":
        assert data["seller"]["inn"] == expected["seller_inn"]
        assert document["supplier_inn"] == expected["seller_inn"]


@pytest.mark.llm
def test_invalid_inn_is_reported(docs):
    body = recognize(docs, "upd_03_bad_inn.pdf").json()
    assert body["needs_review"] is True
    assert any("контрольных цифр" in n for n in body["notes"])
    assert body["document"]["supplier"] == ""


@pytest.mark.llm
def test_unknown_item_is_reported(docs):
    body = recognize(docs, "invoice_02.pdf").json()
    unmatched = [n for n in body["notes"] if "не сопоставлен" in n]
    assert len(unmatched) == 1
    assert "Изолента" in unmatched[0]


def test_log_has_records(docs):
    r = docs.get("/log")
    assert r.status_code == 200
    assert len(r.json()["items"]) > 0


def test_log_requires_api_key():
    assert httpx.get(f"{BASE_URL}/docs/log", headers={"X-Api-Key": API_KEY + "x"}).status_code == 401
