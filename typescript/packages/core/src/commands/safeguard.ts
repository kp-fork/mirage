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

import { CommandSafeguard } from '../types.ts'

const DEFAULT_MAX_LINES = 2000

export const DEFAULT_COMMAND_SAFEGUARDS: Record<string, CommandSafeguard> = Object.freeze(
  Object.fromEntries(
    ['cat', 'grep', 'rg', 'head', 'tail'].map((name) => [
      name,
      new CommandSafeguard({ maxLines: DEFAULT_MAX_LINES }),
    ]),
  ),
)

export function resolveSafeguard(
  name: string,
  commandDefault: CommandSafeguard | null = null,
  mountOverride: CommandSafeguard | null = null,
): CommandSafeguard | null {
  if (mountOverride !== null) return mountOverride
  if (commandDefault !== null) return commandDefault
  return DEFAULT_COMMAND_SAFEGUARDS[name] ?? null
}
