import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

MAX_CONTENT_MB = int(os.environ.get("FFMPEG_MAX_CONTENT_MB", "500"))
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_MB * 1024 * 1024

JOBS_ROOT = Path(os.environ.get("FFMPEG_JOBS_DIR", "/tmp/ffmpeg-jobs"))
JOBS_ROOT.mkdir(parents=True, exist_ok=True)

FFMPEG_TIMEOUT = int(os.environ.get("FFMPEG_TIMEOUT_SECONDS", "600"))
JOB_MAX_AGE_SECONDS = 2 * 3600  # orphaned job dirs older than this get swept

VIDEO_EXTS = {"mp4", "mov", "mkv", "webm", "m4v"}
AUDIO_EXTS = {"mp3", "wav", "m4a", "aac", "ogg", "flac"}


class ValidationError(Exception):
    pass


def ext_of(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def sweep_old_jobs():
    """Best-effort cleanup of job dirs left behind by crashed/interrupted requests."""
    now = time.time()
    try:
        for entry in JOBS_ROOT.iterdir():
            if entry.is_dir() and (now - entry.stat().st_mtime) > JOB_MAX_AGE_SECONDS:
                shutil.rmtree(entry, ignore_errors=True)
    except FileNotFoundError:
        pass


def save_upload(file_storage, dest_path, allowed_exts, label):
    if file_storage is None or file_storage.filename == "":
        raise ValidationError(f'Файл «{label}» не передан')
    filename = secure_filename(file_storage.filename)
    ext = ext_of(filename)
    if ext not in allowed_exts:
        raise ValidationError(f'Недопустимый формат файла «{label}»: .{ext or "?"}')
    file_storage.save(dest_path)
    return ext


def parse_float(value, name, min_v=None, max_v=None, default=None):
    if value is None or value == "":
        if default is not None:
            return default
        raise ValidationError(f"Параметр «{name}» обязателен")
    try:
        v = float(value)
    except ValueError:
        raise ValidationError(f"Параметр «{name}» должен быть числом")
    if min_v is not None and v < min_v:
        raise ValidationError(f"Параметр «{name}» меньше допустимого ({min_v})")
    if max_v is not None and v > max_v:
        raise ValidationError(f"Параметр «{name}» больше допустимого ({max_v})")
    return v


def probe_duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return float(out.stdout.strip())
    except Exception:
        return None


def run_ffmpeg(cmd):
    # cmd is always a list of args (never a shell string), so nothing here is shell-interpreted.
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise ValidationError("Обработка заняла слишком много времени и была прервана")
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-15:])
        raise ValidationError(f"ffmpeg завершился с ошибкой:\n{tail}")


def send_and_cleanup(path, download_name, mimetype, job_dir):
    response = send_file(path, as_attachment=True, download_name=download_name,
                          mimetype=mimetype, conditional=False)
    # Runs only once the WSGI server has finished streaming the response body,
    # so the file is guaranteed to still exist while it's being sent.
    response.call_on_close(lambda: shutil.rmtree(job_dir, ignore_errors=True))
    return response


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/process")
def process():
    sweep_old_jobs()
    mode = request.form.get("mode", "")
    job_dir = JOBS_ROOT / uuid.uuid4().hex
    job_dir.mkdir(parents=True)

    try:
        if mode == "trim":
            src = job_dir / "input"
            ext = save_upload(request.files.get("file"), src, VIDEO_EXTS | AUDIO_EXTS, "файл")
            src = src.with_suffix(f".{ext}")
            (job_dir / "input").rename(src)

            start = parse_float(request.form.get("start"), "start", min_v=0, default=0)
            end = parse_float(request.form.get("end"), "end", min_v=0.1)
            if end <= start:
                raise ValidationError("Время окончания должно быть больше времени начала")

            out_path = job_dir / f"output.{ext}"
            cmd = ["ffmpeg", "-y", "-i", str(src), "-ss", str(start), "-to", str(end),
                   "-c", "copy", str(out_path)]
            run_ffmpeg(cmd)

            mimetype = "video/mp4" if ext in VIDEO_EXTS else "audio/mpeg"
            return send_and_cleanup(out_path, f"trim.{ext}", mimetype, job_dir)

        elif mode in ("replace", "mix", "duck"):
            video_path = job_dir / "video"
            v_ext = save_upload(request.files.get("video"), video_path, VIDEO_EXTS, "видео")
            video_path = video_path.with_suffix(f".{v_ext}")
            (job_dir / "video").rename(video_path)

            audio_path = job_dir / "audio"
            a_ext = save_upload(request.files.get("audio"), audio_path, AUDIO_EXTS, "аудио")
            audio_path = audio_path.with_suffix(f".{a_ext}")
            (job_dir / "audio").rename(audio_path)

            duration = probe_duration(video_path)
            if duration is None:
                raise ValidationError("Не удалось определить длительность видео")

            out_path = job_dir / "output.mp4"

            if mode == "replace":
                cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
                       "-map", "0:v:0", "-map", "1:a:0",
                       "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                       "-shortest", str(out_path)]

            elif mode == "mix":
                music_volume = parse_float(request.form.get("music_volume"), "music_volume",
                                            min_v=0, max_v=3, default=0.4)
                filter_complex = (
                    f"[0:a]volume=1.0[orig];"
                    f"[1:a]atrim=0:{duration:.3f},asetpts=PTS-STARTPTS,volume={music_volume}[music];"
                    f"[orig][music]amix=inputs=2:duration=first:normalize=0[aout]"
                )
                cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
                       "-filter_complex", filter_complex,
                       "-map", "0:v:0", "-map", "[aout]",
                       "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                       "-shortest", str(out_path)]

            else:  # duck
                threshold = parse_float(request.form.get("threshold"), "threshold",
                                         min_v=0.001, max_v=1, default=0.03)
                ratio = parse_float(request.form.get("ratio"), "ratio", min_v=1, max_v=20, default=8)
                attack = parse_float(request.form.get("attack"), "attack", min_v=1, max_v=2000, default=5)
                release = parse_float(request.form.get("release"), "release", min_v=1, max_v=5000, default=300)
                filter_complex = (
                    f"[1:a]atrim=0:{duration:.3f},asetpts=PTS-STARTPTS[music];"
                    f"[music][0:a]sidechaincompress=threshold={threshold}:ratio={ratio}:"
                    f"attack={attack}:release={release}:makeup=1[music_ducked];"
                    f"[0:a][music_ducked]amix=inputs=2:duration=first:normalize=0[aout]"
                )
                cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
                       "-filter_complex", filter_complex,
                       "-map", "0:v:0", "-map", "[aout]",
                       "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                       "-shortest", str(out_path)]

            run_ffmpeg(cmd)
            return send_and_cleanup(out_path, "result.mp4", "video/mp4", job_dir)

        else:
            raise ValidationError("Неизвестный режим обработки")

    except ValidationError as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 400
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": f"Файл слишком большой (максимум {MAX_CONTENT_MB} МБ)"}), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
