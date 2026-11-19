import 'dart:convert';
import 'dart:math';

import 'package:material_ui/material_ui.dart';
import 'package:printing/printing.dart';

import 'models.dart';
import 'screens/dashboard_screen.dart';
import 'screens/items_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/sales_history_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/settings_store.dart';
import 'services/api_service.dart';
import 'utils/formatting.dart';
import 'utils/receipt_pdf.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const WerwinesApp());
}

class WerwinesApp extends StatefulWidget {
  const WerwinesApp({super.key, this.apiService, this.settingsStore});

  final ApiService? apiService;
  final AppSettingsStore? settingsStore;

  @override
  State<WerwinesApp> createState() => _WerwinesAppState();
}

class _WerwinesAppState extends State<WerwinesApp> {
  late final ApiService _api = widget.apiService ?? ApiService();
  bool _restoring = true;
  bool _signedIn = false;
  String? _restoreError;

  @override
  void initState() {
    super.initState();
    _restoreSession();
  }

  Future<void> _restoreSession() async {
    try {
      await _api.restoreToken();
      if (mounted) {
        setState(() {
          _signedIn = _api.hasToken;
          _restoring = false;
          _restoreError = null;
        });
      }
    } on Exception catch (error) {
      if (mounted) {
        setState(() {
          _restoring = false;
          _restoreError = error.toString();
        });
      }
    }
  }

  void _signIn() {
    setState(() {
      _signedIn = true;
      _restoreError = null;
    });
  }

  Future<void> _signOut() async {
    await _api.logout();
    if (mounted) {
      setState(() => _signedIn = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'WeRWines',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF291D34)),
        useMaterial3: true,
        cardTheme: const CardThemeData(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(8)),
          ),
        ),
      ),
      home: _restoring
          ? const _LoadingScreen(message: 'Restoring session…')
          : _restoreError != null
          ? _SessionErrorScreen(
              error: _restoreError!,
              onContinue: () => setState(() {
                _restoreError = null;
              }),
            )
          : _signedIn
          ? CashierScreen(
              api: _api,
              onSignOut: _signOut,
              settingsStore: widget.settingsStore,
            )
          : LoginScreen(api: _api, onSignedIn: _signIn),
    );
  }
}

class _LoadingScreen extends StatelessWidget {
  const _LoadingScreen({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            Text(message),
          ],
        ),
      ),
    );
  }
}

class _SessionErrorScreen extends StatelessWidget {
  const _SessionErrorScreen({required this.error, required this.onContinue});

