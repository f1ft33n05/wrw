class CatalogueItem {
  const CatalogueItem({
    required this.id,
    required this.name,
    required this.barcode,
    required this.retailPrice,
    required this.wholesalePrice,
    required this.wholesaleThreshold,
    required this.quantity,
    required this.unit,
  });

  final int id;
  final String name;
  final String barcode;
  final double retailPrice;
  final double wholesalePrice;
  final double wholesaleThreshold;
  final double quantity;
  final String unit;

  factory CatalogueItem.fromJson(Map<String, dynamic> json) {
    return CatalogueItem(
      id: _requiredInt(json, 'id'),
      name: _requiredString(json, 'name'),
      barcode: json['barcode']?.toString() ?? '',
      retailPrice: _requiredNumber(json, 'selling_price_retail'),
      wholesalePrice: _requiredNumber(json, 'selling_price_wholesale'),
      wholesaleThreshold: _requiredNumber(json, 'wholesale_threshold'),
      quantity: _requiredNumber(json, 'quantity'),
      unit: _requiredString(json, 'unit'),
    );
  }
}

class Customer {
  const Customer({required this.id, required this.name});

  final int id;
  final String name;

  factory Customer.fromJson(Map<String, dynamic> json) {
    return Customer(id: json['id'] as int, name: json['name'] as String);
  }
}

class ActiveEvent {
  const ActiveEvent({required this.id, required this.name, this.venue});

  final int id;
  final String name;
  final String? venue;

  factory ActiveEvent.fromJson(Map<String, dynamic> json) => ActiveEvent(
    id: _requiredInt(json, 'id'),
    name: _requiredString(json, 'name'),
    venue: json['venue']?.toString(),
  );
}

class MobileProfile {
  const MobileProfile({
    required this.id,
    required this.name,
    required this.username,
    required this.role,
    this.email,
    this.phone,
  });

  final int id;
  final String name;
  final String username;
  final String role;
  final String? email;
  final String? phone;

  factory MobileProfile.fromJson(Map<String, dynamic> json) => MobileProfile(
    id: _requiredInt(json, 'id'),
    name: _requiredString(json, 'name'),
    username: _requiredString(json, 'username'),
    role: _requiredString(json, 'role'),
    email: json['email']?.toString(),
    phone: json['phone']?.toString(),
  );
}

class SaleQuote {
  const SaleQuote({
    required this.subtotal,
    required this.discountAmount,
    required this.totalAmount,
  });

  final double subtotal;
  final double discountAmount;
  final double totalAmount;

  factory SaleQuote.fromJson(Map<String, dynamic> json) {
    return SaleQuote(
      subtotal: double.parse(json['subtotal'].toString()),
      discountAmount: double.parse(json['discount_amount'].toString()),
      totalAmount: double.parse(json['total_amount'].toString()),
    );
  }
}

class SaleResult {
  const SaleResult({
    required this.invoiceId,
    required this.invoiceNumber,
    required this.receiptNumber,
    required this.totalAmount,
    required this.amountPaid,
    required this.changeAmount,
    required this.balanceDue,
  });

  final int invoiceId;
  final String invoiceNumber;
  final String receiptNumber;
  final double totalAmount;
  final double amountPaid;
  final double changeAmount;
  final double balanceDue;

  factory SaleResult.fromJson(Map<String, dynamic> json) {
    final invoiceId = json['invoice_id'] as int;
    return SaleResult(
      invoiceId: invoiceId,
      invoiceNumber: _documentNumber(json, 'invoice_number', 'INV', invoiceId),
      receiptNumber: _documentNumber(json, 'receipt_number', 'RCT', invoiceId),
      totalAmount: double.parse(json['total_amount'].toString()),
      amountPaid: double.parse(json['amount_paid'].toString()),
      changeAmount: double.parse(json['change_amount'].toString()),
      balanceDue: double.parse(json['balance_due'].toString()),
    );
  }
}

class SalesHistoryPage {
  const SalesHistoryPage({required this.sales, required this.nextOffset});

  final List<SaleHistoryEntry> sales;
  final int? nextOffset;

