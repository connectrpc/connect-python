from __future__ import annotations

from example.eliza_connect import ElizaServiceClientSync
from example.eliza_pb2 import IntroduceRequest, SayRequest


def main():
    with ElizaServiceClientSync("http://localhost:8000") as client:
        say_request = "Me: Hello, I'm feeling anxious about my code."
        print(say_request)
        response = client.say(SayRequest(sentence=say_request))
        print(f"    Eliza says: {response.sentence}")

        introduce_request = "Python Developer"
        print(f"Me: Hi, I'm a {introduce_request}.")
        for response in client.introduce(IntroduceRequest(name=introduce_request)):
            print(f"    Eliza: {response.sentence}")


if __name__ == "__main__":
    main()
