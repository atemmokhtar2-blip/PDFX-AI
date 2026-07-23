from weasyprint import HTML

html = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<style>
  @page { size: A4; margin: 2cm; }
  body { font-family: 'Noto Naskh Arabic', sans-serif; }
  a { color: #0d3b66; text-decoration: none; }
  .pagebreak { page-break-before: always; }
  .toc-line::after { content: leader(".") target-counter(attr(href), page); float: left; }
</style>
</head>
<body>
<h1>الفهرس</h1>
<div class="toc-line"><a href="#sec1">القسم الأول</a></div>
<div class="toc-line"><a href="#sec2">القسم الثاني</a></div>
<div class="pagebreak"></div>
<h2 id="sec1">القسم الأول</h2>
<p>نص</p>
<div class="pagebreak"></div>
<h2 id="sec2">القسم الثاني</h2>
<p>نص</p>
</body>
</html>"""

HTML(string=html).write_pdf("test_toc.pdf")
print("done")
