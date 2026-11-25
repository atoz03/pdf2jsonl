"""Search OpenAlex and add readable, deduplicated PDFs to a local library."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import sqlite3
import ssl
import tempfile
import time
import unicodedata
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from http.client import HTTPException
from pathlib import Path
from threading import RLock
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .contract_link import sha256_file

OPENALEX_API = "https://api.openalex.org"
OPENALEX_CONTENT = "https://content.openalex.org"
WORK_ID = re.compile(r"W[0-9]+")
SCHOLAR_ID = re.compile(r"GS-[0-9a-f]{32}")
DOI = re.compile(r"10\.\d{4,9}/[^\s<>\"?#]+", re.IGNORECASE)
LABELED_DOI = re.compile(r"(?:\bdoi\s*:\s*|https?://(?:dx\.)?doi\.org/)"
                         + DOI.pattern, re.IGNORECASE)
MAX_PDF_BYTES = 100 * 1024 * 1024
SEARCH_FIELDS = (
    "id,doi,title,publication_year,authorships,primary_location,open_access,"
    "best_oa_location,locations,content_urls"
)


class PaperError(Exception):
    """An error that can be displayed without exposing request credentials."""


def normalize_doi(value: str) -> str:
    value = unquote(value.strip())
    value = re.sub(r"^(?:doi\s*:\s*|https?://(?:dx\.)?doi\.org/)", "", value, flags=re.IGNORECASE)
    value = value.rstrip(".,;:")
    if value.endswith(")") and value.count(")") > value.count("("):
        value = value[:-1]
    return value.lower() if DOI.fullmatch(value) else ""


def title_key(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    key = "".join(char for char in text if char.isalnum())
    return key if len(key) >= 12 else ""


def _https_host(url: str) -> str:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").rstrip(".")
        if parsed.scheme == "https" and parsed.port in (None, 443) and "@" not in parsed.netloc:
            return host if "." in host or ":" in host else ""
    except ValueError:
        pass
    return ""


def _public_download_url(url: str) -> None:
    host = _https_host(url)
    if not host:
        raise PaperError("全文链接需要使用公开的 HTTPS 地址。")
    try:
        addresses = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, 443)}
    except (OSError, ValueError) as exc:
        raise PaperError("无法解析全文来源。") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise PaperError("全文来源不是公网地址。")


class _PublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _public_download_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass(frozen=True)
class PdfSource:
    url: str
    provider: str
    version: str | None = None
    license: str | None = None


@dataclass(frozen=True)
class Paper:
    id: str
    doi: str
    title: str
    year: int | None
    authors: tuple[str, ...]
    journal: str
    landing_url: str
    is_oa: bool
    cached_pdf: bool
    pdfs: tuple[PdfSource, ...]
    provider: str = "openalex"


@dataclass(frozen=True)
class SearchPage:
    papers: list[Paper]
    number: int
    limit: int
    total: int | None
    has_next: bool


def validate_search(query: str, from_year: int | None, to_year: int | None, limit: int,
                    page: int, *, max_limit: int, max_results: int) -> str:
    query = query.strip()
    if not 1 <= len(query) <= 500:
        raise ValueError("请输入 1–500 个字符的关键词、题名或 DOI。")
    if any(year is not None and not 1500 <= year <= 2100 for year in (from_year, to_year)):
        raise ValueError("年份应在 1500 至 2100 之间。")
    if from_year is not None and to_year is not None and from_year > to_year:
        raise ValueError("起始年份应早于或等于结束年份。")
    if not 1 <= limit <= max_limit:
        raise ValueError(f"每页可检索 1–{max_limit} 篇论文。")
    if page < 1 or page * limit > max_results:
        raise ValueError(f"页码超出范围，该来源可翻阅前 {max_results:,} 条结果。")
    return query


def _paper(work: dict) -> Paper | None:
    work_id = (work.get("id") or "").rsplit("/", 1)[-1]
    if not WORK_ID.fullmatch(work_id):
        return None
    doi = normalize_doi(work.get("doi") or "")
    primary = work.get("primary_location") or {}
    best = work.get("best_oa_location") or {}
    landing = next((url for url in (primary.get("landing_page_url"), best.get("landing_page_url"))
                    if url and _https_host(url)), "")
    pdfs = {}
    for location in [best, *(work.get("locations") or [])]:
        url = location.get("pdf_url") or ""
        if location.get("is_oa") and _https_host(url):
            pdfs.setdefault(url, PdfSource(url, "open_access_location", location.get("version"),
                                          location.get("license")))
    return Paper(
        id=work_id, doi=doi, title=work.get("title") or work.get("display_name") or work_id,
        year=work.get("publication_year"), journal=(primary.get("source") or {}).get("display_name") or "",
        authors=tuple(item["author"]["display_name"] for item in work.get("authorships") or []
                      if (item.get("author") or {}).get("display_name")),
        landing_url=landing or ("https://doi.org/" + quote(doi, safe="/") if doi else
                                "https://openalex.org/" + work_id),
        is_oa=bool((work.get("open_access") or {}).get("is_oa")),
        cached_pdf=bool((work.get("content_urls") or {}).get("pdf")),
        pdfs=tuple(pdfs.values()),
    )


class OpenAlex:
    def __init__(self, api_key: str | None = None):
        self.api_key = (api_key if api_key is not None else os.environ.get("OPENALEX_API_KEY", "")).strip()
        self._metadata = build_opener()
        self._content = build_opener(_PublicRedirects())

    def _json(self, url: str) -> dict:
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "pdf2jsonl/4"})
        if self.api_key:
            request.add_unredirected_header("Authorization", "Bearer " + self.api_key)
        for attempt in range(2):
            try:
                with self._metadata.open(request, timeout=20) as response:
                    return json.load(response)
            except HTTPError as exc:
                with exc:
                    if exc.code == 404:
                        return {}
                    if exc.code in (429, 503):
                        retry_after = exc.headers.get("Retry-After", "")
                        if attempt == 0 and retry_after.isdigit() and int(retry_after) <= 3:
                            time.sleep(int(retry_after))
                            continue
                    if exc.code == 429:
                        raise PaperError("OpenAlex 检索暂时达到限额。请稍后重试或配置 API Key。") from None
                    if exc.code in (401, 403):
                        raise PaperError("OpenAlex 拒绝了请求。请检查 API Key。") from None
                    raise PaperError(f"OpenAlex 检索失败（HTTP {exc.code}）。") from None
            except (URLError, TimeoutError, OSError, ValueError):
                raise PaperError("未能读取 OpenAlex 的检索结果，请检查网络后重试。") from None
        raise PaperError("OpenAlex 检索暂时不可用。")

    def search(self, query: str, *, from_year: int | None = None, to_year: int | None = None,
               limit: int = 25, oa_only: bool = False) -> list[Paper]:
        return self.search_page(query, from_year=from_year, to_year=to_year, limit=limit, oa_only=oa_only).papers

    def search_page(self, query: str, *, from_year: int | None = None, to_year: int | None = None,
                    limit: int = 25, page: int = 1, oa_only: bool = False) -> SearchPage:
        max_results = 10_000
        query = validate_search(query, from_year, to_year, limit, page, max_limit=100, max_results=max_results)
        doi = normalize_doi(query)
        if doi:
            work = self._json(f"{OPENALEX_API}/works/https://doi.org/{quote(doi, safe='/')}")
            paper = _paper(work)
            eligible = (paper is not None and (not oa_only or paper.is_oa)
                        and (from_year is None or (paper.year is not None and paper.year >= from_year))
                        and (to_year is None or (paper.year is not None and paper.year <= to_year)))
            return SearchPage([paper] if eligible and page == 1 else [], page, limit, int(eligible), False)
        filters = ["type:article"]
        if from_year is not None:
            filters.append(f"from_publication_date:{from_year:04d}-01-01")
        if to_year is not None:
            filters.append(f"to_publication_date:{to_year:04d}-12-31")
        if oa_only:
            filters.append("open_access.is_oa:true")
        params = urlencode({"search": query, "filter": ",".join(filters), "per_page": limit, "page": page,
                            "select": SEARCH_FIELDS})
        works = self._json(f"{OPENALEX_API}/works?{params}")
        rows = works.get("results") or []
        papers = [paper for work in rows if (paper := _paper(work)) is not None]
        count = (works.get("meta") or {}).get("count")
        total = count if isinstance(count, int) and count >= 0 else None
        more = page * limit < total if total is not None else len(rows) == limit
        return SearchPage(papers, page, limit, total, more and (page + 1) * limit <= max_results)

    def get(self, work_id: str) -> Paper:
        if not WORK_ID.fullmatch(work_id):
            raise ValueError("无效的 OpenAlex 论文 ID。")
        paper = _paper(self._json(f"{OPENALEX_API}/works/{work_id}"))
        if paper is None:
            raise PaperError("OpenAlex 中找不到这篇论文。")
        return paper

    def sources(self, paper: Paper) -> tuple[PdfSource, ...]:
        if self.api_key and paper.cached_pdf:
            return (PdfSource(f"{OPENALEX_CONTENT}/works/{paper.id}.pdf", "openalex"), *paper.pdfs)
        return paper.pdfs

    def fetch_pdf(self, source: PdfSource, destination: Path) -> tuple[str, int]:
        url = source.url
        _public_download_url(url)
        if source.provider == "openalex":
            url += "?" + urlencode({"api_key": self.api_key})
        request = Request(url, headers={"Accept": "application/pdf, application/octet-stream",
                                        "User-Agent": "pdf2jsonl/4"})
        digest = hashlib.sha256()
        size = 0
        try:
            with self._content.open(request, timeout=20) as response, destination.open("wb") as out:
                content_length = response.headers.get("Content-Length", "")
                expected_size = int(content_length) if content_length.isascii() and content_length.isdigit() else None
                if expected_size is not None and expected_size > MAX_PDF_BYTES:
                    raise PaperError("PDF 超过 100 MB 下载上限。")
                for block in iter(lambda: response.read(1 << 16), b""):
                    size += len(block)
                    if size > MAX_PDF_BYTES:
                        raise PaperError("PDF 超过 100 MB 下载上限。")
                    digest.update(block)
                    out.write(block)
                if expected_size is not None and size != expected_size:
                    raise PaperError("全文传输中断，请重试。")
        except HTTPError as exc:
            with exc:
                if exc.code == 429:
                    raise PaperError("全文来源暂时限流，请稍后重试。") from None
                raise PaperError(f"全文来源返回 HTTP {exc.code}。") from None
        except URLError as exc:
            if isinstance(exc.reason, ssl.SSLCertVerificationError):
                raise PaperError("全文来源的 TLS 证书校验失败。") from None
            raise PaperError("无法连接全文来源。") from None
        except (HTTPException, OSError):
            raise PaperError("未能完整读取全文。") from None
        return digest.hexdigest(), size


def _pdf_info(path: Path, *, identify: bool = False) -> tuple[int, str, str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise PaperError("读取 PDF 需要安装项目的 pdf 依赖。") from None
    with path.open("rb") as stream:
        if b"%PDF-" not in stream.read(1024):
            raise PaperError("全文链接返回的内容不是 PDF。")
        stream.seek(0)
        try:
            pdf = PdfReader(stream)
            if pdf.is_encrypted and not pdf.decrypt(""):
                raise PaperError("PDF 需要密码。")
            pages = len(pdf.pages)
            if pages < 1:
                raise PaperError("PDF 没有可读取的页面。")
            if not identify:
                return pages, "", ""
            metadata = pdf.metadata or {}
            title = str(metadata.get("/Title") or "")
            doi = next((value for key, item in metadata.items() if str(key).lower() == "/doi"
                        and (value := normalize_doi(str(item)))), "")
            if not doi:
                try:
                    front = (pdf.pages[0].extract_text() or "")[:3600]
                except Exception:
                    front = ""
                marked = {normalize_doi(match.group()) for match in
                          LABELED_DOI.finditer(str(metadata.get("/Subject") or "") + "\n" + front)}
                marked.discard("")
                doi = marked.pop() if len(marked) == 1 else ""
            return pages, doi, title
        except PaperError:
            raise
        except Exception:
            raise PaperError("PDF 文件无法解析。") from None


@dataclass(frozen=True)
class LocalPdf:
    path: Path
    digest: str
    doi: str
    titles: frozenset[str]
    work_id: str = ""


def same_paper(paper: Paper, copies: tuple[LocalPdf, ...], digest: str = "") -> tuple[LocalPdf, str] | None:
    title = title_key(paper.title)
    for copy in copies:
        if digest and copy.digest == digest:
            return copy, "sha256"
        if paper.id == copy.work_id or (paper.doi and paper.doi == copy.doi):
            return copy, "doi" if paper.doi and paper.doi == copy.doi else paper.provider
    for copy in copies:
        if title and title in copy.titles and (not paper.doi or not copy.doi):
            return copy, "title"
    return None


class PaperLibrary:
    def __init__(self, output: Path, directories: list[Path] | None = None):
        self.output = output.expanduser().resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        additional = [path.expanduser().resolve() for path in directories or []]
        self.directories = tuple(dict.fromkeys([self.output, *additional]))
        for path in self.directories:
            if not path.is_dir():
                raise ValueError(f"文献目录不存在：{path}")
        self._lock = RLock()
        self._cache: dict[Path, tuple[tuple[int, int, int, int], LocalPdf]] = {}

    def _load_copy(self, path: Path) -> LocalPdf:
        digest = sha256_file(path)
        try:
            manifest = json.loads((path.parent / "download.json").read_text(encoding="utf-8"))
            if manifest["sha256"] == digest and manifest["filename"] == path.name:
                return LocalPdf(path, digest, normalize_doi(manifest.get("doi") or ""),
                                frozenset((title_key(manifest.get("title") or ""),)), manifest["id"])
        except (OSError, ValueError, KeyError, TypeError):
            pass
        try:
            _, doi, title = _pdf_info(path, identify=True)
            return LocalPdf(path, digest, doi, frozenset((title_key(title), title_key(path.stem))))
        except PaperError:
            return LocalPdf(path, digest, "", frozenset())

    def refresh(self) -> tuple[LocalPdf, ...]:
        with self._lock:
            updated = {}
            for root in self.directories:
                for directory, folders, filenames in os.walk(root):
                    folders[:] = sorted(name for name in folders if not name.startswith("."))
                    for name in sorted(filenames):
                        if not name.lower().endswith(".pdf"):
                            continue
                        try:
                            path = (Path(directory) / name).resolve()
                            if path in updated or not path.is_relative_to(root):
                                continue
                            stat = path.stat()
                            manifest = path.parent / "download.json"
                            manifest_stat = manifest.stat() if manifest.is_file() else None
                            stamp = (stat.st_mtime_ns, stat.st_size,
                                     manifest_stat.st_mtime_ns if manifest_stat else 0,
                                     manifest_stat.st_size if manifest_stat else 0)
                            cached = self._cache.get(path)
                            updated[path] = cached if cached and cached[0] == stamp else (stamp, self._load_copy(path))
                        except OSError:
                            continue
            self._cache = updated
            return tuple(entry[1] for entry in updated.values())

    def summary(self, copies: tuple[LocalPdf, ...]) -> dict:
        return {"pdf_count": len({copy.digest for copy in copies}), "file_count": len(copies),
                "directories": [str(path) for path in self.directories], "output_dir": str(self.output)}

    def download(self, client: OpenAlex, paper: Paper) -> dict:
        existing = same_paper(paper, self.refresh())
        if existing:
            return {"status": "already_exists", "local": local_details(*existing)}
        sources = client.sources(paper)
        if not sources:
            return {"status": "unavailable", "message": "当前没有可下载的公开 PDF。"}
        errors = []
        with tempfile.TemporaryDirectory(prefix=".download-", dir=self.output) as name:
            stage = Path(name)
            partial = stage / "paper.part"
            for source in sources[:5]:
                try:
                    digest, size = client.fetch_pdf(source, partial)
                    pages, doi, _ = _pdf_info(partial, identify=not paper.doi)
                except PaperError as exc:
                    errors.append(str(exc))
                    continue
                identified = replace(paper, doi=doi) if doi else paper
                return self._store(identified, source, stage, partial, digest, size, pages)
        return {"status": "failed", "message": " ".join(dict.fromkeys(errors))}

    def _store(self, paper: Paper, source: PdfSource, stage: Path, partial: Path,
               digest: str, size: int, pages: int) -> dict:
        # Serialize commits from the web server and standalone CLI sessions sharing this output.
        with self._lock, closing(sqlite3.connect(self.output / ".library-lock", timeout=30)) as lock:
            try:
                lock.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError:
                raise PaperError("无法锁定下载目录，请稍后重试。") from None
            existing = same_paper(paper, self.refresh(), digest)
            if existing:
                return {"status": "already_exists", "local": local_details(*existing)}
            dest = self.output / paper.id
            if not (WORK_ID.fullmatch(paper.id) or SCHOLAR_ID.fullmatch(paper.id)):
                raise PaperError("无效的论文标识。")
            if dest.exists():
                raise PaperError(f"下载目录已存在，请检查其中的文件：{dest}")
            label = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", paper.title).strip()[:92].rstrip(" .")
            filename = f"{paper.id} - {label}.pdf" if label else f"{paper.id}.pdf"
            partial.rename(stage / filename)
            manifest = {"id": paper.id, "doi": paper.doi, "title": paper.title, "year": paper.year,
                        "landing_url": paper.landing_url, "source_url": source.url, "provider": source.provider,
                        "version": source.version, "license": source.license, "filename": filename,
                        "sha256": digest, "bytes": size, "pages": pages,
                        "downloaded_at": datetime.now(timezone.utc).isoformat()}
            (stage / "download.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                                encoding="utf-8")
            stage.rename(dest)
            copy = LocalPdf(dest / filename, digest, paper.doi, frozenset((title_key(paper.title),)), paper.id)
            return {"status": "downloaded", "local": local_details(copy, "download")}


def local_details(copy: LocalPdf, reason: str) -> dict:
    return {"path": str(copy.path), "filename": copy.path.name, "sha256": copy.digest, "match": reason}


def search_library(client: OpenAlex, library: PaperLibrary, query: str, **filters) -> dict:
    return describe_search_page(client, library, query, client.search_page(query, **filters), "openalex")


def describe_search_page(client: OpenAlex, library: PaperLibrary, query: str,
                         page: SearchPage, provider: str) -> dict:
    copies = library.refresh()
    items = []
    seen = set()
    for paper in page.papers:
        key = paper.doi or paper.id
        if key in seen:
            continue
        seen.add(key)
        existing = same_paper(paper, copies)
        items.append({"id": paper.id, "doi": paper.doi, "title": paper.title, "year": paper.year,
                      "authors": paper.authors, "journal": paper.journal, "url": paper.landing_url,
                      "is_oa": paper.is_oa, "can_download": bool(client.sources(paper)),
                      "can_lookup": paper.provider == "google_scholar" and bool(paper.doi),
                      "key_can_help": paper.cached_pdf and not client.api_key,
                      "local": local_details(*existing) if existing else None})
    return {"query": query, "provider": provider, "results": items, "library": library.summary(copies),
            "pagination": {"page": page.number, "limit": page.limit, "total": page.total,
                           "has_previous": page.number > 1, "has_next": page.has_next}}
