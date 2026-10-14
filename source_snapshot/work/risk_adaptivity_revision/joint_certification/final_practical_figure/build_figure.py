"""Source-linked figure; data and inline TeX require only the standard library.

Use --render for optional Matplotlib PDF/PNG exports. No study output is edited.
"""
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math

HERE = Path(__file__).resolve().parent
JC = HERE.parent
CASE = 'external/hpm_1/2025-07-05/12'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def span(row, a, b):
    return max(row[a:b]) - min(row[a:b])


def lines_for(C, k, j):
    rows = []
    for c in C:
        if j < k:
            a, b = max(span(c, 0, j), span(c, j, k)), span(c, k, 6)
        else:
            a, b = span(c, 0, k), max(span(c, k, j), span(c, j, 6))
        rows.append((a - b, b))
    return rows


def knots(lines):
    points = {F(0), F(1)}
    for (m, b), (n, c) in combinations(lines, 2):
        if m != n:
            t = (c-b)/(m-n)
            if 0 < t < 1:
                points.add(t)
    return sorted(points)


def upper(lines, t):
    return max(m*t+b for m, b in lines)


def simplify(points):
    result = []
    for point in points:
        while len(result) >= 2:
            a, b = result[-2:]
            if (b[1]-a[1])*(point[0]-b[0]) != (point[1]-b[1])*(b[0]-a[0]):
                break
            result.pop()
        result.append(point)
    return result


def coord(points):
    return ' '.join(f'({float(x):.12g},{float(y):.12g})' for x, y in points)


