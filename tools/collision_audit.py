#!/usr/bin/env python3
"""Read every level's original collision families; no rendering export or source asset edits."""
import argparse
import json
from pathlib import Path
import psp_export as ex
from p3d import read

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    levels = []
    for level in range(1, 8):
        art = ex.GAME / 'art'
        names = [f'l{level}_terra'] + sorted(p.stem for p in art.glob(f'l{level}r*.p3d')) + sorted(p.stem for p in art.glob(f'l{level}z*.p3d'))
        tri, box, cyl, seg, rep = ex.col_collect([(n, read(art / (n + '.p3d'))) for n in names])
        marked = int((box[:, 15] == 1).sum() + (cyl[:, 9] == 1).sum())
        assert marked == len(rep['foliage']), f'L{level}: foliage identity lost'
        assert not rep['errors'], rep['errors']
        levels.append(dict(level=level, scenes=names, terrain_triangles=len(tri), boxes=len(box),
                           capsules=len(cyl), world_boundaries=len(seg), foliage_volumes=marked,
                           foliage=rep['foliage'], dynamic_families=rep['skipped']))
        print(f'L{level}: ground={len(tri)} boxes={len(box)} capsules={len(cyl)} boundaries={len(seg)} foliage={marked}', flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(dict(policy='foliage = CollisionEffect physProp whose ATC row spawns eShrub (psp_export.col_material), same rule for all levels; no name or texture inference', levels=levels), indent=2))

if __name__ == '__main__':
    main()
