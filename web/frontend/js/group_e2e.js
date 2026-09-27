// Group E2E encryption helpers (Phase 70)
const GroupE2E = (() => {
    const cache = {};  // group_id -> { salt, key_version, key }

    async function loadMeta(groupId) {
        if (cache[groupId] && cache[groupId].salt) return cache[groupId];
        const meta = await API.get(`/api/groups/${groupId}/encryption`);
        cache[groupId] = meta;
        return meta;
    }

    async function deriveGroupKey(groupId, passphrase) {
        const meta = await loadMeta(groupId);
        const saltStr = `group:${groupId}:${meta.salt}`;
        const key = await deriveKey(passphrase, saltStr);
        cache[groupId] = { ...meta, key };
        return key;
    }

    async function encrypt(groupId, passphrase, plaintext) {
        const key = await deriveGroupKey(groupId, passphrase);
        return await encryptMessage(key, plaintext);
    }

    async function decrypt(groupId, passphrase, ciphertext) {
        const key = await deriveGroupKey(groupId, passphrase);
        return await decryptMessage(key, ciphertext);
    }

    async function rotate(groupId) {
        const res = await API.post(`/api/groups/${groupId}/encryption/rotate`, {});
        cache[groupId] = res;
        return res;
    }

    return { loadMeta, deriveGroupKey, encrypt, decrypt, rotate };
})();
