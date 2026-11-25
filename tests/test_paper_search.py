from __future__ import annotations

import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Thread
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

import pytest

from pdf2jsonl_skill.paper_commands import PaperServer
from pdf2jsonl_skill.papers import (
    OpenAlex, Paper, PaperError, PaperLibrary, PdfSource, SearchPage, normalize_doi, search_library,
)
from pdf2jsonl_skill.scholar import GoogleScholar

pypdf = pytest.importorskip("pypdf")


def write_pdf(path: Path, title: str, doi: str = "") -> bytes:
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_metadata({"/Title": title, "/DOI": doi})
    writer.write(path)
    return path.read_bytes()


def sample_paper(work_id="W42", doi="10.1234/rice.42", title="Grain yield and heading date in rice"):
    return Paper(work_id, doi, title, 2024, ("J. Li",), "Crop Journal", "https://example.org/article",
                 True, False, (PdfSource("https://example.org/paper.pdf", "open_access_location",
                                          "publishedVersion", "cc-by"),))


class LocalClient(OpenAlex):
    def __init__(self, paper, content, barrier=None):
        super().__init__("")
        self.paper = paper
        self.content = content
        self.barrier = barrier
        self.fetched = 0

    def search_page(self, query, *, page=1, limit=25, **filters):
        return SearchPage([self.paper, self.paper], page, limit, 1, False)

    def get(self, work_id):
        assert work_id == self.paper.id
        return self.paper

    def fetch_pdf(self, source, destination):
        self.fetched += 1
        if self.barrier:
            self.barrier.wait(timeout=5)
        destination.write_bytes(self.content)
        return hashlib.sha256(self.content).hexdigest(), len(self.content)


def test_query_filters_and_exact_doi_lookup(monkeypatch):
    calls = []
    work = {"id": "https://openalex.org/W42", "doi": "https://doi.org/10.1234/Rice.42",
            "title": "Grain yield and heading date in rice", "publication_year": 2024,
            "open_access": {"is_oa": True}, "best_oa_location": {"is_oa": True, "pdf_url": "https://example.org/a.pdf"},
            "locations": [{"is_oa": False, "pdf_url": "https://example.org/b.pdf"}]}
    client = OpenAlex("")

    def fetch(url):
        calls.append(url)
        return {"results": [work]} if "?" in url else work

    monkeypatch.setattr(client, "_json", fetch)
    paper, = client.search("rice & heading date", from_year=2020, to_year=2025, limit=10, oa_only=True)
    params = parse_qs(urlsplit(calls[-1]).query)
    assert params["search"] == ["rice & heading date"]
    assert params["filter"] == ["type:article,from_publication_date:2020-01-01,to_publication_date:2025-12-31,"
                                "open_access.is_oa:true"]
    assert [source.url for source in client.sources(paper)] == ["https://example.org/a.pdf"]
    assert client.search("doi:10.1234/RICE.42") == [paper]
    assert calls[-1].endswith("/works/https://doi.org/10.1234/rice.42")
    assert client.search("https://doi.org/10.1234/RICE.42", from_year=2025) == []
    assert normalize_doi("https://doi.org/10.1234/abc%28x%29.") == "10.1234/abc(x)"


def test_openalex_paging_fetches_upstream_page_and_respects_limit(monkeypatch, tmp_path):
    calls = []
    client = OpenAlex("")

    def fetch(url):
        calls.append(parse_qs(urlsplit(url).query))
        work = {"id": "https://openalex.org/W" + calls[-1]["page"][0], "title": "Rice yield"}
        return {"results": [work], "meta": {"count": 10_400}}

    monkeypatch.setattr(client, "_json", fetch)
    library = PaperLibrary(tmp_path / "papers")
    second = search_library(client, library, "rice yield", page=2, limit=20, from_year=2020)
    assert second["results"][0]["id"] == "W2"
    assert second["pagination"] == {"page": 2, "limit": 20, "total": 10400,
                                    "has_previous": True, "has_next": True}
    assert calls[-1]["page"] == ["2"] and calls[-1]["per_page"] == ["20"]
    assert "from_publication_date:2020-01-01" in calls[-1]["filter"][0]
    assert not client.search_page("rice yield", page=500, limit=20).has_next
    with pytest.raises(ValueError, match="页码"):
        client.search_page("rice yield", page=501, limit=20)


