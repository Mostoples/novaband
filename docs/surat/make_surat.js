// Surat permohonan kunjungan & konsultasi ke Laboratorium Pusat UNS (tim Nova-Band).
// node docs/surat/make_surat.js  ->  docs/surat/Surat_Permohonan_Kunjungan_Lab_UNS.docx
// Bagian bersorot kuning = data yang harus dilengkapi/diperiksa pihak sekolah.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType,
  AlignmentType, BorderStyle, TabStopType, VerticalAlign, ShadingType,
} = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const FONT = "Times New Roman";
const SZ = 24;                       // 12 pt

// a paragraph built from segments; [text, {b, i, u, hl}] where hl = placeholder highlight
function P(segs, o = {}) {
  const runs = (Array.isArray(segs) ? segs : [[segs]]).map((s) => {
    const [t, f = {}] = Array.isArray(s) ? s : [s];
    return new TextRun({ text: t, font: FONT, size: o.size || SZ, bold: f.b, italics: f.i,
      underline: f.u ? {} : undefined, highlight: f.hl ? "yellow" : undefined });
  });
  return new Paragraph({
    children: runs, alignment: o.align || AlignmentType.JUSTIFIED,
    spacing: { after: o.after ?? 0, before: o.before ?? 0, line: o.line ?? 276 },
    indent: o.indent, tabStops: o.tabs, border: o.border,
  });
}
const HL = (t) => [t, { hl: true }];
const B = (t) => [t, { b: true }];

// ---------------------------------------------------------------- letterhead
const crest = fs.readFileSync(path.join(ROOT, "deck", "assets", "img", "crest-sman1.png"));
const noBorder = { top: { style: BorderStyle.NONE, size: 0 }, bottom: { style: BorderStyle.NONE, size: 0 },
  left: { style: BorderStyle.NONE, size: 0 }, right: { style: BorderStyle.NONE, size: 0 } };
const kop = new Table({
  width: { size: 9070, type: WidthType.DXA }, columnWidths: [1500, 7570],
  borders: { ...noBorder, insideHorizontal: { style: BorderStyle.NONE, size: 0 }, insideVertical: { style: BorderStyle.NONE, size: 0 } },
  rows: [new TableRow({ children: [
    new TableCell({ width: { size: 1500, type: WidthType.DXA }, borders: noBorder, verticalAlign: VerticalAlign.CENTER,
      children: [new Paragraph({ alignment: AlignmentType.CENTER,
        children: [new ImageRun({ type: "png", data: crest, transformation: { width: 72, height: 86 } })] })] }),
    new TableCell({ width: { size: 7570, type: WidthType.DXA }, borders: noBorder, verticalAlign: VerticalAlign.CENTER, children: [
      P("PEMERINTAH PROVINSI JAWA TENGAH", { align: AlignmentType.CENTER, size: 24 }),
      P("DINAS PENDIDIKAN DAN KEBUDAYAAN", { align: AlignmentType.CENTER, size: 24 }),
      P([B("SEKOLAH MENENGAH ATAS NEGERI 1 SURAKARTA")], { align: AlignmentType.CENTER, size: 27 }),
      P([HL("Jl. Monginsidi No. 40, Kestalan, Banjarsari, Surakarta 57133 · Telp. (0271) …  · Surel …")],
        { align: AlignmentType.CENTER, size: 20 }),
    ] }),
  ] })],
});
const rule = new Paragraph({ children: [], spacing: { after: 240 },
  border: { bottom: { style: BorderStyle.THICK_THIN_SMALL_GAP, size: 18, color: "000000", space: 4 } } });

