"""Offline text extraction for the attached LaTeX PDFs, not a general PDF parser.
Supports their Flate streams, object streams, single-byte ToUnicode CMaps and
text operators. Keeps page boundaries; original PDFs remain the authority.
"""
import re
import zlib
import hashlib
from pathlib import Path


def extract(path):
    raw = path.read_bytes()
    objects = {}
    streams = {}
    for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj\b(.*?)endobj',raw,re.S):
        oid = int(m[1]); body=m[3]; objects[oid]=body
        sm=re.search(rb'stream\r?\n(.*?)\r?\nendstream',body,re.S)
        if sm:
            b=sm[1]
            if b'/FlateDecode' in body[:sm.start()]: b=zlib.decompress(b)
            streams[oid]=b
    for oid,body in list(objects.items()):
        if b'/Type /ObjStm' not in body: continue
        first=int(re.search(rb'/First\s+(\d+)',body)[1]); n=int(re.search(rb'/N\s+(\d+)',body)[1])
        b=streams[oid]; pairs=list(map(int,b[:first].split()))
        for i in range(n):
            num,offset=pairs[2*i:2*i+2]; end=pairs[2*i+3] if i+1<n else len(b)-first
            objects[num]=b[first+offset:first+end]
    cmaps={}
    for oid,b in streams.items():
        if b'begincmap' not in b:continue
        cmap={}
        for part in re.findall(rb'beginbfchar(.*?)endbfchar',b,re.S):
            for a,c in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>',part):
                cmap[int(a,16)]=bytes.fromhex(c.decode()).decode('utf-16-be')
        for part in re.findall(rb'beginbfrange(.*?)endbfrange',b,re.S):
            for a,c,d in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>',part):
                for x in range(int(a,16),int(c,16)+1):cmap[x]=chr(int(d,16)+x-int(a,16))
        cmaps[oid]=cmap
    fonts={}
    for body in objects.values():
        for name,ref in re.findall(rb'/(F\d+)\s+(\d+)\s+0\s+R',body):
            fb=objects.get(int(ref),b'');tm=re.search(rb'/ToUnicode\s+(\d+)\s+0\s+R',fb)
            if tm:fonts[name.decode()]=cmaps[int(tm[1])]
    token = re.compile(rb'\((?:\\(?:[0-7]{1,3}|\r?\n|.)|[^\\()])*\)|<[0-9a-fA-F\s]+>|/[^\s\[\]()<>]+|[-+]?\d*\.?\d+|[A-Za-z\x27\x22]+|[\[\]]',re.S)
    def string(t):
        if t.startswith(b'<'):return bytes.fromhex(t[1:-1].decode())
        b=t[1:-1];out=bytearray();i=0
        while i<len(b):
            if b[i]!=92:out.append(b[i]);i+=1;continue
            i+=1
            if i>=len(b):break
            if 48<=b[i]<=55:
                j=i+1
                while j<min(i+3,len(b)) and 48<=b[j]<=55:j+=1
                out.append(int(b[i:j],8));i=j
            elif b[i] in (10,13):
                if b[i]==13 and i+1<len(b) and b[i+1]==10:i+=1
                i+=1
            else:out.extend({ord('n'):b'\n',ord('r'):b'\r',ord('t'):b'\t'}.get(b[i],bytes([b[i]])));i+=1
        return bytes(out)
    pages=[]
    # Page-tree order, rather than object-number order (linearized PDFs differ).
    pages_root=next((oid for oid,b in objects.items() if re.search(rb'/Type\s*/Catalog\b',b)),None)
    root=int(re.search(rb'/Pages\s+(\d+)\s+0\s+R',objects[pages_root])[1])
    def walk(oid):
        body=objects[oid]
        if re.search(rb'/Type\s*/Page\b',body):pages.append(body);return
        kids=re.search(rb'/Kids\s*\[(.*?)\]',body,re.S)
        for ref in re.findall(rb'(\d+)\s+0\s+R',kids[1]):walk(int(ref))
    walk(root)
    result=[]
    for page_number,body in enumerate(pages,1):
        refs=re.search(rb'/Contents\s*(\[.*?\]|\d+\s+0\s+R)',body,re.S)
        content=b'\n'.join(streams[int(x)] for x in re.findall(rb'(\d+)\s+0\s+R',refs[1]))
        output=[];args=[];font='';inside=False
        for t in token.findall(content):
            if t==b'BT':inside=True;args=[];output.append('\n');continue
            if t==b'ET':inside=False;args=[];output.append('\n');continue
            if not inside:continue
            if t in (b'Tf',b'Td',b'TD',b'Tm',b'Tj',b'TJ',b'T*',b"'",b'"'):
                if t==b'Tf':font=next((x[1:].decode() for x in args if x.startswith(b'/')),font)
                elif t in (b'Td',b'TD'):
                    if len(args)>=2 and float(args[-1])!=0:output.append('\n')
                elif t in (b'Tm',b'T*'):output.append('\n')
                else:
                    for x in args:
                        if x.startswith((b'(',b'<')):
                            output.append(''.join(fonts.get(font,{}).get(c,chr(c)) for c in string(x)))
                        elif re.fullmatch(rb'[-+]?\d*\.?\d+',x) and float(x)<-100:output.append(' ')
                args=[]
            elif t in (b'Tc',b'Tw',b'Tz',b'TL',b'Tr',b'Ts',b'g',b'G'):args=[]
            else:args.append(t)
        text=''.join(output).replace('\u2423',' ')
        text=re.sub(r'\n[ \t]*\n+', '\n',text)
        result.append(f'\n## PDF page {page_number}\n'+text.strip()+'\n')
    return f'# Extracted from {path.name}\n\nSHA-256: {hashlib.sha256(raw).hexdigest()}\nPages: {len(pages)}\n'+''.join(result)


if __name__=='__main__':
    root=Path(__file__).resolve().parents[2]
    out=root/'docs/organizer/attachments';out.mkdir(parents=True,exist_ok=True)
    for path in (root.parent/'uploads').glob('*.pdf'):
        dest=out/(path.stem+'.md');dest.write_text(extract(path));print(dest)
