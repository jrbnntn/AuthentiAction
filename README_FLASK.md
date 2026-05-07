# AuthentiAction — Flask Web App

A **Pattern-Based Gesture Authentication System** with **real-time webcam hand detection** using Flask, OpenCV, and MediaPipe.

## 📋 Features

✅ **Real-time Hand Detection** — Live webcam feed with MediaPipe gesture recognition  
✅ **User Registration** — Register a 4-gesture password pattern  
✅ **Gesture Authentication** — Authenticate by reproducing your gesture sequence  
✅ **Pattern-Only Auth** — No timing dependency, just gesture sequence matching  
✅ **Session Management** — Secure login and logout  
✅ **User Profiles** — Store hashed gesture patterns in JSON files

## 🚀 How to Run

### 1. Install Dependencies

```bash
pip install flask opencv-python mediapipe
```

### 2. Run the Flask App

```bash
python app.py
```

### 3. Open in Browser

Navigate to: **http://127.0.0.1:5000**

## 🎮 Usage

### **1. Login Page** (`/login`)

- Enter your username
- Choose: **Register** (create new gesture password) or **Authenticate** (login)

### **2. Register Flow** (`/register`)

- Your **webcam feed** appears live
- **Show your hand** to the camera
- **Hold each gesture** for ~1 second to capture it
- System detects 5 gestures: G1, G2, G3, G4, G5
- Capture **4 gestures** in sequence
- Click **Save** to store your profile

### **3. Authenticate Flow** (`/authenticate`)

- Show your hand to the camera
- **Reproduce your 4-gesture pattern** in the correct order
- 3 attempts allowed
- Pattern must match exactly (order matters)
- **Successful match** grants access to dashboard

### **4. Dashboard** (`/dashboard`)

- Post-authentication success page
- View profile details and gesture pattern info
- Options to update password or logout

## 🖐️ Available Gestures

| Gesture | Name        | Emoji | Description                 |
| ------- | ----------- | ----- | --------------------------- |
| **G1**  | Index Up    | ☝     | Only index finger extended  |
| **G2**  | Pinch       | 🤏    | Thumb + index tips touching |
| **G3**  | Two Fingers | ✌     | Index + middle extended     |
| **G4**  | Open Palm   | 🖐    | All 5 fingers extended      |
| **G5**  | Fist        | ✊    | All fingers folded          |

## 📁 Project Structure

```
├── app.py                          # Flask main application
├── templates/
│   ├── login.html                  # Login page
│   ├── register.html               # Registration with webcam
│   ├── authenticate.html           # Authentication with webcam
│   └── dashboard.html              # Post-auth dashboard
├── gesture_profiles/               # User profile storage (auto-created)
│   └── {username}.json             # User gesture hash
└── requirements.txt                # (optional) Python dependencies
```

## 🔐 Security Features

- **SHA-256 Hashing** — Gesture sequences are hashed and stored securely
- **Session Management** — User sessions tracked via Flask sessions
- **Pattern-Based** — Only the gesture sequence order matters, no timing
- **Multi-Attempt Protection** — Max 3 attempts before lockout

## 📹 Webcam Requirements

- **Webcam/Camera Device** — Must have a working webcam
- **Lighting** — Good lighting conditions improve detection accuracy
- **Hand Visibility** — Keep your hand fully visible to the camera
- **Distance** — Position hand ~30-50cm from camera

## 🛠️ Technical Stack

- **Framework**: Flask (Python web framework)
- **Computer Vision**: OpenCV + MediaPipe (hand detection)
- **Frontend**: HTML5 + CSS3 + Vanilla JavaScript
- **Backend**: Python 3.8+
- **Video Streaming**: MJPEG (Motion JPEG)

## 📝 API Endpoints

| Endpoint        | Method   | Purpose                             |
| --------------- | -------- | ----------------------------------- |
| `/`             | GET      | Redirect to login/dashboard         |
| `/login`        | POST     | Handle login                        |
| `/register`     | GET/POST | Register gesture password           |
| `/authenticate` | GET/POST | Authenticate with gesture           |
| `/dashboard`    | GET      | View dashboard (post-auth)          |
| `/video_feed`   | GET      | Stream webcam video (MJPEG)         |
| `/api/gesture`  | GET      | Get current detected gesture (JSON) |
| `/logout`       | GET      | Clear session and logout            |

## 🎯 Gesture Detection Logic

1. **Frame Capture** — 30 FPS webcam stream
2. **Hand Detection** — MediaPipe detects hand landmarks
3. **Gesture Classification** — Analyzes finger positions:
   - **G1**: Index extended only
   - **G2**: Pinch (thumb + index close)
   - **G3**: Two fingers (index + middle)
   - **G4**: Open palm (5 fingers)
   - **G5**: Fist (all fingers folded)
4. **Hold Detection** — Gesture must be held ~1 second (18 frames @ 18 FPS)
5. **Capture** — Auto-captures when hold time reached

## ⚠️ Troubleshooting

### Webcam Not Detected

- Check if camera device is connected
- Verify camera permissions in OS settings
- Try restarting the app

### Poor Hand Detection

- Ensure good lighting (natural light preferred)
- Keep hand fully visible in frame
- Adjust hand distance from camera (30-50cm optimal)
- Make sure gestures are distinct and held clearly

### Gesture Not Capturing

- Hold gesture steady for full ~1 second
- Ensure finger positions match gesture definition
- Check hand is fully in camera view

## 📦 Optional: requirements.txt

```
Flask==3.1.1
opencv-python==4.11.0.86
mediapipe==0.10.20
```

Install all at once:

```bash
pip install -r requirements.txt
```

## 🎓 Example Workflow

1. **Register**:

   ```
   Username: john_doe
   Gesture Sequence: G1 → G3 → G5 → G2
   Profile Saved ✅
   ```

2. **Authenticate**:

   ```
   Username: john_doe
   Input: G1 → G3 → G5 → G2
   Pattern Matched ✅ Access Granted!
   ```

3. **Failed Attempt**:
   ```
   Username: john_doe
   Input: G1 → G2 → G5 → G2
   Pattern Mismatch ❌ (2 attempts remaining)
   ```

## 📞 Notes

- The Flask app runs in **debug mode** (`debug=True`) for development
- For production, set `debug=False` and use a production WSGI server (gunicorn)
- Gesture profiles are stored in `gesture_profiles/` directory as JSON files
- Each user has their own profile file: `{username}.json`

---

**Made with ❤️ for pattern-based biometric authentication**
