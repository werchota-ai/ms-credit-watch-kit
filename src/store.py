"""State and daily history: a private blob container in Azure, a local folder when run locally."""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error

from collect import Tokens, http

VER = {"x-ms-version": "2023-11-03"}


class Store:
    def __init__(self, tokens: Tokens, account: str | None = None, folder: str | None = None):
        self.tokens, self.account, self.folder = tokens, account, folder
        if folder:
            os.makedirs(os.path.join(folder, "history"), exist_ok=True)

    def _url(self, name: str) -> str:
        return f"https://{self.account}.blob.core.windows.net/state/{name}"

    def get(self, name: str):
        try:
            if self.account:
                return json.loads(http("GET", self._url(name), self.tokens.get("storage"), headers=VER, raw=True))
            p = os.path.join(self.folder, name)
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
        return None

    def put(self, name: str, obj) -> None:
        data = json.dumps(obj, indent=1).encode()
        if self.account:
            http("PUT", self._url(name), self.tokens.get("storage"), data,
                 headers={**VER, "x-ms-blob-type": "BlockBlob", "Content-Type": "application/json"}, raw=True)
        else:
            with open(os.path.join(self.folder, name), "wb") as f:
                f.write(data)

    # daily snapshots, one per day: history/YYYY-MM-DD.json
    def put_day(self, snap: dict) -> None:
        self.put(f"history/{snap['day']}.json", snap)

    def history(self, end: dt.date, days: int) -> dict[str, dict]:
        """Snapshots of the `days` days ending with `end` (missing days are skipped)."""
        out = {}
        for i in range(days):
            d = (end - dt.timedelta(days=i)).isoformat()
            s = self.get(f"history/{d}.json")
            if s:
                out[d] = s
        return dict(sorted(out.items()))
