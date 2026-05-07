"""
╔══════════════════════════════════════════════════════════════════╗
║      AuthentiAction — Pattern-Based Gesture Authentication       ║
║        Hand Gesture Passwordless Security System                 ║
╚══════════════════════════════════════════════════════════════════╝

Requirements:
    pip install -r requirements.txt

Usage:
    python authentiaction.py

Modes:
    R — Register a new gesture password
    A — Authenticate with your gesture password
    Q — Quit
"""

import cv2
import mediapipe as mp
import numpy as np
import time
import json
import hashlib
import os

# ── MediaPipe Setup ──────────────────────────────────────────────────────────
mp_hands   = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_styles  = mp.solutions.drawing_styles

# ── Constants ────────────────────────────────────────────────────────────────
PROFILE_FILE      = "gesture_profile.json"
SEQUENCE_LENGTH   = 4          # number of gestures in password
HOLD_FRAMES       = 12         # frames a gesture must be held to register
MAX_ATTEMPTS      = 3          # lockout after this many failures
COOLDOWN_SECS     = 5.0        # seconds between gesture registrations

# Gesture definitions
GESTURES = {
    "G1": {"name": "Index Up",   "emoji": "☝",  "desc": "Only index finger extended"},
    "G2": {"name": "Pinch",      "emoji": "🤏", "desc": "Thumb + index tips touching"},
    "G3": {"name": "Two Fingers","emoji": "✌",  "desc": "Index + middle extended"},
    "G4": {"name": "Open Palm",  "emoji": "🖐",  "desc": "All 5 fingers extended"},
    "G5": {"name": "Fist",       "emoji": "✊",  "desc": "All fingers folded"},
}

# UI colours (BGR)
COL_GREEN  = (0,   220, 120)
COL_BLUE   = (255, 160,  40)
COL_RED    = (60,   60, 220)
COL_YELLOW = (0,   200, 230)
COL_WHITE  = (230, 230, 230)
COL_GREY   = (120, 120, 120)
COL_BG     = (18,  18,  24)


# ══════════════════════════════════════════════════════════════════
#  GESTURE CLASSIFIER
# ══════════════════════════════════════════════════════════════════

def fingers_up(lm):
    """Returns [thumb, index, middle, ring, pinky] — 1=extended, 0=folded."""
    tips = [4, 8, 12, 16, 20]
    up   = []
    # Thumb (x-axis comparison, mirrored camera)
    up.append(1 if lm[tips[0]].x < lm[tips[0]-1].x else 0)
    # Other fingers (y-axis: tip above pip = extended)
    for i in range(1, 5):
        up.append(1 if lm[tips[i]].y < lm[tips[i]-2].y else 0)
    return up


def pinch_dist(lm):
    """Normalised Euclidean distance between thumb tip and index tip."""
    t, i = lm[4], lm[8]
    return np.hypot(t.x - i.x, t.y - i.y)


def classify(lm):
    """Returns gesture key string: G1–G5 or None."""
    up    = fingers_up(lm)
    pinch = pinch_dist(lm)
    th, ix, mid, rng, pnk = up

    if sum(up) == 5:                                      return "G4"  # Open Palm
    if sum(up) == 0:                                      return "G5"  # Fist
    if pinch < 0.06 and mid == 0 and rng == 0 and pnk == 0: return "G2"  # Pinch
    if ix == 1 and mid == 1 and rng == 0 and pnk == 0:   return "G3"  # Two Fingers
    if ix == 1 and mid == 0 and rng == 0 and pnk == 0:   return "G1"  # Index Up
    return None


# ══════════════════════════════════════════════════════════════════
#  PROFILE  (save / load / hash)
# ══════════════════════════════════════════════════════════════════

def hash_sequence(seq):
    raw = "-".join(seq).encode()
    return hashlib.sha256(raw).hexdigest()


def save_profile(sequence):
    data = {
        "sequence_hash": hash_sequence(sequence),
        "created_at":     time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(PROFILE_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n✅  Profile saved → {PROFILE_FILE}")


def load_profile():
    if not os.path.exists(PROFILE_FILE):
        return None
    with open(PROFILE_FILE) as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════════════
#  DRAWING HELPERS
# ══════════════════════════════════════════════════════════════════

def draw_bg(frame):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (frame.shape[1], frame.shape[0]), COL_BG, -1)
    cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)


def draw_panel(frame, x, y, w, h, alpha=0.6):
    sub  = frame[y:y+h, x:x+w]
    rect = np.full(sub.shape, (22, 22, 32), dtype=np.uint8)
    cv2.addWeighted(rect, alpha, sub, 1-alpha, 0, sub)
    frame[y:y+h, x:x+w] = sub
    cv2.rectangle(frame, (x, y), (x+w, y+h), (50, 50, 65), 1)


