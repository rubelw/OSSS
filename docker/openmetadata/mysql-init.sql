-- Ensure user/db exist with mysql_native_password and correct privileges
CREATE DATABASE IF NOT EXISTS openmetadata
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE USER IF NOT EXISTS 'openmetadata_user'@'%'
  IDENTIFIED WITH mysql_native_password BY 'openmetadata_password';

GRANT ALL PRIVILEGES ON openmetadata.* TO 'openmetadata_user'@'%';
FLUSH PRIVILEGES;
