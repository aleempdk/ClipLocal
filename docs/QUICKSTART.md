# Start creating clips

1. On the GitHub repository page, choose **Code > Download ZIP**. Extract the ZIP into a writable folder on your Windows computer. Do not launch from inside the ZIP.
2. Double-click **Start ClipLocal.cmd**. The first launch runs setup if needed. Keep the terminal window open.
3. Paste a supported video link or choose a local video. Select a caption style, format and sound palette, then choose **Find & create clips**.
4. Review the clips, framing, words and sound. Use transcript corrections, time ranges and re-export when needed.
5. Open **Title, description & tags**, review the drafts and save your changes.
6. Download a clip or its ZIP bundle. Upload the MP4 to your preferred platform yourself.

## Recommended first settings

Use 1080p, large captions, Stable face framing, Picture motion Off, subtle sound effects and automatic decorations. For busy scenes or multiple speakers, try Keep the full picture. For faster experiments, use 720p and fewer clips before exporting the final version.

## First-run requirements

Windows, internet access, a writable folder and sufficient free disk space are needed. Setup uses Python 3.12, FFmpeg, Node.js and Python packages. Windows App Installer/winget is used for missing tools. NVIDIA speech libraries are optional and exceed 1 GB. Run `Setup ClipLocal.cmd --skip-gpu` to use CPU speech instead.

Internet is needed for setup, initial speech models and online video downloads. Previously downloaded local media and models can be processed locally. Fresh-machine setup still needs testing on additional Windows computers.

## Where are my files?

Exports are saved in `clips/<job>/` inside the extracted app folder. Each job includes MP4 clips, caption files, covers, upload drafts, reports and a ZIP. Uploaded source files are in `uploads/`. Do not share these folders if they contain private media.
