"""
GyFi: Gym & Personal Finance Tracker
Main application entry point, routing, top branding bar, and SafeArea configuration.
"""

import flet as ft
import db
from logger import logger
from views_gym import build_gym_view
from views_fin import build_finance_view
from views_split import build_split_view


def get_nav_destination(icon, label, selected_icon=None):
    """
    Creates a navigation destination compatible across all Flet versions.
    """
    if hasattr(ft, "NavigationBarDestination"):
        return ft.NavigationBarDestination(
            icon=icon, selected_icon=selected_icon or icon, label=label
        )
    elif hasattr(ft, "NavigationDestination"):
        return ft.NavigationDestination(
            icon=icon, selected_icon=selected_icon or icon, label=label
        )
    else:
        return ft.NavigationDestination(icon=icon, label=label)


def build_app_header():
    """
    Constructs the top GyFi branding header with dual Gym & Finance icons.
    """
    return ft.Container(
        content=ft.Row(
            [
                # Custom Logo Image
                ft.Image(
                    src="gyfi.png",
                    width=38,
                    height=38,
                    fit=ft.BoxFit.CONTAIN,      # Or simply: fit="contain"
                    border_radius=8,
                    error_content=ft.Icon(
                        ft.Icons.FITNESS_CENTER,
                        color=ft.Colors.BLUE_400,
                        size=24
                    )
                ),
                # App Title & Subtitle
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    "Gy",
                                    size=22,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.BLUE_400,
                                ),
                                ft.Text(
                                    "Fi",
                                    size=22,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.GREEN_400,
                                ),
                            ],
                            spacing=0,
                        ),
                        ft.Text(
                            "Gym & Personal Finance Tracker",
                            size=10,
                            color=ft.Colors.GREY_500,
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                    spacing=0,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
        padding=ft.Padding(0, 10, 0, 8),
        alignment=ft.Alignment.CENTER,
    )


def build_footer():
    """
    Constructs a subtle, centered copyright footer.
    """
    return ft.Container(
        content=ft.Column(
            [
                ft.Divider(height=16, color=ft.Colors.GREY_800),
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.COPYRIGHT, size=12, color=ft.Colors.GREY_600
                        ),
                        ft.Text(
                            "2026 GyFi • Sourabha Sadasiv Mohanty. All rights reserved.",
                            size=10,
                            color=ft.Colors.GREY_600,
                            weight=ft.FontWeight.W_400,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=4,
                ),
                ft.Container(height=8),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        ),
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding(0, 4, 0, 8),
    )


def main(page: ft.Page):
    logger.info("Initializing GyFi application...")

    # Tell Flet where the asset files live for mobile bundling
    page.assets_dir = "assets"

    # Page Configuration
    page.title = "GyFi"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0  # Let SafeArea handle screen insets cleanly
    page.scroll = ft.ScrollMode.AUTO
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    # Initialize Database
    try:
        db.init_db()
        logger.info("Database connection and tables verified.")
    except Exception as e:
        logger.exception(f"Fatal error during database init: {e}")

    # Build Header, Views & Footer
    header = build_app_header()
    gym_view, update_gym_ui = build_gym_view(page)
    fin_view, update_fin_ui = build_finance_view(page)
    split_view, update_split_ui = build_split_view(page)
    footer = build_footer()

    # Navigation Handler
    def on_nav_change(e):
        selected_index = e.control.selected_index
        if selected_index == 0:
            logger.info("Navigating to Gym View")
            gym_view.visible = True
            fin_view.visible = False
            split_view.visible = False
            update_gym_ui()
        elif selected_index == 1:
            logger.info("Navigating to Finance View")
            gym_view.visible = False
            fin_view.visible = True
            split_view.visible = False
            update_fin_ui()
        elif selected_index == 2:
            logger.info("Navigating to Split View")
            gym_view.visible = False
            fin_view.visible = False
            split_view.visible = True
            update_split_ui()
        page.update()

    # Navigation Bar
    page.navigation_bar = ft.NavigationBar(
        destinations=[
            get_nav_destination(
                icon=ft.Icons.FITNESS_CENTER,
                selected_icon=ft.Icons.FITNESS_CENTER,
                label="Gym",
            ),
            get_nav_destination(
                icon=ft.Icons.ACCOUNT_BALANCE_WALLET,
                selected_icon=ft.Icons.ACCOUNT_BALANCE_WALLET,
                label="Finance",
            ),
            get_nav_destination(
                icon=ft.Icons.CALL_SPLIT,
                selected_icon=ft.Icons.CALL_SPLIT,
                label="Split",
            ),
        ],
        selected_index=0,
        on_change=on_nav_change,
        bgcolor=ft.Colors.GREY_900,
    )

    # Master Content Container with padding
    content_column = ft.Column(
        [
            header,
            gym_view,
            fin_view,
            split_view,
            footer,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=6,
    )

    # Wrap in SafeArea to prevent overlap with status bar / camera notch
    safe_wrapper = ft.SafeArea(
        content=ft.Container(
            content=content_column,
            padding=ft.Padding(12, 4, 12, 8),
            alignment=ft.Alignment.TOP_CENTER,
        ),
        expand=True,
    )

    page.add(safe_wrapper)

    # Initial view load
    gym_view.visible = True
    fin_view.visible = False
    split_view.visible = False
    update_gym_ui()
    page.update()
    logger.info("GyFi started successfully with notch and status bar protection.")


# Entry point supporting both ft.run and ft.app
if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)