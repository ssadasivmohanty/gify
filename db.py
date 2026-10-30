"""
Database operations and persistence layer for the GyFi app.
"""

import sqlite3
import math
from datetime import datetime, date
from logger import logger
import queries
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "life_tracker.db")
# DB_NAME = "life_tracker.db"


def get_connection():
    try:
        return sqlite3.connect(DB_NAME)
    except sqlite3.Error as e:
        logger.error(f"Failed to connect to database '{DB_NAME}': {e}", exc_info=True)
        raise


def init_db():
    logger.info("Initializing database schema...")
    try:
        conn = get_connection()
        c = conn.cursor()

        c.execute(queries.CREATE_GYM_SESSIONS_TABLE)
        c.execute(queries.CREATE_WORKOUT_EXERCISES_TABLE)
        c.execute(queries.CREATE_GYM_MEMBERSHIP_TABLE)
        c.execute(queries.CREATE_GYM_LOCATION_TABLE)
        c.execute(queries.CREATE_CREDIT_CARDS_TABLE)
        c.execute(queries.CREATE_EXPENSES_TABLE)

        # Splitwise tables (optional / when ready)
        c.execute(queries.CREATE_SPLIT_GROUPS_TABLE)
        c.execute(queries.CREATE_SPLIT_MEMBERS_TABLE)
        c.execute(queries.CREATE_SPLIT_EXPENSES_TABLE)
        c.execute(queries.CREATE_SPLIT_PARTICIPANTS_TABLE)

        # Alter gym_sessions if upgrading existing table without lat/long
        try:
            c.execute("ALTER TABLE gym_sessions ADD COLUMN latitude REAL")
            c.execute("ALTER TABLE gym_sessions ADD COLUMN longitude REAL")
        except sqlite3.OperationalError:
            pass  # Columns already exist

        conn.commit()
        conn.close()
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.exception(f"Error during database initialization: {e}")


# ---------------------------------------------------------------------------
# Geolocation & Distance Calculation
# ---------------------------------------------------------------------------

def calculate_distance_meters(lat1, lon1, lat2, lon2):
    """
    Haversine formula to compute great-circle distance between two GPS coordinates in meters.
    """
    R = 6371000  # Radius of earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def get_gym_target_location():
    """
    Returns stored target gym coordinates (lat, lon, radius).
    """
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.SELECT_GYM_LOCATION)
        row = c.fetchone()
        conn.close()
        return row
    except Exception as e:
        logger.exception(f"Error fetching gym target location: {e}")
        return None


def save_gym_target_location(gym_name, lat, lon, radius_meters=100.0):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.INSERT_OR_UPDATE_GYM_LOCATION, (
            gym_name.strip(),
            float(lat),
            float(lon),
            float(radius_meters)
        ))
        conn.commit()
        conn.close()
        logger.info(f"Saved target gym location '{gym_name}' at ({lat}, {lon}) with radius {radius_meters}m")
    except Exception as e:
        logger.exception(f"Failed to save gym location: {e}")


# ---------------------------------------------------------------------------
# Gym & Workout Helpers
# ---------------------------------------------------------------------------

def get_active_gym_session():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.SELECT_ACTIVE_GYM_SESSION)
        row = c.fetchone()
        conn.close()
        return row
    except Exception as e:
        logger.exception(f"Error in get_active_gym_session: {e}")
        return None


def punch_in_with_geo(latitude=None, longitude=None):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"User Punch-In with Geo at {now_str} (Lat: {latitude}, Lon: {longitude})")
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.INSERT_PUNCH_IN_WITH_GEO, (now_str, latitude, longitude))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.exception(f"Failed to record punch_in: {e}")


def punch_out(session_id, in_time_str):
    out_dt = datetime.now()
    try:
        in_dt = datetime.strptime(in_time_str, "%Y-%m-%d %H:%M:%S")
        duration = max(1, int((out_dt - in_dt).total_seconds() / 60))
        out_str = out_dt.strftime("%Y-%m-%d %H:%M:%S")

        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.UPDATE_PUNCH_OUT, (out_str, duration, session_id))
        conn.commit()
        conn.close()
        logger.info(f"User Punch-Out recorded for session {session_id} (Duration: {duration} mins)")
    except Exception as e:
        logger.exception(f"Failed to record punch_out for session {session_id}: {e}")


def get_workout_dates_for_month(year, month):
    month_prefix = f"{year:04d}-{month:02d}%"
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.SELECT_WORKOUT_DATES_FOR_MONTH, (month_prefix,))
        rows = [r[0] for r in c.fetchall()]
        conn.close()

        gym_days = set()
        for r in rows:
            try:
                gym_days.add(datetime.strptime(r, "%Y-%m-%d").day)
            except ValueError:
                continue
        return gym_days
    except Exception as e:
        logger.exception(f"Error fetching workout dates for {year}-{month:02d}: {e}")
        return set()


def get_day_workout_details(target_date_str):
    try:
        conn = get_connection()
        c = conn.cursor()

        c.execute(queries.SELECT_DAY_GYM_SESSIONS, (target_date_str,))
        sessions = c.fetchall()
        total_minutes = sum(s[2] for s in sessions if s[2] is not None)

        c.execute(queries.SELECT_DAY_EXERCISES, (target_date_str,))
        exercises = c.fetchall()

        conn.close()
        return total_minutes, sessions, exercises
    except Exception as e:
        logger.exception(f"Error fetching day workout details for {target_date_str}: {e}")
        return 0, [], []


