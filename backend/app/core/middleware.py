"""Request ID, request log, body limit and response headers, as one ASGI middleware."""
import logging
import re
import uuid
from time import perf_counter

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse

from .config import get_settings

log = logging.getLogger("changewise")
_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")


class RequestMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        given = headers.get("x-request-id", "")
        request_id = given if _SAFE_ID.fullmatch(given) else uuid.uuid4().hex
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        started, status = perf_counter(), 500

        async def wrapped(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                out = MutableHeaders(scope=message)
                out["X-Request-ID"] = request_id
                out["X-Content-Type-Options"] = "nosniff"
                out["Cache-Control"] = "no-store"
                out["Referrer-Policy"] = "no-referrer"
            await send(message)

        def problem(code, error, text):
            return JSONResponse({"error": {"code": error, "message": text, "details": [], "request_id": request_id}}, code)

        # A margin above the file limit covers the multipart envelope.
        limit = get_settings().max_upload_bytes + 64 * 1024
        length = headers.get("content-length", "")
        chunked = "chunked" in headers.get("transfer-encoding", "")
        try:
            if chunked or (length.isdigit() and int(length) > limit):
                await problem(413, "TOO_LARGE", "The request is too large.")(scope, receive, wrapped)
            else:
                await self.app(scope, receive, wrapped)
        except Exception:  # the last resort: log it here, tell the client nothing
            log.exception("unhandled_error", extra={"fields": {"request_id": request_id, "path": scope["path"]}})
            if status == 500:
                await problem(500, "INTERNAL_ERROR", "Something went wrong.")(scope, receive, wrapped)
        finally:
            route = scope.get("route")
            log.info("request", extra={"fields": {
                "request_id": request_id, "method": scope["method"], "route": getattr(route, "path", scope["path"]),
                "status": status, "ok": status < 400, "user_id": state.get("user_id"), "run_id": state.get("run_id"),
                "ms": round((perf_counter() - started) * 1000, 1)}})
