"""
SQL query constants and DDL definitions for the GyFi database.
"""

# ===========================================================================
# Table Creation (DDL)
# ===========================================================================

CREATE_GYM_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS gym_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    punch_in TEXT NOT NULL,
    punch_out TEXT,
    duration_minutes INTEGER,
    latitude REAL,
    longitude REAL
);
"""

CREATE_WORKOUT_EXERCISES_TABLE = """
CREATE TABLE IF NOT EXISTS workout_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_date TEXT NOT NULL,
    exercise_name TEXT NOT NULL,
    sets INTEGER DEFAULT 0,
    reps INTEGER DEFAULT 0,
    weight_kg REAL DEFAULT 0.0,
    notes TEXT
);
"""

CREATE_GYM_MEMBERSHIP_TABLE = """
CREATE TABLE IF NOT EXISTS gym_membership (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_name TEXT NOT NULL,
    fee_paid REAL DEFAULT 0.0,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    proof_details TEXT
);
"""

CREATE_GYM_LOCATION_TABLE = """
CREATE TABLE IF NOT EXISTS gym_location (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gym_name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    radius_meters REAL DEFAULT 100.0
);
"""

CREATE_CREDIT_CARDS_TABLE = """
CREATE TABLE IF NOT EXISTS credit_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    credit_limit REAL DEFAULT 0.0
);
"""

CREATE_EXPENSES_TABLE = """
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    amount REAL NOT NULL,
    payment_mode TEXT NOT NULL,
    card_id INTEGER,
    date_logged TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES credit_cards (id) ON DELETE SET NULL
);
"""

CREATE_SPLIT_GROUPS_TABLE = """
CREATE TABLE IF NOT EXISTS split_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

CREATE_SPLIT_MEMBERS_TABLE = """
CREATE TABLE IF NOT EXISTS split_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    upi_id TEXT,
    FOREIGN KEY (group_id) REFERENCES split_groups(id) ON DELETE CASCADE
);
"""

CREATE_SPLIT_EXPENSES_TABLE = """
CREATE TABLE IF NOT EXISTS split_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    total_amount REAL NOT NULL,
    paid_by_member_id INTEGER NOT NULL,
    split_type TEXT DEFAULT 'EQUAL',
    date TEXT NOT NULL,
    FOREIGN KEY (group_id) REFERENCES split_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (paid_by_member_id) REFERENCES split_members(id)
);
"""

CREATE_SPLIT_PARTICIPANTS_TABLE = """
CREATE TABLE IF NOT EXISTS split_expense_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    owed_amount REAL NOT NULL,
    FOREIGN KEY (expense_id) REFERENCES split_expenses(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES split_members(id)
);
"""

# ===========================================================================
# Gym & Location Queries
# ===========================================================================

SELECT_ACTIVE_GYM_SESSION = """
SELECT id, punch_in 
FROM gym_sessions 
WHERE punch_out IS NULL 
ORDER BY id DESC LIMIT 1;
"""

INSERT_PUNCH_IN_WITH_GEO = """
INSERT INTO gym_sessions (punch_in, latitude, longitude) 
VALUES (?, ?, ?);
"""

UPDATE_PUNCH_OUT = """
UPDATE gym_sessions 
SET punch_out = ?, duration_minutes = ? 
WHERE id = ?;
"""

SELECT_WORKOUT_DATES_FOR_MONTH = """
SELECT DISTINCT date(punch_in) 
FROM gym_sessions 
WHERE punch_in LIKE ?;
"""

SELECT_DAY_GYM_SESSIONS = """
SELECT punch_in, punch_out, duration_minutes 
FROM gym_sessions 
WHERE date(punch_in) = ? AND punch_out IS NOT NULL 
ORDER BY id ASC;
"""

SELECT_DAY_EXERCISES = """
SELECT id, exercise_name, sets, reps, weight_kg, notes 
FROM workout_exercises 
WHERE workout_date = ? 
ORDER BY id ASC;
"""

INSERT_WORKOUT_EXERCISE = """
INSERT INTO workout_exercises (workout_date, exercise_name, sets, reps, weight_kg, notes) 
VALUES (?, ?, ?, ?, ?, ?);
"""

DELETE_WORKOUT_EXERCISE = """
DELETE FROM workout_exercises 
WHERE id = ?;
"""
DELETE_GYM_SESSION = """DELETE FROM gym_attendance WHERE id = ?"""

SELECT_RECENT_GYM_SESSIONS = """
SELECT punch_in, punch_out, duration_minutes 
FROM gym_sessions 
WHERE punch_out IS NOT NULL 
ORDER BY id DESC LIMIT ?;
"""

SELECT_ACTIVE_MEMBERSHIP = """
SELECT id, plan_name, fee_paid, start_date, end_date, proof_details 
FROM gym_membership 
ORDER BY id DESC LIMIT 1;
"""

