"""Resolve the observed Steam installation without a machine-specific path."""
from pathlib import PureWindowsPath


def game_launch_path(recorded_path):
    """Steam installs must launch through Steam; retain other recorded installs."""
    if not recorded_path:
        return None
    path = PureWindowsPath(recorded_path)
    parts = [part.lower() for part in path.parts]
    if path.name.lower() != 'starsavior.exe':
        return None
    if any(parts[i:i+2] == ['steamapps', 'common'] for i in range(len(parts)-1)):
        return 'steam://rungameid/3609080'
    return str(path)
