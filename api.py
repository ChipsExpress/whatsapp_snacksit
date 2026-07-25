from fastapi import FastAPI, Request
from fastapi.responses import Response

from utils.conversation_store import (
    ConversationStoreError,
    save_inbound_message,
    update_message_status,
)


app = FastAPI(title="WhatsApp Bulk Sender API")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    payload = dict(form)

    try:
        save_inbound_message(payload)
    except ConversationStoreError as exc:
        print(f"WhatsApp webhook database error: {exc}")
        return Response(status_code=500)

    return Response(status_code=200)


@app.post("/webhook/whatsapp/status")
async def whatsapp_status_webhook(request: Request):
    form = await request.form()
    payload = dict(form)

    try:
        update_message_status(payload)
    except ConversationStoreError as exc:
        print(f"WhatsApp status webhook database error: {exc}")
        return Response(status_code=500)

    return Response(status_code=200)
