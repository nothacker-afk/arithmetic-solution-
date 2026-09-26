// Passkey (WebAuthn) helper — registration + login
const Passkey = (() => {
    function supported() {
        return !!(window.PublicKeyCredential && navigator.credentials);
    }

    function b64urlToBuf(s) {
        const pad = s.length % 4 === 0 ? "" : "=".repeat(4 - (s.length % 4));
        const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/") + pad);
        const buf = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
        return buf.buffer;
    }
    function bufToB64url(buf) {
        const bytes = new Uint8Array(buf);
        let bin = "";
        for (const b of bytes) bin += String.fromCharCode(b);
        return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    }

    async function register(name = "passkey") {
        if (!supported()) throw new Error("not supported");
        if (!API.isLoggedIn()) throw new Error("login first");

        const opts = await API.post("/api/passkeys/register/begin", {});
        const publicKey = {
            ...opts,
            challenge: b64urlToBuf(opts.challenge),
            user: { ...opts.user, id: new TextEncoder().encode(opts.user.id) },
            excludeCredentials: (opts.excludeCredentials || []).map(c => ({
                ...c, id: b64urlToBuf(c.id),
            })),
        };
        const credential = await navigator.credentials.create({ publicKey });
        const payload = {
            id: credential.id,
            rawId: bufToB64url(credential.rawId),
            type: credential.type,
            response: {
                clientDataJSON: bufToB64url(credential.response.clientDataJSON),
                attestationObject: bufToB64url(credential.response.attestationObject),
            },
        };
        return await API.post("/api/passkeys/register/finish", { credential: payload, name });
    }

    async function login(username) {
        if (!supported()) throw new Error("not supported");
        username = username || prompt("Username to sign in with a passkey:");
        if (!username) throw new Error("username required");

        const opts = await API.post("/api/passkeys/login/begin", { username });
        const publicKey = {
            ...opts,
            challenge: b64urlToBuf(opts.challenge),
            allowCredentials: (opts.allowCredentials || []).map(c => ({
                ...c, id: b64urlToBuf(c.id),
            })),
        };
        const assertion = await navigator.credentials.get({ publicKey });
        const payload = {
            id: assertion.id,
            rawId: bufToB64url(assertion.rawId),
            type: assertion.type,
            response: {
                clientDataJSON: bufToB64url(assertion.response.clientDataJSON),
                authenticatorData: bufToB64url(assertion.response.authenticatorData),
                signature: bufToB64url(assertion.response.signature),
                userHandle: assertion.response.userHandle
                    ? bufToB64url(assertion.response.userHandle) : null,
            },
        };
        return await API.post("/api/passkeys/login/finish", { username, credential: payload });
    }

    return { supported, register, login };
})();
