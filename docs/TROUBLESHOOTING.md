# Troubleshooting

| Problem | What to try |
|---|---|
| Setup stops | Read the terminal error and rerun Setup ClipLocal.cmd. Check internet access and free disk space. |
| winget is missing | Install/update Windows App Installer, or install Python 3.12, FFmpeg and Node.js from their official sites, then rerun setup. |
| NVIDIA package download fails | Run Setup ClipLocal.cmd --skip-gpu. CPU speech remains available. |
| Link cannot be downloaded | Try a local video file. Private, restricted, expired and unsupported links may fail. |
| First video is slow | Initial model downloads and model loading take time. Reusing a completed source/transcript avoids repeating those stages. |
| Wrong words or names | Correct the transcript and re-export. Caption correction does not change the original spoken audio. |
| Crop chooses the wrong person | Use Keep the full picture or a fixed crop. Face framing does not identify the active speaker. |
| Video moves too much | Set Picture motion to Off. Stable face framing holds small movements; a fixed crop removes automatic panning. |
| Graphics cover source content | Turn decorations off or choose a quieter caption style. |
| Browser closes | Keep the launcher open and reopen the local address shown in its terminal. Closing the server interrupts work. |

## Reporting an issue

Include Windows version, the visible error, reproduction steps, selected settings and a hardware summary. Remove usernames, private paths, private links and personal media before posting publicly. Do not upload your entire app folder or local logs without reviewing them.

The hardware benchmark selects the fastest successful short encoder test. Real exports also depend on transcription, face analysis, effects, resolution, duration, source codec and disk speed. AMD/Intel video encoding may work while speech still runs on CPU.
