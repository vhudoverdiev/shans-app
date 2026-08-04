# Reference

- Source: `C:\Users\Владимир\Desktop\Сайты\Передача\Презентация Peredacha\Раб.файлы для видео\Сценарий_видеопрезентации_CRM_Передача.docx`
- SHA-256: `7ABEA04CC586635146177D7D967C1DE4F4382FE2655CC4240635A884CAD1C628`
- Size: 58,514 bytes.
- Page count: 5. Section count: 1.
- Render evidence: `.codex_artifacts/shans_video_script/reference-render/page-1.png` through `page-5.png`. The packaged renderer was attempted first; LibreOffice was unavailable, so the reference was exported read-only through Microsoft Word to PDF and rasterized with bundled Poppler.
- Structural evidence: `reference-style-evidence.json`, `reference-package-inventory.txt`, `section_audit.py` output, and the read-only paragraph/table inventory.

# Page system

- US Letter portrait, 8.5 x 11 inches.
- Margins: 1.0 inch on all sides; usable width 9360 DXA.
- Header and footer distances: 0.4917 inch.
- One section, no different first page, no odd/even split.
- New stages begin on new pages; cover is page 1, stage pages follow.

# Typography

- Base family: Calibri; body color `1F2937`.
- Cover brand label: 9 pt, bold, Shans blue `2F63F1`, 3 pt after. This is an intentional brand-color adaptation from the reference CRM.
- Cover title: 30 pt, bold, dark `111827`, single spacing, 8 pt after.
- Cover subtitle: 12 pt, gray `667085`, 1.2 spacing, 18 pt after.
- Stage label: 9 pt, bold, Shans blue `2F63F1`, 3 pt after, keep with next.
- Heading 1: 16 pt, bold, Shans blue `2F63F1`, single spacing, 0 pt before on stage pages and 5 pt after.
- Stage lead: 10.5 pt, gray `667085`, 10 pt after.
- Segment bar: 13 pt bold title, blue time code, dark title, pale blue fill `EDF4FF`, blue left border; 6 pt before and 5 pt after.
- Field labels: 8.5 pt, bold, uppercase, blue `2F63F1`.
- Screen actions: 10 pt, regular, 1.15 spacing.
- Voiceover: 10 pt, italic, dark `111827`, 1.15 spacing, 7 pt after.
- Callout text: 12 pt, bold, dark; pale fill, colored single border, 0.12 inch inner paragraph indents.
- Header/footer: 8-9 pt, gray-blue `667085`.

# Lists and tables

- Cover timeline table: 9360 DXA total width, 120 DXA indent, four equal columns of 2340 DXA, fixed layout.
- Table borders: `C7D7FE`, 0.75 pt; first row fill `EDF4FF`; 100 DXA vertical and 120 DXA horizontal cell margins; vertical center.
- Timeline times: centered, bold blue; phase labels: centered, bold dark.
- Checklist uses the source document's real `List Bullet` numbering definition with green bullets; no fake bullet characters.

# Components

- Cover: 0.75 inch square logo, brand label, two-line title, subtitle, four-column timing table, objective label and bold objective.
- Stage pages: header, stage label, green heading, gray lead, repeated segment blocks with segment bar, screen actions, and voiceover.
- Final page: stage heading, lead, bordered key-message callout, preparation checklist, and technical-note callout.
- Footer: left product label, centered page number field.

# Content flow

1. Cover and 90-second timeline.
2. Desktop overview and developer introduction, 0:00-0:30.
3. Mobile version, first 34 seconds, 0:30-1:04.
4. Mobile version completion plus platform close, 1:04-1:30.
5. Montage package: key title, asset checklist, recording/edit specifications, and wording constraints.

# Slot map

- Cover logo: replace source image with authentic `app/static/logo.png`; preserve 0.75 inch frame.
- Cover brand/title/subtitle/timeline/objective: rewrite in place; preserve paragraph/table geometry.
- Stage labels/headings/leads: rewrite in place; preserve page breaks and hierarchy.
- Existing segment blocks: rewrite in place. The source provides 3 blocks on page 2, 3 on page 3, and 4 on page 4; all ten blocks are used.
- Each segment bar keeps the inherited pale-green bar and left border. Each action/voiceover pair keeps inherited spacing and type.
- Page 5 callouts and checklist: rewrite in place; keep source callout borders/fills and real bullet list.
- Header/footer: rewrite product text only; preserve page-number field and placement.

# Package preservation

- Full baseline inventory: `reference-package-inventory.txt` with part path, byte size, and SHA-256.
- Editable: `word/document.xml`, `word/header1.xml`, `word/footer1.xml`, `word/media/image1.png`, and core metadata.
- Brand-adapted: `word/styles.xml` and `word/numbering.xml` may change only accent colors from the source green to Shans blue.
- Preserve-only: theme, settings, font table, web settings, endnotes, footnotes, custom XML, relationships, and content types unless python-docx must update a relationship for the authentic replacement image.
- Reference file must remain byte-for-byte unchanged.

# Fidelity gates

- Five pages, one portrait Letter section, 1 inch margins.
- Source-derived layout and typography hierarchy remain recognizable; green accents are consistently adapted to the authentic Shans blue/violet brand palette.
- All ten segment bars remain aligned; no action or voiceover paragraph is separated from its bar.
- Mobile coverage is exactly 0:30-1:15, 45 seconds or 50% of runtime.
- No source CRM names, domains, features, or developer wording remain.
- No clipping, crowding, blank broken pages, or table width drift.
