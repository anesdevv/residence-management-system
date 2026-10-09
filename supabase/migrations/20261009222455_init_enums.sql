create type gender as enum ('male', 'female');
create type study_level as enum ('L1', 'L2', 'L3', 'M1', 'M2', 'Doctorat');
create type user_role as enum ('student', 'staff', 'admin');
create type student_status as enum ('pending', 'active', 'rejected');
create type report_status as enum ('pending', 'in_progress', 'resolved');
create type request_status as enum ('pending', 'approved', 'rejected');
create type maintenance_category as enum ('plumbing', 'electrical', 'furniture', 'internet', 'other');