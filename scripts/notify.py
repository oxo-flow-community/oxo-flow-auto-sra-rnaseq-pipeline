#!/usr/bin/env python3
"""Port of the upstream scripts/utilize.py notification helpers
(feishu_notification verbatim; bark_notification fixed).

The upstream batch runner (run.py) sends a bark and/or feishu push after
each metadata file finishes. The oxo-flow port of that runner
(scripts/run_batch.py) calls these helpers.

Fidelity note: the upstream bark_notification body is
`base_url = api; content = quote(contents)` — it computes variables and
never sends anything (a silent no-op). The port implements the Bark push
API the same way feishu_notification works (HTTP request), so the
notification actually fires; everything else about the call shape is
unchanged.
"""

import json
from urllib import request
from urllib.parse import quote


def feishu_notification(api: str, contents: str):
    """Upstream scripts/utilize.py feishu_notification, verbatim."""
    req = request.Request(api, method="POST")  # this will make the method "POST"
    req.add_header('Content-Type', 'application/json')
    data_dict = {
        "msg_type": "text",
        "content": {"text": "进展报告: " + contents}
    }
    data = json.dumps(data_dict).encode()
    resp = request.urlopen(req, data=data)
    return resp


def bark_notification(api: str, contents: str):
    """Bark push notification (upstream no-op fixed, see module docstring).

    GET {api}/{title}/{content}; the title is fixed to 'oxo-flow' and the
    message is URL-encoded, mirroring how the upstream runner composed the
    message for feishu (single text payload).
    """
    url = api.rstrip("/") + "/oxo-flow/" + quote(contents)
    resp = request.urlopen(url)
    return resp


if __name__ == "__main__":
    import argparse
    import sys

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("channel", choices=["bark", "feishu"])
    p.add_argument("api", help="bark API base URL or feishu webhook URL")
    p.add_argument("contents")
    args = p.parse_args()

    try:
        if args.channel == "bark":
            bark_notification(args.api, args.contents)
        else:
            feishu_notification(args.api, args.contents)
        print(f"{args.channel} notification sent")
    except Exception as e:  # noqa: BLE001 — a notification must never fail a run
        print(f"unable to send {args.channel} notification: {e}", file=sys.stderr)
        sys.exit(1)
