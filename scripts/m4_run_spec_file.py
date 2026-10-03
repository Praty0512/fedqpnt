"""Same as fedqpnt.node.runner._main but reads the RunSpec JSON from a file (argv[1]) (Windows cmdline limit)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fedqpnt.node.runner import RunSpec, run_single

if __name__ == "__main__":
    spec_dict = json.loads(Path(sys.argv[1]).read_text())
    result = run_single(RunSpec(**spec_dict))
    print(json.dumps(result, default=lambda o: None))
