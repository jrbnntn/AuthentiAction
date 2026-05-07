"""
AuthentiAction — Flask Web App with Live Webcam
Pattern-Based Gesture Authentication System
Real-time hand gesture detection with OpenCV + MediaPipe
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import cv2
import mediapipe as mp
import numpy as np
import json
import os
import hashlib
from datetime import datetime
import threading
from collections import deque

# ── MediaPipe Setup ──────────────────────────────────────────────────────────
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles

# ── Flask Setup ──────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = 'gesturekey_secret_2026'
PROFILE_DIR = "gesture_profiles"

# ── Constants ────────────────────────────────────────────────────────────────
SEQUENCE_LENGTH = 4
HOLD_FRAMES = 18
MAX_ATTEMPTS = 3
COOLDOWN_FRAMES = 8

# Gesture definitions
GESTURES = {
    "G1": {"name": "Index Up", "emoji": "☝", "desc": "Only index finger extended"},
    "G2": {"name": "Pinch", "emoji": "🤏", "desc": "Thumb + index tips touching"},
    "G3": {"name": "Two Fingers", "emoji": "✌", "desc": "Index + middle extended"},
    "G4": {"name": "Open Palm", "emoji": "🖐", "desc": "All 5 fingers extended"},
    "G5": {"name": "Fist", "emoji": "✊", "desc": "All fingers folded"},
}

# Global gesture processor
gesture_buffer = deque(maxlen=10)
current_gesture_state = {"gesture": None, "hold_count": 0}


# ── Gesture Classification ───────────────────────────────────────────────────
def fingers_up(lm):
    """Returns [thumb, index, middle, ring, pinky] — 1=extended, 0=folded."""
    tips = [4, 8, 12, 16, 20]
    up = []
    up.append(1 if lm[tips[0]].x < lm[tips[0] - 1].x else 0)
    for i in range(1, 5):
        up.append(1 if lm[tips[i]].y < lm[tips[i] - 2].y else 0)
    return up


def pinch_dist(lm):
    """Normalised Euclidean distance between thumb tip and index tip."""
    t, i = lm[4], lm[8]
    return np.hypot(t.x - i.x, t.y - i.y)


def classify(lm):
    """Returns gesture key string: G1–G5 or None."""
    up = fingers_up(lm)
    pinch = pinch_dist(lm)
    th, ix, mid, rng, pnk = up

    if sum(up) == 5:
        return "G4"
    if sum(up) == 0:
        return "G5"
    if pinch < 0.06 and mid == 0 and rng == 0 and pnk == 0:
        return "G2"
    if ix == 1 and mid == 1 and rng == 0 and pnk == 0:
        return "G3"
    if ix == 1 and mid == 0 and rng == 0 and pnk == 0:
        return "G1"
    return None


# ── Profile Management ───────────────────────────────────────────────────────
def hash_sequence(seq):
    raw = "-".join(seq).encode()
    return hashlib.sha256(raw).hexdigest()


def ensure_profile_dir():
    if not os.path.exists(PROFILE_DIR):
        os.makedirs(PROFILE_DIR)


def save_profile(username, sequence):
    ensure_profile_dir()
    profile_path = os.path.join(PROFILE_DIR, f"{username}.json")
    data = {
        "username": username,
        "sequence_hash": hash_sequence(sequence),
        "created_at": datetime.now().isoformat(),
    }
    with open(profile_path, "w") as f:
        json.dump(data, f, indent=2)


def load_profile(username):
    ensure_profile_dir()
    profile_path = os.path.join(PROFILE_DIR, f"{username}.json")
    if not os.path.exists(profile_path):
        return None
    with open(profile_path) as f:
        return json.load(f)


def profile_exists(username):
    ensure_profile_dir()
    return os.path.exists(os.path.join(PROFILE_DIR, f"{username}.json"))


# ── Video Frame Generator ────────────────────────────────────────────────────
def generate_frames():
    """Generate video frames with gesture detection."""
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.3,
    )
    cap = cv2.VideoCapture(0)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        h, w, c = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Process gestures
        result = hands.process(rgb_frame)
        current_gesture = None

        if result.multi_hand_landmarks:
            hl = result.multi_hand_landmarks[0]
            mp_drawing.draw_landmarks(
                frame,
                hl,
                mp_hands.HAND_CONNECTIONS,
                mp_styles.get_default_hand_landmarks_style(),
                mp_styles.get_default_hand_connections_style(),
            )
            current_gesture = classify(hl.landmark)

        # Draw gesture info
        if current_gesture:
            gesture_name = GESTURES[current_gesture]["name"]
            emoji = GESTURES[current_gesture]["emoji"]
            cv2.putText(
                frame,
                f"{emoji} {current_gesture}: {gesture_name}",
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 220, 130),
                2,
            )
        else:
            cv2.putText(
                frame,
                "No hand detected",
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (100, 100, 100),
                2,
            )

        # Store current gesture
        gesture_buffer.append(current_gesture)
        current_gesture_state["gesture"] = current_gesture

        # Encode frame to JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


# ──────────────────────────────────────────────────────────────────────────────
#  ROUTES
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()

        if not username:
            return jsonify({"success": False, "error": "Username required"}), 400

        session['username'] = username
        session['page'] = 'login'
        return jsonify({"success": True})

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = request.get_json()
        sequence = data.get('sequence', [])

        if len(sequence) != SEQUENCE_LENGTH:
            return jsonify({"success": False, "error": "Invalid sequence length"}), 400

        username = session['username']
        save_profile(username, sequence)
        
        session['authenticated'] = True
        return jsonify({"success": True})

    return render_template('register.html', gestures=GESTURES, sequence_length=SEQUENCE_LENGTH)


@app.route('/authenticate', methods=['GET', 'POST'])
def authenticate():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    if not profile_exists(username):
        return redirect(url_for('register'))

    if request.method == 'POST':
        data = request.get_json()
        sequence = data.get('sequence', [])

        profile = load_profile(username)
        stored_hash = profile["sequence_hash"]
        current_hash = hash_sequence(sequence)

        if current_hash == stored_hash:
            session['authenticated'] = True
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Pattern mismatch"}), 401

    return render_template('authenticate.html', gestures=GESTURES, sequence_length=SEQUENCE_LENGTH, max_attempts=MAX_ATTEMPTS)


@app.route('/dashboard')
def dashboard():
    if 'authenticated' not in session or not session['authenticated']:
        return redirect(url_for('login'))

    username = session.get('username', 'User')
    profile = load_profile(username)

    return render_template('dashboard.html', username=username, profile=profile, gestures=GESTURES)


@app.route('/video_feed')
def video_feed():
    """Stream video frames."""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/gesture')
def api_gesture():
    """Get current detected gesture."""
    gesture = current_gesture_state.get("gesture")
    return jsonify({
        "gesture": gesture,
        "emoji": GESTURES[gesture]["emoji"] if gesture else None,
        "name": GESTURES[gesture]["name"] if gesture else None,
    })


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ──────────────────────────────────────────────────────────────────────────────
#  ERROR HANDLING
# ──────────────────────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(error):
    return redirect(url_for('login'))


@app.errorhandler(500)
def server_error(error):
    return "Server error", 500


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    from flask import Response
    app.run(debug=True, host='127.0.0.1', port=5000)
