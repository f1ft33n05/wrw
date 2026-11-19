import 'package:flutter_test/flutter_test.dart';
import 'package:pdf/pdf.dart';
import 'package:werwines/models.dart';
import 'package:werwines/utils/receipt_pdf.dart';
import 'package:werwines/utils/sales_report_pdf.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('builds a PDF from the backend receipt data', () async {
    const receipt = SaleReceipt(
      invoiceId: 42,
      invoiceNumber: 'INV-2026-00042',
      receiptNumber: 'RCT-2026-00042',
      status: 'paid',
      createdAt: '2026-11-18T10:00:00+02:00',
      customerName: 'Walk-in customer',
      eventName: null,
      cashierName: 'Cashier',
      lines: [
        ReceiptLine(
          name: 'Cabernet',
          description: 'Cabernet bottle',
          quantity: 1,
          unitPrices: [
            ReceiptUnitPrice(quantity: 1, priceType: 'retail', unitPrice: 1250),
          ],
          total: 1250,
        ),
      ],
      payments: [
        ReceiptPayment(
          createdAt: '2026-11-18T10:00:00+02:00',
          paymentMethod: 'cash',
          amount: 1250,
          changeAmount: 0,
        ),
      ],
      subtotal: 1250,
      discountAmount: 0,
      totalAmount: 1250,
      amountPaid: 1250,
      balanceDue: 0,
      changeAmount: 0,
    );

    final pdf = await buildReceiptPdf(receipt, showCashierName: true);

    expect(String.fromCharCodes(pdf.take(4)), '%PDF');
    expect(
      thermalReceiptPageFormat(receipt).width,
      closeTo(80 * PdfPageFormat.mm, 0.01),
    );
  });

  test(
    'builds an 80 mm cash-up report with payment and item breakdowns',
    () async {
      const report = SalesReport(
        dateFrom: '2026-11-18',
        dateTo: '2026-11-18',
        cashierName: 'Cashier Casey',
        transactionCount: 1,
        totalSales: 140,
        vat: 20,
        totalPaid: 140,
        balanceDue: 0,
        sales: [],
        paymentMethods: [
          SalesReportPaymentMethod(
            name: 'Cash',
            transactionCount: 1,
            amount: 140,
          ),
        ],
        itemsSold: [
          SalesReportItem(
            name: 'Pinotage',
            quantitiesByType: {'Retail': 3, 'Wholesale': 16},
            totalAmount: 140,
          ),
        ],
      );

      final pdf = await buildSalesReportPdf(report);

      expect(String.fromCharCodes(pdf.take(4)), '%PDF');
      expect(
        salesReportPageFormat(report).width,
        closeTo(80 * PdfPageFormat.mm, 0.01),
      );
    },
  );
}
