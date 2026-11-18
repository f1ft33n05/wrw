import 'package:flutter_test/flutter_test.dart';
import 'package:pdf/pdf.dart';
import 'package:werwines/models.dart';
import 'package:werwines/utils/receipt_pdf.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('builds a PDF from the backend receipt data', () async {
    const receipt = SaleReceipt(
      invoiceId: 42,
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
}