def test_scholar_provider_paginates_and_filters_pdf_resources(monkeypatch):
    client = GoogleScholar("test-key")
    calls = []
    existing = {"title": "Rice yield and drought", "result_id": "example-1",
                "link": "https://link.springer.com/article/10.1234/rice.1",
                "publication_info": {"summary": "J Li - Crop Journal, 2024 - Springer",
                                     "authors": [{"name": "J Li"}]}}
    downloadable = {"title": "Seed yield and protein", "result_id": "example-2",
                    "resources": [{"file_format": "HTML", "link": "https://example.org/article"},
                                  {"file_format": "PDF", "link": "http://example.org/paper.pdf"}]}

    def fetch(params):
        calls.append(params)
        return {"organic_results": [existing, downloadable],
                "search_information": {"total_results": 72},
                "serpapi_pagination": {"next": "https://serpapi.com/search.json?start=20"}}

    monkeypatch.setattr(client, "_json", fetch)
    page = client.search_page("rice drought", page=2, limit=10, from_year=2019, to_year=2025)
    assert calls[-1] == {"engine": "google_scholar", "q": "rice drought", "hl": "en",
                         "start": 10, "num": 10, "as_ylo": 2019, "as_yhi": 2025}
    assert page.number == 2 and page.total == 72 and page.has_next
    assert (page.papers[0].doi, page.papers[0].year, page.papers[0].journal) == ("10.1234/rice.1", 2024, "Crop Journal")
    assert page.papers[1].pdfs == (PdfSource("https://example.org/paper.pdf", "google_scholar"),)
    filtered = client.search_page("rice drought", page=2, limit=10, oa_only=True)
    assert filtered.papers == page.papers[1:] and filtered.total is None and filtered.has_next
    with pytest.raises(PaperError, match="SERPAPI_API_KEY"):
        GoogleScholar("").search_page("rice drought")


def test_preexisting_doi_and_title_prevent_new_download(tmp_path):
    existing = tmp_path / "existing"
    existing.mkdir()
    paper = sample_paper()
    write_pdf(existing / "renamed.pdf", "Publisher title variant", "https://doi.org/10.1234/RICE.42")
    write_pdf(existing / "Soybean seed oil protein content.pdf", "")
    library = PaperLibrary(tmp_path / "downloads", [existing])
    client = LocalClient(paper, b"")
    items = search_library(client, library, "rice")["results"]
    assert len(items) == 1
    assert items[0]["local"]["filename"] == "renamed.pdf"
    assert library.download(client, paper)["local"]["match"] == "doi"
    no_doi = sample_paper("W43", "", "Soybean seed oil/protein content")
    assert library.download(client, no_doi)["local"]["match"] == "title"
    assert client.fetched == 0
    assert not list(library.output.iterdir())


def test_byte_identical_pdf_is_reused_after_download(tmp_path):
    old_directory = tmp_path / "old"
    old_directory.mkdir()
    source = write_pdf(old_directory / "unknown.pdf", "Unrelated local metadata")
    library = PaperLibrary(tmp_path / "downloads", [old_directory])
    paper = sample_paper()
    client = LocalClient(paper, source)
    result = library.download(client, paper)
    assert result["status"] == "already_exists"
    assert result["local"]["match"] == "sha256"
    assert result["local"]["filename"] == "unknown.pdf"
    assert not list(library.output.glob("**/*.pdf"))


def test_concurrent_download_commits_one_copy_and_reopens_manifest(tmp_path):
    content = write_pdf(tmp_path / "fixture.pdf", "Publisher metadata")
    paper = sample_paper(title="Rice: yield & QTL / progress")
    output = tmp_path / "downloads"
    libraries = [PaperLibrary(output), PaperLibrary(output)]
    client = LocalClient(paper, content, Barrier(2))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda library: library.download(client, paper), libraries))
    assert sorted(item["status"] for item in results) == ["already_exists", "downloaded"]
    saved, = output.glob("**/*.pdf")
    assert saved.read_bytes() == content
    manifest = json.loads((saved.parent / "download.json").read_text(encoding="utf-8"))
    assert manifest["sha256"] == hashlib.sha256(content).hexdigest()
    assert manifest["license"] == "cc-by"
    assert PaperLibrary(output).download(client, paper)["status"] == "already_exists"
    assert client.fetched == 2


