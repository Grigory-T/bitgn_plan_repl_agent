import builtins
import os
from typing import Literal

from pydantic import BaseModel, Field

from bitgn_sdk.vm.pcm_connect import PcmRuntimeClientSync
from bitgn_sdk.vm.pcm_pb2 import (
    AnswerRequest,
    ContextRequest,
    DeleteRequest,
    FindRequest,
    ListRequest,
    MkDirRequest,
    MoveRequest,
    Outcome,
    ReadRequest,
    SearchRequest,
    TreeRequest,
    WriteRequest,
)


OutcomeName = Literal[
    "OUTCOME_OK",
    "OUTCOME_DENIED_SECURITY",
    "OUTCOME_NONE_CLARIFICATION",
    "OUTCOME_NONE_UNSUPPORTED",
    "OUTCOME_ERR_INTERNAL",
]


class ContextResult(BaseModel):
    unix_time: int
    time: str


class TreeNode(BaseModel):
    name: str
    is_dir: bool
    children: list["TreeNode"] = Field(default_factory=list)


class TreeResult(BaseModel):
    root: TreeNode


class FindResult(BaseModel):
    items: list[str] = Field(default_factory=list)


class ReadResult(BaseModel):
    path: str
    content: str


class ListEntry(BaseModel):
    name: str
    path: str
    is_dir: bool


class ListResult(BaseModel):
    entries: list[ListEntry] = Field(default_factory=list)


class SearchSnippet(BaseModel):
    path: str
    line: int
    line_text: str


class SearchResult(BaseModel):
    matches: list[SearchSnippet] = Field(default_factory=list)


class WriteResult(BaseModel):
    path: str
    bytes_written: int
    start_line: int = 0
    end_line: int = 0


class DeleteResult(BaseModel):
    path: str
    deleted: bool = True


class MkDirResult(BaseModel):
    path: str
    created: bool = True


class MoveResult(BaseModel):
    from_name: str
    to_name: str
    moved: bool = True


class AnswerResult(BaseModel):
    message: str
    outcome: OutcomeName
    refs: list[str] = Field(default_factory=list)
    submitted: bool = True


TreeNode.model_rebuild()


_OUTCOME_BY_NAME = {
    "OUTCOME_OK": Outcome.OUTCOME_OK,
    "OUTCOME_DENIED_SECURITY": Outcome.OUTCOME_DENIED_SECURITY,
    "OUTCOME_NONE_CLARIFICATION": Outcome.OUTCOME_NONE_CLARIFICATION,
    "OUTCOME_NONE_UNSUPPORTED": Outcome.OUTCOME_NONE_UNSUPPORTED,
    "OUTCOME_ERR_INTERNAL": Outcome.OUTCOME_ERR_INTERNAL,
}


_client: PcmRuntimeClientSync | None = None
_harness_url: str | None = None


def reset() -> None:
    global _client, _harness_url
    _client = None
    _harness_url = None


def _normalize_request_path(path: str | None, *, root_empty: bool = False) -> str:
    if not path or path == "/":
        return "" if root_empty else "/"
    normalized = path.strip()
    if not normalized:
        return "" if root_empty else "/"
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    if normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    if not normalized:
        return "" if root_empty else "/"
    return normalized


def _normalize_runtime_path(path: str | None) -> str:
    if not path:
        return "/"
    normalized = path.strip()
    if not normalized or normalized == "/":
        return "/"
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    if normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    return normalized or "/"


def configure(harness_url: str | None = None) -> str:
    global _client, _harness_url

    chosen_url = harness_url or os.getenv("BITGN_HARNESS_URL")
    if not chosen_url:
        raise RuntimeError(
            "BitGN runtime is not configured. Set BITGN_HARNESS_URL or pass "
            "--task-id to run_bitgn_task.py."
        )

    _client = PcmRuntimeClientSync(chosen_url)
    _harness_url = chosen_url
    return chosen_url


def is_configured() -> bool:
    return _client is not None or bool(os.getenv("BITGN_HARNESS_URL"))


def current_harness_url() -> str | None:
    return _harness_url or os.getenv("BITGN_HARNESS_URL")


def _runtime() -> PcmRuntimeClientSync:
    if _client is None:
        configure()
    assert _client is not None
    return _client


def context() -> ContextResult:
    response = _runtime().context(ContextRequest())
    return ContextResult(unix_time=response.unix_time, time=response.time)


def _tree_node_from_proto(entry) -> TreeNode:
    return TreeNode(
        name=entry.name,
        is_dir=entry.is_dir,
        children=[_tree_node_from_proto(child) for child in entry.children],
    )


def tree_data(path: str = "/", level: int = 0) -> TreeResult:
    response = _runtime().tree(
        TreeRequest(
            root=_normalize_request_path(path, root_empty=True),
            level=level,
        )
    )
    return TreeResult(root=_tree_node_from_proto(response.root))


def tree(path: str = "/", level: int = 0) -> str:
    result = tree_data(path=path, level=level)
    root_label = _normalize_runtime_path(path)

    if result.root.name and not result.root.is_dir and not result.root.children:
        return root_label

    def _walk(node: TreeNode, depth: int) -> builtins.list[str]:
        lines: builtins.list[str] = []
        indent = "  " * depth
        for child in sorted(node.children, key=lambda item: (not item.is_dir, item.name)):
            label = child.name + "/" if child.is_dir else child.name
            lines.append(f"{indent}{label}")
            if child.children:
                lines.extend(_walk(child, depth + 1))
        return lines

    body = _walk(result.root, 1)
    if not body:
        return root_label
    return "\n".join([root_label, *body])


