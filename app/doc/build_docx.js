// Build dist/swmm5-kw-doc.docx from app/doc/out/essay.json and the light-theme figure SVGs
// that app/build.py writes there. Same source as the app's Doc tab.
//   node app/doc/build_docx.js
const fs = require('fs'), path = require('path');
const NODE = process.env.NODE_PATH || '';
const req = m => { try { return require(m); } catch (e) { return require(path.join(NODE, m)); } };
const sharp = req('sharp');
const { Document, Packer, Paragraph, TextRun, ImageRun, HeadingLevel, AlignmentType, LevelFormat, ShadingType, BorderStyle, Footer, PageNumber } = req('docx');

const OUT = path.join(__dirname, 'out'), DIST = path.join(__dirname, '..', '..', 'dist');
const blocks = JSON.parse(fs.readFileSync(path.join(OUT, 'essay.json'), 'utf8'));
const BODY = 'Georgia', HEAD = 'Arial', MONO = 'Consolas';

function runs(rs, extra = {}) {
  return rs.map(([t, f]) => new TextRun(Object.assign({ text: t, font: f.code ? MONO : BODY, size: f.code ? 19 : 22, bold: !!f.b, italics: !!f.i }, extra)));
}
(async () => {
  const kids = [];
  for (const b of blocks) {
    if (b.kind === 'h1') kids.push(new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun({ text: b.text, font: HEAD, size: 44, bold: true, color: '1E3A5F' })], spacing: { after: 120 } }));
    else if (b.kind === 'deck') kids.push(new Paragraph({ children: [new TextRun({ text: b.text, font: HEAD, size: 24, color: '4F5D6E' })], spacing: { after: 360 } }));
    else if (b.kind === 'h2') kids.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: b.text, font: HEAD, size: 30, bold: true, color: '1E3A5F' })], spacing: { before: 360, after: 120 }, keepNext: true }));
    else if (b.kind === 'p') kids.push(new Paragraph({ children: runs(b.runs), spacing: { after: 160, line: 300 } }));
    else if (b.kind === 'pre') kids.push(new Paragraph({ children: [new TextRun({ text: b.text, font: MONO, size: 18 })], shading: { type: ShadingType.CLEAR, color: 'auto', fill: 'EEF2F7' }, spacing: { before: 60, after: 180 }, indent: { left: 240, right: 240 } }));
    else if (b.kind === 'ul') for (const it of b.items) kids.push(new Paragraph({ numbering: { reference: 'bullets', level: 0 }, children: runs(it), spacing: { after: 80, line: 290 } }));
    else if (b.kind === 'box') kids.push(new Paragraph({ children: runs(b.runs), shading: { type: ShadingType.CLEAR, color: 'auto', fill: 'EFF6FF' }, spacing: { after: 160 } }));
    else if (b.kind === 'fig') {
      const svg = fs.readFileSync(path.join(OUT, `fig_${b.key}.svg`));
      const png = await sharp(svg, { density: 192 }).flatten({ background: '#ffffff' }).png().toBuffer();
      const meta = await sharp(png).metadata();
      const w = 624, h = Math.round(w * meta.height / meta.width);       // 6.5 in at 96 px per inch
      kids.push(new Paragraph({ children: [new ImageRun({ type: 'png', data: png, transformation: { width: w, height: h }, altText: { title: `Figure ${b.n}`, description: b.caption.map(r => r[0]).join(''), name: `fig${b.n}` } })], alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true }));
      kids.push(new Paragraph({ children: [new TextRun({ text: `Figure ${b.n}. `, font: HEAD, size: 18, bold: true, color: '4F5D6E' }), ...b.caption.map(([t, f]) => new TextRun({ text: t, font: f.code ? MONO : HEAD, size: 18, color: '4F5D6E', bold: !!f.b, italics: !!f.i }))], spacing: { after: 240 } }));
    }
  }
  const doc = new Document({
    creator: 'Robert Dickinson', title: 'Forks in the Road: swmm5-kw',
    description: 'How swmm5-kw splits junctions and runs loops under SWMM kinematic wave and steady flow. Written with Claude (Anthropic); see the AI use section.',
    styles: { default: { document: { run: { font: BODY, size: 22 } } } },
    numbering: { config: [{ reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] }] },
    sections: [{
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'swmm5-kw · github.com/SWMMBobSWMM6/swmm5-kw · page ', font: HEAD, size: 16, color: '6B7280' }), new TextRun({ children: [PageNumber.CURRENT], font: HEAD, size: 16, color: '6B7280' })] })] }) },
      children: kids,
    }],
  });
  fs.mkdirSync(DIST, { recursive: true });
  fs.writeFileSync(path.join(DIST, 'swmm5-kw-doc.docx'), await Packer.toBuffer(doc));
  console.log('dist/swmm5-kw-doc.docx', fs.statSync(path.join(DIST, 'swmm5-kw-doc.docx')).size, 'bytes,', blocks.filter(b => b.kind === 'fig').length, 'figures');
})();
