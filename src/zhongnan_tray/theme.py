from dataclasses import dataclass

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Theme:
    background: str
    surface: str
    text: str
    muted: str
    line: str
    actual: str = "#087f9c"
    forecast: str = "#7961c9"


def theme() -> Theme:
    dark = QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128
    if dark:
        return Theme(
            "#1d2630", "#24313e", "#edf3f8", "#a4b5c5", "#3c4c5d", "#64d3df", "#b2a1f1"
        )
    return Theme("#f7f9fc", "#eaf0f7", "#193247", "#647d90", "#dce5ee")


def stylesheet() -> str:
    t = theme()
    return f"""
        QMenu {{ background:{t.background}; color:{t.text}; border:1px solid {t.line};
            border-radius:10px; padding:5px; font-size:12px; }}
        QMenu::item {{ padding:7px 12px; border-radius:6px; }}
        QMenu::item:selected {{ background:{t.surface}; }}
        QMenu::separator {{ height:1px; background:{t.line}; margin:6px 14px; }}
        QWidget#panel {{ background:{t.background}; color:{t.text}; }}
        QLabel {{ color:{t.text}; background:transparent; }}
        QLabel#brand {{ font-size:14px; font-weight:600; }}
        QLabel#muted, QLabel#status, QLabel#model {{ color:{t.muted}; font-size:11px; }}
        QLabel#count {{ font-size:36px; font-weight:600; }}
        QLabel#date {{ font-size:12px; font-weight:600; }}
        QLabel#summary {{ color:{t.muted}; font-size:11px; }}
        QToolButton {{ color:{t.text}; background:transparent; border:0;
            border-radius:6px; font-size:14px; padding:3px 8px; }}
        QToolButton:hover {{ background:{t.surface}; }}
        QToolButton:disabled {{ color:{t.line}; }}
        QToolButton:focus {{ border:1px solid {t.actual}; }}
    """
