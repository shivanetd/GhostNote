from pydantic import BaseModel, Field
from datetime import datetime


class CreateSecretRequest(BaseModel):
    """
    Only ciphertext + IV are accepted. The decryption key must NEVER be sent here.
    It belongs in the URL fragment (#key) so browsers never transmit it to the server.
    """
    ciphertext: str = Field(
        ...,
        description="AES-256-GCM ciphertext, base64-encoded. Unreadable without the key.",
    )
    iv: str = Field(
        ...,
        description="AES-GCM initialization vector, base64-encoded. Not secret — required for decryption.",
    )
    ttl_seconds: int = Field(
        default=3600,
        ge=300,      # 5 minutes minimum
        le=604800,   # 7 days maximum
        description="Seconds until the secret auto-expires, even if never viewed. Default: 3600 (1 hour).",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "ciphertext": "U2FsdGVkX1...(base64)",
                "iv": "YWJjZGVmZ2g...(base64)",
                "ttl_seconds": 3600,
            }
        }
    }


class CreateSecretResponse(BaseModel):
    id: str = Field(..., description="Unique secret ID. Append your key as URL fragment: /s/{id}#{key}")
    expires_at: datetime = Field(..., description="UTC timestamp when the secret auto-expires.")


class SecretMetadataResponse(BaseModel):
    id: str
    expires_at: datetime


class RevealSecretResponse(BaseModel):
    ciphertext: str = Field(
        ...,
        description="Encrypted data. Decrypt client-side using the key from your URL fragment.",
    )
    iv: str = Field(..., description="IV needed for AES-GCM decryption.")
