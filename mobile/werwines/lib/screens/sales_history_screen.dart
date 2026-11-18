import 'package:material_ui/material_ui.dart';
import 'package:printing/printing.dart';

import '../models.dart';
import '../services/api_service.dart';
import '../utils/formatting.dart';
import '../utils/receipt_pdf.dart';
import 'settings_store.dart';

class SalesHistoryScreen extends StatefulWidget {
  const SalesHistoryScreen({
    required this.api,
    required this.onSignOut,
    this.embedded = false,
    this.settingsStore,
    super.key,
  });

  final ApiService api;
  final VoidCallback onSignOut;
  final bool embedded;
  final AppSettingsStore? settingsStore;

  @override
  State<SalesHistoryScreen> createState() => _SalesHistoryScreenState();
}

class _SalesHistoryScreenState extends State<SalesHistoryScreen> {
  final List<SaleHistoryEntry> _sales = [];
  int? _nextOffset;
  bool _loading = true;
  bool _loadingMore = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadPage(refresh: true);
  }

  Future<void> _loadPage({bool refresh = false}) async {
    if (_loadingMore || (_loading && !refresh)) return;
    if (refresh) {
      setState(() {
        _loading = true;
        _error = null;
      });
    } else {
      setState(() {
        _loadingMore = true;
        _error = null;
      });
    }

    try {
      final page = await widget.api.fetchSalesHistory(
        offset: refresh ? 0 : _nextOffset ?? 0,
      );
      if (mounted) {
        setState(() {
          if (refresh) _sales.clear();
          _sales.addAll(page.sales);
          _nextOffset = page.nextOffset;
          _loading = false;
          _loadingMore = false;
        });
      }
    } on ApiException catch (error) {
      if (error.statusCode == 401) {
        _returnToSignIn();
      } else if (mounted) {
        setState(() {
          _error = error.message;
          _loading = false;
          _loadingMore = false;
        });
      }
    } on Exception catch (error) {
      if (mounted) {
        setState(() {
          _error = error.toString();
          _loading = false;
          _loadingMore = false;
        });
      }
    }
  }

  void _returnToSignIn() {
    widget.onSignOut();
    Navigator.of(context).popUntil((route) => route.isFirst);
  }

  Future<void> _openReceipt(SaleHistoryEntry sale) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => SaleReceiptScreen(
          api: widget.api,
          invoiceId: sale.invoiceId,
          onSignOut: widget.onSignOut,
          settingsStore: widget.settingsStore ?? MobileSettingsStore(),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: widget.embedded
          ? null
          : AppBar(
              title: const Text('Sales history'),
              actions: [
                IconButton(
                  tooltip: 'Refresh sales history',
                  onPressed: _loading ? null : () => _loadPage(refresh: true),
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _sales.isEmpty && _error != null
          ? _HistoryError(
              message: _error!,
              onRetry: () => _loadPage(refresh: true),
            )
          : _sales.isEmpty
          ? const Center(child: Text('No sales yet.'))
          : RefreshIndicator(
              onRefresh: () => _loadPage(refresh: true),
              child: ListView.separated(
                padding: const EdgeInsets.all(12),
                itemCount: _sales.length + 1,
                separatorBuilder: (_, _) => const SizedBox(height: 4),
                itemBuilder: (context, index) {
                  if (index == _sales.length) {
                    if (_error != null) {
                      return _HistoryError(
                        message: _error!,
                        onRetry: _loadPage,
                      );
                    }
                    if (_nextOffset == null) {
                      return const SizedBox(height: 12);
                    }
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: Center(
                        child: OutlinedButton(
                          onPressed: _loadingMore ? null : _loadPage,
                          child: _loadingMore
                              ? const SizedBox(
                                  height: 18,
                                  width: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Text('Load older sales'),
                        ),
                      ),
                    );
                  }

                  final sale = _sales[index];
                  return Card(
                    child: ListTile(
                      key: ValueKey('sale-${sale.invoiceId}'),
                      title: Text(
                        'Sale #${sale.invoiceId}',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      subtitle: Text(
                        '${sale.customerName}\n'
                        '${_formatDate(sale.createdAt)} · '
                        '${sale.itemCount} ${sale.itemCount == 1 ? 'item' : 'items'} · '
                        '${sale.status.replaceAll('_', ' ')}',
                      ),
                      isThreeLine: true,
                      trailing: Text(
                        formatMoney(sale.totalAmount),
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      onTap: () => _openReceipt(sale),
                    ),
                  );
                },
              ),
            ),
    );
  }
}

class SaleReceiptScreen extends StatefulWidget {
  const SaleReceiptScreen({
    required this.api,
    required this.invoiceId,
    required this.onSignOut,
    required this.settingsStore,
    super.key,
  });

  final ApiService api;
  final int invoiceId;
  final VoidCallback onSignOut;
  final AppSettingsStore settingsStore;

  @override
  State<SaleReceiptScreen> createState() => _SaleReceiptScreenState();
}

class _SaleReceiptScreenState extends State<SaleReceiptScreen> {
  SaleReceipt? _receipt;
  String? _error;
  bool _loading = true;
  bool _receiptActionLoading = false;
  MobileAppSettings _settings = const MobileAppSettings();
  String? _settingsError;

  @override
  void initState() {
    super.initState();
    _loadReceipt();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    try {
      final settings = await widget.settingsStore.read();
      if (mounted) setState(() => _settings = settings);
    } on Exception catch (error) {
      if (mounted) setState(() => _settingsError = error.toString());
    }
  }

  Future<void> _loadReceipt() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final receipt = await widget.api.fetchReceipt(widget.invoiceId);
      if (mounted) {
        setState(() {
          _receipt = receipt;
          _loading = false;
        });
      }
    } on ApiException catch (error) {
      if (error.statusCode == 401) {
        if (mounted) {
          widget.onSignOut();
          Navigator.of(context).popUntil((route) => route.isFirst);
        }
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

  Future<void> _shareReceipt(SaleReceipt receipt) async {
    await _runReceiptAction('share', () async {
      final bytes = await buildReceiptPdf(
        receipt,
        showCashierName: _settings.showCashierName,
      );
      await Printing.sharePdf(
        bytes: bytes,
        filename: 'receipt-${receipt.invoiceId}.pdf',
        subject: 'Receipt #${receipt.invoiceId}',
      );
    });
  }

  Future<void> _printReceipt(SaleReceipt receipt) async {
    await _runReceiptAction('print', () async {
      await Printing.layoutPdf(
        name: 'Receipt #${receipt.invoiceId}',
        format: thermalReceiptPageFormat(receipt),
        onLayout: (_) => buildReceiptPdf(
          receipt,
          showCashierName: _settings.showCashierName,
        ),
      );
    });
  }

  Future<void> _runReceiptAction(
    String action,
    Future<void> Function() run,
  ) async {
    setState(() => _receiptActionLoading = true);
    try {
      await run();
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
    final receipt = _receipt;
    return Scaffold(
      appBar: AppBar(
        title: Text('Receipt #${widget.invoiceId}'),
        actions: [
          IconButton(
            tooltip: 'Share receipt',
            onPressed: _loading || receipt == null || _receiptActionLoading
                ? null
                : () => _shareReceipt(receipt),
            icon: const Icon(Icons.share_outlined),
          ),
          IconButton(
            tooltip: 'Print receipt',
            onPressed: _loading || receipt == null || _receiptActionLoading
                ? null
                : () => _printReceipt(receipt),
            icon: const Icon(Icons.print_outlined),
          ),
          IconButton(
            tooltip: 'Refresh receipt',
            onPressed: _loading || _receiptActionLoading ? null : _loadReceipt,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null && receipt == null
          ? _HistoryError(message: _error!, onRetry: _loadReceipt)
          : _buildReceipt(receipt!),
    );
  }

  Widget _buildReceipt(SaleReceipt receipt) {
    return MediaQuery(
      data: MediaQuery.of(context)
          .copyWith(textScaler: TextScaler.linear(_settings.receiptTextScale)),
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_settingsError != null)
            Text(
              _settingsError!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          Text(
            'Sale #${receipt.invoiceId}',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          _ReceiptInfoRow(label: 'Date', value: _formatDate(receipt.createdAt)),
          _ReceiptInfoRow(label: 'Customer', value: receipt.customerName),
          if (_settings.showCashierName && receipt.cashierName != null)
            _ReceiptInfoRow(label: 'Cashier', value: receipt.cashierName!),
          if (receipt.eventName != null)
            _ReceiptInfoRow(label: 'Event', value: receipt.eventName!),
          _ReceiptInfoRow(
            label: 'Status',
            value: receipt.status.replaceAll('_', ' '),
          ),
          const Divider(height: 28),
          Text('Items', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          ...receipt.lines.map(
            (line) => Material(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            line.name,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ),
                        Text(formatMoney(line.total)),
                      ],
                    ),
                    if (line.description.isNotEmpty &&
                        line.description != line.name)
                      Text(line.description),
                    Text('Quantity: ${_formatQuantity(line.quantity)}'),
                    ...line.unitPrices.map(
                      (price) => Text(
                        '${_formatQuantity(price.quantity)} ${price.priceType} '
                        '@ ${formatMoney(price.unitPrice)}',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const Divider(height: 28),
          _ReceiptInfoRow(
            label: 'Subtotal',
            value: formatMoney(receipt.subtotal),
          ),
          _ReceiptInfoRow(
            label: 'Discount',
            value: '-${formatMoney(receipt.discountAmount)}',
          ),
          _ReceiptInfoRow(
            label: 'Total',
            value: formatMoney(receipt.totalAmount),
            emphasized: true,
          ),
          const SizedBox(height: 12),
          if (_settings.showPaymentBreakdown) ...[
            Text('Payments', style: Theme.of(context).textTheme.titleLarge),
            if (receipt.payments.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('No payments recorded.'),
              )
            else
              ...receipt.payments.map(
                (payment) => _ReceiptInfoRow(
                  label:
                      '${payment.paymentMethod ?? 'Payment'} · ${_formatDate(payment.createdAt)}',
                  value: formatMoney(payment.amount),
                ),
              ),
          ],
          _ReceiptInfoRow(
            label: 'Paid',
            value: formatMoney(receipt.amountPaid),
          ),
          if (receipt.changeAmount > 0)
            _ReceiptInfoRow(
              label: 'Change',
              value: formatMoney(receipt.changeAmount),
            ),
          if (receipt.balanceDue > 0)
            _ReceiptInfoRow(
              label: 'Balance due',
              value: formatMoney(receipt.balanceDue),
            ),
        ],
      ),
    );
  }
}

class _ReceiptInfoRow extends StatelessWidget {
  const _ReceiptInfoRow({
    required this.label,
    required this.value,
    this.emphasized = false,
  });

  final String label;
  final String value;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    final style = emphasized
        ? Theme.of(context).textTheme.titleMedium
              ?.copyWith(fontWeight: FontWeight.bold)
        : Theme.of(context).textTheme.bodyMedium;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: Text(label, style: style)),
          const SizedBox(width: 12),
          Text(value, style: style, textAlign: TextAlign.end),
        ],
      ),
    );
  }
}

class _HistoryError extends StatelessWidget {
  const _HistoryError({required this.message, required this.onRetry});

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

String _formatDate(String? value) {
  if (value == null) return 'Date unavailable';
  final date = DateTime.tryParse(value)?.toLocal();
  if (date == null) return value;
  final month = date.month.toString().padLeft(2, '0');
  final day = date.day.toString().padLeft(2, '0');
  final hour = date.hour.toString().padLeft(2, '0');
  final minute = date.minute.toString().padLeft(2, '0');
  return '${date.year}-$month-$day $hour:$minute';
}
