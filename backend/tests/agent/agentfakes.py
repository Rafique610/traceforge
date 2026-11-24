"""Scripted gateway and canned diagnoses for agent tests (unique name: no conftest clash)."""

import json

from traceforge.agent.gateway import GatewayError, ModelResponse, ToolCall


def call(name, **args):
    return ToolCall(name=name, arguments=json.dumps(args))


def resp(*calls, content=None):
    return ModelResponse(
        content=content,
        tool_calls=list(calls),
        tokens_in=100,
        tokens_out=10,
        provider="ollama",
        model="fake",
    )


class FakeChat:
    """Scripted gateway: pops one item per call; an Exception item is raised."""

    def __init__(self, *script):
        self.script, self.messages, self.tools, self.kw = list(script), [], [], []

    def __call__(self, messages, tools=None, **kw):
        self.kw.append(kw)  # e.g. attempt_index
        self.messages.append(messages)
        self.tools.append(tools)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def n(self):
        return len(self.messages)


DIFF = "<<<<<<< SEARCH x.py\na\n=======\nb\n>>>>>>> REPLACE"
SUBMIT_CODE = call(
    "submit_diagnosis",
    cause_class="application_code",
    path="lab/shop_api/app/orders.py",
    qualname="order_total",
    supporting_evidence_ids=["EV-0001", "EV-0002"],
    rationale="items[0]",
)
SUBMIT_CFG = call(
    "submit_diagnosis",
    cause_class="configuration",
    config_key="worker.REDIS_HOST",
    supporting_evidence_ids=["EV-0002", "EV-0004"],
    rationale="typo in host",
)
PROVIDER_DOWN = GatewayError("cannot reach ollama (is it running?)")
