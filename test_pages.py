from weasyprint import HTML

html = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<style>
  @page {
    size: A4;
    margin: 2.2cm 1.8cm 2.2cm 1.8cm;
    @top-center { content: "PDFX AI — تقرير تجريبي"; font-family: 'Noto Sans Arabic'; font-size: 9pt; color: #6b7280; }
    @bottom-center { content: "صفحة " counter(page) " من " counter(pages); font-family: 'Noto Sans Arabic'; font-size: 9pt; color: #6b7280; }
  }
  body { font-family: 'Noto Naskh Arabic', 'Noto Sans Arabic', sans-serif; color: #1a1a2e; }
  h1 { color: #0d3b66; }
  .pagebreak { page-break-before: always; }
</style>
</head>
<body>
<h1>الصفحة الأولى</h1>
<p>محتوى الصفحة الأولى نص تجريبي طويل نسبيا لملء الصفحة. </p>
<div class="pagebreak"></div>
<h1>الصفحة الثانية</h1>
<p>محتوى الصفحة الثانية.</p>
</body>
</html>"""

HTML(string=html).write_pdf("test_pages.pdf")
print("done")
