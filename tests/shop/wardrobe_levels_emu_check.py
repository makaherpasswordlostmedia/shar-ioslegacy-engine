#!/usr/bin/env python3
"""Check normal wardrobe screen/input/wear frames from the headless PSP build.

Fixture opens the normal screen through wardtestopen; room entry is not covered.
Names and prices are read independently from the owner's rewards.mfk.
"""
import argparse
from pathlib import Path
import re
import sys
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
from wardrobe_levels import contract

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('report'); a = ap.parse_args()
    directory = Path(a.report); log = (directory / 'smoke.txt').read_text(errors='replace')
    fails = []
    if not re.search(r'^END\b', log, re.M): fails.append('scenario did not reach END')
    for level in range(2, 8):
        match = re.search(rf'^# scene ward_l{level}.*?(?=^# scene |^END|\Z)', log, re.M | re.S)
        # Scene marker in viewer/smoke.h is SCENE, not every log embeds the hash prefix.
        if not match: match = re.search(rf'^SCENE ward_l{level}.*?(?=^SCENE |^END|\Z)', log, re.M | re.S)
        if not match:
            # Delimit by selection names (unique first costume on each level).
            starts = [m.start() for m in re.finditer(rf'WARDV open n=4 cur=0 coins=\d+ name={contract(level)[0][0]}\b', log)]
            shot = log.find(f'SHOT l{level}_restored')
            start = next((s for s in starts if s < shot and f'SHOT l{level}_default' in log[s:shot]), -1)
            block = log[start:shot] if start >= 0 else ''
        else: block = match.group(0)
        rows = contract(level); name, _, price = rows[1]
        opened = re.search(r'WARDV open n=4 cur=0 coins=(\d+)', block)
        purchased = re.search(rf'WARDV buy 1 name={name} price={price} coins=(\d+)', block)
        if not opened or not purchased or int(opened[1]) - int(purchased[1]) != price: fails.append(f'L{level} purchase amount')
        for text in ('WARDV model 0 player.shr', 'WARDV model 1 skin1.shr', 'WARDROBE wear 1 skin1.shr', 'WARDROBE wear 0 player.shr'):
            if text not in block: fails.append(f'L{level} missing {text}')
        for suffix in ('default', 'costume', 'worn', 'restored'):
            file = directory / f'l{level}_{suffix}.png'
            if not file.is_file(): fails.append(f'L{level} missing {suffix} frame')
        p, q = directory / f'l{level}_default.png', directory / f'l{level}_costume.png'
        if p.is_file() and q.is_file():
            # In the default row there is no yellow padlock. Detect the player's
            # warm skin pixels inside the gallery, away from coins/name/arrows.
            # OLD has zero; a mere change of selection/lock is not a model proof.
            gallery = np.asarray(Image.open(p).convert('RGB'))[35:225, 155:320].astype('int16')
            skin_pixels = int(((gallery[:, :, 0] > 60) & (gallery[:, :, 1] > 50) &
                               (gallery[:, :, 2] < gallery[:, :, 0] * .6)).sum())
            if skin_pixels < 100: fails.append(f'L{level} empty default model ({skin_pixels} skin pixels)')
            print(f'CHECK L{level} default_model skin_pixels={skin_pixels}')
            image1 = np.asarray(Image.open(p).convert('RGB'))[55:195, 155:320].astype('int16')
            image2 = np.asarray(Image.open(q).convert('RGB'))[55:195, 155:320].astype('int16')
            changed = int((np.abs(image1 - image2).max(axis=2) > 40).sum())
            if changed < 100: fails.append(f'L{level} preview images identical ({changed} changed pixels)')
            print(f'CHECK L{level} preview changed_pixels={changed}')
        print(f'CHECK L{level} purchase/wear {"FAIL" if any(f.startswith(f"L{level} ") for f in fails) else "OK"}')
    for fail in fails: print('FAIL', fail)
    print('wardrobe levels emulator: ' + ('FAIL' if fails else 'PASS'))
    return bool(fails)

if __name__ == '__main__': raise SystemExit(main())
