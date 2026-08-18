// The live layer of a room: one websocket (chat, presence, speaking,
// reactions, role changes) plus a WebRTC audio mesh negotiated over it.
// The server only relays signaling — audio flows peer-to-peer.

import { useCallback, useEffect, useRef, useState } from "react";
import { tokens } from "../api.js";

const RTC_CONFIG = { iceServers: [{ urls: "stun:stun.l.google.com:19302" }] };

export function useRoomLive(roomId, selfId, { onPresence } = {}) {
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState([]);
  const [speaking, setSpeaking] = useState({}); // userId -> bool
  const [micStates, setMicStates] = useState({}); // userId -> bool
  const [micOn, setMicOn] = useState(false);
  const [reactions, setReactions] = useState([]); // floating emoji
  const [captions, setCaptions] = useState([]); // live transcript lines
  const [captionsOn, setCaptionsOn] = useState(false);
  const [recording, setRecording] = useState(false);

  const wsRef = useRef(null);
  const peersRef = useRef(new Map()); // userId -> { pc, polite, makingOffer, audio }
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const recognitionRef = useRef(null);
  const recorderRef = useRef(null);
  const presenceRef = useRef(onPresence);
  presenceRef.current = onPresence;

  const send = useCallback((payload) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
  }, []);

  /* ---------- WebRTC mesh ---------- */

  const ensurePeer = useCallback(
    (peerId) => {
      let entry = peersRef.current.get(peerId);
      if (entry) return entry;

      const pc = new RTCPeerConnection(RTC_CONFIG);
      // deterministic role assignment prevents offer collisions ("perfect
      // negotiation": the polite side rolls back on glare)
      entry = { pc, polite: selfId > peerId, makingOffer: false, audio: null };
      peersRef.current.set(peerId, entry);

      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => pc.addTrack(t, streamRef.current));
      }

      pc.onicecandidate = ({ candidate }) => {
        if (candidate) send({ type: "signal", target: peerId, data: { candidate } });
      };

      pc.onnegotiationneeded = async () => {
        try {
          entry.makingOffer = true;
          await pc.setLocalDescription();
          send({ type: "signal", target: peerId, data: { description: pc.localDescription } });
        } catch {
          /* peer likely gone */
        } finally {
          entry.makingOffer = false;
        }
      };

      pc.ontrack = ({ streams }) => {
        if (!entry.audio) {
          entry.audio = new Audio();
          entry.audio.autoplay = true;
        }
        entry.audio.srcObject = streams[0];
        entry.stream = streams[0]; // kept so the recorder can mix it in
        entry.audio.play().catch(() => {});
      };

      return entry;
    },
    [selfId, send]
  );

  const dropPeer = useCallback((peerId) => {
    const entry = peersRef.current.get(peerId);
    if (!entry) return;
    try {
      entry.pc.close();
    } catch {}
    if (entry.audio) entry.audio.srcObject = null;
    peersRef.current.delete(peerId);
  }, []);

  const handleSignal = useCallback(
    async (fromId, data) => {
      const entry = ensurePeer(fromId);
      const { pc } = entry;
      try {
        if (data.description) {
          const collision =
            data.description.type === "offer" &&
            (entry.makingOffer || pc.signalingState !== "stable");
          if (collision && !entry.polite) return; // impolite side ignores glare
          await pc.setRemoteDescription(data.description);
          if (data.description.type === "offer") {
            await pc.setLocalDescription();
            send({ type: "signal", target: fromId, data: { description: pc.localDescription } });
          }
        } else if (data.candidate) {
          await pc.addIceCandidate(data.candidate).catch(() => {});
        }
      } catch {
        /* signaling race with a departing peer — safe to ignore */
      }
    },
    [ensurePeer, send]
  );

  /* ---------- microphone ---------- */

  const startSpeakingDetector = useCallback(() => {
    const ctx = new AudioContext();
    audioCtxRef.current = ctx;
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    ctx.createMediaStreamSource(streamRef.current).connect(analyser);
    const buf = new Uint8Array(analyser.frequencyBinCount);
    let last = false;
    const tick = () => {
      if (!audioCtxRef.current) return;
      analyser.getByteFrequencyData(buf);
      const level = buf.reduce((a, b) => a + b, 0) / buf.length;
      const now = level > 22 && streamRef.current?.getAudioTracks()[0]?.enabled;
      if (now !== last) {
        last = now;
        setSpeaking((s) => ({ ...s, [selfId]: now }));
        send({ type: "speaking", value: now });
      }
      requestAnimationFrame(tick);
    };
    tick();
  }, [selfId, send]);

  const toggleMic = useCallback(async () => {
    if (!streamRef.current) {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      // publish to every existing peer; onnegotiationneeded renegotiates
      peersRef.current.forEach(({ pc }) =>
        stream.getTracks().forEach((t) => pc.addTrack(t, stream))
      );
      startSpeakingDetector();
      setMicOn(true);
      send({ type: "mic", value: true });
      return;
    }
    const track = streamRef.current.getAudioTracks()[0];
    track.enabled = !track.enabled;
    setMicOn(track.enabled);
    send({ type: "mic", value: track.enabled });
  }, [send, startSpeakingDetector]);

  /* ---------- live captions (free, in-browser speech recognition) ---------- */

  const toggleCaptions = useCallback(
    (language = "en-IN") => {
      const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        throw new Error("This browser has no speech recognition (try Chrome).");
      }
      if (recognitionRef.current) {
        recognitionRef.current.onend = null;
        recognitionRef.current.stop();
        recognitionRef.current = null;
        setCaptionsOn(false);
        return;
      }
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = false; // only broadcast settled phrases
      recognition.lang = language;
      recognition.onresult = (event) => {
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const result = event.results[i];
          if (!result.isFinal) continue;
          const text = result[0].transcript.trim();
          if (text) send({ type: "caption", text, language });
        }
      };
      // recognition stops itself on silence; restart while still enabled
      recognition.onend = () => {
        if (recognitionRef.current === recognition) {
          try {
            recognition.start();
          } catch {
            /* already restarting */
          }
        }
      };
      recognition.start();
      recognitionRef.current = recognition;
      setCaptionsOn(true);
    },
    [send]
  );

  /* ---------- recording: mix every stream, capture once ---------- */

  const startRecording = useCallback(() => {
    const context = new AudioContext();
    const destination = context.createMediaStreamDestination();
    let sources = 0;
    if (streamRef.current) {
      context.createMediaStreamSource(streamRef.current).connect(destination);
      sources += 1;
    }
    peersRef.current.forEach((entry) => {
      if (entry.stream) {
        context.createMediaStreamSource(entry.stream).connect(destination);
        sources += 1;
      }
    });
    if (sources === 0) throw new Error("No audio to record yet — turn a mic on.");

    const chunks = [];
    const recorder = new MediaRecorder(destination.stream);
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    recorder.start();
    recorderRef.current = { recorder, chunks, context, startedAt: Date.now() };
    setRecording(true);
  }, []);

  const stopRecording = useCallback(
    () =>
      new Promise((resolve, reject) => {
        const current = recorderRef.current;
        if (!current) return resolve(null);
        const { recorder, chunks, context, startedAt } = current;
        recorder.onstop = async () => {
          const blob = new Blob(chunks, { type: "audio/webm" });
          const seconds = Math.round((Date.now() - startedAt) / 1000);
          context.close().catch(() => {});
          recorderRef.current = null;
          setRecording(false);
          const form = new FormData();
          form.append("audio", blob, `room-${roomId}.webm`);
          form.append("duration", String(seconds));
          try {
            const res = await fetch(`/api/v1/rooms/${roomId}/recording/`, {
              method: "POST",
              headers: { Authorization: `Bearer ${tokens.access}` },
              body: form, // no Content-Type: the browser sets the boundary
            });
            if (!res.ok) throw new Error("Upload failed");
            resolve({ seconds, size: blob.size });
          } catch (err) {
            reject(err);
          }
        };
        recorder.stop();
      }),
    [roomId]
  );

  /* ---------- socket lifecycle ---------- */

  useEffect(() => {
    if (!roomId || !tokens.access) return;
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(
      `${proto}://${window.location.host}/ws/rooms/${roomId}/?token=${tokens.access}`
    );
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);

    ws.onmessage = (raw) => {
      const msg = JSON.parse(raw.data);
      const uid = msg.user?.id;
      switch (msg.event) {
        case "peer_joined":
          if (uid !== selfId) {
            ensurePeer(uid); // existing side initiates once tracks/negotiation fire
            presenceRef.current?.();
          }
          break;
        case "peer_left":
          if (uid !== selfId) {
            dropPeer(uid);
            setSpeaking((s) => ({ ...s, [uid]: false }));
            presenceRef.current?.();
          }
          break;
        case "chat":
          setMessages((m) => [...m.slice(-199), msg]);
          break;
        case "signal":
          if (msg.from !== selfId) handleSignal(msg.from, msg.data);
          break;
        case "speaking":
          if (uid !== selfId) setSpeaking((s) => ({ ...s, [uid]: msg.value }));
          break;
        case "mic":
          setMicStates((s) => ({ ...s, [uid]: msg.value }));
          break;
        case "caption":
          setCaptions((c) => [
            ...c.slice(-49),
            { id: `${uid}-${Date.now()}`, who: msg.user.display_name, text: msg.text },
          ]);
          break;
        case "reaction": {
          const id = Math.random().toString(36).slice(2);
          setReactions((r) => [...r, { id, emoji: msg.value, name: msg.user.display_name }]);
          setTimeout(() => setReactions((r) => r.filter((x) => x.id !== id)), 2600);
          break;
        }
        case "role":
        case "question":
        case "goal":
          // server-side state changed for everyone — refetch room data
          presenceRef.current?.();
          break;
        default:
          break;
      }
    };

    return () => {
      ws.close();
      peersRef.current.forEach((_, id) => dropPeer(id));
      peersRef.current.clear();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      audioCtxRef.current?.close().catch(() => {});
      audioCtxRef.current = null;
      if (recognitionRef.current) {
        recognitionRef.current.onend = null;
        recognitionRef.current.stop();
        recognitionRef.current = null;
      }
      if (recorderRef.current) {
        try {
          recorderRef.current.recorder.stop();
          recorderRef.current.context.close();
        } catch {
          /* already torn down */
        }
        recorderRef.current = null;
      }
    };
  }, [roomId, selfId, ensurePeer, dropPeer, handleSignal]);

  const sendChat = useCallback((text) => send({ type: "chat", text }), [send]);
  const sendReaction = useCallback((emoji) => send({ type: "reaction", value: emoji }), [send]);

  return {
    connected,
    messages,
    setMessages,
    sendChat,
    sendReaction,
    reactions,
    speaking,
    micStates,
    micOn,
    toggleMic,
    captions,
    captionsOn,
    toggleCaptions,
    recording,
    startRecording,
    stopRecording,
  };
}