def put_text(frame, text, pos, scale=0.6, color=COL_WHITE, thickness=1):
    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_DUPLEX,
                scale, color, thickness, cv2.LINE_AA)


def draw_sequence_slots(frame, captured, total=SEQUENCE_LENGTH,
                        ox=20, oy=90, label="Password"):
    put_text(frame, label, (ox, oy-10), 0.45, COL_GREY)
    for i in range(total):
        x = ox + i * 74
        filled = i < len(captured)
        color  = COL_GREEN if filled else (50, 50, 65)
        cv2.rectangle(frame, (x, oy), (x+62, oy+62), color, -1)
        cv2.rectangle(frame, (x, oy), (x+62, oy+62),
                      COL_GREEN if filled else (80, 80, 100), 2)
        if filled:
            g    = captured[i]
            emoji = GESTURES[g]["emoji"]
            put_text(frame, g, (x+18, oy+40), 0.75, COL_BG, 2)
        else:
            put_text(frame, "?", (x+22, oy+40), 0.85, (60, 60, 80), 2)


def draw_gesture_legend(frame, current, fx=460, fy=80):
    draw_panel(frame, fx-8, fy-20, 172, 148)
    put_text(frame, "Gestures", (fx, fy-4), 0.42, COL_GREY)
    for j, (key, info) in enumerate(GESTURES.items()):
        col = COL_GREEN if key == current else COL_GREY
        put_text(frame, f"{info['emoji']} {key}: {info['name']}",
                 (fx, fy + 18 + j*22), 0.42, col)


def draw_status_bar(frame, text, color=COL_WHITE):
    h = frame.shape[0]
    draw_panel(frame, 0, h-44, frame.shape[1], 44, alpha=0.75)
    put_text(frame, text, (14, h-16), 0.55, color, 1)


def draw_mode_badge(frame, mode):
    colors = {"REGISTER": COL_YELLOW, "AUTHENTICATE": COL_BLUE, "MENU": COL_GREY}
    col = colors.get(mode, COL_WHITE)
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 36), (14, 14, 20), -1)
    put_text(frame, f"AuthentiAction  |  MODE: {mode}", (14, 24), 0.58, col, 1)


# ══════════════════════════════════════════════════════════════════
#  REGISTER MODE
# ══════════════════════════════════════════════════════════════════