  final String error;
  final VoidCallback onContinue;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.lock_outline, size: 48),
              const SizedBox(height: 16),
              const Text('Could not restore the saved sign-in.'),
              const SizedBox(height: 8),
              Text(error, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: onContinue,
                child: const Text('Continue to sign in'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({required this.api, required this.onSignedIn, super.key});

  final ApiService api;
  final VoidCallback onSignedIn;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.api.login(
        _usernameController.text.trim(),
        _passwordController.text,
      );
      if (mounted) widget.onSignedIn();
    } on Exception catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Image.asset(
                      'assets/images/logo-plum.png',
                      width: 56,
                      height: 56,
                      fit: BoxFit.contain,
                    ),
                    const SizedBox(height: 20),
                    Text(
                      'WeRWines',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 10),
                    Text(
                      'Welcome Back!',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                    const SizedBox(height: 32),
                    TextFormField(
                      key: const ValueKey('username'),
                      controller: _usernameController,
                      decoration: const InputDecoration(
                        labelText: 'Username',
                        border: OutlineInputBorder(),
                      ),
                      textInputAction: TextInputAction.next,
                      autofillHints: const [AutofillHints.username],
                      validator: (value) =>
                          value == null || value.trim().isEmpty
                          ? 'Enter your username'
                          : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      key: const ValueKey('password'),
                      controller: _passwordController,
                      decoration: const InputDecoration(
                        labelText: 'Password',
                        border: OutlineInputBorder(),
                      ),
                      obscureText: true,
                      textInputAction: TextInputAction.done,
                      autofillHints: const [AutofillHints.password],
                      onFieldSubmitted: (_) => _submit(),
                      validator: (value) => value == null || value.isEmpty
                          ? 'Enter your password'
                          : null,
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 16),
                      Text(
                        _error!,
                        key: const ValueKey('login-error'),
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ],
                    const SizedBox(height: 24),
                    FilledButton(
                      key: const ValueKey('sign-in'),
                      onPressed: _submitting ? null : _submit,
                      child: _submitting
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Sign in'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class CashierScreen extends StatefulWidget {
  const CashierScreen({
    required this.api,
    required this.onSignOut,
    this.settingsStore,
    super.key,
  });

  final ApiService api;
  final Future<void> Function() onSignOut;
  final AppSettingsStore? settingsStore;

  @override
  State<CashierScreen> createState() => _CashierScreenState();
}

class _CashierScreenState extends State<CashierScreen> {
  static const _tabTitles = [
    'WeRWines',
    'Items',
    'POS',
    'Receipts',
    'Settings',
  ];
  final _visitedTabs = List<bool>.filled(5, false);
  late final AppSettingsStore _settingsStore =
      widget.settingsStore ?? MobileSettingsStore();
  List<ActiveEvent> _events = [];
  int? _selectedEventId;
  MobileProfile? _profile;
  String? _profileError;
  String? _eventsError;
  int _selectedTab = 0;

  @override
  void initState() {
    super.initState();
    _visitedTabs[0] = true;
    _loadEvents();
    _loadProfile();
  }

  Future<void> _loadEvents() async {
    try {
      final events = await widget.api.fetchActiveEvents();
      if (mounted) {
        setState(() {
          _events = events;
          if (!_events.any((event) => event.id == _selectedEventId)) {
            _selectedEventId = null;
          }
          _eventsError = null;
        });
      }
    } on ApiException catch (error) {
      if (error.statusCode == 401) {
        widget.onSignOut();
      } else if (mounted) {
        setState(() => _eventsError = error.message);
      }
    } on Exception catch (error) {
      if (mounted) setState(() => _eventsError = error.toString());
    }
  }

  Future<void> _loadProfile() async {
    try {
      final profile = await widget.api.fetchProfile();
      if (mounted) {
        setState(() {
          _profile = profile;
          _profileError = null;
        });
      }
    } on ApiException catch (error) {
      if (error.statusCode == 401) {
        widget.onSignOut();
      } else if (mounted) {
        setState(() => _profileError = error.message);
      }
    } on Exception catch (error) {
      if (mounted) setState(() => _profileError = error.toString());
    }
  }

  void _selectTab(int index) {
    setState(() {
      _selectedTab = index;
      _visitedTabs[index] = true;
    });
  }

  Widget _buildTab(int index) {
    switch (index) {
      case 0:
        return DashboardScreen(
          key: const ValueKey('dashboard-tab'),
          api: widget.api,
          events: _events,
          eventsError: _eventsError,
          selectedEventId: _selectedEventId,
          onEventChanged: (eventId) =>
              setState(() => _selectedEventId = eventId),
          onRetryEvents: _loadEvents,
          onSignOut: widget.onSignOut,
          onOpenReceipts: () => _selectTab(3),
        );
      case 1:
        return ItemsScreen(
          key: const ValueKey('items-tab'),
          api: widget.api,
          onSignOut: widget.onSignOut,
          eventId: _selectedEventId,
        );
      case 2:
        return PosScreen(
          key: const ValueKey('pos-tab'),
          api: widget.api,
          eventId: _selectedEventId,
          settingsStore: _settingsStore,
          onSignOut: widget.onSignOut,
        );
      case 3:
        return SalesHistoryScreen(
          key: const ValueKey('receipts-tab'),
          api: widget.api,
          onSignOut: widget.onSignOut,
          embedded: true,
          settingsStore: _settingsStore,
        );
      case 4:
        return SettingsScreen(
          key: const ValueKey('settings-tab'),
          store: _settingsStore,
        );
      default:
        throw RangeError.index(index, _tabTitles);
    }
  }

  Future<void> _openProfile() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => ProfileScreen(
          api: widget.api,
          onSignOut: widget.onSignOut,
          onProfileUpdated: (profile) {
            if (mounted) setState(() => _profile = profile);
          },
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(_tabTitles[_selectedTab]),
      actions: [
        IconButton(
          key: const ValueKey('profile-avatar'),
          tooltip: _profileError == null ? 'Profile' : 'Profile · tap to retry',
          onPressed: _openProfile,
          icon: CircleAvatar(
            radius: 17,
            child: Text(_initials(_profile?.name ?? '')),
          ),
        ),
      ],
    ),
    body: IndexedStack(
      index: _selectedTab,
      children: List.generate(
        _visitedTabs.length,
        (index) =>
            _visitedTabs[index] ? _buildTab(index) : const SizedBox.shrink(),
      ),
    ),
    bottomNavigationBar: NavigationBar(
      selectedIndex: _selectedTab,
      onDestinationSelected: _selectTab,
      destinations: const [
        NavigationDestination(
          key: ValueKey('nav-home'),
          icon: Icon(Icons.home_outlined),
          selectedIcon: Icon(Icons.home),
          label: 'Home',
        ),
        NavigationDestination(
          key: ValueKey('nav-items'),
          icon: Icon(Icons.inventory_2_outlined),
          selectedIcon: Icon(Icons.inventory_2),
          label: 'Items',
        ),
        NavigationDestination(
          key: ValueKey('nav-pos'),
          icon: Icon(Icons.point_of_sale_outlined),
          selectedIcon: Icon(Icons.point_of_sale),
          label: 'POS',
        ),
        NavigationDestination(
          key: ValueKey('nav-receipts'),
          icon: Icon(Icons.receipt_long_outlined),
          selectedIcon: Icon(Icons.receipt_long),
          label: 'Receipts',
        ),
        NavigationDestination(
          key: ValueKey('nav-settings'),
          icon: Icon(Icons.settings_outlined),
          selectedIcon: Icon(Icons.settings),
          label: 'Settings',
        ),
      ],
    ),
  );
}

class PosScreen extends StatefulWidget {
  const PosScreen({
    required this.api,
    required this.onSignOut,
    required this.eventId,
    required this.settingsStore,
    super.key,
  });

  final ApiService api;
  final VoidCallback onSignOut;
  final int? eventId;
  final AppSettingsStore settingsStore;

  @override
  State<PosScreen> createState() => _PosScreenState();
}

class _PosScreenState extends State<PosScreen> {
  final _searchController = TextEditingController();
  List<CatalogueItem> _items = [];
  List<Customer> _customers = [];
  final Map<int, int> _cart = {};
  int? _customerId;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadCatalogue();
  }

  @override
  void didUpdateWidget(covariant PosScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.eventId != widget.eventId) _loadCatalogue();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadCatalogue() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final items = await widget.api.fetchCatalogue(eventId: widget.eventId);
      final customers = await widget.api.fetchCustomers();
      if (mounted) {
        setState(() {
          _items = items;
          _customers = customers;
          _loading = false;
        });
      }
    } on ApiException catch (error) {
      if (error.statusCode == 401) {
        widget.onSignOut();
      } else if (mounted) {
        setState(() {
          _error = error.message;
          _loading = false;
        });
      }
    } on Exception catch (error) {
      if (mounted) {
        setState(() {
          _error = error.toString();
          _loading = false;
        });
      }
    }
  }

  List<CatalogueItem> get _filteredItems {
    final query = _searchController.text.trim().toLowerCase();
    if (query.isEmpty) return _items;
    return _items
        .where(
          (item) =>
              item.name.toLowerCase().contains(query) ||
              item.barcode.toLowerCase().contains(query),
        )
        .toList();
  }

  void _addItem(CatalogueItem item) {
    final quantity = (_cart[item.id] ?? 0) + 1;
    if (quantity > item.quantity) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Only ${_formatQuantity(item.quantity)} in stock.'),
        ),
      );
      return;
    }
    setState(() => _cart[item.id] = quantity);
  }

  void _changeQuantity(int itemId, int difference) {
    final quantity = (_cart[itemId] ?? 0) + difference;
    setState(() {
      if (quantity <= 0) {
        _cart.remove(itemId);
      } else {
        _cart[itemId] = quantity;
      }
    });
  }

  Future<void> _checkout() async {
    final itemsById = {for (final item in _items) item.id: item};
    final checkedOut = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => CheckoutScreen(
          api: widget.api,
          itemsById: itemsById,
          quantities: Map<int, int>.from(_cart),
          customerId: _customerId,
          eventId: widget.eventId,
          settingsStore: widget.settingsStore,
          onSignOut: widget.onSignOut,
        ),
      ),
    );
    if (checkedOut == true && mounted) {
      setState(_cart.clear);
      _loadCatalogue();
    }
  }

  @override
  Widget build(BuildContext context) {
    final filteredItems = _filteredItems;
    final itemCount = _cart.values.fold<int>(
      0,
      (sum, quantity) => sum + quantity,
    );
    return Column(
      children: [
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
              ? _ErrorPanel(message: _error!, onRetry: _loadCatalogue)
              : Column(
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 8, 8, 0),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              widget.eventId == null
                                  ? 'Selling from Store'
                                  : 'Selling at active Event',
                              style: Theme.of(context).textTheme.labelLarge,
                            ),
                          ),
                          IconButton(
                            tooltip: 'Refresh catalogue',
                            onPressed: _loading ? null : _loadCatalogue,
                            icon: const Icon(Icons.refresh),
                          ),
                        ],
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                      child: Column(
                        children: [
                          DropdownButtonFormField<int?>(
                            key: const ValueKey('customer-select'),
                            initialValue: _customerId,
                            decoration: const InputDecoration(
                              labelText: 'Customer',
                              border: OutlineInputBorder(),
                              prefixIcon: Icon(Icons.person_outline),
                            ),
                            items: [
                              const DropdownMenuItem<int?>(
                                value: null,
                                child: Text('Walk-in customer'),
                              ),
                              ..._customers.map(
                                (customer) => DropdownMenuItem<int?>(
                                  value: customer.id,
                                  child: Text(customer.name),
                                ),
                              ),
                            ],
                            onChanged: (value) =>
                                setState(() => _customerId = value),
                          ),
                          const SizedBox(height: 12),
                          TextField(
                            controller: _searchController,
                            onChanged: (_) => setState(() {}),
                            decoration: InputDecoration(
                              hintText: 'Search name or scan barcode',
                              prefixIcon: const Icon(Icons.search),
                              suffixIcon: _searchController.text.isEmpty
                                  ? null
                                  : IconButton(
                                      tooltip: 'Clear search',
                                      onPressed: () {
                                        _searchController.clear();
                                        setState(() {});
                                      },
                                      icon: const Icon(Icons.close),
                                    ),
                              border: const OutlineInputBorder(),
                            ),
                          ),
                          const SizedBox(height: 12),
                          SizedBox(
                            width: double.infinity,
                            child: FilledButton.icon(
                              key: const ValueKey('review-cart'),
                              onPressed: _cart.isEmpty ? null : _checkout,
                              icon: const Icon(Icons.shopping_cart_checkout),
                              label: Text(
                                itemCount == 0
                                    ? 'Review Cart'
                                    : 'Review Cart · $itemCount ${itemCount == 1 ? 'item' : 'items'}',
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    Expanded(
                      child: filteredItems.isEmpty
                          ? const Center(child: Text('No matching products.'))
                          : GridView.builder(
                              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                              gridDelegate:
                                  const SliverGridDelegateWithFixedCrossAxisCount(
                                    crossAxisCount: 2,
                                    crossAxisSpacing: 8,
                                    mainAxisSpacing: 8,
                                    mainAxisExtent: 140,
                                  ),
                              itemCount: filteredItems.length,
                              itemBuilder: (context, index) {
                                final item = filteredItems[index];
                                final inCart = _cart[item.id] ?? 0;
                                final outOfStock = item.quantity <= 0;
                                return Card(
                                  child: Padding(
                                    padding: const EdgeInsets.fromLTRB(
                                      8,
                                      5,
                                      8,
                                      4,
                                    ),
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          item.name,
                                          maxLines: 2,
                                          overflow: TextOverflow.ellipsis,
                                          style: const TextStyle(
                                            fontWeight: FontWeight.bold,
                                            fontSize: 14,
                                          ),
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          formatMoney(item.retailPrice),
                                          style: Theme.of(context)
                                              .textTheme
                                              .titleSmall
                                              ?.copyWith(
                                                fontWeight: FontWeight.bold,
                                              ),
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          'Available: ${_formatQuantity(item.quantity)}',
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: Theme.of(context)
                                              .textTheme
                                              .bodySmall,
                                        ),
                                        const Spacer(),
                                        Row(
                                          mainAxisAlignment:
                                              MainAxisAlignment.spaceBetween,
                                          children: [
                                            if (inCart > 0)
                                              IconButton(
                                                tooltip:
                                                    'Remove one ${item.name}',
                                                visualDensity:
                                                    VisualDensity.compact,
                                                onPressed: () =>
                                                    _changeQuantity(
                                                      item.id,
                                                      -1,
                                                    ),
                                                icon: const Icon(
                                                  Icons.remove_circle_outline,
                                                ),
                                              )
                                            else
                                              const SizedBox(width: 40),
                                            IconButton(
                                              tooltip: inCart > 0
                                                  ? 'Add one ${item.name}'
                                                  : 'Add ${item.name}',
                                              visualDensity:
                                                  VisualDensity.compact,
                                              onPressed: outOfStock
                                                  ? null
                                                  : () => _addItem(item),
                                              icon: const Icon(
                                                Icons.add_circle_outline,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ],
                                    ),
                                  ),
                                );
                              },
                            ),
                    ),
                  ],
                ),
        ),
      ],
    );
  }
}

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({
    required this.api,
    required this.itemsById,
    required this.quantities,
    required this.customerId,
    required this.eventId,
    required this.onSignOut,
    required this.settingsStore,
    super.key,
  });

  final ApiService api;
  final Map<int, CatalogueItem> itemsById;
  final Map<int, int> quantities;
  final int? customerId;
  final int? eventId;
  final VoidCallback onSignOut;
  final AppSettingsStore settingsStore;

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  final _amountController = TextEditingController();
  SaleQuote? _quote;
  SaleResult? _result;
  bool _loading = true;
  bool _submitting = false;
  String? _error;
  String _paymentMethod = 'cash';
  String? _idempotencyKey;
  String? _idempotencyPayload;
  bool _receiptActionLoading = false;

  @override
  void initState() {
    super.initState();
    _loadQuote();
  }

  @override
  void dispose() {
    _amountController.dispose();
    super.dispose();
  }

  Future<void> _loadQuote() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final quote = await widget.api.quoteSale(
        customerId: widget.customerId,
        quantities: widget.quantities,
        eventId: widget.eventId,
      );
      if (mounted) {
        setState(() {
          _quote = quote;
          _amountController.text = quote.totalAmount.toStringAsFixed(2);
          _loading = false;
        });
      }
    } on ApiException catch (error) {
      if (error.statusCode == 401) {
        widget.onSignOut();
      } else if (mounted) {
        setState(() {
          _error = error.message;
          _loading = false;
        });
      }
    } on Exception catch (error) {
      if (mounted) {
        setState(() {
          _error = error.toString();
          _loading = false;
        });
      }
    }
  }

  Future<void> _completeSale() async {
    final quote = _quote;
    if (quote == null) return;
    final tendered = double.tryParse(_amountController.text.trim());
    if (tendered == null ||
        !tendered.isFinite ||
        tendered < quote.totalAmount) {
      setState(() => _error = 'Amount received must cover the sale total.');
      return;
    }
    if (_paymentMethod != 'cash' && tendered != quote.totalAmount) {
      setState(
        () => _error = 'Enter the exact sale total for non-cash payments.',
      );
      return;
    }

    final payload = jsonEncode({
      'customer_id': widget.customerId,
      'items': widget.quantities.entries
          .map((entry) => {'item_id': entry.key, 'quantity': entry.value})
          .toList(),
      'amount_paid': _amountController.text.trim(),
      'payment_method': _paymentMethod,
    });
    if (_idempotencyPayload != payload) {
      _idempotencyPayload = payload;
      _idempotencyKey = _newIdempotencyKey();
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final result = await widget.api.createSale(
        customerId: widget.customerId,
        quantities: widget.quantities,
        amountPaid: _amountController.text.trim(),
        paymentMethod: _paymentMethod,
        idempotencyKey: _idempotencyKey!,
        eventId: widget.eventId,
      );
      if (mounted) setState(() => _result = result);
    } on ApiException catch (error) {
      if (error.statusCode == 401) {
        widget.onSignOut();
      } else if (mounted) {
        setState(() => _error = error.message);
      }
    } on Exception catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  String _newIdempotencyKey() {
    final random = Random.secure();
    final bytes = List<int>.generate(24, (_) => random.nextInt(256));
    return base64Url.encode(bytes).replaceAll('=', '');
  }

  Future<void> _shareReceipt() => _runReceiptAction('share', (receipt) async {
    final settings = await widget.settingsStore.read();
    final bytes = await buildReceiptPdf(
      receipt,
      showCashierName: settings.showCashierName,
    );
    await Printing.sharePdf(
      bytes: bytes,
      filename: 'receipt-${receipt.receiptNumber}.pdf',
      subject: 'Receipt #${receipt.receiptNumber}',
    );
  });

  Future<void> _printReceipt() => _runReceiptAction('print', (receipt) async {
    final settings = await widget.settingsStore.read();
    await Printing.layoutPdf(
      name: 'Receipt #${receipt.receiptNumber}',
      format: thermalReceiptPageFormat(receipt),
      onLayout: (_) =>
          buildReceiptPdf(receipt, showCashierName: settings.showCashierName),
    );
  });

  Future<void> _runReceiptAction(
    String action,
    Future<void> Function(SaleReceipt receipt) run,
  ) async {
    setState(() => _receiptActionLoading = true);
    try {
      final receipt = await widget.api.fetchReceipt(_result!.invoiceId);
      await run(receipt);
    } on ApiException catch (error) {
      if (error.statusCode == 401) {
        widget.onSignOut();
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Could not $action receipt: ${error.message}'),
          ),
        );
      }
    } on Exception catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not $action receipt: $error')),
        );
      }
    } finally {
      if (mounted) setState(() => _receiptActionLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final result = _result;
    return Scaffold(
      appBar: AppBar(
        title: Text(result == null ? 'Checkout' : 'Sale complete'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null && _quote == null
          ? _ErrorPanel(message: _error!, onRetry: _loadQuote)
          : result != null
          ? _SaleConfirmation(
              result: result,
              onNewSale: () => Navigator.of(context).pop(true),
              onShareReceipt: _shareReceipt,
              onPrintReceipt: _printReceipt,
              receiptActionLoading: _receiptActionLoading,
            )
          : _buildCheckoutForm(),
      bottomNavigationBar: !_loading && _quote != null && result == null
          ? SafeArea(
              minimum: const EdgeInsets.all(16),
              child: FilledButton(
                key: const ValueKey('complete-sale'),
                onPressed: _submitting ? null : _completeSale,
                child: _submitting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Finalize'),
              ),
            )
          : null,
    );
  }

  Widget _buildCheckoutForm() {
    final quote = _quote!;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Sale summary', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        ...widget.quantities.entries.map((entry) {
          final item = widget.itemsById[entry.key];
          return ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(item?.name ?? 'Item ${entry.key}'),
            subtitle: Text('Quantity: ${entry.value}'),
          );
        }),
        const Divider(),
        _MoneyRow(label: 'Subtotal', amount: quote.subtotal),
        _MoneyRow(label: 'Discount', amount: -quote.discountAmount),
        const SizedBox(height: 8),
        _MoneyRow(
          label: 'Total due',
          amount: quote.totalAmount,
          emphasized: true,
        ),
        const SizedBox(height: 24),
        DropdownButtonFormField<String>(
          initialValue: _paymentMethod,
          decoration: const InputDecoration(
            labelText: 'Payment method',
            border: OutlineInputBorder(),
          ),
          items: const [
            DropdownMenuItem(value: 'cash', child: Text('Cash')),
            DropdownMenuItem(value: 'card', child: Text('Card')),
            DropdownMenuItem(
              value: 'mobile money',
              child: Text('Mobile Money'),
            ),
            DropdownMenuItem(
              value: 'bank transfer',
              child: Text('Bank Transfer'),
            ),
          ],
          onChanged: (value) {
            if (value != null) {
              setState(() {
                _paymentMethod = value;
                if (value != 'cash') {
                  _amountController.text = quote.totalAmount.toStringAsFixed(2);
                }
              });
            }
          },
        ),
        const SizedBox(height: 16),
        TextField(
          key: const ValueKey('amount-received'),
          controller: _amountController,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(
            labelText: 'Amount Received (MWK)',
            border: OutlineInputBorder(),
          ),
          onChanged: (_) {
            if (_error != null) setState(() => _error = null);
          },
        ),
        if (_paymentMethod == 'cash')
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: _MoneyRow(label: 'Change', amount: _changeAmount(quote)),
          ),
        if (_error != null) ...[
          const SizedBox(height: 12),
          Text(
            _error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        ],
      ],
    );
  }

  double _changeAmount(SaleQuote quote) {
    final tendered = double.tryParse(_amountController.text.trim()) ?? 0;
    if (!tendered.isFinite) return 0;
    return max(0.0, tendered - quote.totalAmount);
  }
}

