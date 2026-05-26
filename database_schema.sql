-- ===================== DATABASE SETUP =====================

CREATE DATABASE IF NOT EXISTS violence_detection_db;
USE violence_detection_db;

-- ===================== USERS TABLE =====================

CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    emergency_phone VARCHAR(20),
    emergency_email VARCHAR(100),
    drive_folder_id VARCHAR(255),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20),
    
    profile_picture_url VARCHAR(255),
    
    role ENUM('USER', 'ADMIN') DEFAULT 'USER',
    
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_role (role),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- For existing databases, run these once if the columns are missing:
-- ALTER TABLE users ADD COLUMN phone VARCHAR(20);
-- ALTER TABLE users ADD COLUMN emergency_phone VARCHAR(20);
-- ALTER TABLE users ADD COLUMN emergency_email VARCHAR(100);
-- ALTER TABLE users ADD COLUMN drive_folder_id VARCHAR(255);

-- ===================== USER PROFILES TABLE =====================

CREATE TABLE user_profiles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL UNIQUE,
    
    bio TEXT,
    organization VARCHAR(255),
    location_latitude DECIMAL(10, 8),
    location_longitude DECIMAL(11, 8),
    
    google_drive_folder_id VARCHAR(255),
    google_drive_sync_enabled BOOLEAN DEFAULT TRUE,
    
    notifications_enabled BOOLEAN DEFAULT TRUE,
    email_alerts BOOLEAN DEFAULT TRUE,
    
    total_incidents INT DEFAULT 0,
    total_videos_saved INT DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================== INCIDENTS TABLE =====================

CREATE TABLE incidents (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    
    detection_type ENUM('REALTIME', 'BATCH') NOT NULL,
    prediction VARCHAR(50) NOT NULL,  -- 'VIOLENT' or 'NONVIOLENT'
    confidence DECIMAL(4, 4) NOT NULL,  -- 0.0000 to 1.0000
    
    video_duration_seconds INT,
    frame_count INT,
    
    preprocessing_time_ms INT,
    inference_time_ms INT,
    total_time_ms INT,
    
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    location_name VARCHAR(255),
    
    video_file_name VARCHAR(255),
    video_file_path VARCHAR(255),
    video_google_drive_id VARCHAR(255),
    video_google_drive_link VARCHAR(500),
    video_size_bytes BIGINT,
    
    is_uploaded_to_drive BOOLEAN DEFAULT FALSE,
    upload_status ENUM('PENDING', 'UPLOADING', 'SUCCESS', 'FAILED') DEFAULT 'PENDING',
    upload_error_message TEXT,
    
    is_reviewed_by_admin BOOLEAN DEFAULT FALSE,
    admin_notes TEXT,
    admin_id INT,
    
    is_marked_for_police BOOLEAN DEFAULT FALSE,
    police_reference_number VARCHAR(50),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_prediction (prediction),
    INDEX idx_confidence (confidence),
    INDEX idx_created_at (created_at),
    INDEX idx_upload_status (upload_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================== DEVICE TOKENS TABLE (for push notifications) =====================

CREATE TABLE device_tokens (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    
    device_token VARCHAR(255) NOT NULL UNIQUE,
    device_type ENUM('ANDROID', 'IOS', 'WEB') DEFAULT 'ANDROID',
    device_name VARCHAR(255),
    
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP NULL,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_device_token (device_token)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================== NOTIFICATIONS TABLE =====================

CREATE TABLE notifications (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    notification_type ENUM('VIDEO_UPLOADED', 'ADMIN_REVIEW', 'INCIDENT_DETECTED') DEFAULT 'INCIDENT_DETECTED',
    
    incident_id INT,
    
    is_read BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_is_read (is_read),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================== AUDIT LOG TABLE =====================

CREATE TABLE audit_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100),
    resource_id INT,
    details JSON,
    ip_address VARCHAR(45),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================== CREATE INDEXES FOR PERFORMANCE =====================

CREATE INDEX idx_incidents_user_prediction ON incidents(user_id, prediction);
CREATE INDEX idx_incidents_created_prediction ON incidents(created_at, prediction);
CREATE INDEX idx_incidents_upload_status ON incidents(upload_status, user_id);

-- ===================== VIEW: User Statistics =====================

CREATE VIEW user_statistics AS
SELECT 
    u.id,
    u.username,
    u.email,
    COUNT(i.id) as total_incidents,
    SUM(CASE WHEN i.prediction = 'VIOLENT' THEN 1 ELSE 0 END) as violent_incidents,
    SUM(CASE WHEN i.prediction = 'NONVIOLENT' THEN 1 ELSE 0 END) as non_violent_incidents,
    AVG(i.confidence) as average_confidence,
    MAX(i.created_at) as last_incident_date
FROM users u
LEFT JOIN incidents i ON u.id = i.user_id
GROUP BY u.id, u.username, u.email;

-- ===================== VIEW: Admin Dashboard Stats =====================

CREATE VIEW admin_dashboard_stats AS
SELECT 
    COUNT(DISTINCT u.id) as total_users,
    COUNT(DISTINCT i.id) as total_incidents,
    SUM(CASE WHEN i.prediction = 'VIOLENT' THEN 1 ELSE 0 END) as violent_incidents_count,
    SUM(CASE WHEN i.is_uploaded_to_drive = FALSE THEN 1 ELSE 0 END) as pending_uploads,
    SUM(CASE WHEN i.is_reviewed_by_admin = FALSE THEN 1 ELSE 0 END) as pending_reviews,
    AVG(i.confidence) as average_confidence
FROM users u
LEFT JOIN incidents i ON u.id = i.user_id
WHERE u.is_active = TRUE;

-- ===================== SAMPLE DATA (for testing) =====================

INSERT INTO users (username, email, password_hash, first_name, last_name, role, is_verified) VALUES
('admin', 'admin@violencedetection.com', '$2b$12$placeholder_admin_hash', 'Admin', 'User', 'ADMIN', TRUE),
('demo_user', 'demo@example.com', '$2b$12$placeholder_user_hash', 'Demo', 'User', 'USER', TRUE);
