"""
RÉSIVO — Modern High-Contrast PySide6 Dark QSS Theme
Deep obsidian canvas, electric indigo/cyan accents, glassmorphic card surfaces,
glowing badges, and high-contrast typography.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

BUTTON_STYLES = {
    "primary": """
        QPushButton {
            background-color: #4f46e5;
            color: #ffffff;
            border: 1px solid #6366f1;
            border-radius: 7px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #6366f1;
            border-color: #818cf8;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #4338ca;
            border-color: #4f46e5;
            color: #ffffff;
        }
        QPushButton:disabled {
            background-color: #1a1e2d;
            color: #475569;
            border-color: #23293d;
        }
    """,
    "success": """
        QPushButton {
            background-color: #059669;
            color: #ffffff;
            border: 1px solid #10b981;
            border-radius: 7px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #10b981;
            border-color: #34d399;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #047857;
            border-color: #059669;
            color: #ffffff;
        }
        QPushButton:disabled {
            background-color: #1a1e2d;
            color: #475569;
            border-color: #23293d;
        }
    """,
    "in_progress": """
        QPushButton {
            background-color: #0284c7;
            color: #ffffff;
            border: 1px solid #38bdf8;
            border-radius: 7px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #0369a1;
            border-color: #7dd3fc;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #075985;
            border-color: #0284c7;
            color: #ffffff;
        }
        QPushButton:disabled {
            background-color: #1a1e2d;
            color: #475569;
            border-color: #23293d;
        }
    """,
    "danger": """
        QPushButton {
            background-color: #dc2626;
            color: #ffffff;
            border: 1px solid #ef4444;
            border-radius: 7px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #ef4444;
            border-color: #f87171;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #b91c1c;
            border-color: #dc2626;
            color: #ffffff;
        }
        QPushButton:disabled {
            background-color: #1a1e2d;
            color: #475569;
            border-color: #23293d;
        }
    """,
    "secondary": """
        QPushButton {
            background-color: #141724;
            color: #cbd5e1;
            border: 1px solid #283145;
            border-radius: 7px;
            padding: 7px 14px;
            font-size: 13px;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #1c2133;
            border-color: #3e4c6c;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #0f121d;
            border-color: #283145;
            color: #94a3b8;
        }
        QPushButton:disabled {
            background-color: #10131d;
            color: #475569;
            border-color: #1c2233;
        }
    """,
    "filter": """
        QPushButton {
            background-color: #0f121a;
            color: #94a3b8;
            border: 1px solid #20273a;
            border-radius: 7px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #161a26;
            color: #f1f5f9;
            border-color: #2f3852;
        }
        QPushButton:checked {
            background-color: #1c2238;
            color: #ffffff;
            border: 1.5px solid #6366f1;
            font-weight: 700;
        }
        QPushButton:checked:hover {
            background-color: #222944;
            border-color: #818cf8;
            color: #ffffff;
        }
    """
}


def apply_button_style(btn: QPushButton, style_key: str):
    """Directly applies bulletproof, high-contrast button styling to a QPushButton."""
    style = BUTTON_STYLES.get(style_key, BUTTON_STYLES["secondary"])
    btn.setStyleSheet(style)
    btn.setCursor(Qt.PointingHandCursor)


def get_badge_qss(status_kind: str) -> str:
    """Returns glowing pill badge styling."""
    if status_kind in ("approved", "resolved", "active", "success"):
        return """
            background-color: #052e16;
            color: #34d399;
            border: 1px solid #10b981;
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 700;
        """
    elif status_kind in ("pending", "warning"):
        return """
            background-color: #2e1b04;
            color: #fbbf24;
            border: 1px solid #f59e0b;
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 700;
        """
    elif status_kind in ("in_progress", "info"):
        return """
            background-color: #082f49;
            color: #38bdf8;
            border: 1px solid #0284c7;
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 700;
        """
    elif status_kind in ("rejected", "danger", "error"):
        return """
            background-color: #360808;
            color: #f87171;
            border: 1px solid #ef4444;
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 700;
        """
    else:  # Neutral / count badge
        return """
            background-color: #141724;
            color: #94a3b8;
            border: 1px solid #283145;
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 700;
        """


DESKTOP_STYLESHEET = """
QMainWindow {
    background-color: #090a0f;
    color: #f8fafc;
    font-family: "Segoe UI";
}

