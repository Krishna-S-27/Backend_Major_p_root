# Violence Detection API

This project is a FastAPI backend for detecting violence in uploaded video files. It loads a TensorFlow H5 model, samples 16 frames from each input video, preprocesses them to `224x224`, runs inference, and returns a JSON prediction with confidence and timing details.

The API is built for mobile apps or web clients that can upload a video file through HTTP multipart requests. It also includes JWT-based authentication, incident tracking, OTP verification, and Google Drive upload support for violent incident recordings.

## Features

- Batch video prediction through `POST /predict`
- Real-time frame-buffer prediction via `POST /predict-realtime`
- JWT authentication with `/auth/register`, `/auth/login`, and `/auth/profile`
- User incident history and admin endpoints under `/api/v1/*`
- Health (`/health`) and stats (`/stats`) endpoints
- Google Drive upload support for violent incidents when configured
- Dev-mode OTP delivery fallback for email/SMS verification

## Current Project Structure

```text
.
├── .gitignore
├── README.md
├── main.py
├── requirements.txt
├── test_api.py
├── app/
│   ├── __init__.py
│   ├── auth.py
│   ├── database.py
│   ├── database_models.py
│   ├── google_drive.py
│   ├── models.py
│   ├── notifications.py
│   ├── repository/
│   ├── routes/
│   ├── schemas/
│   ├── services/
│   └── utils/
└── exports_v2/
    └── exports_v2/
        └── violence_model_v2.h5
```

## Requirements

- Python 3.10 or newer
- TensorFlow 2.21.0
- OpenCV 4.x
- FastAPI
- Uvicorn
- SQLAlchemy and PyMySQL
- JWT, password hashing, dotenv, and Google API clients

Install the exact dependencies from `requirements.txt`:

```powershell
pip install -r requirements.txt
```

## Setup

Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Ensure the model file exists at:

```text
exports_v2/exports_v2/violence_model_v2.h5
```

## Environment Variables

Create a `.env` file with at least these values:

```text
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DATABASE_URL=mysql+pymysql://user:pass@host/dbname
JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-email-password
TWILIO_SID=your_twilio_sid
TWILIO_TOKEN=your_twilio_token
TWILIO_PHONE=+1234567890
```

Only add real SMTP/Twilio credentials for production.

## Run the API

Start the FastAPI server:

```powershell
uvicorn main:app --reload
```

Open the API docs at:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Main Endpoints

### Health Check

```http
GET /health
```

Returns service health and whether the model is loaded.

### Runtime Stats

```http
GET /stats
```

Returns model and server configuration details.

### Batch Video Prediction

```http
POST /predict
```

Requires a valid Bearer token in the `Authorization` header.

Upload a video file using multipart form data with field name `file`.

### Real-time Prediction

```http
POST /predict-realtime
```

Accepts a serialized frame buffer for `1 x 16 x 224 x 224 x 3` input.

### Authentication

```http
POST /auth/register
POST /auth/login
GET /auth/profile
```

### Incident Management (authenticated)

- `GET /api/v1/incidents`
- `GET /api/v1/incidents/{incident_id}`
- `DELETE /api/v1/incidents/{incident_id}`
- `GET /api/v1/incidents/statistics`

### Admin Endpoints

- `GET /api/v1/admin/dashboard`
- `GET /api/v1/admin/users`

## Example Requests

### Login

```powershell
curl.exe -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"your_username\",\"password\":\"your_password\"}"
```

### Register

```http
POST /auth/register
```

```json
{
  "first_name": "Test",
  "last_name": "User",
  "username": "testuser123456",
  "email": "test123456@example.com",
  "password": "TestPassword123",
  "phone": "9876543210",
  "emergency_phone": "9876543211",
  "emergency_email": "emergency123456@example.com",
  "drive_folder_id": "1Abc2Def3GhiFolderId"
}
```

### OTP Verification

```http
POST /auth/send-otp
```

```json
{
  "target": "9876543210",
  "type": "phone"
}
```

```http
POST /auth/verify-otp
```

```json
{
  "target": "9876543210",
  "otp": "123456"
}
```

## Notes

- The app currently expects the H5 model file and will fail startup if it is missing.
- Make sure `.gitignore` excludes local virtual environments, logs, caches, and database files.
- Real OTP delivery requires configured SMTP or Twilio credentials; otherwise the app returns a development OTP in the response.

```powershell
curl.exe -X POST "http://localhost:8000/predict" `
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" `
  -F "file=@file_002001.mp4"
```

Example response:

```json
{
  "success": true,
  "prediction": "NONVIOLENT",
  "confidence": 0.1234,
  "inference_time_ms": 45.67,
  "total_time_ms": 320.15,
  "model_type": "keras_h5",
  "filename": "file_002001.mp4"
}
```

## Run the Test Script

Start the API server first, then run:

```powershell
python test_api.py
```

The script uploads `file_002001.mp4` to `http://localhost:8000/predict` and prints the prediction response.

## Notes for GitHub

The local `venv/`, cache files, logs, and temporary processing folders are ignored by `.gitignore`.

The exported model files are not ignored because the application needs them at runtime. Current model files are small enough for normal GitHub uploads, but if future model files become larger than GitHub's limits, use Git LFS or host the model separately and document where to download it.