  factory SalesHistoryPage.fromJson(Map<String, dynamic> json) {
    final sales = json['sales'];
    if (sales is! List) {
      throw const FormatException('Invalid sales history response.');
    }
    final nextOffset = json['next_offset'];
    return SalesHistoryPage(
      sales: sales
          .map(
            (sale) => SaleHistoryEntry.fromJson(
              Map<String, dynamic>.from(sale as Map),
            ),
          )
          .toList(),
      nextOffset: nextOffset is num ? nextOffset.toInt() : null,
    );
  }
}

class DashboardSummary {
  const DashboardSummary({
    required this.totalPaidToday,
    required this.transactionCountToday,
    required this.recentSales,
  });

  final double totalPaidToday;
  final int transactionCountToday;
  final List<SaleHistoryEntry> recentSales;

  factory DashboardSummary.fromJson(Map<String, dynamic> json) {
    final sales = json['recent_sales'];
    if (sales is! List) {
      throw const FormatException('Invalid dashboard response.');
    }
    return DashboardSummary(
      totalPaidToday: _requiredNumber(json, 'total_paid_today'),
      transactionCountToday: _requiredInt(json, 'transaction_count_today'),
      recentSales: sales
          .map(
            (sale) => SaleHistoryEntry.fromJson(
              Map<String, dynamic>.from(sale as Map),
            ),
          )
          .toList(),
    );
  }
}

class SaleHistoryEntry {
  const SaleHistoryEntry({
    required this.invoiceId,
    required this.invoiceNumber,
    required this.receiptNumber,
    required this.createdAt,
    required this.customerName,
    required this.status,
    required this.totalAmount,
    required this.amountPaid,
    required this.balanceDue,
    required this.itemCount,
    required this.paymentMethods,
  });

  final int invoiceId;
  final String invoiceNumber;
  final String receiptNumber;
  final String? createdAt;
  final String customerName;
  final String status;
  final double totalAmount;
  final double amountPaid;
  final double balanceDue;
  final int itemCount;
  final List<String> paymentMethods;

  factory SaleHistoryEntry.fromJson(Map<String, dynamic> json) {
    final invoiceId = _requiredInt(json, 'invoice_id');
    final createdAt = json['created_at']?.toString();
    return SaleHistoryEntry(
      invoiceId: invoiceId,
      invoiceNumber: _documentNumber(
        json,
        'invoice_number',
        'INV',
        invoiceId,
        createdAt: createdAt,
      ),
      receiptNumber: _documentNumber(
        json,
        'receipt_number',
        'RCT',
        invoiceId,
        createdAt: createdAt,
      ),
      createdAt: createdAt,
      customerName: _requiredString(json, 'customer_name'),
      status: _requiredString(json, 'status'),
      totalAmount: _requiredNumber(json, 'total_amount'),
      amountPaid: _requiredNumber(json, 'amount_paid'),
      balanceDue: _requiredNumber(json, 'balance_due'),
      itemCount: _requiredInt(json, 'item_count'),
      paymentMethods: (json['payment_methods'] as List)
          .map((method) => method.toString())
          .toList(),
    );
  }
}

class SalesReport {
  const SalesReport({
    required this.dateFrom,
    required this.dateTo,
    required this.cashierName,
    required this.transactionCount,
    required this.totalSales,
    required this.vat,
    required this.totalPaid,
    required this.balanceDue,
    required this.sales,
    required this.paymentMethods,
    required this.itemsSold,
  });

  final String dateFrom;
  final String dateTo;
  final String cashierName;
  final int transactionCount;
  final double totalSales;
  final double vat;
  final double totalPaid;
  final double balanceDue;
  final List<SalesReportSale> sales;
  final List<SalesReportPaymentMethod> paymentMethods;
  final List<SalesReportItem> itemsSold;