QWidget {
    font-family: "Segoe UI";
    font-size: 13px;
    color: #f8fafc;
}

/* Sidebar Navigation */
QListWidget#sidebarNav {
    background-color: #07080e;
    border: none;
    border-right: 1px solid #161925;
    outline: none;
    padding: 10px 8px;
}

QListWidget#sidebarNav::item {
    color: #94a3b8;
    height: 44px;
    padding-left: 12px;
    padding-right: 12px;
    margin-bottom: 3px;
    border-radius: 7px;
    font-weight: 500;
}

QListWidget#sidebarNav::item:hover {
    background-color: #121520;
    color: #ffffff;
}

QListWidget#sidebarNav::item:selected {
    background-color: #1a2035;
    border-left: 3px solid #6366f1;
    color: #ffffff;
    font-weight: 700;
}

/* Content Stack */
QStackedWidget {
    background-color: #0c0e15;
    border: none;
}

/* Table Widgets */
QTableWidget {
    background-color: #0f121a;
    border: 1px solid #1c2234;
    border-radius: 10px;
    gridline-color: #181d2c;
    selection-background-color: #222a42;
    selection-color: #ffffff;
    alternate-background-color: #121622;
    outline: none;
}

QTableWidget::item {
    padding: 9px 12px;
    border-bottom: 1px solid #181d2c;
    color: #e2e8f0;
}

QTableWidget::item:selected {
    background-color: #222a42;
    color: #ffffff;
    font-weight: 600;
}

QHeaderView::section {
    background-color: #0a0c13;
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 9px 12px;
    border: none;
    border-bottom: 2px solid #1c2234;
    border-right: 1px solid #181d2c;
}

/* Inputs & Text Edits */
QLineEdit {
    background-color: #090b10;
    border: 1px solid #1f2638;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
    font-size: 13px;
    selection-background-color: #6366f1;
}

QLineEdit:focus {
    border: 1.5px solid #6366f1;
    background-color: #0c0e16;
}

QTextEdit {
    background-color: #090b10;
    border: 1px solid #1f2638;
    border-radius: 8px;
    padding: 10px 12px;
    color: #e2e8f0;
    font-size: 13px;
    selection-background-color: #6366f1;
    line-height: 1.4;
}

QTextEdit:focus {
    border: 1.5px solid #6366f1;
    background-color: #0c0e16;
}

/* Global Default Button fallback */
QPushButton {
    background-color: #141724;
    border: 1px solid #283145;
    border-radius: 7px;
    padding: 7px 14px;
    color: #cbd5e1;
    font-weight: 600;
    font-size: 13px;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #1c2133;
    border-color: #3e4c6c;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #0f121d;
    border-color: #283145;
}

QPushButton:disabled {
    background-color: #10131d;
    border-color: #1c2233;
    color: #475569;
}

/* ComboBox */
QComboBox {
    background-color: #090b10;
    border: 1px solid #1f2638;
    border-radius: 8px;
    padding: 6px 12px;
    color: #f8fafc;
    min-height: 22px;
}

QComboBox:focus {
    border: 1.5px solid #6366f1;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #1c2234;
}

QComboBox QAbstractItemView {
    background-color: #121520;
    color: #f8fafc;
    selection-background-color: #222a42;
    border: 1px solid #1f2638;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background: #090a0f;
    width: 6px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #252c40;
    min-height: 24px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #3b4666;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #090a0f;
    height: 6px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #252c40;
    min-width: 24px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal:hover {
    background: #3b4666;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Status Bar */
QStatusBar {
    background-color: #07080d;
    border-top: 1px solid #161926;
    color: #64748b;
    font-size: 12px;
    padding: 5px 12px;
}

/* Global Card Frame */
QFrame#cardFrame {
    background-color: #121520;
    border: 1px solid #1c2234;
    border-radius: 10px;
}

/* Splitter divider */
QSplitter::handle {
    background-color: #161925;
    width: 2px;
}
"""
