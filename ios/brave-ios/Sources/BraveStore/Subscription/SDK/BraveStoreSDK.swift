// Copyright 2024 The Brave Authors. All rights reserved.
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

import BraveCore
import BraveShared
import Combine
import Foundation
import Preferences
import Shared
import StoreKit
import os.log

/// The Store Environment for use with Debugging APIs
public enum BraveStoreEnvironment: String {
  /// The production environment
  case production

  /// The sandbox environment
  case sandbox

  /// Xcode environment - A debugger is attached
  case xcode
}

/// A structure representing a Product Group offered by Brave's Store
public enum BraveStoreProductGroup: String, CaseIterable {
  #if !BRAVE_IOS_SLIM
  /// The group all VPN products belong to
  case vpn

  /// The group all Leo products belong to
  case leo
  #endif

  /// The group all Origin products belong to
  case origin

  /// The subscription group ID on App Store Connect
  public var subscriptionGroupID: String? {
    switch BraveSkusEnvironment.current {
    case .beta:
      switch self {
      #if !BRAVE_IOS_SLIM
      case .vpn: return "21497512"
      case .leo: return "21497453"
      #endif
      case .origin: return nil
      }
    case .nightly:
      switch self {
      #if !BRAVE_IOS_SLIM
      case .vpn: return "21497623"
      case .leo: return "21497565"
      #endif
      case .origin: return nil
      }
    case .release:
      switch self {
      #if !BRAVE_IOS_SLIM
      case .vpn: return "20621968"
      case .leo: return "21439231"
      #endif
      case .origin: return nil
      }
    }
  }

  /// The SKU's associated environment domain
  public var skusDomain: String {
    switch self {
    #if !BRAVE_IOS_SLIM
    case .vpn: return BraveDomains.serviceDomain(prefix: "vpn")
    case .leo:
      // AI Chat uses staging as its default in unofficial builds. The passed in environment is only
      // used in unofficial builds and when no service override switch is in place.
      return BraveDomains.serviceDomain(prefix: "leo", environment: .staging)
    #endif
    case .origin: return BraveDomains.serviceDomain(prefix: "origin")
    }
  }
}

/// A structure representing a Product offered by Brave's Store
public enum BraveStoreProduct: String, AppStoreProduct, CaseIterable {
  #if !BRAVE_IOS_SLIM
  /// VPN Monthly AppStore SKU
  case vpnMonthly

  /// VPN Yearly AppStore SKU
  case vpnYearly

  /// Leo Monthly AppStore SKU
  case leoMonthly

  /// Leo Yearly AppStore SKU
  case leoYearly
  #endif

  /// Origin One-Time Purchase AppStore SKU
  case originPurchase

  public init?(rawValue: String) {
    if let value = Self.allCases.first(where: { $0.rawValue == rawValue }) {
      self = value
      return
    }

    if let value = Self.allCases.first(where: { $0.itemSKU == rawValue }) {
      self = value
      return
    }

    return nil
  }

  /// The Title of the SKU Group
  public var subscriptionGroup: String {
    switch self {
    #if !BRAVE_IOS_SLIM
    case .vpnMonthly, .vpnYearly: return "Brave VPN"
    case .leoMonthly, .leoYearly: return "Brave Leo"
    #endif
    case .originPurchase: return "Brave Origin"
    }
  }

  /// The Brave Store's SKU
  public var itemSKU: String {
    // These are from the `Order.items.sku` and are NOT the same as the AppStore Skus
    // These are Brave's Skus
    switch self {
    #if !BRAVE_IOS_SLIM
    case .vpnMonthly: return "brave-vpn-premium"
    case .vpnYearly: return "brave-vpn-premium-year"
    case .leoMonthly: return "brave-leo-premium"
    case .leoYearly: return "brave-leo-premium-year"
    #endif
    case .originPurchase: return "brave-origin-premium-perpetual-license"
    }
  }

  /// The AppStore Product Subscription Group
  public var group: BraveStoreProductGroup {
    switch self {
    #if !BRAVE_IOS_SLIM
    case .vpnMonthly, .vpnYearly: return .vpn
    case .leoMonthly, .leoYearly: return .leo
    #endif
    case .originPurchase: return .origin
    }
  }

