#!/usr/bin/env python3

import asyncio
import sys

import aiohttp
import eliza_pb2  # type: ignore[import-not-found]
from eliza_pb2_connect import AsyncElizaServiceClient  # type: ignore[import-not-found]

from connectrpc.client_protocol import ConnectProtocol


async def test_say(client: AsyncElizaServiceClient, protocol_name: str) -> bool:
    """Test the Say unary RPC method"""
    print(f"  [{protocol_name}] Testing Say method...")

    request = eliza_pb2.SayRequest()
    request.sentence = "Hello, I'm feeling anxious about my code."

    try:
        response = await client.say(request)
        if response.sentence:
            print(f"    Eliza says: {response.sentence}")
            return True
        else:
            print("    ERROR: Empty response")
            return False
    except Exception as e:
        print(f"    ERROR: {e}")
        return False


async def test_introduce(client: AsyncElizaServiceClient, protocol_name: str) -> bool:
    """Test the Introduce server streaming RPC method"""
    print(f"  [{protocol_name}] Testing Introduce method...")

    request = eliza_pb2.IntroduceRequest()
    request.name = "Python Developer"

    try:
        responses = []
        async for response in client.introduce(request):
            responses.append(response.sentence)
            print(f"    Eliza: {response.sentence}")

        if responses:
            print(f"    Received {len(responses)} introduction sentences")
            return True
        else:
            print("    ERROR: No introduction sentences received")
            return False
    except Exception as e:
        print(f"    ERROR: {e}")
        raise


async def test_converse(client: AsyncElizaServiceClient, protocol_name: str) -> bool:
    """Test the Converse bidirectional streaming RPC method"""
    print(f"  [{protocol_name}] Testing Converse method...")

    conversation = [
        "I've been having trouble with async programming.",
        "Sometimes I feel like my code is talking back to me.",
        "Do you think Connect RPC will help with my problems?",
    ]

    try:
        requests = []
        for sentence in conversation:
            req = eliza_pb2.ConverseRequest()
            req.sentence = sentence
            requests.append(req)

        responses = []
        async for response in client.converse(requests):
            responses.append(response.sentence)
            print(f"    Eliza: {response.sentence}")

        if responses:
            print(f"    Had {len(responses)} exchanges in conversation")
            return True
        else:
            print("    ERROR: No conversation responses received")
            return False
    except Exception as e:
        print(f"    ERROR: {e}")
        raise


async def test_call_introduce(client: AsyncElizaServiceClient, protocol_name: str) -> bool:
    """Test the Introduce server streaming RPC method with metadata access"""
    print(f"  [{protocol_name}] Testing Introduce stream method with metadata...")

    request = eliza_pb2.IntroduceRequest()
    request.name = "Python Developer Stream"

    try:
        responses = []
        async with await client.call_introduce(request) as stream:
            async for response in stream:
                responses.append(response.sentence)
                print(f"    Eliza: {response.sentence}")

        # Test trailing metadata access
        try:
            trailing_metadata = stream.trailing_metadata()
            print(f"    Trailing metadata: {trailing_metadata}")
        except Exception as e:
            print(f"    Trailing metadata access failed: {e}")

        if responses:
            print(f"    Received {len(responses)} introduction sentences")
            return True
        else:
            print("    ERROR: No introduction sentences received")
            return False
    except Exception as e:
        print(f"    ERROR: {e}")
        raise


async def test_protocol(protocol: ConnectProtocol, protocol_name: str) -> list[bool]:
    """Test all methods with a specific protocol"""
    print(f"\n🧪 Testing {protocol_name} protocol")
    print("-" * 50)

    async with aiohttp.ClientSession() as session:
        client = AsyncElizaServiceClient(
            base_url="https://demo.connectrpc.com",
            http_client=session,
            protocol=protocol,
        )

        results = []
        results.append(await test_say(client, protocol_name))
        results.append(await test_introduce(client, protocol_name))
        results.append(await test_converse(client, protocol_name))
        results.append(await test_call_introduce(client, protocol_name))

        return results


async def main() -> None:
    """Run integration tests for specified protocols"""
    print("🚀 Eliza Service Integration Test")
    print("Testing against: https://demo.connectrpc.com")
    print("=" * 60)

    # Parse command line arguments for protocols
    import argparse

    parser = argparse.ArgumentParser(description="Test Eliza service with different protocols")
    parser.add_argument(
        "--protocols",
        nargs="+",
        choices=["connect-proto", "connect-json", "grpc", "grpc-web"],
        default=["connect-proto", "connect-json"],
        help="Protocols to test (default: connect-proto)",
    )

    args = parser.parse_args()

    # Map CLI args to protocol enums
    protocol_map = {
        "connect-proto": (ConnectProtocol.CONNECT_PROTOBUF, "Connect + Protobuf"),
        "connect-json": (ConnectProtocol.CONNECT_JSON, "Connect + JSON"),
        "grpc": (ConnectProtocol.GRPC, "gRPC"),
        "grpc-web": (ConnectProtocol.GRPC_WEB, "gRPC-Web"),
    }

    protocols_to_test = [protocol_map[p] for p in args.protocols]

    print(f"Testing protocols: {', '.join(args.protocols)}")
    print("=" * 60)

    all_results = {}

    for protocol, name in protocols_to_test:
        try:
            results = await test_protocol(protocol, name)
            all_results[name] = results
        except Exception as e:
            print(f"\n❌ {name} protocol failed completely: {e}")
            import traceback

            traceback.print_exc()
            all_results[name] = [False, False, False, False]

    # Summary
    print("\n📊 Test Results Summary")
    print("=" * 60)

    method_names = ["Say", "Introduce", "Converse", "IntroduceStream"]
    overall_success = True

    for protocol_name, results in all_results.items():
        print(f"\n{protocol_name}:")
        for method, success in zip(method_names, results, strict=False):
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"  {method:10} {status}")
            if not success:
                overall_success = False

    print(f"\n{'=' * 60}")
    if overall_success:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
