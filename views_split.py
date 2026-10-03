"""
views_split.py:
GyFi Splitwise Module View.
"""

from datetime import datetime
import db
from debt_engine import calculate_group_settlements
import flet as ft
from logger import logger


def build_split_view(page: ft.Page):
    logger.debug("Building Splitwise View layout...")

    split_state = {"active_group_id": None, "active_group_name": ""}

    groups_list_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
    members_chips_row = ft.Row(wrap=True, spacing=6)
    expenses_list_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
    settlements_column = ft.Column(spacing=8)

    # ----------------------------------------------------
    # Dialog: Create Group
    # ----------------------------------------------------
    new_group_name_field = ft.TextField(
        label="Group Name", hint_text="e.g. Goa Trip, Flat 402", dense=True
    )

    def close_create_group_dialog(e=None):
        create_group_dialog.open = False
        page.update()

    def save_new_group_click(e):
        if not new_group_name_field.value or not new_group_name_field.value.strip():
            return
        g_id = db.create_split_group(new_group_name_field.value.strip())
        new_group_name_field.value = ""
        close_create_group_dialog()
        load_groups()
        select_group(g_id)

    create_group_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Create New Split Group", weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=new_group_name_field, width=310, padding=5
        ),
        actions=[
            ft.TextButton("Cancel", on_click=close_create_group_dialog),
            ft.FilledButton(
                "Create",
                on_click=save_new_group_click,
                style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700),
            ),
        ],
    )

    def open_create_group_dialog(e):
        if create_group_dialog not in page.overlay:
            page.overlay.append(create_group_dialog)
        create_group_dialog.open = True
        page.update()

    # ----------------------------------------------------
    # Dialog: Add Group Member
    # ----------------------------------------------------
    member_name_field = ft.TextField(
        label="Member Name", hint_text="e.g. Rahul", dense=True
    )
    member_upi_field = ft.TextField(
        label="UPI ID (Optional)", hint_text="e.g. rahul@okaxis", dense=True
    )

    def close_add_member_dialog(e=None):
        add_member_dialog.open = False
        page.update()

    def save_member_click(e):
        if not member_name_field.value or not member_name_field.value.strip():
            return
        g_id = split_state["active_group_id"]
        if g_id:
            db.add_group_member(
                g_id,
                member_name_field.value.strip(),
                (
                    member_upi_field.value.strip()
                    if member_upi_field.value
                    else ""
                ),
            )
            member_name_field.value = ""
            member_upi_field.value = ""
            close_add_member_dialog()
            refresh_active_group_data()

    add_member_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Add Group Member", weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column(
                [member_name_field, member_upi_field], tight=True, spacing=10
            ),
            width=310,
            padding=5,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=close_add_member_dialog),
            ft.FilledButton(
                "Add",
                on_click=save_member_click,
                style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700),
            ),
        ],
    )

    def open_add_member_dialog(e):
        if not split_state["active_group_id"]:
            return
        if add_member_dialog not in page.overlay:
            page.overlay.append(add_member_dialog)
        add_member_dialog.open = True
        page.update()

    # ----------------------------------------------------
    # Dialog: Add Shared Expense (Equal & Manual/Custom)
    # ----------------------------------------------------
    exp_desc_field = ft.TextField(
        label="Description",
        hint_text="e.g. Dinner, Fuel, Groceries",
        dense=True,
    )
    exp_amount_field = ft.TextField(
        label="Total Amount (₹)",
        keyboard_type=ft.KeyboardType.NUMBER,
        dense=True,
    )
    exp_payer_dropdown = ft.Dropdown(label="Paid By", dense=True, width=310)

    # Mode Selector: Equal vs Manual Custom
    split_mode_radio = ft.RadioGroup(
        content=ft.Row(
            [
                ft.Radio(value="EQUAL", label="Split Equally"),
                ft.Radio(value="CUSTOM", label="Manual / Custom"),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=16,
        ),
        value="EQUAL",
    )

    split_validation_hint = ft.Text(
        "", size=11, weight=ft.FontWeight.W_500, visible=False
    )
    split_members_container = ft.Column(spacing=6)

    # Registry tracking: {member_id: {"checkbox": ft.Checkbox, "amount_field": ft.TextField}}
    member_split_inputs = {}

    def recalculate_equal_shares():
        """Auto-computes equal breakdown for checked members."""
        try:
            total_val = float(exp_amount_field.value or 0)
        except ValueError:
            total_val = 0.0

        selected_ids = [
            m_id for m_id, item in member_split_inputs.items()
            if item["checkbox"].value
        ]

        if selected_ids and total_val > 0:
            share = round(total_val / len(selected_ids), 2)
            for m_id, item in member_split_inputs.items():
                if item["checkbox"].value:
                    item["amount_field"].value = f"{share:.2f}"
                else:
                    item["amount_field"].value = "0.00"
        else:
            for item in member_split_inputs.values():
                item["amount_field"].value = "0.00"

        validate_custom_sum()

    def validate_custom_sum():
        """Calculates differences between individual inputs and the total bill."""
        try:
            total_amt = float(exp_amount_field.value or 0)
        except ValueError:
            total_amt = 0.0

        current_sum = 0.0
        for item in member_split_inputs.values():
            try:
                amt = float(item["amount_field"].value or 0)
                current_sum += amt
            except ValueError:
                pass

        current_sum = round(current_sum, 2)
        diff = round(total_amt - current_sum, 2)

        if split_mode_radio.value == "CUSTOM":
            split_validation_hint.visible = True
            if abs(diff) < 0.01:
                split_validation_hint.value = f"✅ Sum: ₹{current_sum:,.2f} / ₹{total_amt:,.2f} (Matches)"
                split_validation_hint.color = ft.Colors.GREEN_400
            elif diff > 0:
                split_validation_hint.value = f"⚠️ Remaining: ₹{diff:,.2f} (Total: ₹{total_amt:,.2f})"
                split_validation_hint.color = ft.Colors.AMBER_400
            else:
                split_validation_hint.value = f"❌ Overallocated by ₹{-diff:,.2f} (Total: ₹{total_amt:,.2f})"
                split_validation_hint.color = ft.Colors.RED_400
        else:
            split_validation_hint.visible = False

        page.update()

    def on_split_mode_change(e):
        is_custom = split_mode_radio.value == "CUSTOM"
        for item in member_split_inputs.values():
            item["amount_field"].read_only = not is_custom
            item["amount_field"].border_color = (
                ft.Colors.BLUE_400 if is_custom else ft.Colors.GREY_700
            )

        if not is_custom:
            recalculate_equal_shares()
        else:
            validate_custom_sum()

    split_mode_radio.on_change = on_split_mode_change

    def on_amount_field_change(e):
        if split_mode_radio.value == "EQUAL":
            recalculate_equal_shares()
        else:
            validate_custom_sum()

    exp_amount_field.on_change = on_amount_field_change

    def on_member_cb_toggle(m_id):
        if split_mode_radio.value == "EQUAL":
            recalculate_equal_shares()
        else:
            if not member_split_inputs[m_id]["checkbox"].value:
                member_split_inputs[m_id]["amount_field"].value = "0.00"
            validate_custom_sum()

    def close_add_expense_dialog(e=None):
        add_expense_dialog.open = False
        page.update()

    def save_shared_expense_click(e):
        # 1. Validation checks with user feedback
        if not exp_desc_field.value or not exp_desc_field.value.strip():
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Please enter an expense description."),
                bgcolor=ft.Colors.RED_700,
            )
            page.snack_bar.open = True
            page.update()
            return

        if not exp_amount_field.value or not exp_amount_field.value.strip():
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Please enter a total bill amount."),
                bgcolor=ft.Colors.RED_700,
            )
            page.snack_bar.open = True
            page.update()
            return

        if not exp_payer_dropdown.value:
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Please select who paid the bill."),
                bgcolor=ft.Colors.RED_700,
            )
            page.snack_bar.open = True
            page.update()
            return

        try:
            total_amt = float(exp_amount_field.value.strip())
            if total_amt <= 0:
                raise ValueError("Amount must be greater than 0")

            payer_id = int(exp_payer_dropdown.value)
            splits = {}

            if split_mode_radio.value == "EQUAL":
                selected_ids = [
                    m_id for m_id, item in member_split_inputs.items()
                    if item["checkbox"].value
                ]

                if not selected_ids:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("Select at least one member to split the bill."),
                        bgcolor=ft.Colors.RED_700,
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

                # Calculate equal share per selected member
                share_each = round(total_amt / len(selected_ids), 2)
                for m_id in selected_ids:
                    splits[m_id] = share_each

            else:
                # CUSTOM / Manual Mode
                total_split_sum = 0.0
                for m_id, item in member_split_inputs.items():
                    val_str = item["amount_field"].value or "0"
                    try:
                        val = float(val_str.strip())
                    except ValueError:
                        val = 0.0

                    if val > 0:
                        splits[m_id] = round(val, 2)
                        total_split_sum += val

                total_split_sum = round(total_split_sum, 2)
                diff = abs(total_split_sum - total_amt)

                # Tolerance of ₹0.50 for rounding
                if diff > 0.50:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Amounts (₹{total_split_sum:.2f}) do not match Total (₹{total_amt:.2f})"),
                        bgcolor=ft.Colors.RED_700,
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

            if not splits:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("No member shares allocated."),
                    bgcolor=ft.Colors.RED_700,
                )
                page.snack_bar.open = True
                page.update()
                return

            # Insert into database
            db.add_split_expense(
                group_id=split_state["active_group_id"],
                description=exp_desc_field.value.strip(),
                total_amount=total_amt,
                paid_by_member_id=payer_id,
                member_splits=splits,
                split_type=split_mode_radio.value,
            )

            # Reset fields and refresh UI
            exp_desc_field.value = ""
            exp_amount_field.value = ""
            close_add_expense_dialog()
            refresh_active_group_data()

            page.snack_bar = ft.SnackBar(
                content=ft.Text("Shared bill added successfully!"),
                bgcolor=ft.Colors.GREEN_700,
            )
            page.snack_bar.open = True
            page.update()

        except ValueError as ve:
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Invalid input: {ve}"),
                bgcolor=ft.Colors.RED_700,
            )
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            logger.exception(f"Error saving shared expense: {ex}")
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Failed to save bill: {ex}"),
                bgcolor=ft.Colors.RED_700,
            )
            page.snack_bar.open = True
            page.update()

    add_expense_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Add Shared Expense", weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column(
                [
                    exp_desc_field,
                    exp_amount_field,
                    exp_payer_dropdown,
                    ft.Divider(height=10, color=ft.Colors.GREY_800),
                    split_mode_radio,
                    split_validation_hint,
                    ft.Text(
                        "Split Allocation:",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.GREY_400,
                    ),
                    split_members_container,
                ],
                tight=True,
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=330,
            padding=5,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=close_add_expense_dialog),
            ft.FilledButton(
                "Save Bill",
                on_click=save_shared_expense_click,
                style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700),
            ),
        ],
    )

    def open_add_expense_dialog(e):
        g_id = split_state["active_group_id"]
        if not g_id:
            return
        members = db.get_group_members(g_id)
        if not members:
            page.snack_bar = ft.SnackBar(
                ft.Text("Add members to the group first!"),
                bgcolor=ft.Colors.RED_700,
            )
            page.snack_bar.open = True
            page.update()
            return

        exp_payer_dropdown.options = [
            ft.dropdown.Option(str(m[0]), m[2]) for m in members
        ]
        exp_payer_dropdown.value = str(members[0][0])

        split_mode_radio.value = "EQUAL"
        split_validation_hint.visible = False
        member_split_inputs.clear()
        split_members_container.controls.clear()

        # Build each member's input line: [Checkbox (Name)] + [Amount Box (₹)]
        for m in members:
            m_id = m[0]
            m_name = m[2]

            cb = ft.Checkbox(label=m_name, value=True)
            amt_box = ft.TextField(
                value="0.00",
                width=85,
                height=38,
                text_size=12,
                keyboard_type=ft.KeyboardType.NUMBER,
                dense=True,
                read_only=True,
                prefix=ft.Text("₹", size=12),
                border_color=ft.Colors.GREY_700,
            )

            # Bind closures to capture current member id
            cb.on_change = (lambda mem_id: lambda evt: on_member_cb_toggle(mem_id))(m_id)
            amt_box.on_change = lambda evt: validate_custom_sum()

            member_split_inputs[m_id] = {
                "checkbox": cb,
                "amount_field": amt_box,
            }

            split_members_container.controls.append(
                ft.Row(
                    [cb, amt_box],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        if add_expense_dialog not in page.overlay:
            page.overlay.append(add_expense_dialog)
        add_expense_dialog.open = True
        page.update()
    # ----------------------------------------------------
    # Data Loaders
    # ----------------------------------------------------
    def select_group(group_id: int):
        split_state["active_group_id"] = group_id
        groups = db.get_split_groups()
        for g in groups:
            if g[0] == group_id:
                split_state["active_group_name"] = g[1]
                active_group_title.value = f"👥 {g[1]}"
                break
        load_groups()
        refresh_active_group_data()

    def load_groups():
        groups_list_column.controls.clear()
        groups = db.get_split_groups()
        if not groups:
            groups_list_column.controls.append(
                ft.Text(
                    "No split groups found. Tap '+ New Group' to start.",
                    size=12,
                    color=ft.Colors.GREY_500,
                    italic=True,
                )
            )
            return

        for g_id, g_name, g_created in groups:
            is_active = g_id == split_state["active_group_id"]
            border = (
                ft.Border.all(1.5, ft.Colors.BLUE_400)
                if is_active
                else ft.Border.all(1, ft.Colors.GREY_800)
            )
            bg = ft.Colors.GREY_800 if is_active else ft.Colors.GREY_900

            groups_list_column.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(
                                        g_name,
                                        weight=ft.FontWeight.BOLD,
                                        size=13,
                                        color=ft.Colors.WHITE,
                                    ),
                                    ft.Text(
                                        f"Created {g_created[:10]}",
                                        size=10,
                                        color=ft.Colors.GREY_400,
                                    ),
                                ],
                                spacing=1,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=ft.Colors.RED_400,
                                icon_size=16,
                                on_click=lambda e, gid=g_id: delete_group_click(
                                    gid
                                ),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    bgcolor=bg,
                    padding=ft.Padding(10, 6, 6, 6),
                    border_radius=8,
                    border=border,
                    width=330,
                    ink=True,
                    on_click=lambda e, gid=g_id: select_group(gid),
                )
            )
        page.update()

    def delete_group_click(group_id):
        db.delete_split_group(group_id)
        if split_state["active_group_id"] == group_id:
            split_state["active_group_id"] = None
            split_state["active_group_name"] = ""
            active_group_title.value = "Select a Group"
        load_groups()
        refresh_active_group_data()

    def refresh_active_group_data():
        g_id = split_state["active_group_id"]
        members_chips_row.controls.clear()
        expenses_list_column.controls.clear()
        settlements_column.controls.clear()

        if not g_id:
            members_chips_row.controls.append(
                ft.Text(
                    "Select a group above.", color=ft.Colors.GREY_500, size=12
                )
            )
            page.update()
            return

        # 1. Render Members
        members = db.get_group_members(g_id)
        if not members:
            members_chips_row.controls.append(
                ft.Text(
                    "No members added yet.", color=ft.Colors.GREY_500, size=12
                )
            )
        else:
            for m_id, _, m_name, m_upi in members:
                upi_label = f" ({m_upi})" if m_upi else ""
                members_chips_row.controls.append(
                    ft.Chip(
                        label=ft.Text(f"{m_name}{upi_label}", size=11),
                        bgcolor=ft.Colors.GREY_800,
                        on_delete=lambda e, mid=m_id: remove_member_click(mid),
                    )
                )

        # 2. Render Expenses
        expenses = db.get_group_expenses(g_id)
        if not expenses:
            expenses_list_column.controls.append(
                ft.Text(
                    "No expenses logged in this group.",
                    size=12,
                    color=ft.Colors.GREY_500,
                    italic=True,
                )
            )
        else:
            for (
                exp_id,
                desc,
                total,
                payer_id,
                payer_name,
                _,
                dt_str,
            ) in expenses:
                expenses_list_column.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            desc,
                                            weight=ft.FontWeight.BOLD,
                                            size=13,
                                        ),
                                        ft.Text(
                                            f"Paid by {payer_name} • {dt_str[:10]}",
                                            size=10,
                                            color=ft.Colors.GREY_400,
                                        ),
                                    ],
                                    expand=True,
                                    spacing=1,
                                ),
                                ft.Text(
                                    f"₹{total:,.2f}",
                                    weight=ft.FontWeight.BOLD,
                                    size=13,
                                    color=ft.Colors.GREEN_400,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_color=ft.Colors.RED_400,
                                    icon_size=16,
                                    on_click=lambda e, eid=exp_id: remove_expense_click(
                                        eid
                                    ),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        bgcolor=ft.Colors.GREY_900,
                        padding=ft.Padding(10, 6, 6, 6),
                        border_radius=8,
                        border=ft.Border.all(1, ft.Colors.GREY_800),
                        width=330,
                    )
                )

        # 3. Compute and Render Settlements
        m_list, split_rows = db.get_group_settlement_data(g_id)
        _, settlements = calculate_group_settlements(m_list, split_rows)

        if not settlements:
            settlements_column.controls.append(
                ft.Container(
                    content=ft.Text(
                        "✨ All debts are settled!",
                        color=ft.Colors.GREEN_400,
                        size=12,
                        weight=ft.FontWeight.W_500,
                    ),
                    padding=8,
                    alignment=ft.Alignment.CENTER,
                )
            )
        else:
            for item in settlements:
                settlements_column.controls.append(build_settlement_card(item))

        page.update()

    def remove_member_click(m_id):
        db.delete_group_member(m_id)
        refresh_active_group_data()

    def remove_expense_click(exp_id):
        db.delete_split_expense(exp_id)
        refresh_active_group_data()

    
    def build_settlement_card(settlement: dict):
        f_name = settlement["from_name"]
        t_name = settlement["to_name"]
        amt = settlement["amount"]
        t_upi = settlement.get("to_upi", "")

        def pay_upi_click(e):
            if t_upi:
                upi_url = f"upi://pay?pa={t_upi}&pn={t_name}&am={amt}&cu=INR&tn=GyFi+Settlement"
                # Use page.open_url or ft.UrlTarget
                try:
                    page.open_url(upi_url)
                except Exception:
                    # Fallback for older Flet versions that exposed launch_url via page.window
                    if hasattr(page, "launch_url"):
                        page.launch_url(upi_url)
                    else:
                        page.snack_bar = ft.SnackBar(
                            ft.Text(f"UPI deep-link ready: {t_upi}"),
                            bgcolor=ft.Colors.BLUE_700,
                        )
                        page.snack_bar.open = True
                        page.update()
            else:
                page.snack_bar = ft.SnackBar(
                    ft.Text(f"No UPI ID saved for {t_name}."),
                    bgcolor=ft.Colors.RED_700,
                )
                page.snack_bar.open = True
                page.update()

        pay_btn = []
        if t_upi:
            pay_btn.append(
                ft.IconButton(
                    icon=ft.Icons.PAYMENT,
                    icon_color=ft.Colors.GREEN_400,
                    tooltip=f"Pay ₹{amt} to {t_upi}",
                    icon_size=18,
                    on_click=pay_upi_click,
                )
            )

        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.ARROW_FORWARD,
                        size=16,
                        color=ft.Colors.AMBER_400,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                f"{f_name} owes {t_name}",
                                weight=ft.FontWeight.BOLD,
                                size=12,
                            ),
                            ft.Text(
                                f"₹{amt:,.2f}",
                                size=11,
                                color=ft.Colors.RED_300,
                                weight=ft.FontWeight.W_500,
                            ),
                        ],
                        expand=True,
                        spacing=1,
                    ),
                    *pay_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.GREY_900,
            padding=ft.Padding(10, 6, 8, 6),
            border_radius=8,
            border=ft.Border.all(1, ft.Colors.GREY_800),
            width=330,
        )

    # ----------------------------------------------------
    # Layout Assembly
    # ----------------------------------------------------
    active_group_title = ft.Text(
        "Select a Group",
        size=15,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.WHITE,
    )

    group_header_bar = ft.Row(
        [
            ft.Text(
                "Groups",
                size=14,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.GREY_300,
            ),
            ft.TextButton(
                "+ New Group",
                on_click=open_create_group_dialog,
                style=ft.ButtonStyle(color=ft.Colors.BLUE_400),
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        width=330,
    )

    member_header_bar = ft.Row(
        [
            active_group_title,
            ft.Row(
                [
                    ft.TextButton(
                        "+ Member",
                        on_click=open_add_member_dialog,
                        style=ft.ButtonStyle(color=ft.Colors.GREEN_400),
                    ),
                    ft.FilledButton(
                        "+ Add Bill",
                        on_click=open_add_expense_dialog,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700),
                    ),
                ],
                spacing=4,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        width=330,
    )

    view_container = ft.Column(
        [
            group_header_bar,
            groups_list_column,
            ft.Divider(height=16, color=ft.Colors.GREY_800),
            member_header_bar,
            ft.Container(
                content=members_chips_row,
                width=330,
                padding=ft.Padding(0, 4, 0, 4),
            ),
            ft.Divider(height=12, color=ft.Colors.TRANSPARENT),
            ft.Text(
                "⚖️ Simplified Balances",
                size=13,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.AMBER_300,
            ),
            settlements_column,
            ft.Divider(height=12, color=ft.Colors.TRANSPARENT),
            ft.Text(
                "📄 Shared Expenses History",
                size=13,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.GREY_300,
            ),
            expenses_list_column,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=8,
    )

    all_groups = db.get_split_groups()
    if all_groups:
        select_group(all_groups[0][0])
    else:
        load_groups()

    return view_container, refresh_active_group_data