  /// The AppStore Product Subscription ID
  /// For release, there is no prefix.
  /// For nightly & beta, there is a prefix
  ///  - [beta | nightly].bravevpn.monthly
  ///  - [beta | nightly]].bravevpn.yearly
  ///  - [beta | nightly].braveleo.monthly
  ///  - [beta | nightly]].braveleo.yearly
  public var rawValue: String {
    var prefix: String {
      switch BraveSkusEnvironment.current {
      case .beta: return "beta."
      case .nightly: return "nightly."
      case .release: return ""
      }
    }

    var productId: String {
      switch self {
      #if !BRAVE_IOS_SLIM
      case .vpnMonthly, .vpnYearly: return "bravevpn"
      case .leoMonthly, .leoYearly: return "braveleo"
      #endif
      case .originPurchase: return "braveorigin"
      }
    }

    switch self {
    #if !BRAVE_IOS_SLIM
    case .vpnMonthly, .leoMonthly: return "\(prefix)\(productId).monthly"
    case .vpnYearly: return "\(prefix)\(productId).yearly"
    case .leoYearly:
      if BraveSkusEnvironment.current == .release {
        return "\(prefix)\(productId).yearly.2"
      }
      return "\(prefix)\(productId).yearly"
    #endif
    case .originPurchase: return "\(prefix)\(productId).perpetual"
    }
  }
}

/// A structure for handling Brave Store transactions, products, and purchases
public class BraveStoreSDK: AppStoreSDK {

  // MARK: - Error

  /// A BraveStoreSDK Error
  enum BraveStoreSDKError: Error {
    /// The product doesn't exist or there is a mismatch between the AppStore product and Brave's offered products
    case invalidProduct
  }

  // MARK: - LEO

  #if !BRAVE_IOS_SLIM
  /// The AppStore Leo Monthly Product offering
  @Published
  private(set) public var leoMonthlyProduct: Product?

  /// The AppStore Leo Monthly Product offering
  @Published
  private(set) public var leoYearlyProduct: Product?

  /// The AppStore Leo customer purchase Subscription Status
  @Published
  private(set) public var leoSubscriptionStatus: Product.SubscriptionInfo.Status?
  #endif

  // MARK: - ORIGIN

  /// The AppStore Origin One-Time Purchase Product offering
  @Published
  private(set) public var originPurchaseProduct: Product?

  // MARK: - Private

  /// All observers this uses
  private var observers = [AnyCancellable]()

  private let skusService: (any SkusSkusService)?

  public init(skusService: (any SkusSkusService)?) {
    self.skusService = skusService

    super.init()

    // Observe Product Updates
    observers.append($allProducts.sink(receiveValue: onProductsUpdated(_:)))

    // Observe Customer Purchase Updates
    observers.append($purchasedProducts.sink(receiveValue: onPurchasesUpdated(_:)))
  }

  // MARK: - Public

  private static func isOffered(_ product: BraveStoreProduct) -> Bool {
    #if BRAVE_IOS_SLIM
    product.group == .origin
    #else
    product.group != .vpn
    #endif
  }

  /// A list of all products the Brave Store offers
  public override var allAppStoreProducts: [any AppStoreProduct] {
    return BraveStoreProduct.allCases.filter(Self.isOffered)
  }

  /// The current store environment
  public var environment: BraveStoreEnvironment {
    if AppConstants.buildChannel == .release {
      return .production
    }

    #if BRAVE_IOS_SLIM
    // In slim builds there is no Leo subscription to read renewal info from.
    if Bundle.main.appStoreReceiptURL?.lastPathComponent == "sandboxReceipt" {
      return .sandbox
    }
    return .production
    #else
    // Retrieve the subscription renewal information
    guard
      let renewalInfo = leoSubscriptionStatus?.renewalInfo
    else {
      // There is currently no subscription so check if there was a restored receipt
      if Bundle.main.appStoreReceiptURL?.lastPathComponent == "sandboxReceipt" {
        return .sandbox
      }

      return .production
    }

    // Retrieve the current environment from StoreKit's Renewal Information
    switch renewalInfo {
    case .verified(let renewalInfo), .unverified(let renewalInfo, _):
      return .init(rawValue: renewalInfo.environment.rawValue) ?? .production
    }
    #endif
  }

  #if !BRAVE_IOS_SLIM
  /// A boolean indicating whether or not all the Leo product offerings has been loaded
  public var isLeoProductsLoaded: Bool {
    if leoMonthlyProduct != nil || leoYearlyProduct != nil {
      return true
    }

    return false
  }
  #endif

  /// A boolean indicating whether or not all the Origin product offerings has been loaded
  public var isOriginProductsLoaded: Bool {
    originPurchaseProduct != nil
  }

  /// Restores a single purchased product
  /// - Parameter product: The product whose purchase receipt to restore
  /// - Returns: Returns true if receipt restoration was successful. False otherwise
  public func restorePurchase(_ product: BraveStoreProduct) async -> Bool {
    guard Self.isOffered(product) else { return false }

    if await currentTransaction(for: product) != nil {
      try? await AppStoreReceipt.sync()
      do {
        try await self.updateSkusPurchaseState(for: product)
        return true
      } catch {
        return false
      }
    }

    return false
  }

