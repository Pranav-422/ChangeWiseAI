"""JSON logs. Callers pass identifiers and timings only: never tokens, keys or document text."""
import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        line = {"time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "level": record.levelname,
                "event": record.getMessage(), **getattr(record, "fields", {})}
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, ensure_ascii=False, default=str)


def configure(level):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("changewise")
    logger.handlers[:] = [handler]
    logger.setLevel(level)
    logger.propagate = False
