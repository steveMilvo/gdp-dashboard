import 'package:flutter/foundation.dart';

/// Per-country runtime configuration. Spec §2: market term, currency,
/// payment provider, and notification channel must be configurable, never
/// hardcoded — so PalengGo (PH), PasarGo (ID/MY), TalatGo (TH), ChoGo (VN)
/// share the same codebase.
@immutable
class RegionConfig {
  const RegionConfig({
    required this.countryCode,
    required this.appName,
    required this.marketTerm,
    required this.currencyCode,
    required this.currencySymbol,
    required this.dialCode,
    required this.paymentProvider,
    required this.paymentProviderAlt,
    required this.notificationChannel,
    required this.riderTerm,
  });

  /// ISO 3166-1 alpha-2.
  final String countryCode;

  /// Brand name in this country (PalengGo, PasarGo, TalatGo, ChoGo).
  final String appName;

  /// Local word for "wet market".
  final String marketTerm;

  /// ISO 4217.
  final String currencyCode;
  final String currencySymbol;

  /// E.164 country code without `+` (e.g. `63` for PH).
  final String dialCode;

  /// Primary mobile-wallet provider key (e.g. `gcash`, `gopay`).
  final String paymentProvider;
  final String paymentProviderAlt;

  /// Primary messaging channel key (`viber`, `whatsapp`, `zalo`, `line`).
  final String notificationChannel;

  /// Local term for the delivery vehicle/operator.
  final String riderTerm;

  static const philippines = RegionConfig(
    countryCode: 'PH',
    appName: 'PalengGo',
    marketTerm: 'Palengke',
    currencyCode: 'PHP',
    currencySymbol: '₱', // ₱
    dialCode: '63',
    paymentProvider: 'gcash',
    paymentProviderAlt: 'maya',
    notificationChannel: 'viber',
    riderTerm: 'Trike',
  );

  // Future regional configs (added when expanding per spec §18.2):
  // static const indonesia = RegionConfig(...);  // PasarGo, GoPay, WhatsApp, Ojek
  // static const thailand  = RegionConfig(...);  // TalatGo, PromptPay, LINE
  // static const vietnam   = RegionConfig(...);  // ChoGo, MoMo, Zalo, Xe ôm
  // static const malaysia  = RegionConfig(...);  // PasarGo, DuitNow, WhatsApp
}
