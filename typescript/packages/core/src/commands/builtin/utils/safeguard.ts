// ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========

import { yieldBytes } from '../../../io/stream.ts'
import { type ByteSource, IOResult } from '../../../io/types.ts'
import { type CommandSafeguard, OnExceed } from '../../../types.ts'

const NEWLINE = 0x0a
const ENC = new TextEncoder()

function trimToLines(buf: Uint8Array, maxLines: number): Uint8Array {
  let count = 0
  for (let i = 0; i < buf.byteLength; i++) {
    if (buf[i] === NEWLINE) {
      count++
      if (count === maxLines) return buf.subarray(0, i + 1)
    }
  }
  return buf
}

function buildNotice(safeguard: CommandSafeguard): Uint8Array {
  const parts: string[] = []
  if (safeguard.maxLines !== null) parts.push(`${String(safeguard.maxLines)} lines`)
  if (safeguard.maxBytes !== null) parts.push(`${String(safeguard.maxBytes)} bytes`)
  const limit = parts.join(' / ')
  return ENC.encode(
    `output truncated at safeguard limit (${limit}); ` +
      `narrow with grep, or read more with head -n / tail -n / ` +
      `a more specific path\n`,
  )
}

function concat(chunks: Uint8Array[], total: number): Uint8Array {
  const out = new Uint8Array(total)
  let offset = 0
  for (const c of chunks) {
    out.set(c, offset)
    offset += c.byteLength
  }
  return out
}

function countNewlines(buf: Uint8Array): number {
  let n = 0
  for (let i = 0; i < buf.byteLength; i++) {
    if (buf[i] === NEWLINE) n++
  }
  return n
}

export async function applySafeguard(
  src: ByteSource,
  safeguard: CommandSafeguard | null,
): Promise<[ByteSource | null, IOResult]> {
  if (safeguard === null) return [src, new IOResult()]
  const { maxLines, maxBytes } = safeguard
  if (maxLines === null && maxBytes === null) return [src, new IOResult()]

  const chunks: Uint8Array[] = []
  let total = 0
  let newlineCount = 0
  let truncated = false

  const iterable: AsyncIterable<Uint8Array> = src instanceof Uint8Array ? yieldBytes(src) : src

  for await (const chunk of iterable) {
    chunks.push(chunk)
    total += chunk.byteLength
    if (maxLines !== null) newlineCount += countNewlines(chunk)
    if (maxBytes !== null && total > maxBytes) {
      truncated = true
      break
    }
    if (maxLines !== null && newlineCount >= maxLines) {
      truncated = true
      break
    }
  }

  let data = concat(chunks, total)
  if (maxBytes !== null && data.byteLength > maxBytes) {
    data = data.subarray(0, maxBytes)
  } else if (maxLines !== null && truncated) {
    data = trimToLines(data, maxLines)
  }

  if (!truncated) return [data, new IOResult()]
  const notice = buildNotice(safeguard)
  if (safeguard.onExceed === OnExceed.ERROR) {
    return [null, new IOResult({ exitCode: 1, stderr: notice })]
  }
  return [data, new IOResult({ stderr: notice })]
}
