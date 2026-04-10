"""Daytona sandbox backend for the Deep Agent.

Uses the Daytona SDK to create an isolated sandbox environment and wraps it
with ``langchain_daytona.DaytonaSandbox`` which implements the Deep Agents
``BackendProtocol``.  The agent runs on the host and calls sandbox APIs
remotely (the "Sandbox as Tool" pattern).

After sandbox creation the local ``agent_config/`` tree is uploaded so that
``SkillsMiddleware`` — which resolves skills via ``backend.ls()`` /
``backend.download_files()`` — can find definitions inside the sandbox.
"""

from __future__ import annotations

import os
from pathlib import Path

from daytona import Daytona, DaytonaConfig
from langchain_daytona import DaytonaSandbox

from template_agent.src.settings import settings
from template_agent.utils.pylogger import get_python_logger

logger = get_python_logger()

SANDBOX_CONFIG_ROOT = "/home/daytona/agent_config"

LOCAL_CONFIG_DIR = Path(__file__).parent.parent.parent / "agent_config"

_backend: DaytonaSandbox | None = None
_daytona_client: Daytona | None = None


def _upload_agent_config(backend: DaytonaSandbox) -> None:
    """Upload the local ``agent_config/`` tree into the Daytona sandbox.

    ``SkillsMiddleware`` calls ``backend.ls()`` and
    ``backend.download_files()`` to load skill definitions, so every file
    must be present inside the sandbox filesystem before the agent is
    created.
    """
    files: list[tuple[str, bytes]] = []

    for root, _dirs, filenames in os.walk(LOCAL_CONFIG_DIR):
        for fname in filenames:
            local_path = Path(root) / fname
            rel = local_path.relative_to(LOCAL_CONFIG_DIR)
            remote_path = f"{SANDBOX_CONFIG_ROOT}/{rel}"
            files.append((remote_path, local_path.read_bytes()))

    if not files:
        logger.warning("No agent_config files found to upload to sandbox")
        return

    logger.info(
        f"Uploading {len(files)} agent_config files to sandbox "
        f"at {SANDBOX_CONFIG_ROOT}"
    )
    responses = backend.upload_files(files)

    errors = [r for r in responses if r.error]
    if errors:
        for err in errors:
            logger.error(f"Failed to upload to sandbox: {err.path} — {err.error}")
        raise RuntimeError(
            f"Failed to upload {len(errors)} file(s) to Daytona sandbox"
        )
    logger.info(f"All {len(files)} agent_config files uploaded to sandbox")


def _get_daytona_client() -> Daytona:
    """Return a singleton Daytona API client configured from settings."""
    global _daytona_client
    if _daytona_client is None:
        config = DaytonaConfig(
            api_key=settings.DAYTONA_API_KEY or "",
            api_url=settings.DAYTONA_API_URL,
            target=settings.DAYTONA_TARGET,
        )
        _daytona_client = Daytona(config)
    return _daytona_client


def create_backend(
    *,
    timeout: int | None = None,
) -> DaytonaSandbox:
    """Create a :class:`DaytonaSandbox` backed by a remote Daytona sandbox.

    After sandbox creation the local ``agent_config/`` tree is uploaded so
    that ``SkillsMiddleware`` can find skill definitions via the backend.

    Args:
        timeout: Per-command timeout in seconds.  Falls back to
            ``settings.DAYTONA_SANDBOX_TIMEOUT``.
    """
    effective_timeout = timeout or settings.DAYTONA_SANDBOX_TIMEOUT

    client = _get_daytona_client()
    sandbox = client.create()
    logger.info(f"Daytona sandbox created: {sandbox.id}")

    backend = DaytonaSandbox(
        sandbox=sandbox,
        timeout=effective_timeout,
    )
    logger.info(
        f"DaytonaSandbox backend ready — sandbox={sandbox.id}, "
        f"timeout={effective_timeout}s"
    )

    _upload_agent_config(backend)

    return backend


def get_backend(
    *,
    timeout: int | None = None,
) -> DaytonaSandbox:
    """Return the singleton backend, creating it on the first call.

    Subsequent calls return the same instance regardless of arguments.
    """
    global _backend
    if _backend is None:
        _backend = create_backend(timeout=timeout)
    return _backend


def initialize_backend() -> DaytonaSandbox:
    """Pre-initialize the singleton backend at server startup.

    Calling this early avoids sandbox-creation latency on the first request.
    """
    logger.info("Pre-initializing Daytona sandbox backend")
    backend = get_backend()
    logger.info("Daytona sandbox backend initialization complete")
    return backend


def cleanup_backend() -> None:
    """Stop the sandbox and release resources on server shutdown."""
    global _backend, _daytona_client
    if _backend is not None:
        try:
            sandbox = _backend._sandbox  # noqa: SLF001
            client = _get_daytona_client()
            client.remove(sandbox)
            logger.info(f"Daytona sandbox {sandbox.id} removed")
        except Exception:
            logger.warning("Failed to remove Daytona sandbox", exc_info=True)
        _backend = None
    _daytona_client = None
