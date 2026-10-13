from pathlib import Path
base=Path(__file__).resolve().parent
p=base/'editorial/front.tex'
s=p.read_text(encoding='utf-8')
anchor='Historical adverse realized-width results are retained.'
addition='A four-model gate certifies 933 of 1,620 proposed winners against every alternative, versus 167 using separate-loss bounds.'
if addition not in s:
    assert anchor in s
    s=s.replace(anchor,addition+' '+anchor)
p.write_text(s,encoding='utf-8')
p=base/'practical/practical_subsection.tex'
s=p.read_text(encoding='utf-8')
s=s.replace('\\begin{tabular}{lrrrr}', '\\small\\setlength{\\tabcolsep}{4pt}\n\\begin{tabular}{lrrrr}')
s=s.replace('Unresolved reduction\\\\','Unresolved reduction\\\\')
p.write_text(s,encoding='utf-8')
