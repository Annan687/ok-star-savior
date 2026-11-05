"""Recognize the observed battle HUD without toggling an uncertain control."""
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from .vision import Text


# These sanitized masks contain only icon silhouettes, not a game screenshot.
# Coordinates refer to the 1600 x 900 client area, excluding the window title.
_AUTO = (1375, 35, 1422, 76)
_SPEED = (1442, 35, 1493, 76)
_PAUSE = (1515, 35, 1547, 76)


@lru_cache(maxsize=1)
def _battle_masks():
    root = Path(__file__).resolve().parent.parent / 'assets' / 'activities'
    auto = cv2.imdecode(np.fromfile(root / 'battle-auto.png', np.uint8), 0)
    controls = cv2.imdecode(np.fromfile(root / 'battle-controls.png', np.uint8), 0)
    if auto is None or controls is None or auto.shape != (41, 47) or controls.shape != (41, 105):
        raise ValueError('Invalid battle-control masks')
    result = []
    for mask in (auto, controls[:, :51], controls[:, 73:]):
        core = cv2.erode(mask, np.ones((3, 3), np.uint8)) > 0
        # Check the black outline around the glyph too: a bright rectangle or
        # wallpaper patch must not become a battle control by brightness alone.
        edge = ((cv2.dilate(mask, np.ones((5, 5), np.uint8)) > 0)
                & ~(cv2.dilate(mask, np.ones((3, 3), np.uint8)) > 0))
        result.append((core, edge))
    return tuple(result)


def _glyph(gray, saturation, bounds, masks, dx, dy):
    x, y, right, bottom = bounds
    patch = gray[y+dy:bottom+dy, x+dx:right+dx]
    color = saturation[y+dy:bottom+dy, x+dx:right+dx]
    core, edge = masks
    if patch.shape != core.shape:
        return None
    values = patch[core]
    low, middle, high = np.quantile(values, (.1, .5, .9))
    if np.mean(color[core] <= 35) < .90:
        return None
    if np.quantile(patch[edge], .75) >= min(90, middle * .60):
        return None
    # A uniformly lit glyph is required; partial occlusion and mouse-hover
    # effects are not evidence that automatic battle is enabled or disabled.
    if high-low > 45:
        return None
    return low, middle, high


def auto_battle_state(v):
    """Return 'on', 'off', or None from the three matching battle HUD icons.

    Enabled is white and disabled is gray. The blue highlight in a hovered
    screenshot is not an enabled-state marker. White speed and pause controls
    must also be present, excluding dim overlays and isolated auto-like icons.
    Caller is responsible for waiting for consecutive consistent frames.
    """
    frame = getattr(v, 'frame', None)
    if (frame is None or frame.ndim != 3 or frame.shape[2] != 3
            or frame.shape[0] < 540 or frame.shape[1] < 960
            or abs(frame.shape[1] / frame.shape[0] - 16/9) > .02):
        return None
    frame = cv2.resize(frame, (1600, 900))
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    saturation = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[:, :, 1]
    masks = _battle_masks()
    states = set()
    # Shared small offsets accommodate scaling/antialiasing without searching
    # the rest of the screen or accepting unrelated white UI controls.
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            controls = [_glyph(gray, saturation, bounds, mask, dx, dy)
                        for bounds, mask in zip((_SPEED, _PAUSE), masks[1:])]
            if any(c is None or c[0] < 215 or c[1] < 230 for c in controls):
                continue
            auto = _glyph(gray, saturation, _AUTO, masks[0], dx, dy)
            if auto is None:
                continue
            low, middle, high = auto
            reference = sum(c[1] for c in controls) / 2
            if low >= 215 and .90 <= middle/reference <= 1.15:
                states.add('on')
            elif low >= 85 and high <= 165 and .35 <= middle/reference <= .70:
                states.add('off')
    return states.pop() if len(states) == 1 else None


def auto_battle_target(v):
    """Return the center of a confirmed disabled auto control, otherwise None."""
    if auto_battle_state(v) != 'off':
        return None
    x, y, right, bottom = _AUTO
    return Text('自動戰鬥', x/1600, y/900, (right-x)/1600, (bottom-y)/900)
