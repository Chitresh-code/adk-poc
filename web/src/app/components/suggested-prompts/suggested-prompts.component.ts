/**
 * @license
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import {ChangeDetectionStrategy, Component, EventEmitter, Output, computed, input} from '@angular/core';
import {MatChipsModule} from '@angular/material/chips';

/**
 * Extracts the bullet list under a "## Try asking" heading in an agent's
 * README.md and renders each item as a clickable chip. Selecting one fills
 * the chat input (via promptSelected) without sending it, so it can still
 * be reviewed or edited first.
 */
@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-suggested-prompts',
  standalone: true,
  imports: [MatChipsModule],
  templateUrl: './suggested-prompts.component.html',
  styleUrls: ['./suggested-prompts.component.scss'],
})
export class SuggestedPromptsComponent {
  readonly readme = input<string>('');
  @Output() readonly promptSelected = new EventEmitter<string>();

  readonly prompts = computed(() => parseTryAskingPrompts(this.readme()));
}

const TRY_ASKING_HEADING = '## try asking';

function parseTryAskingPrompts(readme: string): string[] {
  const lines = readme.split('\n');
  const headingIndex = lines.findIndex(
      (line) => line.trim().toLowerCase() === TRY_ASKING_HEADING);
  if (headingIndex === -1) {
    return [];
  }

  const prompts: string[] = [];
  for (let i = headingIndex + 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith('#')) {
      break;
    }
    const match = line.match(/^[-*]\s+(.*)$/);
    if (match) {
      prompts.push(match[1].trim().replace(/^"(.*)"$/, '$1'));
    }
  }
  return prompts;
}
