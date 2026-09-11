"""Register all Infinite Backlog MCP tools on an MCPServer instance."""
from __future__ import annotations

from . import agent, auth, collection, content, interaction, navigation
from . import play_records, ratings, related, reviews


def register_all(mcp) -> None:
    navigation.register(mcp)
    content.register(mcp)
    interaction.register(mcp)
    auth.register(mcp)
    related.register(mcp)
    collection.register(mcp)
    ratings.register(mcp)
    reviews.register(mcp)
    play_records.register(mcp)
    agent.register(mcp)
