"""Exact retained-frame proof for the clipping broad phase, independent of capture I/O time."""
import argparse, hashlib, json, re, sys
from pathlib import Path
from PIL import Image, ImageChops

def check(run, scenes):
    log = (run / 'smoke.txt').read_text(errors='replace')
    errors, result = [], []
    if 'END' not in log.split() or 'RF_ABORT' in log:
        errors.append('incomplete capture')
    rows = [dict(re.findall(r'(\w+)=(\S+)', s)) for s in log.splitlines() if s.startswith('RF_FRAME ')]
    for scene in scenes:
        frames = [r for r in rows if r['sc'] == scene]
        if len(frames) != 5 or [r['pass'] for r in frames] != list('01234'):
            errors.append(scene + ': incomplete passes'); continue
        if [r['batch'] for r in frames] != list('10101') or any(r['mask'] != '7' for r in frames):
            errors.append(scene + ': wrong comparison policy')
        for key in ('frame', 't', 'hash', 'eye', 'dir', 'fovy', 'near', 'tris', 'draws', 'cars', 'park', 'peds'):
            if len({r[key] for r in frames}) != 1:
                errors.append(scene + ': changed ' + key)
        snap = run / ('rfsnap_' + scene + '.bin')
        meta = [dict(re.findall(r'(\w+)=(\S+)', s)) for s in log.splitlines()
                if s.startswith('RF_SNAPSHOT ') and 'sc=' + scene + ' ' in s]
        sha = None
        if len(meta) != 1 or meta[0].get('ok') != '1' or not snap.exists() or snap.stat().st_size != int(meta[0]['bytes']):
            errors.append(scene + ': invalid snapshot')
        else:
            sha = hashlib.sha256(snap.read_bytes()).hexdigest()
        diffs = []
        try:
            images = [Image.open(run / f'rf_{scene}_{i}.png').convert('RGB') for i in range(5)]
            for image in images[1:]:
                if image.size != images[0].size:
                    errors.append(scene + ': size mismatch'); continue
                pixels = sum(p != (0, 0, 0) for p in ImageChops.difference(images[0], image).getdata())
                diffs.append(pixels)
                if pixels:
                    errors.append(f'{scene}: {pixels} changed pixels')
        except FileNotFoundError:
            errors.append(scene + ': missing image')
        result.append(dict(scene=scene, snapshot_sha256=sha, frames=frames, pixel_differences=diffs))
    return errors, result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('--scenes', default='frozen_house,frozen_exit,frozen_shadow')
    args = parser.parse_args()
    errors, result = check(args.run, args.scenes.split(','))
    (args.run / 'batch-frozen-proof.json').write_text(json.dumps(dict(status='FAIL' if errors else 'PASS', errors=errors, scenes=result), indent=2) + '\n')
    for r in result:
        print(r['scene'], r['pixel_differences'], 'render_us', [f['render_us'] for f in r['frames']])
    for error in errors:
        print('FAIL', error)
    sys.exit(bool(errors))