  /// Restores all purchased products
  /// - Returns: Returns true if receipt restoration was successful. False otherwise
  @MainActor
  public func restorePurchases() async -> Bool {
    #if STOREKIT2
    var didRestore = false
    for await result in Transaction.currentEntitlements {
      if case .verified(let transaction) = result {
        if let product = BraveStoreProduct(rawValue: transaction.productID),
          Self.isOffered(product)
        {
          // Update subscription status for subscription products
          switch product {
          #if !BRAVE_IOS_SLIM
          case .vpnMonthly, .vpnYearly:
            continue
          case .leoMonthly, .leoYearly:
            leoSubscriptionStatus = await transaction.subscriptionStatus
          #endif
          case .originPurchase:
            // Non-consumable purchase, no subscription status
            break
          }

          // Update SkusSDK
          do {
            try await self.updateSkusPurchaseState(for: product)
            didRestore = true
          } catch {
            Logger.module.error(
              "[BraveStoreSDK] - Failed to restore purchased product receipt: \(error, privacy: .public)"
            )
          }
        }
      }
    }
    return didRestore
    #else
    do {
      for product in BraveStoreProduct.allCases where Self.isOffered(product) {
        try await self.updateSkusPurchaseState(for: product)
      }
      return true
    } catch {
      Logger.module.error(
        "[BraveStoreSDK] - Failed to restore purchased product receipt: \(error, privacy: .public)"
      )
      return false
    }
    #endif
  }

  /// Purchases the specified product using In-App purchases
  /// - Parameter product: The product the customer wishes to purchase
  /// - Throws: An exception if purchasing fails for any reason.
  ///           Purchase may be successful with the AppStore, but fail with SkusSDK.
  @MainActor
  @discardableResult
  public func purchase(product: BraveStoreProduct) async throws -> Bool {
    guard Self.isOffered(product) else { throw BraveStoreSDKError.invalidProduct }

    // Handle non-consumable purchases (Origin)
    if product == .originPurchase {
      if let nonConsumableProduct = await nonConsumablePurchase(for: product) {
        if try await super.purchase(nonConsumableProduct) != nil {
          Logger.module.info("[BraveStoreSDK] - Product Purchase Successful")
          return true
        }
      }
    } else {
      // Handle Leo subscriptions
      if let subscription = await subscription(for: product) {
        if try await super.purchase(subscription) != nil {
          Logger.module.info("[BraveStoreSDK] - Product Purchase Successful")
          return true
        }
      }
    }
    return false
  }

  /// Retrieves a non-consumable product from the loaded products
  /// - Parameter product: The product to retrieve
  /// - Returns: The non-consumable product if found
  private func nonConsumablePurchase(for product: any AppStoreProduct) async -> Product? {
    allProducts.nonConsumable.first(where: { $0.id == product.rawValue })
  }

  /// Processes the product purchase transaction with the SkusService
  /// If the transaction cannot be processed (receipt is empty or null), throw an exception
  /// - Parameter productId: The ID of the product that is currently being purchased
  override public func processPurchase(of productId: Product.ID) async throws {
    // Find the Brave offered product from the AppStore Product ID
    guard let product = BraveStoreProduct.allCases.first(where: {
      Self.isOffered($0) && productId == $0.rawValue
    })
    else {
      Logger.module.info("[BraveStoreSDK] - Not a Brave Product! - \(productId, privacy: .public)")
      throw BraveStoreSDKError.invalidProduct
    }

    // Update Skus SDK Purchase
    try await self.updateSkusPurchaseState(for: product)

    Logger.module.info("[BraveStoreSDK] - Purchase Successful")
  }

  // MARK: - Internal

  /// Observer function called when AppStore products have been fetched or updated
  private func onProductsUpdated(_ products: Products) {
    // Process subscriptions and non-consumable products
    let autoRenewableProducts = products.all.filter({ $0.type == .autoRenewable })
    let nonConsumableProducts = products.all.filter({ $0.type == .nonConsumable })

    // No products to process
    if autoRenewableProducts.isEmpty && nonConsumableProducts.isEmpty {
      return
    }

    #if !BRAVE_IOS_SLIM
    // Update leo products
    leoMonthlyProduct = autoRenewableProducts.first(where: {
      $0.id == BraveStoreProduct.leoMonthly.rawValue
    })
    leoYearlyProduct = autoRenewableProducts.first(where: {
      $0.id == BraveStoreProduct.leoYearly.rawValue
    })
    #endif

    // Update origin product
    originPurchaseProduct = nonConsumableProducts.first(where: {
      $0.id == BraveStoreProduct.originPurchase.rawValue
    })
  }

