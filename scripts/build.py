from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def create_icon() -> None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QPixmap

    app = QGuiApplication([])
    image = QPixmap(1024, 1024)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#0c7895"))
    painter.drawRoundedRect(QRectF(32, 32, 960, 960), 208, 208)
    painter.setPen(
        QPen(QColor("#f1fbff"), 54, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    )
    painter.drawLine(QPointF(260, 512), QPointF(764, 512))
    for x, height in ((210, 170), (340, 380), (684, 380), (814, 170)):
        painter.drawLine(QPointF(x, 512 - height / 2), QPointF(x, 512 + height / 2))
    painter.end()
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    if sys.platform == "darwin":
        iconset = build / "ZhongnanGym.iconset"
        iconset.mkdir(exist_ok=True)
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                suffix = "@2x" if scale == 2 else ""
                target = iconset / f"icon_{size}x{size}{suffix}.png"
                if not image.scaled(
                    size * scale,
                    size * scale,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ).save(str(target)):
                    raise RuntimeError(f"无法写入图标 {target}")
        _ = subprocess.run(
            [
                "iconutil",
                "-c",
                "icns",
                str(iconset),
                "-o",
                str(build / "ZhongnanGym.icns"),
            ],
            check=True,
        )
    elif not image.scaled(256, 256).save(str(build / "ZhongnanGym.ico"), "ICO"):
        raise RuntimeError("无法生成 Windows 图标")
    del app


def main() -> None:
    create_icon()
    _ = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            str(ROOT / "packaging" / "zhongnan.spec"),
        ],
        cwd=ROOT,
        check=True,
    )
    if sys.platform == "darwin":
        archive = ROOT / "dist" / f"ZhongnanGym-macOS-{platform.machine()}.zip"
        _ = subprocess.run(
            [
                "ditto",
                "-c",
                "-k",
                "--sequesterRsrc",
                "--keepParent",
                str(ROOT / "dist" / "终南健身.app"),
                str(archive),
            ],
            check=True,
        )
    else:
        _ = shutil.make_archive(
            str(ROOT / "dist" / "ZhongnanGym-Windows-x64"),
            "zip",
            ROOT / "dist",
            "ZhongnanGym-Windows-x64.exe",
        )


if __name__ == "__main__":
    main()
