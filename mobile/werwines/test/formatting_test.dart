import 'package:flutter_test/flutter_test.dart';
import 'package:werwines/config/api_config.dart';
import 'package:werwines/utils/formatting.dart';

void main() {
  test('formats money with comma-separated thousands', () {
    expect(formatMoney(1234567.8), '${ApiConfig.currencyCode} 1,234,567.80');
    expect(formatMoney(-1234.5), '${ApiConfig.currencyCode} -1,234.50');
    expect(formatMoney(12), '${ApiConfig.currencyCode} 12.00');
  });
}
