// Voice recorder (Phase 31) — MediaRecorder + E2E encrypt + upload
const VoiceRecorder = (() => {
    let mediaRecorder = null;
    let chunks = [];
    let startTime = 0;

    function isRecording() {
        return mediaRecorder && mediaRecorder.state === "recording";
    }

    async function start() {
        if (isRecording()) return;
        if (!navigator.mediaDevices || !window.MediaRecorder) {
            throw new Error("Recording not supported on this device");
        }
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        chunks = [];
        const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
            ? "audio/webm;codecs=opus"
            : "audio/webm";
        mediaRecorder = new MediaRecorder(stream, { mimeType: mime });
        mediaRecorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
        mediaRecorder.start();
        startTime = Date.now();
    }

    function stop() {
        return new Promise((resolve, reject) => {
            if (!isRecording()) return reject(new Error("Not recording"));
            mediaRecorder.onstop = () => {
                const blob = new Blob(chunks, { type: "audio/webm" });
                const duration = Date.now() - startTime;
                mediaRecorder.stream.getTracks().forEach(t => t.stop());
                mediaRecorder = null;
                resolve({ blob, durationMs: duration });
            };
            mediaRecorder.stop();
        });
    }

    async function upload(blob, durationMs, key) {
        // Encrypt the audio bytes with the shared E2E key
        const bytes = await fileToBytes(blob);
        const ciphertext_b64 = key ? await encryptBytes(key, bytes)
                                    : await (async () => {
                                        // No key: send base64 of raw bytes with encrypted=false
                                        let bin = "";
                                        for (const b of bytes) bin += String.fromCharCode(b);
                                        return btoa(bin);
                                    })();
        const encrypted = !!key;
        const data = await API.post("/api/voice", {
            ciphertext_b64, duration_ms: durationMs,
            mime: "audio/webm", encrypted,
        });
        return { ...data, encrypted };
    }

    async function loadAndPlay(clipId, encrypted, key, audioEl) {
        const res = await fetch(`${API.base}/api/voice/${clipId}`);
        if (!res.ok) throw new Error("HTTP " + res.status);
        const buf = await res.arrayBuffer();
        let bytes;
        if (encrypted && key) {
            const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
            bytes = await decryptBytes(key, b64);
        } else {
            bytes = new Uint8Array(buf);
        }
        const blob = new Blob([bytes], { type: "audio/webm" });
        audioEl.src = URL.createObjectURL(blob);
        audioEl.play().catch(() => {});
    }

    return { start, stop, isRecording, upload, loadAndPlay };
})();
