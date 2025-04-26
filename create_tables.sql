CREATE DATABASE IF NOT EXISTS mymail;
USE mymail;

CREATE TABLE IF NOT EXISTS emails (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE,
    subject VARCHAR(500),
    sender VARCHAR(255),
    recipients TEXT,
    cc TEXT,
    bcc TEXT,
    content TEXT,
    received_date DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_message_id (message_id),
    INDEX idx_received_date (received_date)
); 