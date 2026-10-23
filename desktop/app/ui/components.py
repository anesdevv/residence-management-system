"""RÉSIVO — desktop component library (visual layer only, no client/RPC calls).

Every colour and size comes from :mod:`desktop.app.ui.theme` tokens. Components
prefer dynamic properties (``variant``, ``role``, ``kind``, ``state``) picked up
by ``DESKTOP_STYLESHEET``; when a component must style itself, the QSS string is
interpolated from tokens — no raw hex appears in this file.

Public API — other agents code against these signatures
-------------------------------------------------------
``Button(text, variant="secondary", icon=None, size="md", parent=None)``
    ``Button.primary(text, icon=None)`` / ``.accent`` / ``.secondary`` / ``.danger`` / ``.ghost``
    ``button.set_variant(variant, icon=None)``
``IconButton(icon_name, tooltip, variant="ghost", size=32, color=None, parent=None)``
``StatusPill(kind, label=None, icon=None, parent=None)``
    ``set_kind(kind, label=None)`` — icon + text label always rendered
``RosterMatchBadge(matched: bool | None, parent=None)`` — ``set_matched(matched)``
``Card(title=None, subtitle=None, icon=None, parent=None)``
    attributes: ``body: QVBoxLayout``, ``footer: QHBoxLayout | None`` (on demand)
    ``add_widget(w)`` / ``add_layout(l)`` / ``add_footer_widget(w)`` / ``set_title(text)``
``StatCard(label, icon_name, accent="teal", parent=None)`` — ``set_value(text)`` / ``set_hint(text)``
``PageHeader(title, subtitle=None, parent=None)`` — ``actions: QHBoxLayout`` / ``set_subtitle(text)``
``SegmentedControl(options: list[tuple[str, str]], parent=None)``
    ``changed = Signal(str)``, ``buttons: dict[str, QPushButton]``
    ``set_current(key)`` / ``current() -> str | None`` / ``set_count(key, count)``
``SearchField(placeholder="Search…", parent=None)``
    ``changed = Signal(str)`` (debounced 180 ms), ``edit: QLineEdit``
    ``text()`` / ``set_text(v)`` (silent) / ``clear()`` (emits ``""``)
``DetailPanel(min_width, max_width, title="Details", parent=None)``
    ``body: QVBoxLayout`` lives ON the frame (children keep the frame as parent)
    ``add_widget(w)`` / ``add_layout(l)`` / ``add_section(overline_text) -> QVBoxLayout``
    ``set_title(text)`` / ``set_empty(message)``
``KeyValueList(parent=None)`` — ``add_row(label, value, mono=False)`` / ``clear()`` / ``set_rows(rows)``
``InlineBanner(kind="info", title=None, message="", icon=None, parent=None)``
    ``set_message(msg)`` / ``set_kind(kind)`` / ``add_action(button)``
``EmptyState(icon_name, title, message, parent=None)`` — ``actions: QHBoxLayout``
``Avatar(name, size=32, parent=None)``
``Stepper(steps: list[str], parent=None)`` — ``set_current(index)`` / ``set_states(list[bool])``
``RoomOccupancyBar(occupied=0, capacity=4, parent=None)``
    ``set_values(occupied, capacity)`` / ``is_full() -> bool``
``Skeleton(rows=3, parent=None)``
``Toast(message, kind="info", icon="bell", parent=None)``
``show_toast(parent, message, kind="info", icon="bell", duration_ms=4000) -> Toast``
``ConfirmDialog(parent, title, message, confirm_text="Delete", danger=True, cancel_text="Cancel")``
    ``confirmed: bool``; ``ConfirmDialog.ask(parent, title, message, confirm_text="Delete", danger=True) -> bool``
``BrandMark(variant="mark"|"logo", color="brand"|"white", size=32, parent=None)``
``GradientHero(parent=None)`` — ``body: QVBoxLayout`` (brand gradient painted in ``paintEvent``)
``LiveDot(parent=None)`` — ``set_state("connected"|"reconnecting"|"offline")``
``style_table(table)`` / ``configure_table(table, headers)`` / ``set_row_height(table, h=44)``
``enable_tabular_numerics(table)`` / ``apply_shadow(widget, level)``

``kind`` values accepted everywhere: ``ok/pending/review/progress/danger/neutral``
plus every legacy alias (``approved, resolved, active, success, matched, warning,
under_review, in_progress, info, rejected, error, urgent, not_in_roster, neutral_info``).
"""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    Signal,
    Property,
)
from PySide6.QtGui import (
    QBrush,
    QFontDatabase,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .icons import get_icon, get_pixmap
from .stepper import NumberStepper
from .theme import C, S, apply_button_style, apply_elevation, qcolor

# status kind -> (default label, icon) for pills and banners
_STATUS_ICONS = {
    "ok": "check-circle",
    "pending": "clock",
    "review": "eye",
    "progress": "refresh",
    "danger": "alert-triangle",
    "neutral": "info",
}
_STATUS_LABELS = {
    "ok": "Active",
    "pending": "Pending",
    "review": "Under review",
    "progress": "In progress",
    "danger": "Attention",
    "neutral": "Info",
}
# accent name -> (ink token, soft tint token) — token colours only
_ACCENTS = {
    "teal": ("teal-600", "selection-tint"),
    "navy": ("navy-800", "surface-subtle"),
    "green": ("status-ok-ink", "status-ok-bg"),
    "gold": ("status-pending-ink", "status-pending-bg"),
    "amber": ("status-pending-ink", "status-pending-bg"),
    "danger": ("status-danger-ink", "status-danger-bg"),
    "review": ("status-review-ink", "status-review-bg"),
}
_BANNER_KINDS = {
    "info": "progress",
    "success": "ok",
    "warning": "pending",
    "error": "danger",
}
_FILLED_VARIANTS = {"primary", "accent", "success", "in_progress", "danger"}
_AVATAR_PALETTE = (
    ("selection-tint", "navy-800"),
    ("status-ok-bg", "status-ok-ink"),
    ("status-pending-bg", "status-pending-ink"),
    ("status-review-bg", "status-review-ink"),
    ("status-progress-bg", "status-progress-ink"),
    ("status-danger-bg", "status-danger-ink"),
)
def _resolve_brand_dir() -> Path:
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "assets" / "brand")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "assets" / "brand")
            candidates.append(Path(meipass) / "desktop" / "assets" / "brand")
    candidates.append(Path(__file__).resolve().parents[2] / "assets" / "brand")
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[-1]


