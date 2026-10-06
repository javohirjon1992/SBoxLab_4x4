"""Optional independent iverilog validation of exported gate primitives."""
import sys,shutil,subprocess,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sboxlab.circuits import load,verilog
from sboxlab.core import construct,inverse

def main():
    compiler=shutil.which('iverilog');runtime=shutil.which('vvp')
    if not compiler or not runtime:raise SystemExit('Install Icarus Verilog (iverilog and vvp on PATH) to run HDL verification.')
    for direction,target in [('forward',construct()),('inverse',inverse(construct()))]:
        inp,out=('x','s') if direction=='forward' else ('y','r')
        checks='\n'.join(f"{inp}=4'h{x:X}; #1; if ({out} !== 4'h{int(y):X}) $fatal(1, \"Mismatch at {x}\");" for x,y in enumerate(target))
        tb=f'''module test; reg [3:0] {inp}; wire [3:0] {out};
sbox_{direction} dut ({inp}, {out}); initial begin
{checks}
$display("All 16 {direction} inputs passed"); $finish; end endmodule'''
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'design.v').write_text(verilog(load(direction),direction));(p/'test.v').write_text(tb)
            subprocess.run([compiler,'-g2012','-o',str(p/'test'),str(p/'design.v'),str(p/'test.v')],check=True,timeout=30)
            subprocess.run([runtime,str(p/'test')],check=True,timeout=30)
if __name__=='__main__':main()
