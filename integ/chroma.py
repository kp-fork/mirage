import asyncio
import json
import re
import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mirage import MountMode, Workspace  # noqa: E402
from mirage.resource.chroma import ChromaConfig, ChromaResource  # noqa: E402

MOUNT = "/knowledge/"

PATH_TREE: dict[str, dict] = {
    "guides/quickstart.md": {
        "size": 180,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-02-01T00:00:00Z",
    },
    "guides/auth.md": {
        "size": 190,
        "created_at": "2026-01-15T00:00:00Z",
        "updated_at": "2026-02-15T00:00:00Z",
    },
    "policies/refunds.md": {
        "size": 150,
        "created_at": "2026-02-01T00:00:00Z",
        "updated_at": "2026-03-01T00:00:00Z",
    },
    "policies/privacy.md": {
        "size": 120,
        "created_at": "2026-02-10T00:00:00Z",
        "updated_at": "2026-03-10T00:00:00Z",
    },
    "CHANGELOG.md": {
        "size": 90,
    },
}

CHUNKS: dict[str, list[dict]] = {
    "guides/quickstart.md": [
        {
            "document":
            "Welcome to Acme. This quickstart gets you running fast.",
            "metadata": {
                "page_slug": "guides/quickstart.md",
                "chunk_index": 0
            },
        },
        {
            "document":
            "Install the CLI with npm i -g acme then run acme login.",
            "metadata": {
                "page_slug": "guides/quickstart.md",
                "chunk_index": 1
            },
        },
        {
            "document":
            "Set your token in the ACME_TOKEN environment variable.",
            "metadata": {
                "page_slug": "guides/quickstart.md",
                "chunk_index": 2
            },
        },
    ],
    "guides/auth.md": [
        {
            "document":
            "Authentication uses bearer tokens via the Authorization header.",
            "metadata": {
                "page_slug": "guides/auth.md",
                "chunk_index": 0
            },
        },
        {
            "document":
            "Requests are rate limited to 100 calls per minute per token.",
            "metadata": {
                "page_slug": "guides/auth.md",
                "chunk_index": 1
            },
        },
        {
            "document":
            "If you exceed the limit you receive HTTP 429 and must back off.",
            "metadata": {
                "page_slug": "guides/auth.md",
                "chunk_index": 2
            },
        },
    ],
    "policies/refunds.md": [
        {
            "document": "Refunds are available within 30 days of purchase.",
            "metadata": {
                "page_slug": "policies/refunds.md",
                "chunk_index": 0
            },
        },
        {
            "document": "Email support to start a refund with your order id.",
            "metadata": {
                "page_slug": "policies/refunds.md",
                "chunk_index": 1
            },
        },
        {
            "document":
            "Approved refunds are processed within five business days.",
            "metadata": {
                "page_slug": "policies/refunds.md",
                "chunk_index": 2
            },
        },
    ],
    "policies/privacy.md": [
        {
            "document":
            "Customer data is stored encrypted at rest and in transit.",
            "metadata": {
                "page_slug": "policies/privacy.md",
                "chunk_index": 0
            },
        },
        {
            "document": "You may request deletion of your data at any time.",
            "metadata": {
                "page_slug": "policies/privacy.md",
                "chunk_index": 1
            },
        },
    ],
    "CHANGELOG.md": [
        {
            "document": "v2.0 added rate limit headers and refund automation.",
            "metadata": {
                "page_slug": "CHANGELOG.md",
                "chunk_index": 0
            },
        },
        {
            "document": "v1.5 introduced encrypted data exports.",
            "metadata": {
                "page_slug": "CHANGELOG.md",
                "chunk_index": 1
            },
        },
    ],
}


