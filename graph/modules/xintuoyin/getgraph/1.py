from docling.document_converter import DocumentConverter

source = "/data1/liwu/xintuoyin/AI文件样例/补充医疗保险费用明细.xlsx"  # document per local path or URL
converter = DocumentConverter()
result = converter.convert(source)
print("\n")

#print(result.document.export_to_markdown())  # output: "## Docling Technical Report[...]"
print(result)