_BRAND_DIR = _resolve_brand_dir()


def _muted(word: str) -> QLabel:
    """Small secondary-colour label."""
    label = QLabel(word)
    theme.apply_role(label, "small")
    return label


def _kind_tokens(kind: str) -> dict[str, str]:
    """Normalised status tokens for any (legacy) kind."""
    return theme.status_tokens(kind)


def _pill_qss(kind: str, radius: str) -> str:
    """Pill frame QSS: status background, hairline border and capsule radius.

    ``radius`` is a concrete px value because Qt renders a square when the
    radius is not smaller than half the pill (``theme.pill_radius``); the text
    colour/typography lives on the inner text label instead (see ``_PillLabel``).
    """
    tokens = _kind_tokens(kind)
    return (
        f"background-color: {tokens['bg']};"
        f" border: 1px solid {tokens['border']};"
        f" border-radius: {radius};"
    )


class Button(QPushButton):
    """Standard action button.

    ``Button(text, variant="secondary", icon=None, size="md", parent=None)``.
    Variants: primary (navy-800), accent (teal-600), secondary (outline),
    danger, ghost; legacy success/in_progress/filter are accepted unchanged.
    Sizes: "md" (default) and "sm".
    """

    def __init__(self, text, variant="secondary", icon=None, size="md", parent=None):
        super().__init__(text, parent)
        self._variant = "secondary"
        self._icon_name = None
        self.setProperty("size", size if size in ("md", "sm") else "md")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_variant(variant, icon)

    def set_variant(self, variant, icon=None):
        """Switch variant (and optionally the icon) without recreating the widget."""
        self._variant = variant if variant in theme.BUTTON_STYLES else "secondary"
        apply_button_style(self, self._variant)
        if icon is not None:
            self._icon_name = icon
        if self._icon_name:
            ink = "surface" if self._variant in _FILLED_VARIANTS else "text-secondary"
            self.setIcon(get_icon(self._icon_name, 16, C(ink)))
            self.setIconSize(QSize(16, 16))
        return self

    def set_icon_name(self, icon_name):
        """Set/replace the leading icon, recoloured for the current variant."""
        return self.set_variant(self._variant, icon_name)

    @classmethod
    def primary(cls, text, icon=None):
        return cls(text, "primary", icon)

    @classmethod
    def accent(cls, text, icon=None):
        return cls(text, "accent", icon)

    @classmethod
    def secondary(cls, text, icon=None):
        return cls(text, "secondary", icon)

    @classmethod
    def danger(cls, text, icon=None):
        return cls(text, "danger", icon)

    @classmethod
    def ghost(cls, text, icon=None):
        return cls(text, "ghost", icon)


class IconButton(QPushButton):
    """Square icon-only button: ``IconButton(icon_name, tooltip, variant="ghost", size=32, color=None, parent=None)``.

    The tooltip doubles as the accessible name (icon-only controls must be
    labelled) and is shown on every state, disabled included.
    """

    _FILLS = {
        "ghost": None,
        "secondary": None,
        "primary": "navy-800",
        "accent": "teal-600",
        "danger": "status-danger-ink",
    }

    def __init__(self, icon_name, tooltip, variant="ghost", size=32, color=None, parent=None):
        super().__init__(parent)
        icon_px = max(12, int(size * 0.55))
        if color is None:
            color = C("surface") if variant in ("primary", "accent", "danger") else C("text-secondary")
        self.setIcon(get_icon(icon_name, icon_px, color))
        self.setIconSize(QSize(icon_px, icon_px))
        self.setFixedSize(size, size)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("variant", variant)
        self.setStyleSheet(self._icon_qss(variant))

    @staticmethod
    def _icon_qss(variant: str) -> str:
        fill = IconButton._FILLS.get(variant)
        background = C(fill) if fill else "transparent"
        hover = C("navy-700") if fill == "navy-800" else (
            C("teal-500") if fill == "teal-600" else (
                C("danger-600") if fill == "status-danger-ink" else C("surface-subtle")
            )
        )
        pressed = C("navy-900") if fill == "navy-800" else (
            C("teal-700") if fill == "teal-600" else (
                C("danger-700") if fill == "status-danger-ink" else C("surface-subtle")
            )
        )
        ink = C("surface") if fill else C("text-secondary")
        return (
            f"QPushButton {{ background-color: {background}; color: {ink};"
            f" border: 1px solid transparent; border-radius: {C('radius-input')}; padding: 0px; }}"
            f"QPushButton:hover {{ background-color: {hover}; }}"
            f"QPushButton:pressed {{ background-color: {pressed}; }}"
            f"QPushButton:focus {{ border: 2px solid {C('teal-600')}; }}"
            f"QPushButton:disabled {{ background-color: {C('surface-subtle')}; border: 1px solid {C('border')}; }}"
        )


