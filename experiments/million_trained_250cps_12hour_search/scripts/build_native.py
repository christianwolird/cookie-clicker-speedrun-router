"""Build the optional native experiments; the Python router needs no compiler."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--work',default=os.environ.get('CCSR_EXPERIMENT_DIRECTORY','/tmp/ccsr-trained-12h-20260914'))
p.add_argument('--compiler',default='g++');args=p.parse_args();work=Path(args.work);work.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,str(HERE/'build_native_model.py')],check=True)
for source,name,flags in [('native_library.cpp','native_search.so',['-fPIC','-shared']),('native_anneal.cpp','native_anneal',['-pthread']),('native_beam.cpp','native_beam',['-pthread']),('native_quantity_scan.cpp','native_quantity_scan',[]),('native_quantity_range.cpp','native_quantity_range',[]),('native_quantity_cube.cpp','native_quantity_cube',[]),('native_policy.cpp','native_policy',[])]:
    temporary=work/(name+'.next')
    subprocess.run([args.compiler,'-std=c++17','-O3',*flags,str(HERE/source),'-o',str(temporary)],check=True)
    temporary.replace(work/name)
    print(work/name,flush=True)