class FakeCollection:

    def __init__(self) -> None:
        self.path_tree = json.dumps(PATH_TREE)
        self.get_count = 0
        self.query_count = 0

    async def get(self, **kwargs):
        self.get_count += 1
        ids = kwargs.get("ids")
        if ids == ["__path_tree__"]:
            return {"documents": [self.path_tree]}

        where = kwargs.get("where") or {}
        slug = where.get("page_slug")
        if isinstance(slug, dict):
            slug_in = slug.get("$in")
            slug_eq = slug.get("$eq")
            if slug_in is not None:
                where_doc = kwargs.get("where_document") or {}
                contains = where_doc.get("$contains")
                regex = where_doc.get("$regex")
                docs, metas = [], []
                for s in slug_in:
                    for chunk in CHUNKS.get(s, []):
                        document = chunk["document"]
                        if contains is not None:
                            matched = contains in document
                        elif regex is not None:
                            matched = re.search(regex, document) is not None
                        else:
                            matched = True
                        if matched:
                            docs.append(document)
                            metas.append(chunk["metadata"])
                return {"documents": docs, "metadatas": metas}
            slug = slug_eq

        if slug is not None:
            items = CHUNKS.get(slug, [])
            offset = kwargs.get("offset") or 0
            limit = kwargs.get("limit")
            if limit is not None:
                items = items[offset:offset + limit]
            elif offset:
                items = items[offset:]
            return {
                "documents": [c["document"] for c in items],
                "metadatas": [c["metadata"] for c in items],
            }
        return {"documents": [], "metadatas": []}

    async def query(self, **kwargs):
        self.query_count += 1
        query_texts = kwargs.get("query_texts", [""])[0]
        n_results = kwargs.get("n_results", 10)
        where = kwargs.get("where")
        scoped = None
        if where:
            scoped = set(where.get("page_slug", {}).get("$in", []))

        lowered = query_texts.lower()
        scored: list[tuple[float, str, str]] = []
        if "throttl" in lowered or "rate" in lowered or "429" in lowered:
            scored = [
                (0.08, "guides/auth.md",
                 "Requests are rate limited to 100 calls per minute per token."
                 ),
                (0.12, "guides/auth.md",
                 "If you exceed the limit you receive HTTP 429"
                 " and must back off."),
            ]
        elif "refund" in lowered or "money" in lowered:
            scored = [
                (0.09, "policies/refunds.md",
                 "Refunds are available within 30 days of purchase."),
                (0.16, "policies/refunds.md",
                 "Approved refunds are processed within five business days."),
            ]
        elif "encrypt" in lowered or "privacy" in lowered:
            scored = [
                (0.11, "policies/privacy.md",
                 "Customer data is stored encrypted at rest and in transit."),
            ]
        else:
            for slug, chunks in sorted(CHUNKS.items()):
                text = " ".join(c["document"] for c in chunks)
                scored.append((0.2, slug, text))

        if scoped is not None:
            scored = [(d, s, t) for d, s, t in scored if s in scoped]
        scored = scored[:n_results]

        return {
            "documents": [[t for _, _, t in scored]],
            "metadatas": [[{
                "page_slug": s
            } for _, s, _ in scored]],
            "distances": [[d for d, _, _ in scored]],
        }


async def _get_collection(collection):
    return collection


PER_MOUNT_CASES: list[tuple[str, str]] = [
    ("ls", "ls {root}"),
    ("ls_guides", "ls {root}guides/"),
    ("tree", "tree {root}"),
    ("find_md", "find {root} -name '*.md'"),
    ("find_type_f", "find {root} -type f | sort"),
    ("cat_auth", "cat {root}guides/auth.md"),
    ("cat_quickstart", "cat {root}guides/quickstart.md"),
    ("head_1", "head -n 1 {root}guides/quickstart.md"),
    ("tail_1", "tail -n 1 {root}guides/quickstart.md"),
    ("grep_429", "grep 429 {root}guides/auth.md"),
    ("grep_c_rate", "grep -c rate {root}guides/auth.md"),
    ("grep_r_refund", "grep -r refund {root}policies/"),
    ("grep_rl_encrypted", "grep -rl encrypted {root}"),
    ("grep_v_bearer", "grep -v bearer {root}guides/auth.md"),
    ("grep_rE_alternation", 'grep -rE "rate limited|refund" {root}'),
    ("wc_l_auth", "wc -l {root}guides/auth.md"),
    ("sort_auth", "sort {root}guides/auth.md"),
    ("uniq_auth", "uniq {root}guides/auth.md"),
    ("uniq_w0_auth", "uniq -w 0 {root}guides/auth.md"),
    ("stat_name_auth", 'stat -c "%n" {root}guides/auth.md'),
    ("cut_d_f1", "cut -d ' ' -f 1 {root}guides/quickstart.md"),
    ("awk_first_word", "awk '{{print $1}}' {root}guides/quickstart.md"),
    ("sed_upper_acme", "sed s/Acme/ACME/ {root}guides/quickstart.md"),
    ("rg_l_token", "rg -l token {root}"),
    ("pipe_cat_wc", "cat {root}guides/auth.md | wc -l"),
    ("pipe_sort_uniq_wc", "cat {root}policies/refunds.md | sort | uniq"
     " | wc -l"),
]

SEARCH_CASES: list[tuple[str, str]] = [
    ("search_throttle", 'search "how am I throttled" {root}'),
    ("search_scoped_refund", 'search "money back" {root}policies/'),
    ("search_encrypted", "search encrypted {root}"),
]


def _build_workspace() -> tuple[Workspace, FakeCollection]:
    collection = FakeCollection()
    config = ChromaConfig(
        host="localhost",
        port=8000,
        collection_name="knowledge",
    )
    resource = ChromaResource(config=config)
    resource.accessor._collection = collection
    resource.accessor.get_collection = partial(_get_collection, collection)
    ws = Workspace({MOUNT: resource}, mode=MountMode.READ)
    return ws, collection


async def _run(ws: Workspace, name: str, cmd: str) -> None:
    result = await ws.execute(cmd)
    out = await result.stdout_str()
    print(f"=== {name} ===")
    print(out, end="" if out.endswith("\n") else "\n")


async def main() -> None:
    ws, collection = _build_workspace()
    for name, tmpl in PER_MOUNT_CASES:
        await _run(ws, name, tmpl.format(root=MOUNT))
    for name, tmpl in SEARCH_CASES:
        await _run(ws, name, tmpl.format(root=MOUNT))


if __name__ == "__main__":
    asyncio.run(main())