class _PillLabel(QLabel):
    """Private pill base: a ``QLabel`` hosting an inner icon label + text label.

    ``QLabel`` paints either a pixmap *or* text, never both, so the pill carries
    two child labels inside a ``QHBoxLayout`` (padding from ``pill-pad-x`` /
    ``pill-pad-y``). ``text()`` / ``setText()`` are forwarded to the inner text
    label, so the subclass still reads like the label it is.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._kind = "neutral"
        self._pill_height = -1
        self._text_label = QLabel(self)
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._text_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._icon_label = QLabel(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            S("pill-pad-x"), S("pill-pad-y"), S("pill-pad-x"), S("pill-pad-y")
        )
        layout.setSpacing(6)
        layout.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._text_label, 0, Qt.AlignmentFlag.AlignVCenter)

    # -- label-ish behaviour ------------------------------------------------
    def text(self):
        """Text of the pill (forwards to the inner label)."""
        return self._text_label.text()

    def setText(self, value):
        """Set the pill text (forwards to the inner label)."""
        self._text_label.setText(str(value))

    def clear(self):
        """Clear the pill text (forwards to the inner label)."""
        self._text_label.clear()
        return self

    def sizeHint(self):
        layout = self.layout()
        return layout.totalSizeHint() if layout is not None else super().sizeHint()

    def minimumSizeHint(self):
        layout = self.layout()
        return layout.totalMinimumSize() if layout is not None else super().minimumSizeHint()

    # -- shared rendering ---------------------------------------------------
    def _pill_radius(self) -> str:
        """Capsule radius for the pill's real height (Qt drops a bigger one).

        Before the first layout pass the widget still reports Qt's default size,
        so the size hint stands in until ``resizeEvent`` reports the real one.
        """
        height = self.height() if self._pill_height >= 0 else self.sizeHint().height()
        return theme.pill_radius(height)

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self.height() != self._pill_height:
            self._pill_height = self.height()
            self.setStyleSheet(_pill_qss(self._kind, self._pill_radius()))

    def _apply_pill(self, kind: str) -> dict[str, str]:
        """Paint the pill frame for ``kind`` and return its status tokens."""
        tokens = _kind_tokens(kind)
        self._kind = kind
        self.setStyleSheet(_pill_qss(kind, self._pill_radius()))
        self._text_label.setStyleSheet(
            f"color: {tokens['ink']};"
            f" font-size: {C('fs-small')}; font-weight: {C('fw-semibold')};"
            f" background: transparent; border: 0px;"
        )
        self.setProperty("kind", theme.status_kind(kind))
        return tokens

    def _set_icon(self, icon_name: str, color: str) -> None:
        """Colour the 12 px leading icon and lock the icon label to its size."""
        pixmap = get_pixmap(icon_name, 12, color)
        self._icon_label.setPixmap(pixmap)
        ratio = pixmap.devicePixelRatio() or 1.0
        self._icon_label.setFixedSize(
            QSize(
                max(1, round(pixmap.width() / ratio)),
                max(1, round(pixmap.height() / ratio)),
            )
        )


class StatusPill(_PillLabel):
    """Status badge: colour **and** icon **and** text label, never colour alone.

    ``StatusPill(kind, label=None, icon=None, parent=None)``; ``set_kind(kind, label=None)``
    accepts every legacy kind (see module docstring). The icon and label are child
    widgets of the pill; ``text()`` returns ``label`` (or the default status word).
    """

    def __init__(self, kind, label=None, icon=None, parent=None):
        super().__init__(parent)
        self._label_text = None
        self._icon_name = icon
        self.set_kind(kind, label)

    def set_kind(self, kind, label=None):
        """Repaint for ``kind`` (any legacy alias); ``label`` overrides the default word."""
        status = theme.status_kind(kind)
        if label is not None:
            self._label_text = str(label)
        if self._label_text is None:
            self._label_text = _STATUS_LABELS[status]
        icon_name = self._icon_name or _STATUS_ICONS[status]
        tokens = self._apply_pill(status)
        self.setText(self._label_text)
        self._set_icon(icon_name, tokens["ink"])
        return self


class RosterMatchBadge(_PillLabel):
    """Roster match state: ``RosterMatchBadge(matched: bool | None, parent=None)``.

    ``True`` -> "Matched" (ok), ``False`` -> "Not in roster" (danger),
    ``None`` -> "Not checked" (neutral). ``set_matched(matched)`` updates it.
    """

    def __init__(self, matched, parent=None):
        super().__init__(parent)
        self.set_matched(matched)

    def set_matched(self, matched):
        """Repaint for ``True`` / ``False`` / ``None``."""
        if matched is True:
            status, text, icon = "ok", "Matched", "check-circle"
        elif matched is False:
            status, text, icon = "danger", "Not in roster", "x-circle"
        else:
            status, text, icon = "neutral", "Not checked", "info"
        tokens = self._apply_pill(status)
        self.setText(text)
        self._set_icon(icon, tokens["ink"])
        return self


class Card(QFrame):
    """Surface card: title row, ``body``, optional footer.

    ``Card(title=None, subtitle=None, icon=None, parent=None)``. The frame is
    named ``cardFrame`` so the global QSS paints surface + hairline border.
    ``footer`` is ``None`` until the first ``add_footer_widget(w)`` call.
    """

    def __init__(self, title=None, subtitle=None, icon=None, parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.setProperty("cardFrame", True)
        self.footer = None
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(S("space-4"), S("space-4"), S("space-4"), S("space-4"))
        self._root.setSpacing(S("space-3"))
        self._header = QHBoxLayout()
        self._header.setSpacing(S("space-3"))
        self._icon_label = QLabel() if icon else None
        if self._icon_label is not None:
            self._icon_label.setPixmap(get_pixmap(icon, 20, C("teal-600")))
            self._header.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignTop)
        self._title_column = QVBoxLayout()
        self._title_column.setSpacing(2)
        self._title_label = QLabel()
        theme.apply_role(self._title_label, "h3")
        self._subtitle_label = QLabel()
        theme.apply_role(self._subtitle_label, "small")
        self._title_column.addWidget(self._title_label)
        self._title_column.addWidget(self._subtitle_label)
        self._header.addLayout(self._title_column, 1)
        self._root.addLayout(self._header)
        self.body = QVBoxLayout()
        self.body.setSpacing(S("space-3"))
        self._root.addLayout(self.body)
        self._root.addStretch(0)
        self.set_title(title)
        if subtitle:
            self._subtitle_label.setText(subtitle)
        self._refresh_header()

    def _refresh_header(self):
        has_title = bool(self._title_label.text())
        has_subtitle = bool(self._subtitle_label.text())
        self._title_label.setVisible(has_title)
        self._subtitle_label.setVisible(has_subtitle)
        if self._icon_label is not None:
            self._icon_label.setVisible(has_title or has_subtitle)

    def set_title(self, text):
        """Update the card title (empty text hides the title row)."""
        self._title_label.setText(text or "")
        self._title_label.setVisible(bool(text))
        self._refresh_header()
        return self

    def add_widget(self, widget):
        """Append a widget to the card body."""
        self.body.addWidget(widget)
        return widget

    def add_layout(self, layout):
        """Append a layout to the card body."""
        self.body.addLayout(layout)
        return layout

    def add_footer_widget(self, widget):
        """Append a widget to the footer, creating the footer row on demand."""
        if self.footer is None:
            footer_frame = QFrame()
            footer_frame.setObjectName("cardFooter")
            separator = QFrame()
            separator.setFixedHeight(1)
            separator.setProperty("role", "separator")
            separator.setStyleSheet(
                f"background-color: {C('border')}; border: none;"
            )
            self._root.addWidget(separator)
            self.footer = QHBoxLayout(footer_frame)
            self.footer.setContentsMargins(0, 0, 0, 0)
            self.footer.setSpacing(S("space-2"))
            self.footer.addStretch(1)
            self._root.addWidget(footer_frame)
        self.footer.addWidget(widget)
        return self.footer


class StatCard(QFrame):
    """KPI card: Outfit 32/700 tabular number, label, hint, icon in a tinted square.

    ``StatCard(label, icon_name, accent="teal", parent=None)``;
    ``set_value(text)`` / ``set_hint(text)``. Accents: teal, navy, green, gold,
    amber, danger, review (token-only tint pairs).
    """

    def __init__(self, label, icon_name, accent="teal", parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.setProperty("cardFrame", True)
        self.setProperty("stat", True)
        ink_token, tint_token = _ACCENTS.get(accent, _ACCENTS["teal"])
        root = QHBoxLayout(self)
        root.setContentsMargins(S("space-4"), S("space-4"), S("space-4"), S("space-4"))
        root.setSpacing(S("space-3"))
        icon_box = QLabel()
        icon_box.setFixedSize(40, 40)
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setPixmap(get_pixmap(icon_name, 20, C(ink_token)))
        icon_box.setStyleSheet(
            f"background-color: {C(tint_token)}; border-radius: {C('radius-input')};"
        )
        root.addWidget(icon_box, 0, Qt.AlignmentFlag.AlignTop)
        column = QVBoxLayout()
        column.setSpacing(2)
        self._label = _muted(label)
        self._value = QLabel("—")
        theme.apply_role(self._value, "display")
        theme.enable_tabular(self._value)
        self._hint = QLabel()
        theme.apply_role(self._hint, "small")
        self._hint.setVisible(False)
        column.addWidget(self._label)
        column.addWidget(self._value)
        column.addWidget(self._hint)
        column.addStretch(1)
        root.addLayout(column, 1)
        self._accent = accent

    def set_value(self, text):
        """Set the KPI number (Outfit 32/700, tabular figures)."""
        self._value.setText(str(text))
        return self

    def set_hint(self, text):
        """Set the small delta/hint line under the number (empty hides it)."""
        self._hint.setText(text or "")
        self._hint.setVisible(bool(text))
        return self


class PageHeader(QWidget):
    """Page title + subtitle + right-aligned action slot.

    ``PageHeader(title, subtitle=None, parent=None)``; add buttons to
    ``header.actions`` (a ``QHBoxLayout``) and call ``set_subtitle(text)``.
    """

    def __init__(self, title, subtitle=None, parent=None):
        super().__init__(parent)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(S("space-4"))
        column = QVBoxLayout()
        column.setSpacing(2)
        self._title = QLabel(title)
        theme.apply_role(self._title, "h1")
        self._subtitle = QLabel(subtitle or "")
        theme.apply_role(self._subtitle, "muted")
        self._subtitle.setVisible(bool(subtitle))
        column.addWidget(self._title)
        column.addWidget(self._subtitle)
        root.addLayout(column, 1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(S("space-2"))
        root.addLayout(self.actions, 0)
        root.addStretch(0)

    def set_subtitle(self, text):
        """Update the subtitle line (empty hides it)."""
        self._subtitle.setText(text or "")
        self._subtitle.setVisible(bool(text))
        return self

    def set_title(self, text):
        """Update the page title."""
        self._title.setText(text or "")
        return self


class SegmentedControl(QWidget):
    """Exclusive segmented filter control.

    ``SegmentedControl(options: list[tuple[str, str]], parent=None)`` where each
    option is ``(key, label)``. Emits ``changed(key)`` when the selection moves.
    ``buttons`` maps key -> checkable ``QPushButton``; ``set_count(key, count)``
    appends a count badge to a segment label.
    """

    changed = Signal(str)

    def __init__(self, options, parent=None):
        super().__init__(parent)
        self.buttons: dict[str, QPushButton] = {}
        self._labels: dict[str, str] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(S("space-1"))
        for key, label in options:
            button = QPushButton(str(label))
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            apply_button_style(button, "filter")
            self._group.addButton(button)
            self.buttons[key] = button
            self._labels[key] = str(label)
            button.clicked.connect(lambda checked=False, k=key: self.changed.emit(k))
            row.addWidget(button)
        row.addStretch(1)
        if options:
            self.buttons[options[0][0]].setChecked(True)

    def set_current(self, key):
        """Check the segment for ``key`` without emitting ``changed``."""
        button = self.buttons.get(key)
        if button is not None:
            button.setChecked(True)
        return self

    def current(self):
        """Key of the checked segment, or ``None``."""
        for key, button in self.buttons.items():
            if button.isChecked():
                return key
        return None

    def set_count(self, key, count):
        """Show a count next to a segment label (``0`` shows just the label)."""
        button = self.buttons.get(key)
        if button is None:
            return self
        label = self._labels[key]
        button.setText(label if not count else f"{label}  ·  {count}")
        return self


class SearchField(QWidget):
    """Debounced search input with a leading icon and a clear affordance.

    ``SearchField(placeholder="Search…", parent=None)``. ``changed(str)`` is
    emitted 180 ms after typing stops, or immediately on Enter and on clear.
    ``self.edit`` is the underlying ``QLineEdit``; ``set_text`` is silent.
    """

    changed = Signal(str)

    def __init__(self, placeholder="Search…", parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(180)
        self._timer.timeout.connect(self._emit)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setClearButtonEnabled(False)
        self.edit.setMinimumHeight(S("size-control"))
        search_action = self.edit.addAction(
            get_icon("search", 16, C("text-muted")), QLineEdit.ActionPosition.LeadingPosition
        )
        search_action.setEnabled(False)
        self._clear_action = self.edit.addAction(
            get_icon("x-circle", 16, C("text-muted")), QLineEdit.ActionPosition.TrailingPosition
        )
        self._clear_action.setToolTip("Clear search")
        self._clear_action.setVisible(False)
        self._clear_action.triggered.connect(self._on_clear)
        self.edit.textChanged.connect(self._on_text_changed)
        self.edit.returnPressed.connect(self._on_return)
        row.addWidget(self.edit)

    def _on_text_changed(self, text):
        self._clear_action.setVisible(bool(text))
        self._timer.start()

    def _on_return(self):
        self._timer.stop()
        self._emit()

    def _on_clear(self):
        self.edit.clear()
        self._timer.stop()
        self.changed.emit("")

    def _emit(self):
        self.changed.emit(self.edit.text())

    def text(self):
        """Current search text."""
        return self.edit.text()

    def set_text(self, value):
        """Set the text without emitting ``changed`` (state restore)."""
        self.edit.setText(value or "")
        self._clear_action.setVisible(bool(self.edit.text()))
        return self

    def clear(self):
        """Clear the field and emit ``changed("")`` immediately."""
        self.edit.clear()
        self._timer.stop()
        self.changed.emit("")
        return self


class DetailPanel(QFrame):
    """Master-detail inspector frame.

    ``DetailPanel(min_width, max_width, title="Details", parent=None)`` — the
    **frame itself** owns the exact min/max widths and hosts ``body``, so any
    widget added to ``body`` keeps this frame as ``parentWidget()``.
    ``add_section(overline_text)`` adds an overline label and returns a fresh
    ``QVBoxLayout`` to fill. ``set_empty(message)`` hides the body and shows the
    message; the next ``add_widget``/``add_layout`` reveals the body again.
    """

    def __init__(self, min_width, max_width, title="Details", parent=None):
        super().__init__(parent)
        self.setObjectName("detailPanel")
        self.setProperty("cardFrame", True)
        self.setMinimumWidth(min_width)
        self.setMaximumWidth(max_width)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(S("space-4"), S("space-4"), S("space-4"), S("space-4"))
        self._root.setSpacing(S("space-3"))
        self._title = QLabel(title)
        theme.apply_role(self._title, "h3")
        self._root.addWidget(self._title)
        self._separator = QFrame()
        self._separator.setFixedHeight(1)
        self._separator.setStyleSheet(f"background-color: {C('border')}; border: none;")
        self._root.addWidget(self._separator)
        self.body = QVBoxLayout()
        self.body.setSpacing(S("space-3"))
        self._root.addLayout(self.body)
        self._empty = QLabel("")
        theme.apply_role(self._empty, "muted")
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._empty.setVisible(False)
        self._root.addWidget(self._empty)
        self._root.addStretch(0)

    def _hide_body_widgets(self, layout=None):
        layout = self.body if layout is None else layout
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget()
            if widget is not None:
                widget.setVisible(False)
            child = item.layout()
            if child is not None:
                self._hide_body_widgets(child)

    def set_title(self, text):
        """Update the panel title."""
        self._title.setText(text or "")
        self._title.setVisible(bool(text))
        return self

    def add_widget(self, widget):
        """Append a widget to the panel body (reveals the body if empty)."""
        if self._empty.isVisible():
            self._empty.setVisible(False)
            self._reveal_body_widgets()
        self.body.addWidget(widget)
        return widget

    def _reveal_body_widgets(self, layout=None):
        layout = self.body if layout is None else layout
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget()
            if widget is not None:
                widget.setVisible(True)
            child = item.layout()
            if child is not None:
                self._reveal_body_widgets(child)

    def add_layout(self, layout):
        """Append a layout to the panel body."""
        if self._empty.isVisible():
            self._empty.setVisible(False)
            self._reveal_body_widgets()
        self.body.addLayout(layout)
        return layout

    def add_section(self, overline_text):
        """Add an overline section header; returns a fresh layout to fill."""
        overline = QLabel(str(overline_text).upper())
        theme.apply_role(overline, "overline")
        self.body.addWidget(overline)
        section = QVBoxLayout()
        section.setSpacing(S("space-2"))
        self.body.addLayout(section)
        return section

    def set_empty(self, message):
        """Show only an explanatory empty message."""
        self._hide_body_widgets()
        self._empty.setText(message)
        self._empty.setVisible(True)
        return self


class KeyValueList(QWidget):
    """Label/value list; values use tabular figures (``mono=True`` = fixed font).

    ``add_row(label, value, mono=False)`` / ``clear()`` / ``set_rows(list[tuple[str, str]])``.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[QWidget] = []
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(S("space-2"))

    def add_row(self, label, value, mono=False):
        """Append one row (returns the row widget)."""
        row = QWidget(self)
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(S("space-3"))
        name = _muted(str(label))
        name.setMinimumWidth(120)
        name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        val = QLabel(str(value))
        theme.apply_role(val, "body")
        val.setWordWrap(True)
        if mono:
            val.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        else:
            theme.enable_tabular(val)
        line.addWidget(name, 0)
        line.addWidget(val, 1)
        self._column.addWidget(row)
        self._rows.append(row)
        return row

    def clear(self):
        """Remove every row."""
        for row in self._rows:
            self._column.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        return self

    def set_rows(self, rows):
        """Replace all rows with ``[(label, value), ...]``."""
        self.clear()
        for label, value in rows:
            self.add_row(label, value)
        return self


