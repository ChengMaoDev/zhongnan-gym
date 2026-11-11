from __future__ import annotations

import hashlib
import platform
import re
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from pydantic import BaseModel

from .release import LATEST_URL, REPOSITORY, VERSION

MAX_SIZE = 350 * 1024 * 1024


class ReleaseAsset(BaseModel):
    name: str
    browser_download_url: str
    digest: str | None = None
    size: int


class Release(BaseModel):
    tag_name: str
    draft: bool = False
    prerelease: bool = False
    assets: list[ReleaseAsset]


@dataclass(frozen=True)
class Update:
    version: str
    name: str
    url: str
    digest: str
    size: int


def version_tuple(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise ValueError("版本号格式异常")
    return int(match[1]), int(match[2]), int(match[3])


def asset_name() -> str:
    if sys.platform == "win32":
        return "ZhongnanGym-Windows-x64.exe"
    if sys.platform == "darwin":
        return f"ZhongnanGym-macOS-{platform.machine()}.zip"
    raise ValueError("此系统没有发布包")


def parse_release(payload: bytes, current: str, name: str) -> Update | None:
    release = Release.model_validate_json(payload)
    if release.draft or release.prerelease:
        return None
    if version_tuple(release.tag_name) <= version_tuple(current):
        return None
    for asset in release.assets:
        if asset.name != name:
            continue
        url = urlparse(asset.browser_download_url)
        if (
            url.scheme != "https"
            or url.netloc != "github.com"
            or not url.path.startswith(
                f"/{REPOSITORY}/releases/download/{release.tag_name}/"
            )
        ):
            raise ValueError("更新下载地址不属于发布仓库")
        if not asset.digest or not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.digest):
            raise ValueError("更新包没有有效的SHA-256摘要")
        if not 0 < asset.size <= MAX_SIZE:
            raise ValueError("更新包大小异常")
        return Update(
            release.tag_name.lstrip("v"),
            asset.name,
            asset.browser_download_url,
            asset.digest[7:],
            asset.size,
        )
    raise ValueError("此版本尚无匹配当前系统的更新包")


def latest(current: str = VERSION, name: str | None = None) -> Update | None:
    request = urllib.request.Request(
        LATEST_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"ZhongnanGym/{VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = cast(bytes, response.read(1024 * 1024))
    return parse_release(payload, current, name or asset_name())


def download(
    update: Update,
    directory: Path,
    cancelled: Callable[[], bool],
    progress: Callable[[int], None],
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / update.name
    if target.exists():
        with target.open("rb") as existing:
            if hashlib.file_digest(existing, "sha256").hexdigest() == update.digest:
                return target
    partial = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    size = 0
    request = urllib.request.Request(
        update.url, headers={"User-Agent": f"ZhongnanGym/{VERSION}"}
    )
    try:
        with (
            urllib.request.urlopen(request, timeout=15) as response,
            partial.open("wb") as output,
        ):
            while True:
                if cancelled():
                    raise InterruptedError("取消下载")
                chunk = cast(bytes, response.read(128 * 1024))
                if not chunk:
                    break
                size += len(chunk)
                if size > update.size:
                    raise ValueError("更新包超过声明大小")
                _ = output.write(chunk)
                digest.update(chunk)
                progress(size * 100 // update.size)
        if size != update.size or digest.hexdigest() != update.digest:
            raise ValueError("更新包完整性校验失败")
        _ = partial.replace(target)
        return target
    finally:
        partial.unlink(missing_ok=True)