INSERT_OR_UPDATE_MEMBERSHIP = """
INSERT INTO gym_membership (plan_name, fee_paid, start_date, end_date, proof_details) 
VALUES (?, ?, ?, ?, ?);
"""

SELECT_GYM_LOCATION = """
SELECT id, gym_name, latitude, longitude, radius_meters 
FROM gym_location 
ORDER BY id DESC LIMIT 1;
"""

INSERT_OR_UPDATE_GYM_LOCATION = """
INSERT INTO gym_location (gym_name, latitude, longitude, radius_meters) 
VALUES (?, ?, ?, ?);
"""

# ===========================================================================
# Finance Queries
# ===========================================================================

INSERT_CREDIT_CARD = """
INSERT INTO credit_cards (name, credit_limit) 
VALUES (?, ?);
"""

DELETE_CREDIT_CARD = """
DELETE FROM credit_cards 
WHERE id = ?;
"""

SELECT_ALL_CREDIT_CARDS = """
SELECT id, name, credit_limit 
FROM credit_cards 
ORDER BY name ASC;
"""

INSERT_EXPENSE = """
INSERT INTO expenses (title, amount, payment_mode, card_id, date_logged) 
VALUES (?, ?, ?, ?, ?);
"""

DELETE_EXPENSE = "DELETE FROM expenses WHERE id = ?"

SELECT_ALL_EXPENSES_FOR_MONTH = """
SELECT id, title, amount, payment_mode, date_logged 
FROM expenses 
WHERE date_logged LIKE ? 
ORDER BY id DESC LIMIT ?;
"""

SELECT_ALL_EXPENSES_GLOBAL = """
SELECT id, title, amount, payment_mode, date_logged 
FROM expenses 
ORDER BY id DESC LIMIT ?;
"""

SELECT_CARD_MONTHLY_EXPENSES = """
SELECT id, title, amount, date_logged 
FROM expenses 
WHERE card_id = ? AND date_logged LIKE ? 
ORDER BY id DESC;
"""

SELECT_MONTHLY_TOTAL_SPENT = """
SELECT SUM(amount) 
FROM expenses 
WHERE date_logged LIKE ?;
"""

SELECT_MONTHLY_CC_DUES = """
SELECT SUM(amount) 
FROM expenses 
WHERE date_logged LIKE ? AND card_id IS NOT NULL;
"""

SELECT_MONTHLY_PER_CARD_BREAKDOWN = """
SELECT c.id, c.name, c.credit_limit, IFNULL(SUM(e.amount), 0.0) 
FROM credit_cards c 
LEFT JOIN expenses e ON c.id = e.card_id AND e.date_logged LIKE ? 
GROUP BY c.id;
"""

# ==============================================================================
# SPLITWISE DML QUERIES
# ==============================================================================

GET_ALL_SPLIT_GROUPS = """
    SELECT id, name, created_at 
    FROM split_groups 
    ORDER BY id DESC;
"""

INSERT_SPLIT_GROUP = """
    INSERT INTO split_groups (name, created_at) 
    VALUES (?, ?);
"""

DELETE_SPLIT_GROUP = """
    DELETE FROM split_groups 
    WHERE id = ?;
"""

GET_MEMBERS_BY_GROUP = """
    SELECT id, group_id, name, upi_id 
    FROM split_members 
    WHERE group_id = ? 
    ORDER BY id ASC;
"""

INSERT_SPLIT_MEMBER = """
    INSERT INTO split_members (group_id, name, upi_id) 
    VALUES (?, ?, ?);
"""

DELETE_SPLIT_MEMBER = """
    DELETE FROM split_members 
    WHERE id = ?;
"""

GET_EXPENSES_BY_GROUP = """
    SELECT e.id, e.description, e.total_amount, e.paid_by_member_id, m.name, e.split_type, e.date
    FROM split_expenses e
    JOIN split_members m ON e.paid_by_member_id = m.id
    WHERE e.group_id = ?
    ORDER BY e.date DESC, e.id DESC;
"""

INSERT_SPLIT_EXPENSE = """
    INSERT INTO split_expenses (group_id, description, total_amount, paid_by_member_id, split_type, date)
    VALUES (?, ?, ?, ?, ?, ?);
"""

INSERT_EXPENSE_PARTICIPANT = """
    INSERT INTO split_expense_participants (expense_id, member_id, owed_amount)
    VALUES (?, ?, ?);
"""

GET_GROUP_SETTLEMENT_RAW = """
    SELECT p.expense_id, e.paid_by_member_id, p.member_id, p.owed_amount
    FROM split_expense_participants p
    JOIN split_expenses e ON p.expense_id = e.id
    WHERE e.group_id = ?;
"""

DELETE_SPLIT_EXPENSE = """
    DELETE FROM split_expenses 
    WHERE id = ?;
"""