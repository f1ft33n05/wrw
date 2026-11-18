import '../config/api_config.dart';

String formatMoney(double amount) {
  if (!amount.isFinite) return '${ApiConfig.currencyCode} $amount';

  final fixed = amount.abs().toStringAsFixed(2);
  final decimalIndex = fixed.indexOf('.');
  final wholePart = fixed.substring(0, decimalIndex);
  final groupedWholePart = wholePart.replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => ',',
  );
  final sign = amount < 0 ? '-' : '';

  return '${ApiConfig.currencyCode} $sign$groupedWholePart'
      '${fixed.substring(decimalIndex)}';
}
