"""Launch one bounded expensive search from the latest verified incumbent."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from experiment_paths import WORK

here=Path(__file__).resolve().parent;config=json.loads((here/'long_campaign.json').read_text())
p=argparse.ArgumentParser();p.add_argument('name',choices=config['trials']);p.add_argument('--seconds',type=float,default=14400)
p.add_argument('--source',default=str(WORK/'session_best.route'));args=p.parse_args()
options=dict(config['common'],**config['trials'][args.name])
options['shared-ruler']=str(WORK/'shared_incumbent.seed')
subprocess.run([sys.executable,str(here/'run_native_beam.py'),args.name,'--source',args.source,
                '--seconds',str(args.seconds),'--options-json',json.dumps(options)],check=True)
