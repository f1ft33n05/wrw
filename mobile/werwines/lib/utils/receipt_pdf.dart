import 'package:flutter/services.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

import '../config/api_config.dart';
import '../models.dart';
import 'formatting.dart';

PdfPageFormat thermalReceiptPageFormat(SaleReceipt receipt) {
  const mm = PdfPageFormat.mm;
  final itemHeight = receipt.lines.fold<double>(0, (total, line) {
    final descriptionLines = (line.description.length / 28).ceil().clamp(1, 8);
    return total + 7 * descriptionLines + 5 * line.unitPrices.length + 3;
  });
  final pageHeight = (105 + itemHeight).clamp(125, 1200) * mm;
  return PdfPageFormat(80 * mm, pageHeight, marginAll: 4 * mm);
}

Future<Uint8List> buildReceiptPdf(
  SaleReceipt receipt, {
  required bool showCashierName,
}) async {
  final logo = pw.MemoryImage(
    (await rootBundle.load('assets/images/wrw-dark.png')).buffer.asUint8List(),
  );
  final document = pw.Document();
  document.addPage(
    pw.Page(
      pageFormat: thermalReceiptPageFormat(receipt),
      build: (context) => pw.Column(
        crossAxisAlignment: pw.CrossAxisAlignment.stretch,
        children: [
          pw.Center(
            child: pw.Image(
              logo,
              width: 42 * PdfPageFormat.mm,
              height: 14 * PdfPageFormat.mm,
            ),
          ),
          pw.SizedBox(height: 1 * PdfPageFormat.mm),
          _centered('Area 47, Sector 4. Lilongwe. Malawi.'),
          _centered('info@wearewines.com'),
          _centered('+265 (0) 999 123 456'),
          pw.SizedBox(height: 4 * PdfPageFormat.mm),
          _metadata('Receipt #', '${receipt.invoiceId}'),
          _metadata('Date', _formatReceiptDate(receipt.createdAt)),
          if (showCashierName && receipt.cashierName != null)
            _metadata('Cashier', receipt.cashierName!),
          _metadata('Customer', receipt.customerName),
          if (receipt.eventName != null) _metadata('Event', receipt.eventName!),
          pw.SizedBox(height: 4 * PdfPageFormat.mm),
          pw.Table(
            columnWidths: const {
              0: pw.FlexColumnWidth(3.2),
              1: pw.FlexColumnWidth(0.7),
              2: pw.FlexColumnWidth(1.7),
              3: pw.FlexColumnWidth(1.7),
            },
            children: [
              pw.TableRow(
                decoration: const pw.BoxDecoration(
                  border: pw.Border(
                    bottom: pw.BorderSide(color: PdfColors.grey500, width: 0.6),
                  ),
                ),
                children: [
                  _tableCell('Item', bold: true),
                  _tableCell('Qty', bold: true, align: pw.TextAlign.right),
                  _tableCell(
                    'Unit Price',
                    bold: true,
                    align: pw.TextAlign.right,
                  ),
                  _tableCell('Total', bold: true, align: pw.TextAlign.right),
                ],
              ),
              ...receipt.lines.map(
                (line) => pw.TableRow(
                  decoration: const pw.BoxDecoration(
                    border: pw.Border(
                      bottom: pw.BorderSide(
                        color: PdfColors.grey300,
                        width: 0.4,
                      ),
                    ),
                  ),
                  children: [
                    _tableCell(
                      line.description.isEmpty ? line.name : line.description,
                    ),
                    _tableCell(
                      _formatQuantity(line.quantity),
                      align: pw.TextAlign.right,
                    ),
                    _tableCell(
                      _unitPrices(line.unitPrices),
                      align: pw.TextAlign.right,
                    ),
                    _tableCell(
                      _plainAmount(line.total),
                      align: pw.TextAlign.right,
                    ),
                  ],
                ),
              ),
            ],
          ),
          pw.SizedBox(height: 3 * PdfPageFormat.mm),
          _figure('Total', formatMoney(receipt.totalAmount), bold: true),
          _figure('Paid', formatMoney(receipt.amountPaid)),
          _figure('Change', formatMoney(receipt.changeAmount)),
          _figure('Balance Due', formatMoney(receipt.balanceDue), bold: true),
          _figure('Payment Status', _titleCase(receipt.status)),
        ],
      ),
    ),
  );
  return document.save();
}

pw.Widget _centered(String value) => pw.Padding(
  padding: const pw.EdgeInsets.symmetric(vertical: 1),
  child: pw.Text(
    value,
    textAlign: pw.TextAlign.center,
    style: const pw.TextStyle(fontSize: 8),
  ),
);

pw.Widget _metadata(String label, String value) => pw.Padding(
  padding: const pw.EdgeInsets.symmetric(vertical: 1.5),
  child: pw.Text(
    '$label: $value',
    style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold),
  ),
);

pw.Widget _tableCell(String value, {bool bold = false, pw.TextAlign? align}) =>
    pw.Padding(
      padding: const pw.EdgeInsets.symmetric(vertical: 2, horizontal: 1),
      child: pw.Text(
        value,
        textAlign: align,
        style: pw.TextStyle(
          fontSize: 7,
          fontWeight: bold ? pw.FontWeight.bold : pw.FontWeight.normal,
        ),
      ),
    );

pw.Widget _figure(String label, String value, {bool bold = false}) {
  final style = pw.TextStyle(
    fontSize: 8,
    fontWeight: bold ? pw.FontWeight.bold : pw.FontWeight.normal,
  );
  return pw.Padding(
    padding: const pw.EdgeInsets.symmetric(vertical: 1.5),
    child: pw.Row(
      mainAxisAlignment: pw.MainAxisAlignment.end,
      children: [
        pw.Text('$label: ', style: style),
        pw.Text(value, style: style),
      ],
    ),
  );
}

String _unitPrices(List<ReceiptUnitPrice> prices) {
  if (prices.isEmpty) return '';
  return prices
      .map((price) {
        final amount = _plainAmount(price.unitPrice);
        return prices.length == 1
            ? amount
            : '${_formatQuantity(price.quantity)} @ $amount';
      })
      .join('\n');
}

String _plainAmount(double amount) =>
    formatMoney(amount).replaceFirst('${ApiConfig.currencyCode} ', '');

String _formatQuantity(double quantity) =>
    quantity == quantity.truncateToDouble()
    ? quantity.toStringAsFixed(0)
    : quantity.toString();

String _formatReceiptDate(String? value) {
  if (value == null) return 'Date unavailable';
  final date = DateTime.tryParse(value)?.toLocal();
  if (date == null) return value;
  return '${date.day.toString().padLeft(2, '0')}/'
      '${date.month.toString().padLeft(2, '0')}/${date.year} '
      '${date.hour.toString().padLeft(2, '0')}:'
      '${date.minute.toString().padLeft(2, '0')}';
}

String _titleCase(String value) => value
    .replaceAll('_', ' ')
    .split(' ')
    .map(
      (word) => word.isEmpty
          ? word
          : '${word[0].toUpperCase()}${word.substring(1).toLowerCase()}',
    )
    .join(' ');
