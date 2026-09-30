"""
Surat-surat Nova-Band untuk Dinas Kesehatan dan Dinas Kepemudaan dan Olahraga
Kota Surakarta — mengikuti pola berkas Tim ASTA (Desktop/ASTA/berkas):

  1. Surat permohonan dari SMA Negeri 1 Surakarta (kop resmi sekolah, ttd Kepala
     Sekolah) -> dibangun dari berkas Word ASTA agar kop, logo, dan blok tanda
     tangan identik.
  2. Konsep surat dukungan (untuk ditinjau & diterbitkan sendiri oleh Dinas di
     kop resminya) -> spanduk KONSEP, tempat kop, catatan untuk Dinas, tanda air.
  3. Lampiran ringkasan penelitian Nova-Band.

    python berkas/make_surat_novaband.py

Keluaran: berkas/permohonan, berkas/dukungan, berkas/lampiran (.docx + .pdf).
Folder berkas/ tidak ikut di-push ke GitHub (repo publik).
"""
import copy
import os
import shutil

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = r"C:\Users\mosto\Desktop\ASTA\berkas\audiensi\Surat Audiensi ASTA - Dinas Kesehatan Kota Surakarta.docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
GREY = RGBColor(0x6b, 0x74, 0x80)
BROWN = RGBColor(0x9a, 0x34, 0x12)
DOTS = ".................................."

JUDUL = ("Nova-Band: An AIoT-Driven Upper-Arm Wearable for Real-Time Physiological "
         "Monitoring and Running Performance")
TIM = ["Maheswara Nala Wisadewa", "Almira Edgina Nareswari Haryadi", "Azra Daniswara Tyandaru",
       "Dela Astiara", "Rizkyta Aufa Mutiagassania", "Satriya Javas Wibisono"]
PERIHAL = "Permohonan Audiensi dan Dukungan Penelitian Nova-Band"

