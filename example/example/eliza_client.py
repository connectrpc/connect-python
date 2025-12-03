from __future__ import annotations

import asyncio

from example.eliza_connect import ElizaServiceClient
from example.eliza_pb2 import ConverseRequest, IntroduceRequest, SayRequest


async def main():
    async with ElizaServiceClient("http://localhost:8000") as client:
        say_request = "Me: Hello, I'm feeling anxious about my code."
        print(say_request)
        response = await client.say(SayRequest(sentence=say_request))
        print(f"    Eliza says: {response.sentence}")

        introduce_request = "Python Developer"
        print(f"Me: Hi, I'm a {introduce_request}.")
        async for response in client.introduce(
            IntroduceRequest(name=introduce_request)
        ):
            print(f"    Eliza: {response.sentence}")

        conversation = [
            "I've been having trouble with async programming.",
            "Sometimes I feel like my code is talking back to me.",
            "Do you think Connect RPC will help with my problems?",
        ]

        async def conversation_request():
            for sentence in conversation:
                print(f"Me: {sentence}")
                yield ConverseRequest(sentence=sentence)

        async for response in client.converse(conversation_request()):
            print(f"    Eliza: {response.sentence}")


if __name__ == "__main__":
    asyncio.run(main())
