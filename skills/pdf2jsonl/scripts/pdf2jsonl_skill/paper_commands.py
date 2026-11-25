"""CLI and loopback-only interface for searching and downloading papers."""
from __future__ import annotations

import json
import logging
import re
import shutil
import sys
from collections import OrderedDict
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, quote, urlsplit

from .papers import SCHOLAR_ID, OpenAlex, Paper, PaperError, PaperLibrary, describe_search_page, search_library
from .scholar import GoogleScholar


class PaperServer(ThreadingHTTPServer):
    def __init__(self, port: int, client: OpenAlex, library: PaperLibrary, scholar: GoogleScholar | None = None):
        if not 0 <= port <= 65535:
            raise ValueError("端口应在 0 至 65535 之间。")
        self.client = client
        self.library = library
        self.scholar = scholar if scholar is not None else GoogleScholar()
        self._scholar_results: OrderedDict[str, Paper] = OrderedDict()
        self._scholar_lock = Lock()
        self.page = files(__package__).joinpath("paper_search.html").read_bytes()
        super().__init__(("127.0.0.1", port), PaperRequest)

    def search(self, provider: str, query: str, **filters) -> dict:
        if provider == "openalex":
            return search_library(self.client, self.library, query, **filters)
        if provider != "google_scholar":
            raise ValueError("请选择 OpenAlex 或 Google 学术。")
        page = self.scholar.search_page(query, **filters)
        with self._scholar_lock:
            for paper in page.papers:
                self._scholar_results[paper.id] = paper
                self._scholar_results.move_to_end(paper.id)
            while len(self._scholar_results) > 1000:
                self._scholar_results.popitem(last=False)
        return describe_search_page(self.client, self.library, query, page, provider)

    def download(self, work_id: str) -> dict:
        if not SCHOLAR_ID.fullmatch(work_id):
            return self.library.download(self.client, self.client.get(work_id))
        with self._scholar_lock:
            paper = self._scholar_results.get(work_id)
        if paper is None:
            raise ValueError("请重新搜索这篇 Google 学术的论文，再发起下载。")

        result = self.library.download(self.client, paper)
        if not paper.doi or result["status"] in ("downloaded", "already_exists"):
            return result
        try:
            alternatives = self.client.search(paper.doi, limit=1)
        except PaperError:
            if result["status"] == "unavailable":
                return {"status": "failed", "message": "暂时无法按 DOI 查找开放全文，请稍后重试。"}
            return result
        if not alternatives:
            return result
        tried = {source.url for source in paper.pdfs[:5]}
        alternative = alternatives[0]
        alternative = replace(alternative, pdfs=tuple(source for source in alternative.pdfs if source.url not in tried))
        fallback = self.library.download(self.client, alternative)
        return result if fallback["status"] == "unavailable" and result["status"] == "failed" else fallback


