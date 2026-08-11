-- STMS for Elis Business Center - PostgreSQL Version
-- Converted from MySQL for Supabase
-- Import this in Supabase SQL Editor

-- Note: CREATE DATABASE is not needed in Supabase, it uses 'postgres' database

SET TIME ZONE 'UTC';

-- Drop tables in reverse order of dependencies
DROP TABLE IF EXISTS payment_ledger CASCADE;
DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS feedbacks CASCADE;
DROP TABLE IF EXISTS renewal_requests CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS announcements CASCADE;
DROP TABLE IF EXISTS concerns CASCADE;
DROP TABLE IF EXISTS tenant_profiles CASCADE;
DROP TABLE IF EXISTS identity_verifications CASCADE;
DROP TABLE IF EXISTS reservations CASCADE;
DROP TABLE IF EXISTS units CASCADE;
DROP TABLE IF EXISTS buildings CASCADE;
DROP TABLE IF EXISTS activity_logs CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Create ENUM types for PostgreSQL
CREATE TYPE user_role AS ENUM ('user', 'tenant', 'admin');
CREATE TYPE unit_status AS ENUM ('available', 'reserved', 'occupied', 'unpaid');
CREATE TYPE reservation_status AS ENUM ('pending', 'approved', 'rejected', 'cancelled');
CREATE TYPE deposit_status AS ENUM ('held', 'partial_return', 'full_return');
CREATE TYPE verification_status AS ENUM ('pending', 'verified', 'failed', 'manual_review');
CREATE TYPE face_match_result AS ENUM ('match', 'no_match', 'inconclusive');
CREATE TYPE verification_result AS ENUM ('passed', 'failed', 'manual_review');
CREATE TYPE concern_status AS ENUM ('pending', 'in_progress', 'resolved');
CREATE TYPE renewal_status AS ENUM ('pending', 'approved', 'rejected');
CREATE TYPE feedback_status AS ENUM ('submitted', 'reviewed');

CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  full_name VARCHAR(120) NOT NULL,
  email VARCHAR(190) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role user_role NOT NULL DEFAULT 'user',
  is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
  otp_code VARCHAR(10) NULL,
  otp_expires_at TIMESTAMP NULL,
  reset_token VARCHAR(100) NULL UNIQUE,
  reset_token_expires_at TIMESTAMP NULL,
  google_id VARCHAR(255) NULL UNIQUE,
  oauth_provider VARCHAR(50) NOT NULL DEFAULT 'email',
  profile_picture VARCHAR(500) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  last_login_at TIMESTAMP NULL,
  is_banned BOOLEAN NOT NULL DEFAULT FALSE,
  is_archived BOOLEAN NOT NULL DEFAULT FALSE,
  banned_at TIMESTAMP NULL,
  archived_at TIMESTAMP NULL,
  ban_reason VARCHAR(255) NULL
);

CREATE INDEX idx_users_reset_token ON users(reset_token);
CREATE INDEX idx_users_google_id ON users(google_id);