def _count_lines(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def tree_with_line_counts(path: str = "/", level: int = 0) -> str:
    result = tree_data(path=path, level=level)
    root_label = _normalize_runtime_path(path)

    if result.root.name and not result.root.is_dir and not result.root.children:
        try:
            file_text = read(root_label).content
            return f"{root_label} [{_count_lines(file_text)}]"
        except Exception:
            return root_label

    def _join_child_path(parent_path: str, child_name: str) -> str:
        if parent_path == "/":
            return _normalize_runtime_path(child_name)
        return _normalize_runtime_path(f"{parent_path}/{child_name}")

    def _walk(node: TreeNode, parent_path: str, depth: int) -> builtins.list[str]:
        lines: builtins.list[str] = []
        indent = "  " * depth
        for child in sorted(node.children, key=lambda item: (not item.is_dir, item.name)):
            child_path = _join_child_path(parent_path, child.name)
            if child.is_dir:
                lines.append(f"{indent}{child.name}/")
            else:
                try:
                    line_count = _count_lines(read(child_path).content)
                    lines.append(f"{indent}{child.name} [{line_count}]")
                except Exception:
                    lines.append(f"{indent}{child.name}")
            if child.children:
                lines.extend(_walk(child, child_path, depth + 1))
        return lines

    body = _walk(result.root, root_label, 1)
    if not body:
        return root_label
    return "\n".join([root_label, *body])


def find(name: str, root: str = "/", kind: Literal["all", "files", "dirs"] = "all", limit: int = 10) -> FindResult:
    type_value = {
        "all": FindRequest.TYPE_ALL,
        "files": FindRequest.TYPE_FILES,
        "dirs": FindRequest.TYPE_DIRS,
    }[kind]
    response = _runtime().find(
        FindRequest(
            root=_normalize_request_path(root, root_empty=True),
            name=name,
            type=type_value,
            limit=limit,
        )
    )
    return FindResult(items=[_normalize_runtime_path(item) for item in response.items])


def search(pattern: str, path: str = "/", count: int = 5) -> SearchResult:
    response = _runtime().search(
        SearchRequest(
            root=_normalize_request_path(path, root_empty=True),
            pattern=pattern,
            limit=count,
        )
    )
    return SearchResult(
        matches=[
            SearchSnippet(
                path=_normalize_runtime_path(item.path),
                line=item.line,
                line_text=item.line_text,
            )
            for item in response.matches
        ]
    )


def list(path: str = "/") -> ListResult:
    normalized_path = _normalize_request_path(path)
    response = _runtime().list(ListRequest(name=_normalize_request_path(path, root_empty=True)))

    def _join_child(name: str) -> str:
        if normalized_path == "/":
            return _normalize_runtime_path(name)
        return _normalize_runtime_path(f"{normalized_path}/{name}")

    return ListResult(
        entries=[
            ListEntry(
                name=item.name,
                path=_join_child(item.name),
                is_dir=item.is_dir,
            )
            for item in response.entries
        ]
    )


def read(path: str, number: bool = False, start_line: int = 0, end_line: int = 0) -> ReadResult:
    normalized_path = _normalize_request_path(path)
    response = _runtime().read(
        ReadRequest(
            path=normalized_path,
            number=number,
            start_line=start_line,
            end_line=end_line,
        )
    )
    return ReadResult(path=_normalize_runtime_path(response.path), content=response.content)


def write(path: str, content: str, start_line: int = 0, end_line: int = 0) -> WriteResult:
    normalized_path = _normalize_request_path(path)
    _runtime().write(
        WriteRequest(
            path=normalized_path,
            content=content,
            start_line=start_line,
            end_line=end_line,
        )
    )
    return WriteResult(
        path=_normalize_runtime_path(normalized_path),
        bytes_written=len(content.encode("utf-8")),
        start_line=start_line,
        end_line=end_line,
    )


def delete(path: str) -> DeleteResult:
    normalized_path = _normalize_request_path(path)
    _runtime().delete(DeleteRequest(path=normalized_path))
    return DeleteResult(path=_normalize_runtime_path(normalized_path))


def mkdir(path: str) -> MkDirResult:
    normalized_path = _normalize_request_path(path)
    _runtime().mk_dir(MkDirRequest(path=normalized_path))
    return MkDirResult(path=_normalize_runtime_path(normalized_path))


def move(from_name: str, to_name: str) -> MoveResult:
    normalized_from = _normalize_request_path(from_name)
    normalized_to = _normalize_request_path(to_name)
    _runtime().move(MoveRequest(from_name=normalized_from, to_name=normalized_to))
    return MoveResult(
        from_name=_normalize_runtime_path(normalized_from),
        to_name=_normalize_runtime_path(normalized_to),
    )


def answer(message: str, outcome: OutcomeName, refs: builtins.list[str] | None = None) -> AnswerResult:
    final_refs: builtins.list[str] = []
    for ref in refs or []:
        cleaned = (ref or "").strip()
        if cleaned and cleaned not in final_refs:
            final_refs.append(cleaned)
    _runtime().answer(
        AnswerRequest(
            message=message,
            outcome=_OUTCOME_BY_NAME[outcome],
            refs=final_refs,
        )
    )
    return AnswerResult(message=message, outcome=outcome, refs=final_refs)