INSTANSI = {
    "dinkes": dict(
        nama="Dinas Kesehatan Kota Surakarta",
        singkat="Dinas Kesehatan Kota Surakarta",
        tujuan=["dr. Retno Erawati Wulandari", "Kepala Dinas Kesehatan Kota Surakarta", "di Surakarta"],
        pejabat="dr. Retno Erawati Wulandari",
        jabatan=["Kepala Dinas Kesehatan", "Kota Surakarta,"],
        relevansi=(
            "Mengingat Dinas Kesehatan Kota Surakarta merupakan pemangku kebijakan kesehatan di tingkat kota, "
            "termasuk dalam upaya promotif dan preventif seperti Gerakan Masyarakat Hidup Sehat (GERMAS) dan "
            "pengendalian penyakit tidak menular, kami memandang penting untuk memperoleh arahan serta masukan "
            "mengenai aspek kesehatan dan keselamatan masyarakat yang berolahraga, khususnya pelari, sekaligus "
            "menjajaki kemungkinan keterkaitan penelitian ini dengan program kesehatan masyarakat setempat."),
        tujuan_audiensi=[
            "memperoleh masukan terkait aspek kesehatan, keselamatan, dan etika pemantauan kondisi fisiologis "
            "pelari melalui perangkat yang dikembangkan;",
            "menjajaki kemungkinan arahan dan dukungan Dinas, termasuk dalam bentuk surat dukungan, pada tahap "
            "pengujian dan pengembangan selanjutnya; dan",
            "memperluas wawasan tim mengenai kebutuhan nyata masyarakat yang berolahraga serta program "
            "kesehatan di Kota Surakarta."],
        pandangan=(
            "Dinas Kesehatan Kota Surakarta memandang bahwa upaya pengembangan teknologi pemantauan kondisi "
            "fisiologis yang terjangkau untuk mendukung aktivitas fisik yang aman sejalan dengan upaya promotif "
            "dan preventif di bidang kesehatan, termasuk Gerakan Masyarakat Hidup Sehat (GERMAS) dan "
            "pengendalian penyakit tidak menular di Kota Surakarta. Dukungan yang kami berikan meliputi:"),
        dukungan=[
            ("Dukungan moril", ", berupa apresiasi dan dorongan kepada tim peneliti untuk melanjutkan penelitian "
                               "dan pengembangan Nova-Band secara bertanggung jawab dan berorientasi pada keselamatan "
                               "pengguna."),
            ("Dukungan fasilitasi", ", berupa pengenalan dan sosialisasi Nova-Band dalam kegiatan promosi kesehatan "
                                    "serta kepada jejaring fasilitas pelayanan kesehatan dan pemangku kepentingan "
                                    "terkait di Kota Surakarta, sesuai dengan kewenangan Dinas dan setelah perangkat "
                                    "memenuhi persyaratan yang ditetapkan peraturan perundang-undangan."),
            ("Dukungan kepakaran", ", berupa kesempatan diskusi, pemberian masukan, dan pengarahan terkait aspek "
                                   "kesehatan olahraga, keselamatan, etika, serta regulasi yang relevan bagi "
                                   "pengembangan Nova-Band lebih lanjut.")],
        batasan=(
            "Dukungan ini diberikan dalam rangka pembinaan kegiatan penelitian dan inovasi pelajar, dan tidak "
            "merupakan pernyataan kelayakan klinis, rekomendasi penggunaan untuk diagnosis, maupun izin edar alat "
            "kesehatan. Pemanfaatan Nova-Band kepada masyarakat wajib memenuhi ketentuan peraturan perundang-"
            "undangan yang berlaku, termasuk perizinan alat kesehatan dari kementerian yang berwenang dan "
            "pelindungan data pribadi pengguna."),
    ),
    "dispora": dict(
        nama="Dinas Kepemudaan dan Olahraga Kota Surakarta",
        singkat="Dinas Kepemudaan dan Olahraga Kota Surakarta",
        tujuan=["Kepala Dinas Kepemudaan dan Olahraga Kota Surakarta", "Jl. Adi Sucipto No. 1, Manahan",
                "di Surakarta"],
        pejabat="( nama Kepala Dinas )",
        jabatan=["Kepala Dinas Kepemudaan dan Olahraga", "Kota Surakarta,"],
        relevansi=(
            "Mengingat Dinas Kepemudaan dan Olahraga Kota Surakarta merupakan pemangku kebijakan di bidang "
            "kepemudaan dan keolahragaan, termasuk pembinaan olahraga rekreasi dan prestasi serta penyelenggaraan "
            "kegiatan olahraga masyarakat, kami memandang penting untuk memperoleh arahan serta masukan mengenai "
            "kebutuhan pelari, komunitas olahraga, dan penyelenggara kegiatan olahraga di Kota Surakarta, "
            "sekaligus menjajaki peluang penerapan penelitian ini untuk mendukung kegiatan olahraga yang aman "
            "dan terukur."),
        tujuan_audiensi=[
            "memperoleh masukan terkait kebutuhan pembinaan olahraga, komunitas lari, dan keselamatan "
            "penyelenggaraan kegiatan olahraga;",
            "menjajaki kemungkinan arahan dan dukungan Dinas, termasuk surat dukungan serta fasilitasi uji coba "
            "lapangan bersama komunitas atau kegiatan olahraga di Kota Surakarta; dan",
            "mengembangkan wawasan tim sebagai pemuda inovator di bidang teknologi olahraga."],
        pandangan=(
            "Dinas Kepemudaan dan Olahraga Kota Surakarta memandang bahwa upaya pengembangan teknologi yang "
            "membantu masyarakat berolahraga secara aman dan terukur sejalan dengan pembinaan dan pengembangan "
            "olahraga rekreasi maupun prestasi, serta pemberdayaan pemuda di bidang inovasi di Kota Surakarta. "
            "Dukungan yang kami berikan meliputi:"),
        dukungan=[
            ("Dukungan moril", ", berupa apresiasi dan dorongan kepada tim peneliti sebagai pemuda inovator untuk "
                               "melanjutkan penelitian dan pengembangan Nova-Band secara bertanggung jawab."),
            ("Dukungan fasilitasi", ", berupa fasilitasi uji coba lapangan serta pengenalan Nova-Band kepada "
                                    "komunitas olahraga dan kegiatan olahraga masyarakat di Kota Surakarta, sesuai "
                                    "dengan kewenangan Dinas dan dengan persetujuan peserta."),
            ("Dukungan kepakaran", ", berupa kesempatan diskusi, pemberian masukan, dan pengarahan terkait aspek "
                                   "keolahragaan, pelatihan, serta keselamatan penyelenggaraan kegiatan olahraga "
                                   "bagi pengembangan Nova-Band lebih lanjut.")],
        batasan=(
            "Dukungan ini diberikan dalam rangka pembinaan kegiatan penelitian dan inovasi pelajar, dan tidak "
            "merupakan rekomendasi komersial atas produk maupun pernyataan kelayakan sebagai alat kesehatan. "
            "Pelaksanaan uji coba dan pemanfaatan Nova-Band kepada masyarakat wajib memenuhi ketentuan peraturan "
            "perundang-undangan yang berlaku, termasuk persetujuan peserta dan pelindungan data pribadi."),
    ),
}

