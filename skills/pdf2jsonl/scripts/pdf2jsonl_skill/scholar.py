"""Google Scholar search through the SerpApi JSON endpoint."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

from .papers import Paper, PaperError, PdfSource, SearchPage, _https_host, normalize_doi, validate_search

SERPAPI_SEARCH = "https://serpapi.com/search.json"
SCHOLAR_SEARCH = "https://scholar.google.com/scholar"
_YEAR = re.compile(r"\b(?:18[0-9]{2}|19[0-9]{2}|20[0-9]{2}|2100)\b")
_DOI_PATH = re.compile(r"(?:^|/)(10\.\d{4,9}/[^/]+?)(?:/(?:abstract|full|pdf|html))?/?$",
                       re.IGNORECASE)


def _as_https(url: str) -> str:
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    return url if _https_host(url) else ""


def _doi_in_link(url: str) -> str:
    if not url:
        return ""
    parsed = urlsplit(url)
    if parsed.hostname in ("doi.org", "dx.doi.org"):
        return normalize_doi(parsed.path.lstrip("/"))
    params = parse_qs(parsed.query)
    for key in ("doi", "id"):
        for value in params.get(key, []):
            if doi := normalize_doi(value):
                return doi
    match = _DOI_PATH.search(unquote(parsed.path))
    return normalize_doi(match[1].removesuffix(".pdf")) if match else ""


def _paper(result: dict) -> Paper | None:
    title = html.unescape(str(result.get("title") or "")).strip()
    if not title:
        return None
    landing = _as_https(str(result.get("link") or ""))
    pdfs = {}
    for resource in result.get("resources") or []:
        url = _as_https(str(resource.get("link") or ""))
        if url and str(resource.get("file_format") or "").upper().strip("[]") == "PDF":
            pdfs.setdefault(url, PdfSource(url, "google_scholar"))
    if landing and urlsplit(landing).path.lower().endswith(".pdf"):
        pdfs.setdefault(landing, PdfSource(landing, "google_scholar"))
    doi = normalize_doi(str(result.get("doi") or "")) or next(
        (doi for url in (landing, *pdfs) if (doi := _doi_in_link(url))), "")

    info = result.get("publication_info") or {}
    summary = html.unescape(str(info.get("summary") or ""))
    parts = summary.split(" - ")
    publication = " - ".join(parts[1:-1]).strip() if len(parts) >= 3 else ""
    year_matches = _YEAR.findall(publication or summary)
    year = int(year_matches[-1]) if year_matches else None
    journal = re.sub(r"(?:,\s*)?" + _YEAR.pattern + r"\s*$", "", publication).strip(" ,")
    authors = tuple(html.unescape(str(author["name"])) for author in info.get("authors") or []
                    if author.get("name"))

    versions = (result.get("inline_links") or {}).get("versions") or {}
    external_id = versions.get("cluster_id") or result.get("result_id") or doi or f"{title}|{landing}"
    work_id = "GS-" + hashlib.sha256(str(external_id).encode("utf-8")).hexdigest()[:32]
    if not landing:
        landing = SCHOLAR_SEARCH + "?" + urlencode({"q": f'"{title}"'})
    return Paper(work_id, doi, title, year, authors, journal, landing, False, False, tuple(pdfs.values()),
                 "google_scholar")


class GoogleScholar:
    def __init__(self, api_key: str | None = None):
        self.api_key = (api_key if api_key is not None else os.environ.get("SERPAPI_API_KEY", "")).strip()

    def _json(self, params: dict) -> dict:
        request = Request(SERPAPI_SEARCH + "?" + urlencode({**params, "api_key": self.api_key}),
                          headers={"Accept": "application/json", "User-Agent": "pdf2jsonl/4"})
        try:
            with urlopen(request, timeout=25) as response:
                data = json.load(response)
        except HTTPError as exc:
            with exc:
                if exc.code in (401, 403):
                    raise PaperError("SerpApi 拒绝了请求，请检查 SERPAPI_API_KEY。") from None
                if exc.code == 429:
                    raise PaperError("SerpApi 暂时达到限额，请检查账户额度后重试。") from None
                raise PaperError(f"Google 学术检索失败（HTTP {exc.code}）。") from None
        except (URLError, OSError, ValueError):
            raise PaperError("未能读取 Google 学术的结果，请检查 SerpApi 网络连接后重试。") from None
        if not isinstance(data, dict):
            raise PaperError("Google 学术返回的数据格式无效。")
        error = str(data.get("error") or "")
        if error and "hasn't returned any results" not in error.casefold():
            raise PaperError("SerpApi 未能返回 Google 学术结果，请检查账户或稍后重试。")
        return data

    def search_page(self, query: str, *, from_year: int | None = None, to_year: int | None = None,
                    limit: int = 10, page: int = 1, oa_only: bool = False) -> SearchPage:
        max_results = 1_000
        query = validate_search(query, from_year, to_year, limit, page, max_limit=20, max_results=max_results)
        if not self.api_key:
            raise PaperError("Google 学术的应用内检索需要 SERPAPI_API_KEY，也可以直接打开 Google 学术查询。")
        params = {"engine": "google_scholar", "q": normalize_doi(query) or query, "hl": "en",
                  "start": (page - 1) * limit, "num": limit}
        if from_year is not None:
            params["as_ylo"] = from_year
        if to_year is not None:
            params["as_yhi"] = to_year
        data = self._json(params)
        papers = [paper for row in data.get("organic_results") or [] if (paper := _paper(row)) is not None]
        more = bool((data.get("serpapi_pagination") or {}).get("next") or
                    (data.get("pagination") or {}).get("next"))
        count = (data.get("search_information") or {}).get("total_results")
        total = count if isinstance(count, int) and count >= 0 and not oa_only else None
        if oa_only:
            papers = [paper for paper in papers if paper.pdfs]
        return SearchPage(papers, page, limit, total, more and (page + 1) * limit <= max_results)
