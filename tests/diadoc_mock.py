"""Заглушка API Диадока для тестов: GetDocuments (V3) и GetEntityContent (V4).

Повторяет то, на что опирается 1С: авторизация Bearer, фильтр по ящику и категории, постраничная
выдача с afterIndexKey и HasMoreResults. Документы задаются тестами через /_test/*.

    uvicorn diadoc_mock:app --app-dir tests --port 8092
"""

import base64
import time

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response

BOX_ID = "test-box"
TOKEN = "test-token"
PAGE_SIZE = 2  # меньше настоящих 100, чтобы тесты проходили через пагинацию
CATEGORY = "UniversalTransferDocument.Inbound"

app = FastAPI()
documents: list[dict] = []
requests_log: list[str] = []


def check_auth(authorization: str | None, box_id: str):
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "Unauthorized")
    if box_id != BOX_ID:
        raise HTTPException(403, "Box access denied")


@app.post("/_test/reset")
def reset():
    documents.clear()
    requests_log.clear()
    return {}


@app.post("/_test/documents")
async def add_documents(request: Request):
    """[{entity_id, message_id, number, date, file_name, content_base64}, ...]"""
    for item in await request.json():
        # IndexKey растет между запусками тестов: база 1С помнит последний загруженный ключ.
        key = f"{time.time_ns():020d}"
        documents.append({**item, "index_key": key, "content": base64.b64decode(item["content_base64"])})
    return {"count": len(documents)}


@app.get("/_test/requests")
def get_requests():
    return requests_log


@app.get("/V3/GetDocuments")
def get_documents(
    boxId: str,
    filterCategory: str,
    afterIndexKey: str | None = None,
    count: int = 100,
    authorization: str | None = Header(None),
):
    check_auth(authorization, boxId)
    requests_log.append(f"GetDocuments afterIndexKey={afterIndexKey}")
    if filterCategory != CATEGORY:
        return {"TotalCount": 0, "Documents": [], "HasMoreResults": False}
    found = [d for d in documents if afterIndexKey is None or d["index_key"] > afterIndexKey]
    page = found[: min(count, PAGE_SIZE)]
    return {
        "TotalCount": len(found),
        "HasMoreResults": len(found) > len(page),
        "Documents": [
            {
                "IndexKey": d["index_key"],
                "MessageId": d["message_id"],
                "EntityId": d["entity_id"],
                "TypeNamedId": "UniversalTransferDocument",
                "DocumentNumber": d["number"],
                "DocumentDate": d["date"],
                "FileName": d["file_name"],
                "Content": {"Size": len(d["content"]), "Data": None},
            }
            for d in page
        ],
    }


@app.get("/V4/GetEntityContent")
def get_entity_content(boxId: str, messageId: str, entityId: str, authorization: str | None = Header(None)):
    check_auth(authorization, boxId)
    requests_log.append(f"GetEntityContent {entityId}")
    for d in documents:
        if d["message_id"] == messageId and d["entity_id"] == entityId:
            return Response(d["content"], media_type="application/octet-stream")
    raise HTTPException(404, "Entity not found")
