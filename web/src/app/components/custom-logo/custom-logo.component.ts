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

import {ChangeDetectionStrategy, Component, computed, inject} from '@angular/core';

import {THEME_SERVICE} from '../../core/services/interfaces/theme';
import {RuntimeConfigUtil} from '../../../utils/runtime-config-util';

/** Logo component to override the default logo. */
@Component({
  changeDetection: ChangeDetectionStrategy.Default,
  selector: 'app-custom-logo',
  standalone: true,
  templateUrl: './custom-logo.component.html',
  styleUrls: ['./custom-logo.component.scss'],
})
export class CustomLogoComponent {
  private readonly themeService = inject(THEME_SERVICE);
  readonly logoConfig = RuntimeConfigUtil.getRuntimeConfig().logo;

  readonly imageUrl = computed(() => {
    const theme = this.themeService.currentTheme();
    const variant = theme === 'light' ?
        this.logoConfig?.imageUrlLight :
        this.logoConfig?.imageUrlDark;
    return variant || this.logoConfig?.imageUrl;
  });
}