def add_workout_exercise(workout_date_str, name, sets, reps, weight_kg, notes=""):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.INSERT_WORKOUT_EXERCISE, (
            workout_date_str,
            name.strip(),
            int(sets or 0),
            int(reps or 0),
            float(weight_kg or 0.0),
            notes.strip()
        ))
        conn.commit()
        conn.close()
        logger.info(f"Added exercise '{name}' for date {workout_date_str}")
    except Exception as e:
        logger.exception(f"Failed to add exercise '{name}' for {workout_date_str}: {e}")


def delete_workout_exercise(exercise_id):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.DELETE_WORKOUT_EXERCISE, (exercise_id,))
        conn.commit()
        conn.close()
        logger.info(f"Deleted exercise ID: {exercise_id}")
    except Exception as e:
        logger.exception(f"Failed to delete exercise ID {exercise_id}: {e}")

def get_recent_gym_history(limit=10):
    """Returns recent gym sessions with their primary key ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, punch_in, punch_out, duration_minutes 
        FROM gym_attendance 
        WHERE punch_out IS NOT NULL 
        ORDER BY punch_in DESC 
        LIMIT ?
    """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def delete_gym_session(session_id: int):
    """Deletes a completed gym session by its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gym_attendance WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

def get_recent_gym_history(limit=5):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.SELECT_RECENT_GYM_SESSIONS, (limit,))
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.exception(f"Error fetching recent gym history: {e}")
        return []


def get_gym_membership():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.SELECT_ACTIVE_MEMBERSHIP)
        row = c.fetchone()
        conn.close()
        return row
    except Exception as e:
        logger.exception(f"Error fetching gym membership: {e}")
        return None


def save_gym_membership(plan_name, fee_paid, start_date_str, end_date_str, proof_details=""):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.INSERT_OR_UPDATE_MEMBERSHIP, (
            plan_name.strip(),
            float(fee_paid or 0.0),
            start_date_str.strip(),
            end_date_str.strip(),
            proof_details.strip()
        ))
        conn.commit()
        conn.close()
        logger.info(f"Saved gym membership '{plan_name}' ending on {end_date_str}")
    except Exception as e:
        logger.exception(f"Failed to save gym membership: {e}")


# ---------------------------------------------------------------------------
# Finance & Credit Card Helpers
# ---------------------------------------------------------------------------

def add_credit_card(name, limit):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.INSERT_CREDIT_CARD, (name.strip(), float(limit or 0)))
        conn.commit()
        conn.close()
        logger.info(f"Added credit card '{name}' with limit ₹{limit}")
    except sqlite3.IntegrityError:
        logger.warning(f"Credit card '{name}' already exists.")
    except Exception as e:
        logger.exception(f"Failed to add credit card '{name}': {e}")


def delete_credit_card(card_id):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.DELETE_CREDIT_CARD, (card_id,))
        conn.commit()
        conn.close()
        logger.info(f"Deleted credit card ID: {card_id}")
    except Exception as e:
        logger.exception(f"Failed to delete credit card ID {card_id}: {e}")


def get_credit_cards():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.SELECT_ALL_CREDIT_CARDS)
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.exception(f"Error fetching credit cards: {e}")
        return []


def add_expense(title, amount, mode, card_id=None):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.INSERT_EXPENSE, (title.strip(), float(amount), mode, card_id, now_str))
        conn.commit()
        conn.close()
        logger.info(f"Logged expense '{title}' (₹{amount}) via {mode}")
    except Exception as e:
        logger.exception(f"Failed to log expense '{title}': {e}")

def delete_expense(tx_id: int):
    """
    Deletes an expense by its primary key ID.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(queries.DELETE_EXPENSE, (tx_id,))
    conn.commit()
    conn.close()
    logger.info(f"Deleted expense ID: {tx_id}")

def get_recent_expenses(limit=10, year=None, month=None):
    try:
        conn = get_connection()
        c = conn.cursor()
        if year and month:
            month_prefix = f"{year:04d}-{month:02d}%"
            c.execute(queries.SELECT_ALL_EXPENSES_FOR_MONTH, (month_prefix, limit))
        else:
            c.execute(queries.SELECT_ALL_EXPENSES_GLOBAL, (limit,))
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.exception(f"Error fetching recent expenses: {e}")
        return []


def get_card_monthly_expenses(card_id, year, month):
    month_prefix = f"{year:04d}-{month:02d}%"
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(queries.SELECT_CARD_MONTHLY_EXPENSES, (card_id, month_prefix))
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.exception(f"Error fetching card expenses for card {card_id} on {year}-{month:02d}: {e}")
        return []


def get_monthly_finance_summary(year, month):
    month_prefix = f"{year:04d}-{month:02d}%"
    try:
        conn = get_connection()
        c = conn.cursor()

        c.execute(queries.SELECT_MONTHLY_TOTAL_SPENT, (month_prefix,))
        total_spent = c.fetchone()[0] or 0.0

        c.execute(queries.SELECT_MONTHLY_CC_DUES, (month_prefix,))
        cc_dues = c.fetchone()[0] or 0.0

        c.execute("""
            SELECT c.id, c.name, c.credit_limit, IFNULL(SUM(e.amount), 0.0) 
            FROM credit_cards c 
            LEFT JOIN expenses e ON c.id = e.card_id AND e.date_logged LIKE ? 
            GROUP BY c.id;
        """, (month_prefix,))
        card_breakdown = c.fetchall()

        conn.close()
        return total_spent, cc_dues, card_breakdown
    except Exception as e:
        logger.exception(f"Error calculating monthly finance summary for {year}-{month:02d}: {e}")
        return 0.0, 0.0, []
    