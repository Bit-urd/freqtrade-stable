from pathlib import Path
import runpy
root=Path(__file__).resolve().parent
runpy.run_path(str(root/'audit_events.py'),run_name='__main__')
runpy.run_path(str(root/'audit_positions.py'),run_name='__main__')