def write_tex(curves, adaptive, theta, peak, replay):
    # TikZ coordinates are generated from exact rational knots and integer counts.
    out = [r'\begin{figure}[htbp]', r'\centering',
           r'\begin{tikzpicture}[x=0.0098\linewidth,y=0.0098\linewidth,',
           r'font=\scriptsize,line cap=round,line join=round]',
           r'\definecolor{auditblue}{HTML}{2166AC}',
           r'\definecolor{auditorange}{HTML}{D95F02}',
           r'\definecolor{auditgreen}{HTML}{238443}',
           r'\node[anchor=west,font=\small\bfseries] at (0,47) {(a) Choosing the second reading};',
           r'\node[anchor=west,font=\small\bfseries] at (53,47) {(b) Recorded precision success};']
    # A: x=7..46; y=11..41. B: x=59..98; y=11..41.
    def path(points, style, transform):
        return r'\draw['+style+'] '+ ' -- '.join(f'({x:.6f},{y:.6f})' for x,y in map(transform,points))+';'
    ta=lambda p:(7+39*float(p[0]),11+30*float(p[1]))
    tb=lambda p:(59+39*(float(p[0])-.4)/.2,11+30*(float(p[1])-40)/60)
    for xx in [F(0),F(1,2),F(1)]:
        x,y=ta((xx,F(0)))
        out += [f'\\draw ({x:.6f},11) -- ({x:.6f},10.3);',
                f'\\node[anchor=north] at ({x:.6f},10.1) {{{float(xx):g}}};']
    for yy in [F(0),F(1,2),F(1)]:
        x,y=ta((F(0),yy))
        out += [f'\\draw[black!12] (7,{y:.6f}) -- (46,{y:.6f});',
                f'\\node[anchor=east] at (6.4,{y:.6f}) {{{float(yy):g}}};']
    out += [r'\draw (7,41) -- (7,11) -- (46,11);',
            r'\draw[dashed,black!65] (7,26) -- (46,26);',
            r'\node[anchor=south east,fill=white,inner sep=1pt] at (46,26) {target $1/2$};']
    # All possible second queries shown, not only the favorable branch choices.
    styles={1:'auditblue,line width=.8pt',3:'black!35,densely dashed,line width=.55pt',
            4:'auditorange,line width=.8pt',5:'black!55,dotted,line width=.7pt'}
    for j in [3,5,1,4]:out.append(path(curves[j],styles[j],ta))
    out.append(path(adaptive,'black,line width=1.15pt',ta))
    px,py=ta((theta,peak))
    out += [f'\\draw[densely dotted] ({px:.6f},11) -- ({px:.6f},{py:.6f});',
            f'\\fill ({px:.6f},{py:.6f}) circle[radius=.45];',
            r'\node[anchor=north,fill=white,inner sep=1pt] at (31,23.9) {$\theta\simeq0.52266$};',
            r'\node[anchor=south] at (27,2) {First answer $t=(C_2-C_0)/E$};',
            r'\node[rotate=90] at (0.3,26) {Conditional worst joint width};',
            r'\draw[auditblue,line width=.8pt] (7,43.4) -- (10,43.4);',
            r'\node[anchor=west] at (10.5,43.4) {$j=1$};',
            r'\draw[auditorange,line width=.8pt] (20,43.4) -- (23,43.4);',
            r'\node[anchor=west] at (23.5,43.4) {$j=4$};',
            r'\draw[black!35,densely dashed] (33,43.4) -- (36,43.4);',
            r'\node[anchor=west] at (36.5,43.4) {$j=3,5$};']
    for yy in [40,60,80,100]:
        x,y=tb((F(2,5),F(yy)))
        out += [f'\\draw[black!12] (59,{y:.6f}) -- (98,{y:.6f});',
                f'\\node[anchor=east] at (58.4,{y:.6f}) {{{yy}}};']
    for xx in [F(2,5),F(9,20),F(1,2),F(11,20),F(3,5)]:
        x,y=tb((xx,F(40)))
        out += [f'\\draw ({x:.6f},11) -- ({x:.6f},10.3);',
                f'\\node[anchor=north] at ({x:.6f},10.1) {{{float(xx):.2f}}};']
    out.append(r'\draw (59,41) -- (59,11) -- (98,11);')
    color={'adaptive':'auditblue','fixed':'auditorange','greedy':'auditgreen'}
    for source in ['original','external']:
        for policy in ['fixed','greedy','adaptive']:
            points=replay[source][policy]
            style=color[policy]+',line width=.8pt'+(',dashed' if source=='external' else '')
            out.append(path(points,style,tb))
            for p in points:
                x,y=tb(p)
                if source=='original':out.append(f'\\fill[{color[policy]}] ({x:.6f},{y:.6f}) circle[radius=.35];')
                else:out.append(f'\\draw[{color[policy]},fill=white] ({x-.32:.6f},{y-.32:.6f}) rectangle ({x+.32:.6f},{y+.32:.6f});')
    out += [r'\node[anchor=south] at (79,2) {Relative width target $\tau$};',
            r'\node[rotate=90] at (52,26) {Success (\%)};']
    for x,policy,label in [(59,'adaptive','Adaptive'),(73,'fixed','Fixed'),(85,'greedy','Greedy')]:
        out += [f'\\draw[{color[policy]},line width=.8pt] ({x},43.4) -- ({x+2.5},43.4);',
                f'\\node[anchor=west] at ({x+3},43.4) {{{label}}};']
    out += [r'\end{tikzpicture}',
            r'\caption{An acquisition rule and its recorded outcomes. (a) Exact conditional envelopes from the saved HPM~1 comparison on 5 July 2025, 12:00--18:00 UTC, after querying boundary~2. Gray curves show the other second-query options; the black lower envelope selects boundary~4 below the switch and boundary~1 above it. Its maximum is about $0.47734$, below the half-width target for every possible first answer. (b) The adaptive, fixed-batch and greedy policies on all 819 original and 279 external blocks at five reporting targets. Solid curves represent the original panel and dashed curves the external panel. These exploratory recorded success rates use the existing $10^{-8}$ comparison tolerance; they are not worst-case precision probabilities.}',
            r'\label{fig:practical-guarantee-replay}',r'\end{figure}']
    (HERE/'figure_fragment.tex').write_text('\n'.join(out)+'\n',encoding='utf8')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--render',action='store_true')
    args=parser.parse_args()
    source=JC/'precision_external_results/plans.json'
    checked=JC/'main_inspectable_certificate_check.json'
    link=JC/'precision_external_results/adaptive_half_check.json'
    summary=JC/'review_sensitivity/results/threshold_summary.csv'
    data=json.loads(source.read_text()); witness=json.loads(checked.read_text()); cert=json.loads(link.read_text())
    assert witness['case']==CASE and witness['precision_plans_sha256']==sha(source)
    assert witness['adaptive_certificate_sha256']==sha(link)
    row=next(r for r in data['plans'] if r['id']==CASE)
    assert row['normalized_coefficients_exact']==witness['normalized_coefficients_exact']
    C=[list(map(F,r)) for r in row['normalized_coefficients_exact']]
    theta=F(witness['exact_switch'])
    branch=next(r for r in cert['cases'] if r['id']==CASE)
    assert branch['first_query']==2 and branch['branches'][0]['second']==4 and branch['branches'][1]['second']==1
    assert F(branch['branches'][0]['hi'])==theta==F(branch['branches'][1]['lo'])
    lines={j:lines_for(C,2,j) for j in [1,3,4,5]}
    curves={j:simplify([(t,upper(ls,t)) for t in knots(ls)]) for j,ls in lines.items()}
    points=knots([r for ls in lines.values() for r in ls])
    adaptive=simplify([(t,min(upper(ls,t) for ls in lines.values())) for t in points])
    peak=max(y for _,y in adaptive)
    assert upper(lines[1],theta)==upper(lines[4],theta)==peak<F(1,2)
    assert max(y for x,y in adaptive if x<=theta)<=F('0.47743079')
    assert max(y for x,y in adaptive if x>=theta)<=F('0.4774')
    for t in points:
        chosen=4 if t<theta else 1
        assert upper(lines[chosen],t)==min(upper(ls,t) for ls in lines.values())
    # Points are all exact line intersections; linear segments cover the continuum.
    replay={s:{p:[] for p in ['adaptive','fixed','greedy']} for s in ['original','external']}
    rows=list(csv.DictReader(summary.open(newline='',encoding='utf8')))
    for source_name in replay:
        for threshold in [F(2,5),F(9,20),F(1,2),F(11,20),F(3,5)]:
            selected=[r for r in rows if r['cohort']==source_name and r['meter']=='ALL' and F(r['threshold'])==threshold and r['baseline'] in ['fixed','greedy']]
            assert len(selected)==2
            n=int(selected[0]['blocks']);a=F(selected[0]['adaptive_success_count'])
            assert n==({'original':819,'external':279}[source_name])
            replay[source_name]['adaptive'].append((threshold,100*a/n))
            for r in selected:
                assert F(r['adaptive_success_count'])==a
                replay[source_name][r['baseline']].append((threshold,100*F(r['baseline_success_count'])/n))
    payload={'case':CASE,'input_sha256':{str(p.relative_to(JC)):sha(p) for p in [source,checked,link,summary]},
             'normalized_coefficients_exact':[[str(v) for v in c] for c in C],
             'first_query':2,'exact_switch':str(theta),'exact_maximum':str(peak),
             'switch_decimal':float(theta),'maximum_decimal':float(peak),
             'conditional_lines_exact':{str(j):[[str(x) for x in line] for line in ls] for j,ls in lines.items()},
             'curves_exact':{str(j):[[str(x),str(y)] for x,y in ps] for j,ps in curves.items()},
             'adaptive_curve_exact':[[str(x),str(y)] for x,y in adaptive],
             'replay_percent_exact':{s:{p:[[str(x),str(y)] for x,y in ps] for p,ps in rr.items()} for s,rr in replay.items()},
             'scope':'Figure reproduces existing exact certificate and retrospective threshold replay; no policy, result or observation changed.',
             'generator_sha256':sha(Path(__file__))}
    (HERE/'figure_data.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf8')
    write_tex(curves,adaptive,theta,peak,replay)
    if args.render:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D
        plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.4,'axes.titlesize':9,'axes.labelsize':8.5,'pdf.fonttype':42,'ps.fonttype':42})
        fig,axes=plt.subplots(1,2,figsize=(7.25,3.25),layout='constrained')
        ax=axes[0]
        styles={1:('#2166ac','-',1.2),3:('#aaa','--',.8),4:('#d95f02','-',1.2),5:('#777',':',1)}
        for j in [3,5,1,4]:
            pts=curves[j];color,style,lw=styles[j]
            ax.plot([float(x) for x,y in pts],[float(y) for x,y in pts],color=color,ls=style,lw=lw,label=f'Second query {j}')
        ax.plot([float(x) for x,y in adaptive],[float(y) for x,y in adaptive],color='black',lw=1.8,label='Chosen query')
        ax.axhline(.5,color='#777',ls='--',lw=.8)
        ax.text(.97,.512,'Target 1/2',ha='right',color='#555',fontsize=7.5)
        ax.vlines(float(theta),0,float(peak),color='#555',linestyle=':',lw=.8)
        ax.plot(float(theta),float(peak),'o',color='black',ms=3)
        ax.annotate(r'$\theta\approx0.52266$',xy=(float(theta),float(peak)),xytext=(.79,.34),arrowprops={'arrowstyle':'-','lw':.6},ha='center',fontsize=8)
        ax.set(xlim=(0,1),ylim=(0,1.04),xticks=[0,.25,.5,.75,1],yticks=[0,.25,.5,.75,1],xlabel=r'First answer $t=(C_2-C_0)/E$',ylabel='Conditional worst joint width')
        ax.set_title('(a) Choosing the second reading',loc='left',fontweight='bold')
        ax.legend(loc='upper center',ncol=2,frameon=False,fontsize=6.9,handlelength=1.6,columnspacing=.8)
        ax=axes[1];colors={'adaptive':'#2166ac','fixed':'#d95f02','greedy':'#238443'}
        for src,ls,marker in [('original','-','o'),('external','--','s')]:
            for policy in ['fixed','greedy','adaptive']:
                ps=replay[src][policy]
                ax.plot([float(x) for x,y in ps],[float(y) for x,y in ps],color=colors[policy],ls=ls,marker=marker,ms=3,mfc='white' if src=='external' else colors[policy],lw=1.2)
        ax.set(xlim=(.39,.61),ylim=(40,101),xticks=[.4,.45,.5,.55,.6],yticks=[40,60,80,100],xlabel=r'Relative width target $\tau$',ylabel='Recorded success (%)')
        ax.set_title('(b) Recorded precision success',loc='left',fontweight='bold')
        handles=[Line2D([0],[0],color=colors[p],lw=1.4,label={'adaptive':'Adaptive','fixed':'Fixed','greedy':'Greedy'}[p]) for p in ['adaptive','fixed','greedy']]
        ax.legend(handles=handles,loc='lower right',frameon=False,ncol=3,fontsize=7.2,handlelength=1.2,columnspacing=.8)
        ax.text(.01,.98,'Solid: original\nDashed: external',transform=ax.transAxes,va='top',fontsize=7.4)
        for ax in axes:
            ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',color='#ddd',lw=.5);ax.set_axisbelow(True)
        fig.savefig(HERE/'practical_guarantee_replay.pdf',metadata={'Title':'Exact acquisition rule and recorded precision sensitivity','CreationDate':None,'ModDate':None})
        fig.savefig(HERE/'practical_guarantee_replay.png',dpi=220)
        plt.close(fig)
    print(json.dumps({'status':'PASS','switch':float(theta),'maximum':float(peak),'curves':len(curves),'sensitivity_points':30,'rendered':args.render}))


if __name__=='__main__':main()