RINGKAS = (
    "Nova-Band merupakan purwarupa perangkat wearable yang dikenakan di lengan atas untuk memantau detak "
    "jantung melalui sensor optik (PPG) dan gerak tubuh melalui sensor inersia (IMU) secara waktu nyata. "
    "Data diolah langsung pada perangkat dan diteruskan ke aplikasi, sehingga peringatan dini dapat diterima "
    "pelari sekaligus pendamping atau pengawas kegiatan apabila batas aman terlampaui. Pada validasi awal, "
    "galat sensor tercatat pada kisaran MAPE 2,5–3,5% terhadap motion capture berkecepatan tinggi dan skor "
    "usability SUS 84,5 dari 60 responden. Penelitian ini masih berstatus purwarupa dan bukan merupakan "
    "alat kesehatan.")


# ---------------------------------------------------------------- helpers (python-docx / XML)
def set_runs(p_el, segs):
    """Replace a paragraph's runs with `segs` [(text, {'b','i'})], keeping the first run's formatting."""
    runs = p_el.findall(W + "r")
    base = copy.deepcopy(runs[0]) if runs else None
    for r in runs:
        p_el.remove(r)
    for text, fmt in segs:
        r = copy.deepcopy(base) if base is not None else OxmlElement("w:r")
        for t in r.findall(W + "t"):
            r.remove(t)
        rpr = r.find(W + "rPr")
        if rpr is None:
            rpr = OxmlElement("w:rPr")
            r.insert(0, rpr)
        for tag in ("b", "i"):
            for old in rpr.findall(W + tag):
                rpr.remove(old)
            if fmt.get(tag):
                rpr.append(OxmlElement("w:" + tag))
        t = OxmlElement("w:t")
        t.set(qn("xml:space"), "preserve")
        t.text = text
        r.append(t)
        p_el.append(r)


def fix_table(table, widths_cm):
    """Fixed layout with explicit column widths (the template's tables autofit badly in Word)."""
    tbl = table._tbl
    tblPr = tbl.tblPr
    for tag in ("tblW", "tblLayout"):
        for old in tblPr.findall(W + tag):
            tblPr.remove(old)
    tw = OxmlElement("w:tblW"); tw.set(qn("w:w"), str(int(sum(widths_cm) * 567))); tw.set(qn("w:type"), "dxa")
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed")
    tblPr.append(tw); tblPr.append(lay)
    grid = tbl.tblGrid
    for gc, w in zip(grid.findall(W + "gridCol"), widths_cm):
        gc.set(qn("w:w"), str(int(w * 567)))
    for row in table.rows:
        for c, w in zip(row.cells, widths_cm):
            c.width = Cm(w)


def S(text, **fmt):
    return (text, fmt)


