"""RÉSIVO — Reusable NumberStepper component.

A 40px-high bordered numeric input field [ value field ][ - ][ + ] wrapping a
QSpinBox with author-styled ghost buttons and tabular figures.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QSize, Qt
from PySide6.QtGui import QFocusEvent, QWheelEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QHBoxLayout,
    QSpinBox,
    QToolButton,
    QWidget,
)

from .icons import get_icon
from .theme import C, enable_tabular


class _InnerSpinBox(QSpinBox):
    """Inner QSpinBox with hidden native buttons and wheel-on-focus guard."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        enable_tabular(self)
        self.setStyleSheet(
            f"QSpinBox {{ "
            f"background: transparent; "
            f"border: none; "
            f"color: {C('text-primary')}; "
            f"padding: 0px 8px 0px 12px; "
            f"}} "
            f"QSpinBox:disabled {{ "
            f"color: {C('text-muted')}; "
            f"}}"
        )

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        # Only adjust value on mouse wheel if the spin box currently has keyboard focus
        if not self.hasFocus():
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta > 0:
            self.stepUp()
            event.accept()
        elif delta < 0:
            self.stepDown()
            event.accept()
        else:
            super().wheelEvent(event)


class NumberStepper(QWidget):
    """Reusable numeric stepper component [ value field ][ - ][ + ].

    Wraps a QSpinBox, preserving its core API (value, setValue, setRange,
    setMinimum, setMaximum, minimum, maximum, valueChanged, stepUp, stepDown),
    with auto-repeating ghost buttons, tabular numerics, and a 40px height.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setObjectName("numberStepper")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(2)

        self._spin = _InnerSpinBox(self)
        layout.addWidget(self._spin, 1)

        btn_qss = (
            f"QToolButton {{ "
            f"background-color: transparent; "
            f"border: none; "
            f"border-radius: 6px; "
            f"padding: 0px; "
            f"}} "
            f"QToolButton:hover {{ "
            f"background-color: {C('surface-subtle')}; "
            f"}} "
            f"QToolButton:pressed {{ "
            f"background-color: {C('border')}; "
            f"}} "
            f"QToolButton:disabled {{ "
            f"background-color: transparent; "
            f"}}"
        )

        # Minus button [ - ]
        self.minus_btn = QToolButton(self)
        self.minus_btn.setObjectName("stepperMinus")
        self.minus_btn.setFixedSize(32, 32)
        self.minus_btn.setIcon(get_icon("minus", 14, C("text-secondary")))
        self.minus_btn.setIconSize(QSize(14, 14))
        self.minus_btn.setStyleSheet(btn_qss)
        self.minus_btn.setAutoRepeat(True)
        self.minus_btn.setAutoRepeatDelay(300)
        self.minus_btn.setAutoRepeatInterval(60)
        self.minus_btn.setToolTip("Decrease value")
        self.minus_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.minus_btn.clicked.connect(self.stepDown)
        layout.addWidget(self.minus_btn)

        # Plus button [ + ]
        self.plus_btn = QToolButton(self)
        self.plus_btn.setObjectName("stepperPlus")
        self.plus_btn.setFixedSize(32, 32)
        self.plus_btn.setIcon(get_icon("plus", 14, C("text-secondary")))
        self.plus_btn.setIconSize(QSize(14, 14))
        self.plus_btn.setStyleSheet(btn_qss)
        self.plus_btn.setAutoRepeat(True)
        self.plus_btn.setAutoRepeatDelay(300)
        self.plus_btn.setAutoRepeatInterval(60)
        self.plus_btn.setToolTip("Increase value")
        self.plus_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.plus_btn.clicked.connect(self.stepUp)
        layout.addWidget(self.plus_btn)

        # Forward signal
        self.valueChanged = self._spin.valueChanged
        self._spin.valueChanged.connect(self._on_value_changed)

        # Focus monitoring on inner spin box for focus ring styling
        self._spin.installEventFilter(self)

        self._update_container_style(focused=False)
        self._update_buttons()

    def _update_container_style(self, focused: bool = False) -> None:
        if not self.isEnabled():
            self.setStyleSheet(
                f"#numberStepper {{ "
                f"background-color: {C('surface-subtle')}; "
                f"border: 1px solid {C('border')}; "
                f"border-radius: 8px; "
                f"}}"
            )
        elif focused:
            self.setStyleSheet(
                f"#numberStepper {{ "
                f"background-color: {C('surface')}; "
                f"border: 2px solid {C('teal-600')}; "
                f"border-radius: 8px; "
                f"}}"
            )
        else:
            self.setStyleSheet(
                f"#numberStepper {{ "
                f"background-color: {C('surface')}; "
                f"border: 1px solid {C('border')}; "
                f"border-radius: 8px; "
                f"}} "
                f"#numberStepper:hover {{ "
                f"border-color: {C('border-strong')}; "
                f"}}"
            )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt API
        if watched is self._spin:
            if event.type() == QEvent.Type.FocusIn:
                self._update_container_style(focused=True)
            elif event.type() == QEvent.Type.FocusOut:
                self._update_container_style(focused=False)
        return super().eventFilter(watched, event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        if not self._spin.hasFocus():
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta > 0:
            self.stepUp()
            event.accept()
        elif delta < 0:
            self.stepDown()
            event.accept()
        else:
            super().wheelEvent(event)

    def _update_buttons(self) -> None:
        enabled = self.isEnabled()
        val = self._spin.value()
        min_v = self._spin.minimum()
        max_v = self._spin.maximum()

        self.minus_btn.setEnabled(enabled and val > min_v)
        self.plus_btn.setEnabled(enabled and val < max_v)

    def _on_value_changed(self, _val: int) -> None:
        self._update_buttons()

    # ----------------------------------------------------------- QSpinBox API
    def value(self) -> int:
        return self._spin.value()

    def setValue(self, val: int) -> None:  # noqa: N802 - Qt API
        self._spin.setValue(val)
        self._update_buttons()

    def setRange(self, min_val: int, max_val: int) -> None:  # noqa: N802 - Qt API
        self._spin.setRange(min_val, max_val)
        self._update_buttons()

    def setMinimum(self, min_val: int) -> None:  # noqa: N802 - Qt API
        self._spin.setMinimum(min_val)
        self._update_buttons()

    def setMaximum(self, max_val: int) -> None:  # noqa: N802 - Qt API
        self._spin.setMaximum(max_val)
        self._update_buttons()

    def minimum(self) -> int:
        return self._spin.minimum()

    def maximum(self) -> int:
        return self._spin.maximum()

    def singleStep(self) -> int:  # noqa: N802 - Qt API
        return self._spin.singleStep()

    def setSingleStep(self, step: int) -> None:  # noqa: N802 - Qt API
        self._spin.setSingleStep(step)

    def stepUp(self) -> None:  # noqa: N802 - Qt API
        self._spin.stepUp()
        self._update_buttons()

    def stepDown(self) -> None:  # noqa: N802 - Qt API
        self._spin.stepDown()
        self._update_buttons()

    def selectAll(self) -> None:  # noqa: N802 - Qt API
        self._spin.selectAll()

    def clear(self) -> None:
        self._spin.clear()

    def text(self) -> str:
        return self._spin.text()

    def cleanText(self) -> str:  # noqa: N802 - Qt API
        return self._spin.cleanText()

    def prefix(self) -> str:
        return self._spin.prefix()

    def setPrefix(self, prefix: str) -> None:  # noqa: N802 - Qt API
        self._spin.setPrefix(prefix)

    def suffix(self) -> str:
        return self._spin.suffix()

    def setSuffix(self, suffix: str) -> None:  # noqa: N802 - Qt API
        self._spin.setSuffix(suffix)

    def setSpecialValueText(self, text: str) -> None:  # noqa: N802 - Qt API
        self._spin.setSpecialValueText(text)

    def setToolTip(self, tip: str) -> None:  # noqa: N802 - Qt API
        super().setToolTip(tip)
        self._spin.setToolTip(tip)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 - Qt API
        super().setEnabled(enabled)
        self._spin.setEnabled(enabled)
        self._update_container_style(focused=False)
        self._update_buttons()

    def setFocus(self) -> None:  # noqa: N802 - Qt API
        self._spin.setFocus()
