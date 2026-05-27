import builtins
import os
import shlex
from typing import Literal

from pydantic import BaseModel, Field

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import (
    AnswerRequest,
    DeleteRequest,
    ExecRequest,
    FindRequest,
    ListRequest,
    NodeKind,
    Outcome,
    ReadRequest,
    SearchRequest,
    StatRequest,
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

NodeKindName = Literal["file", "dir", "unknown"]


class TreeNode(BaseModel):
    name: str
    kind: NodeKindName
    content_type: str = ""
    children: builtins.list["TreeNode"] = Field(default_factory=list)


class TreeResult(BaseModel):
    root: TreeNode
    truncated: bool = False


class ListEntry(BaseModel):
    name: str
    path: str
    kind: NodeKindName
    content_type: str = ""
    is_dir: bool = False


class ListResult(BaseModel):
    path: str
    entries: builtins.list[ListEntry] = Field(default_factory=list)


class FindResult(BaseModel):
    paths: builtins.list[str] = Field(default_factory=list)
    truncated: bool = False


class SearchSnippet(BaseModel):
    path: str
    line: int
    line_text: str


class SearchResult(BaseModel):
    matches: builtins.list[SearchSnippet] = Field(default_factory=list)
    truncated: bool = False


class ReadResult(BaseModel):
    path: str
    content_type: str = ""
    content: str
    sha256: str = ""
    truncated: bool = False


class WriteResult(BaseModel):
    path: str


class DeleteResult(BaseModel):
    path: str
    deleted: bool = True


class StatResult(BaseModel):
    path: str
    kind: NodeKindName
    content_type: str = ""
    writable: bool = False


class ExecResult(BaseModel):
    exit_code: int
    stdout: str = ""
    stderr: str = ""


class AnswerResult(BaseModel):
    message: str
    outcome: OutcomeName
    refs: builtins.list[str] = Field(default_factory=list)
    submitted: bool = True


TreeNode.model_rebuild()


_OUTCOME_BY_NAME = {
    "OUTCOME_OK": Outcome.OUTCOME_OK,
    "OUTCOME_DENIED_SECURITY": Outcome.OUTCOME_DENIED_SECURITY,
    "OUTCOME_NONE_CLARIFICATION": Outcome.OUTCOME_NONE_CLARIFICATION,
    "OUTCOME_NONE_UNSUPPORTED": Outcome.OUTCOME_NONE_UNSUPPORTED,
    "OUTCOME_ERR_INTERNAL": Outcome.OUTCOME_ERR_INTERNAL,
}

_NODE_KIND_BY_NAME = {
    "all": NodeKind.NODE_KIND_UNSPECIFIED,
    "files": NodeKind.NODE_KIND_FILE,
    "dirs": NodeKind.NODE_KIND_DIR,
}


_client: EcomRuntimeClientSync | None = None
_harness_url: str | None = None


def reset() -> None:
    global _client, _harness_url
    _client = None
    _harness_url = None


def configure(harness_url: str | None = None) -> str:
    global _client, _harness_url

    chosen_url = harness_url or os.getenv("BITGN_HARNESS_URL")
    if not chosen_url:
        raise RuntimeError(
            "ECOM runtime is not configured. Set BITGN_HARNESS_URL or start a trial "
            "with run_bitgn_task.py."
        )

    _client = EcomRuntimeClientSync(chosen_url)
    _harness_url = chosen_url
    return chosen_url


def is_configured() -> bool:
    return _client is not None or bool(os.getenv("BITGN_HARNESS_URL"))


def current_harness_url() -> str | None:
    return _harness_url or os.getenv("BITGN_HARNESS_URL")


def _runtime() -> EcomRuntimeClientSync:
    if _client is None:
        configure()
    assert _client is not None
    return _client


def _normalize_path(path: str | None, *, root_empty: bool = False) -> str:
    if path is None:
        return "" if root_empty else "/"
    text = str(path).strip()
    if not text or text == "/":
        return "" if root_empty else "/"
    while text.startswith("./"):
        text = text[2:]
    if not text.startswith("/"):
        text = "/" + text
    while "//" in text:
        text = text.replace("//", "/")
    if len(text) > 1 and text.endswith("/"):
        text = text.rstrip("/")
    return text


def _kind_name(value: int) -> NodeKindName:
    if value == NodeKind.NODE_KIND_FILE:
        return "file"
    if value == NodeKind.NODE_KIND_DIR:
        return "dir"
    return "unknown"


def _tree_node_from_proto(entry) -> TreeNode:
    return TreeNode(
        name=entry.name,
        kind=_kind_name(entry.kind),
        content_type=getattr(entry, "content_type", ""),
        children=[_tree_node_from_proto(child) for child in entry.children],
    )


def tree_data(path: str = "/", level: int = 2) -> TreeResult:
    response = _runtime().tree(
        TreeRequest(
            root=_normalize_path(path, root_empty=True),
            level=level,
        )
    )
    return TreeResult(root=_tree_node_from_proto(response.root), truncated=response.truncated)


def tree(path: str = "/", level: int = 2) -> str:
    result = tree_data(path=path, level=level)
    root_label = _normalize_path(path)

    def _walk(node: TreeNode, depth: int) -> builtins.list[str]:
        lines: builtins.list[str] = []
        indent = "  " * depth
        for child in sorted(node.children, key=lambda item: (item.kind != "dir", item.name)):
            label = child.name + "/" if child.kind == "dir" else child.name
            suffix = f" [{child.content_type}]" if child.content_type and child.kind != "dir" else ""
            lines.append(f"{indent}{label}{suffix}")
            if child.children:
                lines.extend(_walk(child, depth + 1))
        return lines

    root_is_file = result.root.name and result.root.kind == "file" and not result.root.children
    if root_is_file:
        return root_label

    body = _walk(result.root, 1)
    lines = [root_label, *body] if body else [root_label]
    if result.truncated:
        lines.append("[TRUNCATED: use a narrower path or smaller level]")
    return "\n".join(lines)


def list(path: str = "/") -> ListResult:
    response = _runtime().list(ListRequest(path=_normalize_path(path)))
    return ListResult(
        path=response.path or _normalize_path(path),
        entries=[
            ListEntry(
                name=item.name,
                path=item.path,
                kind=_kind_name(item.kind),
                content_type=item.content_type,
                is_dir=item.kind == NodeKind.NODE_KIND_DIR,
            )
            for item in response.entries
        ],
    )


def find(name: str, root: str = "/", kind: Literal["all", "files", "dirs"] = "all", limit: int = 20) -> FindResult:
    response = _runtime().find(
        FindRequest(
            root=_normalize_path(root, root_empty=True),
            name=name,
            kind=_NODE_KIND_BY_NAME[kind],
            limit=limit,
        )
    )
    return FindResult(paths=builtins.list(response.paths), truncated=response.truncated)


def search(pattern: str, path: str = "/", count: int = 20) -> SearchResult:
    response = _runtime().search(
        SearchRequest(
            root=_normalize_path(path, root_empty=True),
            pattern=pattern,
            limit=count,
        )
    )
    return SearchResult(
        matches=[
            SearchSnippet(path=item.path, line=item.line, line_text=item.line_text)
            for item in response.matches
        ],
        truncated=response.truncated,
    )


def read(path: str, number: bool = False, start_line: int = 0, end_line: int = 0) -> ReadResult:
    response = _runtime().read(
        ReadRequest(
            path=_normalize_path(path),
            number=number,
            start_line=start_line,
            end_line=end_line,
        )
    )
    return ReadResult(
        path=response.path,
        content_type=response.content_type,
        content=response.content,
        sha256=response.sha256,
        truncated=response.truncated,
    )


def write(path: str, content: str, if_match_sha256: str = "") -> WriteResult:
    response = _runtime().write(
        WriteRequest(
            path=_normalize_path(path),
            content=content,
            if_match_sha256=if_match_sha256,
        )
    )
    return WriteResult(path=response.path)


def delete(path: str) -> DeleteResult:
    normalized = _normalize_path(path)
    _runtime().delete(DeleteRequest(path=normalized))
    return DeleteResult(path=normalized)


def stat(path: str) -> StatResult:
    response = _runtime().stat(StatRequest(path=_normalize_path(path)))
    return StatResult(
        path=response.path,
        kind=_kind_name(response.kind),
        content_type=response.content_type,
        writable=response.writable,
    )


def exec(path: str, args: builtins.list[str] | None = None, stdin: str = "") -> ExecResult:
    response = _runtime().exec(
        ExecRequest(
            path=_normalize_path(path),
            args=builtins.list(args or []),
            stdin=stdin,
        )
    )
    return ExecResult(exit_code=response.exit_code, stdout=response.stdout, stderr=response.stderr)


def sql(query: str) -> ExecResult:
    return exec("/bin/sql", stdin=query)


def sql_text(query: str) -> str:
    result = sql(query)
    parts: builtins.list[str] = []
    if result.stdout:
        parts.append(result.stdout.rstrip())
    if result.stderr:
        parts.append("stderr:\n" + result.stderr.rstrip())
    if result.exit_code:
        parts.append(f"[exit {result.exit_code}]")
    return "\n".join(parts) if parts else "."


def format_exec(path: str, args: builtins.list[str] | None = None, stdin: str = "") -> str:
    result = exec(path, args=args, stdin=stdin)
    command = " ".join([shlex.quote(path), *(shlex.quote(arg) for arg in (args or []))]).strip()
    if stdin:
        command = f"{command} <<'STDIN'\n{stdin.rstrip()}\nSTDIN"
    body = []
    if result.stdout:
        body.append(result.stdout.rstrip())
    if result.stderr:
        body.append("stderr:\n" + result.stderr.rstrip())
    if result.exit_code:
        body.append(f"[exit {result.exit_code}]")
    return command + "\n" + ("\n".join(body) if body else ".")


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
