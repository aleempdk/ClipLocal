# Third-party components

The application source uses the MIT license. Dependencies retain their own licenses.

- Face model: [OpenCV Zoo YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet). Model-specific MIT license is included in `models/YUNET-LICENSE.txt`. The included model SHA-256 is `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`.
- [FFmpeg](https://ffmpeg.org/legal.html): downloaded separately by Windows Package Manager when needed. Gyan's build includes GPL components. FFmpeg binaries are not included in the source ZIP.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [CTranslate2](https://github.com/OpenNMT/CTranslate2), [OpenCV](https://github.com/opencv/opencv-python), NumPy and PyAV are installed from PyPI with their respective licenses.
- NVIDIA CUDA libraries are optional PyPI dependencies governed by NVIDIA's licenses. A compatible NVIDIA driver is required; this setup does not install or change GPU drivers.
- Whisper speech models download on first use; they are not part of the source release.
- System fonts are used locally and are not redistributed. All bubble/sticker drawings and synthesized effect waveforms are authored in this application's source.
