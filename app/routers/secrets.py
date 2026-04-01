from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta, timezone
import uuid

from app.models import (
    CreateSecretRequest,
    CreateSecretResponse,
    SecretMetadataResponse,
    RevealSecretResponse,
)
from app.database import get_db

router = APIRouter(prefix="/api/secrets", tags=["Secrets"])


@router.post(
    "",
    response_model=CreateSecretResponse,
    status_code=201,
    summary="Store an encrypted secret",
    description=(
        "Accepts only ciphertext and IV — the decryption key must never be sent here. "
        "Returns an ID. Construct the share link as: `https://host/s/{id}#{key}`. "
        "The `#key` fragment is never transmitted to the server by browsers."
    ),
)
async def create_secret(
    payload: CreateSecretRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    secret_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=payload.ttl_seconds)

    await db.secrets.insert_one({
        "_id": secret_id,
        "ciphertext": payload.ciphertext,
        "iv": payload.iv,
        "created_at": now,
        "expires_at": expires_at,
    })

    return CreateSecretResponse(id=secret_id, expires_at=expires_at)


@router.get(
    "/{secret_id}",
    response_model=SecretMetadataResponse,
    summary="Check if a secret exists",
    description=(
        "Returns metadata (ID + expiry) without consuming the secret. "
        "Does NOT return ciphertext. Safe to call multiple times."
    ),
)
async def get_secret_metadata(
    secret_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    # Fetch only metadata fields — never fetch ciphertext in this endpoint
    doc = await db.secrets.find_one(
        {"_id": secret_id},
        {"_id": 1, "expires_at": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Secret not found or already burned")
    return SecretMetadataResponse(id=doc["_id"], expires_at=doc["expires_at"])


@router.delete(
    "/{secret_id}",
    response_model=RevealSecretResponse,
    summary="Reveal and permanently destroy a secret",
    description=(
        "**Atomic operation**: fetches and deletes the document in a single MongoDB "
        "`find_one_and_delete()` call — no race conditions possible. "
        "After this call the ciphertext is permanently gone from the database. "
        "Returns 404 if the secret was already burned or has expired."
    ),
)
async def reveal_and_destroy(
    secret_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    # find_one_and_delete is atomic at the MongoDB document level.
    # Two simultaneous requests cannot both succeed — only one gets the document.
    doc = await db.secrets.find_one_and_delete({"_id": secret_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Secret not found or already burned")

    return RevealSecretResponse(ciphertext=doc["ciphertext"], iv=doc["iv"])