// ---------------------------------------------------------------- header block
const tabs = [{ type: TabStopType.LEFT, position: 1300 }, { type: TabStopType.LEFT, position: 1500 }];
const dateLine = P([["Surakarta, "], HL("… Oktober 2026")], { align: AlignmentType.RIGHT, after: 200 });
const meta = [
  P([["Nomor\t:\t"], HL("…/…/SMA.1/2026")], { tabs, align: AlignmentType.LEFT }),
  P([["Lampiran\t:\t1 (satu) berkas"]], { tabs, align: AlignmentType.LEFT }),
  P([["Hal\t:\t"], B("Permohonan Izin Kunjungan dan Konsultasi Penelitian")], { tabs, align: AlignmentType.LEFT, after: 240 }),
];
const to = [
  P("Kepada Yth.", { align: AlignmentType.LEFT }),
  P([HL("Kepala UPT Laboratorium Terpadu (Laboratorium Pusat)")], { align: AlignmentType.LEFT }),
  P("Universitas Sebelas Maret", { align: AlignmentType.LEFT }),
  P([["c.q. "], HL("Prof. Dr. … (Guru Besar UNS)")], { align: AlignmentType.LEFT }),
  P("di Surakarta", { align: AlignmentType.LEFT, after: 240 }),
];

// ---------------------------------------------------------------- body
const ind = { firstLine: 720 };
const body = [
  P("Dengan hormat,", { after: 120, align: AlignmentType.LEFT }),
  P([["Dalam rangka mempersiapkan keikutsertaan dalam lomba penelitian "], B("Indonesia Science and Invention Fair (ISIF) 2026"),
     [", tim peneliti siswa SMA Negeri 1 Surakarta sedang mengembangkan karya berjudul "],
     ["\u201CNova-Band: An AIoT-Driven Upper-Arm Wearable for Real-Time Physiological Monitoring and Running Performance\u201D", { i: true }],
     [". Karya ini berupa perangkat yang dikenakan di lengan atas untuk memantau detak jantung (sensor optik PPG) dan gerak tubuh (IMU) pelari secara langsung, terhubung ke aplikasi melalui Bluetooth."]],
    { indent: ind, after: 120 }),
  P([["Sehubungan dengan hal tersebut, kami mengajukan permohonan izin bagi tim peneliti beserta guru pembimbing untuk melakukan kunjungan dan konsultasi ke Laboratorium Pusat Universitas Sebelas Maret, dengan tujuan:"]],
    { indent: ind, after: 60 }),
  P("1.\tMemperoleh masukan ilmiah mengenai metode penelitian dan rancangan pengujian purwarupa;", { indent: { left: 1080, hanging: 360 }, tabs: [{ type: TabStopType.LEFT, position: 1080 }] }),
  P("2.\tBerdiskusi mengenai cara memvalidasi akurasi pengukuran detak jantung terhadap alat pembanding (referensi);", { indent: { left: 1080, hanging: 360 }, tabs: [{ type: TabStopType.LEFT, position: 1080 }] }),
  P("3.\tMengenal fasilitas dan standar kerja laboratorium yang relevan dengan penelitian siswa.", { indent: { left: 1080, hanging: 360 }, tabs: [{ type: TabStopType.LEFT, position: 1080 }], after: 120 }),
  P("Adapun rencana pelaksanaan kegiatan sebagai berikut:", { indent: ind, after: 60 }),
];
const tabs2 = [{ type: TabStopType.LEFT, position: 2600 }, { type: TabStopType.LEFT, position: 2800 }];
const plan = [
  P([["\tHari, tanggal\t:\t"], HL("… , … Oktober 2026 (menyesuaikan kesediaan Bapak/Ibu)")], { tabs: [{ type: TabStopType.LEFT, position: 720 }, ...tabs2], align: AlignmentType.LEFT }),
  P([["\tWaktu\t:\t"], HL("… WIB – selesai")], { tabs: [{ type: TabStopType.LEFT, position: 720 }, ...tabs2], align: AlignmentType.LEFT }),
  P([["\tTempat\t:\tLaboratorium Pusat Universitas Sebelas Maret"]], { tabs: [{ type: TabStopType.LEFT, position: 720 }, ...tabs2], align: AlignmentType.LEFT }),
  P([["\tPeserta\t:\t6 (enam) siswa dan 1 (satu) guru pembimbing"]], { tabs: [{ type: TabStopType.LEFT, position: 720 }, ...tabs2], align: AlignmentType.LEFT, after: 120 }),
];

