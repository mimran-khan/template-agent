"""Agent implementation for the template agent system.

This module provides the core agent functionality using the deepagents library,
including initialization, configuration, and agent creation with MCP tools,
skills, subagents, and memory.
"""

from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from deepagents import SubAgent, create_deep_agent
from deepagents.backends import LocalShellBackend
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from template_agent.src.core.exceptions.exceptions import AppException, AppExceptionCode
from template_agent.src.core.prompt import get_system_prompt
from template_agent.src.core.storage import get_global_checkpoint, get_global_store
from template_agent.src.settings import settings
from template_agent.utils.pylogger import get_python_logger

logger = get_python_logger(log_level=settings.PYTHON_LOG_LEVEL)

# Repo root and config directory for memory, skills, and subagents
REPO_ROOT = Path(__file__).parent.parent.parent.parent  # template-agent/
CONFIG_DIR = Path(__file__).parent.parent.parent / "agent_config"


@asynccontextmanager
async def get_template_agent(sso_token: str | None = None):
    """Get a fully initialized deep agent with MCP tools, skills, subagents, and memory.

    This function creates and configures a deep agent using the deepagents library
    with the necessary tools from MCP, skills, subagents, and memory. It uses an
    async context manager to ensure proper resource cleanup.

    Args:
        sso_token: Optional access token for authentication. If provided,
            it will be used for authorization headers in MCP client requests.

    Yields:
        The initialized deep agent instance.

    Raises:
        Exception: If there are issues with database connections or agent setup.
    """
    # Initialize MCP client and get tools
    tools: list = []

    # Log MCP connection details for debugging
    logger.info(f"Attempting to connect to MCP server at {settings.MCP_SERVER_URL}")
    logger.info(f"MCP server name: {settings.MCP_SERVER_NAME}")
    logger.info(f"MCP transport protocol: {settings.MCP_TRANSPORT_PROTOCOL}")
    logger.info(f"MCP connection timeout: {settings.MCP_CONNECTION_TIMEOUT}s")
    logger.info(f"SSO authentication: {'Yes' if sso_token else 'No'}")

    try:
        import asyncio

        # Add timeout wrapper for MCP connection
        async def connect_with_timeout():
            # Configure MCP client with SSL verification setting
            server_config: dict = {
                "url": settings.MCP_SERVER_URL,
                "transport": settings.MCP_TRANSPORT_PROTOCOL,
                "headers": {"Authorization": f"Bearer {sso_token}"}
                if sso_token
                else {},
            }

            client = MultiServerMCPClient({settings.MCP_SERVER_NAME: server_config})
            return await client.get_tools()

        tools = await asyncio.wait_for(
            connect_with_timeout(), timeout=settings.MCP_CONNECTION_TIMEOUT
        )
        logger.info(
            f"Successfully connected to MCP server and loaded {len(tools)} tools"
        )
        logger.info(f"Available tools: {[tool.name for tool in tools]}")
    except asyncio.TimeoutError:
        # Handle timeout specifically
        error_msg = (
            f"Timeout connecting to MCP server at {settings.MCP_SERVER_URL} "
            f"after {settings.MCP_CONNECTION_TIMEOUT}s. "
            f"Server may be down or unreachable."
        )
        logger.error(error_msg)

        if settings.USE_INMEMORY_SAVER:
            logger.warning("Running in local development mode without MCP tools")
            tools = []
        else:
            logger.critical(error_msg)
            raise AppException(
                error_msg,
                AppExceptionCode.PRODUCTION_MCP_CONNECTION_ERROR,
            )
    except Exception as e:
        # Log detailed error information for other exceptions
        logger.error(
            f"Failed to connect to MCP server at {settings.MCP_SERVER_URL}",
            exc_info=True,
        )
        logger.error(f"MCP connection error type: {type(e).__name__}")
        logger.error(f"MCP connection error details: {str(e)}")

        if settings.USE_INMEMORY_SAVER:
            logger.warning("Running in local development mode without MCP tools")
            tools = []  # No tools for local development
        else:
            # In production, MCP is required
            error_msg = (
                f"Failed to connect to required MCP server at {settings.MCP_SERVER_URL}. "
                f"Error: {type(e).__name__}: {str(e)}"
            )
            logger.critical(error_msg)
            raise AppException(
                error_msg,
                AppExceptionCode.PRODUCTION_MCP_CONNECTION_ERROR,
            )

    # Initialize the language model with service account credentials
    import google.auth

    credentials, project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    model = ChatGoogleGenerativeAI(
        model="gemini-3.1-pro-preview",
        temperature=0,
        credentials=credentials,
        project=project,
    )

    # Load subagents from YAML
    subagents_path = CONFIG_DIR / "subagents.yaml"
    logger.info(f"Loading subagents from {subagents_path}")

    tool_by_name = {t.name: t for t in tools}

    # Skills base directory — each sub-agent has its own subdirectory
    skills_base = CONFIG_DIR / "skills"

    subagents_config: list[SubAgent] | None = None
    if subagents_path.exists():
        raw = yaml.safe_load(subagents_path.read_text())
        entries = raw.get("subagents", []) if isinstance(raw, dict) else []
        subagents_config = []
        for entry in entries:
            sa: SubAgent = SubAgent(
                name=entry["name"],
                description=entry.get("description", ""),
                system_prompt=entry.get("instructions", ""),
            )
            yaml_tool_names = entry.get("tools", [])
            if yaml_tool_names:
                resolved = [
                    tool_by_name[n] for n in yaml_tool_names if n in tool_by_name
                ]
                missing = [n for n in yaml_tool_names if n not in tool_by_name]
                if missing:
                    logger.warning(
                        f"Subagent '{entry['name']}' references unknown tools: {missing}"
                    )
                sa["tools"] = resolved
            sa_skills_name = entry.get("skills_dir")
            if sa_skills_name:
                sa_skills_dir = skills_base / sa_skills_name
                if sa_skills_dir.exists():
                    sa["skills"] = [str(sa_skills_dir)]
                    logger.info(f"Subagent '{entry['name']}' skills: {sa_skills_dir}")
                else:
                    logger.warning(
                        f"Subagent '{entry['name']}' skills_dir not found: {sa_skills_dir}"
                    )
            subagents_config.append(sa)
        logger.info(f"Loaded {len(subagents_config)} subagents")
    else:
        logger.warning(f"Subagents file not found at {subagents_path}")

    # Load system prompt
    system_prompt = get_system_prompt()
    logger.info("Loaded system prompt from prompt.py")

    # Setup memory — load all .md files from agent_config/
    memory_files = []
    for md_path in sorted(CONFIG_DIR.glob("*.md")):
        memory_files.append(str(md_path))
        logger.info(f"Loaded memory from {md_path}")
    if not memory_files:
        logger.warning(f"No .md memory files found in {CONFIG_DIR}")

    # Sandbox directory for agent shell execution — keeps output files
    # out of the source tree (e.g., scraped pages, intermediate results).
    sandbox_dir = REPO_ROOT / ".cache" / "agent-workspace"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    backend = LocalShellBackend(root_dir=str(sandbox_dir))

    # Resolve checkpointer and store
    checkpointer = None
    store = None
    pg_ctx = None

    if settings.USE_INMEMORY_SAVER:
        checkpointer = get_global_checkpoint()
        store = get_global_store()
        logger.info(
            f"Using in-memory checkpoint={type(checkpointer).__name__} "
            f"store={type(store).__name__}"
        )
    else:
        logger.info("Using PostgreSQL checkpoint")
        pg_ctx = AsyncPostgresSaver.from_conn_string(settings.database_uri)
        checkpointer = await pg_ctx.__aenter__()
        logger.info(f"PostgreSQL checkpointer ready: {type(checkpointer).__name__}")
        if hasattr(checkpointer, "setup"):
            await checkpointer.setup()

    logger.info(
        f"Creating deep agent with checkpointer={type(checkpointer).__name__ if checkpointer else None} "
        f"store={type(store).__name__ if store else None}"
    )

    try:
        agent = create_deep_agent(
            model=model,
            system_prompt=system_prompt,
            memory=memory_files,
            skills=[],
            tools=[],
            subagents=subagents_config,
            backend=backend,
            checkpointer=checkpointer,
            store=store,
        )
        logger.info("Deep agent initialized successfully")
        yield agent
    finally:
        if pg_ctx is not None:
            await pg_ctx.__aexit__(None, None, None)
