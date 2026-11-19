import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:werwines/main.dart';
import 'package:werwines/services/api_service.dart';
import 'package:werwines/screens/settings_store.dart';

class _MemoryTokenStore implements TokenStore {
  String? token;

  @override
  Future<String?> read() async => token;

  @override
  Future<void> write(String value) async => token = value;

  @override
  Future<void> delete() async => token = null;
}

class _MemorySettingsStore implements AppSettingsStore {
  MobileAppSettings settings = const MobileAppSettings();

  @override
  Future<MobileAppSettings> read() async => settings;

  @override
  Future<void> write(MobileAppSettings value) async => settings = value;
}

void main() {
  testWidgets('cashier signs in, quotes a cart, and completes a sale', (
    WidgetTester tester,
  ) async {
    Map<String, dynamic>? submittedSale;
    String? idempotencyKey;
    final salesHistoryQueries = <Map<String, String>>[];
    final client = MockClient((request) async {
      final httpRequest = request;
      if (httpRequest.url.path == '/auth/token') {
        expect(
          httpRequest.headers['content-type'],
          contains('application/x-www-form-urlencoded'),
        );
        expect(httpRequest.body, contains('username=cashier'));
        return http.Response(
          jsonEncode({'access_token': 'test-token', 'token_type': 'bearer'}),
          200,
        );
      }
      if (httpRequest.headers['authorization'] != 'Bearer test-token') {
        return http.Response(jsonEncode({'detail': 'Unauthorized'}), 401);
      }
      switch (httpRequest.url.path) {
        case '/events/active':
          return http.Response(
            jsonEncode([
              {'id': 3, 'name': 'Test Event', 'venue': 'Cellar'},
            ]),
            200,
          );
        case '/profile/data':
          final profile = {
            'id': 1,
            'name': 'Cashier User',
            'username': 'cashier',
            'email': 'cashier@example.com',
            'phone': '123',
            'role': 'cashier',
          };
          if (httpRequest.method == 'PATCH') {
            final body = jsonDecode(httpRequest.body) as Map<String, dynamic>;
            profile['name'] = body['name'] as String;
          }
          return http.Response(jsonEncode(profile), 200);
        case '/sales/dashboard':
          return http.Response(
            jsonEncode({
              'total_paid_today': '20.00',
              'transaction_count_today': 2,
              'recent_sales': [
                {
                  'invoice_id': 44,
                  'invoice_number': 'INV-2026-00044',
                  'receipt_number': 'RCT-2026-00044',
                  'created_at': '2026-11-18T10:00:00+02:00',
                  'customer_name': 'Walk-in customer',
                  'status': 'paid',
                  'total_amount': '10.00',
                  'amount_paid': '10.00',
                  'balance_due': '0.00',
                  'item_count': 1,
                  'payment_methods': ['cash'],
                },
              ],
            }),
            200,
          );
        case '/sales/history':
          salesHistoryQueries.add(request.url.queryParameters);
          return http.Response(
            jsonEncode({
              'sales': [
                {
                  'invoice_id': 44,
                  'invoice_number': 'INV-2026-00044',
                  'receipt_number': 'RCT-2026-00044',
                  'created_at': '2026-11-18T10:00:00+02:00',
                  'customer_name': 'Walk-in customer',
                  'status': 'paid',
                  'total_amount': '10.00',
                  'amount_paid': '10.00',
                  'balance_due': '0.00',
                  'item_count': 1,
                  'payment_methods': ['cash'],
                },
              ],
              'next_offset': null,
            }),
            200,
          );
        case '/sales/44/receipt/data':
          return http.Response(
            jsonEncode({
              'invoice_id': 44,
              'invoice_number': 'INV-2026-00044',
              'receipt_number': 'RCT-2026-00044',
              'status': 'paid',
              'created_at': '2026-11-18T10:00:00+02:00',
              'customer_name': 'Walk-in customer',
              'event_name': null,
              'cashier_name': 'Cashier',
              'lines': [
                {
                  'name': 'Cabernet',
                  'description': 'Cabernet',
                  'quantity': '1',
                  'unit_prices': [
                    {
                      'quantity': '1',
                      'price_type': 'retail',
                      'unit_price': '10.00',
                    },
                  ],
                  'total': '10.00',
                },
              ],
              'payments': [
                {
                  'created_at': '2026-11-18T10:00:00+02:00',
                  'payment_method': 'cash',
                  'amount': '10.00',
                  'change_amount': '0.00',
                },
              ],
              'subtotal': '10.00',
              'discount_amount': '0.00',
              'total_amount': '10.00',
              'amount_paid': '10.00',
              'balance_due': '0.00',
              'change_amount': '0.00',
            }),
            200,
          );
        case '/items/catalogue':
          return http.Response(
            jsonEncode([
              {
                'id': 7,
                'name': 'Cabernet',
                'barcode': '123',
                'selling_price_retail': 10.0,
                'selling_price_wholesale': 8.0,
                'wholesale_threshold': '6',
                'quantity': 5,
                'unit': 'bottle',
              },
            ]),
            200,
          );
        case '/contacts/':
          return http.Response('[]', 200);
        case '/sales/quote':
          return http.Response(
            jsonEncode({
              'subtotal': '10.00',
              'discount_amount': '0.00',
              'total_amount': '10.00',
              'items': [],
            }),
            200,
          );
        case '/sales/create':
          submittedSale = jsonDecode(httpRequest.body) as Map<String, dynamic>;
          idempotencyKey = httpRequest.headers['Idempotency-Key'];
          return http.Response(
            jsonEncode({
              'invoice_id': 44,
              'invoice_number': 'INV-2026-00044',
              'receipt_number': 'RCT-2026-00044',
              'total_amount': '10.00',
              'amount_paid': '10.00',
              'change_amount': '10.00',
              'balance_due': '0.00',
              'receipt_url': '/sales/44/receipt',
            }),
            201,
          );
        default:
          return http.Response(
            jsonEncode({'detail': 'Unexpected route ${httpRequest.url.path}'}),
            404,
          );
      }
    });
    final api = ApiService(
      client: client,
      tokenStore: _MemoryTokenStore(),
      baseUrl: 'http://test',
    );

    final settingsStore = _MemorySettingsStore();
    await tester.pumpWidget(
      WerwinesApp(apiService: api, settingsStore: settingsStore),
    );
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('username')), 'cashier');
    await tester.enterText(find.byKey(const ValueKey('password')), 'secret');
    await tester.tap(find.byKey(const ValueKey('sign-in')));
    await tester.pumpAndSettle();

    expect(find.text('WeRWines'), findsOneWidget);
    expect(find.text('Paid Sales'), findsOneWidget);
    expect(find.text('Store'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('profile-avatar')));
    await tester.pumpAndSettle();
    expect(find.text('Profile'), findsOneWidget);
    expect(find.text('@cashier · cashier'), findsOneWidget);
    await tester.enterText(
      find.byKey(const ValueKey('profile-name')),
      'Alex Cashier',
    );
    await tester.tap(find.text('Save profile'));
    await tester.pumpAndSettle();
    expect(find.text('Profile updated.'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('active-location')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Test Event (Cellar)').last);
    await tester.pumpAndSettle();
    expect(find.text('Selling from: Test Event'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('nav-receipts')));
    await tester.pumpAndSettle();
    expect(find.text('Sale #RCT-2026-00044'), findsOneWidget);
    expect(find.byKey(const ValueKey('export-sales-report')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('sales-period-filter')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Yesterday').last);
    await tester.pumpAndSettle();
    expect(salesHistoryQueries, hasLength(2));
    expect(salesHistoryQueries.last, containsPair('date_from', isNotEmpty));
    expect(salesHistoryQueries.last, containsPair('date_to', isNotEmpty));
    expect(find.text('Sale #RCT-2026-00044'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('sale-44')));
    await tester.pumpAndSettle();
    expect(find.text('Receipt #RCT-2026-00044'), findsOneWidget);
    expect(find.text('Cabernet'), findsOneWidget);
    expect(find.byTooltip('Share receipt'), findsOneWidget);
    expect(find.byTooltip('Print receipt'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('nav-settings')));
    await tester.pumpAndSettle();
    expect(find.text('Receipt settings'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('receipt-font-size')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Large').last);
    await tester.pumpAndSettle();
    expect(settingsStore.settings.receiptTextScale, 1.15);

    await tester.tap(find.byKey(const ValueKey('nav-pos')));
    await tester.pumpAndSettle();
    expect(find.text('Cabernet'), findsOneWidget);
    await tester.tap(find.byTooltip('Add Cabernet'));
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('review-cart')));
    await tester.pumpAndSettle();

    expect(find.text('Total due'), findsOneWidget);
    await tester.enterText(
      find.byKey(const ValueKey('amount-received')),
      '20.00',
    );
    tester.testTextInput.hide();
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('complete-sale')));
    await tester.pumpAndSettle();

    expect(find.text('Sale complete'), findsWidgets);
    expect(find.byTooltip('Share receipt'), findsOneWidget);
    expect(find.byTooltip('Print receipt'), findsOneWidget);
    expect(submittedSale?['amount_paid'], '20.00');
    expect(submittedSale?['event_id'], 3);
    expect(idempotencyKey, isNotEmpty);
    api.close();
  });
}
