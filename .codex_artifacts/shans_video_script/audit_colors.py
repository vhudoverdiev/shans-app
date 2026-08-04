import collections
import re
import zipfile

path = r"C:\Users\Владимир\Desktop\Сайты\Shans\Сценарий_видеообзора_CRM_Shans_90сек.docx"
with zipfile.ZipFile(path) as archive:
    text = archive.read("word/document.xml").decode("utf-8")
colors = collections.Counter(re.findall(r'(?:val|fill|color)="([0-9A-Fa-f]{6})"', text))
print(colors.most_common())
