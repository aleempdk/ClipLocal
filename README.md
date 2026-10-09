# ClipLocal

![ClipLocal: Long videos. Short clips. Your computer.](docs/assets/banner.svg)

**Windows public preview · Free · MIT licensed · No paid APIs required**

Free local Windows video clipping and editing, with English captions. Paste a supported YouTube/Facebook/web video link or select a local file. Automatic selection uses transcript rules and your clip ratings. No paid API is required.

## What you can create

Turn podcasts, interviews, tutorials, commentary and other speech-led videos into captioned clips. ClipLocal downloads accessible sources, finds transcript-based highlights, reframes the picture, adds captions and optional original sound/graphics, and exports uploadable MP4 files. You stay in control of the final review.

| Feature | What it does |
|---|---|
| Automatic clips | Finds non-overlapping spoken passages using transcript rules and optional topic keywords |
| Readable captions | Multiple animated styles, word emphasis and adjustable size |
| Stable framing | Holds small face movements and eases larger pans; fixed crop and wide framing also available |
| Creative editing | Comic, Kinetic, Cinema and other styles, sparse bubbles/stickers and synthesized sound accents |
| Upload drafts | Editable YouTube title, description, hashtags and tags for each clip |
| Local acceleration | Tests available CPU/NVIDIA/Intel/AMD video encoders; optional NVIDIA speech acceleration |
| Export bundle | MP4, captions, cover, upload details and ZIP |

**Start here:** [Quick start](docs/QUICKSTART.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Release notes](CHANGELOG.md) · [Contributing](CONTRIBUTING.md)

## Download and launch

1. Download the source ZIP (or clone the repository) and extract it into a writable folder.
2. Double-click **Start ClipLocal.cmd**. If its local environment is missing, first-run setup starts automatically. **Setup ClipLocal.cmd** can also be run directly to install or repair dependencies.
3. Review installer prompts. Setup uses Windows Package Manager for Python 3.12, FFmpeg and Node.js when missing, and PyPI for Python packages. A fresh setup requires internet access; Windows App Installer/winget must be available. Administrator or installer confirmation may be requested by Windows.
4. If an NVIDIA GPU is detected, optional CUDA speech libraries install in the app environment (over 1 GB). To skip these, run `Setup ClipLocal.cmd --skip-gpu`. CPU speech remains available if this install fails.
5. The studio opens in your browser. Keep the launcher running while processing.

On every launch, the app detects CPU capacity, NVIDIA memory and installed tools, tests working NVIDIA/Intel/AMD/CPU H.264 encoders, and selects the shortest elapsed time in a small 1080p balanced-quality encode benchmark. The result appears in the studio and `hardware-report.json`. It chooses CPU threads and a bounded CUDA speech batch size from free GPU memory. Real workloads can differ from this brief benchmark. Encoder and speech failures fall back to CPU during processing.

CTranslate2 speech acceleration supports NVIDIA CUDA; Intel and AMD computers use CPU speech and can use their video encoders if the FFmpeg tests pass. [CTranslate2 hardware documentation](https://opennmt.net/CTranslate2/hardware_support.html). This does not install drivers or guarantee maximum performance on every computer.

## Steady framing

**Stable face framing** samples faces locally with YuNet, holds the crop within a safe area, waits for sustained movement and eases any pan. Crop versus wide framing is chosen per scene to avoid detection flicker. New jobs default to **Picture motion: Off**. Gentle and Dynamic push-ins remain optional.

This is prominent-face framing, not active-speaker recognition. Groups, profiles, occlusion, and missed scene cuts can still lead to imperfect framing. **Fill the frame** gives a fixed crop, and **Keep the full picture** preserves the scene. Left/center/right controls apply to a fixed crop. Review busy scenes before posting.

## Creative styles and sound

Styles include Spotlight, Reference podcast, Podcast punch, Classic, Karaoke, Bold, Minimal, Boxed, Neon Mint, Editorial, Comic, Kinetic and Cinema. Caption size is adjustable. Comic uses chunky outlines; Kinetic adds restrained text tilt/pop; Cinema uses quiet caption fades.

Choose automatic, bubble-only, sticker-only, or no decorations. These original vector graphics trigger on transcript cues for questions, money, success and emphasis. They are spaced at least 12 seconds apart and limited to approximately three per minute. Graphics can overlap faces or existing source overlays, so review them or disable them. They are transcript rules, not visual scene understanding. Classic captions use no decorative overlays.

Sound palettes include subtle accents, cinematic swells/bells, digital sweeps/clicks and punchier impacts. Sparse timing uses keyword cues; Throughout adds spaced accents. Added effects are ducked under speech. Source audio only disables all added effects. Existing music and burned-in captions in the source remain.

## YouTube upload details

Every clip includes a **Title, description & tags** editor and Copy controls, plus `.post.txt` and `.youtube.json` downloads and these files in the ZIP. Title and description drafts are extracted from the clip transcript. Hashtags and tags use transcript keywords. Edit and save before uploading; saving refreshes the downloads and ZIP. This does not publish to YouTube.

Titles, descriptions and thumbnails matter more for discovery than tags according to [YouTube Help](https://support.google.com/youtube/answer/146402?hl=en). These drafts do not predict views or promise virality.

## Quality, workflow and files

- Default exports: 1080p H.264/AAC MP4, source frame rate up to 60 fps, large readable captions. GPU encoder quality settings vary by vendor; CPU fallback uses CRF 18.
- Audio: lossless preparation, measured two-pass normalization toward -16 LUFS / -2 dBTP, AAC target 256 kbps / 48 kHz. Poor source quality cannot be restored by upscaling.
- Accessible URLs are downloaded with yt-dlp. Site restrictions or changes can prevent access; use a local file instead. Models download on first local transcription.
- Topic search, transcript corrections, passage exclusion, pause/filler cuts, manual ranges, presets, clip ratings and sequential queues are available.
- Keep/Pass/Clear ratings adjust bounded text/length preferences for future highlight selection. Reference styles were manually interpreted; automatic reference-video learning and neural-network fine-tuning are not implemented.
- `clips/<job>/` contains exports, captions, upload details, covers, reports and ZIP. `uploads/` stores uploaded files; `models/` stores models. These can consume significant disk space. The app stays local at 127.0.0.1.
- Closing the server interrupts active/queued jobs. Completed files remain saved; incomplete jobs are not automatically resumed. The editor preview shows the existing export until a new version is rendered.
- Optional metadata migration adds upload files to older completed projects on launch. Existing video exports remain unchanged.

## Development and GitHub

Use the clean source ZIP for publishing, rather than uploading this working folder. It contains no user videos, transcripts, ratings, local paths, speech models, runtime environment or logs. The small MIT-licensed face model and its license are included. See THIRD-PARTY.md for dependencies.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe app.py
```

GitHub Actions checks Windows unit tests on pushes and pull requests. The workflow has not been run on GitHub in this local session. Fresh-machine installer behavior still needs verification on another Windows computer.

## Preview status and privacy

This is an early public preview. Local tests and sample exports passed; fresh installation on other Windows computers and the latest live interface still need verification. Highlight ranking uses transcript heuristics, not a semantic model, and no tool can guarantee virality.

Core processing runs on your computer. Link downloads, dependency installation and model downloads contact their respective providers. Uploading to social platforms is manual. The clean distribution excludes personal media and local processing history. Use videos you have permission to edit and share.

## License

ClipLocal source is released under the [MIT license](LICENSE). See [third-party notices](THIRD-PARTY.md) for dependency and model licenses.