class PaperRequest(BaseHTTPRequestHandler):
    server: PaperServer

    def _start(self, status: int, content_type: str, size: int, **headers) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for header, value in headers.items():
            self.send_header(header, value)
        self.end_headers()

    def _json(self, status: int, result: dict) -> None:
        payload = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self._start(status, "application/json; charset=utf-8", len(payload))
        self.wfile.write(payload)

    def _local_request(self) -> bool:
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host", "").lower()
        origin = self.headers.get("Origin")
        cross_origin = self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site")
        if host not in hosts or (origin and origin != f"http://{host}") or (cross_origin and self.path.startswith("/api/")):
            self._json(403, {"error": "请从本地论文检索页面发起请求。"})
            return False
        return True

    def _open_pdf(self, digest: str) -> None:
        if re.fullmatch(r"[0-9a-f]{64}", digest):
            for copy in self.server.library.refresh():
                if copy.digest == digest:
                    with copy.path.open("rb") as stream:
                        self._start(200, "application/pdf", copy.path.stat().st_size,
                                    **{"Content-Disposition": "inline; filename*=UTF-8''" +
                                       quote(copy.path.name, safe="")})
                        shutil.copyfileobj(stream, self.wfile, length=1 << 20)
                    return
        self._json(404, {"error": "本地文献库中找不到这个 PDF。"})

    def do_GET(self) -> None:
        if not self._local_request():
            return
        url = urlsplit(self.path)
        library = self.server.library
        client = self.server.client
        try:
            if url.path == "/":
                self._start(200, "text/html; charset=utf-8", len(self.server.page),
                            **{"Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                               "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                               "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})
                self.wfile.write(self.server.page)
            elif url.path == "/api/library":
                result = library.summary(library.refresh())
                self._json(200, {**result, "key_configured": bool(client.api_key),
                                 "scholar_configured": bool(self.server.scholar.api_key)})
            elif url.path == "/api/search":
                params = {key: values[-1] for key, values in parse_qs(url.query).items()}
                provider = params.get("provider", "openalex")
                result = self.server.search(provider, params.get("q", ""),
                                            from_year=int(params["from_year"]) if "from_year" in params else None,
                                            to_year=int(params["to_year"]) if "to_year" in params else None,
                                            limit=int(params.get("limit", "10" if provider == "google_scholar" else "25")),
                                            page=int(params.get("page", "1")), oa_only=params.get("oa_only") == "true")
                self._json(200, result)
            elif url.path.startswith("/api/pdf/"):
                self._open_pdf(url.path.rsplit("/", 1)[-1])
            else:
                self._json(404, {"error": "页面不存在。"})
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except PaperError as exc:
            self._json(502, {"error": str(exc)})

    def do_POST(self) -> None:
        if not self._local_request():
            return
        if self.path != "/api/download":
            self._json(404, {"error": "页面不存在。"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if self.headers.get_content_type() != "application/json" or not 1 <= length <= 4096:
                raise ValueError("下载请求需要提供论文 ID。")
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict) or not isinstance(request.get("id"), str):
                raise ValueError("下载请求需要提供论文 ID。")
            self._json(200, self.server.download(request["id"]))
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except PaperError as exc:
            self._json(502, {"error": str(exc)})
        except OSError:
            self._json(500, {"error": "无法写入本地下载目录。"})

    def log_message(self, format: str, *args) -> None:
        return


def _print_or_save(data, output: Path | None = None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if output is None:
        print(text, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(output)


def _selected_ids(args) -> list[str]:
    if args.id:
        if args.select:
            raise ValueError("--select 需要与 --from 一起使用。")
        return list(dict.fromkeys(args.id))
    if not args.select:
        raise ValueError("--from 需要 --select 指定结果序号，例如 1,3。")
    try:
        results = json.loads(args.results_file.read_text(encoding="utf-8-sig"))["results"]
        positions = [int(value) for value in args.select.split(",")]
        if not all(1 <= number <= len(results) for number in positions):
            raise ValueError
        work_ids = [results[number - 1]["id"] for number in positions]
        if not all(isinstance(work_id, str) for work_id in work_ids):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ValueError("搜索结果文件或所选序号无效。") from None
    return list(dict.fromkeys(work_ids))


def run_papers(args) -> int:
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    try:
        client = OpenAlex()
        library = PaperLibrary(args.out_dir, args.library_dir)
        if args.paper_action == "serve":
            with PaperServer(args.port, client, library) as server:
                print(f"http://127.0.0.1:{server.server_port}/", flush=True)
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
            return 0
        if args.paper_action == "search":
            result = search_library(client, library, args.query, from_year=args.from_year,
                                    to_year=args.to_year, limit=args.limit, page=args.page, oa_only=args.oa_only)
            _print_or_save(result, args.out)
            return 0
        results = []
        for work_id in _selected_ids(args):
            try:
                result = library.download(client, client.get(work_id))
            except (ValueError, OSError, PaperError) as exc:
                result = {"status": "failed", "message": str(exc)}
            results.append({"id": work_id, **result})
        _print_or_save(results)
        return int(any(item["status"] in ("failed", "unavailable") for item in results))
    except (ValueError, OSError, PaperError) as exc:
        print(f"pdf2jsonl papers: {exc}", file=sys.stderr)
        return 1


def add_paper_commands(parser) -> None:
    actions = parser.add_subparsers(dest="paper_action", required=True)
    serve = actions.add_parser("serve", help="serve the local paper search page")
    serve.add_argument("--port", type=int, default=8765)

    search = actions.add_parser("search", help="search OpenAlex by keywords, title or DOI")
    search.add_argument("query")
    search.add_argument("--from-year", type=int)
    search.add_argument("--to-year", type=int)
    search.add_argument("--limit", type=int, default=25, help="results per page")
    search.add_argument("--page", type=int, default=1)
    search.add_argument("--oa-only", action="store_true")
    search.add_argument("--out", type=Path, help="save the ranked results as JSON")

    download = actions.add_parser("download", help="download selected open-access PDFs")
    inputs = download.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--id", action="append", help="OpenAlex work ID, repeatable")
    inputs.add_argument("--from", dest="results_file", type=Path, help="saved search results")
    download.add_argument("--select", help="comma-separated result positions, starting at 1")

    for action in (serve, search, download):
        action.add_argument("--out-dir", type=Path, default=Path("out/papers"), help="PDF download directory")
        action.add_argument("--library-dir", type=Path, action="append", default=[],
                            help="existing PDF directory to check for duplicates, repeatable")
        action.set_defaults(fn=run_papers)
