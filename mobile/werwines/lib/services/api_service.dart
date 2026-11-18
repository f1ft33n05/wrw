import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models.dart';

abstract interface class TokenStore {
  Future<String?> read();
  Future<void> write(String token);
  Future<void> delete();
}

class SecureTokenStore implements TokenStore {
  SecureTokenStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _tokenKey = 'access_token';
  final FlutterSecureStorage _storage;

  @override
  Future<String?> read() => _storage.read(key: _tokenKey);

  @override
  Future<void> write(String token) =>
      _storage.write(key: _tokenKey, value: token);

  @override
  Future<void> delete() => _storage.delete(key: _tokenKey);
}

class ApiException implements Exception {
  const ApiException(this.statusCode, this.message);

  final int statusCode;
  final String message;

  @override
  String toString() => message;
}

class ApiService {
  ApiService({http.Client? client, TokenStore? tokenStore, String? baseUrl})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? SecureTokenStore(),
      _baseUrl = baseUrl ?? ApiConfig.baseUrl;

  final http.Client _client;
  final TokenStore _tokenStore;
  final String _baseUrl;
  String? _token;

  bool get hasToken => _token != null;

  Future<void> restoreToken() async {
    _token = await _tokenStore.read();
  }

  Future<void> login(String username, String password) async {
    final response = await _client
        .post(
          _uri('/auth/token'),
          headers: const {'Accept': 'application/json'},
          body: {'username': username, 'password': password},
        )
        .timeout(const Duration(seconds: 15));
    final body = _decodeResponse(response);
    if (body is! Map) {
      throw const ApiException(
        502,
        'The server returned an invalid login response.',
      );
    }
    final token = body['access_token'];
    if (token is! String || token.isEmpty) {
      throw const ApiException(
        502,
        'The server returned an invalid login response.',
      );
    }
    await _tokenStore.write(token);
    _token = token;
  }

  Future<void> logout() async {
    _token = null;
    await _tokenStore.delete();
  }

  Future<List<CatalogueItem>> fetchCatalogue({int? eventId}) async {
    final path = eventId == null
        ? '/items/catalogue'
        : '/items/catalogue?event_id=$eventId';
    final data = await _get(path);
    if (data is! List) {
      throw const ApiException(
        502,
        'The server returned an invalid item catalogue.',
      );
    }
    return data
        .map(
          (item) =>
              CatalogueItem.fromJson(Map<String, dynamic>.from(item as Map)),
        )
        .toList();
  }

  Future<List<Customer>> fetchCustomers() async {
    final data = await _get('/contacts/?contact_type=customer');
    if (data is! List) {
      throw const ApiException(
        502,
        'The server returned an invalid customer list.',
      );
    }
    return data
        .map(
          (customer) =>
              Customer.fromJson(Map<String, dynamic>.from(customer as Map)),
        )
        .toList();
  }

  Future<List<ActiveEvent>> fetchActiveEvents() async {
    final data = await _get('/events/active');
    if (data is! List) {
      throw const ApiException(
        502,
        'The server returned an invalid event list.',
      );
    }
    return data
        .map(
          (event) =>
              ActiveEvent.fromJson(Map<String, dynamic>.from(event as Map)),
        )
        .toList();
  }

  Future<MobileProfile> fetchProfile() async {
    final data = await _get('/profile/data');
    if (data is! Map) {
      throw const ApiException(502, 'The server returned an invalid profile.');
    }
    return MobileProfile.fromJson(Map<String, dynamic>.from(data));
  }

  Future<MobileProfile> updateProfile({
    required String name,
    required String? email,
    required String? phone,
  }) async {
    final data = await _send(
      'PATCH',
      '/profile/data',
      payload: jsonEncode({'name': name, 'email': email, 'phone': phone}),
      extraHeaders: const {'Content-Type': 'application/json'},
    );
    if (data is! Map) {
      throw const ApiException(502, 'The server returned an invalid profile.');
    }
    return MobileProfile.fromJson(Map<String, dynamic>.from(data));
  }

  Future<DashboardSummary> fetchDashboard() async {
    final data = await _get('/sales/dashboard');
    if (data is! Map) {
      throw const ApiException(
        502,
        'The server returned an invalid dashboard.',
      );
    }
    return DashboardSummary.fromJson(Map<String, dynamic>.from(data));
  }

