# GhostNote

One-time secret sharing with zero-knowledge encryption. Share passwords, API keys, and sensitive data via a self-destructing link — the server never sees your secret.

## How It Works

```
You type a secret
      │
      ▼
Browser encrypts it with AES-256-GCM          ← happens locally, before any network call
      │
      ├─── Ciphertext + IV ──► Server stores in MongoDB
      │
      └─── Decryption key ──► Embedded in URL fragment (#key)
                                Browsers never send fragments to servers (RFC 3986)
                                Server is architecturally incapable of reading your secret

Recipient opens the link
      │
      ├─── /s/{id} ──► Server atomically deletes the ciphertext (find_one_and_delete)
      │                Returns ciphertext + IV — then it's gone forever
      │
      └─── #key ──► Browser decrypts locally → plaintext shown
```

**What MongoDB stores:** only ciphertext and IV — both useless without the key.  
**What MongoDB never stores:** the decryption key, the plaintext, or any metadata linking the two.

Even if the database is fully compromised, an attacker gets unreadable ciphertext with no key.

---

## Security Properties

| Property | Mechanism |
|---|---|
| Server never sees plaintext | AES-256-GCM encryption runs in the browser before any data is sent |
| Server never sees the key | Key lives in the URL fragment (`#key`); browsers exclude fragments from HTTP requests per RFC 3986 |
| One-time view enforced | MongoDB `find_one_and_delete()` — atomic fetch + delete in a single operation, no race condition |
| Auto-expiry | MongoDB TTL index on `expires_at` — no cron job needed, documents deleted automatically |
| No residual trace | After a secret is revealed: ciphertext gone from DB, key cleared from browser URL via `history.replaceState` |

### Encryption Details

- **Algorithm:** AES-256-GCM (authenticated encryption — detects tampering)
- **Key size:** 256-bit, randomly generated per secret
- **IV size:** 96-bit, randomly generated per secret
- **API:** Native [Web Crypto API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Crypto_API) — no third-party crypto libraries
- **Key encoding:** URL-safe base64 (no `+`, `/`, or `=` that could corrupt fragment parsing)

All crypto code lives in [`app/static/crypto.js`](app/static/crypto.js) (~70 lines, auditable).

---

## Project Structure

```
GhostNote/
├── app/
│   ├── main.py           # FastAPI app, routes, CORS, lifespan
│   ├── config.py         # Settings via environment variables (pydantic-settings)
│   ├── database.py       # Motor async MongoDB client + TTL index setup
│   ├── models.py         # Pydantic request/response schemas
│   ├── routers/
│   │   └── secrets.py    # POST / GET / DELETE /api/secrets endpoints
│   └── static/
│       ├── crypto.js     # Client-side AES-256-GCM encrypt/decrypt (ES module)
│       ├── index.html    # Create secret page
│       └── view.html     # Reveal + burn page
├── Dockerfile
├── docker-compose.yml    # App + MongoDB, with health check
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## API Reference

The API is fully usable without the UI. Interactive docs are available at `/docs` (Swagger UI) and `/redoc` when the server is running.

### `POST /api/secrets`

Store an encrypted secret. **Send only ciphertext and IV — never the decryption key.**

```bash
curl -X POST http://localhost:8000/api/secrets \
  -H "Content-Type: application/json" \
  -d '{
    "ciphertext": "<base64-encoded ciphertext>",
    "iv": "<base64-encoded IV>",
    "ttl_seconds": 3600
  }'
```

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `ciphertext` | string | Yes | AES-256-GCM ciphertext, base64-encoded |
| `iv` | string | Yes | Initialization vector, base64-encoded |
| `ttl_seconds` | integer | No | Expiry in seconds. Min: 300 (5 min), Max: 604800 (7 days). Default: 3600 (1 hour) |

**Response `201`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "expires_at": "2024-01-01T13:00:00Z"
}
```

Construct the share link as: `https://yourhost/s/{id}#{decryption_key}`

---

### `GET /api/secrets/{id}`

Check if a secret exists and get its expiry time. **Does not consume or delete the secret.**

```bash
curl http://localhost:8000/api/secrets/550e8400-e29b-41d4-a716-446655440000
```

**Response `200`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "expires_at": "2024-01-01T13:00:00Z"
}
```

**Response `404`:** Secret not found or already burned.

---

### `DELETE /api/secrets/{id}`

Atomically fetch and permanently destroy the secret. Returns the ciphertext for client-side decryption. **Can only succeed once.**

```bash
curl -X DELETE http://localhost:8000/api/secrets/550e8400-e29b-41d4-a716-446655440000
```

**Response `200`:**
```json
{
  "ciphertext": "<base64-encoded ciphertext>",
  "iv": "<base64-encoded IV>"
}
```

**Response `404`:** Secret already burned or expired.

After receiving this response, decrypt using the key from the URL fragment:
```js
import { decryptSecret } from '/static/crypto.js';
const plaintext = await decryptSecret(ciphertext, iv, keyFromFragment);
```

---

## Setup & Running

### Option 1 — Docker (recommended)

Requires [Docker](https://docs.docker.com/get-docker/) and Docker Compose.

```bash
git clone <repo-url>
cd GhostNote

cp .env.example .env
# Edit .env if needed (defaults work out of the box)

docker compose up
```

App is available at `http://localhost:8000`.  
MongoDB data is persisted in a named Docker volume (`mongo_data`).

To stop:
```bash
docker compose down

# To also remove the database volume:
docker compose down -v
```

---

### Option 2 — Local Development

**Prerequisites:** Python 3.11+, MongoDB 6+ running locally.

```bash
git clone <repo-url>
cd GhostNote

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env if your MongoDB is not at localhost:27017

# Run the development server (auto-reloads on file changes)
uvicorn app.main:app --reload
```

App: `http://localhost:8000`  
API docs: `http://localhost:8000/docs`

---

## Configuration

All configuration is via environment variables (or a `.env` file in the project root).

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DB_NAME` | `ghostnote` | MongoDB database name |
| `DEFAULT_TTL_SECONDS` | `3600` | Default secret expiry (1 hour) |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins. Restrict in production (e.g. `["https://yourdomain.com"]`) |

---

## TTL Options

Secrets auto-expire even if never viewed. TTL is enforced by a MongoDB native index (`expireAfterSeconds=0`) — no scheduled jobs required.

| Label | `ttl_seconds` |
|---|---|
| 5 minutes | `300` |
| 1 hour (default) | `3600` |
| 6 hours | `21600` |
| 24 hours | `86400` |
| 3 days | `259200` |
| 7 days | `604800` |

---

## Production Checklist

- [ ] Set `CORS_ORIGINS` to your actual domain instead of `["*"]`
- [ ] Run behind a reverse proxy (nginx, Caddy) with HTTPS — the URL fragment containing the key must be transmitted over TLS
- [ ] Set `MONGODB_URL` to a connection string with authentication
- [ ] Consider binding uvicorn to `127.0.0.1` and exposing only through the proxy
- [ ] Review MongoDB network exposure — it should not be publicly accessible
