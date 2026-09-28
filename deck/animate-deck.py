"""
Post-process the pptxgenjs output:

  1. de-duplicate media  — pptxgenjs writes a fresh copy of an image every
     time it is placed; the same GIF on 24 slides becomes 24 files. Identical
     parts are merged and every slide relationship points at the survivor.
  2. Morph transitions   — every slide gets Morph "by object" (PowerPoint
     2019 / 365), with a Fade fallback for older versions. Elements that
     recur under the same "!!name" (brand, chapter pill, title, page number,
     corner decoration) glide between slides instead of cutting.
  3. entrance builds     — shapes named anim_<order>_<n> fade up in order
     when the slide opens (no clicks), 120 ms apart per order step.

    python deck/animate-deck.py [in.pptx] [out.pptx]
"""
import hashlib
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "ppt", "NovaBand_Deck_Neumorph.pptx")
DST = sys.argv[2] if len(sys.argv) > 2 else SRC

parts = {}
with zipfile.ZipFile(SRC) as z:
    order = z.namelist()
    for n in order:
        parts[n] = z.read(n)

# ------------------------------------------------------------ 1. media dedup
canon, drop = {}, {}
for n in order:
    if n.startswith("ppt/media/"):
        h = hashlib.sha1(parts[n]).hexdigest()
        if h in canon:
            drop[n] = canon[h]
        else:
            canon[h] = n
for n in list(parts):
    if n.endswith(".rels"):
        x = parts[n].decode("utf8")
        for dup, keep in drop.items():
            x = x.replace("../media/" + os.path.basename(dup) + '"', "../media/" + os.path.basename(keep) + '"')
        parts[n] = x.encode("utf8")
for dup in drop:
    del parts[dup]
ct = parts["[Content_Types].xml"].decode("utf8")
for dup in drop:
    ct = re.sub(r'<Override PartName="/%s"[^>]*/>' % re.escape(dup), "", ct)
parts["[Content_Types].xml"] = ct.encode("utf8")

# ------------------------------------------------------------ 2+3. per slide
TRANSITION = (
    '<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
    '<mc:Choice xmlns:p159="http://schemas.microsoft.com/office/powerpoint/2015/09/main" '
    'xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" Requires="p159">'
    '<p:transition spd="slow" p14:dur="1200"><p159:morph option="byObject"/></p:transition></mc:Choice>'
    '<mc:Fallback><p:transition spd="slow"><p:fade/></p:transition></mc:Fallback></mc:AlternateContent>'
)


def effect(ctn, spid, delay):
    """Fade + rise ('fade up'), the same build AQUENT's deck uses (preset 42)."""
    a, b, c, d = ctn, ctn + 1, ctn + 2, ctn + 3
    return (
        f'<p:par><p:cTn id="{a}" presetID="42" presetClass="entr" presetSubtype="0" fill="hold" grpId="0" '
        f'nodeType="withEffect"><p:stCondLst><p:cond delay="{delay}"/></p:stCondLst><p:childTnLst>'
        f'<p:set><p:cBhvr><p:cTn id="{b}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
        f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName>'
        f'</p:attrNameLst></p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>'
        f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{c}" dur="650"/>'
        f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect>'
        f'<p:anim calcmode="lin" valueType="num"><p:cBhvr><p:cTn id="{d}" dur="650" decel="100000" fill="hold"/>'
        f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl><p:attrNameLst><p:attrName>ppt_y</p:attrName></p:attrNameLst>'
        f'</p:cBhvr><p:tavLst><p:tav tm="0"><p:val><p:strVal val="#ppt_y+0.04"/></p:val></p:tav>'
        f'<p:tav tm="100000"><p:val><p:strVal val="#ppt_y"/></p:val></p:tav></p:tavLst></p:anim>'
        f'</p:childTnLst></p:cTn></p:par>'
    )


SHAPE = re.compile(r"<p:(sp|pic|graphicFrame)>(.*?)</p:\1>", re.S)
NAME = re.compile(r'<p:cNvPr id="(\d+)" name="anim_(\d+)_\d+"')

stats = []
for n in sorted(parts):
    m = re.match(r"ppt/slides/slide(\d+)\.xml$", n)
    if not m:
        continue
    x = parts[n].decode("utf8")
    targets = []
    for kind, body in SHAPE.findall(x):
        k = NAME.search(body)
        if k:
            targets.append((int(k.group(2)), int(k.group(1)), kind == "sp" and "<p:txBody>" in body))
    targets.sort(key=lambda t: (t[0], t[1]))

    timing = ""
    if targets:
        ranks = {o: r for r, o in enumerate(sorted({t[0] for t in targets}))}
        ctn, effects = 3, []
        for o, spid, _ in targets:
            effects.append(effect(ctn, spid, 150 + ranks[o] * 120))
            ctn += 4
        outer, inner = ctn, ctn + 1
        bld = "".join(f'<p:bldP spid="{spid}" grpId="0" animBg="1"/>' for _, spid, tx in targets if tx)
        timing = (
            '<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
            '<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
            f'<p:par><p:cTn id="{outer}" fill="hold"><p:stCondLst><p:cond delay="indefinite"/>'
            '<p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst><p:childTnLst>'
            f'<p:par><p:cTn id="{inner}" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
            + "".join(effects) +
            '</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>'
            '</p:childTnLst></p:cTn><p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl>'
            '</p:cond></p:prevCondLst><p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl>'
            '</p:cond></p:nextCondLst></p:seq></p:childTnLst></p:cTn></p:par></p:tnLst>'
            + (f"<p:bldLst>{bld}</p:bldLst>" if bld else "") + "</p:timing>"
        )
    # pptxgenjs closes an inner shadow with </a:outerShdw>: invalid XML PowerPoint rejects
    x = re.sub(r"(<a:innerShdw\b[^>]*>.*?</a:srgbClr>\s*)</a:outerShdw>", r"\1</a:innerShdw>", x, flags=re.S)
    # an empty <a:ln> leaves the outline to defaults; say "no line" explicitly
    x = x.replace("<a:ln></a:ln>", "<a:ln><a:noFill/></a:ln>")
    x = re.sub(r"<p:transition.*?</p:transition>|<mc:AlternateContent.*?</mc:AlternateContent>|<p:timing>.*?</p:timing>",
               "", x, flags=re.S)
    x = x.replace("</p:clrMapOvr>", "</p:clrMapOvr>" + TRANSITION + timing, 1)
    parts[n] = x.encode("utf8")
    stats.append((int(m.group(1)), len(targets)))

tmp = DST + ".tmp"
with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
    for n in order:
        if n in parts:
            # GIF/PNG/JPG are already compressed — store them, deflate the XML
            ctype = zipfile.ZIP_STORED if n.startswith("ppt/media/") else zipfile.ZIP_DEFLATED
            z.writestr(n, parts[n], compress_type=ctype)
os.replace(tmp, DST)

print("media: %d duplicates merged into %d unique parts" % (len(drop), len(canon)))
print("slides with builds:", ", ".join("%d(%d)" % s for s in sorted(stats)))
print("size: %.1f MB -> %s" % (os.path.getsize(DST) / 1e6, DST))
