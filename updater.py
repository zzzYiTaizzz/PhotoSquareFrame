from __future__ import annotations

import hashlib
import json
import platform
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from version import APP_VERSION, GITHUB_REPOSITORY


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    url: str
    digest: str
    size: int


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    title: str
    notes: str
    asset: ReleaseAsset


class UpdateCheckError(Exception):
    """Raised when GitHub cannot provide a usable update response."""


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = value.strip().lstrip("vV").split(".")
    numbers: list[int] = []
    for part in parts:
        digits = "".join(character for character in part if character.isdigit())
        numbers.append(int(digits or 0))
    return tuple(numbers)


def _asset_prefix() -> str:
    if sys.platform == "darwin":
        return "PhotoSquareFrame-macOS-arm64-v" if platform.machine().lower() in {"arm64", "aarch64"} else "PhotoSquareFrame-macOS-x64-v"
    if sys.platform == "win32":
        return "PhotoSquareFrame-Windows-x64-v"
    return ""


def fetch_update(timeout: int = 8) -> UpdateInfo | None:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "PhotoSquareFrame"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            release = json.load(response)
    except urllib.error.HTTPError as error:
        raise UpdateCheckError(_format_http_error(error)) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise UpdateCheckError("无法连接 GitHub，请检查网络连接后重试。") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise UpdateCheckError("GitHub 返回的数据无法解析，请稍后重试。") from error

    if release.get("draft") or release.get("prerelease"):
        return None
    latest = str(release.get("tag_name", "")).lstrip("vV")
    if not latest or _version_tuple(latest) <= _version_tuple(APP_VERSION):
        return None

    prefix = _asset_prefix()
    if not prefix:
        return None
    for item in release.get("assets", []):
        name = str(item.get("name", ""))
        digest = str(item.get("digest", ""))
        url = str(item.get("browser_download_url", ""))
        valid_extension = name.endswith(".dmg") if sys.platform == "darwin" else name.endswith(".zip")
        if name.startswith(prefix) and valid_extension and url.startswith("https://github.com/") and digest.startswith("sha256:"):
            return UpdateInfo(
                version=latest,
                title=str(release.get("name") or f"Photo Square Frame v{latest}"),
                notes=str(release.get("body") or ""),
                asset=ReleaseAsset(name, url, digest.removeprefix("sha256:"), int(item.get("size") or 0)),
            )
    raise UpdateCheckError(f"已发现 v{latest}，但该版本没有可用的当前平台安装包。")


def download_update(info: UpdateInfo, progress: Callable[[int], None] | None = None) -> Path:
    suffix = Path(info.asset.name).suffix
    target = Path(tempfile.gettempdir()) / f"PhotoSquareFrame-update{suffix}"
    request = urllib.request.Request(info.asset.url, headers={"User-Agent": "PhotoSquareFrame"})
    digest = hashlib.sha256()
    received = 0
    total = info.asset.size
    try:
        with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                if progress and total:
                    progress(min(100, round(received * 100 / total)))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    if digest.hexdigest().lower() != info.asset.digest.lower():
        target.unlink(missing_ok=True)
        raise ValueError("下载文件校验失败，文件可能已损坏或来源不可信。")
    if progress:
        progress(100)
    return target


def _format_http_error(error: urllib.error.HTTPError) -> str:
    body = ""
    try:
        body = error.read().decode("utf-8", errors="replace")
    except Exception:
        pass
    try:
        message = str(json.loads(body).get("message", "")).lower()
    except (json.JSONDecodeError, AttributeError):
        message = body.lower()

    headers = error.headers or {}
    remaining = headers.get("X-RateLimit-Remaining", "")
    if error.code == 403 and ("rate limit" in message or remaining == "0"):
        reset = headers.get("X-RateLimit-Reset", "")
        try:
            reset_at = datetime.fromtimestamp(int(reset), tz=timezone.utc).astimezone()
            reset_text = reset_at.strftime("%H:%M")
            return f"GitHub API 请求次数已达上限，请在 {reset_text} 后重试。"
        except (TypeError, ValueError, OverflowError, OSError):
            return "GitHub API 请求次数已达上限，请稍后重试。"
    if error.code == 403:
        return "GitHub 拒绝了更新检查请求（HTTP 403），请稍后重试。"
    if error.code == 404:
        return "找不到 GitHub 更新信息（HTTP 404），请稍后重试。"
    return f"GitHub 返回错误（HTTP {error.code}），请稍后重试。"


def format_error(error: Exception) -> str:
    if isinstance(error, UpdateCheckError):
        return str(error)
    if isinstance(error, urllib.error.HTTPError):
        return _format_http_error(error)
    if isinstance(error, urllib.error.URLError):
        return "无法连接 GitHub，请检查网络连接后重试。"
    return str(error) or "检查更新失败，请稍后重试。"
