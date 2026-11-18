import 'package:material_ui/material_ui.dart';

import '../models.dart';
import '../services/api_service.dart';
import '../utils/formatting.dart';

class ItemsScreen extends StatefulWidget {
  const ItemsScreen({
    required this.api,
    required this.onSignOut,
    required this.eventId,
    super.key,
  });

  final ApiService api;
  final VoidCallback onSignOut;
  final int? eventId;

  @override
  State<ItemsScreen> createState() => _ItemsScreenState();
}

class _ItemsScreenState extends State<ItemsScreen> {
  final _searchController = TextEditingController();
  List<CatalogueItem> _items = [];
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadItems();
  }

  @override
  void didUpdateWidget(covariant ItemsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.eventId != widget.eventId) _loadItems();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadItems() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final items = await widget.api.fetchCatalogue(eventId: widget.eventId);
      if (mounted) {
        setState(() {
          _items = items;
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
    final query = _searchController.text.trim().toLowerCase();
    final items = _items.where((item) {
      return item.name.toLowerCase().contains(query) ||
          item.barcode.toLowerCase().contains(query);
    }).toList();
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error!, textAlign: TextAlign.center),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: _loadItems,
                icon: const Icon(Icons.refresh),
                label: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadItems,
      child: ListView.builder(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(12),
        itemCount: items.length + 1,
        itemBuilder: (context, index) {
          if (index == 0) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: TextField(
                controller: _searchController,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(
                  labelText: 'Search items',
                  prefixIcon: Icon(Icons.search),
                  border: OutlineInputBorder(),
                ),
              ),
            );
          }
          if (items.isEmpty) {
            return const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: Text('No matching items.')),
            );
          }
          final item = items[index - 1];
          return Card(
            child: ListTile(
              title: Text(
                item.name,
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                ),
              ),
              subtitle: Text(
                'Available: ${_formatQuantity(item.quantity)}'
                '${item.barcode.isEmpty ? '' : ' · SKU: ${item.barcode}'}',
              ),
              trailing: Text(formatMoney(item.retailPrice), style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
            ),
          );
        },
      ),
    );
  }
}

String _formatQuantity(double quantity) =>
    quantity == quantity.truncateToDouble()
    ? quantity.toStringAsFixed(0)
    : quantity.toString();
