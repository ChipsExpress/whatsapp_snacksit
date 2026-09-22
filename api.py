import os
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse, Response
from dotenv import load_dotenv

from utils.conversation_store import (
    ConversationStoreError,
    save_inbound_message,
    update_message_status,
)

load_dotenv()

app = FastAPI(title="SnacksIT WhatsApp Bulk Sender API")

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN") or os.getenv("WHATSAPP_VERIFY_TOKEN") or "your_custom_webhook_verify_token_here"


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/webhook/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and (hub_token == META_VERIFY_TOKEN or META_VERIFY_TOKEN == "your_custom_webhook_verify_token_here"):
        print("Meta webhook verified successfully!")
        return PlainTextResponse(content=hub_challenge, status_code=200)
    
    if hub_mode or hub_token:
        raise HTTPException(status_code=403, detail="Verification token mismatch")

    return {"status": "Meta Webhook verification endpoint active"}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    content_type = request.headers.get("content-type", "")
    
    if "application/json" in content_type:
        payload = await request.json()
    else:
        form = await request.form()
        payload = dict(form)

    try:
        # Route to appropriate handler based on payload content
        has_statuses = False
        if isinstance(payload, dict):
            try:
                changes = payload.get("entry", [])[0].get("changes", [])[0].get("value", {})
                if "statuses" in changes:
                    has_statuses = True
            except (IndexError, AttributeError, KeyError):
                pass

        if has_statuses:
            update_message_status(payload)
        else:
            save_inbound_message(payload)
    except ConversationStoreError as exc:
        print(f"WhatsApp webhook database error: {exc}")
        return Response(status_code=500)

    return Response(status_code=200)


@app.post("/webhook/whatsapp/status")
async def whatsapp_status_webhook(request: Request):
    content_type = request.headers.get("content-type", "")
    
    if "application/json" in content_type:
        payload = await request.json()
    else:
        form = await request.form()
        payload = dict(form)

    try:
        update_message_status(payload)
    except ConversationStoreError as exc:
        print(f"WhatsApp status webhook database error: {exc}")
        return Response(status_code=500)

    return Response(status_code=200)


