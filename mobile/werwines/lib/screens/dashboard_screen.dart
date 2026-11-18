import 'package:material_ui/material_ui.dart';

import '../models.dart';
import '../services/api_service.dart';
import '../utils/formatting.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({
    required this.api,
    required this.events,
    required this.eventsError,
    required this.selectedEventId,
    required this.onEventChanged,
    required this.onRetryEvents,
    required this.onSignOut,
    required this.onOpenReceipts,
    super.key,
  });

  final ApiService api;
  final List<ActiveEvent> events;
  final String? eventsError;
  final int? selectedEventId;
  final ValueChanged<int?> onEventChanged;
  final VoidCallback onRetryEvents;
  final VoidCallback onSignOut;
  final VoidCallback onOpenReceipts;

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  DashboardSummary? _summary;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadSummary();
  }

  Future<void> _loadSummary() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final summary = await widget.api.fetchDashboard();
      if (mounted) {
        setState(() {
          _summary = summary;
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

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final selectedEvents = widget.events
        .where((event) => event.id == widget.selectedEventId)
        .toList();
    final selectedEvent = selectedEvents.isEmpty ? null : selectedEvents.first;
    return RefreshIndicator(
      onRefresh: _loadSummary,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'ACTIVE LOCATION',
                    style: theme.textTheme.labelLarge?.copyWith(
                      letterSpacing: 1.2,
                      fontWeight: FontWeight.w500,
                      fontSize: 12.0,
                    ),
                  ),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<int?>(
                    key: const ValueKey('active-location'),
                    initialValue: widget.selectedEventId,
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                      contentPadding: EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                    ),
                    items: [
                      const DropdownMenuItem<int?>(
                        value: null,
                        child: Text('Store'),
                      ),
                      ...widget.events.map(
                        (event) => DropdownMenuItem<int?>(
                          value: event.id,
                          child: Text(
                            event.venue == null || event.venue!.isEmpty
                                ? event.name
                                : '${event.name} (${event.venue})',
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                    ],
                    onChanged: widget.onEventChanged,
                  ),
                  if (widget.eventsError != null)
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            widget.eventsError!,
                            style: TextStyle(color: theme.colorScheme.error),
                          ),
                        ),
                        IconButton(
                          tooltip: 'Retry active events',
                          onPressed: widget.onRetryEvents,
                          icon: const Icon(Icons.refresh),
                        ),
                      ],
                    ),
                  const SizedBox(height: 8),
                  Text(
                    'Selling from: ${selectedEvent?.name ?? 'Store'}',
                    style: theme.textTheme.bodyMedium,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            "TODAY'S SUMMARY",
            style: theme.textTheme.labelLarge?.copyWith(
              letterSpacing: 1.2,
              fontSize: 12.0,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 10),
          if (_loading)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_error != null)
            _DashboardError(message: _error!, onRetry: _loadSummary)
          else ...[
            Row(
              children: [
                Expanded(
                  child: _SummaryCard(
                    key: const ValueKey('total-paid-today'),
                    label: 'Paid Sales',
                    value: formatMoney(_summary!.totalPaidToday),
                    color: theme.colorScheme.primary,
                    foreground: theme.colorScheme.onPrimary,
                    fontSize: 14.0,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _SummaryCard(
                    key: const ValueKey('transactions-today'),
                    label: 'Transactions',
                    value: '${_summary!.transactionCountToday}',
                    color: theme.colorScheme.onSurface,
                    foreground: theme.colorScheme.surface,
                    fontSize: 14.0,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'RECENT SALES',
                          style: theme.textTheme.labelLarge?.copyWith(
                            fontSize: 12.0,
                            letterSpacing: 1,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        TextButton(
                          onPressed: widget.onOpenReceipts,
                          style: TextButton.styleFrom(
                            minimumSize: const Size(0, 32),
                            padding: const EdgeInsets.symmetric(horizontal: 8),
                            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          ),
                          child: const Text('Receipts'),
                        ),
                      ],
                    ),
                    if (_summary!.recentSales.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(20),
                        child: Center(child: Text('No sales yet.')),
                      )
                    else
                      ..._summary!.recentSales.map(
                        (sale) => Card(
                          color: theme.colorScheme.surfaceContainerLow,
                          margin: const EdgeInsets.symmetric(vertical: 2),
                          child: ListTile(
                            dense: true,
                            visualDensity: const VisualDensity(vertical: -2),
                            minVerticalPadding: 0,
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 0,
                            ),
                            title: Text(
                              'Invoice #${sale.invoiceId}',
                              style: const TextStyle(
                                fontSize: 14.0,
                                fontWeight: FontWeight.bold,
                                letterSpacing: 0.8,
                              ),
                            ),
                            subtitle: Text(
                              _formatDate(sale.createdAt),
                              style: const TextStyle(fontSize: 12.0),
                            ),
                            trailing: Text(
                              formatMoney(sale.totalAmount),
                              style: const TextStyle(
                                fontSize: 14.0,
                                fontWeight: FontWeight.bold,
                                letterSpacing: 0.5,
                              ),
                            ),
                            onTap: widget.onOpenReceipts,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.label,
    required this.value,
    required this.color,
    required this.foreground,
    this.fontSize,
    this.fontWeight,
    this.letterSpacing,
    super.key,
  });

  final String label;
  final String value;
  final Color color;
  final Color foreground;
  final double? fontSize;
  final FontWeight? fontWeight;
  final double? letterSpacing;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: color,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: TextStyle(color: foreground)),
            const SizedBox(height: 12),
            Text(
              value,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                color: foreground,
                fontSize: fontSize,
                fontWeight: fontWeight ?? FontWeight.bold,
                letterSpacing: letterSpacing,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DashboardError extends StatelessWidget {
  const _DashboardError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          Text(message, textAlign: TextAlign.center),
          TextButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Try again'),
          ),
        ],
      ),
    ),
  );
}

String _formatDate(String? value) {
  if (value == null) return 'Date unavailable';
  final date = DateTime.tryParse(value)?.toLocal();
  if (date == null) return value;
  final dateText =
      '${date.day.toString().padLeft(2, '0')}/'
      '${date.month.toString().padLeft(2, '0')}/${date.year}';
  final timeText =
      '${date.hour.toString().padLeft(2, '0')}:'
      '${date.minute.toString().padLeft(2, '0')}';
  return '$dateText, $timeText';
}
