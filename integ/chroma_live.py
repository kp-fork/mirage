# ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========

import asyncio
import base64
import gzip
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import chromadb  # noqa: E402

from chroma import CHUNKS, MOUNT, PATH_TREE, PER_MOUNT_CASES  # noqa: E402

from mirage import MountMode, Workspace  # noqa: E402
from mirage.resource.chroma import ChromaConfig, ChromaResource  # noqa: E402

CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8000"))
EMBED_DIM = 8


def encoded_path_tree() -> str:
    # gzip+base64 variant so the live run covers parse_path_tree's
    # encoded branch (the fake harness seeds plain JSON)
    raw = json.dumps(PATH_TREE).encode()
    return base64.b64encode(gzip.compress(raw)).decode()


def embedding_for(position: int) -> list[float]:
    vector = [0.0] * EMBED_DIM
    vector[position % EMBED_DIM] = 1.0
    return vector


async def seed_collection(collection_name: str) -> None:
    client = await chromadb.AsyncHttpClient(host=CHROMA_HOST,
                                            port=CHROMA_PORT)
    collection = await client.create_collection(collection_name)
    ids = ["__path_tree__"]
    documents = [encoded_path_tree()]
    metadatas: list[dict] = [{"kind": "path_tree"}]
    embeddings = [embedding_for(0)]
    position = 1
    for chunks in CHUNKS.values():
        for chunk in chunks:
            slug = chunk["metadata"]["page_slug"]
            index = chunk["metadata"]["chunk_index"]
            ids.append(f"{slug}#{index}")
            documents.append(chunk["document"])
            metadatas.append(chunk["metadata"])
            embeddings.append(embedding_for(position))
            position += 1
    await collection.add(ids=ids,
                         documents=documents,
                         metadatas=metadatas,
                         embeddings=embeddings)


async def run_case(ws: Workspace, name: str, cmd: str) -> None:
    result = await ws.execute(cmd)
    out = await result.stdout_str()
    print(f"=== {name} ===")
    print(out, end="" if out.endswith("\n") else "\n")


async def main() -> None:
    collection_name = f"mirage-integ-{uuid.uuid4().hex[:8]}"
    await seed_collection(collection_name)
    config = ChromaConfig(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
        collection_name=collection_name,
    )
    ws = Workspace({MOUNT: ChromaResource(config=config)},
                   mode=MountMode.READ)
    # SEARCH_CASES are excluded: query_texts needs an embedding function,
    # which the thin client deliberately does not bundle. Vector search
    # stays covered by the FakeCollection harness in chroma.py.
    for name, tmpl in PER_MOUNT_CASES:
        await run_case(ws, name, tmpl.format(root=MOUNT))


if __name__ == "__main__":
    asyncio.run(main())
