import 'package:material_ui/material_ui.dart';

import '../models.dart';
import '../services/api_service.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({
    required this.api,
    required this.onSignOut,
    required this.onProfileUpdated,
    super.key,
  });

  final ApiService api;
  final Future<void> Function() onSignOut;
  final ValueChanged<MobileProfile> onProfileUpdated;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  MobileProfile? _profile;
  String? _error;
  bool _loading = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _loadProfile() async {
    try {
      final profile = await widget.api.fetchProfile();
      if (mounted) {
        setState(() {
          _profile = profile;
          _nameController.text = profile.name;
          _emailController.text = profile.email ?? '';
          _phoneController.text = profile.phone ?? '';
          _loading = false;
          _error = null;
        });
      }
    } on ApiException catch (error) {
      if (error.statusCode == 401) {
        await widget.onSignOut();
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

  Future<void> _saveProfile() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final profile = await widget.api.updateProfile(
        name: _nameController.text.trim(),
        email: _emailController.text.trim().isEmpty
            ? null
            : _emailController.text.trim(),
        phone: _phoneController.text.trim().isEmpty
            ? null
            : _phoneController.text.trim(),
      );
      if (mounted) {
        setState(() {
          _profile = profile;
          _saving = false;
        });
        widget.onProfileUpdated(profile);
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Profile updated.')));
      }
    } on ApiException catch (error) {
      if (error.statusCode == 401) {
        await widget.onSignOut();
      } else if (mounted) {
        setState(() {
          _error = error.message;
          _saving = false;
        });
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
    final profile = _profile;
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (profile == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _error ?? 'Profile unavailable.',
                textAlign: TextAlign.center,
              ),
              TextButton(onPressed: _loadProfile, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          CircleAvatar(radius: 32, child: Text(_initials(profile.name))),
          const SizedBox(height: 8),
          Center(child: Text('@${profile.username} · ${profile.role}')),
          const SizedBox(height: 24),
          Form(
            key: _formKey,
            child: Column(
              children: [
                TextFormField(
                  key: const ValueKey('profile-name'),
                  controller: _nameController,
                  decoration: const InputDecoration(
                    labelText: 'Name',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) => value == null || value.trim().isEmpty
                      ? 'Enter your name'
                      : null,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  key: const ValueKey('profile-email'),
                  controller: _emailController,
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(
                    labelText: 'Email',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  key: const ValueKey('profile-phone'),
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(
                    labelText: 'Phone',
                    border: OutlineInputBorder(),
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _saving ? null : _saveProfile,
                  child: _saving
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Save profile'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 32),
          OutlinedButton.icon(
            onPressed: widget.onSignOut,
            icon: const Icon(Icons.logout),
            label: const Text('Log out'),
          ),
        ],
      ),
    );
  }
}

String _initials(String value) {
  final parts = value
      .trim()
      .split(RegExp(r'\s+'))
      .where((part) => part.isNotEmpty);
  return parts.take(2).map((part) => part[0].toUpperCase()).join();
}
