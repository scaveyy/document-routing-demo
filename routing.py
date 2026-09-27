"""Plan document routing over invented messages. No files are moved."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


EXAMPLE = Path(__file__).parent / "examples" / "batch.json"
ID_PATTERN = re.compile(r"[A-Z0-9-]{3,40}\Z")
NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,79}\Z")
DESTINATION_PATTERN = re.compile(r"[a-z][a-z0-9_-]{0,39}\Z")
ALLOWED_SUFFIXES = {".pdf", ".docx", ".xlsx"}


class RoutingError(ValueError):
    """The input cannot be routed safely."""


@dataclass(frozen=True)
class Message:
    message_id: str
    category: str
    attachment_name: str
    content: str

    @property
    def fingerprint(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Rule:
    category: str
    destination: str


@dataclass(frozen=True)
class Decision:
    message_id: str
    status: str
    reason: str
    destination: str | None = None


def load_batch(path: Path = EXAMPLE) -> tuple[list[Message], list[Rule]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"messages", "rules"}:
        raise RoutingError("batch needs messages and rules")
    if not isinstance(raw["messages"], list) or not isinstance(raw["rules"], list):
        raise RoutingError("messages and rules must be lists")
    messages = []
    for index, row in enumerate(raw["messages"]):
        if (not isinstance(row, dict)
                or set(row) != {"message_id", "category", "attachment_name", "content"}
                or any(not isinstance(value, str) for value in row.values())):
            raise RoutingError(f"invalid message at index {index}")
        messages.append(Message(**row))
    rules = []
    for index, row in enumerate(raw["rules"]):
        if (not isinstance(row, dict) or set(row) != {"category", "destination"}
                or any(not isinstance(value, str) for value in row.values())):
            raise RoutingError(f"invalid rule at index {index}")
        rules.append(Rule(**row))
    return messages, rules


def validate_rules(rules: list[Rule]) -> None:
    for rule in rules:
        if (not rule.category.strip()
                or not DESTINATION_PATTERN.fullmatch(rule.destination)):
            raise RoutingError("invalid routing rule")


def valid_message(message: Message) -> bool:
    name = message.attachment_name
    return bool(
        ID_PATTERN.fullmatch(message.message_id)
        and message.category.strip()
        and message.content.strip()
        and NAME_PATTERN.fullmatch(name)
        and not name.endswith(".")
        and Path(name).suffix.lower() in ALLOWED_SUFFIXES
        and "/" not in name
        and "\\" not in name
    )


def plan_batch(
    messages: list[Message], rules: list[Rule], ledger: dict[str, str] | None = None
) -> tuple[list[Decision], dict[str, str]]:
    """Return a plan and proposed ledger. The caller performs any actual writes."""
    validate_rules(rules)
    if ledger is not None and not isinstance(ledger, dict):
        raise RoutingError("invalid ledger")
    next_ledger = dict(ledger or {})
    if any(not isinstance(key, str) or not isinstance(value, str)
           or not ID_PATTERN.fullmatch(key) or not re.fullmatch(r"[0-9a-f]{64}", value)
           for key, value in next_ledger.items()):
        raise RoutingError("invalid ledger")

    decisions = []
    for message in messages:
        if not valid_message(message):
            decisions.append(Decision(message.message_id, "review", "invalid_message"))
            continue
        old_fingerprint = next_ledger.get(message.message_id)
        if old_fingerprint == message.fingerprint:
            decisions.append(Decision(message.message_id, "skipped", "already_planned"))
            continue
        if old_fingerprint is not None:
            decisions.append(Decision(message.message_id, "review", "id_content_conflict"))
            continue
        matches = [rule for rule in rules if rule.category == message.category]
        if len(matches) != 1:
            reason = "no_rule" if not matches else "ambiguous_rules"
            decisions.append(Decision(message.message_id, "review", reason))
            continue
        destination = f"{matches[0].destination}/{message.message_id}-{message.attachment_name}"
        decisions.append(Decision(message.message_id, "ready", "one_matching_rule", destination))
        next_ledger[message.message_id] = message.fingerprint
    return decisions, next_ledger


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, default=EXAMPLE)
    args = parser.parse_args()
    messages, rules = load_batch(args.batch)
    decisions, ledger = plan_batch(messages, rules)
    print(json.dumps({"decisions": [asdict(item) for item in decisions], "proposed_ledger": ledger}, indent=2))


if __name__ == "__main__":
    main()
