from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
root=Path(r"C:\Users\Владимир\Desktop\Сайты\Shans\tmp\pdfs")
for folder in [p for p in root.iterdir() if p.is_dir()]:
    files=sorted(folder.glob('page-*.png'))
    thumbs=[]
    for i,f in enumerate(files,1):
        im=Image.open(f).convert('RGB')
        im.thumbnail((320,180))
        canvas=Image.new('RGB',(330,205),'white')
        canvas.paste(im,((330-im.width)//2,5))
        ImageDraw.Draw(canvas).text((8,187),str(i),fill='black')
        thumbs.append(canvas)
    cols=4; rows=(len(thumbs)+cols-1)//cols
    sheet=Image.new('RGB',(cols*330,rows*205),(220,220,220))
    for idx,im in enumerate(thumbs): sheet.paste(im,((idx%cols)*330,(idx//cols)*205))
    sheet.save(root/(folder.name+'_contact.jpg'),quality=88)
