import 'dart:convert';
import 'package:http/http.dart' as http;

import '../config/api_config.dart';

class ApiService {

  static Future<dynamic> get(String endpoint) async {

    final url = Uri.parse(
      '${ApiConfig.baseUrl}$endpoint'
    );

    final response = await http.get(url);

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }

    throw Exception(
      'API Error: ${response.statusCode}'
    );
  }
}