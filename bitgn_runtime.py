import builtins
import os
from typing import List

from pydantic import BaseModel, Field

from bitgn_sdk.vm.mini_connect import MiniRuntimeClientSync
from bitgn_sdk.vm.mini_pb2 import (
    AnswerRequest,
    DeleteRequest,
    ListRequest,
    OutlineRequest,
    ReadRequest,
    SearchRequest,
    WriteRequest,
)


class OutlineFile(BaseModel):
    path: str
    headers: list[str] = Field(default_factory=list)


class OutlineResult(BaseModel):
    path: str
    folders: list[str] = Field(default_factory=list)
    files: list[OutlineFile] = Field(default_factory=list)


class ReadResult(BaseModel):
    path: str
    content: str


class ListResult(BaseModel):
    folders: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)


class SearchSnippet(BaseModel):
    file: str
    match: str
    line: int


class SearchResult(BaseModel):
    snippets: list[SearchSnippet] = Field(default_factory=list)


class WriteResult(BaseModel):
    path: str
    bytes_written: int


class DeleteResult(BaseModel):
    path: str
    deleted: bool = True


class AnswerResult(BaseModel):
    answer: str
    refs: list[str] = Field(default_factory=list)
    submitted: bool = True


_client: MiniRuntimeClientSync | None = None
_harness_url: str | None = None


def _normalize_request_path(path: str | None) -> str:
    if not path or path == "/":
        return "/"
    normalized = path.strip()
    if not normalized:
        return "/"
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    if normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    return normalized or "/"


def _normalize_runtime_path(path: str | None) -> str:
    if not path or path == "/":
        return "/"
    normalized = path.strip()
    if not normalized:
        return "/"
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    if normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    return normalized or "/"


def _join_child_path(parent: str, child: str) -> str:
    child_path = child.strip()
    if child_path.startswith("/"):
        return _normalize_runtime_path(child_path)
    base = _normalize_runtime_path(parent)
    if base == "/":
        return _normalize_runtime_path(child_path)
    return _normalize_runtime_path(f"{base}/{child_path}")


def configure(harness_url: str | None = None) -> str:
    global _client, _harness_url

    chosen_url = harness_url or os.getenv("BITGN_HARNESS_URL")
    if not chosen_url:
        raise RuntimeError(
            "BitGN runtime is not configured. Set BITGN_HARNESS_URL or pass "
            "--task-id to run_bitgn_task.py."
        )

    _client = MiniRuntimeClientSync(chosen_url)
    _harness_url = chosen_url
    return chosen_url


def is_configured() -> bool:
    return _client is not None or bool(os.getenv("BITGN_HARNESS_URL"))


def current_harness_url() -> str | None:
    return _harness_url or os.getenv("BITGN_HARNESS_URL")


def _runtime() -> MiniRuntimeClientSync:
    if _client is None:
        configure()
    assert _client is not None
    return _client


def outline(path: str = "/") -> OutlineResult:
    normalized_path = _normalize_request_path(path)
    response = _runtime().outline(OutlineRequest(path=normalized_path))
    return OutlineResult(
        path=_normalize_runtime_path(response.path),
        folders=[_join_child_path(response.path, item) for item in builtins.list(response.folders)],
        files=[
            OutlineFile(
                path=_join_child_path(response.path, item.path),
                headers=builtins.list(item.headers),
            )
            for item in response.files
        ],
    )


def tree(path: str = "/") -> str:
    def _walk(current_path: str, depth: int) -> builtins.list[str]:
        result = outline(current_path)
        lines: builtins.list[str] = []
        indent = "  " * depth

        for folder in sorted(result.folders):
            lines.append(f"{indent}{folder}/")
            lines.extend(_walk(folder, depth + 1))

        for item in sorted(result.files, key=lambda file: file.path):
            headers = ", ".join(item.headers[:3])
            if len(item.headers) > 3:
                headers += ", ..."
            if headers:
                lines.append(f"{indent}{item.path} [{headers}]")
            else:
                lines.append(f"{indent}{item.path}")

        return lines

    normalized_path = _normalize_request_path(path)
    root_label = normalized_path if normalized_path != "/" else "/"
    body = _walk(normalized_path, 1)
    if not body:
        return root_label
    return "\n".join([root_label, *body])


def search(pattern: str, path: str = "/", count: int = 5) -> SearchResult:
    normalized_path = _normalize_request_path(path)
    response = _runtime().search(SearchRequest(path=normalized_path, pattern=pattern, count=count))
    return SearchResult(
        snippets=[
            SearchSnippet(file=_join_child_path(normalized_path, item.file), match=item.match, line=item.line)
            for item in response.snippets
        ]
    )


def list(path: str = "/") -> ListResult:
    normalized_path = _normalize_request_path(path)
    response = _runtime().list(ListRequest(path=normalized_path))
    return ListResult(
        folders=[_join_child_path(normalized_path, item) for item in builtins.list(response.folders)],
        files=[_join_child_path(normalized_path, item) for item in builtins.list(response.files)],
    )


def read(path: str) -> ReadResult:
    normalized_path = _normalize_request_path(path)
    response = _runtime().read(ReadRequest(path=normalized_path))
    return ReadResult(path=_normalize_runtime_path(response.path), content=response.content)


def write(path: str, content: str) -> WriteResult:
    normalized_path = _normalize_request_path(path)
    _runtime().write(WriteRequest(path=normalized_path, content=content))
    return WriteResult(path=_normalize_runtime_path(normalized_path), bytes_written=len(content.encode("utf-8")))


def delete(path: str) -> DeleteResult:
    normalized_path = _normalize_request_path(path)
    _runtime().delete(DeleteRequest(path=normalized_path))
    return DeleteResult(path=_normalize_runtime_path(normalized_path))


def answer(answer: str, refs: List[str] | None = None) -> AnswerResult:
    final_refs = []
    for ref in refs or []:
        cleaned = (ref or "").strip()
        if cleaned and cleaned not in final_refs:
            final_refs.append(cleaned)
    _runtime().answer(AnswerRequest(answer=answer, refs=final_refs))
    return AnswerResult(answer=answer, refs=final_refs)