// participants table
const W = [700, 4770, 1300, 2300];
const cell = (t, w, o = {}) => new TableCell({
  width: { size: w, type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
  shading: o.head ? { type: ShadingType.CLEAR, fill: "E7E6E6", color: "auto" } : undefined,
  margins: { top: 60, bottom: 60, left: 100, right: 100 },
  children: [P(o.hl ? [HL(t)] : o.head ? [B(t)] : t, { align: o.center ? AlignmentType.CENTER : AlignmentType.LEFT })],
});
const team = ["Satriya Javas Wibisono", "Almira Edgina Nareswari Haryadi", "Azra Daniswara Tyandaru",
  "Maheswara Nala Wisadewa", "Dela Astiara", "Rizkyta Aufa Mutiagassania"];
const table = new Table({
  width: { size: 9070, type: WidthType.DXA }, columnWidths: W,
  rows: [
    new TableRow({ tableHeader: true, children: [cell("No.", W[0], { head: true, center: true }), cell("Nama", W[1], { head: true }),
      cell("Kelas", W[2], { head: true, center: true }), cell("Keterangan", W[3], { head: true, center: true })] }),
    ...team.map((n, i) => new TableRow({ children: [cell(String(i + 1), W[0], { center: true }), cell(n, W[1]),
      cell("…", W[2], { hl: true, center: true }), cell("Siswa", W[3], { center: true })] })),
    new TableRow({ children: [cell("7", W[0], { center: true }), cell("… (nama guru pembimbing)", W[1], { hl: true }),
      cell("–", W[2], { center: true }), cell("Guru Pembimbing", W[3], { center: true })] }),
  ],
});

const close = [
  P([["Sebagai bahan pertimbangan, bersama surat ini kami lampirkan ringkasan penelitian. Narahubung kegiatan: "],
     HL("… (nama guru pembimbing), No. HP …"), ["."]], { indent: ind, before: 200, after: 120 }),
  P("Demikian permohonan ini kami sampaikan. Atas perhatian dan kesediaan Bapak/Ibu, kami mengucapkan terima kasih.",
    { indent: ind, after: 360 }),
];
const sign = [
  P("Kepala SMA Negeri 1 Surakarta,", { align: AlignmentType.LEFT, indent: { left: 5200 } }),
  P("", { after: 1100 }),
  P([HL("… (nama Kepala Sekolah)")], { align: AlignmentType.LEFT, indent: { left: 5200 } }),
  P([["NIP "], HL("…")], { align: AlignmentType.LEFT, indent: { left: 5200 }, after: 360 }),
  P([["Tembusan:", { u: true }]], { align: AlignmentType.LEFT, size: 22 }),
  P("1.  Wakil Kepala Sekolah Bidang Kurikulum SMA Negeri 1 Surakarta", { align: AlignmentType.LEFT, size: 22 }),
  P("2.  Guru Pembimbing Tim Nova-Band", { align: AlignmentType.LEFT, size: 22 }),
  P("3.  Arsip", { align: AlignmentType.LEFT, size: 22 }),
];

const doc = new Document({
  creator: "Tim Nova-Band — SMA Negeri 1 Surakarta",
  title: "Permohonan Izin Kunjungan dan Konsultasi Penelitian",
  styles: { default: { document: { run: { font: FONT, size: SZ } } } },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1418, right: 1418 } } },
    children: [kop, rule, dateLine, ...meta, ...to, ...body, ...plan, table, ...close, ...sign],
  }],
});
const out = path.join(__dirname, "Surat_Permohonan_Kunjungan_Lab_UNS.docx");
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(out, b); console.log("wrote", out); });
