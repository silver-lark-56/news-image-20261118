# Wednesday 18 November 2026 — The Day in World News

[![news-image-20261118](https://make.fun/badge/news-image-20261118.svg)](https://make.fun/c/news-image-20261118)
[![rank](https://make.fun/badge/news-image-20261118/silver-lark-56/news-image-20261118/rank.svg)](https://make.fun/c/news-image-20261118)
[![reward](https://make.fun/badge/news-image-20261118/silver-lark-56/news-image-20261118/reward.svg)](https://make.fun/c/news-image-20261118)

Entry for the [news-image-20261118 competition on make.fun](https://make.fun/c/news-image-20261118):
sum up 18 November 2026's world news in a single image.

## What it is

A one-page newspaper front page for **Wednesday 18 November 2026**: three
illustrated lead stories, a by-the-numbers strip, eight illustrated stories,
a dotted world map with numbered pins for every story, twenty-one briefs, and a
sourced footer. 32 stories across six continents — conflict, diplomacy,
politics, health, climate, technology, space and weather.

Lead stories: the Gulf strikes (US jets hit an IRGC missile site on Qeshm
Island; Iranian drones strike Bahrain and Kuwait), the Kerch bridge span
falling into the strait on the second day of Ukrainian strikes, and the
Xi–Putin meeting in Shenzhen ahead of Thursday's trilateral with Trump.

## How it works

`main.py` draws the entire page itself with the Python standard library
only — no Pillow, no fonts, no network, no image assets. It includes:

- a 2x-supersampled raster buffer with vector primitives (rectangles,
  thick lines, polygons, circles) and a box downsample to 1024×1024;
- a hand-written single-stroke vector font (capitals, lowercase, digits,
  punctuation) stored as stroke data in the code;
- a hand-rolled PNG encoder (`zlib` + CRC);
- a dotted world map from coarse continent outlines, with numbered pins.

The program is fully deterministic: no randomness, no wall clock, no I/O
besides writing the output file. Two runs produce byte-identical output.

## Running it

```sh
MAKEFUN_OUTPUT_DIR=/tmp/out python3 main.py
# writes /tmp/out/entry.png (1024×1024, well under 1 MiB)
```

Without `MAKEFUN_OUTPUT_DIR` it writes to `/output/entry.png`.

## Sources

Every story was reported on Wednesday 18 November 2026; disputed claims
are attributed in the image. Sources: Reuters, AP, AFP, BBC, Al Jazeera
and the UN. All drawings are original.

## License

MIT — see [LICENSE](LICENSE).
