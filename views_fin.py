"""
Finance Tracker View:
Handles daily expense logging at the top, collapsible credit card management (2 cards default),
monthly spending metrics, month/year navigation, card-specific transaction drill-downs,
collapsible recent transactions, delete operations with confirmation, and standard Indian Rupee (INR) numbering.
"""

import calendar
from datetime import datetime, date
import flet as ft
import db
from logger import logger


def format_inr(number: float, include_decimals: bool = True) -> str:
    """
    Formats a number into the Indian Rupee system:
    100000 -> ₹1,00,000.00
    1550000 -> ₹15,50,000.00
    """
    try:
        val = float(number)
    except (ValueError, TypeError):
        return "₹0"

    sign = "-" if val < 0 else ""
    val = abs(val)

    parts = f"{val:.2f}".split(".")
    int_part, dec_part = parts[0], parts[1]

    if len(int_part) <= 3:
        formatted_int = int_part
    else:
        last_three = int_part[-3:]
        remaining = int_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted_int = ",".join(groups) + "," + last_three

    if include_decimals:
        return f"₹{sign}{formatted_int}.{dec_part}"
    return f"₹{sign}{formatted_int}"


def build_finance_view(page: ft.Page):
    """
    Constructs and returns the Finance UI layout and controller hooks.
    """
    logger.debug("Building Finance View layout...")

    finance_view_state = {
        "year": date.today().year,
        "month": date.today().month,
        "show_all_transactions": False,
        "show_all_cards": False,
        "active_card_detail": None  # (card_id, card_name, card_limit, card_spent)
    }

    month_display_text = ft.Text("", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    total_spent_text = ft.Text("₹0", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    cc_dues_text = ft.Text("₹0", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400)

    cards_list_column = ft.Column(spacing=8)
    toggle_cards_container = ft.Container()
    
    expense_history_column = ft.Column(spacing=8)
    toggle_show_container = ft.Container()

    # Expense Form Fields
    exp_title_field = ft.TextField(label="Expense Description", hint_text="e.g. Protein Powder, Groceries", width=340)
    exp_amount_field = ft.TextField(label="Amount (₹)", keyboard_type=ft.KeyboardType.NUMBER, width=340)
    payment_mode_dropdown = ft.Dropdown(
        label="Payment Method",
        width=340,
        options=[ft.dropdown.Option("Cash/UPI")]
    )

    # ----------------------------------------------------
    # Delete Confirmation Dialog Setup
    # ----------------------------------------------------
    item_to_delete = {"type": None, "id": None, "title": ""}

    def close_delete_dialog(e=None):
        delete_confirm_dialog.open = False
        item_to_delete["type"] = None
        item_to_delete["id"] = None
        item_to_delete["title"] = ""
        page.update()

    def confirm_delete_action(e=None):
        target_type = item_to_delete["type"]
        target_id = item_to_delete["id"]
        target_title = item_to_delete["title"]

        if target_type == "expense" and target_id is not None:
            logger.info(f"User confirmed deletion of expense ID: {target_id} ('{target_title}')")
            try:
                db.delete_expense(target_id)
                close_delete_dialog()
                update_finance_ui()

                # Refresh active card detail modal if open
                if finance_view_state["active_card_detail"]:
                    cid, cn, cl, _ = finance_view_state["active_card_detail"]
                    # Recalculate card spend after deletion
                    refreshed_cards = db.get_credit_cards()
                    _, _, cards_summary = db.get_monthly_finance_summary(finance_view_state["year"], finance_view_state["month"])
                    updated_spent = next((cs for c_id, _, _, cs in cards_summary if c_id == cid), 0.0)
                    open_card_details(cid, cn, cl, updated_spent)

            except Exception as ex:
                logger.exception(f"Failed to delete expense ID {target_id}: {ex}")

        elif target_type == "card" and target_id is not None:
            logger.info(f"User confirmed removal of card ID: {target_id} ('{target_title}')")
            try:
                db.delete_credit_card(target_id)
                close_delete_dialog()
                update_finance_ui()
            except Exception as ex:
                logger.exception(f"Failed to remove card ID {target_id}: {ex}")

    delete_dialog_msg = ft.Text("", size=14)

    delete_confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Confirm Deletion", weight=ft.FontWeight.BOLD),
        content=delete_dialog_msg,
        actions=[
            ft.TextButton("Cancel", on_click=close_delete_dialog),
            ft.FilledButton(
                "Delete",
                on_click=confirm_delete_action,
                style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE)
            )
        ],
        actions_alignment=ft.MainAxisAlignment.END
    )

    def prompt_delete_expense(exp_id: int, title: str):
        item_to_delete["type"] = "expense"
        item_to_delete["id"] = exp_id
        item_to_delete["title"] = title
        delete_dialog_msg.value = f"Are you sure you want to delete '{title}'?"
        if delete_confirm_dialog not in page.overlay:
            page.overlay.append(delete_confirm_dialog)
        delete_confirm_dialog.open = True
        page.update()

    def prompt_delete_card(card_id: int, card_name: str):
        item_to_delete["type"] = "card"
        item_to_delete["id"] = card_id
        item_to_delete["title"] = card_name
        delete_dialog_msg.value = f"Are you sure you want to remove '{card_name}'? Expenses linked to it will not be deleted."
        if delete_confirm_dialog not in page.overlay:
            page.overlay.append(delete_confirm_dialog)
        delete_confirm_dialog.open = True
        page.update()

    # ----------------------------------------------------
    # Month / Year Navigation
    # ----------------------------------------------------
    def change_finance_month(delta):
        old_month, old_year = finance_view_state["month"], finance_view_state["year"]
        finance_view_state["month"] += delta
        if finance_view_state["month"] > 12:
            finance_view_state["month"] = 1
            finance_view_state["year"] += 1
        elif finance_view_state["month"] < 1:
            finance_view_state["month"] = 12
            finance_view_state["year"] -= 1
        finance_view_state["show_all_transactions"] = False
        finance_view_state["show_all_cards"] = False
        logger.debug(f"Finance month navigated from {old_year}-{old_month:02d} to {finance_view_state['year']}-{finance_view_state['month']:02d}")
        update_finance_ui()

    month_nav_row = ft.Container(
        content=ft.Row([
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=lambda e: change_finance_month(-1), icon_size=20),
            month_display_text,
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=lambda e: change_finance_month(1), icon_size=20),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        bgcolor=ft.Colors.GREY_900,
        padding=ft.Padding(12, 4, 12, 4),
        border_radius=12,
        width=340
    )

    # ----------------------------------------------------
    # Add Card Dialog
    # ----------------------------------------------------
    new_card_name = ft.TextField(label="Card Name (e.g. HDFC Regalia, ICICI Amazon)", autofocus=True)
    new_card_limit = ft.TextField(label="Credit Limit (₹)", keyboard_type=ft.KeyboardType.NUMBER, value="50000")

    def close_card_dialog(e=None):
        logger.debug("Closing add credit card dialog.")
        card_dialog.open = False
        page.update()

    def save_new_card(e=None):
        if not new_card_name.value or not new_card_name.value.strip():
            logger.warning("Attempted to add card with an empty name.")
            return

        c_name = new_card_name.value.strip()
        c_limit = new_card_limit.value or "0"
        logger.info(f"User requested adding credit card '{c_name}' with limit ₹{c_limit}")

        try:
            db.add_credit_card(c_name, c_limit)
            new_card_name.value = ""
            new_card_limit.value = "50000"
            close_card_dialog()
            update_finance_ui()
        except Exception as ex:
            logger.exception(f"Error during save_new_card: {ex}")

    card_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Add Credit Card", weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column([
                new_card_name,
                new_card_limit
            ], tight=True, spacing=12),
            width=300,
            padding=10
        ),
        actions=[
            ft.TextButton("Cancel", on_click=close_card_dialog),
            ft.ElevatedButton("Save Card", on_click=save_new_card) if hasattr(ft, "ElevatedButton") else ft.Button("Save Card", on_click=save_new_card),
        ],
        actions_alignment=ft.MainAxisAlignment.END
    )

    def open_card_dialog(e):
        logger.debug("Opening add credit card dialog.")
        if card_dialog not in page.overlay:
            page.overlay.append(card_dialog)
        card_dialog.open = True
        page.update()

    # ----------------------------------------------------
    # Card Specific Expenses Modal
    # ----------------------------------------------------
    card_modal_title = ft.Text("", weight=ft.FontWeight.BOLD, size=16)
    card_modal_summary = ft.Text("", size=13, color=ft.Colors.GREY_300)
    card_expenses_list = ft.Column(spacing=6)

    def close_card_detail_dialog(e=None):
        finance_view_state["active_card_detail"] = None
        card_detail_dialog.open = False
        page.update()

    card_detail_dialog = ft.AlertDialog(
        modal=True,
        title=card_modal_title,
        content=ft.Container(
            content=ft.Column([
                card_modal_summary,
                ft.Divider(height=10, color=ft.Colors.GREY_800),
                ft.Text("Transactions this month:", size=13, weight=ft.FontWeight.BOLD),
                card_expenses_list
            ], tight=True, spacing=8, scroll=ft.ScrollMode.AUTO),
            width=330,
            padding=5
        ),
        actions=[
            ft.TextButton("Close", on_click=close_card_detail_dialog)
        ]
    )

    def open_card_details(card_id, card_name, card_limit, card_spent):
        yr = finance_view_state["year"]
        mo = finance_view_state["month"]
        month_name = calendar.month_name[mo]
        finance_view_state["active_card_detail"] = (card_id, card_name, card_limit, card_spent)

        logger.info(f"Opening expense breakdown for card '{card_name}' for {month_name} {yr}")
        card_modal_title.value = f"💳 {card_name}"
        card_modal_summary.value = f"{month_name} {yr} Spend: {format_inr(card_spent)} / {format_inr(card_limit, include_decimals=False)}"

        card_expenses_list.controls.clear()
        transactions = db.get_card_monthly_expenses(card_id, yr, mo)
        if not transactions:
            card_expenses_list.controls.append(
                ft.Text(f"No transactions found for {month_name} {yr}.", italic=True, size=12, color=ft.Colors.GREY_500)
            )
        else:
            for exp_id, title, amt, dt in transactions:
                d_time = dt.split(" ")[0][5:]
                card_expenses_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Text(title, weight=ft.FontWeight.W_500, size=13),
                                ft.Text(d_time, size=11, color=ft.Colors.GREY_400)
                            ], spacing=2, expand=True),
                            ft.Text(format_inr(amt), weight=ft.FontWeight.BOLD, color=ft.Colors.RED_300, size=13),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=ft.Colors.RED_400,
                                icon_size=16,
                                tooltip="Delete Expense",
                                on_click=lambda e, eid=exp_id, et=title: prompt_delete_expense(eid, et)
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        bgcolor=ft.Colors.GREY_900,
                        padding=ft.Padding(8, 6, 4, 6),
                        border_radius=8
                    )
                )

        if card_detail_dialog not in page.overlay:
            page.overlay.append(card_detail_dialog)
        card_detail_dialog.open = True
        page.update()

    # ----------------------------------------------------
    # Expense Operations
    # ----------------------------------------------------
    def log_new_expense(e):
        if not exp_title_field.value or not exp_amount_field.value:
            logger.warning("User attempted to log expense with missing title or amount.")
            return

        mode = payment_mode_dropdown.value or "Cash/UPI"
        card_id = None

        cards = db.get_credit_cards()
        for c_id, c_name, _ in cards:
            if c_name == mode:
                card_id = c_id
                break

        try:
            amt = float(exp_amount_field.value)
            logger.info(f"Logging expense '{exp_title_field.value}' ({format_inr(amt)}) using payment mode: {mode}")
            db.add_expense(exp_title_field.value, amt, mode, card_id)
            exp_title_field.value = ""
            exp_amount_field.value = ""
            
            # Snap back to current date so newly logged expense is in view
            finance_view_state["year"] = date.today().year
            finance_view_state["month"] = date.today().month
            finance_view_state["show_all_transactions"] = False
            update_finance_ui()
        except ValueError:
            logger.error(f"Invalid numeric amount entered for expense: '{exp_amount_field.value}'")
        except Exception as ex:
            logger.exception(f"Unexpected error while logging expense: {ex}")

    def toggle_show_more_transactions(e):
        finance_view_state["show_all_transactions"] = not finance_view_state["show_all_transactions"]
        update_finance_ui()

    def toggle_show_more_cards(e):
        finance_view_state["show_all_cards"] = not finance_view_state["show_all_cards"]
        update_finance_ui()

    def update_finance_ui():
        yr = finance_view_state["year"]
        mo = finance_view_state["month"]
        show_all_tx = finance_view_state["show_all_transactions"]
        show_all_cards = finance_view_state["show_all_cards"]
        month_name = calendar.month_name[mo]
        month_display_text.value = f"🗓️ {month_name} {yr}"

        logger.debug(f"Updating Finance View UI for {month_name} {yr} (show_all_tx={show_all_tx}, show_all_cards={show_all_cards})...")
        try:
            tot_spent, cc_dues, cards_summary = db.get_monthly_finance_summary(yr, mo)
            total_spent_text.value = format_inr(tot_spent)
            cc_dues_text.value = format_inr(cc_dues)

            all_cards = db.get_credit_cards()
            payment_mode_dropdown.options = [ft.dropdown.Option("Cash/UPI")] + [
                ft.dropdown.Option(c[1]) for c in all_cards
            ]
            if not payment_mode_dropdown.value:
                payment_mode_dropdown.value = "Cash/UPI"

            # ----------------------------------------------------
            # Sync Cards List (Show 2 by default)
            # ----------------------------------------------------
            cards_list_column.controls.clear()
            total_cards_count = len(cards_summary)
            displayed_cards = cards_summary if show_all_cards else cards_summary[:2]

            if not displayed_cards:
                cards_list_column.controls.append(
                    ft.Text("No credit cards added yet.", italic=True, color=ft.Colors.GREY_500)
                )
            for c_id, c_name, c_limit, c_spent in displayed_cards:
                utilization = (c_spent / c_limit * 100) if c_limit > 0 else 0
                spent_str = format_inr(c_spent, include_decimals=False)
                limit_str = format_inr(c_limit, include_decimals=False)

                cards_list_column.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(f"💳 {c_name}", weight=ft.FontWeight.BOLD, size=15),
                                ft.Row([
                                    ft.Text("View Spends >", size=11, color=ft.Colors.BLUE_300, italic=True),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        icon_color=ft.Colors.RED_400,
                                        icon_size=18,
                                        on_click=lambda e, cid=c_id, cn=c_name: prompt_delete_card(cid, cn)
                                    )
                                ], spacing=4)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Row([
                                ft.Text(f"Used: {spent_str} / {limit_str}", size=12, color=ft.Colors.GREY_300),
                                ft.Text(
                                    f"{utilization:.1f}%",
                                    size=12,
                                    color=ft.Colors.RED_400 if utilization > 30 else ft.Colors.GREEN_400,
                                    weight=ft.FontWeight.BOLD
                                )
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ]),
                        bgcolor=ft.Colors.GREY_900,
                        padding=12,
                        border_radius=10,
                        width=340,
                        ink=True,
                        on_click=lambda e, cid=c_id, cn=c_name, cl=c_limit, cs=c_spent: open_card_details(cid, cn, cl, cs)
                    )
                )

            # Toggle button for Cards (if > 2)
            if total_cards_count > 2:
                btn_card_label = "Show Less Cards" if show_all_cards else f"Show More Cards ({total_cards_count - 2} more)"
                btn_card_icon = ft.Icons.KEYBOARD_ARROW_UP if show_all_cards else ft.Icons.KEYBOARD_ARROW_DOWN
                toggle_cards_container.content = ft.Container(
                    content=ft.Row([
                        ft.Icon(btn_card_icon, color=ft.Colors.BLUE_400, size=16),
                        ft.Text(btn_card_label, color=ft.Colors.BLUE_400, size=12, weight=ft.FontWeight.W_600)
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=4),
                    padding=ft.Padding(8, 6, 8, 6),
                    border_radius=8,
                    bgcolor=ft.Colors.GREY_900,
                    width=340,
                    on_click=toggle_show_more_cards,
                    ink=True
                )
                toggle_cards_container.visible = True
            else:
                toggle_cards_container.visible = False

            # ----------------------------------------------------
            # Sync Recent Expense List (Show 5 by default)
            # ----------------------------------------------------
            all_month_expenses = db.get_recent_expenses(limit=1000, year=yr, month=mo)
            total_tx_count = len(all_month_expenses)
            displayed_expenses = all_month_expenses if show_all_tx else all_month_expenses[:5]

            expense_history_column.controls.clear()
            if not displayed_expenses:
                expense_history_column.controls.append(
                    ft.Text(f"No expenses logged for {month_name} {yr}.", italic=True, color=ft.Colors.GREY_500)
                )
            else:
                for exp_id, title, amount, mode, d_logged in displayed_expenses:
                    d_time = d_logged.split(" ")[0][5:]
                    expense_history_column.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Column([
                                    ft.Text(title, weight=ft.FontWeight.W_500),
                                    ft.Text(f"{d_time} • {mode}", size=11, color=ft.Colors.GREY_400)
                                ], spacing=2, expand=True),
                                ft.Text(format_inr(amount), weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_color=ft.Colors.RED_400,
                                    icon_size=18,
                                    tooltip="Delete Expense",
                                    on_click=lambda e, eid=exp_id, et=title: prompt_delete_expense(eid, et)
                                )
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            bgcolor=ft.Colors.GREY_900,
                            padding=ft.Padding(10, 8, 4, 8),
                            border_radius=8,
                            width=340
                        )
                    )

            # Toggle button for Transactions (if > 5)
            if total_tx_count > 5:
                btn_tx_label = "Show Less" if show_all_tx else f"Show More ({total_tx_count - 5} more)"
                btn_tx_icon = ft.Icons.KEYBOARD_ARROW_UP if show_all_tx else ft.Icons.KEYBOARD_ARROW_DOWN
                toggle_show_container.content = ft.Container(
                    content=ft.Row([
                        ft.Icon(btn_tx_icon, color=ft.Colors.BLUE_400, size=16),
                        ft.Text(btn_tx_label, color=ft.Colors.BLUE_400, size=13, weight=ft.FontWeight.W_600)
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=4),
                    padding=ft.Padding(8, 6, 8, 6),
                    border_radius=8,
                    bgcolor=ft.Colors.GREY_900,
                    width=340,
                    on_click=toggle_show_more_transactions,
                    ink=True
                )
                toggle_show_container.visible = True
            else:
                toggle_show_container.visible = False

            page.update()
        except Exception as e:
            logger.exception(f"Error executing update_finance_ui: {e}")

    kpi_row = ft.Row([
        ft.Container(
            content=ft.Column([
                ft.Text("THIS MONTH SPENT", size=10, color=ft.Colors.GREY_400, weight=ft.FontWeight.BOLD),
                total_spent_text
            ]),
            bgcolor=ft.Colors.GREY_900, padding=12, border_radius=12, width=165
        ),
        ft.Container(
            content=ft.Column([
                ft.Text("TOTAL CC DUE", size=10, color=ft.Colors.GREY_400, weight=ft.FontWeight.BOLD),
                cc_dues_text
            ]),
            bgcolor=ft.Colors.GREY_900, padding=12, border_radius=12, width=165
        )
    ], alignment=ft.MainAxisAlignment.CENTER, spacing=10)

    # Compact Add Card Button
    small_add_card_btn = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.ADD, color=ft.Colors.BLUE_400, size=14),
            ft.Text("Add Card", color=ft.Colors.BLUE_400, size=12, weight=ft.FontWeight.W_600)
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=3),
        border=ft.Border.all(1, ft.Colors.BLUE_400),
        border_radius=6,
        padding=ft.Padding(8, 4, 8, 4),
        on_click=open_card_dialog,
        ink=True
    )

    cards_header_row = ft.Container(
        content=ft.Row([
            ft.Text("💳 Your Cards & Dues", size=15, weight=ft.FontWeight.BOLD),
            small_add_card_btn
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        width=340
    )

    log_expense_btn = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.ADD_CARD, color=ft.Colors.WHITE),
            ft.Text("Add Expense", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
        ], alignment=ft.MainAxisAlignment.CENTER),
        bgcolor=ft.Colors.BLUE_700,
        height=48,
        width=340,
        border_radius=10,
        on_click=log_new_expense,
        ink=True,
        alignment=ft.Alignment.CENTER
    )

    # Reordered layout: Month Nav -> KPIs -> Log Expense -> Cards (with Show More) -> Transactions
    view_container = ft.Column([
        month_nav_row,
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        kpi_row,
        ft.Divider(height=15, color=ft.Colors.GREY_800),
        ft.Text("📝 Log an Expense", size=16, weight=ft.FontWeight.BOLD),
        exp_title_field,
        exp_amount_field,
        payment_mode_dropdown,
        log_expense_btn,
        ft.Divider(height=15, color=ft.Colors.GREY_800),
        cards_header_row,
        cards_list_column,
        toggle_cards_container,
        ft.Divider(height=20, color=ft.Colors.GREY_800),
        ft.Text("Month Transactions", size=16, weight=ft.FontWeight.BOLD),
        expense_history_column,
        toggle_show_container
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, visible=False)

    return view_container, update_finance_ui