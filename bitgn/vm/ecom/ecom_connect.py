# -*- coding: utf-8 -*-

from collections.abc import Mapping

from connectrpc.client import ConnectClientSync
from connectrpc.method import IdempotencyLevel, MethodInfo
from connectrpc.request import Headers

import bitgn.vm.ecom.ecom_pb2 as bitgn_dot_vm_dot_ecom__pb2


class EcomRuntimeClientSync(ConnectClientSync):
    def read(
        self,
        request: bitgn_dot_vm_dot_ecom__pb2.ReadRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_ecom__pb2.ReadResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Read",
                service_name="bitgn.vm.ecom.EcomRuntime",
                input=bitgn_dot_vm_dot_ecom__pb2.ReadRequest,
                output=bitgn_dot_vm_dot_ecom__pb2.ReadResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def list(
        self,
        request: bitgn_dot_vm_dot_ecom__pb2.ListRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_ecom__pb2.ListResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="List",
                service_name="bitgn.vm.ecom.EcomRuntime",
                input=bitgn_dot_vm_dot_ecom__pb2.ListRequest,
                output=bitgn_dot_vm_dot_ecom__pb2.ListResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def tree(
        self,
        request: bitgn_dot_vm_dot_ecom__pb2.TreeRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_ecom__pb2.TreeResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Tree",
                service_name="bitgn.vm.ecom.EcomRuntime",
                input=bitgn_dot_vm_dot_ecom__pb2.TreeRequest,
                output=bitgn_dot_vm_dot_ecom__pb2.TreeResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def find(
        self,
        request: bitgn_dot_vm_dot_ecom__pb2.FindRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_ecom__pb2.FindResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Find",
                service_name="bitgn.vm.ecom.EcomRuntime",
                input=bitgn_dot_vm_dot_ecom__pb2.FindRequest,
                output=bitgn_dot_vm_dot_ecom__pb2.FindResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def search(
        self,
        request: bitgn_dot_vm_dot_ecom__pb2.SearchRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_ecom__pb2.SearchResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Search",
                service_name="bitgn.vm.ecom.EcomRuntime",
                input=bitgn_dot_vm_dot_ecom__pb2.SearchRequest,
                output=bitgn_dot_vm_dot_ecom__pb2.SearchResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def exec(
        self,
        request: bitgn_dot_vm_dot_ecom__pb2.ExecRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_ecom__pb2.ExecResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Exec",
                service_name="bitgn.vm.ecom.EcomRuntime",
                input=bitgn_dot_vm_dot_ecom__pb2.ExecRequest,
                output=bitgn_dot_vm_dot_ecom__pb2.ExecResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def write(
        self,
        request: bitgn_dot_vm_dot_ecom__pb2.WriteRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_ecom__pb2.WriteResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Write",
                service_name="bitgn.vm.ecom.EcomRuntime",
                input=bitgn_dot_vm_dot_ecom__pb2.WriteRequest,
                output=bitgn_dot_vm_dot_ecom__pb2.WriteResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def delete(
        self,
        request: bitgn_dot_vm_dot_ecom__pb2.DeleteRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_ecom__pb2.DeleteResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Delete",
                service_name="bitgn.vm.ecom.EcomRuntime",
                input=bitgn_dot_vm_dot_ecom__pb2.DeleteRequest,
                output=bitgn_dot_vm_dot_ecom__pb2.DeleteResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def stat(
        self,
        request: bitgn_dot_vm_dot_ecom__pb2.StatRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_ecom__pb2.StatResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Stat",
                service_name="bitgn.vm.ecom.EcomRuntime",
                input=bitgn_dot_vm_dot_ecom__pb2.StatRequest,
                output=bitgn_dot_vm_dot_ecom__pb2.StatResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def answer(
        self,
        request: bitgn_dot_vm_dot_ecom__pb2.AnswerRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_vm_dot_ecom__pb2.AnswerResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Answer",
                service_name="bitgn.vm.ecom.EcomRuntime",
                input=bitgn_dot_vm_dot_ecom__pb2.AnswerRequest,
                output=bitgn_dot_vm_dot_ecom__pb2.AnswerResponse,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )
