import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, TypedDict
import re
from urllib.parse import urlparse

import numpy as np
import numpy.typing as npt
from beartype import beartype
from PIL import Image

try:
    from vertexai.preview.generative_models import Image as VertexImage  # type: ignore
except Exception:
    # Optional dependency; only used when Google Cloud is configured.
    VertexImage = None  # type: ignore

@dataclass
class DetachedPage:
    url: str
    content: str  # html


@beartype
def png_bytes_to_numpy(png: bytes) -> npt.NDArray[np.uint8]:
    """Convert png bytes to numpy array

    Example:

    >>> fig = go.Figure(go.Scatter(x=[1], y=[1]))
    >>> plt.imshow(png_bytes_to_numpy(fig.to_image('png')))
    """
    return np.array(Image.open(BytesIO(png)))


def pil_to_b64(img: Image.Image) -> str:
    with BytesIO() as image_buffer:
        img.save(image_buffer, format="PNG")
        byte_data = image_buffer.getvalue()
        img_b64 = base64.b64encode(byte_data).decode("utf-8")
        img_b64 = "data:image/png;base64," + img_b64
    return img_b64


def pil_to_vertex(img: Image.Image):  # type: ignore[no-untyped-def]
    if VertexImage is None:
        raise ImportError("vertexai is not available. Configure Google Cloud to use pil_to_vertex().")
    with BytesIO() as image_buffer:
        img.save(image_buffer, format="PNG")
        byte_data = image_buffer.getvalue()
        return VertexImage.from_bytes(byte_data)


class DOMNode(TypedDict):
    nodeId: str
    nodeType: str
    nodeName: str
    nodeValue: str
    attributes: str
    backendNodeId: str
    parentId: str
    childIds: list[str]
    cursor: int
    union_bound: list[float] | None
    center: list[float] | None


class AccessibilityTreeNode(TypedDict):
    nodeId: str
    ignored: bool
    role: dict[str, Any]
    chromeRole: dict[str, Any]
    name: dict[str, Any]
    properties: list[dict[str, Any]]
    childIds: list[str]
    parentId: str
    backendDOMNodeId: int
    frameId: str
    bound: list[float] | None
    union_bound: list[float] | None
    offsetrect_bound: list[float] | None
    center: list[float] | None


class BrowserConfig(TypedDict):
    win_upper_bound: float
    win_left_bound: float
    win_width: float
    win_height: float
    win_right_bound: float
    win_lower_bound: float
    device_pixel_ratio: float


class BrowserInfo(TypedDict):
    DOMTree: dict[str, Any]
    config: BrowserConfig


AccessibilityTree = list[AccessibilityTreeNode]
DOMTree = list[DOMNode]

Observation = str | npt.NDArray[np.uint8]


class StateInfo(TypedDict):
    observation: dict[str, Observation]
    info: Dict[str, Any]
    url: str


# -------------------- URL mapping helpers (stateless) --------------------
def _strip_www(host: str) -> str:
    """Return host without a leading 'www.' prefix (case-insensitive)."""
    host_lower = host.lower()
    return host_lower[4:] if host_lower.startswith("www.") else host_lower


def _split_base(base: str) -> tuple[str, str, str]:
    """Return (scheme, host_no_www, path_prefix) for a base URL.

    Ensures path_prefix starts with '/' or is '' if missing.
    """
    p = urlparse(base)
    path = p.path or ""
    if path and not path.startswith("/"):
        path = "/" + path
    return (p.scheme or "http", _strip_www(p.netloc), path)


def _build_url(base: str, remainder_path: str, query: str, fragment: str) -> str:
    base = base.rstrip("/")
    # Avoid double slashes when remainder_path is empty or '/'
    if remainder_path.startswith("/"):
        url = f"{base}{remainder_path}"
    elif remainder_path:
        url = f"{base}/{remainder_path}"
    else:
        url = base
    if query:
        url += f"?{query}"
    if fragment:
        url += f"#{fragment}"
    return url


def map_url(url: str, src_to_dst: dict[str, str]) -> str:
    """Generic URL mapper.

    - src_to_dst maps base URLs from source to destination (either real->local or local->real)
    - Matches http/https URLs (with or without 'www.') in the input text
    - Preserves path/query/fragment
    - Handles bases that include a path prefix (e.g., 'http://luma.com/admin')
    """
    if not url:
        return url

    # Preprocess mapping for faster lookups
    processed = []
    for src_base, dst_base in src_to_dst.items():
        _, src_host, src_path = _split_base(src_base)
        processed.append((src_host, src_path or "/", dst_base))

    url_re = re.compile(r'https?://[^\s\]\)\"\']+')

    def _replace(m: re.Match) -> str:
        u = m.group(0)
        p = urlparse(u)
        host = _strip_www(p.netloc)
        path = p.path or ""
        for src_host, src_path, dst_base in processed:
            if host == src_host:
                sp = src_path
                if sp != "/" and not sp.startswith("/"):
                    sp = "/" + sp
                if sp == "/" or path.startswith(sp):
                    remainder = path[len(sp):] if sp != "/" else path
                    return _build_url(dst_base, remainder, p.query, p.fragment)
        return u

    return url_re.sub(_replace, url)


def map_urls_to_local(text: str, local_to_real: dict[str, str]) -> str:
    """Map real domains to local counterparts using the given mapping."""
    # invert mapping: real -> local
    real_to_local = {v: k for k, v in local_to_real.items()}
    return map_url(text, real_to_local)


def map_urls_to_real(text: str, local_to_real: dict[str, str]) -> str:
    """Map local domains to real counterparts using the given mapping."""
    return map_url(text, local_to_real)


def extract_action_from_response(response: str, action_splitter: str) -> str | None:
    pattern = rf"{action_splitter}((.|\n)*?){action_splitter}"
    match = re.search(pattern, response)
    if match:
        return match.group(1).strip()
    return None
