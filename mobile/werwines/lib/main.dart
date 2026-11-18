import 'package:material_ui/material_ui.dart';
import 'services/api_service.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: const ApiTestScreen(),
    );
  }
}

class ApiTestScreen extends StatefulWidget {
  const ApiTestScreen({super.key});

  @override
  State<ApiTestScreen> createState() =>
      _ApiTestScreenState();
}

class _ApiTestScreenState extends State<ApiTestScreen> {

  String result = 'Testing connection...';

  @override
  void initState() {
    super.initState();
    testConnection();
  }

  Future<void> testConnection() async {
    try {
      final data = await ApiService.get('/health/ready');

      setState(() {
        result = 'Connected successfully!\nResponse: $data';
      });
    } catch (e) {
      setState(() {
        result = 'Connection failed: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Werwines API Test'),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Text(result),
        ),
      ),
    );
  }
}