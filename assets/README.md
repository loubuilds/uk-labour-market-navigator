# README artwork

`navigator-header.svg` combines the maintainer-supplied folded-map logo with outlined Manrope lettering. `logo.png` preserves the supplied image data; embedded EXIF/text metadata was removed before inclusion. The masthead is self-contained: its lettering is SVG paths and its logo is embedded PNG data. There are no remote font, image or script requests.

- Background: warm white `#FAF9F6`.
- Lettering: deep teal `#07545B`.
- Accent: orange `#F87916`.
- “UK Labour Market”: Manrope Semibold, weight 600, size 48.
- “Navigator”: Manrope Bold, weight 700, size 96.

Manrope is by [The Manrope Project Authors](https://github.com/sharanda/manrope). The lettering was shaped from the [Google Fonts source](https://github.com/google/fonts/tree/main/ofl/manrope) using fontTools 4.65.0 and HarfBuzz through uharfbuzz 0.56.1, then converted to paths. The font software is [SIL Open Font License 1.1](https://github.com/google/fonts/blob/main/ofl/manrope/OFL.txt); no font file is distributed here. Font input SHA256: `d0639be45d0af36e798172419d7bd173c4bd4f29e2b76cbb69db1d11bf8b0a40`.

The README's `examples/preview.svg` is different: it contains the actual generated report chart. It is reproduced and checked by `python -m scripts.make_example --check`.

Designed HTML reports embed a small copy of the logo beside the product name. The packaged `uk_labour_market_navigator/resources/logo.png` is byte-identical to `assets/logo.png`; embedding keeps standalone reports usable offline.
