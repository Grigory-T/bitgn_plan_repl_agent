# -*- coding: utf-8 -*-

from collections.abc import Mapping

from connectrpc.client import ConnectClientSync
from connectrpc.method import IdempotencyLevel, MethodInfo
from connectrpc.request import Headers

import bitgn_sdk.harness_pb2 as bitgn_dot_harness__pb2


class HarnessServiceClientSync(ConnectClientSync):
    def status(
        self,
        request: bitgn_dot_harness__pb2.StatusRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_harness__pb2.StatusResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="Status",
                service_name="bitgn.harness.HarnessService",
                input=bitgn_dot_harness__pb2.StatusRequest,
                output=bitgn_dot_harness__pb2.StatusResponse,
                idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def get_benchmark(
        self,
        request: bitgn_dot_harness__pb2.GetBenchmarkRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_harness__pb2.GetBenchmarkResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="GetBenchmark",
                service_name="bitgn.harness.HarnessService",
                input=bitgn_dot_harness__pb2.GetBenchmarkRequest,
                output=bitgn_dot_harness__pb2.GetBenchmarkResponse,
                idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def start_run(
        self,
        request: bitgn_dot_harness__pb2.StartRunRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_harness__pb2.StartRunResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="StartRun",
                service_name="bitgn.harness.HarnessService",
                input=bitgn_dot_harness__pb2.StartRunRequest,
                output=bitgn_dot_harness__pb2.StartRunResponse,
                idempotency_level=IdempotencyLevel.IDEMPOTENT,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def get_run(
        self,
        request: bitgn_dot_harness__pb2.GetRunRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_harness__pb2.GetRunResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="GetRun",
                service_name="bitgn.harness.HarnessService",
                input=bitgn_dot_harness__pb2.GetRunRequest,
                output=bitgn_dot_harness__pb2.GetRunResponse,
                idempotency_level=IdempotencyLevel.NO_SIDE_EFFECTS,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def start_playground(
        self,
        request: bitgn_dot_harness__pb2.StartPlaygroundRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_harness__pb2.StartPlaygroundResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="StartPlayground",
                service_name="bitgn.harness.HarnessService",
                input=bitgn_dot_harness__pb2.StartPlaygroundRequest,
                output=bitgn_dot_harness__pb2.StartPlaygroundResponse,
                idempotency_level=IdempotencyLevel.IDEMPOTENT,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def start_trial(
        self,
        request: bitgn_dot_harness__pb2.StartTrialRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_harness__pb2.StartTrialResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="StartTrial",
                service_name="bitgn.harness.HarnessService",
                input=bitgn_dot_harness__pb2.StartTrialRequest,
                output=bitgn_dot_harness__pb2.StartTrialResponse,
                idempotency_level=IdempotencyLevel.IDEMPOTENT,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def end_trial(
        self,
        request: bitgn_dot_harness__pb2.EndTrialRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_harness__pb2.EndTrialResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="EndTrial",
                service_name="bitgn.harness.HarnessService",
                input=bitgn_dot_harness__pb2.EndTrialRequest,
                output=bitgn_dot_harness__pb2.EndTrialResponse,
                idempotency_level=IdempotencyLevel.IDEMPOTENT,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )

    def submit_run(
        self,
        request: bitgn_dot_harness__pb2.SubmitRunRequest,
        *,
        headers: Headers | Mapping[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> bitgn_dot_harness__pb2.SubmitRunResponse:
        return self.execute_unary(
            request=request,
            method=MethodInfo(
                name="SubmitRun",
                service_name="bitgn.harness.HarnessService",
                input=bitgn_dot_harness__pb2.SubmitRunRequest,
                output=bitgn_dot_harness__pb2.SubmitRunResponse,
                idempotency_level=IdempotencyLevel.IDEMPOTENT,
            ),
            headers=headers,
            timeout_ms=timeout_ms,
        )
