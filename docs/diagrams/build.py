"""Create editable draw.io diagrams and matching PNGs from one layout."""
import html
from pathlib import Path
import xml.etree.ElementTree as ET
import cairosvg

HERE = Path(__file__).resolve().parent
BG, INK, BORDER = '#FFFFFF', '#243247', '#CCD5DF'
BLUE, GREEN, RED, AMBER = '#EAF2FF', '#E9F5EF', '#FFF0EF', '#FFF6DF'
CASES = [
    ('FE-1', 'Follower recovery', 'fe2', 'Follower down', 'Two voters keep metadata writes available'),
    ('FE-2', 'Leader recovery', 'fe2', 'Leader down', 'A surviving voter becomes leader'),
    ('FE-3', 'Leader isolation', None, '', 'Majority writes succeed; isolated FE cannot commit'),
    ('BE-1', 'Backend availability', 'be0', 'BE down', 'Two replicas per tablet keep writes available'),
    ('CRED-1', 'Password rotation', 'be0', 'Stale password', 'Force ESO sync, verify Secret, then restart BE-0'),
]

def build(case, title, failed, state, footer):
    model = ET.Element('mxGraphModel', adaptiveColors='auto', page='1', pageWidth='900', pageHeight='560')
    root = ET.SubElement(model, 'root')
    ET.SubElement(root, 'mxCell', id='0')
    ET.SubElement(root, 'mxCell', id='1', parent='0')
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="560" viewBox="0 0 900 560"><rect width="900" height="560" fill="{BG}"/>']
    sequence = 0
    def cell(label, x,y,w,h, style, parent='1', ident=None):
        nonlocal sequence
        sequence += 1
        c = ET.SubElement(root,'mxCell',id=ident or f's{sequence}',value=label,style=style+';html=1;',vertex='1',parent=parent)
        ET.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
    def text(label,x,y,w=400,size=16,color=INK,bold=False):
        cell(label,x,y,w,28,f'text;strokeColor=none;fillColor=none;align=left;fontSize={size};fontColor={color};fontStyle={1 if bold else 0}')
        svg.append(f'<text x="{x}" y="{y+21}" font-family="DejaVu Sans,sans-serif" font-size="{size}" fill="{color}" font-weight="{"bold" if bold else "normal"}">{html.escape(label)}</text>')
    def box(x,y,w,h,fill,stroke=BORDER,dash=False):
        dash_style = 'stroke-dasharray="7 5"' if dash else ''
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.5" {dash_style}/>')
    text(f'{case} · {title}',35,20,800,24,bold=True)
    cell('GKE · us-west4',35,75,830,365,'swimlane;startSize=32;rounded=1;fillColor=#F7F9FC;strokeColor=#CCD5DF;fontSize=16;align=left;spacingLeft=15',ident='region')
    box(35,75,830,365,'#F7F9FC')
    svg.append('<text x="53" y="100" font-family="DejaVu Sans" font-size="16" fill="#243247">GKE · us-west4</text>')
    positions={}
    for i,zone in enumerate(('a','b','c')):
        x=60+i*270
        zone_id=f'zone{i}'
        cell(f'us-west4-{zone}',x-35,48,240,290,'swimlane;startSize=35;rounded=1;fillColor=#FFFFFF;strokeColor=#CCD5DF;fontSize=15',parent='region',ident=zone_id)
        box(x,123,240,290,'#FFFFFF')
        svg.append(f'<text x="{x+120}" y="148" text-anchor="middle" font-family="DejaVu Sans" font-size="15" fill="{INK}">us-west4-{zone}</text>')
        for role,y,fill in [('FE',175,BLUE),('BE',300,GREEN)]:
            ident=f'{role.lower()}{i}'
            px=x+65
            positions[ident]=(px,y)
            bad=ident==failed
            nodefill=RED if bad else fill
            stroke='#CA534D' if bad else '#6E849C'
            label=f'{role}-{i}'
            cell(label,65,y-123,110,70,f'shape=cylinder3;boundedLbl=1;size=15;fillColor={nodefill};strokeColor={stroke};fontColor={INK};fontSize=17;fontStyle=1',parent=zone_id,ident=ident)
            svg.append(f'<path d="M {px} {y+12} C {px} {y-4} {px+110} {y-4} {px+110} {y+12} L {px+110} {y+58} C {px+110} {y+74} {px} {y+74} {px} {y+58} Z" fill="{nodefill}" stroke="{stroke}" stroke-width="1.6"/>')
            svg.append(f'<ellipse cx="{px+55}" cy="{y+12}" rx="55" ry="12" fill="{nodefill}" stroke="{stroke}" stroke-width="1.6"/>')
            svg.append(f'<text x="{px+55}" y="{y+48}" text-anchor="middle" font-family="DejaVu Sans" font-weight="bold" font-size="17" fill="{INK}">{label}</text>')
            if bad:
                text(state,px-10,y+75,180,14,'#B13B36')
    def edge(source,target,label,color='#3D6C99'):
        sx,sy=positions[source]; tx,ty=positions[target]
        c=ET.SubElement(root,'mxCell',id=f'e-{source}-{target}',value='',style=f'html=1;strokeColor={color};strokeWidth=2;endArrow=classic;fontSize=13;',edge='1',parent='region',source=source,target=target)
        ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
        x1=sx+110; x2=tx
        svg.append(f'<path d="M{x1} {sy+35} L{x2-8} {ty+35}" stroke="{color}" stroke-width="2" fill="none"/><path d="M{x2-8} {ty+30} L{x2} {ty+35} L{x2-8} {ty+40} Z" fill="{color}"/>')
        # A small label below the link leaves space around the cylinders.
        text(label,(x1+x2)/2-28,sy+43,120,12,color)
    if case in ('FE-1','FE-2','FE-3'):
        edge('fe0','fe1','2 voters')
    if case=='FE-2':
        text('New leader',395,258,160,14,'#2C6D50',True)
    if case=='FE-3':
        # A zone boundary indicates the database network partition.
        cell('',578,45,244,295,'rounded=1;fillColor=none;strokeColor=#CA534D;strokeWidth=2;dashed=1;',parent='region')
        svg.append('<rect x="613" y="120" width="244" height="295" rx="10" fill="none" stroke="#CA534D" stroke-width="2" stroke-dasharray="7 5"/>')
        text('Isolated leader',665,250,190,14,'#B13B36')
        text('Network partition',620,443,230,14,'#B13B36')
    if case=='BE-1':
        edge('be1','be2','2 replicas','#2C7B58')
    if case=='CRED-1':
        text('FE password rotated',60,443,280,14)
        text('ESO Secret still old',350,443,280,14,'#B13B36')
    text(footer,35,490,840,18,bold=True)
    text('Blue: FE   ·   Green: BE   ·   Red: fault',35,525,800,13,'#617185')
    svg.append('</svg>')
    mxfile=ET.Element('mxfile',host='app.diagrams.net')
    diagram=ET.SubElement(mxfile,'diagram',id=case,name=title)
    diagram.append(model)
    stem=case.lower()
    ET.indent(mxfile)
    (HERE/f'{stem}.drawio').write_text(ET.tostring(mxfile,encoding='unicode'))
    (HERE/f'{stem}.svg').write_text(''.join(svg))
    cairosvg.svg2png(bytestring=''.join(svg).encode(),write_to=str(HERE/f'{stem}.png'),output_width=1800,output_height=1120)

for case in CASES:
    build(*case)
print('Created five editable diagrams and five PNG exports.')
