"""
Residence Tlemcen — Modern PySide6 Desktop QSS Theme
Institutional slate palette with high scanability, crisp table borders,
smooth rounded controls, and semantic status indicators.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

BUTTON_STYLES = {
    "primary": """
        QPushButton {
            background-color: #0f172a;
            color: #ffffff;
            border: 1px solid #0f172a;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #1e293b;
            border-color: #1e293b;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #020617;
            border-color: #020617;
            color: #ffffff;
        }
        QPushButton:disabled {
            background-color: #e2e8f0;
            color: #94a3b8;
            border-color: #cbd5e1;
        }
    """,
    "success": """
        QPushButton {
            background-color: #059669;
            color: #ffffff;
            border: 1px solid #059669;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #047857;
            border-color: #047857;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #065f46;
            border-color: #065f46;
            color: #ffffff;
        }
        QPushButton:disabled {
            background-color: #e2e8f0;
            color: #94a3b8;
            border-color: #cbd5e1;
        }
    """,
    "in_progress": """
        QPushButton {
            background-color: #2563eb;
            color: #ffffff;
            border: 1px solid #2563eb;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #1d4ed8;
            border-color: #1d4ed8;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #1e40af;
            border-color: #1e40af;
            color: #ffffff;
        }
        QPushButton:disabled {
            background-color: #e2e8f0;
            color: #94a3b8;
            border-color: #cbd5e1;
        }
    """,
    "danger": """
        QPushButton {
            background-color: #dc2626;
            color: #ffffff;
            border: 1px solid #dc2626;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #b91c1c;
            border-color: #b91c1c;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #991b1b;
            border-color: #991b1b;
            color: #ffffff;
        }
        QPushButton:disabled {
            background-color: #e2e8f0;
            color: #94a3b8;
            border-color: #cbd5e1;
        }
    """,
    "secondary": """
        QPushButton {
            background-color: #ffffff;
            color: #1e293b;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 7px 14px;
            font-size: 13px;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #f8fafc;
            border-color: #94a3b8;
            color: #0f172a;
        }
        QPushButton:pressed {
            background-color: #f1f5f9;
            color: #0f172a;
        }
        QPushButton:disabled {
            background-color: #f8fafc;
            color: #94a3b8;
            border-color: #e2e8f0;
        }
    """,
    "filter": """
        QPushButton {
            background-color: #ffffff;
            color: #475569;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #f8fafc;
            color: #0f172a;
            border-color: #94a3b8;
        }
        QPushButton:checked {
            background-color: #0f172a;
            color: #ffffff;
            border: 1px solid #0f172a;
            font-weight: 700;
        }
        QPushButton:checked:hover {
            background-color: #1e293b;
            border-color: #1e293b;
            color: #ffffff;
        }
    """
}


def apply_button_style(btn: QPushButton, style_key: str):
    """Directly applies bulletproof, high-contrast button styling to a QPushButton."""
    style = BUTTON_STYLES.get(style_key, BUTTON_STYLES["secondary"])
    btn.setStyleSheet(style)
    btn.setCursor(Qt.PointingHandCursor)


DESKTOP_STYLESHEET = """
QMainWindow {
    background-color: #f8fafc;
    color: #0f172a;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: #0f172a;
}

/* Sidebar Navigation */
QListWidget#sidebarNav {
    background-color: #0f172a;
    border: none;
    outline: none;
    padding: 10px 8px;
}

QListWidget#sidebarNav::item {
    color: #94a3b8;
    height: 42px;
    padding-left: 12px;
    padding-right: 12px;
    margin-bottom: 4px;
    border-radius: 6px;
    font-weight: 500;
}

QListWidget#sidebarNav::item:hover {
    background-color: #1e293b;
    color: #f8fafc;
}

QListWidget#sidebarNav::item:selected {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 600;
}

/* Content Stack */
QStackedWidget {
    background-color: #f8fafc;
    border: none;
}

/* Table Widgets */
QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    gridline-color: #f1f5f9;
    selection-background-color: #eff6ff;
    selection-color: #1d4ed8;
    alternate-background-color: #fcfdfe;
    outline: none;
}

QTableWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #f1f5f9;
}

QTableWidget::item:selected {
    background-color: #eff6ff;
    color: #1d4ed8;
    font-weight: 600;
}

QHeaderView::section {
    background-color: #f8fafc;
    color: #475569;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 8px 10px;
    border: none;
    border-bottom: 2px solid #e2e8f0;
    border-right: 1px solid #f1f5f9;
}

/* Inputs & Text Edits */
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 7px 10px;
    color: #0f172a;
    font-size: 13px;
    selection-background-color: #2563eb;
}

QLineEdit:focus {
    border: 1.5px solid #2563eb;
    background-color: #ffffff;
}

QTextEdit {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 8px 10px;
    color: #0f172a;
    font-size: 13px;
    selection-background-color: #2563eb;
    line-height: 1.4;
}

QTextEdit:focus {
    border: 1.5px solid #2563eb;
}

/* Global Default Button fallback */
QPushButton {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 7px 14px;
    color: #334155;
    font-weight: 600;
    font-size: 13px;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #f8fafc;
    border-color: #94a3b8;
    color: #0f172a;
}

QPushButton:pressed {
    background-color: #f1f5f9;
}

QPushButton:disabled {
    background-color: #f8fafc;
    border-color: #e2e8f0;
    color: #94a3b8;
}

/* ComboBox */
QComboBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    color: #0f172a;
    min-height: 20px;
}

QComboBox:focus {
    border: 1.5px solid #2563eb;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #e2e8f0;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background: #f8fafc;
    width: 8px;
    margin: 0px 0px 0px 0px;
}

QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #f8fafc;
    height: 8px;
    margin: 0px 0px 0px 0px;
}

QScrollBar::handle:horizontal {
    background: #cbd5e1;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #94a3b8;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Status Bar */
QStatusBar {
    background-color: #ffffff;
    border-top: 1px solid #e2e8f0;
    color: #64748b;
    font-size: 12px;
    padding: 4px 10px;
}

/* Global Card Frame */
QFrame#cardFrame {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
}
"""
