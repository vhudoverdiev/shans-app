from docx import Document
from docx.oxml.ns import qn

doc = Document(r"C:\Users\Владимир\Desktop\Сайты\Передача\Презентация Peredacha\Раб.файлы для видео\Сценарий_видеопрезентации_CRM_Передача.docx")
for name in ["Normal", "Heading 1", "List Bullet"]:
    style = doc.styles[name]
    fonts = style.element.rPr.rFonts if style.element.rPr is not None else None
    print(name, {
        "font_name": style.font.name,
        "ascii": fonts.get(qn("w:ascii")) if fonts is not None else None,
        "hAnsi": fonts.get(qn("w:hAnsi")) if fonts is not None else None,
        "size": str(style.font.size),
        "bold": style.font.bold,
        "italic": style.font.italic,
        "color": str(style.font.color.rgb) if style.font.color.rgb else None,
        "before": str(style.paragraph_format.space_before),
        "after": str(style.paragraph_format.space_after),
        "line": str(style.paragraph_format.line_spacing),
    })
