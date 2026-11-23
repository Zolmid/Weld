// Copyright 2024 The Brave Authors. All rights reserved.
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

import BraveUI
import DesignSystem
import Preferences
import SwiftUI

struct UserScriptsDebugView: View {

  @ObservedObject
  private var blockAllScripts = Preferences.UserScript.blockAllScripts

  @ObservedObject
  private var cookieBlocking = Preferences.UserScript.cookieBlocking

  @ObservedObject
  private var mediaBackgroundPlay = Preferences.UserScript.mediaBackgroundPlay

  @ObservedObject
  private var mediaSource = Preferences.UserScript.mediaSource

  @ObservedObject
  private var playlist = Preferences.UserScript.playlist

  @ObservedObject
  private var deAmp = Preferences.UserScript.deAmp

  @ObservedObject
  private var requestBlocking = Preferences.UserScript.requestBlocking

  @ObservedObject
  private var trackingProtectionStats = Preferences.UserScript.trackingProtectionStats

  #if !BRAVE_IOS_SLIM
  @ObservedObject
  private var ethereumProvider = Preferences.UserScript.ethereumProvider

  @ObservedObject
  private var solanaProvider = Preferences.UserScript.solanaProvider
  #endif

  @ObservedObject
  private var youtubeQuality = Preferences.UserScript.youtubeQuality

  #if !BRAVE_IOS_SLIM
  @ObservedObject
  private var leo = Preferences.UserScript.leo
  #endif

  @ObservedObject
  private var translate = Preferences.UserScript.translate

  var body: some View {
    List {
      Section {
        Text("Enable or Disable Java-Script Features\n(Restart the app after toggling an option)")
          .font(.callout.bold())
          .fixedSize(horizontal: false, vertical: true)
          .frame(maxWidth: .infinity)
      }

      Section {
        Toggle("Block All (Everything below & more!)", isOn: $blockAllScripts.value)

        Toggle("Cookie Blocking", isOn: $cookieBlocking.value)

        Toggle("Background Play", isOn: $mediaBackgroundPlay.value)

        Toggle("Media Source", isOn: $mediaSource.value)

        Toggle("Playlist", isOn: $playlist.value)

        Toggle("DeAmp", isOn: $deAmp.value)

        Toggle("Request Blocking", isOn: $requestBlocking.value)

        Toggle("Tracking Protection Stats", isOn: $trackingProtectionStats.value)

        #if !BRAVE_IOS_SLIM
        Toggle("Ethereum Provider", isOn: $ethereumProvider.value)

        Toggle("Solana Provider", isOn: $solanaProvider.value)
        #endif

        Toggle("Youtube Quality", isOn: $youtubeQuality.value)

        #if !BRAVE_IOS_SLIM
        Toggle("Leo/AI-Chat", isOn: $leo.value)
        #endif

        Toggle("Brave Translate", isOn: $translate.value)
      }
      .font(.callout)
      .tint(Color(braveSystemName: .primary60))
    }
    .navigationTitle("Injected Scripts")
  }
}

#Preview {
  UserScriptsDebugView()
}
