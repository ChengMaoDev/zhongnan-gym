from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

MAC_HELPER = r"""#!/bin/sh
set -eu
app_pid="$1"
archive="$2"
target="$3"
stage="$(mktemp -d "$(dirname "$target")/.zhongnan-update.XXXXXX")"
backup="$stage/previous.app"
recover() {
    if [ -d "$backup" ] && [ ! -d "$target" ]; then mv "$backup" "$target"; fi
    /usr/bin/open "$target" || true
}
trap recover EXIT
/usr/bin/ditto -x -k "$archive" "$stage"
test -f "$stage/终南健身.app/Contents/MacOS/ZhongnanGym"
while kill -0 "$app_pid" 2>/dev/null; do sleep 0.2; done
mv "$target" "$backup"
mv "$stage/终南健身.app" "$target"
/usr/bin/open "$target"
trap - EXIT
rm -rf "$stage"
"""

WINDOWS_HELPER = r"""param([int]$ParentPid, [string]$Source, [string]$Target, [string]$ErrorFile)
$ErrorActionPreference = 'Stop'
$backup = $Target + '.previous'
$staged = $Target + '.new'
try {
    Copy-Item -LiteralPath $Source -Destination $staged -Force
    $parent = Get-Process -Id $ParentPid -ErrorAction SilentlyContinue
    if ($parent) { Wait-Process -Id $ParentPid -Timeout 60 }
    if (Test-Path -LiteralPath $backup) { throw 'Previous update backup already exists' }
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        try { Move-Item -LiteralPath $Target -Destination $backup; break }
        catch { if ($attempt -eq 39) { throw }; Start-Sleep -Milliseconds 250 }
    }
    Move-Item -LiteralPath $staged -Destination $Target
    Start-Process -FilePath $Target
    Remove-Item -LiteralPath $backup
} catch {
    $_.Exception.Message | Out-File -LiteralPath $ErrorFile -Encoding utf8
    if ((Test-Path -LiteralPath $backup) -and !(Test-Path -LiteralPath $Target)) {
        Move-Item -LiteralPath $backup -Destination $Target
    }
    if (Test-Path -LiteralPath $Target) { Start-Process -FilePath $Target }
}
"""


def validate_archive(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        total = 0
        for entry in archive.infolist():
            name = PurePosixPath(entry.filename)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError("更新包包含越界路径")
            total += entry.file_size
            if total > 2 * 1024**3:
                raise ValueError("更新包展开大小异常")
        if "终南健身.app/Contents/MacOS/ZhongnanGym" not in archive.namelist():
            raise ValueError("更新包缺少应用主程序")


def install_update(archive: Path, directory: Path) -> None:
    if not getattr(sys, "frozen", False):
        raise RuntimeError("源码运行时请更新源码，安装包更新仅用于已打包应用")
    environment = os.environ.copy()
    environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    log_path = directory / "install.log"
    if sys.platform == "darwin":
        validate_archive(archive)
        helper = directory / "install.sh"
        _ = helper.write_text(MAC_HELPER, encoding="utf-8")
        target = Path(sys.executable).parents[2]
        if target.suffix != ".app":
            raise ValueError("无法确定当前应用位置")
        command = ["/bin/sh", str(helper), str(os.getpid()), str(archive), str(target)]
        creationflags = 0
    elif sys.platform == "win32":
        helper = directory / "install.ps1"
        _ = helper.write_text(WINDOWS_HELPER, encoding="utf-8-sig")
        command = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper),
            "-ParentPid",
            str(os.getpid()),
            "-Source",
            str(archive),
            "-Target",
            sys.executable,
            "-ErrorFile",
            str(log_path),
        ]
        creationflags = subprocess.CREATE_NO_WINDOW
    else:
        raise RuntimeError("此系统不支持安装更新")
    with log_path.open("ab") as log:
        _ = subprocess.Popen(
            command,
            env=environment,
            stdout=log,
            stderr=log,
            creationflags=creationflags,
            start_new_session=sys.platform != "win32",
        )
