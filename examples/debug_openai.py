"""Debug script pour tester le client OpenAI."""

import asyncio
import os

from ai_engine import LLMProviderConfig, ProviderType, Message, MessageRole
from ai_engine.services.llm import get_llm_client, LLMRequest


async def test_openai():
    # Provider
    provider = LLMProviderConfig(
        name="OpenAI GPT-4o",
        provider_type=ProviderType.OPENAI,
        default_model="gpt-4o",
        api_key=os.environ.get("OPENAI_API_KEY", "sk-..."),
    )

    # Message avec conversation_id
    msg = Message(
        conversation_id="test-conv-123",
        role=MessageRole.USER,
        content="Hello, this is a test.",
    )

    print(f"Message créé: {msg}")
    print(f"Message dict: {msg.model_dump()}")

    # Client
    client = get_llm_client(provider)
    print(f"Client créé: {type(client)}")

    # Request
    request = LLMRequest(
        messages=[msg],
        temperature=0.7,
        max_tokens=50,
    )

    print(f"Request créée: {request}")
    print(f"Messages dans request: {[m.model_dump() for m in request.messages]}")

    try:
        response = await client.acomplete(request)
        print(f"✅ Réponse reçue: {response.content[:100]}...")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_openai())
