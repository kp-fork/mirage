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

import { describe, expect, it, vi } from 'vitest'
import type * as ReaddirModule from './readdir.ts'

vi.mock('./readdir.ts', async () => {
  const actual = await vi.importActual<typeof ReaddirModule>('./readdir.ts')
  return { ...actual, readdir: vi.fn() }
})

import { DropboxAccessor } from '../../accessor/dropbox.ts'
import { PathSpec } from '../../types.ts'
import type { DropboxTokenManager } from './_client.ts'
import { find } from './find.ts'
import * as readdirMod from './readdir.ts'

const STUB_TM = {} as DropboxTokenManager

function makeAccessor(): DropboxAccessor {
  return new DropboxAccessor({ tokenManager: STUB_TM })
}

function mockTree(tree: Record<string, string[]>): void {
  vi.mocked(readdirMod.readdir).mockImplementation((_accessor, spec) => {
    const children = tree[spec.original]
    if (children === undefined) return Promise.reject(new Error(`ENOENT: ${spec.original}`))
    return Promise.resolve(children)
  })
}

const TREE: Record<string, string[]> = {
  '/': ['/docs/', '/notes.txt'],
  '/docs': ['/docs/readme.md', '/docs/inner/'],
  '/docs/inner': ['/docs/inner/deep.md'],
}

const ROOT = new PathSpec({ original: '/', directory: '/' })

describe('dropbox core find', () => {
  it('walks recursively returning files and dirs sorted without trailing slashes', async () => {
    mockTree(TREE)
    const out = await find(makeAccessor(), ROOT)
    expect(out).toEqual([
      '/docs',
      '/docs/inner',
      '/docs/inner/deep.md',
      '/docs/readme.md',
      '/notes.txt',
    ])
  })

  it('filters by name glob', async () => {
    mockTree(TREE)
    const out = await find(makeAccessor(), ROOT, { name: '*.md' })
    expect(out).toEqual(['/docs/inner/deep.md', '/docs/readme.md'])
  })

  it('filters by type f and type d', async () => {
    mockTree(TREE)
    const files = await find(makeAccessor(), ROOT, { type: 'f' })
    expect(files).toEqual(['/docs/inner/deep.md', '/docs/readme.md', '/notes.txt'])
    const dirs = await find(makeAccessor(), ROOT, { type: 'd' })
    expect(dirs).toEqual(['/docs', '/docs/inner'])
  })

  it('honors maxDepth and minDepth', async () => {
    mockTree(TREE)
    const shallow = await find(makeAccessor(), ROOT, { maxDepth: 1 })
    expect(shallow).toEqual(['/docs', '/notes.txt'])
    const deep = await find(makeAccessor(), ROOT, { minDepth: 2 })
    expect(deep).toEqual(['/docs/inner', '/docs/inner/deep.md', '/docs/readme.md'])
  })

  it('strips the mount prefix from returned keys', async () => {
    mockTree({
      '/mnt/dbx': ['/mnt/dbx/docs/', '/mnt/dbx/notes.txt'],
      '/mnt/dbx/docs': ['/mnt/dbx/docs/readme.md'],
    })
    const root = new PathSpec({ original: '/mnt/dbx', directory: '/mnt/dbx', prefix: '/mnt/dbx' })
    const out = await find(makeAccessor(), root)
    expect(out).toEqual(['/docs', '/docs/readme.md', '/notes.txt'])
  })
})
