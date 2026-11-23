/* Copyright (c) 2026 The Brave Authors. All rights reserved.
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at https://mozilla.org/MPL/2.0/. */

import * as React from 'react'

import { useWelcomeApi } from '../api/welcome_api_context'
import { useImportableProfiles } from './use_importable_profiles'
import {
  hasFeaturesAvailable,
  useProductFeatures,
} from './use_product_features'
import {
  hasMetricsAvailable,
  useAvailableMetrics,
} from './use_available_metrics'

const baseSteps = [
  'welcome',
  'import',
  'appearance',
  'features',
  'metrics',
] as const

export type Step = (typeof baseSteps)[number]

// Returns the current list of visible Welcome steps.
export function useStepList() {
  const promotionsEnabled = useWelcomeApi().usePromotionsEnabledData()
  const profiles = useImportableProfiles()
  const features = useProductFeatures()
  const metrics = useAvailableMetrics()

  return React.useMemo(() => {
    const hidden = new Set<Step>()

    if (!promotionsEnabled) {
      hidden.add('appearance')
    }

    if (!promotionsEnabled || !profiles?.length) {
      hidden.add('import')
    }

    if (!promotionsEnabled || !hasFeaturesAvailable(features)) {
      hidden.add('features')
    }

    // Hide the metrics step if there are no settable metrics.
    if (!hasMetricsAvailable(metrics)) {
      hidden.add('metrics')
    }

    return baseSteps.filter((step) => !hidden.has(step))
  }, [promotionsEnabled, profiles, features, metrics])
}