  Future<SalesHistoryPage> fetchSalesHistory({
    int offset = 0,
    int limit = 50,
  }) async {
    final data = await _get('/sales/history?offset=$offset&limit=$limit');
    if (data is! Map) {
      throw const ApiException(
        502,
        'The server returned an invalid sales history.',
      );
    }
    return SalesHistoryPage.fromJson(Map<String, dynamic>.from(data));
  }

  Future<SaleReceipt> fetchReceipt(int invoiceId) async {
    final data = await _get('/sales/$invoiceId/receipt/data');
    if (data is! Map) {
      throw const ApiException(502, 'The server returned an invalid receipt.');
    }
    return SaleReceipt.fromJson(Map<String, dynamic>.from(data));
  }

  Future<SaleQuote> quoteSale({
    required int? customerId,
    required Map<int, int> quantities,
    int? eventId,
  }) async {
    final data = await _postJson('/sales/quote', {
      'customer_id': customerId,
      'event_id': eventId,
      'location': eventId == null ? 'store' : 'event',
      'items': quantities.entries
          .map((entry) => {'item_id': entry.key, 'quantity': entry.value})
          .toList(),
      'amount_paid': 0,
      'payment_method': null,
      'discount_mode': 'automatic',
      'discount_value': null,
      'save_draft': false,
    });
    return SaleQuote.fromJson(data);
  }

  Future<SaleResult> createSale({
    required int? customerId,
    required Map<int, int> quantities,
    required String amountPaid,
    required String paymentMethod,
    required String idempotencyKey,
    int? eventId,
  }) async {
    final data = await _postJson(
      '/sales/create',
      {
        'customer_id': customerId,
        'event_id': eventId,
        'location': eventId == null ? 'store' : 'event',
        'items': quantities.entries
            .map((entry) => {'item_id': entry.key, 'quantity': entry.value})
            .toList(),
        'amount_paid': amountPaid,
        'payment_method': paymentMethod,
        'discount_mode': 'automatic',
        'discount_value': null,
        'save_draft': false,
      },
      extraHeaders: {'Idempotency-Key': idempotencyKey},
    );
    return SaleResult.fromJson(data);
  }

  Future<dynamic> _get(String path) => _send('GET', path);

  Future<Map<String, dynamic>> _postJson(
    String path,
    Map<String, dynamic> payload, {
    Map<String, String> extraHeaders = const {},
  }) async {
    final data = await _send(
      'POST',
      path,
      payload: jsonEncode(payload),
      extraHeaders: {'Content-Type': 'application/json', ...extraHeaders},
    );
    if (data is! Map) {
      throw const ApiException(502, 'The server returned an invalid response.');
    }
    return Map<String, dynamic>.from(data);
  }

  Future<dynamic> _send(
    String method,
    String path, {
    String? payload,
    Map<String, String> extraHeaders = const {},
  }) async {
    final headers = <String, String>{
      'Accept': 'application/json',
      if (_token != null) 'Authorization': 'Bearer $_token',
      ...extraHeaders,
    };
    final request = http.Request(method, _uri(path))..headers.addAll(headers);
    if (payload != null) {
      request.body = payload;
    }
    final streamedResponse = await _client
        .send(request)
        .timeout(const Duration(seconds: 20));
    final response = await http.Response.fromStream(streamedResponse);
    if (response.statusCode == 401) {
      await logout();
    }
    return _decodeResponse(response);
  }

  dynamic _decodeResponse(http.Response response) {
    dynamic body;
    try {
      body = response.body.isEmpty
          ? <String, dynamic>{}
          : jsonDecode(response.body);
    } on FormatException {
      throw ApiException(
        response.statusCode,
        'The server returned an unreadable response (${response.statusCode}).',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = body is Map ? body['detail'] : null;
      throw ApiException(
        response.statusCode,
        detail?.toString() ?? 'Request failed (${response.statusCode}).',
      );
    }
    if (body is! Map && body is! List) {
      throw const ApiException(502, 'The server returned an invalid response.');
    }
    return body is Map ? Map<String, dynamic>.from(body) : body;
  }

  Uri _uri(String path) =>
      Uri.parse('${_baseUrl.replaceFirst(RegExp(r'/$'), '')}$path');

  void close() => _client.close();
}
