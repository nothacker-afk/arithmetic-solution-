/* Client-side encryption for Arithmetic Super App.
 *
 * Scheme:
 *   1. Room passphrase -> PBKDF2(SHA-256, 100k iterations) -> AES-GCM 256-bit key
 *   2. Random 12-byte IV per message
 *   3. Output: base64(iv || ciphertext)
 *
 * The server never sees the passphrase or plaintext.
 * Different rooms with the same passphrase produce different keys
 * because the room name is mixed into the salt.
 */

async function deriveKey(passphrase, roomName) {
    const enc = new TextEncoder();
    const keyMaterial = await crypto.subtle.importKey(
        "raw",
        enc.encode(passphrase),
        { name: "PBKDF2" },
        false,
        ["deriveKey"],
    );
    return crypto.subtle.deriveKey(
        {
            name: "PBKDF2",
            salt: enc.encode("arith-chat-v1:" + roomName),
            iterations: 100000,
            hash: "SHA-256",
        },
        keyMaterial,
        { name: "AES-GCM", length: 256 },
        false,
        ["encrypt", "decrypt"],
    );
}

function toBase64(buf) {
    const bytes = new Uint8Array(buf);
    let bin = "";
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin);
}

function fromBase64(b64) {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes;
}

async function encryptMessage(key, plaintext) {
    const enc = new TextEncoder();
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ciphertext = await crypto.subtle.encrypt(
        { name: "AES-GCM", iv },
        key,
        enc.encode(plaintext),
    );
    const combined = new Uint8Array(iv.length + ciphertext.byteLength);
    combined.set(iv, 0);
    combined.set(new Uint8Array(ciphertext), iv.length);
    return toBase64(combined);
}

async function decryptMessage(key, b64) {
    const combined = fromBase64(b64);
    const iv = combined.slice(0, 12);
    const ciphertext = combined.slice(12);
    const plaintext = await crypto.subtle.decrypt(
        { name: "AES-GCM", iv },
        key,
        ciphertext,
    );
    return new TextDecoder().decode(plaintext);
}

/* Byte-level encryption (for file sharing).
 * Input: ArrayBuffer/Uint8Array. Output: base64 string (iv || ciphertext).
 */
async function encryptBytes(key, bytes) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ciphertext = await crypto.subtle.encrypt(
        { name: "AES-GCM", iv },
        key,
        bytes,
    );
    const combined = new Uint8Array(iv.length + ciphertext.byteLength);
    combined.set(iv, 0);
    combined.set(new Uint8Array(ciphertext), iv.length);
    return toBase64(combined);
}

async function decryptBytes(key, b64) {
    const combined = fromBase64(b64);
    const iv = combined.slice(0, 12);
    const ciphertext = combined.slice(12);
    const plaintext = await crypto.subtle.decrypt(
        { name: "AES-GCM", iv },
        key,
        ciphertext,
    );
    return new Uint8Array(plaintext);
}

/* Read a File/Blob into a Uint8Array. */
async function fileToBytes(file) {
    return new Uint8Array(await file.arrayBuffer());
}

/* Trigger a browser download of a Uint8Array. */
function downloadBytes(bytes, filename, mime = "application/octet-stream") {
    const blob = new Blob([bytes], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
