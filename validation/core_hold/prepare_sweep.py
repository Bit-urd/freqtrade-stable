"""Generate static strategy subclasses for Freqtrade's --strategy-list.

The generated file belongs in an isolated research strategy directory.
"""
from pathlib import Path


def generate(destination: Path) -> list[str]:
    names = []
    lines = ['from ma200_btc_regime_full_cycle_core_hold_strategy import '
             'Ma200BtcRegimeFullCycleCoreHoldStrategy as Base', '']
    for mode in ('alignment', 'early'):
        for retained in (25, 50, 75):
            for days in (1, 2, 3):
                name = f'CoreHold_{mode}_{retained}_{days}d'
                names.append(name)
                lines.extend([f'class {name}(Base):',
                              f'    CORE_RETAIN_FRACTION = {retained / 100}',
                              f'    BTC_BEAR_CONFIRM_DAYS = {days}',
                              f'    BULL_ENTRY_MODE = "{mode}"', ''])
    destination.write_text('\n'.join(lines))
    return names


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(' '.join(generate(args.destination)))