class _SaleConfirmation extends StatelessWidget {
  const _SaleConfirmation({
    required this.result,
    required this.onNewSale,
    required this.onShareReceipt,
    required this.onPrintReceipt,
    required this.receiptActionLoading,
  });

  final SaleResult result;
  final VoidCallback onNewSale;
  final VoidCallback onShareReceipt;
  final VoidCallback onPrintReceipt;
  final bool receiptActionLoading;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.check_circle_outline,
              size: 72,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 12),
            Text(
              'Sale complete',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 20),
            _MoneyRow(label: 'Receipt #', receiptNumber: result.receiptNumber),
            _MoneyRow(label: 'Total', amount: result.totalAmount),
            _MoneyRow(label: 'Paid', amount: result.amountPaid),
            _MoneyRow(label: 'Change', amount: result.changeAmount),
            if (result.balanceDue > 0)
              _MoneyRow(label: 'Balance due', amount: result.balanceDue),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  key: const ValueKey('share-sale-receipt'),
                  tooltip: 'Share receipt',
                  onPressed: receiptActionLoading ? null : onShareReceipt,
                  icon: const Icon(Icons.share_outlined),
                ),
                IconButton(
                  key: const ValueKey('print-sale-receipt'),
                  tooltip: 'Print receipt',
                  onPressed: receiptActionLoading ? null : onPrintReceipt,
                  icon: const Icon(Icons.print_outlined),
                ),
                const SizedBox(width: 8),
                FilledButton.icon(
                  key: const ValueKey('new-sale'),
                  onPressed: onNewSale,
                  icon: const Icon(Icons.add_shopping_cart),
                  label: const Text('New Sale'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _MoneyRow extends StatelessWidget {
  const _MoneyRow({
    required this.label,
    this.amount,
    this.receiptNumber,
    this.emphasized = false,
  });

  final String label;
  final double? amount;
  final String? receiptNumber;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    final style = emphasized
        ? Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.bold)
        : Theme.of(context).textTheme.bodyLarge;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: style),
          Text(receiptNumber ?? formatMoney(amount ?? 0), style: style),
        ],
      ),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_outlined, size: 48),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}

String _formatQuantity(double quantity) =>
    quantity == quantity.truncateToDouble()
    ? quantity.toStringAsFixed(0)
    : quantity.toString();

String _initials(String value) {
  final parts = value
      .trim()
      .split(RegExp(r'\s+'))
      .where((part) => part.isNotEmpty);
  if (parts.isEmpty) return '?';
  return parts.take(2).map((part) => part[0].toUpperCase()).join();
}
