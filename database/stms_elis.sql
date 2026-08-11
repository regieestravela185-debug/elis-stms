-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: localhost
-- Generation Time: Aug 07, 2026 at 10:45 AM
-- Server version: 10.4.28-MariaDB
-- PHP Version: 8.2.4

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `stms_elis`
--

-- --------------------------------------------------------

--
-- Table structure for table `activity_logs`
--

CREATE TABLE `activity_logs` (
  `id` int(11) NOT NULL,
  `actor_user_id` int(11) DEFAULT NULL,
  `action` varchar(120) NOT NULL,
  `meta_json` text DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `activity_logs`
--

INSERT INTO `activity_logs` (`id`, `actor_user_id`, `action`, `meta_json`, `created_at`) VALUES
(1, 1, 'reservation_approved', NULL, '2026-05-19 23:25:52'),
(2, 1, 'reservation_approved', NULL, '2026-05-19 23:48:02'),
(3, 1, 'reservation_approved', NULL, '2026-05-20 01:10:02'),
(4, 1, 'reservation_approved', NULL, '2026-05-20 01:26:02');

-- --------------------------------------------------------

--
-- Table structure for table `announcements`
--

CREATE TABLE `announcements` (
  `id` int(11) NOT NULL,
  `title` varchar(200) NOT NULL,
  `content` text NOT NULL,
  `category` varchar(50) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `is_pinned` tinyint(1) NOT NULL DEFAULT 0,
  `target_audience` varchar(20) NOT NULL DEFAULT 'all',
  `expires_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `announcement_reads`
--

CREATE TABLE `announcement_reads` (
  `id` int(11) NOT NULL,
  `announcement_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `read_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `blockchain_alarm_dismissal`
--

CREATE TABLE `blockchain_alarm_dismissal` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `dismissed_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `blockchain_alarm_dismissal`
--

INSERT INTO `blockchain_alarm_dismissal` (`id`, `user_id`, `dismissed_at`) VALUES
(1, 1, '2026-05-19 23:31:52');

-- --------------------------------------------------------

--
-- Table structure for table `buildings`
--

CREATE TABLE `buildings` (
  `id` int(11) NOT NULL,
  `code` varchar(16) NOT NULL,
  `name` varchar(120) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `buildings`
--

INSERT INTO `buildings` (`id`, `code`, `name`) VALUES
(1, 'B1', 'Building 1'),
(2, 'B2', 'Building 2'),
(3, 'B3', 'Building 3'),
(4, 'B4', 'Building 4'),
(5, 'B5', 'Building 5');

-- --------------------------------------------------------

--
-- Table structure for table `chat_logs`
--

CREATE TABLE `chat_logs` (
  `id` int(11) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `user_role` varchar(20) NOT NULL,
  `message` text NOT NULL,
  `response` text NOT NULL,
  `detected_intent` varchar(100) DEFAULT NULL,
  `chatbot_confidence_score` decimal(5,4) DEFAULT NULL,
  `created_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `chat_logs`
--

INSERT INTO `chat_logs` (`id`, `user_id`, `user_role`, `message`, `response`, `detected_intent`, `chatbot_confidence_score`, `created_at`) VALUES
(1, NULL, 'customer', 'Can I bring my dog?', 'Pet policy depends on the unit/building. Please confirm with the office before bringing pets. / Depende sa unit/building ang pet policy. Magtanong sa office.', 'pets', 0.7000, '2026-05-24 12:35:03'),
(2, NULL, 'customer', 'Is wifi included?', 'Amenities vary per building (e.g., CCTV, security, common laundry). Wi-Fi may be per-unit or separate—please confirm with the office. / Iba-iba ang amenities per building. I-confirm sa office.', 'amenities', 0.8000, '2026-05-24 12:35:16'),
(3, NULL, 'customer', 'What documents do I need?', 'Reservation requirements: 1 valid government ID, a clear selfie (AI verification), and signed reservation form. / Kailangan: 1 valid government ID, malinaw na selfie, at signed reservation form.', 'requirements', 0.7500, '2026-05-24 12:35:35'),
(4, NULL, 'customer', 'Magkano ang upa?', 'Residential units ay studio type. Sample rates ay nasa Units section. Commercial units ay may minimum 1-year contract. Para sa updated availability at details, mag-sign in at makipag-ugnayan sa office. / Residential units are studio type. Sample rates are in the Units section. Commercial units have a minimum 1-year contract. For updated availability and details, sign in and contact our office.', 'unit_inquiry', 1.0000, '2026-05-24 12:36:05'),
(5, NULL, 'customer', 'How much is the rent?', 'Residential units ay studio type. Sample rates ay nasa Units section. Commercial units ay may minimum 1-year contract. Para sa updated availability at details, mag-sign in at makipag-ugnayan sa office. / Residential units are studio type. Sample rates are in the Units section. Commercial units have a minimum 1-year contract. For updated availability and details, sign in and contact our office.', 'unit_inquiry', 1.0000, '2026-08-07 07:11:56'),
(6, NULL, 'customer', 'pera', 'I\'m not sure I understand. Try asking about units, pricing, reservation, payments, amenities, parking, pets, or maintenance. / Pakitanong tungkol sa units, presyo, reservation, payments, amenities, parking, alaga, o maintenance.', 'fallback', 0.0000, '2026-08-07 07:30:31');

-- --------------------------------------------------------

--
-- Table structure for table `concerns`
--

CREATE TABLE `concerns` (
  `id` int(11) NOT NULL,
  `tenant_profile_id` int(11) NOT NULL,
  `subject` varchar(120) NOT NULL,
  `description` text NOT NULL,
  `status` enum('pending','in_progress','resolved') NOT NULL DEFAULT 'pending',
  `priority` varchar(20) NOT NULL DEFAULT 'medium',
  `category` varchar(50) NOT NULL DEFAULT 'general',
  `admin_response` text DEFAULT NULL,
  `admin_response_at` datetime DEFAULT NULL,
  `admin_response_by` int(11) DEFAULT NULL,
  `attachments_json` text DEFAULT NULL,
  `is_cancelled` tinyint(1) NOT NULL DEFAULT 0,
  `cancelled_at` datetime DEFAULT NULL,
  `resolved_at` datetime DEFAULT NULL,
  `in_progress_at` datetime DEFAULT NULL,
  `satisfaction_rating` int(11) DEFAULT NULL,
  `satisfaction_feedback` text DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `concern_follow_ups`
--

CREATE TABLE `concern_follow_ups` (
  `id` int(11) NOT NULL,
  `concern_id` int(11) NOT NULL,
  `message` text NOT NULL,
  `attachments_json` text DEFAULT NULL,
  `created_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `documents`
--

CREATE TABLE `documents` (
  `id` int(11) NOT NULL,
  `tenant_profile_id` int(11) NOT NULL,
  `title` varchar(200) NOT NULL,
  `document_type` varchar(50) NOT NULL,
  `file_path` varchar(255) NOT NULL,
  `uploaded_at` datetime NOT NULL DEFAULT current_timestamp(),
  `uploaded_by` int(11) DEFAULT NULL,
  `is_viewed` tinyint(1) NOT NULL DEFAULT 0,
  `viewed_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `document_views`
--

CREATE TABLE `document_views` (
  `id` int(11) NOT NULL,
  `document_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `viewed_at` datetime NOT NULL,
  `downloaded` tinyint(1) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `feedbacks`
--

CREATE TABLE `feedbacks` (
  `id` int(11) NOT NULL,
  `tenant_profile_id` int(11) NOT NULL,
  `unit_id` int(11) DEFAULT NULL,
  `category` varchar(50) NOT NULL,
  `rating` int(11) DEFAULT NULL,
  `comments` text NOT NULL,
  `status` enum('submitted','reviewed') NOT NULL DEFAULT 'submitted',
  `admin_response` text DEFAULT NULL,
  `admin_response_at` datetime DEFAULT NULL,
  `admin_response_by` int(11) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `identity_verifications`
--

CREATE TABLE `identity_verifications` (
  `id` int(11) NOT NULL,
  `reservation_id` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `id_image_path` varchar(255) DEFAULT NULL,
  `id_type_detected` varchar(64) DEFAULT NULL,
  `id_number_detected` varchar(120) DEFAULT NULL,
  `ocr_confidence` decimal(5,4) DEFAULT NULL,
  `fake_score` decimal(5,4) DEFAULT NULL,
  `is_fake` tinyint(1) NOT NULL DEFAULT 0,
  `ela_score` decimal(8,2) DEFAULT NULL,
  `noise_score` decimal(8,2) DEFAULT NULL,
  `has_exif` tinyint(1) NOT NULL DEFAULT 0,
  `image_format` varchar(20) DEFAULT NULL,
  `qr_detected` tinyint(1) NOT NULL DEFAULT 0,
  `qr_valid` tinyint(1) NOT NULL DEFAULT 0,
  `qr_data` text DEFAULT NULL,
  `detection_reasons_json` text DEFAULT NULL,
  `selfie_image_path` varchar(255) DEFAULT NULL,
  `face_detected_in_id` tinyint(1) NOT NULL DEFAULT 0,
  `face_detected_in_selfie` tinyint(1) NOT NULL DEFAULT 0,
  `face_match_score` decimal(5,4) DEFAULT NULL,
  `face_match_result` enum('match','no_match','inconclusive') DEFAULT NULL,
  `verification_result` enum('passed','failed','manual_review') NOT NULL DEFAULT 'manual_review',
  `verified_at` datetime NOT NULL DEFAULT current_timestamp(),
  `reviewed_by` int(11) DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `review_notes` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `identity_verifications`
--

INSERT INTO `identity_verifications` (`id`, `reservation_id`, `user_id`, `id_image_path`, `id_type_detected`, `id_number_detected`, `ocr_confidence`, `fake_score`, `is_fake`, `ela_score`, `noise_score`, `has_exif`, `image_format`, `qr_detected`, `qr_valid`, `qr_data`, `detection_reasons_json`, `selfie_image_path`, `face_detected_in_id`, `face_detected_in_selfie`, `face_match_score`, `face_match_result`, `verification_result`, `verified_at`, `reviewed_by`, `reviewed_at`, `review_notes`) VALUES
(1, 6, 6, 'uploads/820abc7f-3b54-4e9c-a085-f3b7c471c5f8.jpeg', 'National ID', '5926-9829-3275-2463', NULL, 0.0000, 1, NULL, NULL, 0, NULL, 0, 0, NULL, '[\"Fake ID check error: [Errno 2] No such file or directory: \'/Users/regie-302004/Desktop/ElisSystem/app/static/uploads/uploads/820abc7f-3b54-4e9c-a085-f3b7c471c5f8.jpeg\'\"]', 'uploads/selfie_cff1fa5a215b44ed914e1fa920e6f381.jpg', 0, 1, 0.0000, 'inconclusive', 'failed', '2026-06-01 08:41:23', NULL, NULL, NULL),
(2, 7, 6, 'uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg', 'PhilHealth', '08-051636356-1', NULL, 0.0000, 0, NULL, NULL, 0, NULL, 0, 0, NULL, '[\"Fake ID check error: [Errno 2] No such file or directory: \'/Users/regie-302004/Desktop/ElisSystem/uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg\'\"]', NULL, 0, 0, NULL, 'inconclusive', 'manual_review', '2026-08-07 07:54:45', NULL, NULL, NULL),
(3, 8, 6, 'uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg', 'PhilHealth', '08-051636356-1', NULL, 0.0000, 0, NULL, NULL, 0, NULL, 0, 0, NULL, '[\"Fake ID check error: [Errno 2] No such file or directory: \'/Users/regie-302004/Desktop/ElisSystem/uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg\'\"]', NULL, 0, 0, NULL, 'inconclusive', 'manual_review', '2026-08-07 07:59:34', NULL, NULL, NULL),
(4, 9, 6, 'uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg', 'PhilHealth', '08-051636356-1', NULL, 0.0000, 0, NULL, NULL, 0, NULL, 0, 0, NULL, '[\"Fake ID check error: [Errno 2] No such file or directory: \'/Users/regie-302004/Desktop/ElisSystem/uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg\'\"]', NULL, 0, 0, NULL, 'inconclusive', 'manual_review', '2026-08-07 08:05:04', NULL, NULL, NULL),
(5, 10, 6, 'uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg', 'PhilHealth', '08-051636356-1', NULL, 0.0000, 0, NULL, NULL, 0, NULL, 0, 0, NULL, '[\"Fake ID check error: [Errno 2] No such file or directory: \'/Users/regie-302004/Desktop/ElisSystem/uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg\'\"]', NULL, 0, 0, NULL, 'inconclusive', 'manual_review', '2026-08-07 08:15:28', NULL, NULL, NULL),
(6, 11, 6, 'uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg', 'PhilHealth', '08-051636356-1', NULL, 0.0000, 0, NULL, NULL, 0, NULL, 0, 0, NULL, '[\"Fake ID check error: [Errno 2] No such file or directory: \'/Users/regie-302004/Desktop/ElisSystem/uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg\'\"]', NULL, 0, 0, NULL, 'inconclusive', 'manual_review', '2026-08-07 08:21:13', NULL, NULL, NULL);

-- --------------------------------------------------------

--
-- Table structure for table `inquiries`
--

CREATE TABLE `inquiries` (
  `id` int(11) NOT NULL,
  `full_name` varchar(120) NOT NULL,
  `email` varchar(190) NOT NULL,
  `phone` varchar(50) DEFAULT NULL,
  `subject` varchar(200) NOT NULL,
  `message` text NOT NULL,
  `status` varchar(9) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `inquiry_replies`
--

CREATE TABLE `inquiry_replies` (
  `id` int(11) NOT NULL,
  `inquiry_id` int(11) NOT NULL,
  `admin_user_id` int(11) NOT NULL,
  `message` text NOT NULL,
  `created_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `notification_history`
--

CREATE TABLE `notification_history` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `notification_type` varchar(17) NOT NULL,
  `notification_priority` varchar(6) NOT NULL,
  `automated_trigger_type` varchar(100) DEFAULT NULL,
  `message` text NOT NULL,
  `sent_at` datetime NOT NULL,
  `read_at` datetime DEFAULT NULL,
  `status` varchar(9) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `payments`
--

CREATE TABLE `payments` (
  `id` int(11) NOT NULL,
  `tenant_profile_id` int(11) NOT NULL,
  `amount` decimal(12,2) NOT NULL,
  `paid_at` datetime NOT NULL DEFAULT current_timestamp(),
  `reference` varchar(120) DEFAULT NULL,
  `notes` varchar(255) DEFAULT NULL,
  `is_deposit` tinyint(1) NOT NULL DEFAULT 0,
  `deposit_transaction_type` varchar(50) DEFAULT NULL,
  `payment_status` varchar(20) NOT NULL DEFAULT 'verified',
  `is_late` tinyint(1) NOT NULL DEFAULT 0,
  `breakdown_json` text DEFAULT NULL,
  `receipt_number` varchar(50) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `payments`
--

INSERT INTO `payments` (`id`, `tenant_profile_id`, `amount`, `paid_at`, `reference`, `notes`, `is_deposit`, `deposit_transaction_type`, `payment_status`, `is_late`, `breakdown_json`, `receipt_number`) VALUES
(1, 1, 4500.00, '2026-05-19 23:25:52', 'Monthly - B1-001', 'First month payment', 0, NULL, 'verified', 0, NULL, NULL),
(2, 1, 5000.00, '2026-05-19 23:25:52', 'Deposit - B1-001', 'Reservation deposit (refundable after contract ends)', 1, 'deposit_paid', 'verified', 0, NULL, NULL),
(3, 2, 4500.00, '2026-05-19 23:48:02', 'Monthly - B2-001', 'First month payment', 0, NULL, 'verified', 0, NULL, NULL),
(4, 2, 5000.00, '2026-05-19 23:48:02', 'Deposit - B2-001', 'Reservation deposit (refundable after contract ends)', 1, 'deposit_paid', 'verified', 0, NULL, NULL),
(5, 3, 6500.00, '2026-05-20 01:10:02', 'Monthly - B3-002', 'First month payment', 0, NULL, 'verified', 0, NULL, NULL),
(6, 3, 5000.00, '2026-05-20 01:10:02', 'Deposit - B3-002', 'Reservation deposit (refundable after contract ends)', 1, 'deposit_paid', 'verified', 0, NULL, NULL),
(7, 4, 4500.00, '2026-05-20 01:26:02', 'Monthly - B1-003', 'First month payment', 0, NULL, 'verified', 0, NULL, NULL),
(8, 4, 5000.00, '2026-05-20 01:26:02', 'Deposit - B1-003', 'Reservation deposit (refundable after contract ends)', 1, 'deposit_paid', 'verified', 0, NULL, NULL);

-- --------------------------------------------------------

--
-- Table structure for table `payment_ledger`
--

CREATE TABLE `payment_ledger` (
  `id` int(11) NOT NULL,
  `payment_id` int(11) NOT NULL,
  `payload_json` text NOT NULL,
  `previous_hash` char(64) DEFAULT NULL,
  `hash` char(64) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `payment_ledger`
--

INSERT INTO `payment_ledger` (`id`, `payment_id`, `payload_json`, `previous_hash`, `hash`, `created_at`) VALUES
(19, 1, '{\"amount\": 4500.0, \"paid_at\": \"2026-05-19T23:25:52\", \"payment_id\": 1, \"reference\": \"Monthly - B1-001\", \"tenant_profile_id\": 1}', '', '08d33599d24b3e38782e8a35c927e5b58db498bbd1647eaa79b2d81865c8bf43', '2026-05-24 15:08:42'),
(20, 2, '{\"amount\": 5000.0, \"paid_at\": \"2026-05-19T23:25:52\", \"payment_id\": 2, \"reference\": \"Deposit - B1-001\", \"tenant_profile_id\": 1}', '08d33599d24b3e38782e8a35c927e5b58db498bbd1647eaa79b2d81865c8bf43', '80aedd762d6fa5820d5d818515cb22f9a57af969c22979e414c3468662182551', '2026-05-24 15:08:42'),
(21, 3, '{\"amount\": 4500.0, \"paid_at\": \"2026-05-19T23:48:02\", \"payment_id\": 3, \"reference\": \"Monthly - B2-001\", \"tenant_profile_id\": 2}', '80aedd762d6fa5820d5d818515cb22f9a57af969c22979e414c3468662182551', '8ad1c8d5a25db2ee71334b1a2fd2d1903dc3860ff5b143a8981fe503ae78104e', '2026-05-24 15:08:42'),
(22, 4, '{\"amount\": 5000.0, \"paid_at\": \"2026-05-19T23:48:02\", \"payment_id\": 4, \"reference\": \"Deposit - B2-001\", \"tenant_profile_id\": 2}', '8ad1c8d5a25db2ee71334b1a2fd2d1903dc3860ff5b143a8981fe503ae78104e', '02a14081e0b31e2ee0c88fc9056a98dab405a9121f2571c6e0e0afc70f327e6e', '2026-05-24 15:08:42'),
(23, 5, '{\"amount\": 6500.0, \"paid_at\": \"2026-05-20T01:10:02\", \"payment_id\": 5, \"reference\": \"Monthly - B3-002\", \"tenant_profile_id\": 3}', '02a14081e0b31e2ee0c88fc9056a98dab405a9121f2571c6e0e0afc70f327e6e', '97ed79abc10eec274e5634b3c0842c73e45278a75a6b3af3f2b2128865a6c4f6', '2026-05-24 15:08:42'),
(24, 6, '{\"amount\": 5000.0, \"paid_at\": \"2026-05-20T01:10:02\", \"payment_id\": 6, \"reference\": \"Deposit - B3-002\", \"tenant_profile_id\": 3}', '97ed79abc10eec274e5634b3c0842c73e45278a75a6b3af3f2b2128865a6c4f6', '2c976ca939a42be58f5b97547a45c4bb3a1137183d2ec413594f47f914a98887', '2026-05-24 15:08:42'),
(25, 7, '{\"amount\": 4500.0, \"paid_at\": \"2026-05-20T01:26:02\", \"payment_id\": 7, \"reference\": \"Monthly - B1-003\", \"tenant_profile_id\": 4}', '2c976ca939a42be58f5b97547a45c4bb3a1137183d2ec413594f47f914a98887', '38d0c3ff0471e88492ea1b1958c3e88ebfe5b390205192a4849f052671caeee6', '2026-05-24 15:08:42'),
(26, 8, '{\"amount\": 5000.0, \"paid_at\": \"2026-05-20T01:26:02\", \"payment_id\": 8, \"reference\": \"Deposit - B1-003\", \"tenant_profile_id\": 4}', '38d0c3ff0471e88492ea1b1958c3e88ebfe5b390205192a4849f052671caeee6', '747ce927be3a5f2596aeaaa1dc699440a544b5bb7446be9430ec548a346d125c', '2026-05-24 15:08:42');

-- --------------------------------------------------------

--
-- Table structure for table `renewal_requests`
--

CREATE TABLE `renewal_requests` (
  `id` int(11) NOT NULL,
  `tenant_profile_id` int(11) NOT NULL,
  `requested_end_date` date NOT NULL,
  `notes` text DEFAULT NULL,
  `status` enum('pending','approved','rejected') NOT NULL DEFAULT 'pending',
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `renewal_requests`
--

INSERT INTO `renewal_requests` (`id`, `tenant_profile_id`, `requested_end_date`, `notes`, `status`, `created_at`, `updated_at`) VALUES
(1, 4, '2026-07-20', 'gusto ko pa mag stay', 'pending', '2026-05-20 01:26:53', '2026-05-20 01:26:53');

-- --------------------------------------------------------

--
-- Table structure for table `reservations`
--

CREATE TABLE `reservations` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `unit_id` int(11) NOT NULL,
  `full_name` varchar(120) NOT NULL,
  `email` varchar(190) NOT NULL,
  `contact` varchar(50) NOT NULL,
  `id_type` varchar(64) DEFAULT NULL,
  `id_number` varchar(120) DEFAULT NULL,
  `move_in_date` date NOT NULL,
  `move_out_date` date NOT NULL,
  `id_upload_path` varchar(255) DEFAULT NULL,
  `ocr_name` varchar(120) DEFAULT NULL,
  `ocr_id_number` varchar(80) DEFAULT NULL,
  `status` enum('pending','approved','rejected','cancelled') NOT NULL DEFAULT 'pending',
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `deposit_amount` decimal(10,2) NOT NULL DEFAULT 5000.00,
  `deposit_status` enum('held','partial_return','full_return') NOT NULL DEFAULT 'held',
  `deposit_deductions` text DEFAULT NULL,
  `deposit_return_amount` decimal(10,2) DEFAULT NULL,
  `deposit_return_date` date DEFAULT NULL,
  `deposit_notes` text DEFAULT NULL,
  `selfie_image` varchar(255) DEFAULT NULL COMMENT 'Path to uploaded selfie image for facial recognition',
  `face_match_score` decimal(5,4) DEFAULT NULL COMMENT 'Face matching score between ID and selfie (0-1)',
  `verification_status` enum('pending','verified','failed','manual_review') DEFAULT 'pending' COMMENT 'AI verification status',
  `fake_id_flag` tinyint(1) DEFAULT 0 COMMENT 'Flag for potential fake ID detection',
  `id_authenticity_score` decimal(5,4) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `reservations`
--

INSERT INTO `reservations` (`id`, `user_id`, `unit_id`, `full_name`, `email`, `contact`, `id_type`, `id_number`, `move_in_date`, `move_out_date`, `id_upload_path`, `ocr_name`, `ocr_id_number`, `status`, `created_at`, `updated_at`, `deposit_amount`, `deposit_status`, `deposit_deductions`, `deposit_return_amount`, `deposit_return_date`, `deposit_notes`, `selfie_image`, `face_match_score`, `verification_status`, `fake_id_flag`, `id_authenticity_score`) VALUES
(1, 2, 1, 'Estravela Regie', 'regieestravela185@gmail.com', '09318766367', 'Driver\'s License', 'D12-24-004398', '2026-05-20', '2026-07-20', 'uploads/22420dae-e0e3-451f-b9e6-818b125911f3.jpeg', NULL, 'D12-24-004398', 'approved', '2026-05-19 23:25:29', '2026-05-19 23:25:52', 5000.00, 'held', NULL, NULL, NULL, NULL, NULL, NULL, 'pending', 0, NULL),
(2, 3, 2, 'CARRIDO, Kyrien E.', 'carridokyrien@gmail.com', '09345678900', 'PhilHealth', '08-051636356-1', '2026-05-20', '2026-06-20', 'uploads/fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg', NULL, '08-051636356-1', 'approved', '2026-05-19 23:47:22', '2026-05-19 23:48:02', 5000.00, 'held', NULL, NULL, NULL, NULL, NULL, NULL, 'pending', 0, NULL),
(3, 4, 14, 'ivan cruzat', 'luffincrossand@gmail.com', '09318766367', 'PhilHealth', '08-051636356-1', '2026-05-20', '2026-08-20', NULL, NULL, '', 'approved', '2026-05-20 01:00:33', '2026-05-20 01:10:02', 5000.00, 'held', NULL, NULL, NULL, NULL, NULL, NULL, 'pending', 0, NULL),
(4, 5, 7, 'regie', 'regiemunoz01@gmail.com', '09318766367', 'National ID', '5926-9829-3275-2463', '2026-05-20', '2026-06-20', 'uploads/820abc7f-3b54-4e9c-a085-f3b7c471c5f8.jpeg', NULL, '5926-9829-3275-2463', 'approved', '2026-05-20 01:25:34', '2026-05-20 01:26:02', 5000.00, 'held', NULL, NULL, NULL, NULL, NULL, NULL, 'pending', 0, NULL),
(5, 6, 6, 'Regie', 'regiemunoz06@gmail.com', '09318766367', 'Postal ID', '108141234567', '2026-05-24', '2026-05-30', 'uploads/Postal-id-sample.webp', NULL, '108141234567', 'cancelled', '2026-05-24 14:31:22', '2026-05-27 15:21:56', 5000.00, 'held', NULL, NULL, NULL, NULL, 'uploads/selfie_803b0d7baadd4beda3ddf4a94542d830.jpg', NULL, 'manual_review', 0, NULL),
(6, 6, 8, 'Regie', 'regiemunoz06@gmail.com', '09318766367', 'National ID', '5926-9829-3275-2463', '2026-06-01', '2026-06-30', 'uploads/820abc7f-3b54-4e9c-a085-f3b7c471c5f8.jpeg', NULL, '5926-9829-3275-2463', 'cancelled', '2026-06-01 08:41:23', '2026-08-07 07:30:34', 5000.00, 'held', NULL, NULL, NULL, NULL, 'uploads/selfie_cff1fa5a215b44ed914e1fa920e6f381.jpg', 0.0000, 'failed', 1, 1.0000),
(7, 6, 5, 'Regie', 'regiemunoz06@gmail.com', '09318766367', 'PhilHealth', '08-051636356-1', '2026-08-07', '2026-08-31', 'uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg', NULL, '08-051636356-1', 'pending', '2026-08-07 07:54:45', '2026-08-07 07:54:45', 5000.00, 'held', NULL, NULL, NULL, NULL, NULL, NULL, 'pending', 0, 1.0000),
(8, 6, 5, 'Regie', 'regiemunoz06@gmail.com', '09318766367', 'PhilHealth', '08-051636356-1', '2026-08-07', '2026-08-30', 'uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg', NULL, '08-051636356-1', 'pending', '2026-08-07 07:59:34', '2026-08-07 07:59:34', 5000.00, 'held', NULL, NULL, NULL, NULL, NULL, NULL, 'pending', 0, 1.0000),
(9, 6, 5, 'Regie', 'regiemunoz06@gmail.com', '09318766367', 'PhilHealth', '08-051636356-1', '2026-08-07', '2026-08-31', 'uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg', NULL, '08-051636356-1', 'pending', '2026-08-07 08:05:04', '2026-08-07 08:05:04', 5000.00, 'held', NULL, NULL, NULL, NULL, NULL, NULL, 'pending', 0, 1.0000),
(10, 6, 15, 'Regie', 'regiemunoz06@gmail.com', '09318766367', 'PhilHealth', '08-051636356-1', '2026-08-07', '2026-10-07', 'uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg', NULL, '08-051636356-1', 'pending', '2026-08-07 08:15:28', '2026-08-07 08:15:28', 5000.00, 'held', NULL, NULL, NULL, NULL, NULL, NULL, 'pending', 0, 1.0000),
(11, 6, 5, 'Regie', 'regiemunoz06@gmail.com', '09318766367', 'PhilHealth', '08-051636356-1', '2026-08-07', '2026-09-07', 'uploads/1_lease_agreement_fc41faf0-7c8e-4a6f-a8a2-838e82d624ab.jpeg', NULL, '08-051636356-1', 'pending', '2026-08-07 08:21:13', '2026-08-07 08:21:13', 5000.00, 'held', NULL, NULL, NULL, NULL, NULL, NULL, 'pending', 0, 1.0000);

-- --------------------------------------------------------

--
-- Table structure for table `tenant_profiles`
--

CREATE TABLE `tenant_profiles` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `unit_id` int(11) NOT NULL,
  `contract_start` date NOT NULL,
  `contract_end` date DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `last_renewal_reminder_sent` date DEFAULT NULL,
  `email_announcements` tinyint(1) NOT NULL DEFAULT 1,
  `email_payment_reminders` tinyint(1) NOT NULL DEFAULT 1,
  `email_concern_updates` tinyint(1) NOT NULL DEFAULT 1,
  `password_changed_at` datetime DEFAULT NULL,
  `payment_risk_level` enum('low','medium','high') DEFAULT 'low' COMMENT 'Predicted payment risk level',
  `prediction_score` decimal(5,4) DEFAULT NULL COMMENT 'AI prediction score for late payment risk (0-1)',
  `payment_behavior_history` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'Historical payment behavior data for ML analysis' CHECK (json_valid(`payment_behavior_history`))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `tenant_profiles`
--

INSERT INTO `tenant_profiles` (`id`, `user_id`, `unit_id`, `contract_start`, `contract_end`, `is_active`, `created_at`, `last_renewal_reminder_sent`, `email_announcements`, `email_payment_reminders`, `email_concern_updates`, `password_changed_at`, `payment_risk_level`, `prediction_score`, `payment_behavior_history`) VALUES
(1, 2, 1, '2026-05-20', '2026-07-20', 1, '2026-05-19 23:25:52', NULL, 1, 1, 1, NULL, 'low', 0.0000, '{\"total_payments\": 2, \"late_payments\": 0, \"on_time_payments\": 2, \"features\": {\"avg_days_late\": 0.0, \"late_payment_frequency\": 0.0, \"payment_consistency\": 1.0, \"months_active\": 2, \"recent_payment_trend\": 0.0}, \"analyzed_at\": \"2026-05-24T22:31:58.717669\"}'),
(2, 3, 2, '2026-05-20', '2026-06-20', 1, '2026-05-19 23:48:02', NULL, 1, 1, 1, NULL, 'low', 0.0000, '{\"total_payments\": 2, \"late_payments\": 0, \"on_time_payments\": 2, \"features\": {\"avg_days_late\": 0.0, \"late_payment_frequency\": 0.0, \"payment_consistency\": 1.0, \"months_active\": 2, \"recent_payment_trend\": 0.0}, \"analyzed_at\": \"2026-05-24T22:31:58.734763\"}'),
(3, 4, 14, '2026-05-20', '2026-08-20', 1, '2026-05-20 01:10:02', NULL, 1, 1, 1, NULL, 'low', 0.0000, '{\"total_payments\": 2, \"late_payments\": 0, \"on_time_payments\": 2, \"features\": {\"avg_days_late\": 0.0, \"late_payment_frequency\": 0.0, \"payment_consistency\": 1.0, \"months_active\": 2, \"recent_payment_trend\": 0.0}, \"analyzed_at\": \"2026-05-24T22:31:58.738819\"}'),
(4, 5, 7, '2026-05-20', '2026-06-20', 1, '2026-05-20 01:26:02', NULL, 1, 1, 1, NULL, 'low', 0.0000, '{\"total_payments\": 2, \"late_payments\": 0, \"on_time_payments\": 2, \"features\": {\"avg_days_late\": 0.0, \"late_payment_frequency\": 0.0, \"payment_consistency\": 1.0, \"months_active\": 2, \"recent_payment_trend\": 0.0}, \"analyzed_at\": \"2026-05-24T22:31:58.743590\"}');

-- --------------------------------------------------------

--
-- Table structure for table `units`
--

CREATE TABLE `units` (
  `id` int(11) NOT NULL,
  `building_id` int(11) NOT NULL,
  `unit_number` varchar(32) NOT NULL,
  `unit_code` varchar(64) NOT NULL,
  `price_monthly` decimal(12,2) NOT NULL DEFAULT 0.00,
  `status` enum('available','reserved','occupied','unpaid') NOT NULL DEFAULT 'available',
  `floor` int(11) DEFAULT NULL,
  `type` varchar(64) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `unit_images_json` text DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `is_archived` tinyint(1) NOT NULL DEFAULT 0,
  `archived_at` datetime DEFAULT NULL,
  `archived_by` int(11) DEFAULT NULL,
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `units`
--

INSERT INTO `units` (`id`, `building_id`, `unit_number`, `unit_code`, `price_monthly`, `status`, `floor`, `type`, `description`, `unit_images_json`, `created_at`, `is_archived`, `archived_at`, `archived_by`, `updated_at`) VALUES
(1, 1, '001', 'B1-001', 4500.00, 'unpaid', 1, 'residential', '4,500 for 1-2pax units (inclusion bedframe, CR)', '[\"uploads/B1-001_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B1-001_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B1-001_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B1-001_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-19 23:24:01', 0, NULL, NULL, '2026-08-07 07:14:42'),
(2, 2, '001', 'B2-001', 4500.00, 'unpaid', 1, 'residential', '4,500 for 1-2pax units (inclusion bedframe, CR)', '[\"uploads/B2-001_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B2-001_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B2-001_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B2-001_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-19 23:45:44', 0, NULL, NULL, '2026-08-07 07:14:42'),
(3, 4, '001', 'B4-001', 4500.00, 'available', 1, 'residential', '4,500 for 1-2pax units (inclusion bedframe, CR)', '[\"uploads/B4-001_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B4-001_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B4-001_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B4-001_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-20 00:28:22', 0, NULL, NULL, '2026-05-20 00:28:22'),
(4, 5, '001', 'B5-001', 22500.00, 'available', 1, 'commercial', '22,500 (contract for minimum of 1 year)', '[\"uploads/B5-001_498321732_1258029989663680_525070222618595571_n.jpg\", \"uploads/B5-001_497515915_1258030219663657_7912038041291362760_n.jpg\", \"uploads/B5-001_497524835_1258030216330324_5604330388872104053_n.jpg\", \"uploads/B5-001_497814314_1258030169663662_3449305466377272931_n.jpg\"]', '2026-05-20 00:31:50', 0, NULL, NULL, '2026-05-20 00:31:50'),
(5, 3, '001', 'B3-001', 4500.00, 'available', 1, 'residential', '4,500 for 1-2pax units (inclusion bedframe, CR)', '[\"uploads/B3-001_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B3-001_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B3-001_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B3-001_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-20 00:32:55', 0, NULL, NULL, '2026-05-20 00:32:55'),
(6, 1, '002', 'B1-002', 4500.00, 'available', 2, 'residential', '4,500 for 1-2pax units (inclusion bedframe, CR)', '[\"uploads/B1-002_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B1-002_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B1-002_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B1-002_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-20 00:33:31', 0, NULL, NULL, '2026-05-27 15:21:56'),
(7, 1, '003', 'B1-003', 4500.00, 'unpaid', 1, 'residential', '4,500 for 1-2pax units (inclusion bedframe, CR)', '[\"uploads/B1-003_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B1-003_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B1-003_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B1-003_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-20 00:34:17', 0, NULL, NULL, '2026-08-07 07:14:42'),
(8, 1, '004', 'B1-004', 4500.00, 'available', 3, 'residential', '4,500 for 1-2pax units (inclusion bedframe, CR)', '[\"uploads/B1-004_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B1-004_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B1-004_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B1-004_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-20 00:35:12', 0, NULL, NULL, '2026-08-07 07:30:34'),
(9, 1, '005', 'B1-005', 6000.00, 'available', 4, 'residential', '6,000 for 3-4pax units (inclusion bedframe, CR)', '[\"uploads/B1-005_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B1-005_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B1-005_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B1-005_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-20 00:35:48', 0, NULL, NULL, '2026-05-20 00:35:48'),
(10, 2, '002', 'B2-002', 6000.00, 'available', 2, 'residential', '6,000 for 3-4pax units (inclusion bedframe, CR)', '[\"uploads/B2-002_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B2-002_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B2-002_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B2-002_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-20 00:36:25', 0, NULL, NULL, '2026-05-20 00:36:25'),
(11, 2, '003', 'B2-003', 6000.00, 'available', 3, 'residential', '6,000 for 3-4pax units (inclusion bedframe, CR)', '[\"uploads/B2-003_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B2-003_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B2-003_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B2-003_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-20 00:37:02', 0, NULL, NULL, '2026-05-20 00:37:02'),
(12, 2, '004', 'B2-004', 6500.00, 'available', 4, 'residential', '6,500 for 4-6pax units (inclusion bedframe, CR)', '[\"uploads/B2-004_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B2-004_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B2-004_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B2-004_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-20 00:37:46', 0, NULL, NULL, '2026-05-20 00:37:46'),
(14, 3, '002', 'B3-002', 6500.00, 'unpaid', 1, 'residential', '6,500 for 4-6pax units (inclusion bedframe, CR)', '[\"uploads/B3-002_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B3-002_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B3-002_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B3-002_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-20 00:41:14', 0, NULL, NULL, '2026-08-07 07:14:42'),
(15, 3, '003', 'B3-003', 6000.00, 'available', 1, 'residential', '6,000 for 3-4pax units (inclusion bedframe, CR)', '[\"uploads/B3-003_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B3-003_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B3-003_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B3-003_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-20 00:42:05', 0, NULL, NULL, '2026-05-20 00:42:05'),
(16, 4, '002', 'B4-002', 6000.00, 'available', 2, 'residential', '6,000 for 3-4pax units (inclusion bedframe, CR)', '[\"uploads/B4-002_497019540_1258030232996989_1319261549101346560_n.jpg\", \"uploads/B4-002_632511569_1505268418273168_1298124637772010309_n.jpg\", \"uploads/B4-002_632821847_1505268414939835_6724373168789646552_n.jpg\", \"uploads/B4-002_632606124_1505268411606502_5773529691861886070_n.jpg\"]', '2026-05-20 00:42:36', 0, NULL, NULL, '2026-05-20 00:42:36');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `full_name` varchar(120) NOT NULL,
  `email` varchar(190) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` enum('user','tenant','admin') NOT NULL DEFAULT 'user',
  `is_email_verified` tinyint(1) NOT NULL DEFAULT 0,
  `otp_code` varchar(10) DEFAULT NULL,
  `otp_expires_at` datetime DEFAULT NULL,
  `reset_token` varchar(100) DEFAULT NULL,
  `reset_token_expires_at` datetime DEFAULT NULL,
  `google_id` varchar(255) DEFAULT NULL,
  `oauth_provider` varchar(50) NOT NULL DEFAULT 'email',
  `profile_picture` varchar(500) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `last_login_at` datetime DEFAULT NULL,
  `is_banned` tinyint(1) NOT NULL DEFAULT 0,
  `is_archived` tinyint(1) NOT NULL DEFAULT 0,
  `banned_at` datetime DEFAULT NULL,
  `archived_at` datetime DEFAULT NULL,
  `ban_reason` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`id`, `full_name`, `email`, `password_hash`, `role`, `is_email_verified`, `otp_code`, `otp_expires_at`, `reset_token`, `reset_token_expires_at`, `google_id`, `oauth_provider`, `profile_picture`, `created_at`, `last_login_at`, `is_banned`, `is_archived`, `banned_at`, `archived_at`, `ban_reason`) VALUES
(1, 'Admin', 'admin@gmail.com', 'admin123', 'admin', 1, NULL, NULL, NULL, NULL, NULL, 'email', NULL, '2026-05-19 23:19:07', '2026-08-07 08:21:51', 0, 0, NULL, NULL, NULL),
(2, 'Estravela Regie', 'regieestravela185@gmail.com', 'Regie#123', 'tenant', 1, NULL, NULL, NULL, NULL, NULL, 'email', NULL, '2026-05-19 23:20:26', '2026-05-21 06:29:47', 0, 0, NULL, NULL, NULL),
(3, 'CARRIDO, Kyrien E.', 'carridokyrien@gmail.com', 'Kyrien#123', 'tenant', 1, NULL, NULL, NULL, NULL, NULL, 'email', NULL, '2026-05-19 23:46:33', '2026-05-20 09:11:54', 0, 0, NULL, NULL, NULL),
(4, 'ivan cruzat', 'luffincrossand@gmail.com', 'Ivan#123', 'tenant', 1, NULL, NULL, NULL, NULL, NULL, 'email', NULL, '2026-05-20 00:39:03', '2026-08-07 07:44:01', 0, 0, NULL, NULL, NULL),
(5, 'regie', 'regiemunoz01@gmail.com', 'Regie#123', 'tenant', 1, NULL, NULL, NULL, NULL, NULL, 'email', NULL, '2026-05-20 01:24:02', '2026-05-20 01:26:17', 0, 0, NULL, NULL, NULL),
(6, 'Regie', 'regiemunoz06@gmail.com', 'LOPTKI3Gq7I-LqBBItENj2l80CGZCwZORDidUeJIeHs', 'user', 1, NULL, NULL, NULL, NULL, '109772340566647878383', 'google', 'https://lh3.googleusercontent.com/a/ACg8ocIitRD0Sdxt6Hign6sOjhcpzooJSADtlqe0kPR7ld7nwrFv7g=s96-c', '2026-05-21 09:13:31', '2026-08-07 08:20:05', 0, 0, NULL, NULL, NULL);

--
-- Indexes for dumped tables
--

--
-- Indexes for table `activity_logs`
--
ALTER TABLE `activity_logs`
  ADD PRIMARY KEY (`id`),
  ADD KEY `actor_user_id` (`actor_user_id`);

--
-- Indexes for table `announcements`
--
ALTER TABLE `announcements`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `announcement_reads`
--
ALTER TABLE `announcement_reads`
  ADD PRIMARY KEY (`id`),
  ADD KEY `ix_announcement_reads_announcement_id` (`announcement_id`),
  ADD KEY `ix_announcement_reads_user_id` (`user_id`);

--
-- Indexes for table `blockchain_alarm_dismissal`
--
ALTER TABLE `blockchain_alarm_dismissal`
  ADD PRIMARY KEY (`id`),
  ADD KEY `ix_blockchain_alarm_dismissal_user_id` (`user_id`);

--
-- Indexes for table `buildings`
--
ALTER TABLE `buildings`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `code` (`code`);

--
-- Indexes for table `chat_logs`
--
ALTER TABLE `chat_logs`
  ADD PRIMARY KEY (`id`),
  ADD KEY `user_id` (`user_id`);

--
-- Indexes for table `concerns`
--
ALTER TABLE `concerns`
  ADD PRIMARY KEY (`id`),
  ADD KEY `tenant_profile_id` (`tenant_profile_id`),
  ADD KEY `admin_response_by` (`admin_response_by`);

--
-- Indexes for table `concern_follow_ups`
--
ALTER TABLE `concern_follow_ups`
  ADD PRIMARY KEY (`id`),
  ADD KEY `ix_concern_follow_ups_concern_id` (`concern_id`);

--
-- Indexes for table `documents`
--
ALTER TABLE `documents`
  ADD PRIMARY KEY (`id`),
  ADD KEY `tenant_profile_id` (`tenant_profile_id`),
  ADD KEY `uploaded_by` (`uploaded_by`);

--
-- Indexes for table `document_views`
--
ALTER TABLE `document_views`
  ADD PRIMARY KEY (`id`),
  ADD KEY `ix_document_views_user_id` (`user_id`),
  ADD KEY `ix_document_views_document_id` (`document_id`);

--
-- Indexes for table `feedbacks`
--
ALTER TABLE `feedbacks`
  ADD PRIMARY KEY (`id`),
  ADD KEY `tenant_profile_id` (`tenant_profile_id`),
  ADD KEY `unit_id` (`unit_id`),
  ADD KEY `admin_response_by` (`admin_response_by`);

--
-- Indexes for table `identity_verifications`
--
ALTER TABLE `identity_verifications`
  ADD PRIMARY KEY (`id`),
  ADD KEY `reservation_id` (`reservation_id`),
  ADD KEY `user_id` (`user_id`),
  ADD KEY `reviewed_by` (`reviewed_by`);

--
-- Indexes for table `inquiries`
--
ALTER TABLE `inquiries`
  ADD PRIMARY KEY (`id`),
  ADD KEY `ix_inquiries_email` (`email`);

--
-- Indexes for table `inquiry_replies`
--
ALTER TABLE `inquiry_replies`
  ADD PRIMARY KEY (`id`),
  ADD KEY `ix_inquiry_replies_inquiry_id` (`inquiry_id`),
  ADD KEY `ix_inquiry_replies_admin_user_id` (`admin_user_id`);

--
-- Indexes for table `notification_history`
--
ALTER TABLE `notification_history`
  ADD PRIMARY KEY (`id`),
  ADD KEY `user_id` (`user_id`);

--
-- Indexes for table `payments`
--
ALTER TABLE `payments`
  ADD PRIMARY KEY (`id`),
  ADD KEY `tenant_profile_id` (`tenant_profile_id`);

--
-- Indexes for table `payment_ledger`
--
ALTER TABLE `payment_ledger`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `payment_id` (`payment_id`),
  ADD KEY `payment_id_2` (`payment_id`);

--
-- Indexes for table `renewal_requests`
--
ALTER TABLE `renewal_requests`
  ADD PRIMARY KEY (`id`),
  ADD KEY `tenant_profile_id` (`tenant_profile_id`);

--
-- Indexes for table `reservations`
--
ALTER TABLE `reservations`
  ADD PRIMARY KEY (`id`),
  ADD KEY `user_id` (`user_id`),
  ADD KEY `unit_id` (`unit_id`);

--
-- Indexes for table `tenant_profiles`
--
ALTER TABLE `tenant_profiles`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `user_id` (`user_id`),
  ADD KEY `user_id_2` (`user_id`),
  ADD KEY `unit_id` (`unit_id`);

--
-- Indexes for table `units`
--
ALTER TABLE `units`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unit_code` (`unit_code`),
  ADD UNIQUE KEY `uq_unit_building_num` (`building_id`,`unit_number`),
  ADD KEY `building_id` (`building_id`),
  ADD KEY `archived_by` (`archived_by`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `email` (`email`),
  ADD UNIQUE KEY `reset_token` (`reset_token`),
  ADD UNIQUE KEY `google_id` (`google_id`),
  ADD KEY `reset_token_2` (`reset_token`),
  ADD KEY `google_id_2` (`google_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `activity_logs`
--
ALTER TABLE `activity_logs`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `announcements`
--
ALTER TABLE `announcements`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `announcement_reads`
--
ALTER TABLE `announcement_reads`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `blockchain_alarm_dismissal`
--
ALTER TABLE `blockchain_alarm_dismissal`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT for table `buildings`
--
ALTER TABLE `buildings`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `chat_logs`
--
ALTER TABLE `chat_logs`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

--
-- AUTO_INCREMENT for table `concerns`
--
ALTER TABLE `concerns`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `concern_follow_ups`
--
ALTER TABLE `concern_follow_ups`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `documents`
--
ALTER TABLE `documents`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `document_views`
--
ALTER TABLE `document_views`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `feedbacks`
--
ALTER TABLE `feedbacks`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `identity_verifications`
--
ALTER TABLE `identity_verifications`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

--
-- AUTO_INCREMENT for table `inquiries`
--
ALTER TABLE `inquiries`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `inquiry_replies`
--
ALTER TABLE `inquiry_replies`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `notification_history`
--
ALTER TABLE `notification_history`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `payments`
--
ALTER TABLE `payments`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=9;

--
-- AUTO_INCREMENT for table `payment_ledger`
--
ALTER TABLE `payment_ledger`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=27;

--
-- AUTO_INCREMENT for table `renewal_requests`
--
ALTER TABLE `renewal_requests`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT for table `reservations`
--
ALTER TABLE `reservations`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=12;

--
-- AUTO_INCREMENT for table `tenant_profiles`
--
ALTER TABLE `tenant_profiles`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `units`
--
ALTER TABLE `units`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=17;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `activity_logs`
--
ALTER TABLE `activity_logs`
  ADD CONSTRAINT `fk_logs_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL;

--
-- Constraints for table `announcement_reads`
--
ALTER TABLE `announcement_reads`
  ADD CONSTRAINT `announcement_reads_ibfk_1` FOREIGN KEY (`announcement_id`) REFERENCES `announcements` (`id`),
  ADD CONSTRAINT `announcement_reads_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

--
-- Constraints for table `blockchain_alarm_dismissal`
--
ALTER TABLE `blockchain_alarm_dismissal`
  ADD CONSTRAINT `blockchain_alarm_dismissal_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

--
-- Constraints for table `chat_logs`
--
ALTER TABLE `chat_logs`
  ADD CONSTRAINT `chat_logs_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

--
-- Constraints for table `concerns`
--
ALTER TABLE `concerns`
  ADD CONSTRAINT `fk_concern_admin` FOREIGN KEY (`admin_response_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  ADD CONSTRAINT `fk_concern_tenant` FOREIGN KEY (`tenant_profile_id`) REFERENCES `tenant_profiles` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `concern_follow_ups`
--
ALTER TABLE `concern_follow_ups`
  ADD CONSTRAINT `concern_follow_ups_ibfk_1` FOREIGN KEY (`concern_id`) REFERENCES `concerns` (`id`);

--
-- Constraints for table `documents`
--
ALTER TABLE `documents`
  ADD CONSTRAINT `fk_document_tenant` FOREIGN KEY (`tenant_profile_id`) REFERENCES `tenant_profiles` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `fk_document_uploader` FOREIGN KEY (`uploaded_by`) REFERENCES `users` (`id`) ON DELETE SET NULL;

--
-- Constraints for table `document_views`
--
ALTER TABLE `document_views`
  ADD CONSTRAINT `document_views_ibfk_1` FOREIGN KEY (`document_id`) REFERENCES `documents` (`id`),
  ADD CONSTRAINT `document_views_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

--
-- Constraints for table `feedbacks`
--
ALTER TABLE `feedbacks`
  ADD CONSTRAINT `fk_feedback_admin` FOREIGN KEY (`admin_response_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  ADD CONSTRAINT `fk_feedback_tenant` FOREIGN KEY (`tenant_profile_id`) REFERENCES `tenant_profiles` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `fk_feedback_unit` FOREIGN KEY (`unit_id`) REFERENCES `units` (`id`) ON DELETE SET NULL;

--
-- Constraints for table `identity_verifications`
--
ALTER TABLE `identity_verifications`
  ADD CONSTRAINT `fk_verification_reservation` FOREIGN KEY (`reservation_id`) REFERENCES `reservations` (`id`) ON DELETE SET NULL,
  ADD CONSTRAINT `fk_verification_reviewer` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  ADD CONSTRAINT `fk_verification_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL;

--
-- Constraints for table `inquiry_replies`
--
ALTER TABLE `inquiry_replies`
  ADD CONSTRAINT `inquiry_replies_ibfk_1` FOREIGN KEY (`inquiry_id`) REFERENCES `inquiries` (`id`),
  ADD CONSTRAINT `inquiry_replies_ibfk_2` FOREIGN KEY (`admin_user_id`) REFERENCES `users` (`id`);

--
-- Constraints for table `notification_history`
--
ALTER TABLE `notification_history`
  ADD CONSTRAINT `notification_history_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

--
-- Constraints for table `payments`
--
ALTER TABLE `payments`
  ADD CONSTRAINT `fk_pay_tenant` FOREIGN KEY (`tenant_profile_id`) REFERENCES `tenant_profiles` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `payment_ledger`
--
ALTER TABLE `payment_ledger`
  ADD CONSTRAINT `fk_ledger_payment` FOREIGN KEY (`payment_id`) REFERENCES `payments` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `renewal_requests`
--
ALTER TABLE `renewal_requests`
  ADD CONSTRAINT `fk_renewal_tenant` FOREIGN KEY (`tenant_profile_id`) REFERENCES `tenant_profiles` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `reservations`
--
ALTER TABLE `reservations`
  ADD CONSTRAINT `fk_res_unit` FOREIGN KEY (`unit_id`) REFERENCES `units` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `fk_res_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `tenant_profiles`
--
ALTER TABLE `tenant_profiles`
  ADD CONSTRAINT `fk_tenant_unit` FOREIGN KEY (`unit_id`) REFERENCES `units` (`id`),
  ADD CONSTRAINT `fk_tenant_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `units`
--
ALTER TABLE `units`
  ADD CONSTRAINT `fk_units_archived_by` FOREIGN KEY (`archived_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  ADD CONSTRAINT `fk_units_building` FOREIGN KEY (`building_id`) REFERENCES `buildings` (`id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