def register_mode(cap, hands):
    print("\n[ REGISTER ] Perform your 4-gesture password sequence.")
    print("Hold each gesture steady until it registers.\n")

    captured        = []   # list of gesture keys captured so far
    last_gesture    = None
    hold_counter    = 0
    last_reg_time   = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res   = hands.process(rgb)

        current_gesture = None

        if res.multi_hand_landmarks:
            hl = res.multi_hand_landmarks[0]
            mp_drawing.draw_landmarks(
                frame, hl, mp_hands.HAND_CONNECTIONS,
                mp_styles.get_default_hand_landmarks_style(),
                mp_styles.get_default_hand_connections_style())
            current_gesture = classify(hl.landmark)

        draw_bg(frame)
        draw_mode_badge(frame, "REGISTER")

        # ── Hold-to-register logic ───────────────────────────────
        now = time.time()
        if (current_gesture and
                current_gesture == last_gesture and
                now - last_reg_time > COOLDOWN_SECS and
                len(captured) < SEQUENCE_LENGTH):

            hold_counter += 1
            pct = int((hold_counter / HOLD_FRAMES) * 100)

            # Progress ring
            cx, cy, r = 320, 240, 48
            cv2.ellipse(frame, (cx, cy), (r, r), -90,
                        0, int(3.6 * pct), COL_GREEN, 6)
            put_text(frame, f"{pct}%", (cx-16, cy+8), 0.65, COL_GREEN)

            if hold_counter >= HOLD_FRAMES:
                captured.append(current_gesture)
                last_reg_time = now
                hold_counter  = 0
                print(f"  ✔ Gesture {len(captured)}: {current_gesture} "
                      f"({GESTURES[current_gesture]['name']})")
        else:
            if current_gesture != last_gesture:
                hold_counter    = 0
        last_gesture = current_gesture

        # ── Draw UI ──────────────────────────────────────────────
        draw_panel(frame, 10, 46, 440, 230)
        draw_sequence_slots(frame, captured, label="Your Gesture Password")

        remaining = SEQUENCE_LENGTH - len(captured)
        if remaining > 0:
            put_text(frame, f"Perform gesture {len(captured)+1} of {SEQUENCE_LENGTH}",
                     (20, 270), 0.5, COL_WHITE)
            put_text(frame, f"Hold steady to register  •  {remaining} remaining",
                     (20, 292), 0.42, COL_GREY)
        else:
            put_text(frame, "Sequence complete!  Press S to SAVE",
                     (20, 270), 0.55, COL_GREEN)

        draw_gesture_legend(frame, current_gesture)
        draw_status_bar(frame,
            f"Detected: {GESTURES[current_gesture]['name'] if current_gesture else 'No hand'}"
            f"  |  Press S to save  |  Press M for menu",
            COL_GREEN if current_gesture else COL_GREY)

        cv2.imshow("AuthentiAction", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('s') and len(captured) == SEQUENCE_LENGTH:
            save_profile(captured)
            show_result(cap, hands, success=True,
                        msg="Password Registered Successfully!")
            return

        if key == ord('m') or key == ord('q'):
            return


# ══════════════════════════════════════════════════════════════════
#  AUTHENTICATE MODE
# ══════════════════════════════════════════════════════════════════

def authenticate_mode(cap, hands):
    profile = load_profile()
    if not profile:
        print("\n⚠  No profile found. Please register first (press R).")
        return

    stored_hash    = profile["sequence_hash"]

    print("\n[ AUTHENTICATE ] Reproduce your gesture password pattern.\n")

    attempts     = 0
    captured     = []
    last_gesture = None
    hold_counter = 0
    last_reg_time   = 0

    while attempts < MAX_ATTEMPTS:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res   = hands.process(rgb)

        current_gesture = None
        if res.multi_hand_landmarks:
            hl = res.multi_hand_landmarks[0]
            mp_drawing.draw_landmarks(
                frame, hl, mp_hands.HAND_CONNECTIONS,
                mp_styles.get_default_hand_landmarks_style(),
                mp_styles.get_default_hand_connections_style())
            current_gesture = classify(hl.landmark)

        draw_bg(frame)
        draw_mode_badge(frame, "AUTHENTICATE")

        # ── Hold-to-register logic ───────────────────────────────
        now = time.time()
        if (current_gesture and
                current_gesture == last_gesture and
                now - last_reg_time > COOLDOWN_SECS and
                len(captured) < SEQUENCE_LENGTH):

            hold_counter += 1
            pct = int((hold_counter / HOLD_FRAMES) * 100)
            cx, cy, r = 320, 240, 48
            cv2.ellipse(frame, (cx, cy), (r, r), -90,
                        0, int(3.6 * pct), COL_BLUE, 6)
            put_text(frame, f"{pct}%", (cx-16, cy+8), 0.65, COL_BLUE)

            if hold_counter >= HOLD_FRAMES:
                captured.append(current_gesture)
                last_reg_time = now
                hold_counter  = 0

        else:
            if current_gesture != last_gesture:
                hold_counter    = 0
        last_gesture = current_gesture

        # ── Check if sequence complete ───────────────────────────
        if len(captured) == SEQUENCE_LENGTH:
            seq_match = hash_sequence(captured) == stored_hash

            if seq_match:
                show_result(cap, hands, success=True,
                            msg="ACCESS GRANTED — Welcome!")
                return
            else:
                attempts += 1
                remaining = MAX_ATTEMPTS - attempts
                reason = []
                if not seq_match:    reason.append("Wrong gesture sequence")
                print(f"\n❌ Attempt {attempts}/{MAX_ATTEMPTS} failed:")
                print(f"   Reason: {' + '.join(reason) if reason else 'Unknown'}")

                if attempts >= MAX_ATTEMPTS:
                    show_result(cap, hands, success=False,
                                msg=f"ACCESS DENIED — {MAX_ATTEMPTS} attempts exceeded")
                    return

                # Reset for next attempt
                captured        = []
                last_gesture    = None
                hold_counter    = 0
                last_reg_time   = 0
                show_flash(cap, "WRONG — Try again!", COL_RED)

        # ── Draw UI ──────────────────────────────────────────────
        draw_panel(frame, 10, 46, 440, 230)
        draw_sequence_slots(frame, captured, label="Enter Your Password")

        # Attempt counter
        for i in range(MAX_ATTEMPTS):
            col = COL_RED if i < attempts else (60, 60, 80)
            cv2.circle(frame, (20 + i*18, 278), 6, col, -1)
        put_text(frame, f"Attempts: {attempts}/{MAX_ATTEMPTS}",
                 (74, 282), 0.42, COL_GREY)

        draw_gesture_legend(frame, current_gesture)
        draw_status_bar(frame,
            f"Detected: {GESTURES[current_gesture]['name'] if current_gesture else 'No hand'}"
            f"  |  Gesture {len(captured)+1} of {SEQUENCE_LENGTH}  |  M=menu",
            COL_BLUE if current_gesture else COL_GREY)

        cv2.imshow("AuthentiAction", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('m') or key == ord('q'):
            return


# ══════════════════════════════════════════════════════════════════
#  RESULT & FLASH SCREENS
# ══════════════════════════════════════════════════════════════════

def show_flash(cap, msg, color, duration=1.2):
    t0 = time.time()
    while time.time() - t0 < duration:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        overlay = frame.copy()
        cv2.rectangle(overlay, (0,0), (frame.shape[1], frame.shape[0]), color, -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
        fw = cv2.getTextSize(msg, cv2.FONT_HERSHEY_DUPLEX, 1.1, 2)[0][0]
        put_text(frame, msg,
                 ((frame.shape[1]-fw)//2, frame.shape[0]//2),
                 1.1, COL_WHITE, 2)
        cv2.imshow("AuthentiAction", frame)
        cv2.waitKey(1)


def show_result(cap, hands, success, msg, duration=3.0):
    color = COL_GREEN if success else COL_RED
    icon  = "✔  " if success else "✘  "
    t0    = time.time()
    while time.time() - t0 < duration:
        ret, frame = cap.read()
        if not ret:
            break
        frame   = cv2.flip(frame, 1)
        overlay = frame.copy()
        cv2.rectangle(overlay, (0,0), (frame.shape[1], frame.shape[0]),
                      (10,10,14), -1)
        cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

        # Big icon
        cv2.circle(frame, (320, 200), 70, color, 4)
        fw = cv2.getTextSize(icon, cv2.FONT_HERSHEY_DUPLEX, 2.2, 3)[0][0]
        put_text(frame, icon, ((frame.shape[1]-fw)//2 - 10, 220), 2.2, color, 3)

        # Message
        mw = cv2.getTextSize(msg, cv2.FONT_HERSHEY_DUPLEX, 0.75, 1)[0][0]
        put_text(frame, msg, ((frame.shape[1]-mw)//2, 310), 0.75, COL_WHITE)

        remaining = int(duration - (time.time() - t0)) + 1
        put_text(frame, f"Returning to menu in {remaining}s...",
                 (180, 360), 0.42, COL_GREY)

        cv2.imshow("AuthentiAction", frame)
        cv2.waitKey(1)


# ══════════════════════════════════════════════════════════════════
#  MAIN MENU
# ══════════════════════════════════════════════════════════════════

def draw_menu(frame):
    draw_bg(frame)
    h, w = frame.shape[:2]

    # Title block
    cv2.rectangle(frame, (0, 0), (w, 50), (14, 14, 20), -1)
    put_text(frame, "AuthentiAction", (18, 32), 1.0, COL_GREEN, 2)
    put_text(frame, "Pattern-Based Gesture Authentication", (200, 32),
             0.5, COL_GREY)

    # Menu panel
    draw_panel(frame, w//2-160, 80, 320, 220, alpha=0.75)
    put_text(frame, "MAIN MENU", (w//2-56, 112), 0.62, COL_YELLOW)

    options = [
        ("R", "Register Password",    COL_YELLOW),
        ("A", "Authenticate",         COL_BLUE),
        ("Q", "Quit",                 COL_RED),
    ]
    for i, (key, label, col) in enumerate(options):
        y = 148 + i * 46
        cv2.rectangle(frame, (w//2-148, y-22),
                      (w//2+148, y+18), (30, 30, 40), -1)
        cv2.rectangle(frame, (w//2-148, y-22),
                      (w//2+148, y+18), col, 1)
        put_text(frame, f"[ {key} ]  {label}",
                 (w//2-120, y+4), 0.6, col)

    # Profile status
    profile = load_profile()
    if profile:
        put_text(frame, f"✔  Profile found — created {profile['created_at']}",
                 (20, h-60), 0.42, COL_GREEN)
    else:
        put_text(frame, "⚠  No profile found. Register first.",
                 (20, h-60), 0.42, COL_YELLOW)

    put_text(frame, "AuthentiAction  |  Behavioral Biometric Auth System",
             (20, h-20), 0.38, COL_GREY)


def main():
    print("\n" + "═"*60)
    print("  AuthentiAction — Rhythm-Aware Gesture Authentication")
    print("═"*60)
    print("  R → Register    A → Authenticate    Q → Quit")
    print("═"*60 + "\n")

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    with mp_hands.Hands(
        max_num_hands=1,
        min_detection_confidence=0.75,
        min_tracking_confidence=0.65,
    ) as hands:

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            draw_menu(frame)
            cv2.imshow("AuthentiAction", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('r'):
                register_mode(cap, hands)
            elif key == ord('a'):
                authenticate_mode(cap, hands)
            elif key == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()
    print("\n👋  AuthentiAction session ended.")


if __name__ == "__main__":
    main()