  /// Observer function called when AppStore customer purchased products have been fetched or updated
  private func onPurchasesUpdated(_ products: Products) {
    // Process subscriptions and non-consumable products
    let subscriptionProducts = products.all.filter({ $0.type == .autoRenewable }).filter({
      $0.subscription != nil
    })
    let nonConsumableProducts = products.all.filter({ $0.type == .nonConsumable })

    // No products to process
    if subscriptionProducts.isEmpty && nonConsumableProducts.isEmpty {
      return
    }

    Task { @MainActor [weak self] in
      guard let self = self else { return }

      #if !BRAVE_IOS_SLIM
      // Retrieve subscriptions
      let leoSubscriptions = subscriptionProducts.filter({
        $0.id == BraveStoreProduct.leoMonthly.rawValue
          || $0.id == BraveStoreProduct.leoYearly.rawValue
      })
      #endif

      // Retrieve non-consumable purchases
      let originPurchases = nonConsumableProducts.filter({
        $0.id == BraveStoreProduct.originPurchase.rawValue
      })

      #if !BRAVE_IOS_SLIM
      // Retrieve subscription statuses
      let leoSubscriptionsStatuses = leoSubscriptions.compactMap({ $0.subscription })

      // Statuses apply to the entire group
      leoSubscriptionStatus = try? await leoSubscriptionsStatuses.first?.status.first

      // Save subscription Ids
      Preferences.AIChat.subscriptionProductId.value = leoSubscriptions.first?.id
      #endif
      Preferences.BraveOrigin.purchaseProductId.value = originPurchases.first?.id

      // Once our backend allows restoring purchases `without` linking, we can get rid of this and just use `processTransaction`.
      #if BACKEND_SUPPORTS_IOS_MULTI_DEVICE_RESTORE

      // Restore product subscription if necessary
      #if BRAVE_IOS_SLIM
      if Preferences.BraveOrigin.purchaseOrderId.value == nil {
        _ = await restorePurchases()
      }
      #else
      if Preferences.AIChat.subscriptionOrderId.value == nil
        || Preferences.BraveOrigin.purchaseOrderId.value == nil
      {
        // We don't have a cached subscriptionOrderId
        // This means the product was purchased on a different device
        // So let's automatically restore it to this device as well
        _ = await restorePurchases()
      }
      #endif
      #endif
    }
  }

  /// Updates the Skus-SDK credentials and order information
  /// - Parameter product: The product whose information to update
  /// - Throws: An exception if updating the purchase information fails
  @MainActor
  private func updateSkusPurchaseState(for product: BraveStoreProduct) async throws {
    guard Self.isOffered(product) else { throw BraveStoreSDKError.invalidProduct }
    switch product.group {
    #if !BRAVE_IOS_SLIM
    case .vpn:
      throw BraveStoreSDKError.invalidProduct
    case .leo:
      Preferences.AIChat.subscriptionProductId.value = product.rawValue
    #endif
    case .origin:
      Preferences.BraveOrigin.purchaseProductId.value = product.rawValue
    }

    guard let skusService else {
      throw SkusError.skusServiceUnavailable
    }

    Logger.module.info("[BraveStoreSDK] - Syncing Receipt")

    // Attempt to update the Application Bundle's receipt, by force
    try await AppStoreReceipt.sync()

    if try AppStoreReceipt.receipt.isEmpty {
      Logger.module.error("[BraveStoreSDK] - Receipt is Empty")
      throw AppStoreReceipt.AppStoreReceiptError.invalidReceiptData
    }

    // Create a Skus-SDK for the specified product
    // Create an order for the AppStore receipt
    // If an order already exists, refreshes the order information
    let orderId = try await skusService.createOrder(for: product)

    // There is an order, and an expiry date, but no credentials
    // Fetch the credentials
    let skusResult = await skusService.fetchOrderCredentials(
      domain: product.group.skusDomain,
      orderId: orderId
    )
    if skusResult.code != .ok {
      Logger.module.info(
        "[SkusService] - Failed Fetching Credentials - \(skusResult.message, privacy: .public)"
      )
      throw SkusError.cannotFetchCredentials
    }

    // Store the Order-ID
    switch product.group {
    #if !BRAVE_IOS_SLIM
    case .vpn:
      break
    case .leo:
      Preferences.AIChat.subscriptionOrderId.value = orderId
    #endif
    case .origin:
      Preferences.BraveOrigin.purchaseOrderId.value = orderId
    }

    Logger.module.info("[BraveStoreSDK] - Order Completed")
  }
}