def test_invalid_pdf_has_no_published_file(tmp_path):
    paper = sample_paper()
    library = PaperLibrary(tmp_path / "downloads")
    client = LocalClient(paper, b"<html>please sign in</html>")
    result = library.download(client, paper)
    assert result["status"] == "failed"
    assert not list(library.output.iterdir())


def test_truncated_transfer_is_rejected(monkeypatch, tmp_path):
    response = io.BytesIO(b"%PDF-1.7")
    response.headers = {"Content-Length": "100"}
    client = OpenAlex("")
    monkeypatch.setattr("pdf2jsonl_skill.papers._public_download_url", lambda url: None)
    monkeypatch.setattr(client._content, "open", lambda request, timeout: response)
    with pytest.raises(PaperError, match="传输中断"):
        client.fetch_pdf(PdfSource("https://example.org/paper.pdf", "open_access_location"), tmp_path / "test.part")


def test_local_ui_search_download_open_and_repeat(tmp_path):
    content = write_pdf(tmp_path / "fixture.pdf", "Rice yield")
    paper = sample_paper()
    library = PaperLibrary(tmp_path / "downloads")
    client = LocalClient(paper, content)
    with PaperServer(0, client, library) as server:
        base = f"http://127.0.0.1:{server.server_port}"
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(base, timeout=4) as response:
                assert "论文检索" in response.read().decode()
            with urlopen(base + "/api/search?q=rice", timeout=4) as response:
                assert json.load(response)["results"][0]["can_download"] is True
            request = Request(base + "/api/download", data=json.dumps({"id": paper.id}).encode(),
                              headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=4) as response:
                result = json.load(response)
            assert result["status"] == "downloaded"
            with urlopen(base + "/api/pdf/" + result["local"]["sha256"], timeout=4) as response:
                assert response.headers["Content-Type"] == "application/pdf"
                assert response.read() == content
            with urlopen(request, timeout=4) as response:
                assert json.load(response)["status"] == "already_exists"
            request.add_header("Origin", "https://example.org")
            with pytest.raises(HTTPError) as exc:
                urlopen(request, timeout=4)
            assert exc.value.code == 403
            cross_site = Request(base + "/api/search?q=rice", headers={"Sec-Fetch-Site": "cross-site"})
            with pytest.raises(HTTPError) as exc:
                urlopen(cross_site, timeout=4)
            assert exc.value.code == 403
            assert client.fetched == 1
        finally:
            server.shutdown()
            thread.join()


def test_scholar_download_uses_shared_library_and_doi_fallback(tmp_path, monkeypatch):
    paper = sample_paper()
    content = write_pdf(tmp_path / "fixture.pdf", "Publisher PDF")
    library = PaperLibrary(tmp_path / "downloads")
    client = LocalClient(paper, content)
    scholar = GoogleScholar("test-only-secret")
    raw = {"title": paper.title, "result_id": "scholar-rice-qtl",
           "link": f"https://doi.org/{paper.doi}"}
    monkeypatch.setattr(scholar, "_json", lambda params: {"organic_results": [raw]})
    with PaperServer(0, client, library, scholar) as server:
        base = f"http://127.0.0.1:{server.server_port}"
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(base + "/api/library", timeout=4) as response:
                assert json.load(response)["scholar_configured"] is True
            url = base + "/api/search?provider=google_scholar&q=rice+yield&page=2"
            with urlopen(url, timeout=4) as response:
                payload = response.read().decode()
            assert "test-only-secret" not in payload
            data = json.loads(payload)
            entry, = data["results"]
            assert data["provider"] == "google_scholar" and data["pagination"]["page"] == 2
            assert entry["can_lookup"] is True and entry["can_download"] is False
            request = Request(base + "/api/download", data=json.dumps({"id": entry["id"]}).encode(),
                              headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=4) as response:
                assert json.load(response)["status"] == "downloaded"
            with urlopen(request, timeout=4) as response:
                assert json.load(response)["status"] == "already_exists"
            assert len(list(library.output.glob("**/*.pdf"))) == client.fetched == 1
        finally:
            server.shutdown()
            thread.join()
