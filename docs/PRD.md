# PRD: FaceTag — AR Name Recall Glasses

> **Team:** 3 people | **Timeline:** Hackathon (1 hour) | **Hardware:** Rokid Glasses

---

## Problem Statement

Nobody remembers names after group introductions. You meet 10 people in 5 minutes and immediately forget 8 of them. It's universal, it's embarrassing, and there's no good solution short of asking again.

## Solution

AR glasses that automatically learn who people are during introductions, then display their name (and key context) as a HUD overlay whenever you see them again.

**The flow:**
1. You wear Rokid Glasses during an introduction session
2. The glasses capture video + audio of each person as they introduce themselves
3. A backend extracts face embeddings + transcribes what they said (name, role, fun fact)
4. Face → identity mapping is stored in a local database
5. When you see that person again, the glasses display their name + context on the HUD

---

## Architecture

```
┌─────────────────┐     Bluetooth/CXR     ┌─────────────────┐
│  Rokid Glasses   │◄───────────────────►│  Android Phone   │
│  (glasses-app)   │                      │  (phone-app)     │
│                  │                      │                  │
│ • Camera capture │                      │ • CXR SDK bridge │
│ • HUD display    │                      │ • Face detection │
│ • Mic audio      │                      │ • API calls      │
└─────────────────┘                      └────────┬─────────┘
                                                   │ HTTPS
                                                   ▼
                                         ┌─────────────────┐
                                         │  Backend Server  │
                                         │  (Python/Fast)   │
                                         │                  │
                                         │ • Face embedding │
                                         │   (face_recog/   │
                                         │    InsightFace)  │
                                         │ • STT (Whisper)  │
                                         │ • Person DB      │
                                         │ • Match + lookup │
                                         └─────────────────┘
```

### Component Breakdown

#### 1. Glasses App (Android — runs on Rokid)
- **Camera Service:** Captures frames via Camera2 API (through CXR SDK)
- **Audio Capture:** Records mic audio during introductions
- **HUD Renderer:** Displays name overlay when a match is found
- **Mode Toggle:** "Learning mode" (introductions) vs "Recall mode" (recognition)

#### 2. Phone App (Android — companion)
- **CXR SDK Bridge:** Manages Bluetooth connection to glasses
- **Frame Relay:** Receives camera frames, sends to backend
- **Audio Relay:** Receives audio, sends to backend
- **Result Display:** Pushes recognized identity back to glasses HUD

#### 3. Backend Server (Python)
- **Face Pipeline:**
  - Detect faces in frame (MTCNN or RetinaFace)
  - Extract 128/512-dim face embedding (face_recognition lib or InsightFace)
  - Store embedding vectors in person DB
  - Match incoming face against known embeddings (cosine similarity, threshold ~0.6)
- **Audio Pipeline:**
  - Receive audio chunk from introduction
  - Transcribe via Whisper (local or API)
  - Extract name + key facts via simple NLP or LLM prompt
- **Person Database:**
  - SQLite or PostgreSQL
  - Schema: `person_id, name, role, fun_fact, face_embedding[], created_at, last_seen`
- **API Endpoints:**
  - `POST /enroll` — new person (face frame + audio clip) → creates person record
  - `POST /recognize` — face frame → returns matched person or "unknown"
  - `GET /people` — list all enrolled people
  - `DELETE /people/{id}` — remove a person

---

## HUD Display Design

When a person is recognized, the glasses show:

```
┌──────────────────────────────┐
│                              │
│                              │
│                              │
│    ┌─────────────────────┐   │
│    │  Sarah Chen          │   │
│    │  PM @ Microsoft      │   │
│    │  🎸 Plays guitar     │   │
│    └─────────────────────┘   │
└──────────────────────────────┘
```

- **Name** (large, bold) — always shown
- **Role/Title** (medium) — if captured during intro
- **Fun Fact** (small, with emoji) — if captured during intro
- Display appears for ~5 seconds, then fades
- Position: bottom-center of FOV (30° on Rokid)
- Max 2 lines below name to stay readable at 480x640 resolution

---

## Team Split (3 people, 1 hour)

### Person A — Designer / UX
- Design the HUD overlay layout (Figma or sketch)
- Design the phone app UI (Learning mode vs Recall mode toggle)
- Define the visual states: scanning, recognized, unknown, enrolling
- Create any demo/pitch assets

