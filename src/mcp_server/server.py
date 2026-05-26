from mcp.server.fastmcp import FastMCP

from mcp_server.tools import get_campus_events, get_course_schedule, query_campus_policy

mcp = FastMCP(
    "campus-ai-agent-tools",
    instructions=(
        "Read-only campus tools for course schedules, campus events, and campus policy queries."
    ),
)

mcp.tool(name="get_course_schedule", structured_output=True)(get_course_schedule)
mcp.tool(name="get_campus_events", structured_output=True)(get_campus_events)
mcp.tool(name="query_campus_policy", structured_output=True)(query_campus_policy)


def main() -> None:
    """Run the local MCP server over standard input/output."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
