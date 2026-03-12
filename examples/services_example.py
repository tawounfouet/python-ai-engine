"""
Example: Using AI Engine Services

Demonstrates how to use the services layer for agent management and conversations.
"""

from ai_engine.models.provider import LLMProviderConfig
from ai_engine.services import AgentService
from ai_engine.storage.sqlite import SQLiteStorage
from ai_engine.types import ProviderType


def main():
    """Example usage of AI Engine services."""
    # Initialize storage
    storage = SQLiteStorage("example_agents.db")

    with storage:
        # Initialize services
        agent_service = AgentService(storage)

        # Create a provider configuration
        provider = LLMProviderConfig(
            name="OpenAI GPT-4",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
            api_key="sk-your-openai-api-key-here",  # Replace with real API key
        )
        saved_provider = storage.save_provider(provider)
        print(f"✅ Created provider: {saved_provider.name}")

        # Create an agent
        agent = agent_service.create_agent(
            name="Research Assistant",
            provider_id=saved_provider.id,
            system_prompt="You are a helpful research assistant with expertise in analyzing and synthesizing information.",
        )
        print(f"✅ Created agent: {agent.name} (ID: {agent.id})")

        # Create a conversation
        conversation = agent_service.create_conversation(
            agent_id=agent.id,
            title="Research on AI Trends",
        )
        print(f"✅ Created conversation: {conversation.title}")

        # Simulate a conversation (would need real API key for actual LLM calls)
        print("\n📝 Example conversation flow:")
        print("User: What are the latest trends in AI development?")
        print("Assistant: [Would respond with AI trends analysis]")

        # Note: Actual chat requires valid API key
        # response, _ = agent_service.chat(
        #     agent_id=agent.id,
        #     message="What are the latest trends in AI development?",
        #     conversation_id=conversation.id,
        # )

        # Get agent statistics
        stats = agent_service.get_agent_stats(agent.id)
        print(f"\n📊 Agent stats: {stats}")

        # List all agents
        all_agents = agent_service.list_agents()
        print(f"\n👥 Total agents: {len(all_agents)}")

        print("\n✨ Example completed successfully!")


if __name__ == "__main__":
    main()
