# Speech Bubble Editor

**Speech bubbles, comic pages, photo collages, layers, and video edits for desktop.**

[![GitHub Release](https://img.shields.io/github/v/release/longweekendlabs/speech-bubble-editor?style=flat-square)](https://github.com/longweekendlabs/speech-bubble-editor/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Platforms](https://img.shields.io/badge/platform-Windows%20x64%20%7C%20Linux%20x64%20%7C%20macOS%20Apple%20Silicon-lightgrey?style=flat-square)](https://longweekendlabs.github.io/speech-bubble-editor/)

---

## 🇨🇳 简体中文汉化版

**这个 fork 是中文汉化版**，界面已全量中文化（约 1080 处文案），并额外做了几处改进：

| 内容 | 说明 |
|---|---|
| 界面汉化 | 工具栏、顶栏、属性面板四页、对话框、状态栏、撤销历史、提示全部中文 |
| 中英切换 | 顶栏右上角 **EN / 中文** 按钮，运行时即时切换，无需重启 |
| 中文字体兜底 | 内置 Noto Sans SC，未装中文字体的 Windows 也不会显示方块 |
| 拼贴 1:1 方图 | 除竖向 4:5 / 横向 16:9，新增方形 1:1 页面 |
| 拼贴布局 12 种 | 原 4 种扩到 12 种（一上多下 / 上中下 / 大图左 / 黄金比 …），缩略图按真实几何绘制 |
| 打码升级 | 模糊与像素化合并为一个「打码」工具：马赛克 / 高斯模糊 / 纯色填充 + 羽化 |
| 导出 JPG 修复 | 扩展名跟随所选格式；JPEG 自动垫白底，不会出现黑底 |
| 记住上次文件夹 | 导入图片和导出时，从上次用过的目录开始 |
| 单文件打包 | `sbe_zh_onefile.spec`，可自行打包成免安装 exe |

**📖 完整使用说明、汉化范围、验证结果 → [汉化说明.md](汉化说明.md)**

打包成 exe（免安装）：

```powershell
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build sbe_zh_onefile.spec
```

从源码启动（需要 Python + PyQt6）：双击 `start.bat`，或 `python start_zh.py`

> 本 fork 基于 [longweekendlabs/speech-bubble-editor](https://github.com/longweekendlabs/speech-bubble-editor) v4.5.2，
> 遵循原项目 MIT 许可，保留全部原始版权声明。上游仓库不受本 fork 影响。

---

Drop a photo in, say something over it, and you are done. Speech Bubble Editor turns a picture into a comic panel, a meme, a collage, or a captioned video clip, with hand-drawn bubbles that actually look drawn. Everything runs on your own machine: no account, no upload, no subscription.

### [Download for Windows, Linux, and macOS](https://github.com/longweekendlabs/speech-bubble-editor/releases/latest)

![Speech Bubble Editor showing its built-in bubble shapes](docs/screenshots/bubble-shapes.png)

## Bubbles that look drawn, not stamped

Nineteen styles, including speech, round, soft box, cloud, starburst, twin and triple balloons, text-only, scrim, and caption. Balloon bodies use a natural, slightly irregular ink line, so a bubble sits on a photo like it belongs there.

Grab the tail and drag it anywhere. Resize from any corner. Set the fill, the outline weight and colour, the opacity, and the shadow. Point the tail at whoever is talking and it stays pointed there while you move the bubble.

<img src="docs/screenshots/bubble-shapes.png" width="49%" alt="Four friends using oval, soft-box, cloud, and starburst bubbles" /> <img src="docs/screenshots/typography.png" width="49%" alt="Speech bubble typography and caption controls on a taxi-side scene" />

## Type that carries the joke

Twelve bundled comic and display faces, from Bangers and Permanent Marker to Klee and Yusei Magic, plus Japanese-capable fonts for manga work. Size, weight, alignment, colour, and a proper outline so white text survives a bright background.

Nothing is downloaded at runtime. The fonts ship inside the app and render the same on every machine.

## Comic pages and collages

**Comic Maker** builds 4, 6, 7, and 8 panel hand-inked layouts. Regenerate the layout as many times as you like and your bubbles and photos stay where they are.

**Photo Collage** handles 2 to 9 frames on portrait, square, story, landscape, or photo canvases. Drag a photo from one frame to another and they swap. Move the crop inside a frame without moving the frame. Scale anywhere from 10% to 500%. Fill the gaps with a blur of the photo itself or a solid colour. Save any arrangement as a named preset.

<img src="docs/screenshots/comic-maker.png" width="49%" alt="Four-panel Comic Maker story" /> <img src="docs/screenshots/photo-collage.png" width="49%" alt="Four-photo mosaic in Photo Collage" />

## Effects and layers

Lines, blur, and pixelate that follow whichever frame you are working in, so a speed line does not spill into the panel next door. Blur and pixelate double as a quick way to hide a face or a licence plate.

The layer list covers images, videos, bubbles, and captions together. Reorder by dragging, hide anything without deleting it, and pull one element to the front without hunting for it on the canvas.

<img src="docs/screenshots/effects.png" width="49%" alt="Effects inspector with shadow and expression controls" /> <img src="docs/screenshots/layers.png" width="49%" alt="Layers inspector with a three-bubble conversation" />

## Video, not just stills

Open a clip and the timeline appears. Trim the ends, cut a section out of the middle, reverse it, slow it down, or mute the audio. Bubbles and captions ride on top and export with the video. FFmpeg is bundled, so there is nothing to install alongside.

## Meme mode and dual mode

Two one-click layouts for the formats people actually post: classic top and bottom meme text, and a stacked two-panel setup for reaction shots.

![Meme mode with top and bottom captions](docs/screenshots/meme-mode.png)

## Less waiting, more editing

The app starts from its installed files without unpacking its runtime on every launch. Smaller packages keep the fonts, image formats, and video tools included. Unchanged bubble outlines are reused between redraws while exports keep their full resolution.

Open a photo or video on the main canvas, in dual mode, or as a layer while decoding runs in the background. The current canvas stays available, and Reset cancels a pending import.

## The rest

Full resolution image export. Undo and redo everywhere. Keyboard shortcuts for the things you repeat. Your operating system's own file dialogs, not a toolkit imitation. A dark interface that stays out of the way of the picture.

## Download

Windows x64, Linux x64, and Apple Silicon macOS builds are on the [**releases page**](https://github.com/longweekendlabs/speech-bubble-editor/releases/latest): a Windows installer and portable zip, an AppImage, RPM, DEB, and tar.gz for Linux, and a DMG for macOS 15 or newer. The [download page](https://longweekendlabs.github.io/speech-bubble-editor/) picks the right one for you.

## Feedback

[Open an issue](https://github.com/longweekendlabs/speech-bubble-editor/issues) for a bug or a request.

## License

MIT License. See [LICENSE](LICENSE). Free and open source: no licence key, no trial, no subscription.

© 2026 Long Weekend Labs

---

Made with ♥ by **[Long Weekend Labs](https://github.com/longweekendlabs)**
