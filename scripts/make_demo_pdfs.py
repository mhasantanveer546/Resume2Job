"""Create five synthetic selectable-text resume PDFs using the parser dependency."""
from pathlib import Path
import pymupdf as fitz
root=Path(__file__).resolve().parents[1]
(root/'demo').mkdir(exist_ok=True)
for path in (root/'tests/fixtures').glob('*.txt'):
    doc=fitz.open();page=doc.new_page(width=595,height=842)
    text=path.read_text().replace('—','-').replace('–','-')
    remaining=page.insert_textbox(fitz.Rect(45,55,550,790),text,fontsize=11,lineheight=1.5,fontname='helv')
    assert remaining>=0,path
    doc.save(root/'demo'/f'{path.stem}.pdf')
    if path.stem=='ayesha':page.get_pixmap().save('/tmp/r2j-demo-pdf.png')
