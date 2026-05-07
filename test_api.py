import requests
import json
from pathlib import Path

# Configuration
API_URL = "http://localhost:8000/predict"
TEST_VIDEO = "file_002001.mp4" 

def test_predict():
    """Test the prediction endpoint"""
    
    # Check if test video exists
    if not Path(TEST_VIDEO).exists():
        print(f"❌ Test video '{TEST_VIDEO}' not found!")
        print("Please provide a video file at least 16 frames long")
        return
    
    print(f"📹 Testing with video: {TEST_VIDEO}")
    print(f"🔗 API endpoint: {API_URL}")
    print("-" * 60)
    
    try:
        # Open and send video file
        with open(TEST_VIDEO, 'rb') as video_file:
            files = {'file': video_file}
            
            print("⏳ Sending request to server...")
            response = requests.post(API_URL, files=files, timeout=60)
        
        print(f"📊 Status Code: {response.status_code}")
        print("-" * 60)
        
        # Parse response
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print(f"\nResponse:")
            print(json.dumps(result, indent=2))
            
            # Summary
            print("\n" + "=" * 60)
            print(f"🎯 PREDICTION: {result['prediction']}")
            print(f"📈 CONFIDENCE: {result['confidence']}")
            print(f"⚡ Inference Time: {result['inference_time_ms']}ms")
            print(f"⏱️  Total Time: {result['total_time_ms']}ms")
            print(f"🤖 Model Type: {result['model_type']}")
            print("=" * 60)
        else:
            print("❌ ERROR!")
            print(f"Response: {response.text}")
    
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server!")
        print("Make sure the server is running: uvicorn main:app --reload")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    test_predict()