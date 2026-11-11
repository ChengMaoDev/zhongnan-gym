import hashlib
import io
import json
import subprocess
import urllib.response
import zipfile
from email.message import Message
from pathlib import Path

import pytest

from zhongnan_tray import download
from zhongnan_tray.download import Update, parse_release, version_tuple
from zhongnan_tray.install import MAC_HELPER, validate_archive
from zhongnan_tray.release import REPOSITORY


def release_payload(digest: str | None = None, url: str | None = None) -> bytes:
    return json.dumps(
        {
            "tag_name": "v1.2.0",
            "assets": [
                {
                    "name": "ZhongnanGym-Windows-x64.exe",
                    "size": 3,
                    "digest": digest or "sha256:" + "a" * 64,
                    "browser_download_url": url
                    or f"https://github.com/{REPOSITORY}/releases/download/v1.2.0/ZhongnanGym-Windows-x64.exe",
                }
            ],
        }
    ).encode()


def test_semantic_versions_are_compared_numerically() -> None:
    assert version_tuple("v1.10.0") > version_tuple("1.9.9")
    assert (
        parse_release(release_payload(), "1.2.0", "ZhongnanGym-Windows-x64.exe") is None
    )
    assert (
        parse_release(release_payload(), "1.1.0", "ZhongnanGym-Windows-x64.exe")
        is not None
    )


@pytest.mark.parametrize(
    "digest,url", [("sha256:abc", None), (None, "https://evil.example/update.exe")]
)
def test_update_requires_repository_url_and_full_digest(
    digest: str | None, url: str | None
) -> None:
    with pytest.raises(ValueError):
        _ = parse_release(
            release_payload(digest, url), "1.0.0", "ZhongnanGym-Windows-x64.exe"
        )


def test_download_checks_digest_and_reuses_verified_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = b"an executable"
    update = Update(
        "1.0.1",
        "update.exe",
        "https://github.com/test",
        hashlib.sha256(content).hexdigest(),
        len(content),
    )
    calls: list[int] = []

    def respond(*args: object, **kwargs: object) -> urllib.response.addinfourl:
        del args, kwargs
        calls.append(1)
        return urllib.response.addinfourl(io.BytesIO(content), Message(), update.url)

    monkeypatch.setattr(download.urllib.request, "urlopen", respond)
    path = download.download(update, tmp_path, lambda: False, lambda _: None)
    assert path.read_bytes() == content
    assert download.download(update, tmp_path, lambda: False, lambda _: None) == path
    assert len(calls) == 1


def test_bad_digest_never_creates_an_installable_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    update = Update("1.0.1", "update.exe", "https://github.com/test", "a" * 64, 3)

    def respond(*args: object, **kwargs: object) -> urllib.response.addinfourl:
        del args, kwargs
        return urllib.response.addinfourl(io.BytesIO(b"bad"), Message(), update.url)

    monkeypatch.setattr(download.urllib.request, "urlopen", respond)
    with pytest.raises(ValueError, match="校验"):
        _ = download.download(update, tmp_path, lambda: False, lambda _: None)
    assert not (tmp_path / "update.exe").exists()
    assert not (tmp_path / "update.exe.part").exists()


def test_mac_installer_rejects_zip_paths_outside_app(tmp_path: Path) -> None:
    archive = tmp_path / "update.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../outside.txt", "bad")
    with pytest.raises(ValueError, match="越界"):
        validate_archive(archive)


def test_mac_install_script_has_valid_shell_syntax() -> None:
    import sys

    if sys.platform == "win32":
        return
    _ = subprocess.run(["/bin/sh", "-n"], input=MAC_HELPER, text=True, check=True)
