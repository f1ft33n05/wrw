class ApiConfig {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://192.168.8.106:8000',
  );
  static const String currencyCode = String.fromEnvironment(
    'CURRENCY_CODE',
    defaultValue: 'MK',
  );
}