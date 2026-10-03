"""
Gym Tracker View:
Provides Geo-Verified punch-in/out check-in functionality, gym GPS geofence configuration,
interactive monthly calendar with membership due-date highlights, workout exercise logs,
and session deletion capabilities.
"""

import calendar
from datetime import datetime, date
import flet as ft
import db
from logger import logger


def format_inr(number: float) -> str:
    try:
        val = abs(float(number))
        parts = f"{val:.2f}".split(".")
        int_part, dec_part = parts[0], parts[1]
        if len(int_part) <= 3:
            res = int_part
        else:
            last_three = int_part[-3:]
            remaining = int_part[:-3]
            groups = []
            while len(remaining) > 2:
                groups.insert(0, remaining[-2:])
                remaining = remaining[:-2]
            if remaining:
                groups.insert(0, remaining)
            res = ",".join(groups) + "," + last_three
        return f"₹{res}"
    except Exception:
        return "₹0"


def create_primary_button(text: str, on_click, icon=None, height=40):
    """Universal cross-version primary button using styled ft.Container."""
    icon_ctrl = [ft.Icon(icon, size=16, color=ft.Colors.WHITE)] if icon else []
    return ft.Container(
        content=ft.Row(
            icon_ctrl
            + [
                ft.Text(
                    text,
                    color=ft.Colors.WHITE,
                    size=13,
                    weight=ft.FontWeight.BOLD,
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=6,
        ),
        bgcolor=ft.Colors.BLUE_700,
        border_radius=8,
        height=height,
        padding=ft.Padding(12, 6, 12, 6),
        on_click=on_click,
        ink=True,
        alignment=ft.Alignment.CENTER,
    )


def build_gym_view(page: ft.Page):
    logger.debug("Building Gym View layout...")

    gym_view_state = {
        "year": date.today().year,
        "month": date.today().month,
        "selected_date": date.today().strftime("%Y-%m-%d"),
        "user_lat": 19.0760,
        "user_lon": 72.8777,
    }

    status_text = ft.Text("⚪ Out of Gym", size=14, color=ft.Colors.GREY_400)
    timer_hint = ft.Text("", size=13, color=ft.Colors.BLUE_GREY_200)
    geo_status_banner = ft.Text(
        "", size=12, color=ft.Colors.AMBER_400, weight=ft.FontWeight.W_500
    )

    calendar_container = ft.Container()
    membership_container = ft.Container()
    gym_history_column = ft.Column(spacing=10)

    # ----------------------------------------------------
    # Session Delete Confirmation Dialog
    # ----------------------------------------------------
    session_to_delete_id = None

    def confirm_delete_session(e):
        nonlocal session_to_delete_id
        if session_to_delete_id is not None:
            try:
                db.delete_gym_session(session_to_delete_id)
                logger.info(f"Deleted gym session ID: {session_to_delete_id}")
                delete_session_dialog.open = False
                update_gym_ui()
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Gym session deleted successfully"),
                    bgcolor=ft.Colors.GREEN_700,
                )
                page.snack_bar.open = True
            except Exception as ex:
                logger.exception(f"Failed to delete session: {ex}")
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error: {ex}"), bgcolor=ft.Colors.RED_700
                )
                page.snack_bar.open = True
            finally:
                session_to_delete_id = None
                page.update()

    def cancel_delete_session(e):
        nonlocal session_to_delete_id
        session_to_delete_id = None
        delete_session_dialog.open = False
        page.update()

    delete_session_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(
            "Delete Gym Session", size=16, weight=ft.FontWeight.BOLD
        ),
        content=ft.Text(
            "Are you sure you want to delete this completed gym check-in log?"
        ),
        actions=[
            ft.TextButton("Cancel", on_click=cancel_delete_session),
            ft.FilledButton(
                "Delete",
                on_click=confirm_delete_session,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE
                ),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def prompt_delete_session(e, session_id):
        nonlocal session_to_delete_id
        session_to_delete_id = session_id
        if delete_session_dialog not in page.overlay:
            page.overlay.append(delete_session_dialog)
        delete_session_dialog.open = True
        page.update()

    # ----------------------------------------------------
    # Gym GPS Geofence Configuration Dialog
    # ----------------------------------------------------
    loc_name_field = ft.TextField(label="Gym Name / Branch", value="Gold's Gym / Cult", dense=True)
    loc_lat_field = ft.TextField(label="Gym Latitude", value="19.0760", dense=True)
    loc_lon_field = ft.TextField(label="Gym Longitude", value="72.8777", dense=True)
    loc_radius_field = ft.TextField(label="Allowed Radius (Meters)", value="100", dense=True)

    def close_location_dialog(e=None):
        location_dialog.open = False
        page.update()

    def save_location_click(e):
        try:
            db.save_gym_target_location(
                loc_name_field.value,
                float(loc_lat_field.value),
                float(loc_lon_field.value),
                float(loc_radius_field.value or 100),
            )
            geo_status_banner.value = f"📍 Geofence configured for {loc_name_field.value} (±{loc_radius_field.value}m)"
            geo_status_banner.color = ft.Colors.GREEN_400
            close_location_dialog()
            page.update()
        except ValueError:
            logger.error(
                "Invalid coordinates entered in location config dialog."
            )

    def set_current_location_as_gym(e):
        loc_lat_field.value = str(round(gym_view_state["user_lat"], 5))
        loc_lon_field.value = str(round(gym_view_state["user_lon"], 5))
        page.update()

    current_loc_btn = create_primary_button(
        "Use Device Location",
        set_current_location_as_gym,
        icon=ft.Icons.MY_LOCATION,
        height=36,
    )
    save_loc_btn = create_primary_button(
        "Save GPS", save_location_click, height=36
    )

    location_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("📍 Configure Gym Geofence", weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Punch-ins will be verified against these coordinates:",
                        size=12,
                        color=ft.Colors.GREY_400,
                    ),
                    loc_name_field,      # Line 1
                    loc_lat_field,       # Line 2 (now on its own line)
                    loc_lon_field,       # Line 3 (now on its own line)
                    loc_radius_field,    # Line 4
                    current_loc_btn,     # Line 5
                ],
                tight=True,
                spacing=10,
            ),
            width=320,
            padding=5,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=close_location_dialog),
            save_loc_btn,
        ],
    )

    def open_location_dialog(e):
        saved = db.get_gym_target_location()
        if saved:
            loc_name_field.value = saved[1]
            loc_lat_field.value = str(saved[2])
            loc_lon_field.value = str(saved[3])
            loc_radius_field.value = str(int(saved[4]))
        if location_dialog not in page.overlay:
            page.overlay.append(location_dialog)
        location_dialog.open = True
        page.update()

    # ----------------------------------------------------
    # Membership Dialog
    # ----------------------------------------------------
    mem_name_field = ft.TextField(
        label="Gym / Plan Name", hint_text="e.g. Annual Plan", autofocus=True
    )
    mem_fee_field = ft.TextField(
        label="Fee Paid (₹)",
        keyboard_type=ft.KeyboardType.NUMBER,
        value="15000",
    )
    mem_start_field = ft.TextField(
        label="Start Date (YYYY-MM-DD)",
        value=date.today().strftime("%Y-%m-%d"),
    )
    mem_end_field = ft.TextField(
        label="Due / Expiry Date (YYYY-MM-DD)", hint_text="e.g. 2026-12-31"
    )
    mem_proof_field = ft.TextField(
        label="Proof / Invoice No / ID", hint_text="e.g. Receipt #GG-8921"
    )

    def close_membership_dialog(e=None):
        membership_dialog.open = False
        page.update()

    def save_membership_click(e):
        if not mem_name_field.value or not mem_end_field.value:
            return
        db.save_gym_membership(
            mem_name_field.value,
            mem_fee_field.value or 0.0,
            mem_start_field.value or date.today().strftime("%Y-%m-%d"),
            mem_end_field.value,
            mem_proof_field.value or "",
        )
        close_membership_dialog()
        update_gym_ui()

    save_mem_btn = create_primary_button(
        "Save", save_membership_click, height=36
    )

    membership_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Edit Gym Membership", weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column(
                [
                    mem_name_field,
                    mem_fee_field,
                    mem_start_field,
                    mem_end_field,
                    mem_proof_field,
                ],
                tight=True,
                spacing=10,
            ),
            width=320,
            padding=5,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=close_membership_dialog),
            save_mem_btn,
        ],
    )

    def open_membership_dialog(e):
        mem = db.get_gym_membership()
        if mem:
            mem_name_field.value = mem[1]
            mem_fee_field.value = str(mem[2])
            mem_start_field.value = mem[3]
            mem_end_field.value = mem[4]
            mem_proof_field.value = mem[5]
        if membership_dialog not in page.overlay:
            page.overlay.append(membership_dialog)
        membership_dialog.open = True
        page.update()

    # ----------------------------------------------------
    # Day Detail Dialog (Exercises & Hours)
    # ----------------------------------------------------
    modal_title = ft.Text("Workout Details", weight=ft.FontWeight.BOLD, size=18)
    modal_duration_text = ft.Text(
        "⏱️ 0 hrs 0 mins",
        size=15,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.GREEN_400,
    )
    modal_membership_note = ft.Text(
        "", size=12, color=ft.Colors.PURPLE_200, italic=True
    )
    exercises_list_column = ft.Column(spacing=6)

    ex_name_field = ft.TextField(
        label="Exercise (e.g. Bench Press)", height=48, text_size=13
    )
    ex_sets_field = ft.TextField(
        label="Sets",
        keyboard_type=ft.KeyboardType.NUMBER,
        value="3",
        width=80,
        height=48,
        text_size=13,
    )
    ex_reps_field = ft.TextField(
        label="Reps",
        keyboard_type=ft.KeyboardType.NUMBER,
        value="10",
        width=80,
        height=48,
        text_size=13,
    )
    ex_weight_field = ft.TextField(
        label="Kg",
        keyboard_type=ft.KeyboardType.NUMBER,
        value="50",
        width=85,
        height=48,
        text_size=13,
    )
    ex_notes_field = ft.TextField(
        label="Notes (optional)", height=45, text_size=12
    )

    def close_day_dialog(e=None):
        day_detail_dialog.open = False
        page.update()

    def refresh_day_modal_content():
        target_date = gym_view_state["selected_date"]
        try:
            total_mins, sessions, exercises = db.get_day_workout_details(
                target_date
            )

            hrs = total_mins // 60
            mins = total_mins % 60
            if total_mins > 0:
                modal_duration_text.value = f"⏱️ Total Workout Time: {hrs}h {mins}m ({total_mins} mins)"
                modal_duration_text.color = ft.Colors.GREEN_400
            else:
                modal_duration_text.value = (
                    "⏱️ No gym punch-in logged for this day."
                )
                modal_duration_text.color = ft.Colors.GREY_400

            mem = db.get_gym_membership()
            if mem and mem[4] == target_date:
                modal_membership_note.value = (
                    f"⚠️ GYM MEMBERSHIP DUE / EXPIRY DATE: {mem[1]}"
                )
                modal_membership_note.visible = True
            else:
                modal_membership_note.visible = False

            exercises_list_column.controls.clear()
            if not exercises:
                exercises_list_column.controls.append(
                    ft.Text(
                        "No exercises added yet.",
                        italic=True,
                        size=12,
                        color=ft.Colors.GREY_500,
                    )
                )
            else:
                for ex_id, name, sets, reps, wt, notes in exercises:
                    note_str = f" • {notes}" if notes else ""
                    exercises_list_column.controls.append(
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Column(
                                        [
                                            ft.Text(
                                                f"💪 {name}",
                                                weight=ft.FontWeight.BOLD,
                                                size=13,
                                            ),
                                            ft.Text(
                                                f"{sets} sets × {reps} reps @ {wt} kg{note_str}",
                                                size=11,
                                                color=ft.Colors.GREY_300,
                                            ),
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        icon_color=ft.Colors.RED_400,
                                        icon_size=18,
                                        tooltip="Delete Exercise",
                                        on_click=lambda e, eid=ex_id: remove_exercise(
                                            eid
                                        ),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            bgcolor=ft.Colors.GREY_900,
                            padding=8,
                            border_radius=8,
                        )
                    )
            page.update()
        except Exception as e:
            logger.exception(
                f"Failed to refresh day modal content for {target_date}: {e}"
            )

    def save_exercise_click(e):
        if not ex_name_field.value or not ex_name_field.value.strip():
            return
        target_date = gym_view_state["selected_date"]
        try:
            db.add_workout_exercise(
                target_date,
                ex_name_field.value,
                ex_sets_field.value or 0,
                ex_reps_field.value or 0,
                ex_weight_field.value or 0.0,
                ex_notes_field.value or "",
            )
            ex_name_field.value = ""
            ex_notes_field.value = ""
            refresh_day_modal_content()
        except Exception as ex:
            logger.exception(f"Error handling save_exercise_click: {ex}")

    def remove_exercise(exercise_id):
        try:
            db.delete_workout_exercise(exercise_id)
            refresh_day_modal_content()
        except Exception as ex:
            logger.exception(f"Error deleting exercise ID {exercise_id}: {ex}")

    add_ex_btn = create_primary_button(
        "Add Exercise",
        save_exercise_click,
        icon=ft.Icons.ADD,
        height=40,
    )

    day_detail_dialog = ft.AlertDialog(
        modal=True,
        title=modal_title,
        content=ft.Container(
            content=ft.Column(
                [
                    modal_duration_text,
                    modal_membership_note,
                    ft.Divider(height=10, color=ft.Colors.GREY_800),
                    ft.Text(
                        "Exercises Completed:",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                    ),
                    exercises_list_column,
                    ft.Divider(height=10, color=ft.Colors.GREY_800),
                    ft.Text(
                        "Add Exercise Log:",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ex_name_field,
                    ft.Row(
                        [ex_sets_field, ex_reps_field, ex_weight_field],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ex_notes_field,
                    add_ex_btn,
                ],
                tight=True,
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=330,
            padding=5,
        ),
        actions=[ft.TextButton("Close", on_click=close_day_dialog)],
    )

    def on_calendar_day_click(selected_date_str):
        gym_view_state["selected_date"] = selected_date_str
        modal_title.value = f"🗓️ {selected_date_str}"
        if day_detail_dialog not in page.overlay:
            page.overlay.append(day_detail_dialog)
        day_detail_dialog.open = True
        refresh_day_modal_content()

    def change_gym_month(delta):
        gym_view_state["month"] += delta
        if gym_view_state["month"] > 12:
            gym_view_state["month"] = 1
            gym_view_state["year"] += 1
        elif gym_view_state["month"] < 1:
            gym_view_state["month"] = 12
            gym_view_state["year"] -= 1
        update_gym_ui()

    def build_calendar_view():
        try:
            today = date.today()
            year = gym_view_state["year"]
            month = gym_view_state["month"]
            month_name = calendar.month_name[month]

            gym_days = db.get_workout_dates_for_month(year, month)
            mem = db.get_gym_membership()
            mem_due_date_str = mem[4] if mem else ""

            weeks = calendar.monthcalendar(year, month)
            cal_rows = []

            header_cells = [
                ft.Container(
                    content=ft.Text(
                        d,
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.GREY_400,
                    ),
                    alignment=ft.Alignment.CENTER,
                    width=36,
                    height=24,
                )
                for d in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
            ]
            cal_rows.append(
                ft.Row(
                    controls=header_cells,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                )
            )

            for week in weeks:
                row_cells = []
                for day in week:
                    if day == 0:
                        row_cells.append(ft.Container(width=36, height=36))
                    else:
                        cell_date = date(year, month, day)
                        cell_date_str = cell_date.strftime("%Y-%m-%d")
                        is_today = cell_date == today
                        is_past = cell_date < today
                        went_to_gym = day in gym_days
                        is_due_date = cell_date_str == mem_due_date_str

                        if is_due_date:
                            bg_color = ft.Colors.PURPLE_800
                            txt_color = ft.Colors.WHITE
                        elif went_to_gym:
                            bg_color = ft.Colors.GREEN_700
                            txt_color = ft.Colors.WHITE
                        elif is_past:
                            bg_color = ft.Colors.RED_900
                            txt_color = ft.Colors.RED_200
                        elif is_today:
                            bg_color = ft.Colors.GREY_800
                            txt_color = ft.Colors.WHITE
                        else:
                            bg_color = ft.Colors.GREY_900
                            txt_color = ft.Colors.GREY_600

                        border_side = (
                            ft.Border.all(2, ft.Colors.AMBER_400)
                            if is_today
                            else None
                        )

                        cell_content = ft.Column(
                            [
                                ft.Text(
                                    str(day),
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=txt_color,
                                ),
                                (
                                    ft.Text(
                                        "DUE",
                                        size=8,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.AMBER_300,
                                    )
                                    if is_due_date
                                    else ft.Container()
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=0,
                        )

                        row_cells.append(
                            ft.Container(
                                content=cell_content,
                                alignment=ft.Alignment.CENTER,
                                width=36,
                                height=36,
                                bgcolor=bg_color,
                                border_radius=8,
                                border=border_side,
                                ink=True,
                                on_click=lambda e, d_str=cell_date_str: on_calendar_day_click(
                                    d_str
                                ),
                            )
                        )
                cal_rows.append(
                    ft.Row(
                        controls=row_cells,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=6,
                    )
                )

            cal_header = ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.CHEVRON_LEFT,
                        on_click=lambda e: change_gym_month(-1),
                        icon_size=20,
                    ),
                    ft.Text(
                        f"🗓️ {month_name} {year}",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CHEVRON_RIGHT,
                        on_click=lambda e: change_gym_month(1),
                        icon_size=20,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )

            legend = ft.Row(
                [
                    ft.Container(
                        width=8,
                        height=8,
                        bgcolor=ft.Colors.GREEN_700,
                        border_radius=4,
                    ),
                    ft.Text("Attended", size=10, color=ft.Colors.GREY_400),
                    ft.Container(
                        width=8,
                        height=8,
                        bgcolor=ft.Colors.RED_900,
                        border_radius=4,
                    ),
                    ft.Text("Missed", size=10, color=ft.Colors.GREY_400),
                    ft.Container(
                        width=8,
                        height=8,
                        bgcolor=ft.Colors.PURPLE_800,
                        border_radius=4,
                    ),
                    ft.Text(
                        "Expiry Due",
                        size=10,
                        color=ft.Colors.PURPLE_200,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
            )

            return ft.Container(
                content=ft.Column(
                    [
                        cal_header,
                        legend,
                        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                        ft.Column(controls=cal_rows, spacing=6),
                    ]
                ),
                bgcolor=ft.Colors.GREY_900,
                padding=16,
                border_radius=16,
                width=340,
            )
        except Exception as e:
            logger.exception(f"Error building calendar view: {e}")
            return ft.Container(
                content=ft.Text(
                    "Error loading calendar.", color=ft.Colors.RED_400
                )
            )

    def build_membership_view():
        mem = db.get_gym_membership()
        if not mem:
            return ft.Container(
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(
                                    "💳 Gym Membership",
                                    weight=ft.FontWeight.BOLD,
                                    size=14,
                                ),
                                ft.Text(
                                    "No active membership logged",
                                    size=11,
                                    color=ft.Colors.GREY_400,
                                ),
                            ]
                        ),
                        ft.Container(
                            content=ft.Text(
                                "+ Add Plan",
                                size=12,
                                color=ft.Colors.BLUE_400,
                                weight=ft.FontWeight.BOLD,
                            ),
                            on_click=open_membership_dialog,
                            padding=ft.Padding(8, 4, 8, 4),
                            border=ft.Border.all(1, ft.Colors.BLUE_400),
                            border_radius=6,
                            ink=True,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                bgcolor=ft.Colors.GREY_900,
                padding=12,
                border_radius=12,
                width=340,
            )

        m_id, plan_name, fee_paid, start_date_str, end_date_str, proof_details = (
            mem
        )

        try:
            end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            days_left = (end_dt - date.today()).days
            if days_left > 0:
                badge_text = f"⏳ {days_left} days left"
                badge_color = (
                    ft.Colors.GREEN_400
                    if days_left > 15
                    else ft.Colors.AMBER_400
                )
            elif days_left == 0:
                badge_text = "⚠️ Expires Today!"
                badge_color = ft.Colors.RED_400
            else:
                badge_text = f"❌ Expired {-days_left}d ago"
                badge_color = ft.Colors.RED_400
        except Exception:
            badge_text = f"Due: {end_date_str}"
            badge_color = ft.Colors.PURPLE_300

        proof_display = (
            f"Proof: {proof_details}" if proof_details else "No receipt/proof"
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                f"🏷️ {plan_name}",
                                weight=ft.FontWeight.BOLD,
                                size=15,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    "Edit", size=11, color=ft.Colors.BLUE_300
                                ),
                                on_click=open_membership_dialog,
                                ink=True,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                f"Fee: {format_inr(fee_paid)}",
                                size=12,
                                color=ft.Colors.GREY_300,
                            ),
                            ft.Text(
                                badge_text,
                                size=12,
                                color=badge_color,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=6, color=ft.Colors.GREY_800),
                    ft.Row(
                        [
                            ft.Text(
                                f"📅 Due: {end_date_str}",
                                size=11,
                                color=ft.Colors.PURPLE_200,
                                weight=ft.FontWeight.W_500,
                            ),
                            ft.Text(
                                proof_display,
                                size=11,
                                color=ft.Colors.GREY_400,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=4,
            ),
            bgcolor=ft.Colors.GREY_900,
            padding=12,
            border_radius=12,
            width=340,
        )

    def refresh_gym_history():
        gym_history_column.controls.clear()
        try:
            recent = db.get_recent_gym_history()
            if not recent:
                gym_history_column.controls.append(
                    ft.Text(
                        "No completed sessions yet.",
                        italic=True,
                        color=ft.Colors.GREY_500,
                    )
                )
            for row in recent:
                # Handle both 4-column: (id, p_in, p_out, dur) and 3-column: (p_in, p_out, dur)
                if len(row) >= 4 and isinstance(row[0], int):
                    s_id, p_in, p_out, dur = row[0], row[1], row[2], row[3]
                else:
                    s_id, p_in, p_out, dur = None, row[0], row[1], row[2]

                d_date = (
                    p_in.split(" ")[0]
                    if isinstance(p_in, str) and " " in p_in
                    else str(p_in)
                )
                d_in = (
                    p_in.split(" ")[1][:5]
                    if isinstance(p_in, str) and " " in p_in
                    else "--"
                )
                d_out = (
                    p_out.split(" ")[1][:5]
                    if isinstance(p_out, str) and " " in p_out
                    else "--"
                )

                dur_int = int(dur) if isinstance(dur, (int, float)) else 0
                hrs = dur_int // 60
                mins = dur_int % 60
                dur_str = f"{hrs}h {mins}m" if hrs > 0 else f"{mins} min"

                # Delete button control for this session
                delete_btn = (
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=ft.Colors.RED_400,
                        icon_size=18,
                        tooltip="Delete Session",
                        on_click=lambda e, sid=s_id: prompt_delete_session(
                            e, sid
                        ),
                    )
                    if s_id is not None
                    else ft.Container()
                )

                gym_history_column.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            f"📅 {d_date}",
                                            weight=ft.FontWeight.W_500,
                                            size=13,
                                        ),
                                        ft.Text(
                                            f"{d_in} - {d_out}",
                                            size=11,
                                            color=ft.Colors.GREY_400,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Text(
                                    dur_str,
                                    color=ft.Colors.GREEN_400,
                                    weight=ft.FontWeight.BOLD,
                                    size=13,
                                ),
                                delete_btn,
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        bgcolor=ft.Colors.GREY_900,
                        padding=ft.Padding(12, 6, 8, 6),
                        border_radius=8,
                        width=340,
                        ink=True,
                        on_click=lambda e, d_str=d_date: on_calendar_day_click(
                            d_str
                        ),
                    )
                )
        except Exception as e:
            logger.exception(f"Failed to refresh gym history list: {e}")

    # ----------------------------------------------------
    # Geo-Validated Punch In / Punch Out
    # ----------------------------------------------------
    def on_punch_click(e):
        try:
            active = db.get_active_gym_session()
            if active:
                logger.info(
                    f"Punch-out button clicked for active session: {active[0]}"
                )
                db.punch_out(active[0], active[1])
                geo_status_banner.value = "✅ Punch out successful!"
                geo_status_banner.color = ft.Colors.GREEN_400
            else:
                target_gym = db.get_gym_target_location()
                user_lat = gym_view_state["user_lat"]
                user_lon = gym_view_state["user_lon"]

                if target_gym:
                    g_id, g_name, gym_lat, gym_lon, allowed_radius = target_gym
                    distance = db.calculate_distance_meters(
                        user_lat, user_lon, gym_lat, gym_lon
                    )

                    if distance > allowed_radius:
                        logger.warning(
                            f"Punch-in rejected: {distance:.1f}m away from {g_name} (Max: {allowed_radius}m)"
                        )
                        geo_status_banner.value = f"❌ Too far from gym! Distance: {int(distance)}m (Limit: {int(allowed_radius)}m)"
                        geo_status_banner.color = ft.Colors.RED_400
                        page.update()
                        return

                logger.info(
                    f"Punch-in verified within geofence at ({user_lat}, {user_lon})"
                )
                db.punch_in_with_geo(user_lat, user_lon)
                geo_status_banner.value = (
                    "📍 Verified at Gym. Punch-in successful!"
                )
                geo_status_banner.color = ft.Colors.GREEN_400

            gym_view_state["year"] = date.today().year
            gym_view_state["month"] = date.today().month
            update_gym_ui()
        except Exception as ex:
            logger.exception(f"Error handling punch button click: {ex}")

    gym_action_btn = ft.Container(
        content=ft.Row(alignment=ft.MainAxisAlignment.CENTER),
        alignment=ft.Alignment.CENTER,
        height=52,
        width=340,
    )

    gym_action_container = ft.Container(
        content=gym_action_btn,
        border_radius=12,
        on_click=on_punch_click,
        ink=True,
    )

    geo_header_row = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.LOCATION_ON,
                            size=16,
                            color=ft.Colors.BLUE_400,
                        ),
                        ft.Text(
                            "Geo-Verification Enabled",
                            size=12,
                            color=ft.Colors.BLUE_300,
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                    spacing=4,
                ),
                ft.Container(
                    content=ft.Text(
                        "Config GPS >",
                        size=11,
                        color=ft.Colors.BLUE_400,
                        weight=ft.FontWeight.BOLD,
                    ),
                    on_click=open_location_dialog,
                    ink=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        width=340,
        padding=ft.Padding(4, 0, 4, 0),
    )

    def update_gym_ui():
        try:
            active = db.get_active_gym_session()
            if active:
                gym_action_btn.content = ft.Row(
                    [
                        ft.Icon(ft.Icons.LOGOUT, color=ft.Colors.WHITE),
                        ft.Text(
                            "Punch Out (Leave Gym)",
                            color=ft.Colors.WHITE,
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                )
                gym_action_container.bgcolor = ft.Colors.RED_700
                status_text.value = "🟢 Currently in Gym"
                status_text.color = ft.Colors.GREEN_ACCENT
                in_time = active[1].split(" ")[1][:5]
                timer_hint.value = f"Checked in at: {in_time}"
            else:
                gym_action_btn.content = ft.Row(
                    [
                        ft.Icon(ft.Icons.LOGIN, color=ft.Colors.WHITE),
                        ft.Text(
                            "Punch In (Enter Gym)",
                            color=ft.Colors.WHITE,
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                )
                gym_action_container.bgcolor = ft.Colors.GREEN_700
                status_text.value = "⚪ Out of Gym"
                status_text.color = ft.Colors.GREY_400

                recent_history = db.get_recent_gym_history(limit=1)
                last_out_time = None

                if recent_history and len(recent_history) > 0:
                    row = recent_history[0]
                    p_out = None

                    if len(row) >= 4 and isinstance(row[2], str):
                        p_out = row[2]
                    elif len(row) == 3 and isinstance(row[1], str):
                        p_out = row[1]

                    if p_out and " " in p_out:
                        last_out_time = p_out.split(" ")[1][:5]

                if last_out_time:
                    timer_hint.value = f"Last punch out: {last_out_time}"
                else:
                    timer_hint.value = "No sessions logged"

            calendar_container.content = build_calendar_view()
            membership_container.content = build_membership_view()
            refresh_gym_history()
            page.update()
        except Exception as e:
            logger.exception(f"Error executing update_gym_ui: {e}")

    view_container = ft.Column(
        [
            geo_header_row,
            gym_action_container,
            ft.Container(
                content=ft.Row(
                    [status_text, timer_hint],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                width=340,
                padding=ft.Padding(4, 2, 4, 0),
            ),
            geo_status_banner,
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            calendar_container,
            ft.Divider(height=15, color=ft.Colors.TRANSPARENT),
            membership_container,
            ft.Divider(height=20, color=ft.Colors.GREY_800),
            ft.Text("Recent Sessions", size=16, weight=ft.FontWeight.W_600),
            gym_history_column,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        visible=True,
    )

    return view_container, update_gym_ui