  factory SalesReport.fromJson(Map<String, dynamic> json) {
    final sales = json['sales'];
    final paymentMethods = json['payment_methods'];
    final itemsSold = json['items_sold'];
    if (sales is! List || paymentMethods is! List || itemsSold is! List) {
      throw const FormatException('Invalid sales report response.');
    }
    return SalesReport(
      dateFrom: _requiredString(json, 'date_from'),
      dateTo: _requiredString(json, 'date_to'),
      cashierName: _requiredString(json, 'cashier_name'),
      transactionCount: _requiredInt(json, 'transaction_count'),
      totalSales: _requiredNumber(json, 'total_sales'),
      vat: _requiredNumber(json, 'vat'),
      totalPaid: _requiredNumber(json, 'total_paid'),
      balanceDue: _requiredNumber(json, 'balance_due'),
      sales: sales
          .map(
            (sale) => SalesReportSale.fromJson(
              Map<String, dynamic>.from(sale as Map),
            ),
          )
          .toList(),
      paymentMethods: paymentMethods
          .map(
            (method) => SalesReportPaymentMethod.fromJson(
              Map<String, dynamic>.from(method as Map),
            ),
          )
          .toList(),
      itemsSold: itemsSold
          .map(
            (item) => SalesReportItem.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
    );
  }
}

class SalesReportSale {
  const SalesReportSale({
    required this.invoiceId,
    required this.createdAt,
    required this.customerName,
    required this.status,
    required this.totalAmount,
    required this.amountPaid,
    required this.balanceDue,
    required this.paymentMethods,
  });

  final int invoiceId;
  final String? createdAt;
  final String customerName;
  final String status;
  final double totalAmount;
  final double amountPaid;
  final double balanceDue;
  final List<String> paymentMethods;

  factory SalesReportSale.fromJson(Map<String, dynamic> json) =>
      SalesReportSale(
        invoiceId: _requiredInt(json, 'invoice_id'),
        createdAt: json['created_at']?.toString(),
        customerName: _requiredString(json, 'customer_name'),
        status: _requiredString(json, 'status'),
        totalAmount: _requiredNumber(json, 'total_amount'),
        amountPaid: _requiredNumber(json, 'amount_paid'),
        balanceDue: _requiredNumber(json, 'balance_due'),
        paymentMethods: (json['payment_methods'] as List)
            .map((method) => method.toString())
            .toList(),
      );
}

class SalesReportPaymentMethod {
  const SalesReportPaymentMethod({
    required this.name,
    required this.transactionCount,
    required this.amount,
  });

  final String name;
  final int transactionCount;
  final double amount;

  factory SalesReportPaymentMethod.fromJson(Map<String, dynamic> json) =>
      SalesReportPaymentMethod(
        name: _requiredString(json, 'payment_method'),
        transactionCount: _requiredInt(json, 'transaction_count'),
        amount: _requiredNumber(json, 'amount'),
      );
}

class SalesReportItem {
  const SalesReportItem({
    required this.name,
    required this.quantitiesByType,
    required this.totalAmount,
  });

  final String name;
  final Map<String, double> quantitiesByType;
  final double totalAmount;

  factory SalesReportItem.fromJson(Map<String, dynamic> json) {
    final quantitiesByType = json['quantities_by_type'];
    if (quantitiesByType is! Map) {
      throw const FormatException('Invalid sales report item quantities.');
    }
    return SalesReportItem(
      name: _requiredString(json, 'item_name'),
      quantitiesByType: quantitiesByType.map((type, quantity) {
        final parsed = double.tryParse(quantity.toString());
        if (parsed == null || !parsed.isFinite) {
          throw const FormatException('Invalid sales report item quantity.');
        }
        return MapEntry(type.toString(), parsed);
      }),
      totalAmount: _requiredNumber(json, 'total_amount'),
    );
  }
}

class SaleReceipt {
  const SaleReceipt({
    required this.invoiceId,
    required this.invoiceNumber,
    required this.receiptNumber,
    required this.status,
    required this.createdAt,
    required this.customerName,
    required this.eventName,
    required this.cashierName,
    required this.lines,
    required this.payments,
    required this.subtotal,
    required this.discountAmount,
    required this.totalAmount,
    required this.amountPaid,
    required this.balanceDue,
    required this.changeAmount,
  });

  final int invoiceId;
  final String invoiceNumber;
  final String receiptNumber;
  final String status;
  final String? createdAt;
  final String customerName;
  final String? eventName;
  final String? cashierName;
  final List<ReceiptLine> lines;
  final List<ReceiptPayment> payments;
  final double subtotal;
  final double discountAmount;
  final double totalAmount;
  final double amountPaid;
  final double balanceDue;
  final double changeAmount;

