/* Copyright (c) 2020 The Brave Authors. All rights reserved.
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at https://mozilla.org/MPL/2.0/. */

#include "brave/ios/browser/profile/model/brave_keyed_service_factories.h"

#include "brave/components/ai_chat/core/common/buildflags/buildflags.h"
#include "brave/components/brave_account/features.h"
#include "brave/components/brave_ads/buildflags/buildflags.h"
#include "brave/components/brave_wallet/common/buildflags/buildflags.h"
#include "brave/ios/browser/api/webcompat_reporter/webcompat_reporter_service_factory.h"
#include "brave/ios/browser/brave_account/brave_account_service_factory_ios.h"
#include "brave/ios/browser/brave_origin/brave_origin_service_factory.h"
#include "brave/ios/browser/brave_shields/brave_shields_settings_service_factory.h"
#include "brave/ios/browser/debounce/debounce_service_factory+private.h"
#include "brave/ios/browser/favicon/brave_ios_favicon_loader_factory.h"
#include "brave/ios/browser/serp_metrics/serp_metrics_service_factory_ios.h"
#include "brave/ios/browser/skus/skus_service_factory.h"
#include "brave/ios/browser/url_sanitizer/url_sanitizer_service_factory+private.h"

#if BUILDFLAG(ENABLE_AI_CHAT)
#include "brave/ios/browser/ai_chat/ai_chat_service_factory.h"
#include "brave/ios/browser/ai_chat/model_service_factory.h"
#include "brave/ios/browser/ai_chat/tab_tracker_service_factory.h"
#include "brave/ios/browser/misc_metrics/profile_misc_metrics_service_factory.h"
#endif  // BUILDFLAG(ENABLE_AI_CHAT)

#if BUILDFLAG(ENABLE_BRAVE_ADS)
#include "brave/ios/browser/brave_ads/ads_service_factory_ios.h"
#endif  // BUILDFLAG(ENABLE_BRAVE_ADS)

#if BUILDFLAG(ENABLE_BRAVE_WALLET)
#include "brave/ios/browser/brave_wallet/brave_wallet_service_factory.h"
#endif  // BUILDFLAG(ENABLE_BRAVE_WALLET)

namespace brave {

void EnsureProfileKeyedServiceFactoriesBuilt() {
#if BUILDFLAG(ENABLE_AI_CHAT)
  misc_metrics::ProfileMiscMetricsServiceFactory::GetInstance();
  ai_chat::ModelServiceFactory::GetInstance();
  ai_chat::AIChatServiceFactory::GetInstance();
  ai_chat::TabTrackerServiceFactory::GetInstance();
#endif  // BUILDFLAG(ENABLE_AI_CHAT)
  if (brave_account::features::IsBraveAccountEnabled()) {
    brave_account::BraveAccountServiceFactoryIOS::GetInstance();
  }
#if BUILDFLAG(ENABLE_BRAVE_ADS)
  brave_ads::AdsServiceFactoryIOS::GetInstance();
#endif  // BUILDFLAG(ENABLE_BRAVE_ADS)
  serp_metrics::SerpMetricsServiceFactoryIOS::GetInstance();
  brave_favicon::BraveIOSFaviconLoaderFactory::GetInstance();
  brave_origin::BraveOriginServiceFactory::GetInstance();
  brave_shields::BraveShieldsSettingsServiceFactory::GetInstance();
#if BUILDFLAG(ENABLE_BRAVE_WALLET)
  brave_wallet::BraveWalletServiceFactory::GetInstance();
#endif  // BUILDFLAG(ENABLE_BRAVE_WALLET)
  skus::SkusServiceFactory::GetInstance();
  brave::URLSanitizerServiceFactory::GetInstance();
  debounce::DebounceServiceFactory::GetInstance();
  webcompat_reporter::WebcompatReporterServiceFactory::GetInstance();
}

}  // namespace brave
