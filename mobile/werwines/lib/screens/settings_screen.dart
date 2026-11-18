import 'package:material_ui/material_ui.dart';

import 'settings_store.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({required this.store, super.key});

  final AppSettingsStore store;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  MobileAppSettings _settings = const MobileAppSettings();
  String? _error;
  bool _loading = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    try {
      final settings = await widget.store.read();
      if (mounted) {
        setState(() {
          _settings = settings;
          _loading = false;
          _error = null;
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

  Future<void> _save(MobileAppSettings settings) async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.store.write(settings);
      if (mounted) {
        setState(() {
          _settings = settings;
          _saving = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Receipt settings saved on this device.'),
          ),
        );
      }
    } on Exception catch (error) {
      if (mounted) {
        setState(() {
          _error = error.toString();
          _saving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null && _settings == const MobileAppSettings()) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error!, textAlign: TextAlign.center),
              TextButton(onPressed: _loadSettings, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Receipt settings', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        DropdownButtonFormField<double>(
          key: const ValueKey('receipt-font-size'),
          initialValue: _settings.receiptTextScale,
          decoration: const InputDecoration(
            labelText: 'Receipt font size',
            border: OutlineInputBorder(),
          ),
          items: const [
            DropdownMenuItem(value: 0.9, child: Text('Small')),
            DropdownMenuItem(value: 1.0, child: Text('Standard')),
            DropdownMenuItem(value: 1.15, child: Text('Large')),
            DropdownMenuItem(value: 1.3, child: Text('Extra large')),
          ],
          onChanged: _saving
              ? null
              : (value) {
                  if (value != null) {
                    _save(_settings.copyWith(receiptTextScale: value));
                  }
                },
        ),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Show cashier name on receipts'),
          value: _settings.showCashierName,
          onChanged: _saving
              ? null
              : (value) => _save(_settings.copyWith(showCashierName: value)),
        ),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Show payment breakdown'),
          value: _settings.showPaymentBreakdown,
          onChanged: _saving
              ? null
              : (value) =>
                    _save(_settings.copyWith(showPaymentBreakdown: value)),
        ),
        const Divider(height: 32),
        Text('Display', style: Theme.of(context).textTheme.titleLarge),
        const ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(Icons.phone_android),
          title: Text('App font'),
          subtitle: Text('Uses your device accessibility text settings.'),
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
      ],
    );
  }
}