  factory SaleReceipt.fromJson(Map<String, dynamic> json) {
    final invoiceId = _requiredInt(json, 'invoice_id');
    final createdAt = json['created_at']?.toString();
    return SaleReceipt(
      invoiceId: invoiceId,
      invoiceNumber: _documentNumber(
        json,
        'invoice_number',
        'INV',
        invoiceId,
        createdAt: createdAt,
      ),
      receiptNumber: _documentNumber(
        json,
        'receipt_number',
        'RCT',
        invoiceId,
        createdAt: createdAt,
      ),
      status: _requiredString(json, 'status'),
      createdAt: createdAt,
      customerName: _requiredString(json, 'customer_name'),
      eventName: json['event_name']?.toString(),
      cashierName: json['cashier_name']?.toString(),
      lines: (json['lines'] as List)
          .map(
            (line) =>
                ReceiptLine.fromJson(Map<String, dynamic>.from(line as Map)),
          )
          .toList(),
      payments: (json['payments'] as List)
          .map(
            (payment) => ReceiptPayment.fromJson(
              Map<String, dynamic>.from(payment as Map),
            ),
          )
          .toList(),
      subtotal: _requiredNumber(json, 'subtotal'),
      discountAmount: _requiredNumber(json, 'discount_amount'),
      totalAmount: _requiredNumber(json, 'total_amount'),
      amountPaid: _requiredNumber(json, 'amount_paid'),
      balanceDue: _requiredNumber(json, 'balance_due'),
      changeAmount: _requiredNumber(json, 'change_amount'),
    );
  }
}

class ReceiptLine {
  const ReceiptLine({
    required this.name,
    required this.description,
    required this.quantity,
    required this.unitPrices,
    required this.total,
  });

  final String name;
  final String description;
  final double quantity;
  final List<ReceiptUnitPrice> unitPrices;
  final double total;

  factory ReceiptLine.fromJson(Map<String, dynamic> json) {
    return ReceiptLine(
      name: _requiredString(json, 'name'),
      description: _requiredString(json, 'description'),
      quantity: _requiredNumber(json, 'quantity'),
      unitPrices: (json['unit_prices'] as List)
          .map(
            (price) => ReceiptUnitPrice.fromJson(
              Map<String, dynamic>.from(price as Map),
            ),
          )
          .toList(),
      total: _requiredNumber(json, 'total'),
    );
  }
}

class ReceiptUnitPrice {
  const ReceiptUnitPrice({
    required this.quantity,
    required this.priceType,
    required this.unitPrice,
  });

  final double quantity;
  final String priceType;
  final double unitPrice;

  factory ReceiptUnitPrice.fromJson(Map<String, dynamic> json) {
    return ReceiptUnitPrice(
      quantity: _requiredNumber(json, 'quantity'),
      priceType: _requiredString(json, 'price_type'),
      unitPrice: _requiredNumber(json, 'unit_price'),
    );
  }
}

class ReceiptPayment {
  const ReceiptPayment({
    required this.createdAt,
    required this.paymentMethod,
    required this.amount,
    required this.changeAmount,
  });

  final String? createdAt;
  final String? paymentMethod;
  final double amount;
  final double changeAmount;

  factory ReceiptPayment.fromJson(Map<String, dynamic> json) {
    return ReceiptPayment(
      createdAt: json['created_at']?.toString(),
      paymentMethod: json['payment_method']?.toString(),
      amount: _requiredNumber(json, 'amount'),
      changeAmount: _requiredNumber(json, 'change_amount'),
    );
  }
}

String _requiredString(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is String) return value;
  throw FormatException('Invalid item field: $key');
}

int _requiredInt(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is int) return value;
  if (value is num && value.isFinite && value == value.roundToDouble()) {
    return value.toInt();
  }
  final parsed = int.tryParse(value?.toString() ?? '');
  if (parsed != null) return parsed;
  throw FormatException('Invalid item field: $key');
}

double _requiredNumber(Map<String, dynamic> json, String key) {
  final value = json[key];
  final parsed = value is num ? value.toDouble() : double.tryParse('$value');
  if (parsed != null && parsed.isFinite) return parsed;
  throw FormatException('Invalid item field: $key');
}

String _documentNumber(
  Map<String, dynamic> json,
  String key,
  String prefix,
  int recordId, {
  String? createdAt,
}) {
  final number = json[key]?.toString();
  if (number != null && number.isNotEmpty) return number;
  final year = DateTime.tryParse(createdAt ?? '')?.year ?? DateTime.now().year;
  return '$prefix-$year-${recordId.toString().padLeft(5, '0')}';
}
