# 🚀 AuthentiAction Flask Web App — Quick Start Guide

## ✅ What's Ready

Your gesture authentication system is **complete and ready to run**! Here's what was created:

### **Backend (Python/Flask)**

- ✅ `app.py` — Main Flask application with:
  - Live webcam video streaming (MJPEG format)
  - Hand gesture detection using MediaPipe
  - User authentication & registration endpoints
  - Session management
  - Gesture pattern hashing & storage

### **Frontend (HTML/CSS/JavaScript)**

- ✅ `templates/login.html` — Username entry & route selection
- ✅ `templates/register.html` — 4-gesture pattern capture with live video
- ✅ `templates/authenticate.html` — Gesture pattern verification with attempt tracking
- ✅ `templates/dashboard.html` — Post-authentication success page

### **Data Storage**

- ✅ `gesture_profiles/` — Directory for user profiles (auto-created)
- ✅ Each user's gesture pattern stored as hashed JSON

---

## 🎯 How to Test

### **Step 1: Start the Flask App**

```bash
cd d:\Coding\Personal Projects\files
python app.py
```

You should see:

```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

### **Step 2: Open in Browser**

Navigate to: **http://127.0.0.1:5000**

You'll see the **Login Page** with:

- Username input field
- Two buttons: **Register** and **Authenticate**

### **Step 3: Test Registration**

1. Enter a username (e.g., `testuser`)
2. Click **Register**
3. You'll see the **Registration Page** with:
   - Live webcam feed on the left
   - Progress slots (0/4) on the right
   - Gesture legend showing G1-G5
4. **Show your hand** to the camera
5. **Hold a gesture** for ~1 second (18 frames)
6. When ready, click **Save** to store your 4-gesture pattern

### **Step 4: Test Authentication**

1. Go back to login (click **Logout**)
2. Enter the same username
3. Click **Authenticate**
4. **Reproduce your 4-gesture pattern** in the exact same order
5. If it matches → **Dashboard** (success!)
6. If it doesn't match → Try again (3 attempts allowed)

---

## 🖐️ Gesture Guide for Testing

Make these hand shapes and hold them for ~1 second each:

| Gesture              | Shape                       | Demo                            |
| -------------------- | --------------------------- | ------------------------------- |
| **G1** (Index Up)    | Point with one finger ☝     | 🖐️ → close all except index     |
| **G2** (Pinch)       | Touch thumb + index tips 🤏 | Close your fingers into a pinch |
| **G3** (Two Fingers) | Peace sign ✌                | Extend index + middle only      |
| **G4** (Open Palm)   | Spread all fingers 🖐       | Open hand wide                  |
| **G5** (Fist)        | Closed fist ✊              | Make a tight fist               |

### **Example 4-Gesture Sequences to Try:**

1. G1 → G3 → G5 → G2 (simple progression)
2. G4 → G5 → G1 → G4 (opposite-to-same pattern)
3. G2 → G3 → G2 → G3 (alternating pinch & peace sign)

---

## 🎮 Expected User Flow

```
START
  ↓
LOGIN PAGE (http://localhost:5000)
  ├─→ Register Button
  │     ↓
  │   REGISTER PAGE
  │     ├─→ Show hand to camera
  │     ├─→ Hold 4 gestures in sequence
  │     ├─→ Click Save
  │     ↓
  │   Profile Saved ✅
  │     ↓
  │   DASHBOARD (logged in)
  │
  └─→ Authenticate Button
      ↓
    AUTHENTICATE PAGE
      ├─→ Show hand to camera
      ├─→ Reproduce 4-gesture pattern
      ├─→ Click Submit
      ├─→ Pattern Matches ✅
      ↓
    DASHBOARD (access granted)
```

---

## 📹 Camera Tips for Best Results

✅ **Do This:**

- Keep hand 30-50cm from camera
- Ensure good lighting (natural light preferred)
- Keep hand fully visible in the frame
- Hold gestures clearly and distinctly
- Make hand movements slow and deliberate

❌ **Avoid This:**

- Too close or too far from camera
- Poor lighting or shadows on hand
- Hand partially cut off from frame
- Sudden jerky movements
- Unclear/ambiguous finger positions

---

## 🔧 Troubleshooting

### **"No hand detected" in video feed**

- Check webcam is connected and working
- Check camera permissions in Windows Settings
- Ensure good lighting
- Position hand closer to camera

### **Gesture not capturing**

- Hold gesture for full ~1 second (should auto-capture)
- Ensure fingers are in correct positions
- Check that gesture is fully visible in video stream

### **Pattern mismatch on authenticate**

- Remember the exact order of your 4 gestures
- Reproduce gestures in the SAME order as registration
- Note: Only sequence matters, not timing

### **Camera permission denied**

Windows 10/11:

1. Settings → Privacy & Security → Camera
2. Enable camera access for Python/Flask

### **Flask app won't start**

- Check if port 5000 is already in use:
  ```bash
  netstat -ano | findstr :5000
  ```
- Try a different port in app.py:
  ```python
  app.run(host='127.0.0.1', port=5001, debug=True)
  ```

---

## 📊 What Happens Behind the Scenes

### **Registration Flow:**

1. User shows hand to camera
2. MediaPipe detects hand landmarks (21 points)
3. Flask classifies landmarks into G1-G5 gesture
4. Browser polls `/api/gesture` every 100ms
5. When gesture held for 18 frames → auto-captured
6. After 4 gestures captured → user clicks Save
7. Sequence hashed with SHA-256
8. Profile saved to `gesture_profiles/{username}.json`

### **Authentication Flow:**

1. User shows hand to camera
2. Same gesture detection process
3. 4 gestures captured in sequence
4. Sequence hashed and compared to stored hash
5. If hashes match → Access granted
6. If hashes don't match → Attempt counter increments
7. After 3 failed attempts → Locked out

---

## 📁 File Structure

```
d:\Coding\Personal Projects\files\
├── app.py                           ← Flask backend (RUN THIS)
├── authentiaction.py                ← Original desktop app (AuthentiAction)
├── templates/
│   ├── login.html                   ← Entry point
│   ├── register.html                ← Registration with webcam
│   ├── authenticate.html            ← Authentication with webcam
│   └── dashboard.html               ← Success page
├── gesture_profiles/                ← User profile storage
│   └── testuser.json                ← Example: {sequence_hash, created_at}
├── README_FLASK.md                  ← Full documentation
└── QUICKSTART.md                    ← This file
```

---

## 🔐 Security Notes

- **No passwords stored** — Only gesture sequences (as hashes)
- **SHA-256 hashing** — Patterns irreversible
- **Session-based** — Flask sessions track authenticated users
- **Pattern-only auth** — No timing dependency = more reliable
- **Local storage** — All profiles stored locally (JSON files)

---

## 🎯 Next Steps (Optional)

1. **Customize Gestures** — Edit `GESTURES` dict in `app.py` to rename/change emoji
2. **Add Database** — Replace JSON files with SQLite/PostgreSQL
3. **Deploy** — Use Gunicorn + Nginx for production
4. **Mobile Support** — Deploy Flask to server + access from phone camera
5. **Additional Features**:
   - Email notifications on new login
   - Gesture history/audit log
   - Multiple gesture passwords per user
   - Fallback authentication method

---

## ✨ You're All Set!

Your gesture authentication system is **fully functional and ready to use**.

**To start:** Run `python app.py` and navigate to `http://127.0.0.1:5000`

Enjoy your biometric gesture authentication! 🚀

---

**Questions?** Check `README_FLASK.md` for complete API documentation.
