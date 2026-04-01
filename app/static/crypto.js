/**
 * GhostNote — Client-side cryptography module
 *
 * Uses the native Web Crypto API (AES-256-GCM).
 * No external libraries. Auditable in ~50 lines.
 *
 * Security model:
 *   - The plaintext never leaves the browser unencrypted
 *   - The decryption key is embedded in the URL fragment (#key)
 *   - Browsers never send URL fragments to servers (RFC 3986)
 *   - The server stores only ciphertext + IV — both useless without the key
 */

/**
 * Encrypt plaintext. Returns { ciphertext, iv, keyFragment }.
 * keyFragment is URL-safe base64 — suitable for embedding after # in a URL.
 * ciphertext and iv are standard base64 — suitable for JSON transport to the server.
 *
 * @param {string} plaintext
 * @returns {Promise<{ciphertext: string, iv: string, keyFragment: string}>}
 */
export async function encryptSecret(plaintext) {
    const key = await crypto.subtle.generateKey(
        { name: "AES-GCM", length: 256 },
        true,           // extractable — we need to export it for the URL fragment
        ["encrypt", "decrypt"]
    );

    // 96-bit IV is the recommended size for AES-GCM
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encoded = new TextEncoder().encode(plaintext);

    const ciphertext = await crypto.subtle.encrypt(
        { name: "AES-GCM", iv },
        key,
        encoded
    );

    const rawKey = await crypto.subtle.exportKey("raw", key);

    return {
        ciphertext: toBase64(ciphertext),
        iv: toBase64(iv.buffer),
        keyFragment: toBase64url(rawKey), // URL-safe: no +/= chars that could confuse fragments
    };
}

/**
 * Decrypt ciphertext using the key from the URL fragment.
 *
 * @param {string} ciphertextB64  standard base64
 * @param {string} ivB64          standard base64
 * @param {string} keyFragment    URL-safe base64 (from URL #fragment)
 * @returns {Promise<string>}     decrypted plaintext
 */
export async function decryptSecret(ciphertextB64, ivB64, keyFragment) {
    const keyBytes = fromBase64url(keyFragment);
    const ivBytes = fromBase64(ivB64);
    const ciphertextBytes = fromBase64(ciphertextB64);

    const cryptoKey = await crypto.subtle.importKey(
        "raw",
        keyBytes,
        { name: "AES-GCM" },
        false, // not extractable — no need to re-export after import
        ["decrypt"]
    );

    const plaintext = await crypto.subtle.decrypt(
        { name: "AES-GCM", iv: ivBytes },
        cryptoKey,
        ciphertextBytes
    );

    return new TextDecoder().decode(plaintext);
}

// --- Base64 helpers ---

function toBase64(buffer) {
    return btoa(String.fromCharCode(...new Uint8Array(buffer)));
}

function fromBase64(b64) {
    return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

/** URL-safe base64: replaces +→-, /→_, strips = padding */
function toBase64url(buffer) {
    return toBase64(buffer)
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=/g, "");
}

/** Reverse URL-safe base64 back to standard, restore padding, decode */
function fromBase64url(b64url) {
    const b64 = b64url.replace(/-/g, "+").replace(/_/g, "/");
    const padding = "=".repeat((4 - (b64.length % 4)) % 4);
    return fromBase64(b64 + padding);
}
