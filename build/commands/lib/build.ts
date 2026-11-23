// Copyright (c) 2017 The Brave Authors. All rights reserved.
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this file,
// You can obtain one at https://mozilla.org/MPL/2.0/.

import config from './config.ts'
import util from './util.ts'
import branding from './branding.js'
import type * as buildOptions from './buildOptions.ts'
import * as buildUtils from './buildUtils.ts'

export async function build(
  buildConfig = config.defaultBuildConfig,
  options: buildOptions.BuildDirOptions
    & buildOptions.TargetConfigOptions
    & buildOptions.GnArgsOptions
    & buildOptions.GnGenOptions
    & buildOptions.NinjaOptions & { slim?: boolean },
) {
  config.buildConfig = buildConfig
  config.update(
    options.slim
      ? {
          ...options,
          gn: [
            ...(options.gn ?? []),
            'enable_ai_chat:false',
            'enable_local_ai:false',
            'enable_brave_wallet:false',
            'enable_brave_rewards:false',
            'enable_brave_ads:false',
            'enable_brave_promotions:false',
            'enable_brave_vpn_v1:false',
            'enable_brave_vpn_v2:false',
          ],
        }
      : options,
  )
  buildUtils.checkVersionsMatch()

  util.touchOverriddenFiles()
  branding.update()
  buildUtils.ensureVsFilesMount()

  if (options.prepare_only) {
    return
  }

  if (config.xcode_gen_target) {
    util.generateXcodeWorkspace()
  } else {
    if (!config.use_no_gn_gen) {
      await util.generateNinjaFiles()
    }
    await util.buildTargets()
  }
}
