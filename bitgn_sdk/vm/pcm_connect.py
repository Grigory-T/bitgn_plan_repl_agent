# -*- coding: utf-8 -*-

from collections.abc import Mapping

from connectrpc.client import ConnectClientSync
from connectrpc.method import IdempotencyLevel, MethodInfo
from connectrpc.request import Headers

import bitgn_sdk.vm.pcm_pb2 as bitgn_dot_vm_dot_pcm__pb2


class PcmRuntimeClientSync(ConnectClientSync):
    def read(
        self,
        request: bitgn_dot_vm_dot_pcm__pb2.ReadRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_pcm__pb2.ReadResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Read",
                service_name="bitgn.vm.pcm.PcmRuntime",
                input=bitgn_dot_vm_dot_pcm__pb2.ReadRequest,
                output=bitgn_dot_vm_dot_pcm__pb2.ReadResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def write(
        self,
        request: bitgn_dot_vm_dot_pcm__pb2.WriteRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_pcm__pb2.WriteResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Write",
                service_name="bitgn.vm.pcm.PcmRuntime",
                input=bitgn_dot_vm_dot_pcm__pb2.WriteRequest,
                output=bitgn_dot_vm_dot_pcm__pb2.WriteResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def delete(
        self,
        request: bitgn_dot_vm_dot_pcm__pb2.DeleteRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_pcm__pb2.DeleteResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Delete",
                service_name="bitgn.vm.pcm.PcmRuntime",
                input=bitgn_dot_vm_dot_pcm__pb2.DeleteRequest,
                output=bitgn_dot_vm_dot_pcm__pb2.DeleteResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def mk_dir(
        self,
        request: bitgn_dot_vm_dot_pcm__pb2.MkDirRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_pcm__pb2.MkDirResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="MkDir",
                service_name="bitgn.vm.pcm.PcmRuntime",
                input=bitgn_dot_vm_dot_pcm__pb2.MkDirRequest,
                output=bitgn_dot_vm_dot_pcm__pb2.MkDirResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def move(
        self,
        request: bitgn_dot_vm_dot_pcm__pb2.MoveRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_pcm__pb2.MoveResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Move",
                service_name="bitgn.vm.pcm.PcmRuntime",
                input=bitgn_dot_vm_dot_pcm__pb2.MoveRequest,
                output=bitgn_dot_vm_dot_pcm__pb2.MoveResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def list(
        self,
        request: bitgn_dot_vm_dot_pcm__pb2.ListRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_pcm__pb2.ListResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="List",
                service_name="bitgn.vm.pcm.PcmRuntime",
                input=bitgn_dot_vm_dot_pcm__pb2.ListRequest,
                output=bitgn_dot_vm_dot_pcm__pb2.ListResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def tree(
        self,
        request: bitgn_dot_vm_dot_pcm__pb2.TreeRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_pcm__pb2.TreeResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Tree",
                service_name="bitgn.vm.pcm.PcmRuntime",
                input=bitgn_dot_vm_dot_pcm__pb2.TreeRequest,
                output=bitgn_dot_vm_dot_pcm__pb2.TreeResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def find(
        self,
        request: bitgn_dot_vm_dot_pcm__pb2.FindRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_pcm__pb2.FindResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Find",
                service_name="bitgn.vm.pcm.PcmRuntime",
                input=bitgn_dot_vm_dot_pcm__pb2.FindRequest,
                output=bitgn_dot_vm_dot_pcm__pb2.FindResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def search(
        self,
        request: bitgn_dot_vm_dot_pcm__pb2.SearchRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_pcm__pb2.SearchResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Search",
                service_name="bitgn.vm.pcm.PcmRuntime",
                input=bitgn_dot_vm_dot_pcm__pb2.SearchRequest,
                output=bitgn_dot_vm_dot_pcm__pb2.SearchResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def context(
        self,
        request: bitgn_dot_vm_dot_pcm__pb2.ContextRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_pcm__pb2.ContextResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Context",
                service_name="bitgn.vm.pcm.PcmRuntime",
                input=bitgn_dot_vm_dot_pcm__pb2.ContextRequest,
                output=bitgn_dot_vm_dot_pcm__pb2.ContextResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def answer(
        self,
        request: bitgn_dot_vm_dot_pcm__pb2.AnswerRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_pcm__pb2.AnswerResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Answer",
                service_name="bitgn.vm.pcm.PcmRuntime",
                input=bitgn_dot_vm_dot_pcm__pb2.AnswerRequest,
                output=bitgn_dot_vm_dot_pcm__pb2.AnswerResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )
