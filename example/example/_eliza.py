from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# Ported from https://github.com/connectrpc/examples-go
# Originally from https://github.com/mattshiel/eliza-go
# See https://github.com/mattshiel/eliza-go/blob/master/LICENSE.


def reply(message: str) -> tuple[str, bool]:
    """Responds to a statement as a psychotherapist might."""

    message = _preprocess(message)
    if message in _GOODBYE_INPUTS:
        return random.choice(_GOODBYE_RESPONSES), True
    return _lookup_response(message), False


def get_intro_responses(name: str) -> Sequence[str]:
    """Returns a collection of introductory responses tailored to the given name."""
    intros = [res.format(name) for res in _INTRO_RESPONSES]
    intros.append(random.choice(_ELIZA_FACTS))
    intros.append("How are you feeling today?")
    return intros


def _lookup_response(message: str) -> str:
    for pattern, responses in _REQUEST_INPUT_REGEX_TO_RESPONSE_OPTIONS.items():
        match = pattern.match(message)
        if not match:
            continue
        response = random.choice(responses)
        if "{}" not in response:
            return response

        fragment = _reflect(match.group(1))
        return response.format(fragment)
    return random.choice(_DEFAULT_RESPONSES)


def _preprocess(message: str) -> str:
    return message.strip().lower().strip(".!?'\"")


def _reflect(fragment: str) -> str:
    words = [s.strip() for s in fragment.split()]
    for i, word in enumerate(words):
        if reflected := _REFLECTED_WORDS[word]:
            words[i] = reflected
    return " ".join(words)


# Input statements which terminate the session.
_GOODBYE_INPUTS: set[str] = {"bye", "exit", "goodbye", "quit"}

# End-of-session responses.
_GOODBYE_RESPONSES: list[str] = [
    "Goodbye. It was nice talking to you.",
    "Thank you for talking with me.",
    "Thank you, that will be $150. Have a good day!",
    "Goodbye. This was really a nice talk.",
    "Goodbye. I'm looking forward to our next session.",
    "This was a good session, wasn't it - but time is over now. Goodbye.",
    "Maybe we could discuss this over more in our next session? Goodbye.",
    "Good-bye.",
]