class InlineBanner(QFrame):
    """Inline info/success/warning/error banner (used to explain disabled actions).

    ``InlineBanner(kind="info", title=None, message="", icon=None, parent=None)``.
    ``set_message(msg)`` / ``set_kind(kind)`` / ``add_action(button)``.
    """

    def __init__(self, kind="info", title=None, message="", icon=None, parent=None):
        super().__init__(parent)
        self.setObjectName("inlineBanner")
        self._icon_name = icon
        root = QHBoxLayout(self)
        root.setContentsMargins(S("space-3"), S("space-3"), S("space-3"), S("space-3"))
        root.setSpacing(S("space-3"))
        self._icon = QLabel()
        self._icon.setFixedWidth(20)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self._icon, 0)
        column = QVBoxLayout()
        column.setSpacing(2)
        self._title = QLabel(title or "")
        theme.apply_role(self._title, "h3")
        self._title.setVisible(bool(title))
        self._message = QLabel(message or "")
        theme.apply_role(self._message, "body")
        self._message.setWordWrap(True)
        self._message.setVisible(bool(message))
        column.addWidget(self._title)
        column.addWidget(self._message)
        root.addLayout(column, 1)
        self._actions = QHBoxLayout()
        self._actions.setSpacing(S("space-2"))
        root.addLayout(self._actions, 0)
        self._kind = "info"
        self.set_kind(kind)

    def set_kind(self, kind):
        """Switch banner kind (info/success/warning/error, legacy aliases accepted)."""
        self._kind = kind if kind in _BANNER_KINDS else "info"
        status = _BANNER_KINDS[self._kind]
        tokens = _kind_tokens(status)
        self.setProperty("kind", self._kind)
        self.setProperty("status", status)
        self.setStyleSheet(
            f"QFrame#inlineBanner {{ background-color: {tokens['bg']};"
            f" border: 1px solid {tokens['border']}; border-radius: {C('radius-card')}; }}"
        )
        icon_name = self._icon_name or _STATUS_ICONS[status]
        self._icon.setPixmap(get_pixmap(icon_name, 16, tokens["ink"]))
        return self

    def set_message(self, msg):
        """Update the banner message (empty hides the line)."""
        self._message.setText(msg or "")
        self._message.setVisible(bool(msg))
        return self

    def set_title(self, text):
        """Set the bold first line (empty hides it)."""
        self._title.setText(text or "")
        self._title.setVisible(bool(text))
        return self

    def add_action(self, button):
        """Add an action button on the right of the banner."""
        self._actions.addWidget(button)
        return button