def build_permohonan(key):
    I = INSTANSI[key]
    doc = Document(TEMPLATE)
    body = doc.element.body
    els = list(body.iterchildren())
    proto = {"date": els[4], "line": els[5], "bold": els[6], "body": els[11], "title": els[12],
             "lettered": els[16], "numbered": els[21], "blank": els[27]}
    proto = {k: copy.deepcopy(v) for k, v in proto.items()}
    usable = (doc.sections[0].page_width - doc.sections[0].left_margin - doc.sections[0].right_margin) / 360000
    fix_table(doc.tables[0], [2.6, usable - 5.2, 2.6])       # letterhead: logo | text | crest
    fix_table(doc.tables[1], [2.4, 0.5, usable - 2.9])       # Nomor / Lampiran / Perihal
    fix_table(doc.tables[2], [usable / 2, usable / 2])       # signature block on the right
    meta = doc.tables[1]
    meta.rows[1].cells[2].paragraphs[0].runs[0].text = "2 (dua) berkas"
    for r in meta.rows[1].cells[2].paragraphs[0].runs[1:]:
        r.text = ""
    per = meta.rows[2].cells[2].paragraphs[0]
    per.runs[0].text = PERIHAL
    for r in per.runs[1:]:
        r.text = ""
    # remove everything from the date line up to (not including) the signature table
    ttd = els[29]
    for el in els[4:29]:
        body.remove(el)

    def add(kind, segs):
        e = copy.deepcopy(proto[kind])
        if segs is not None:
            set_runs(e, segs)
        ttd.addprevious(e)

    add("date", [S("Surakarta, " + DOTS + " 2026")])
    add("line", [S("Yth.")])
    add("bold", [S(I["tujuan"][0], b=True)])
    for line in I["tujuan"][1:]:
        add("line", [S(line)])
    add("line", [S("Dengan hormat,")])
    add("body", [S("Sehubungan dengan kegiatan penelitian dan pengembangan yang dilaksanakan oleh siswa SMA "
                   "Negeri 1 Surakarta, dengan ini kami sampaikan bahwa tim peneliti kami sedang mengembangkan "
                   "sebuah purwarupa penelitian dengan judul:")])
    add("title", [S("\u201c" + JUDUL + "\u201d", b=True, i=True)])
    add("body", [S(RINGKAS)])
    add("body", [S(I["relevansi"])])
    add("body", [S("Sehubungan dengan hal tersebut, kami bermaksud memohon kesediaan Bapak/Ibu untuk menerima "
                   "audiensi dan berdiskusi bersama tim peneliti kami, guna:")])
    for ch, t in zip("abc", I["tujuan_audiensi"]):
        add("lettered", [S("%s. %s" % (ch, t))])
    add("body", [S("Waktu dan tempat pelaksanaan audiensi kami serahkan sepenuhnya kepada kesediaan dan "
                   "kesempatan Bapak/Ibu. Tim kami akan menghubungi lebih lanjut melalui kontak sekolah pada kop "
                   "surat ini untuk menyepakati jadwal. Sebagai bahan pertimbangan, bersama surat ini kami "
                   "lampirkan ringkasan penelitian Nova-Band serta konsep surat dukungan yang dapat disesuaikan "
                   "sepenuhnya oleh " + I["singkat"] + ".")])
    add("body", [S("Tim peneliti yang dimaksud terdiri atas:")])
    for i, n in enumerate(TIM, 1):
        add("numbered", [S("%d. %s%s" % (i, n, " (Ketua Tim)" if i == 1 else ""))])
    add("blank", None)
    add("body", [S("Demikian surat permohonan ini kami sampaikan. Atas perhatian dan kesediaan Bapak/Ibu, kami "
                   "ucapkan terima kasih.")])
    # the filing note after the signature
    note = [e for e in body.iterchildren() if e.tag == W + "p" and "Catatan berkas" in "".join(t.text or "" for t in e.iter(W + "t"))]
    if note:
        set_runs(note[0], [S("Catatan berkas. ", b=True),
                           S("Ini adalah rancangan surat untuk memudahkan pengajuan resmi; bukan surat yang sudah "
                             "berlaku. Nomor surat dikosongkan agar diisi oleh Tata Usaha sesuai sistem penomoran "
                             "sekolah, dan tanggal dikosongkan agar diisi saat surat benar-benar dikirim. Ruang "
                             "tanda tangan harus dibubuhi tanda tangan asli Kepala Sekolah serta cap sekolah asli "
                             "sebelum dikirim. Lampiran: (1) Ringkasan Penelitian Nova-Band dan (2) Konsep Surat "
                             "Dukungan " + I["singkat"] + " — keduanya disertakan terpisah.")])
    name = "Surat Permohonan Audiensi dan Dukungan Nova-Band - %s.docx" % I["nama"]
    out = os.path.join(HERE, "permohonan", name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    doc.save(out)
    return out


# ---------------------------------------------------------------- konsep surat dukungan (pola ASTA dukungan_docx.py)
def shade(cell, fill):
    tc = cell._tc.get_or_add_tcPr()
    el = OxmlElement("w:shd"); el.set(qn("w:val"), "clear"); el.set(qn("w:fill"), fill); tc.append(el)


def par(d, text="", bold=False, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY, after=6, size=12):
    p = d.add_paragraph(); p.alignment = align; p.paragraph_format.space_after = Pt(after)
    if text:
        r = p.add_run(text); r.bold = bold; r.italic = italic; r.font.size = Pt(size)
    return p


def build_konsep(key):
    I = INSTANSI[key]
    d = Document()
    s = d.sections[0]
    s.page_width, s.page_height = Cm(21.0), Cm(29.7)
    s.top_margin = Cm(1.6); s.bottom_margin = Cm(1.5); s.left_margin = Cm(2.3); s.right_margin = Cm(2.3)
    st = d.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(12)

    b = d.add_table(rows=1, cols=1); c = b.rows[0].cells[0]; shade(c, "FFF4E5")
    r = c.paragraphs[0].add_run("KONSEP untuk ditinjau %s. " % I["nama"])
    r.bold = True; r.font.size = Pt(9); r.font.color.rgb = BROWN
    r2 = c.paragraphs[0].add_run("Disiapkan oleh Tim Peneliti Nova-Band sebagai bahan; isi dapat diubah seluruhnya. "
                                 "Surat baru berlaku setelah diterbitkan Dinas di kop surat resmi, diberi nomor, "
                                 "ditandatangani, dan dicap. Hapus kotak ini dan catatan di akhir saat diterbitkan.")
    r2.font.size = Pt(9); r2.font.color.rgb = BROWN
    d.add_paragraph().paragraph_format.space_after = Pt(2)

    k = d.add_table(rows=1, cols=1); kc = k.rows[0].cells[0]; shade(kc, "F3F4F6")
    kp = kc.paragraphs[0]; kp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    kr = kp.add_run("[ KOP SURAT RESMI %s ]" % I["nama"].upper()); kr.bold = True; kr.font.size = Pt(10.5)
    kr.font.color.rgb = GREY
    kp2 = kc.add_paragraph(); kp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    kr2 = kp2.add_run("diisi oleh " + I["nama"]); kr2.font.size = Pt(9); kr2.font.color.rgb = GREY

    g = d.add_paragraph(); pPr = g._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr"); bt = OxmlElement("w:bottom")
    bt.set(qn("w:val"), "double"); bt.set(qn("w:sz"), "18"); bt.set(qn("w:space"), "1"); bt.set(qn("w:color"), "000000")
    bdr.append(bt); pPr.append(bdr); g.paragraph_format.space_after = Pt(10)

    meta = d.add_table(rows=3, cols=3)
    for i, (a, v, bold) in enumerate([("Nomor", ".................. / .................. / 2026", False),
                                       ("Lampiran", "\u2013", False),
                                       ("Perihal", "Surat Dukungan Penelitian dan Pengembangan Nova-Band", True)]):
        meta.rows[i].cells[0].paragraphs[0].add_run(a)
        meta.rows[i].cells[1].paragraphs[0].add_run(":")
        rr = meta.rows[i].cells[2].paragraphs[0].add_run(v); rr.bold = bold
    for row in meta.rows:
        for ci, w in enumerate((Cm(2.4), Cm(0.5), Cm(13.4))):
            row.cells[ci].width = w

    par(d, "Surakarta, " + DOTS + " 2026", align=WD_ALIGN_PARAGRAPH.RIGHT, after=10)
    for i, (t, bold) in enumerate([("Yth.", False), ("Kepala SMA Negeri 1 Surakarta", True),
                                   ("c.q. Tim Peneliti Nova-Band", False), ("di Surakarta", False)]):
        par(d, t, bold=bold, align=WD_ALIGN_PARAGRAPH.LEFT, after=0 if i < 3 else 10)

    par(d, "Dengan hormat,")
    par(d, "Menindaklanjuti surat SMA Negeri 1 Surakarta Nomor " + DOTS + " tanggal " + DOTS + " perihal "
        + PERIHAL + ", serta diskusi yang telah dilaksanakan pada tanggal " + DOTS + ", dengan ini "
        + I["nama"] + " menyampaikan dukungan terhadap kegiatan penelitian dan pengembangan berikut:")

    rows = [("Judul", JUDUL), ("Pelaksana", "Tim Peneliti SMA Negeri 1 Surakarta"), ("Ketua Tim", TIM[0]),
            ("Anggota", ", ".join(TIM[1:])), ("Guru Pembimbing", DOTS)]
    t = d.add_table(rows=len(rows), cols=3)
    for i, (a, v) in enumerate(rows):
        t.rows[i].cells[0].paragraphs[0].add_run(a)
        t.rows[i].cells[1].paragraphs[0].add_run(":")
        rv = t.rows[i].cells[2].paragraphs[0].add_run(v); rv.italic = (a == "Judul")
        for ci, w in enumerate((Cm(3.6), Cm(0.5), Cm(12.2))):
            t.rows[i].cells[ci].width = w
    d.add_paragraph().paragraph_format.space_after = Pt(2)

    par(d, I["pandangan"])
    for i, (lead, rest) in enumerate(I["dukungan"], 1):
        p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.left_indent = Cm(0.8); p.paragraph_format.first_line_indent = Cm(-0.6)
        p.paragraph_format.space_after = Pt(4)
        p.add_run("%d. " % i); rb = p.add_run(lead); rb.bold = True; p.add_run(rest)
    par(d, I["batasan"])
    par(d, "Demikian surat dukungan ini dibuat untuk dapat dipergunakan sebagaimana mestinya.", after=10)

    sg = d.add_table(rows=1, cols=2)
    cell = sg.rows[0].cells[1]
    cell.paragraphs[0].add_run(I["jabatan"][0])
    cell.add_paragraph(I["jabatan"][1])
    pr = cell.add_paragraph(); rr = pr.add_run("[tanda tangan & cap dinas \u2014 dibubuhkan oleh Dinas]")
    rr.italic = True; rr.font.size = Pt(9); rr.font.color.rgb = GREY
    cell.add_paragraph(); cell.add_paragraph()
    pn = cell.add_paragraph(); rn = pn.add_run(I["pejabat"]); rn.bold = True; rn.underline = True
    cell.add_paragraph("NIP " + DOTS)

    d.add_paragraph()
    n = d.add_table(rows=1, cols=1); nc = n.rows[0].cells[0]; shade(nc, "F6F8FA")
    nr = nc.paragraphs[0].add_run("Catatan untuk Dinas. "); nr.bold = True; nr.font.size = Pt(8.5)
    nr2 = nc.paragraphs[0].add_run(
        "Bagian bertitik (nomor surat, tanggal, NIP, nama guru pembimbing, rujukan surat dan tanggal diskusi) "
        "sengaja dikosongkan. Rumusan dukungan, terutama butir fasilitasi dan kalimat batasan tanggung jawab, "
        "dapat disesuaikan dengan kebijakan dan kewenangan Dinas. Bagian ini, spanduk konsep di atas, dan tanda "
        "air dihapus saat diterbitkan.")
    nr2.font.size = Pt(8.5); nr2.font.color.rgb = GREY

    out = os.path.join(HERE, "dukungan", "Konsep Surat Dukungan Nova-Band - %s.docx" % I["nama"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    d.save(out)
    return out


# ---------------------------------------------------------------- lampiran: ringkasan penelitian
def build_ringkasan():
    d = Document()
    s = d.sections[0]
    s.page_width, s.page_height = Cm(21.0), Cm(29.7)
    s.top_margin = Cm(1.8); s.bottom_margin = Cm(1.6); s.left_margin = Cm(2.3); s.right_margin = Cm(2.3)
    st = d.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(11.5)
    par(d, "LAMPIRAN", bold=True, align=WD_ALIGN_PARAGRAPH.LEFT, after=0, size=10)
    par(d, "Ringkasan Penelitian Nova-Band", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=2, size=15)
    par(d, JUDUL, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=2, size=11.5)
    par(d, "Tim Peneliti SMA Negeri 1 Surakarta · ISIF 2026", align=WD_ALIGN_PARAGRAPH.CENTER, after=12, size=10.5)

    def head(t):
        p = par(d, t, bold=True, align=WD_ALIGN_PARAGRAPH.LEFT, after=3, size=12)
        p.paragraph_format.space_before = Pt(6)

    def bullets(items):
        for it in items:
            p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.left_indent = Cm(0.7); p.paragraph_format.first_line_indent = Cm(-0.45)
            p.paragraph_format.space_after = Pt(3)
            p.add_run("\u2022  " + it)

    head("1. Latar Belakang")
    par(d, "Sebanyak 37,4% penduduk Indonesia berusia 10 tahun ke atas belum memenuhi rekomendasi aktivitas "
           "fisik (SKI 2023). Lari menjadi pilihan olahraga yang banyak diminati, namun latihan berlebih dan "
           "kurangnya pemantauan dapat meningkatkan risiko cedera maupun kejadian kesehatan saat berolahraga. "
           "Di sisi lain, perangkat wearable konsumen yang umum dikenakan di pergelangan tangan menunjukkan galat "
           "cukup besar, yaitu MAPE 1–42% pada penghitungan langkah dan 15–44% pada estimasi kalori.")
    head("2. Solusi yang Dikembangkan")
    par(d, RINGKAS)
    head("3. Cara Kerja")
    bullets(["Sensor optik PPG membaca detak jantung; sensor IMU (akselerometer, giroskop, magnetometer) membaca "
             "gerak, postur, dan irama langkah.",
             "Data diolah pada mikrokontroler ESP32-S3 dan ditampilkan pada layar sentuh perangkat.",
             "Perangkat terhubung ke aplikasi web melalui Bluetooth LE atau USB; aplikasi menghitung Readiness "
             "Score harian.",
             "Shared Safety Net: saat batas aman terlampaui, peringatan diterima pelari dan pendamping atau "
             "pengawas kegiatan pada saat yang sama."])
    head("4. Status dan Hasil Sementara")
    bullets(["Status: purwarupa penelitian (belum merupakan alat kesehatan dan belum diedarkan).",
             "Akurasi sensor: MAPE 2,5–3,5% terhadap motion capture berkecepatan tinggi.",
             "Usability: skor SUS 84,5 (kategori A) dari 60 responden.",
             "Purwarupa kerja: casing cetak 3D berisi modul ESP32-S3 dengan layar 1,9 inci, aplikasi web "
             "yang dapat dipasang (PWA), dan dasbor komunitas."])
    head("5. Dukungan yang Diharapkan")
    bullets(["Masukan dan arahan dari sisi kesehatan, keolahragaan, keselamatan, dan etika pengambilan data.",
             "Fasilitasi pengenalan serta uji coba lapangan yang aman bersama komunitas atau kegiatan olahraga, "
             "dengan persetujuan peserta.",
             "Surat dukungan sebagai bagian dari pembinaan penelitian dan inovasi pelajar."])
    head("6. Tim Peneliti")
    par(d, "%s (Ketua Tim), %s." % (TIM[0], ", ".join(TIM[1:])))
    par(d, "Informasi lengkap dan purwarupa aplikasi: novaband-id.web.app  ·  Kontak melalui SMA Negeri 1 Surakarta, "
           "Jl. Monginsidi No. 40, Surakarta, telepon 0271-652975.", after=0, size=10.5)
    out = os.path.join(HERE, "lampiran", "Lampiran - Ringkasan Penelitian Nova-Band.docx")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    d.save(out)
    return out


if __name__ == "__main__":
    made = [build_permohonan("dinkes"), build_permohonan("dispora"),
            build_konsep("dinkes"), build_konsep("dispora"), build_ringkasan()]
    for m in made:
        print("ok", m)
