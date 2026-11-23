// Copyright 2022 The Brave Authors. All rights reserved.
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

import BraveCore
import BraveStore
import Foundation
import Preferences
import Shared
import os.log

extension SkusSkusService {
  @MainActor
  public func refreshSkusCredentials() async {
    #if BRAVE_IOS_SLIM
    let domains = [BraveStoreProductGroup.origin.skusDomain]
    #else
    let domains = BraveStoreProductGroup.allCases.filter { $0 != .vpn }.map(\.skusDomain)
    #endif
    for domain in domains {
      // Always refresh credentials and trust the credentials from Brave-Core rather than cached credentials
      let summary = await credentialSummary(domain: domain).message
      if !summary.isEmpty, summary != "{}" {
        await updatePreferences(for: domain, summaryData: Data(summary.utf8))
      }
    }
  }

  @MainActor
  func updatePreferences(for domain: String, summaryData: Data) async {
    do {
      let credentialSummary = try CredentialSummary.from(data: summaryData)
      let credentialType = CredentialType.from(domain: domain)
      switch credentialSummary.state {
      case .valid:
        switch credentialType {
        #if !BRAVE_IOS_SLIM
        case .leo:
          if Preferences.AIChat.subscriptionOrderId.value == nil {
            Preferences.AIChat.subscriptionOrderId.value = credentialSummary.orderId
          }
          Preferences.AIChat.subscriptionProductId.value = credentialSummary.product?.rawValue
        #endif
        case .origin:
          if Preferences.BraveOrigin.purchaseOrderId.value == nil {
            Preferences.BraveOrigin.purchaseOrderId.value = credentialSummary.orderId
          }
          Preferences.BraveOrigin.purchaseProductId.value = credentialSummary.product?.rawValue
        case .unknown:
          Logger.module.debug("[SkusManager] - Unknown Credentials")
          break
        }
      case .invalid:
        if !credentialSummary.active {
          Logger.module.debug("[SkusManager] - The credential summary is not active")
        }

        if credentialSummary.remainingCredentialCount <= 0 {
          Logger.module.debug(
            "[SkusManager] - The credential summary does not have any remaining credentials"
          )
        }
      case .sessionExpired:
        Logger.module.debug("[SkusManager] - This credential session has expired")
      }
    } catch {
      Logger.module.error("[SkusManager] - \(error)")
    }

  }
}

private enum CredentialType {
  case unknown
  #if !BRAVE_IOS_SLIM
  case leo
  #endif
  case origin

  static func from(domain: String) -> CredentialType {
    switch domain {
    #if !BRAVE_IOS_SLIM
    case "leo.brave.software", "leo.bravesoftware.com", "leo.brave.com": return .leo
    #endif
    case "origin.brave.software", "origin.bravesoftware.com", "origin.brave.com": return .origin
    default:
      return .unknown
    }
  }
}

private struct CredentialSummary {
  let expiresAt: Date?
  let active: Bool
  let remainingCredentialCount: Int
  let product: BraveStoreProduct?
  let orderId: String?

  static func from(data: Data) throws -> CredentialSummary {
    let summary = try jsonDecoder.decode(SkusCredentialSummary.self, from: data)
    let orderId = summary.order.id
    let expiresAt = summary.order.expiresAt
    let product = summary.order.items.compactMap({ BraveStoreProduct(rawValue: $0.sku) }).first
    return CredentialSummary(
      expiresAt: expiresAt,
      active: summary.active,
      remainingCredentialCount: Int(summary.remainingCredentialCount),
      product: product,
      orderId: orderId
    )
  }

  enum State {
    case valid
    case invalid
    case sessionExpired
  }

  var state: State {
    if active && remainingCredentialCount > 0 { return .valid }
    if active && remainingCredentialCount == 0 { return .sessionExpired }
    return .invalid
  }

  private static var jsonDecoder: JSONDecoder {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [
      .withYear,
      .withMonth,
      .withDay,
      .withTime,
      .withDashSeparatorInDate,
      .withColonSeparatorInTime,
    ]

    let decoder = JSONDecoder()
    decoder.keyDecodingStrategy = .convertFromSnakeCase
    decoder.dateDecodingStrategy = .custom({ decoder in
      let container = try decoder.singleValueContainer()
      let dateString = try container.decode(String.self)

      guard let date = formatter.date(from: try container.decode(String.self)) else {
        throw DecodingError.dataCorruptedError(
          in: container,
          debugDescription: "Cannot decode date string \(dateString)"
        )
      }

      return date
    })
    return decoder
  }
}
