import argparse,json
from pathlib import Path
from .core import construct,analyze,inverse
from .catalog import comparison
from .experiments import demo,image_from_file,run
from .cipher import key_bytes
from .export import sbox_zip,experiment_zip

def main():
    p=argparse.ArgumentParser(description='SBoxLab reproducible research CLI')
    p.add_argument('command',choices=['analyze','experiment']);p.add_argument('--images',nargs='*',default=[])
    p.add_argument('--output',default='results');p.add_argument('--key',default='00112233445566778899AABBCCDDEEFF')
    p.add_argument('--trials',type=int,default=100);p.add_argument('--key-trials',type=int,default=30)
    p.add_argument('--warmups',type=int,default=5);p.add_argument('--repeats',type=int,default=30);p.add_argument('--seed',type=int,default=42)
    a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True);s=construct()
    if a.command=='analyze':
        (out/'sbox_analysis.zip').write_bytes(sbox_zip({'forward':analyze(s),'inverse':analyze(inverse(s))},comparison()))
        print('Saved:',out/'sbox_analysis.zip')
    else:
        items=[(Path(f).stem,image_from_file(f)) for f in a.images] if a.images else [('synthetic-demo',demo())]
        for i,(name,image) in enumerate(items):
            r=run(image,key_bytes(a.key),name,s,a.trials,a.key_trials,a.warmups,a.repeats,a.seed)
            path=out/f'{i+1:02d}_{name}_results.zip';path.write_bytes(experiment_zip(r));print(path,json.dumps(r['runtime']))
if __name__=='__main__':main()
