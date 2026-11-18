import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class MobileAppSettings {
  const MobileAppSettings({
    this.receiptTextScale = 1,
    this.showCashierName = true,
    this.showPaymentBreakdown = true,
  });

  final double receiptTextScale;
  final bool showCashierName;
  final bool showPaymentBreakdown;

  MobileAppSettings copyWith({
    double? receiptTextScale,
    bool? showCashierName,
    bool? showPaymentBreakdown,
  }) => MobileAppSettings(
    receiptTextScale: receiptTextScale ?? this.receiptTextScale,
    showCashierName: showCashierName ?? this.showCashierName,
    showPaymentBreakdown: showPaymentBreakdown ?? this.showPaymentBreakdown,
  );

  factory MobileAppSettings.fromJson(Map<String, dynamic> json) {
    final scale = json['receipt_text_scale'];
    if (scale is! num || !scale.isFinite) {
      throw const FormatException('Invalid receipt text size setting.');
    }
    final showCashierName = json['show_cashier_name'];
    final showPaymentBreakdown = json['show_payment_breakdown'];
    if (showCashierName is! bool || showPaymentBreakdown is! bool) {
      throw const FormatException('Invalid receipt display settings.');
    }
    return MobileAppSettings(
      receiptTextScale: scale.toDouble(),
      showCashierName: showCashierName,
      showPaymentBreakdown: showPaymentBreakdown,
    );
  }

  Map<String, dynamic> toJson() => {
    'receipt_text_scale': receiptTextScale,
    'show_cashier_name': showCashierName,
    'show_payment_breakdown': showPaymentBreakdown,
  };
}

abstract interface class AppSettingsStore {
  Future<MobileAppSettings> read();
  Future<void> write(MobileAppSettings settings);
}

class MobileSettingsStore implements AppSettingsStore {
  MobileSettingsStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _settingsKey = 'mobile_app_settings';
  final FlutterSecureStorage _storage;

  @override
  Future<MobileAppSettings> read() async {
    final value = await _storage.read(key: _settingsKey);
    if (value == null) return const MobileAppSettings();
    final decoded = jsonDecode(value);
    if (decoded is! Map) {
      throw const FormatException('Invalid saved app settings.');
    }
    return MobileAppSettings.fromJson(Map<String, dynamic>.from(decoded));
  }

  @override
  Future<void> write(MobileAppSettings settings) =>
      _storage.write(key: _settingsKey, value: jsonEncode(settings.toJson()));
}
