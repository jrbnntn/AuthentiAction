"""
AuthentiAction — Web-Based Gesture Authentication with Live Webcam
Pattern-Based Gesture Passwordless Security System
Real-time hand gesture detection via WebRTC
"""

import streamlit as st
import json
import os
import hashlib
import numpy as np
import cv2
import av
from datetime import datetime
from pathlib import Path
from streamlit_webrtc import webrtc_streamer, RTCConfiguration, WebRtcMode, WebRtcStreamerContext
from av.video.frame import VideoFrame
import mediapipe as mp
import threading

# ── MediaPipe Setup ──────────────────────────────────────────────────────────
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles

# ── Constants ────────────────────────────────────────────────────────────────
PROFILE_DIR = "gesture_profiles"
SEQUENCE_LENGTH = 4
HOLD_FRAMES = 18  # Frames to hold for gesture to register
MAX_ATTEMPTS = 3
COOLDOWN_FRAMES = 8  # Frames between gesture captures

# Gesture definitions
GESTURES = {
    "G1": {"name": "Index Up", "emoji": "☝", "desc": "Only index finger extended"},
    "G2": {"name": "Pinch", "emoji": "🤏", "desc": "Thumb + index tips touching"},
    "G3": {"name": "Two Fingers", "emoji": "✌", "desc": "Index + middle extended"},
    "G4": {"name": "Open Palm", "emoji": "🖐", "desc": "All 5 fingers extended"},
    "G5": {"name": "Fist", "emoji": "✊", "desc": "All fingers folded"},
}

RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun1.l.google.com:19302"]}]}
)


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


# ── Streamlit Session State ──────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "login"
if "username" not in st.session_state:
    st.session_state.username = ""
if "captured" not in st.session_state:
    st.session_state.captured = []
if "attempts" not in st.session_state:
    st.session_state.attempts = 0
if "last_gesture" not in st.session_state:
    st.session_state.last_gesture = None
if "hold_counter" not in st.session_state:
    st.session_state.hold_counter = 0
if "cooldown_counter" not in st.session_state:
    st.session_state.cooldown_counter = 0


def set_page(page_name):
    st.session_state.page = page_name


def logout():
    st.session_state.page = "login"
    st.session_state.username = ""
    st.session_state.captured = []
    st.session_state.attempts = 0


# ──────────────────────────────────────────────────────────────────────────────
#  GESTURE PROCESSOR FOR WEBRTC
# ──────────────────────────────────────────────────────────────────────────────
class GestureVideoProcessor:
    def __init__(self):
        self.hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.3,
        )
        self.current_gesture = None
        self.hold_frames = 0
        self.gesture_info = {}

    def process_frame(self, frame: av.VideoFrame) -> av.VideoFrame:
        """Process video frame and detect gestures."""
        img = frame.to_ndarray(format="bgr24")
        h, w, c = img.shape

        # Convert BGR to RGB for MediaPipe
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Detect hand landmarks
        result = self.hands.process(rgb_img)
        annotated = img.copy()
        self.current_gesture = None

        # Draw hand landmarks if detected
        if result.multi_hand_landmarks:
            hl = result.multi_hand_landmarks[0]
            mp_drawing.draw_landmarks(
                annotated,
                hl,
                mp_hands.HAND_CONNECTIONS,
                mp_styles.get_default_hand_landmarks_style(),
                mp_styles.get_default_hand_connections_style(),
            )
            self.current_gesture = classify(hl.landmark)

            # Add gesture label
            if self.current_gesture:
                gesture_name = GESTURES[self.current_gesture]["name"]
                emoji = GESTURES[self.current_gesture]["emoji"]
                cv2.putText(
                    annotated,
                    f"{emoji} {self.current_gesture}: {gesture_name}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 220, 130),
                    2,
                )
        else:
            cv2.putText(
                annotated,
                "No hand detected",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (100, 100, 100),
                2,
            )

        # Store gesture info for session state
        self.gesture_info = {"gesture": self.current_gesture}

        return av.VideoFrame.from_ndarray(annotated, format="bgr24")