class EmptyState(QWidget):
    """Authored empty state: icon + title + one helpful sentence + actions.

    ``EmptyState(icon_name, title, message, parent=None)``; ``actions`` is a
    ``QHBoxLayout`` for an optional primary button.
    """

    def __init__(self, icon_name, title, message, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(S("space-8"), S("space-8"), S("space-8"), S("space-8"))
        root.setSpacing(S("space-2"))
        root.addStretch(1)
        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(get_pixmap(icon_name, 28, C("text-muted")))
        root.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        title_label = QLabel(title)
        theme.apply_role(title_label, "h2")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title_label)
        message_label = _muted(message)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(message_label)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(S("space-2"))
        root.addLayout(self.actions)
        root.addStretch(1)


class Avatar(QLabel):
    """Initials avatar: ``Avatar(name, size=32, parent=None)``.

    Circle, background tint derived deterministically from the name using token
    colour pairs only (no random colours, no images).
    """

    def __init__(self, name, size=32, parent=None):
        super().__init__(parent)
        self._size = int(size)
        self.setFixedSize(self._size, self._size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_name(name)

    @staticmethod
    def _initials(name: str) -> str:
        parts = [part for part in str(name or "").split() if part]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def set_name(self, name):
        """Recompute initials and tint from a full name."""
        initials = self._initials(name)
        bg_token, ink_token = _AVATAR_PALETTE[sum(ord(ch) for ch in str(name)) % len(_AVATAR_PALETTE)]
        self.setText(initials)
        self.setToolTip(str(name))
        self.setStyleSheet(
            f"background-color: {C(bg_token)}; color: {C(ink_token)};"
            f" border-radius: {self._size // 2}px;"
            f" font-size: {C('fs-small')}; font-weight: {C('fw-semibold')};"
        )
        return self


class Stepper(QWidget):
    """Four-stage lifecycle stepper (numbered dots + connector line + labels).

    ``Stepper(steps: list[str], parent=None)``; ``set_current(index)`` marks the
    active stage (teal-600), ``set_states(list[bool])`` marks completed stages
    (status-ok, drawn as a check). Everything else is border/muted.
    """

    _RADIUS = 12
    _TOP = 14

    def __init__(self, steps, parent=None):
        super().__init__(parent)
        self._steps = [str(step) for step in steps]
        self._current = 0
        self._done = [False] * len(self._steps)
        self.setFixedHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_current(self, index):
        """Mark ``index`` as the current stage (clamped to range)."""
        if not self._steps:
            return self
        self._current = max(0, min(int(index), len(self._steps) - 1))
        self.update()
        return self

    def set_states(self, states):
        """Mark completed stages (list of booleans, clamped to the step count)."""
        values = [bool(value) for value in states][: len(self._steps)]
        self._done = values + [False] * (len(self._steps) - len(values))
        self.update()
        return self

    def _dot_centers(self):
        count = max(1, len(self._steps))
        segment = self.width() / count
        return [int(segment * (index + 0.5)) for index in range(count)]

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        centers = self._dot_centers()
        top = self._TOP
        radius = self._RADIUS
        for index in range(len(centers) - 1):
            color = qcolor("status-ok-ink") if self._done[index] else qcolor("border")
            pen = QPen(color, 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(
                QPoint(centers[index] + radius + S("space-1"), top),
                QPoint(centers[index + 1] - radius - S("space-1"), top),
            )
        label_font = theme.font("small")
        metrics = QFontMetrics(label_font)
        for index, center in enumerate(centers):
            done = self._done[index]
            current = index == self._current and not done
            if done:
                fill, ink, border = qcolor("status-ok-ink"), qcolor("surface"), qcolor("status-ok-ink")
            elif current:
                fill, ink, border = qcolor("teal-600"), qcolor("surface"), qcolor("teal-600")
            else:
                fill, ink, border = qcolor("surface"), qcolor("text-muted"), qcolor("border-strong")
            painter.setPen(QPen(border, 1.5))
            painter.setBrush(QBrush(fill))
            painter.drawEllipse(QPoint(center, top), radius, radius)
            if done:
                pen = QPen(ink, 2)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.drawPolyline(
                    [QPoint(center - 4, top), QPoint(center - 1, top + 3), QPoint(center + 4, top - 3)]
                )
            else:
                painter.setPen(QPen(ink))
                painter.setFont(theme.font("small"))
                painter.drawText(
                    center - radius, top - radius, radius * 2, radius * 2,
                    Qt.AlignmentFlag.AlignCenter, str(index + 1),
                )
                painter.setFont(label_font)
            color = (
                qcolor("status-ok-ink") if done
                else qcolor("text-primary") if current
                else qcolor("text-muted")
            )
            painter.setPen(QPen(color))
            width = int(self.width() / max(1, len(centers)))
            text = metrics.elidedText(self._steps[index], Qt.TextElideMode.ElideRight, width - S("space-2"))
            painter.drawText(
                center - width // 2, top + radius + S("space-1"), width, 18,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, text,
            )
        painter.end()


class _OccupancyBar(QWidget):
    """Inner rounded meter; colour follows the occupancy state."""

    _STATE_TOKENS = {"ok": "teal-500", "near": "status-pending-ink", "full": "status-danger-ink"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._ratio = 0.0
        self._state = "ok"

    def set_values(self, ratio, state):
        self._ratio = max(0.0, min(1.0, float(ratio)))
        self._state = state if state in self._STATE_TOKENS else "ok"
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        height = self.height()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor("surface-subtle"))
        painter.drawRoundedRect(0, 0, self.width(), height, height / 2, height / 2)
        if self._ratio > 0:
            painter.setBrush(qcolor(self._STATE_TOKENS[self._state]))
            painter.drawRoundedRect(0, 0, int(self.width() * self._ratio), height, height / 2, height / 2)
        painter.end()


class RoomOccupancyBar(QWidget):
    """Capacity meter: ``3 / 4`` + bar (teal under load, amber nearly full, red full).

    ``RoomOccupancyBar(occupied=0, capacity=4, parent=None)``;
    ``set_values(occupied, capacity)``; ``is_full()`` returns ``True`` at capacity.
    """

    def __init__(self, occupied=0, capacity=4, parent=None):
        super().__init__(parent)
        self._occupied = 0
        self._capacity = 1
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(S("space-1"))
        line = QHBoxLayout()
        line.setSpacing(S("space-2"))
        self._value = QLabel()
        theme.apply_role(self._value, "small")
        theme.enable_tabular(self._value)
        self._full_label = QLabel("Full")
        theme.apply_role(self._full_label, "small")
        self._full_label.setStyleSheet(
            f"color: {C('status-danger-ink')}; font-size: {C('fs-small')}; font-weight: {C('fw-semibold')};"
        )
        line.addWidget(self._value)
        line.addStretch(1)
        line.addWidget(self._full_label)
        self._bar = _OccupancyBar()
        root.addLayout(line)
        root.addWidget(self._bar)
        self.set_values(occupied, capacity)

    def set_values(self, occupied, capacity):
        """Update occupancy; the bar and the word "Full" follow automatically."""
        self._occupied = max(0, int(occupied))
        self._capacity = max(1, int(capacity or 1))
        ratio = self._occupied / self._capacity
        full = self._occupied >= self._capacity
        state = "full" if full else ("near" if ratio >= 0.8 else "ok")
        self._bar.set_values(ratio, state)
        self._value.setText(f"{self._occupied} / {self._capacity}")
        self._value.setToolTip(f"{self._occupied} of {self._capacity} beds occupied")
        self._full_label.setVisible(full)
        return self

    def is_full(self):
        """``True`` when the room is at or above capacity."""
        return self._occupied >= self._capacity


class Skeleton(QWidget):
    """Loading placeholder: ``Skeleton(rows=3, parent=None)``.

    Grey ``surface-subtle`` rounded blocks with a slow opacity pulse. The
    animation is parented to the widget and only runs while it is visible, so
    tests that never show the widget are unaffected and nothing leaks.
    """

    _BLOCK_HEIGHT = 12
    _GAP = 10

    def __init__(self, rows=3, parent=None):
        super().__init__(parent)
        self.setObjectName("skeleton")
        self._row_count = max(1, int(rows))
        self._pulse = 1.0
        self.setMinimumHeight(self._row_count * (self._BLOCK_HEIGHT + self._GAP))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._animation = QPropertyAnimation(self, b"pulse", self)
        self._animation.setStartValue(1.0)
        self._animation.setKeyValueAt(0.5, 0.4)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(1600)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)

    def _get_pulse(self):
        return self._pulse

    def _set_pulse(self, value):
        self._pulse = float(value)
        self.update()

    pulse = Property(float, _get_pulse, _set_pulse)

    def showEvent(self, event):  # noqa: N802 - Qt API
        super().showEvent(event)
        self._animation.start()

    def hideEvent(self, event):  # noqa: N802 - Qt API
        self._animation.stop()
        super().hideEvent(event)

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = qcolor("surface-subtle")
        color.setAlphaF(max(0.15, min(1.0, 0.35 + 0.65 * self._pulse)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        y = 0
        radius = self._BLOCK_HEIGHT / 2
        for index in range(self._row_count):
            width = self.width() if index < self._row_count - 1 else int(self.width() * 0.6)
            painter.drawRoundedRect(0, y, max(0, width), self._BLOCK_HEIGHT, radius, radius)
            y += self._BLOCK_HEIGHT + self._GAP
        painter.end()


class Toast(QFrame):
    """Bottom-right notification: ``Toast(message, kind="info", icon="bell", parent=None)``.

    Replaces the old emoji "LIVE EVENT" status text — icon + message only.
    Prefer ``show_toast(parent, message, ...)`` which positions, raises and
    auto-dismisses the toast.
    """

    def __init__(self, message, kind="info", icon="bell", parent=None):
        super().__init__(parent)
        self.setObjectName("toast")
        self._kind = kind if kind in _BANNER_KINDS else "info"
        status = _BANNER_KINDS[self._kind]
        tokens = _kind_tokens(status)
        self.setProperty("kind", self._kind)
        self.setStyleSheet(
            f"QFrame#toast {{ background-color: {C('surface')};"
            f" border: 1px solid {C('border')}; border-left: 3px solid {tokens['ink']};"
            f" border-radius: {C('radius-card')}; }}"
            f"QFrame#toast QLabel {{ color: {C('text-primary')}; font-size: {C('fs-body')}; border: none; }}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(S("space-3"), S("space-3"), S("space-3"), S("space-3"))
        row.setSpacing(S("space-2"))
        icon_label = QLabel()
        icon_label.setPixmap(get_pixmap(icon, 16, tokens["ink"]))
        text = QLabel(str(message))
        text.setWordWrap(True)
        text.setMaximumWidth(320)
        row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(text, 1)
        apply_elevation(self, 2)


def show_toast(parent, message, kind="info", icon="bell", duration_ms=4000):
    """Show a Toast at the bottom-right of ``parent``; auto-dismiss after 4 s.

    Slides in 150 ms, raises above its siblings and calls ``deleteLater`` on
    timeout (the timer and animation are parented to the toast itself).
    """
    if parent is None:
        return None
    toast = Toast(message, kind, icon, parent)
    toast.adjustSize()
    margin = S("space-6")
    end = QPoint(
        max(0, parent.width() - toast.width() - margin),
        max(0, parent.height() - toast.height() - margin),
    )
    start = QPoint(end.x() + 16, end.y())
    toast.move(start)
    toast.show()
    toast.raise_()
    slide = QPropertyAnimation(toast, b"pos", toast)
    slide.setDuration(S("dur-fast"))
    slide.setStartValue(start)
    slide.setEndValue(end)
    slide.setEasingCurve(QEasingCurve.Type.OutCubic)
    slide.start()
    timer = QTimer(toast)
    timer.setSingleShot(True)
    timer.timeout.connect(toast.deleteLater)
    timer.start(int(duration_ms))
    return toast


class ConfirmDialog(QDialog):
    """Danger-aware confirmation dialog.

    ``ConfirmDialog(parent, title, message, confirm_text="Delete", danger=True, cancel_text="Cancel")``;
    ``confirmed`` is ``True`` only after the confirm button. ``ConfirmDialog.ask(...)``
    execs the dialog and returns that boolean.
    """

    def __init__(self, parent, title, message, confirm_text="Delete", danger=True, cancel_text="Cancel"):
        super().__init__(parent)
        self.confirmed = False
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(380)
        root = QVBoxLayout(self)
        root.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        root.setSpacing(S("space-4"))
        head = QHBoxLayout()
        head.setSpacing(S("space-3"))
        icon = QLabel()
        icon.setPixmap(
            get_pixmap(
                "alert-triangle" if danger else "info",
                22,
                C("status-danger-ink") if danger else C("teal-600"),
            )
        )
        head.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        column = QVBoxLayout()
        column.setSpacing(S("space-1"))
        title_label = QLabel(title)
        theme.apply_role(title_label, "h2")
        message_label = QLabel(message)
        theme.apply_role(message_label, "muted")
        message_label.setWordWrap(True)
        column.addWidget(title_label)
        column.addWidget(message_label)
        head.addLayout(column, 1)
        root.addLayout(head)
        buttons = QHBoxLayout()
        buttons.setSpacing(S("space-2"))
        buttons.addStretch(1)
        cancel_button = Button(cancel_text, "secondary")
        confirm_button = Button(confirm_text, "danger" if danger else "primary")
        cancel_button.clicked.connect(self.reject)
        confirm_button.clicked.connect(self._on_confirm)
        buttons.addWidget(cancel_button)
        buttons.addWidget(confirm_button)
        root.addLayout(buttons)
        apply_elevation(self, 2)

    def _on_confirm(self):
        self.confirmed = True
        self.accept()

    @classmethod
    def ask(cls, parent, title, message, confirm_text="Delete", danger=True):
        """Exec the dialog; ``True`` when the confirm button was used."""
        dialog = cls(parent, title, message, confirm_text, danger)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return bool(accepted and dialog.confirmed)


class BrandMark(QLabel):
    """Brand image: ``BrandMark(variant="mark"|"logo", color="brand"|"white", size=32, parent=None)``.

    Loads ``desktop/assets/brand/resivo_{mark|logo}[_white].png``, scaled
    smoothly; falls back to a text wordmark when the file is missing.
    """

    def __init__(self, variant="mark", color="brand", size=32, parent=None):
        super().__init__(parent)
        kind = variant if variant in ("mark", "logo") else "mark"
        suffix = "_white" if color == "white" else ""
        for candidate in (f"resivo_{kind}{suffix}.png", f"resivo_{kind}.png"):
            path = _BRAND_DIR / candidate
            if path.is_file():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    self.setPixmap(
                        pixmap.scaled(
                            int(size), int(size),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    self.setToolTip("RÉSIVO")
                    return
        self.setText("RÉSIVO" if kind == "logo" else "R")
        ink = C("text-on-dark") if color == "white" else C("text-secondary")
        self.setStyleSheet(
            f"color: {ink}; font-size: {C('fs-h3')}; font-weight: {C('fw-bold')};"
        )


class GradientHero(QFrame):
    """Brand-gradient hero container (135°: navy-800 → teal-600 → green-500).

    ``GradientHero(parent=None)``; add children to ``self.body`` (a
    ``QVBoxLayout``). The gradient plus a ≤6% white curve pattern are painted in
    ``paintEvent``; children keep transparent backgrounds.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gradientHero")
        self.setMinimumHeight(150)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(S("space-6"), S("space-6"), S("space-6"), S("space-6"))
        self.body.setSpacing(S("space-3"))

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        radius = S("radius-hero")
        shape = QPainterPath()
        shape.addRoundedRect(rect, radius, radius)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, qcolor("navy-800"))
        gradient.setColorAt(0.55, qcolor("teal-600"))
        gradient.setColorAt(1.0, qcolor("green-500"))
        painter.fillPath(shape, gradient)
        painter.setClipPath(shape)
        pattern = qcolor("surface")
        pattern.setAlpha(15)  # ~6% white, per DESIGN.md §1
        pen = QPen(pattern, 1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for index in range(3):
            ring = QPainterPath()
            span = rect.height() * (0.85 + index * 0.42)
            center = QPointF(rect.right() - rect.height() * 0.1, rect.bottom() + rect.height() * 0.3)
            ring.addEllipse(center, span, span)
            painter.drawPath(ring)
        painter.end()


class LiveDot(QLabel):
    """Live-sync indicator dot: ``LiveDot(parent=None)``.

    ``set_state("connected"|"reconnecting"|"offline")`` — teal pulsing /
    amber / red. The caller sets the tooltip text. Object name ``liveDot``.
    """

    _STATE_TOKENS = {
        "connected": "teal-500",
        "reconnecting": "gold-500",
        "offline": "status-danger-ink",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("liveDot")
        self.setFixedSize(10, 10)
        self._state = "connected"
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._animation = QPropertyAnimation(self._effect, b"opacity", self)
        self._animation.setStartValue(1.0)
        self._animation.setKeyValueAt(0.5, 0.35)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(1200)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.set_state("connected")

    def set_state(self, state):
        """Switch the dot colour and start/stop the pulse (connected only)."""
        self._state = state if state in self._STATE_TOKENS else "offline"
        self.setProperty("state", self._state)
        self.setStyleSheet(
            f"background-color: {C(self._STATE_TOKENS[self._state])};"
            f" border-radius: {C('radius-dot')};"
        )
        theme.repolish(self)
        if self._state == "connected" and self.isVisible():
            self._animation.start()
        else:
            self._animation.stop()
        return self

    def showEvent(self, event):  # noqa: N802 - Qt API
        super().showEvent(event)
        if self._state == "connected":
            self._animation.start()

    def hideEvent(self, event):  # noqa: N802 - Qt API
        self._animation.stop()
        super().hideEvent(event)


# ---------------------------------------------------------------------------
# Table helpers (DESIGN.md §6 — DataTable contract)
# ---------------------------------------------------------------------------
def set_row_height(table: QTableView, h: int = 44) -> QTableView:
    """Set the default row height (44px per DESIGN.md §6)."""
    table.verticalHeader().setDefaultSectionSize(int(h))
    return table


def enable_tabular_numerics(table: QTableView) -> QTableView:
    """Apply tabular figures to the whole table (card IDs, rooms, counts, dates)."""
    theme.enable_tabular(table)
    return table


def style_table(table: QTableView) -> QTableView:
    """No gridlines, row selection, 44px rows, overline header, tabular numerics."""
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(False)
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setStretchLastSection(True)
    vertical = table.verticalHeader()
    if vertical is not None:
        vertical.setVisible(False)
    set_row_height(table)
    enable_tabular_numerics(table)
    return table


def configure_table(table: QTableView, headers: list[str]) -> QTableView:
    """Set uppercased headers (the overline look) and apply ``style_table``."""
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels([str(head).upper() for head in headers])
    return style_table(table)


def apply_shadow(widget: QWidget, level: int = 1) -> QWidget:
    """Alias of :func:`theme.apply_elevation` (level 1 = hairline, 2 = shadow)."""
    return apply_elevation(widget, level)