CREATE TABLE activity_logs (
  id SERIAL PRIMARY KEY,
  actor_user_id INTEGER NULL,
  action VARCHAR(120) NOT NULL,
  meta_json TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_logs_actor FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_activity_logs_actor ON activity_logs(actor_user_id);

CREATE TABLE buildings (
  id SERIAL PRIMARY KEY,
  code VARCHAR(16) NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL
);

CREATE TABLE units (
  id SERIAL PRIMARY KEY,
  building_id INTEGER NOT NULL,
  unit_number VARCHAR(32) NOT NULL,
  unit_code VARCHAR(64) NOT NULL UNIQUE,
  price_monthly DECIMAL(12,2) NOT NULL DEFAULT 0,
  status unit_status NOT NULL DEFAULT 'available',
  floor INTEGER NULL,
  type VARCHAR(64) NULL,
  description TEXT NULL,
  unit_images_json TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  is_archived BOOLEAN NOT NULL DEFAULT FALSE,
  archived_at TIMESTAMP NULL,
  archived_by INTEGER NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE (building_id, unit_number),
  CONSTRAINT fk_units_building FOREIGN KEY (building_id) REFERENCES buildings(id) ON DELETE CASCADE,
  CONSTRAINT fk_units_archived_by FOREIGN KEY (archived_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_units_building ON units(building_id);
CREATE INDEX idx_units_archived_by ON units(archived_by);

CREATE TABLE reservations (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  unit_id INTEGER NOT NULL,
  full_name VARCHAR(120) NOT NULL,
  email VARCHAR(190) NOT NULL,
  contact VARCHAR(50) NOT NULL,
  id_type VARCHAR(64) NULL,
  id_number VARCHAR(120) NULL,
  move_in_date DATE NOT NULL,
  move_out_date DATE NOT NULL,
  id_upload_path VARCHAR(255) NULL,
  ocr_name VARCHAR(120) NULL,
  ocr_id_number VARCHAR(80) NULL,
  status reservation_status NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  deposit_amount DECIMAL(10,2) NOT NULL DEFAULT 5000.00,
  deposit_status deposit_status NOT NULL DEFAULT 'held',
  deposit_deductions TEXT NULL,
  deposit_return_amount DECIMAL(10,2) NULL,
  deposit_return_date DATE NULL,
  deposit_notes TEXT NULL,
  selfie_image VARCHAR(255) NULL,
  face_match_score DECIMAL(5,4) NULL,
  verification_status verification_status NOT NULL DEFAULT 'pending',
  fake_id_flag BOOLEAN NOT NULL DEFAULT FALSE,
  id_authenticity_score DECIMAL(5,4) NULL,
  CONSTRAINT fk_res_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_res_unit FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE
);

CREATE INDEX idx_reservations_user ON reservations(user_id);
CREATE INDEX idx_reservations_unit ON reservations(unit_id);

CREATE TABLE identity_verifications (
  id SERIAL PRIMARY KEY,
  reservation_id INTEGER NULL,
  user_id INTEGER NULL,
  id_image_path VARCHAR(255) NULL,
  id_type_detected VARCHAR(64) NULL,
  id_number_detected VARCHAR(120) NULL,
  ocr_confidence DECIMAL(5,4) NULL,
  fake_score DECIMAL(5,4) NULL,
  is_fake BOOLEAN NOT NULL DEFAULT FALSE,
  ela_score DECIMAL(8,2) NULL,
  noise_score DECIMAL(8,2) NULL,
  has_exif BOOLEAN NOT NULL DEFAULT FALSE,
  image_format VARCHAR(20) NULL,
  qr_detected BOOLEAN NOT NULL DEFAULT FALSE,
  qr_valid BOOLEAN NOT NULL DEFAULT FALSE,
  qr_data TEXT NULL,
  detection_reasons_json TEXT NULL,
  selfie_image_path VARCHAR(255) NULL,
  face_detected_in_id BOOLEAN NOT NULL DEFAULT FALSE,
  face_detected_in_selfie BOOLEAN NOT NULL DEFAULT FALSE,
  face_match_score DECIMAL(5,4) NULL,
  face_match_result face_match_result NULL,
  verification_result verification_result NOT NULL DEFAULT 'manual_review',
  verified_at TIMESTAMP NOT NULL DEFAULT NOW(),
  reviewed_by INTEGER NULL,
  reviewed_at TIMESTAMP NULL,
  review_notes TEXT NULL,
  CONSTRAINT fk_verification_reservation FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE SET NULL,
  CONSTRAINT fk_verification_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT fk_verification_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_identity_verifications_reservation ON identity_verifications(reservation_id);
CREATE INDEX idx_identity_verifications_user ON identity_verifications(user_id);
CREATE INDEX idx_identity_verifications_reviewed_by ON identity_verifications(reviewed_by);

CREATE TABLE tenant_profiles (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL UNIQUE,
  unit_id INTEGER NOT NULL,
  contract_start DATE NOT NULL,
  contract_end DATE NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  last_renewal_reminder_sent DATE NULL,
  email_announcements BOOLEAN NOT NULL DEFAULT TRUE,
  email_payment_reminders BOOLEAN NOT NULL DEFAULT TRUE,
  email_concern_updates BOOLEAN NOT NULL DEFAULT TRUE,
  password_changed_at TIMESTAMP NULL,
  CONSTRAINT fk_tenant_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_tenant_unit FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE RESTRICT
);

CREATE INDEX idx_tenant_profiles_user ON tenant_profiles(user_id);
CREATE INDEX idx_tenant_profiles_unit ON tenant_profiles(unit_id);

CREATE TABLE payments (
  id SERIAL PRIMARY KEY,
  tenant_profile_id INTEGER NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  paid_at TIMESTAMP NOT NULL DEFAULT NOW(),
  reference VARCHAR(120) NULL,
  notes VARCHAR(255) NULL,
  is_deposit BOOLEAN NOT NULL DEFAULT FALSE,
  deposit_transaction_type VARCHAR(50) NULL,
  payment_status VARCHAR(20) NOT NULL DEFAULT 'verified',
  is_late BOOLEAN NOT NULL DEFAULT FALSE,
  breakdown_json TEXT NULL,
  receipt_number VARCHAR(50) NULL,
  CONSTRAINT fk_pay_tenant FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id) ON DELETE CASCADE
);

CREATE INDEX idx_payments_tenant_profile ON payments(tenant_profile_id);

CREATE TABLE payment_ledger (
  id SERIAL PRIMARY KEY,
  payment_id INTEGER NOT NULL UNIQUE,
  payload_json TEXT NOT NULL,
  previous_hash CHAR(64) NULL,
  hash CHAR(64) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_ledger_payment FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE
);

CREATE INDEX idx_payment_ledger_payment ON payment_ledger(payment_id);

CREATE TABLE concerns (
  id SERIAL PRIMARY KEY,
  tenant_profile_id INTEGER NOT NULL,
  subject VARCHAR(120) NOT NULL,
  description TEXT NOT NULL,
  status concern_status NOT NULL DEFAULT 'pending',
  priority VARCHAR(20) NOT NULL DEFAULT 'medium',
  category VARCHAR(50) NOT NULL DEFAULT 'general',
  admin_response TEXT NULL,
  admin_response_at TIMESTAMP NULL,
  admin_response_by INTEGER NULL,
  attachments_json TEXT NULL,
  is_cancelled BOOLEAN NOT NULL DEFAULT FALSE,
  cancelled_at TIMESTAMP NULL,
  resolved_at TIMESTAMP NULL,
  in_progress_at TIMESTAMP NULL,
  satisfaction_rating INTEGER NULL,
  satisfaction_feedback TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_concern_tenant FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id) ON DELETE CASCADE,
  CONSTRAINT fk_concern_admin FOREIGN KEY (admin_response_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_concerns_tenant_profile ON concerns(tenant_profile_id);
CREATE INDEX idx_concerns_admin_response_by ON concerns(admin_response_by);

CREATE TABLE announcements (
  id SERIAL PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  content TEXT NOT NULL,
  category VARCHAR(50) NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
  target_audience VARCHAR(20) NOT NULL DEFAULT 'all',
  expires_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE documents (
  id SERIAL PRIMARY KEY,
  tenant_profile_id INTEGER NOT NULL,
  title VARCHAR(200) NOT NULL,
  document_type VARCHAR(50) NOT NULL,
  file_path VARCHAR(255) NOT NULL,
  uploaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
  uploaded_by INTEGER NULL,
  is_viewed BOOLEAN NOT NULL DEFAULT FALSE,
  viewed_at TIMESTAMP NULL,
  CONSTRAINT fk_document_tenant FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id) ON DELETE CASCADE,
  CONSTRAINT fk_document_uploader FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_documents_tenant_profile ON documents(tenant_profile_id);
CREATE INDEX idx_documents_uploaded_by ON documents(uploaded_by);

CREATE TABLE renewal_requests (
  id SERIAL PRIMARY KEY,
  tenant_profile_id INTEGER NOT NULL,
  requested_end_date DATE NOT NULL,
  notes TEXT NULL,
  status renewal_status NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_renewal_tenant FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id) ON DELETE CASCADE
);

CREATE INDEX idx_renewal_requests_tenant_profile ON renewal_requests(tenant_profile_id);

CREATE TABLE feedbacks (
  id SERIAL PRIMARY KEY,
  tenant_profile_id INTEGER NOT NULL,
  unit_id INTEGER NULL,
  category VARCHAR(50) NOT NULL,
  rating INTEGER NULL,
  comments TEXT NOT NULL,
  status feedback_status NOT NULL DEFAULT 'submitted',
  admin_response TEXT NULL,
  admin_response_at TIMESTAMP NULL,
  admin_response_by INTEGER NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_feedback_tenant FOREIGN KEY (tenant_profile_id) REFERENCES tenant_profiles(id) ON DELETE CASCADE,
  CONSTRAINT fk_feedback_unit FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE SET NULL,
  CONSTRAINT fk_feedback_admin FOREIGN KEY (admin_response_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_feedbacks_tenant_profile ON feedbacks(tenant_profile_id);
CREATE INDEX idx_feedbacks_unit ON feedbacks(unit_id);
CREATE INDEX idx_feedbacks_admin_response_by ON feedbacks(admin_response_by);

-- Seed buildings
INSERT INTO buildings (code, name) VALUES
('B1', 'Building 1'),
('B2', 'Building 2'),
('B3', 'Building 3'),
('B4', 'Building 4'),
('B5', 'Building 5');

-- Seed demo admin account (plain-text password; dev/demo only)
INSERT INTO users (full_name, email, password_hash, role, is_email_verified)
VALUES
('Admin', 'admin@gmail.com', 'admin123', 'admin', TRUE);

-- Create function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for auto-updating updated_at
CREATE TRIGGER update_units_updated_at BEFORE UPDATE ON units
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_reservations_updated_at BEFORE UPDATE ON reservations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_concerns_updated_at BEFORE UPDATE ON concerns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_announcements_updated_at BEFORE UPDATE ON announcements
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_renewal_requests_updated_at BEFORE UPDATE ON renewal_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Database schema created successfully for PostgreSQL/Supabase!';
    RAISE NOTICE 'Total tables: 15';
    RAISE NOTICE 'Seeded: 5 buildings, 1 admin user';
END $$;