# Request phrase to response phrases as a lookup table.
_REQUEST_INPUT_REGEX_TO_RESPONSE_OPTIONS: dict[re.Pattern, list[str]] = {
    re.compile(r"i need (.*)"): [
        "Why do you need {}?",
        "Would it really help you to get {}?",
        "Are you sure you need {}?",
    ],
    re.compile(r"why don'?t you ([^\?]*)\??"): [
        "Do you really think I don't {}?",
        "Perhaps eventually I will {}.",
        "Do you really want me to {}?",
    ],
    re.compile(r"why can'?t I ([^\?]*)\??"): [
        "Do you think you should be able to {}?",
        "If you could {}, what would you do?",
        "I don't know -- why can't you {}?",
        "Have you really tried?",
    ],
    re.compile(r"i can'?t (.*)"): [
        "How do you know you can't {}?",
        "Perhaps you could {} if you tried.",
        "What would it take for you to {}?",
    ],
    re.compile(r"i am (.*)"): [
        "Did you come to me because you are {}?",
        "How long have you been {}?",
        "How do you feel about being {}?",
    ],
    re.compile(r"i'?m (.*)"): [
        "How does being {} make you feel?",
        "Do you enjoy being {}?",
        "Why do you tell me you're {}?",
        "Why do you think you're {}?",
    ],
    re.compile(r"are you ([^\?]*)\??"): [
        "Why does it matter whether I am {}?",
        "Would you prefer it if I were not {}?",
        "Perhaps you believe I am {}.",
        "I may be {} -- what do you think?",
    ],
    re.compile(r"what (.*)"): [
        "Why do you ask?",
        "How would an answer to that help you?",
        "What do you think?",
    ],
    re.compile(r"how (.*)"): [
        "How do you suppose?",
        "Perhaps you can answer your own question.",
        "What is it you're really asking?",
    ],
    re.compile(r"because (.*)"): [
        "Is that the real reason?",
        "What other reasons come to mind?",
        "Does that reason apply to anything else?",
        "If {}, what else must be true?",
    ],
    re.compile(r"(.*) sorry (.*)"): [
        "There are many times when no apology is needed.",
        "What feelings do you have when you apologize?",
    ],
    re.compile(r"^hello(.*)"): [
        "Hello...I'm glad you could drop by today.",
        "Hello there...how are you today?",
        "Hello, how are you feeling today?",
    ],
    re.compile(r"^hi(.*)"): [
        "Hello...I'm glad you could drop by today.",
        "Hi there...how are you today?",
        "Hello, how are you feeling today?",
    ],
    re.compile(r"^thanks(.*)"): ["You're welcome!", "Anytime!"],
    re.compile(r"^thank you(.*)"): ["You're welcome!", "Anytime!"],
    re.compile(r"^good morning(.*)"): [
        "Good morning...I'm glad you could drop by today.",
        "Good morning...how are you today?",
        "Good morning, how are you feeling today?",
    ],
    re.compile(r"^good afternoon(.*)"): [
        "Good afternoon...I'm glad you could drop by today.",
        "Good afternoon...how are you today?",
        "Good afternoon, how are you feeling today?",
    ],
    re.compile(r"I think (.*)"): [
        "Do you doubt {}?",
        "Do you really think so?",
        "But you're not sure {}?",
    ],
    re.compile(r"(.*) friend (.*)"): [
        "Tell me more about your friends.",
        "When you think of a friend, what comes to mind?",
        "Why don't you tell me about a childhood friend?",
    ],
    re.compile(r"yes"): ["You seem quite sure.", "OK, but can you elaborate a bit?"],
    re.compile(r"(.*) computer(.*)"): [
        "Are you really talking about me?",
        "Does it seem strange to talk to a computer?",
        "How do computers make you feel?",
        "Do you feel threatened by computers?",
    ],
    re.compile(r"is it (.*)"): [
        "Do you think it is {}?",
        "Perhaps it's {} -- what do you think?",
        "If it were {}, what would you do?",
        "It could well be that {}.",
    ],
    re.compile(r"it is (.*)"): [
        "You seem very certain.",
        "If I told you that it probably isn't {}, what would you feel?",
    ],
    re.compile(r"can you ([^\?]*)\??"): [
        "What makes you think I can't {}?",
        "If I could {}, then what?",
        "Why do you ask if I can {}?",
    ],
    re.compile(r"(.*)dream(.*)"): ["Tell me more about your dream."],
    re.compile(r"can I ([^\?]*)\??"): [
        "Perhaps you don't want to {}.",
        "Do you want to be able to {}?",
        "If you could {}, would you?",
    ],
    re.compile(r"you are (.*)"): [
        "Why do you think I am {}?",
        "Does it please you to think that I'm {}?",
        "Perhaps you would like me to be {}.",
        "Perhaps you're really talking about yourself?",
    ],
    re.compile(r"you'?re (.*)"): [
        "Why do you say I am {}?",
        "Why do you think I am {}?",
        "Are we talking about you, or me?",
    ],
    re.compile(r"i don'?t (.*)"): [
        "Don't you really {}?",
        "Why don't you {}?",
        "Do you want to {}?",
    ],
    re.compile(r"i feel (.*)"): [
        "Good, tell me more about these feelings.",
        "Do you often feel {}?",
        "When do you usually feel {}?",
        "When you feel {}, what do you do?",
        "Feeling {}? Tell me more.",
    ],
    re.compile(r"i have (.*)"): [
        "Why do you tell me that you've {}?",
        "Have you really {}?",
        "Now that you have {}, what will you do next?",
    ],
    re.compile(r"i would (.*)"): [
        "Could you explain why you would {}?",
        "Why would you {}?",
        "Who else knows that you would {}?",
    ],
    re.compile(r"is there (.*)"): [
        "Do you think there is {}?",
        "It's likely that there is {}.",
        "Would you like there to be {}?",
    ],
    re.compile(r"my (.*)"): [
        "I see, your {}.",
        "Why do you say that your {}?",
        "When your {}, how do you feel?",
    ],
    re.compile(r"you (.*)"): [
        "We should be discussing you, not me.",
        "Why do you say that about me?",
        "Why do you care whether I {}?",
    ],
    re.compile(r"why (.*)"): [
        "Why don't you tell me the reason why {}?",
        "Why do you think {}?",
    ],
    re.compile(r"i want (.*)"): [
        "What would it mean to you if you got {}?",
        "Why do you want {}?",
        "What would you do if you got {}?",
        "If you got {}, then what would you do?",
    ],
    re.compile(r"(.*) mother(.*)"): [
        "Tell me more about your mother.",
        "What was your relationship with your mother like?",
        "How do you feel about your mother?",
        "How does this relate to your feelings today?",
        "Good family relations are important.",
    ],
    re.compile(r"(.*) father(.*)"): [
        "Tell me more about your father.",
        "How did your father make you feel?",
        "How do you feel about your father?",
        "Does your relationship with your father relate to your feelings today?",
        "Do you have trouble showing affection with your family?",
    ],
    re.compile(r"(.*) child(.*)"): [
        "Did you have close friends as a child?",
        "What is your favorite childhood memory?",
        "Do you remember any dreams or nightmares from childhood?",
        "Did the other children sometimes tease you?",
        "How do you think your childhood experiences relate to your feelings today?",
    ],
    re.compile(r"(.*)\?"): [
        "Why do you ask that?",
        "Please consider whether you can answer your own question.",
        "Perhaps the answer lies within yourself?",
        "Why don't you tell me?",
    ],
}

_DEFAULT_RESPONSES: list[str] = [
    "Please tell me more.",
    "Let's change focus a bit...Tell me about your family.",
    "Can you elaborate on that?",
    "I see.",
    "Very interesting.",
    "I see. And what does that tell you?",
    "How does that make you feel?",
    "How do you feel when you say that?",
]

# A table to reflect words in question fragments inside the response.
# For example, the phrase "your jacket" in "I want your jacket" should be
# reflected to "my jacket" in the response.
_REFLECTED_WORDS: dict[str, str] = {
    "am": "are",
    "was": "were",
    "i": "you",
    "i'd": "you would",
    "i've": "you have",
    "i'll": "you will",
    "my": "your",
    "are": "am",
    "you've": "I have",
    "you'll": "I will",
    "your": "my",
    "yours": "mine",
    "you": "me",
    "me": "you",
}

_INTRO_RESPONSES: list[str] = [
    "Hi {}. I'm Eliza.",
    "Before we begin, {}, let me tell you something about myself.",
]

# A string array of facts about ELIZA.  Used in responses to Introduce, which is a server-stream.
_ELIZA_FACTS: list[str] = [
    "I was created by Joseph Weizenbaum.",
    "I was created in the 1960s.",
    "I am a Rogerian psychotherapist.",
    "I am named after Eliza Doolittle from the play Pygmalion.",
    "I was originally written on an IBM 7094.",
    "I can be accessed in most Emacs implementations with the command M-x doctor.",
    "I was created at the MIT Artificial Intelligence Laboratory.",
    "I was one of the first programs capable of attempting the Turing test.",
    "I was designed as a method to show the superficiality of communication between man and machine.",
]
