class ApiConfig {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://werwines.onrender.com/',
  );
  static const String currencyCode = String.fromEnvironment(
    'CURRENCY_CODE',
    defaultValue: 'MK',
  );
}