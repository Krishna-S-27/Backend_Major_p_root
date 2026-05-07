# Violence Detection API

This project is a FastAPI backend for detecting violence in uploaded video files. It loads an exported TensorFlow model, samples 16 frames from an input video, preprocesses them to `224x224`, runs inference, and returns a JSON prediction with confidence and timing information.

The API is designed to be used by a mobile app or any client that can upload a video file through an HTTP multipart request.

## Features

- Loads the best available model format with fallback support:
  - TFLite: `exports_v2/exports_v2/violence_model_v2.tflite`
  - Keras: `exports_v2/exports_v2/violence_model_v2.keras`
  - H5: `exports_v2/exports_v2/violence_model_v2.h5`
  - SavedModel: `exports_v2/exports_v2/violence_model_v2_savedmodel/`
- Accepts common video formats such as `.mp4`, `.avi`, `.mov`, `.mkv`, `.flv`, `.wmv`, and `.webm`.
- Extracts 16 uniformly spaced frames from the uploaded video.
- Returns `VIOLENT` or `NONVIOLENT` using a confidence threshold of `0.5`.
- Includes health, stats, and interactive API documentation endpoints.

## Project Structure

```text
.
├── main.py
├── requirements.txt
├── test_api.py
├── file_002001.mp4
└── exports_v2/
    └── exports_v2/
        ├── violence_model_v2.tflite
        ├── violence_model_v2.keras
        ├── violence_model_v2.h5
        └── violence_model_v2_savedmodel/
```

## Requirements

- Python 3.10 or newer
- TensorFlow
- OpenCV
- FastAPI
- Uvicorn

Install the exact Python packages from `requirements.txt`.

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

Make sure the model files exist in this path:

```text
exports_v2/exports_v2/
```

## Run the API

Start the FastAPI server:

```powershell
uvicorn main:app --reload
```

The API will run at:

```text
http://localhost:8000
```

Open the interactive Swagger documentation:

```text
http://localhost:8000/docs
```

## API Endpoints

### Health Check

```http
GET /health
```

Returns whether the service is healthy and whether the model is loaded.

### Runtime Stats

```http
GET /stats
```

Returns model status, model type, preprocessing settings, and model paths.

### Predict Violence

```http
POST /predict
```

Upload a video file using multipart form data with the field name `file`.

Example using PowerShell:

```powershell
curl.exe -X POST "http://localhost:8000/predict" -F "file=@file_002001.mp4"
```

Example response:

```json
{
  "success": true,
  "prediction": "NONVIOLENT",
  "confidence": 0.1234,
  "inference_time_ms": 45.67,
  "total_time_ms": 320.15,
  "model_type": "tflite",
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