### Person B — Glasses + Phone App (has the hardware)
- Set up the Rokid CXR SDK connection (phone ↔ glasses)
- Implement camera frame capture on glasses
- Implement audio capture on glasses
- Build the phone-side relay that sends frames/audio to backend
- Render HUD text overlay on glasses when backend returns a match

### Person C — Backend (Kaleb)
- Stand up a Python FastAPI server
- Implement `/enroll` endpoint:
  - Accept image + audio
  - Run face_recognition to extract embedding
  - Run Whisper to transcribe audio → extract name/facts
  - Store in SQLite
- Implement `/recognize` endpoint:
  - Accept image frame
  - Extract embedding, compare against DB
  - Return best match (name, role, fun_fact) or "unknown"
- Deploy locally or on a quick cloud instance (ngrok for hackathon)

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Glasses app | Kotlin/Android, CXR SDK | Rokid native |
| Phone app | Kotlin/Android, CXR-M SDK | Companion bridge |
| Backend | Python, FastAPI | Fast to prototype |
| Face detection | face_recognition (dlib) or InsightFace | Proven, fast setup |
| Face embeddings | Same as above (128-dim vectors) | Works for small DB |
| STT | OpenAI Whisper (API or local) | Best accuracy/speed |
| Name extraction | GPT-4o-mini or regex | Parse "Hi I'm Sarah, I'm a PM" |
| Database | SQLite | Zero setup, hackathon-friendly |
| Tunnel | ngrok | Phone → backend over internet |

---

## MVP Scope (1-hour hackathon)

### Must Have (demo-able)
- [ ] Backend: `/enroll` accepts an image + name (manual name entry OK if STT isn't ready)
- [ ] Backend: `/recognize` accepts an image, returns name or "unknown"
- [ ] Face embedding + matching working with >80% accuracy on small set
- [ ] Glasses can capture a frame and send it to phone → backend
- [ ] Glasses display returned name as HUD text

### Nice to Have (if time permits)
- [ ] Audio transcription to auto-extract name during enrollment
- [ ] LLM extraction of role + fun fact from transcription
- [ ] Phone app UI with Learning/Recall mode toggle
- [ ] Multiple face detection in a single frame
- [ ] Confidence score display

### Out of Scope (post-hackathon)
- Persistent cloud database
- Privacy controls / consent flow
- LinkedIn profile lookup (despite the repo name 😄)
- Multi-user support
- Offline on-device inference

---

## API Spec (Quick Reference)

### POST /enroll
```json
// Request
{
  "image": "<base64 encoded frame>",
  "audio": "<base64 encoded audio clip>",  // optional
  "name": "Sarah Chen",                     // fallback if no STT
  "role": "PM @ Microsoft",                 // optional
  "fun_fact": "Plays guitar"                // optional
}

// Response
{
  "person_id": "uuid",
  "name": "Sarah Chen",
  "status": "enrolled"
}
```

### POST /recognize
```json
// Request
{
  "image": "<base64 encoded frame>"
}

// Response
{
  "matched": true,
  "person": {
    "person_id": "uuid",
    "name": "Sarah Chen",
    "role": "PM @ Microsoft",
    "fun_fact": "Plays guitar",
    "confidence": 0.87
  }
}
```

### GET /people
```json
// Response
{
  "people": [
    {"person_id": "uuid", "name": "Sarah Chen", "enrolled_at": "..."},
    ...
  ]
}
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| CXR SDK setup takes too long | Can't demo on glasses | Fall back to webcam demo on laptop |
| Face recognition accuracy low | Wrong names displayed | Lower match threshold, show confidence |
| Audio transcription too slow | Can't auto-enroll | Manual name entry via phone app |
| Network latency (ngrok) | Slow recognition | Run backend on local network |
| Rokid 480x640 resolution | Hard to read text | Large font, minimal text, high contrast |

---

## Fallback Demo Plan

If glasses integration isn't ready in time:
1. Use a **laptop webcam** as the camera input
2. Run the same backend
3. Show the HUD overlay in a **web browser** (simple HTML/JS overlay on video feed)
4. Pitch the Rokid integration as "next step" with the architecture diagram

This still demonstrates the core value prop: see a face → get their name.

---

*Created: 2026-03-28 | Hackathon PRD | Team: 3*
