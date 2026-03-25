import logging, json
from logging.handlers import TimedRotatingFileHandler
from utils.paths import LOG_DIR


# Cache per-UUID LoggerAdapter instances to avoid adding duplicate handlers
_uuid_loggers: dict[str, logging.LoggerAdapter] = {}


class JsonFormatter(logging.Formatter):
    """
    A JSON formatter for log records.

    Produces one JSON object per line with:
      - ts: timestamp formatted using `datefmt`
      - level: log level name (INFO, ERROR, etc.)
      - logger: logger name (e.g., 'user.<uuid>')
      - uuid: propagated from LoggerAdapter's `extra`
      - msg: final message string

    If present on the record, the formatter also includes:
      - api, elapsed_ms, saved_to, size_bytes, details

    If `exc_info` is set, a formatted stack trace will be included as 'exc'.
    """

    def format(self, record: logging.LogRecord) -> str:
        doc = {
            "ts": self.formatTime(record, self.datefmt),  # Timestamp string
            "level": record.levelname,  # Log level
            "logger": record.name,  # Logger name
            "uuid": getattr(record, "uuid", None),  # Injected by LoggerAdapter
            "msg": record.getMessage(),  # Rendered message text
        }

        # Include common custom fields when available
        for k in ("api", "elapsed_ms", "saved_to", "size_bytes", "details"):
            if hasattr(record, k):
                doc[k] = getattr(record, k)

        # Include exception info if present
        if record.exc_info:
            doc["exc"] = self.formatException(record.exc_info)

        # Keep Unicode characters as-is
        return json.dumps(doc, ensure_ascii=False)


def setup_logging(level: str = "INFO", app_log: str | None = None):
    if app_log is None:
        app_log = str(LOG_DIR / "app.log")

    """
    Configure root logging for the application.

    Actions:
      1) Ensure the 'logs/' directory exists.
      2) Set root logger level and remove existing handlers (prevents duplicates when hot-reloading).
      3) Add a console handler (human-readable format).
      4) Add a daily-rotated file handler that writes JSON lines to `app_log`.

    Args:
        level (str): Log level name, e.g., "DEBUG", "INFO", "WARNING".
        app_log (str): Path to the main application log file.

    Note:
        - `TimedRotatingFileHandler` rotates at local midnight. In multi-process
          deployments, consider a process-safe handler (e.g., concurrent-log-handler)
          or ship logs to stdout and aggregate externally (Docker, Cloud logs, etc.).
    """


    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear any pre-existing handlers to avoid duplicate logs
    root.handlers.clear()

    # Console handler (plain text)
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    root.addHandler(ch)

    # File handler (JSON), rotates daily, keeps 7 backups
    fh = TimedRotatingFileHandler(
        app_log, when="midnight", backupCount=7, encoding="utf-8"
    )
    fh.setFormatter(JsonFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
    root.addHandler(fh)


def get_uuid_logger(uuid: str, propagate_to_root: bool = True) -> logging.LoggerAdapter:
    """
    Get a per-UUID logger that writes to `logs/<uuid>.log` in JSON format.

    The returned object is a LoggerAdapter which injects `uuid` into each record.
    By default, logs also propagate to the root logger (so they appear in `app.log`).

    Args:
        uuid (str): The UUID to associate with this user's log stream.
        propagate_to_root (bool): If True (default), records also go to the root
            handlers (e.g., console and app.log). If False, records write only
            to `logs/<uuid>.log`.

    Returns:
        logging.LoggerAdapter: Use `.info()`, `.error()`, etc. and optionally pass
        `extra={...}` to add structured fields (e.g., api, elapsed_ms).

    Example:
        logger = get_uuid_logger("12345")
        logger.info("translation completed", extra={"api": "code/translator", "elapsed_ms": 5321})
    """
    # Return cached adapter if already created
    if uuid in _uuid_loggers:
        return _uuid_loggers[uuid]
    
    # Add a daily-rotated file handler for this UUID, keep 14 backups
    fh = TimedRotatingFileHandler(
        str(LOG_DIR / f"{uuid}.log"), when="midnight", backupCount=14, encoding="utf-8"
    )
    fh.setFormatter(JsonFormatter(datefmt="%Y-%m-%d %H:%M:%S"))

    # Create a base logger for this UUID
    base = logging.getLogger(f"user.{uuid}")
    base.setLevel(logging.INFO)
    base.propagate = propagate_to_root  # True -> also writes to root handlers
    base.addHandler(fh)

    # Wrap with LoggerAdapter to inject the uuid into each record
    adapter = logging.LoggerAdapter(base, {"uuid": uuid})
    _uuid_loggers[uuid] = adapter
    return adapter
