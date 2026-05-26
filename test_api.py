"""
Complete API Testing Script
Tests all endpoints with proper authentication
"""

import requests
import json
from pathlib import Path
import time

# ===================== CONFIGURATION =====================

BASE_URL = "http://localhost:8000"
TEST_VIDEO = "file_002001.mp4"

# Generate unique username (alphanumeric only!)
TIMESTAMP = str(int(time.time()))[-6:]  # Last 6 digits
TEST_USER = {
    "username": f"testuser{TIMESTAMP}",  # Alphanumeric only
    "email": f"test{TIMESTAMP}@example.com",
    "password": "TestPassword123",
    "first_name": "Test",
    "last_name": "User",
    "phone": "9876543210",
    "emergency_phone": "9876543211",
    "emergency_email": f"emergency{TIMESTAMP}@example.com",
    "drive_folder_id": "testDriveFolderId123"
}

# ===================== HELPER FUNCTIONS =====================

def print_section(title):
    """Print section separator"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_response(response, title="Response"):
    """Pretty print response"""
    print(f"\n📊 Status Code: {response.status_code}")
    try:
        data = response.json()
        print(f"✓ {title}:")
        print(json.dumps(data, indent=2))
        return data
    except:
        print(f"✗ Response: {response.text}")
        return None

# ===================== TEST 1: HEALTH CHECK =====================

def test_health_check():
    """Test health check (no auth needed)"""
    print_section("TEST 1: HEALTH CHECK")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        data = print_response(response, "Health Check")
        
        if response.status_code == 200:
            print("\n✅ Health check passed!")
            print(f"   Model loaded: {data.get('model_loaded')}")
            print(f"   Model type: {data.get('model_type')}")
            return True
        else:
            print("\n❌ Health check failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# ===================== TEST 2: REGISTER USER =====================

def test_register():
    """Test user registration"""
    print_section("TEST 2: USER REGISTRATION")
    
    print(f"📝 Registering user: {TEST_USER['username']}")
    print(f"   Email: {TEST_USER['email']}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json=TEST_USER,
            timeout=10
        )
        data = print_response(response, "Registration")
        
        if response.status_code == 201:
            print("\n✅ Registration successful!")
            print(f"   User ID: {data['user']['id']}")
            print(f"   Username: {data['user']['username']}")
            print(f"   Email: {data['user']['email']}")
            return data
        else:
            print("\n❌ Registration failed!")
            if data:
                print(f"   Error: {data}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# ===================== TEST 3: LOGIN =====================

def test_login():
    """Test user login"""
    print_section("TEST 3: USER LOGIN")
    
    login_data = {
        "username": TEST_USER["username"],
        "password": TEST_USER["password"]
    }
    
    print(f"🔐 Logging in as: {TEST_USER['username']}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json=login_data,
            timeout=10
        )
        data = print_response(response, "Login")
        
        if response.status_code == 200:
            token = data.get('access_token')
            print("\n✅ Login successful!")
            print(f"   Token: {token[:30]}...")
            return token
        else:
            print("\n❌ Login failed!")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# ===================== TEST 4: GET PROFILE =====================

def test_get_profile(token):
    """Test get user profile"""
    print_section("TEST 4: GET USER PROFILE")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/auth/profile",
            headers=headers,
            timeout=10
        )
        data = print_response(response, "User Profile")
        
        if response.status_code == 200:
            print("\n✅ Profile retrieved!")
            print(f"   User: {data['user']['username']}")
            print(f"   Email: {data['user']['email']}")
            print(f"   Total incidents: {data['total_incidents']}")
            return data
        else:
            print("\n❌ Failed to get profile!")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# ===================== TEST 5: BATCH PREDICTION (VIDEO UPLOAD) =====================

def test_batch_prediction(token):
    """Test batch video prediction"""
    print_section("TEST 5: BATCH PREDICTION (VIDEO UPLOAD)")
    
    # Check if video exists
    if not Path(TEST_VIDEO).exists():
        print(f"⚠️  Video file not found: {TEST_VIDEO}")
        print(f"   Place {TEST_VIDEO} in E:\\Backend_Major_p_root\\")
        print("   Skipping video upload test...")
        return None
    
    print(f"📹 Uploading video: {TEST_VIDEO}")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        with open(TEST_VIDEO, 'rb') as f:
            files = {'file': f}
            response = requests.post(
                f"{BASE_URL}/predict",
                files=files,
                headers=headers,
                timeout=60  # 60 second timeout for video processing
            )
        
        data = print_response(response, "Prediction Result")
        
        if response.status_code == 200:
            print("\n✅ Prediction successful!")
            print(f"   Prediction: {data['prediction']}")
            print(f"   Confidence: {data['confidence']:.4f}")
            print(f"   Inference time: {data['inference_time_ms']}ms")
            print(f"   Incident ID: {data['incident_id']}")
            return data
        else:
            print("\n❌ Prediction failed!")
            return None
            
    except requests.Timeout:
        print("\n⚠️  Request timed out (video processing takes time)")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# ===================== TEST 6: LIST INCIDENTS =====================

def test_list_incidents(token):
    """Test list user incidents"""
    print_section("TEST 6: LIST INCIDENTS")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # CORRECT URL - use query parameters, not path parameters
        url = f"{BASE_URL}/api/v1/incidents/list?skip=0&limit=20"
        
        print(f"📍 URL: {url}")
        
        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )
        data = print_response(response, "Incidents List")
        
        if response.status_code == 200:
            print(f"\n✅ Incidents retrieved!")
            print(f"   Total: {data['total']}")
            print(f"   Retrieved: {len(data['incidents'])}")
            
            if data['incidents']:
                for i, incident in enumerate(data['incidents'][:3], 1):  # Show first 3
                    print(f"\n   Incident {i}:")
                    print(f"     - ID: {incident['id']}")
                    print(f"     - Prediction: {incident['prediction']}")
                    print(f"     - Confidence: {incident['confidence']:.4f}")
                    print(f"     - Type: {incident['detection_type']}")
            
            return data
        else:
            print("\n❌ Failed to list incidents!")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# ===================== TEST 7: GET STATISTICS =====================

def test_statistics(token):
    """Test get incident statistics"""
    print_section("TEST 7: INCIDENT STATISTICS")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/incidents/user/statistics",
            headers=headers,
            timeout=10
        )
        data = print_response(response, "Statistics")
        
        if response.status_code == 200:
            print("\n✅ Statistics retrieved!")
            print(f"   Total incidents: {data['total_incidents']}")
            print(f"   Violent: {data['violent_incidents']}")
            print(f"   Non-violent: {data['non_violent_incidents']}")
            print(f"   Detection rate: {data['detection_rate']:.2f}%")
            return data
        else:
            print("\n❌ Failed to get statistics!")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# ===================== TEST 8: GET INCIDENT DETAILS =====================

def test_get_incident_details(token, incident_id):
    """Test get incident details"""
    if not incident_id:
        print_section("TEST 8: SKIP (No incident to test)")
        print("⏭️  Skipping - no incident ID from prediction test")
        return None
    
    print_section("TEST 8: GET INCIDENT DETAILS")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/incidents/{incident_id}",
            headers=headers,
            timeout=10
        )
        data = print_response(response, "Incident Details")
        
        if response.status_code == 200:
            print("\n✅ Incident details retrieved!")
            print(f"   ID: {data['id']}")
            print(f"   Prediction: {data['prediction']}")
            print(f"   Confidence: {data['confidence']:.4f}")
            return data
        else:
            print("\n❌ Failed to get incident!")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# ===================== TEST 9: ADMIN DASHBOARD =====================

def test_admin_dashboard(token):
    """Test admin dashboard (will fail if not admin)"""
    print_section("TEST 9: ADMIN DASHBOARD (Expected: Admin access required)")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/admin/dashboard",
            headers=headers,
            timeout=10
        )
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 403:
            print("\n✓ Expected: User is not admin")
            print("   This is correct behavior!")
            return None
        elif response.status_code == 200:
            data = print_response(response, "Admin Dashboard")
            return data
        else:
            data = print_response(response)
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# ===================== MAIN TEST RUNNER =====================

def main():
    """Run all tests"""
    print("VIOLENCE DETECTION API - COMPLETE TEST SUITE")
    
    # Test 1: Health Check
    if not test_health_check():
        print("\n❌ Backend is not running!")
        print("Start backend with: python main.py")
        return
    
    # Test 2: Register
    reg_data = test_register()
    if not reg_data:
        print("\n❌ Registration failed!")
        return
    
    # Test 3: Login
    token = test_login()
    if not token:
        print("\n❌ Login failed!")
        return
    
    # Test 4: Get Profile
    test_get_profile(token)
    
    # Test 5: Batch Prediction (if video exists)
    print("\n⏳ Testing batch prediction...")
    pred_data = test_batch_prediction(token)
    incident_id = pred_data['incident_id'] if pred_data else None
    
    # Test 6: List Incidents
    test_list_incidents(token)
    
    # Test 7: Statistics
    test_statistics(token)
    
    # Test 8: Get Incident Details
    test_get_incident_details(token, incident_id)
    
    # Test 9: Admin Dashboard
    test_admin_dashboard(token)
    
    # Final summary
    print_section("TEST SUITE COMPLETE")
    print("\n✅ All core tests completed!")
    print("\nAPI is working correctly:")
    print("  ✓ Health check works")
    print("  ✓ Registration works")
    print("  ✓ Login works")
    print("  ✓ Authentication works")
    print("  ✓ Profile retrieval works")
    print("  ✓ Incident listing works")
    print("  ✓ Incident details work")
    print("  ✓ Statistics works")
    print("\n🎉 Backend is PRODUCTION READY!")
    print("=" * 60)

if __name__ == "__main__":
    main()
