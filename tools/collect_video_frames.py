"""Extract provenance-tracked frames from a public or local gameplay recording.

Use a separate video environment. Frames remain unlabelled; this command does
not create ground truth or upload media. Existing output directories are refused.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, help='Existing local recording; otherwise download --url')
    p.add_argument('--url', required=True, help='Original public source URL, retained in the manifest')
    p.add_argument('--start', type=float, default=0)
    p.add_argument('--end', type=float, required=True)
    p.add_argument('--interval', type=float, default=2)
    p.add_argument('--crop', type=int, nargs=4, metavar=('X','Y','WIDTH','HEIGHT'))
    p.add_argument('--normalize', action='store_true', help='Explicitly normalize the chosen viewport to 720x1280')
    p.add_argument('--group', required=True, help='Original recording/session group, shared by all reposts')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists() or args.start < 0 or args.end <= args.start or args.interval <= 0:
        p.error('Use a new output directory and a positive extraction interval')
    if args.normalize and not args.crop:
        p.error('--normalize requires an explicitly reviewed crop')
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    args.output.mkdir(parents=True)
    video = args.input.resolve() if args.input else None
    metadata = None
    if video is None:
        import yt_dlp
        with yt_dlp.YoutubeDL({'format': 'bestvideo[protocol=https][ext=mp4][vcodec^=avc1][height<=1920]/bestvideo[height<=1920]',
                              'noplaylist': True, 'socket_timeout': 20, 'retries': 3,
                              'ffmpeg_location': ffmpeg, 'outtmpl': str(args.output/'video.%(ext)s')}) as downloader:
            info = downloader.extract_info(args.url, download=True)
            video = Path(downloader.prepare_filename(info))
            metadata = {k: info.get(k) for k in ['id','title','uploader','channel_id','upload_date','duration','width','height']}
    frames = args.output/'frames'
    frames.mkdir()
    filters = [f'trim=duration={args.end-args.start}',
               f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{args.interval})'"]
    if args.crop:
        x,y,w,h = args.crop
        if min(x,y)<0 or min(w,h)<=0:
            p.error('Invalid crop')
        filters.append(f'crop={w}:{h}:{x}:{y}')
    if args.normalize:
        filters.append('scale=720:1280:flags=lanczos')
    filters.append('showinfo')
    command = [ffmpeg,'-hide_banner','-loglevel','info','-ss',str(args.start),'-i',str(video),
               '-t',str(args.end-args.start),'-vf',','.join(filters),'-vsync','vfr',str(frames/'%05d.png')]
    result = subprocess.run(command, capture_output=True, text=True)
    (args.output/'ffmpeg.log').write_text(result.stderr,'utf-8')
    if result.returncode:
        raise RuntimeError('Frame extraction failed; inspect ffmpeg.log')
    times = [float(v) for v in re.findall(r'\bn:\s*\d+\s+pts:\s*-?\d+\s+pts_time:([\d.]+)',result.stderr)]
    paths = sorted(frames.glob('*.png'))
    if len(times) != len(paths) or not paths:
        raise RuntimeError('Output frames and frame presentation timestamps disagree')
    from PIL import Image
    records = []
    for path,pts in zip(paths,times):
        with Image.open(path) as image:
            width,height = image.size
        records.append({'path':str(path.relative_to(args.output)),'timestampSeconds':args.start+pts,
                        'sha256':digest(path),'width':width,'height':height,'labelsVerified':False})
    decoder_warnings = [line for line in result.stderr.splitlines() if any(t in line.lower() for t in
                        ['error', 'corrupt', 'invalid', 'not implemented', 'conceal'])]
    manifest = {'sourceUrl':args.url,'recordingGroup':args.group,'sourceMetadata':metadata,
                'videoSha256':digest(video),'sourceFile':str(video),'cropXYWH':args.crop,
                'normalized720x1280':args.normalize,'intervalSeconds':args.interval,
                'split':'unassigned','frames':records,'python':sys.version,'decoderWarnings':decoder_warnings,
                'ffmpegCommand':command,'ffmpegVersion':subprocess.check_output([ffmpeg,'-version'],text=True).splitlines()[0]}
    (args.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'frames':len(records),'manifest':str(args.output/'manifest.json'),'labelsVerified':False}),flush=True)


if __name__=='__main__':
    main()
