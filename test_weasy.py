from weasyprint import HTML

html = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<style>
  @page { size: A4; margin: 2cm; }
  body { font-family: 'Noto Naskh Arabic', 'Noto Sans Arabic', sans-serif; color: #1a1a2e; }
  h1 { color: #0d3b66; }
  table { width: 100%; border-collapse: collapse; }
  td, th { border: 1px solid #ccc; padding: 6px; }
</style>
</head>
<body>
<h1>تقرير تجريبي</h1>
<p>هذا نص تجريبي للتحقق من دعم اللغة العربية والاتجاه من اليمين لليسار. Testing English mixed in: Hello World 123.</p>
<table>
<tr><th>البند</th><th>القيمة</th></tr>
<tr><td>المبيعات</td><td>1000</td></tr>
</table>
</body>
</html>"""

HTML(string=html).write_pdf("test.pdf")
print("done")
