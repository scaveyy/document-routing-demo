# Document routing with a review path

This Python demo plans where invented documents should go. It also shows when the safe answer is to stop and ask a person to review the item. All messages, rules, and destinations here are made up. There is no employer or client material and no connection to an email account or document system.

## Try it

Python 3.10 or later is enough. No packages, credentials, or network access are needed.

```sh
python3 -m unittest discover -s tests -v
python3 routing.py
```

The sample batch has three items: one clear route, one item with no rule, and one replay of the first item. The output shows `ready`, `review`, and `skipped`. Nothing is moved or written.

## What the code checks

1. Reject malformed input and unsafe rule destinations before planning.
2. Require an exact category match with one rule. Zero or multiple rules send the item to review.
3. Check the message ID and attachment name before making a destination. Unsafe names and unsupported file types go to review.
4. Use a content fingerprint to spot replays. If an ID returns with different content, send it to review instead of overwriting anything.
5. Return a proposed ledger with the decisions. The caller must only save that ledger **after** a real destination write succeeds. This demo does not perform that write or provide an atomic transaction.

The tests cover replay, changed content, ambiguous rules, unsafe paths, invalid ledgers, and the fact that planning does not write files. GitHub Actions runs the tests on pushes and pull requests.

## What this does not prove

This is a local routing planner. It does not read email, classify documents, write to SharePoint, authenticate users, or prove that a real file was delivered. The category in the input is supplied by the caller. A real workflow would need trusted input, destination permissions, an atomic write and ledger step, monitoring, and a human review queue. Those parts are outside this demo.