# ──────────────────────────────────────────────────────────────────────────────
#  LOGIN PAGE
# ──────────────────────────────────────────────────────────────────────────────
def page_login():
    st.set_page_config(page_title="AuthentiAction - Login", layout="centered")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style='text-align: center; padding: 20px 0;'>
                <h1 style='color: #00dc82; font-size: 2.5em; margin: 0;'>🔐 AuthentiAction</h1>
                <p style='color: #888; font-size: 0.95em; margin: 5px 0;'>Pattern-Based Gesture Authentication</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                        padding: 30px; border-radius: 12px; border: 1px solid #00dc82;'>
            """,
            unsafe_allow_html=True,
        )

        username = st.text_input(
            "👤 Username",
            key="login_username",
            placeholder="Enter your username",
        )

        col_reg, col_auth = st.columns(2)

        with col_reg:
            if st.button("📝 Register", use_container_width=True):
                if username.strip():
                    st.session_state.username = username
                    st.session_state.page = "register"
                    st.rerun()
                else:
                    st.error("Please enter a username")

        with col_auth:
            if st.button("✓ Authenticate", use_container_width=True):
                if username.strip():
                    if profile_exists(username):
                        st.session_state.username = username
                        st.session_state.page = "authenticate"
                        st.rerun()
                    else:
                        st.error(f"No profile for '{username}'. Register first!")
                else:
                    st.error("Please enter a username")

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(
            """
            <p style='text-align: center; color: #888; font-size: 0.85em;'>
                🎯 Register your 4-gesture password pattern<br>
                🔒 Authenticate with the same pattern to gain access<br>
                📹 Real-time webcam hand detection
            </p>
            """,
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────────────────────────────────────
#  GESTURE DISPLAY
# ──────────────────────────────────────────────────────────────────────────────
def draw_gesture_slots(captured, total=SEQUENCE_LENGTH):
    """Display gesture sequence progress."""
    st.markdown("### 🎯 Gesture Sequence Progress")

    cols = st.columns(total)
    for i, col in enumerate(cols):
        with col:
            if i < len(captured):
                g = captured[i]
                emoji = GESTURES[g]["emoji"]
                name = GESTURES[g]["name"]
                st.markdown(
                    f"""
                    <div style='text-align: center; padding: 15px; 
                                background: linear-gradient(135deg, #00dc82 0%, #00a86b 100%);
                                border-radius: 10px; color: white; font-weight: bold;'>
                        <div style='font-size: 1.8em; margin: 10px 0;'>{emoji}</div>
                        <div style='font-size: 0.85em;'>{g}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div style='text-align: center; padding: 15px; 
                                background: #333; border: 2px dashed #666;
                                border-radius: 10px; color: #666; font-weight: bold;'>
                        <div style='font-size: 1.8em; margin: 10px 0;'>❓</div>
                        <div style='font-size: 0.85em;'>Gesture {i+1}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def draw_gesture_legend():
    """Display available gestures."""
    st.markdown("### 🖐️ Available Gestures")
    cols = st.columns(5)
    for idx, (key, info) in enumerate(GESTURES.items()):
        with cols[idx]:
            st.markdown(
                f"""
                <div style='text-align: center; padding: 10px; background: #222; 
                            border-radius: 8px; font-size: 0.9em;'>
                    <div style='font-size: 1.5em;'>{info['emoji']}</div>
                    <div style='font-weight: bold; color: #00dc82;'>{key}</div>
                    <div style='color: #888; font-size: 0.75em;'>{info['name']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER PAGE WITH LIVE WEBCAM
# ──────────────────────────────────────────────────────────────────────────────
def page_register():
    st.set_page_config(page_title="AuthentiAction - Register", layout="wide")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"""
            <div style='text-align: center; padding: 15px 0;'>
                <h2 style='color: #00dc82; margin: 0;'>📝 Register Gesture Password</h2>
                <p style='color: #888; margin: 10px 0;'>User: <strong>{st.session_state.username}</strong></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    draw_gesture_legend()
    st.markdown("---")
    draw_gesture_slots(st.session_state.captured)
    st.markdown("---")

    # Webcam setup
    st.markdown("### 📹 Live Gesture Capture")
    st.info(
        f"🎥 **Show your hand gestures to the camera**\n\n"
        f"Hold each gesture steady for ~1 second to capture it.\n"
        f"Progress: {len(st.session_state.captured)}/{SEQUENCE_LENGTH} gestures captured"
    )

    col_cam, col_info = st.columns([2, 1])

    with col_cam:
        # Create gesture processor instance
        gesture_processor = GestureVideoProcessor()

        # WebRTC streamer with video processor
        rtc_ctx = webrtc_streamer(
            key="register-gesture-capture",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=RTC_CONFIGURATION,
            media_stream_constraints={"audio": False, "video": True},
            video_processor_factory=lambda: gesture_processor,
            async_processing=False,
        )

        # Status placeholder
        status_placeholder = col_info.empty()

    with col_info:
        st.markdown("### 📊 Status")
        if len(st.session_state.captured) > 0:
            for i, g in enumerate(st.session_state.captured):
                st.success(f"✓ {i+1}. {GESTURES[g]['emoji']} {g}")

        remaining = SEQUENCE_LENGTH - len(st.session_state.captured)
        if remaining > 0:
            st.warning(f"⏳ {remaining} more gesture{'s' if remaining != 1 else ''} needed")
        else:
            st.success("✅ All gestures captured!")

        # Gesture detection logic
        if rtc_ctx.state.playing:
            detected_gesture = gesture_processor.gesture_info.get("gesture")
            if detected_gesture:
                st.info(f"🎯 **Detected**: {GESTURES[detected_gesture]['emoji']} {detected_gesture}")

                # Gesture hold logic
                if detected_gesture == st.session_state.last_gesture:
                    st.session_state.hold_counter += 1
                    pct = int((st.session_state.hold_counter / HOLD_FRAMES) * 100)
                    st.progress(pct / 100, f"Hold: {pct}%")

                    if (
                        st.session_state.hold_counter >= HOLD_FRAMES
                        and st.session_state.cooldown_counter == 0
                        and len(st.session_state.captured) < SEQUENCE_LENGTH
                    ):
                        st.session_state.captured.append(detected_gesture)
                        st.session_state.hold_counter = 0
                        st.session_state.cooldown_counter = COOLDOWN_FRAMES
                        st.session_state.last_gesture = None
                        st.rerun()
                else:
                    st.session_state.last_gesture = detected_gesture
                    st.session_state.hold_counter = 0

                if st.session_state.cooldown_counter > 0:
                    st.session_state.cooldown_counter -= 1
            else:
                st.warning("No hand detected")

    st.markdown("---")

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.captured = []
            st.rerun()

    with col2:
        if len(st.session_state.captured) == SEQUENCE_LENGTH:
            if st.button("✅ Save Profile", use_container_width=True):
                save_profile(st.session_state.username, st.session_state.captured)
                st.balloons()
                st.success(
                    f"✅ Profile saved!\n\n"
                    f"Your gesture password: {' → '.join([GESTURES[g]['emoji'] for g in st.session_state.captured])}"
                )
                st.session_state.page = "login"
                st.session_state.captured = []
                st.rerun()
        else:
            st.info(f"⏳ Capture {SEQUENCE_LENGTH - len(st.session_state.captured)} more...")

    with col3:
        if st.button("❌ Cancel", use_container_width=True):
            logout()
            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
#  AUTHENTICATE PAGE WITH LIVE WEBCAM
# ──────────────────────────────────────────────────────────────────────────────
def page_authenticate():
    st.set_page_config(page_title="AuthentiAction - Authenticate", layout="wide")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"""
            <div style='text-align: center; padding: 15px 0;'>
                <h2 style='color: #00a8ff; margin: 0;'>🔓 Authenticate</h2>
                <p style='color: #888; margin: 10px 0;'>User: <strong>{st.session_state.username}</strong></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    draw_gesture_legend()
    st.markdown("---")
    draw_gesture_slots(st.session_state.captured)
    st.markdown("---")

    # Webcam setup
    st.markdown("### 📹 Live Gesture Verification")
    st.info(
        f"🎥 **Reproduce your gesture password**\n\n"
        f"Show your hand gestures in the same order you registered.\n"
        f"Progress: {len(st.session_state.captured)}/{SEQUENCE_LENGTH} gestures\n"
        f"Attempts: {st.session_state.attempts}/{MAX_ATTEMPTS}"
    )

    col_cam, col_info = st.columns([2, 1])

    with col_cam:
        # Create gesture processor instance
        gesture_processor = GestureVideoProcessor()

        # WebRTC streamer with video processor
        rtc_ctx = webrtc_streamer(
            key="auth-gesture-capture",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=RTC_CONFIGURATION,
            media_stream_constraints={"audio": False, "video": True},
            video_processor_factory=lambda: gesture_processor,
            async_processing=False,
        )

    with col_info:
        st.markdown("### 📊 Status")
        for i, g in enumerate(st.session_state.captured):
            st.success(f"✓ {i+1}. {GESTURES[g]['emoji']} {g}")

        if len(st.session_state.captured) < SEQUENCE_LENGTH:
            remaining = SEQUENCE_LENGTH - len(st.session_state.captured)
            st.warning(f"⏳ {remaining} more gesture{'s' if remaining != 1 else ''} needed")

        # Gesture detection logic
        if rtc_ctx.state.playing:
            detected_gesture = gesture_processor.gesture_info.get("gesture")
            if detected_gesture:
                st.info(f"🎯 **Detected**: {GESTURES[detected_gesture]['emoji']} {detected_gesture}")

                # Gesture hold logic
                if detected_gesture == st.session_state.last_gesture:
                    st.session_state.hold_counter += 1
                    pct = int((st.session_state.hold_counter / HOLD_FRAMES) * 100)
                    st.progress(pct / 100, f"Hold: {pct}%")

                    if (
                        st.session_state.hold_counter >= HOLD_FRAMES
                        and st.session_state.cooldown_counter == 0
                        and len(st.session_state.captured) < SEQUENCE_LENGTH
                    ):
                        st.session_state.captured.append(detected_gesture)
                        st.session_state.hold_counter = 0
                        st.session_state.cooldown_counter = COOLDOWN_FRAMES
                        st.session_state.last_gesture = None
                        st.rerun()
                else:
                    st.session_state.last_gesture = detected_gesture
                    st.session_state.hold_counter = 0

                if st.session_state.cooldown_counter > 0:
                    st.session_state.cooldown_counter -= 1
            else:
                st.warning("No hand detected")

    st.markdown("---")

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.captured = []
            st.session_state.attempts = 0
            st.rerun()

    with col2:
        if len(st.session_state.captured) == SEQUENCE_LENGTH:
            if st.button("✓ Submit", use_container_width=True):
                # Load profile and check
                profile = load_profile(st.session_state.username)
                stored_hash = profile["sequence_hash"]
                current_hash = hash_sequence(st.session_state.captured)

                if current_hash == stored_hash:
                    st.balloons()
                    st.success(
                        f"✅ ACCESS GRANTED!\n\n"
                        f"Welcome back, {st.session_state.username}! 🎉\n\n"
                        f"Your gesture pattern matched perfectly."
                    )
                    st.session_state.page = "dashboard"
                    st.rerun()
                else:
                    st.session_state.attempts += 1
                    if st.session_state.attempts >= MAX_ATTEMPTS:
                        st.error(
                            f"❌ ACCESS DENIED\n\n"
                            f"Maximum attempts exceeded ({MAX_ATTEMPTS}/{MAX_ATTEMPTS})."
                        )
                        if st.button("Return to Login"):
                            logout()
                            st.rerun()
                    else:
                        remaining = MAX_ATTEMPTS - st.session_state.attempts
                        st.error(
                            f"❌ INCORRECT PATTERN\n\n"
                            f"Attempts remaining: {remaining}/{MAX_ATTEMPTS}"
                        )
                        st.session_state.captured = []
                        st.rerun()

    with col3:
        if st.button("❌ Cancel", use_container_width=True):
            logout()
            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
#  DASHBOARD PAGE (After Successful Auth)
# ──────────────────────────────────────────────────────────────────────────────
def page_dashboard():
    st.set_page_config(page_title="AuthentiAction - Dashboard", layout="wide")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"""
            <div style='text-align: center; padding: 20px 0;'>
                <h1 style='color: #00dc82; margin: 0;'>✅ Welcome, {st.session_state.username}!</h1>
                <p style='color: #888; margin: 10px 0;'>You have been successfully authenticated</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            ### 🎯 Authentication Details
            - **Status**: ✅ Authenticated
            - **Method**: Real-time Gesture Recognition
            - **Gestures**: 4-Gesture Sequence
            - **Security**: Pattern-Based (SHA-256)
            - **Detection**: Live Webcam with MediaPipe
            """
        )

    with col2:
        profile = load_profile(st.session_state.username)
        st.markdown(
            f"""
            ### 📋 Profile Information
            - **Username**: {st.session_state.username}
            - **Created**: {profile['created_at'].split('T')[0]}
            - **Pattern Hash**: {profile['sequence_hash'][:16]}...
            - **Auth Method**: Gesture Pattern
            """
        )

    st.markdown("---")

    st.markdown("### 🔐 Session Actions")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Update Gesture Password", use_container_width=True):
            st.session_state.page = "register"
            st.session_state.captured = []
            st.rerun()

    with col2:
        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()

    st.markdown("---")
    st.markdown(
        """
        <p style='text-align: center; color: #888; font-size: 0.9em;'>
            🔒 Your gesture password is securely hashed and stored.<br>
            Real-time webcam detection with MediaPipe hand tracking.
        </p>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN APP ROUTING
# ──────────────────────────────────────────────────────────────────────────────
def main():
    # Dark theme styling
    st.markdown(
        """
        <style>
            body { background: linear-gradient(135deg, #0f0f1e 0%, #1a1a2e 100%); color: #fff; }
            .stButton > button { border-radius: 8px; border: 1px solid #00dc82; background: linear-gradient(135deg, #00dc82 0%, #00a86b 100%); color: black; font-weight: bold; }
            .stButton > button:hover { box-shadow: 0 0 20px rgba(0, 220, 130, 0.5); }
            .stTextInput > div > div > input { background: #222; border: 1px solid #00dc82; color: #fff; border-radius: 8px; }
            .stInfo { background: linear-gradient(135deg, #1a3a2e 0%, #0f2e1e 100%); border-left: 4px solid #00dc82; }
            .stSuccess { background: linear-gradient(135deg, #1a3a2e 0%, #0f2e1e 100%); border-left: 4px solid #00dc82; }
            .stError { background: linear-gradient(135deg, #3a1a1e 0%, #2e0f0f 100%); border-left: 4px solid #ff5555; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.page == "login":
        page_login()
    elif st.session_state.page == "register":
        page_register()
    elif st.session_state.page == "authenticate":
        page_authenticate()
    elif st.session_state.page == "dashboard":
        page_dashboard()


if __name__ == "__main__":
    main()
