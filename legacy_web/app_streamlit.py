"""English Streamlit interface. Start: python -m streamlit run app.py"""
from pathlib import Path
import io,json,zipfile
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from sboxlab.core import A,B,construct,core,inverse,analyze,parse_lut,trace,affine_search
from sboxlab.catalog import comparison,benchmarks,gate_comparison
from sboxlab import circuits
from sboxlab.cipher import key_bytes,nonce_for,material,encrypt,decrypt
from sboxlab.experiments import demo,image_from_file,png,stats,recovery,run,metadata
from sboxlab.export import heatmap,sbox_zip,experiment_zip,json_bytes,cipher_bundle,load_cipher,benchmark_tables_zip

st.set_page_config(page_title='SBoxLab 4×4 | Experimental Platform',page_icon='🔬',layout='wide')
st.markdown('''<style>.stApp {background:#f7f9fc} h1,h2,h3 {color:#10233f}
[data-testid="stMetric"] {background:white;border:1px solid #dde4ed;padding:16px;border-radius:12px}
[data-testid="stSidebar"] {background:#edf2f8}</style>''',unsafe_allow_html=True)
st.sidebar.title('SBoxLab')
st.sidebar.caption('4×4 S-Box Construction • Cryptographic Analysis • Reproducible Experiments')
page=st.sidebar.radio('Workspace',['Overview','Construction','Cryptographic Analysis','Benchmark Comparison','Logic Circuits','Image Encryption','Experiments','Affine Exploration'])
choice=st.sidebar.selectbox('Active S-box',['Proposed S','Proposed inverse','Custom hexadecimal LUT'])
try:
    if choice=='Custom hexadecimal LUT':s=parse_lut(st.sidebar.text_input('16 hexadecimal values','4B8A6C72013E59FD'))
    else:s=construct() if choice=='Proposed S' else inverse(construct())
except ValueError as e:st.error(str(e));st.stop()
st.sidebar.code(''.join(f'{x:X}' for x in s))
st.sidebar.caption('LSB-first bit order. Research prototype; not authenticated production encryption.')
st.title(page)

if page=='Overview':
    st.markdown('### From algebraic construction to measured image experiments')
    st.write('Generate the paper’s S-box, inspect every cryptographic table, compare 25 benchmark substitutions, verify logic networks, and run image experiments on your own machine.')
    st.caption('Verified manuscript reference pair')
    c=st.columns(4)
    for col,label,val in zip(c,['Vectorial NL','Differential uniformity','Bidirectional SAC','Gates / direction'],[4,4,'0.500','28']):col.metric(label,val)
    st.info('Image KDF serialization is explicitly defined as SBoxLab-image-v1. The manuscript did not specify all byte encodings, so newly measured image statistics are not guaranteed to equal its earlier tables.')
    st.dataframe(pd.DataFrame([
      ['Construction','ANF core → input affine map → output affine map → inverse'],
      ['Analysis','LAT, DDT, SAC, ANF, NL, DU, AD, AT, FP/OFP, BIC'],
      ['Comparison','25 source LUTs recomputed under one convention'],
      ['Circuits','28-gate networks, exhaustive simulation, DOT/Verilog/BLIF export'],
      ['Images','Two rounds, round-trip decryption, histograms and correlation'],
      ['Experiments','100 plaintext flips, 30 key flips, 5 warm-ups, 30 timing runs'],
      ['Exports','Raw CSV, JSON metadata, LaTeX tables, PNG/PDF figures, ciphertext bundle']
    ],columns=['Module','Capabilities']),hide_index=True,width='stretch')
    st.caption('Synthetic demo images are included. Upload the original USC-SIPI files to run the paper’s image set.')
    with st.expander('Detected execution environment'):st.json(metadata())

elif page=='Construction':
    st.latex(r'S(x)=B\,G(Ax\oplus\alpha)\oplus\beta')
    st.caption('Rows and columns of binary matrices follow the LSB-first convention.')
    c1,c2=st.columns(2)
    with c1:aa=st.data_editor(pd.DataFrame(A),key='matrix_a');alpha=st.number_input('Input offset alpha',0,15,9)
    with c2:bb=st.data_editor(pd.DataFrame(B),key='matrix_b');beta=st.number_input('Output offset beta',0,15,10)
    try:
        custom=construct(aa.to_numpy(),bb.to_numpy(),alpha,beta)
        st.code('G = '+''.join(f'{x:X}' for x in core())+'\nS = '+''.join(f'{x:X}' for x in custom)+'\nInverse = '+''.join(f'{x:X}' for x in inverse(custom)))
        st.dataframe(pd.DataFrame(trace(aa.to_numpy(),bb.to_numpy(),alpha,beta)),hide_index=True,width='stretch')
        st.download_button('Download construction JSON',json_bytes({'A':aa.to_numpy(),'B':bb.to_numpy(),'alpha':alpha,'beta':beta,'core':core(),'lut':custom,'inverse':inverse(custom)}),'construction.json')
        st.caption('To analyze an edited construction in another workspace, copy its LUT into the sidebar’s Custom hexadecimal LUT field.')
    except ValueError as e:st.error(str(e))

elif page=='Cryptographic Analysis':
    f=analyze(s);inv=analyze(inverse(s));c=st.columns(4)
    for col,k in zip(c,['NL','DU','linear_bias','SAC_mean']):col.metric(k,f['summary'][k])
    direction=st.radio('Direction',['Forward','Inverse'],horizontal=True);r=f if direction=='Forward' else inv
    st.dataframe(pd.DataFrame([r['summary']]).astype(str),hide_index=True)
    tabs=st.tabs(['LAT (Walsh)','DDT','SAC','ANF','BIC'])
    for tab,key,title in zip(tabs[:3],['lat','ddt','sac'],['Walsh LAT','Difference distribution table','Strict avalanche criterion']):
        with tab:
            st.dataframe(pd.DataFrame(r[key]),width='stretch')
            fig=heatmap(r[key],title);st.pyplot(fig);plt.close(fig)
    with tabs[3]:
        for j,expr in enumerate(r['anf']):st.code(f'f{j} = {expr}')
    with tabs[4]:st.write('SAC of pairwise coordinate XORs (not a complete proof of avalanche-bit independence).');st.dataframe(pd.DataFrame(r['bic_sac'],columns=['0 XOR 1','0 XOR 2','0 XOR 3','1 XOR 2','1 XOR 3','2 XOR 3']))
    st.success(f"Inverse checks: LAT transpose = {np.array_equal(inv['lat'],f['lat'].T)}; DDT transpose = {np.array_equal(inv['ddt'],f['ddt'].T)}")
    if st.button('Prepare analysis export'):st.session_state['analysis_export']=sbox_zip({'forward':f,'inverse':inv});st.session_state['analysis_lut']=s.tolist()
    if st.session_state.get('analysis_lut')==s.tolist():st.download_button('Download analysis ZIP',st.session_state['analysis_export'],'sbox_analysis.zip')

elif page=='Benchmark Comparison':
    df=comparison();st.write('All metrics are recomputed from the 25 manuscript LUTs; the proposed pair is also included.')
    st.dataframe(df,hide_index=True,width='stretch')
    st.download_button('Download comparison CSV',df.to_csv(index=False),'comparison.csv')
    st.download_button('Download LaTeX table',df.to_latex(index=False),'comparison.tex')
    st.dataframe(pd.DataFrame(benchmarks()),hide_index=True)
    selected=st.selectbox('Inspect benchmark', [r['name'] for r in benchmarks()])
    entry=next(r for r in benchmarks() if r['name']==selected)
    detail=analyze(parse_lut(entry['lut']))
    field=st.radio('Benchmark table',['sac','lat','ddt','bic_sac'],horizontal=True)
    st.dataframe(pd.DataFrame(detail[field]),width='stretch')
    if st.button('Prepare all benchmark tables'):st.session_state['benchmark_export']=benchmark_tables_zip()
    if 'benchmark_export' in st.session_state:st.download_button('Download all benchmark tables',st.session_state['benchmark_export'],'benchmark_tables.zip')

elif page=='Logic Circuits':
    direction=st.radio('Circuit',['forward','inverse'],horizontal=True);g=circuits.load(direction);values,info=circuits.simulate(g,direction)
    expected=construct() if direction=='forward' else inverse(construct())
    st.caption('These fixed networks implement the manuscript pair, independently of the sidebar selection.')
    st.json(info);st.success('All 16 inputs match the manuscript LUT.' if np.array_equal(values,expected) else 'Verification failed.')
    asset=Path('assets')/f'{direction}_circuit.png'
    if asset.exists():st.image(str(asset),caption='Original manuscript circuit, verified against the executable netlist.',width='stretch')
    with st.expander('Dependency graph (gate types shown as labels)'):st.graphviz_chart(circuits.dot(g,direction))
    st.dataframe(pd.DataFrame(g,columns=['Output','Gate','Input A','Input B']),hide_index=True)
    st.download_button('Verilog',circuits.verilog(g,direction),f'{direction}.v')
    st.download_button('Netlist JSON',json_bytes(g),f'{direction}_netlist.json')
    st.download_button('Graphviz DOT',circuits.dot(g,direction),f'{direction}.dot')
    st.download_button('Active S-box BLIF',circuits.blif(s),'active_sbox.blif')
    with st.expander('Published gate-count comparison (21 literature implementations)'):
        gd=gate_comparison();st.dataframe(gd,hide_index=True,width='stretch')
        st.caption('Literature rows are transcribed reported counts, not new synthesis measurements. The final two rows are verified manuscript networks.')
        st.download_button('Download gate comparison CSV',gd.to_csv(index=False),'gate_comparison.csv')
    with st.expander('Optional new synthesis with Berkeley ABC'):
        st.write('Requires abc on PATH. This new generic mapping run permits INV cells and does not recreate the unavailable original optimizer or guarantee 28 gates. Inspect and verify its output before use.')
        if st.button('Run ABC on active S-box'):
            try:
                log,hdl=circuits.run_abc(s);st.code(log);st.download_button('Download ABC Verilog',hdl,'abc_mapped.v')
            except (RuntimeError,TimeoutError) as e:st.error(str(e))

elif page=='Image Encryption':
    mode=st.radio('Operation',['Encrypt and verify','Decrypt saved bundle'],horizontal=True)
    key=st.text_input('128-bit key (32 hex characters)','00112233445566778899AABBCCDDEEFF',type='password')
    if mode=='Encrypt and verify':
        file=st.file_uploader('Upload grayscale or RGB image',type=['png','jpg','jpeg','tif','tiff','bmp'])
        image_id=st.text_input('Image ID',file.name if file else 'synthetic-demo')
        st.caption('No upload uses a synthetic 64 × 64 RGB test pattern. The key is not included in exports.')
        if st.button('Encrypt → decrypt → verify'):
            try:
                img=image_from_file(file) if file else demo();k=key_bytes(key);nonce=nonce_for(image_id,img.shape);m=material(k,nonce,img.shape)
                states=encrypt(img,m,s,True);rec=decrypt(states[-1],m,s)
                st.session_state['image_run']={'images':[img,*states,rec],'recovery':recovery(img,rec),'stats':[{'stage':n,**stats(a)} for n,a in zip(['Original','R1','R2'],[img,*states])],
                  'bundle':cipher_bundle(states[-1],nonce,s,image_id),'image_id':image_id,'lut':s.tolist()}
            except (ValueError,OSError) as e:st.error(str(e))
        if 'image_run' in st.session_state:
            r=st.session_state['image_run'];st.caption('Saved result: '+r['image_id']+' • LUT '+''.join(f'{v:X}' for v in r['lut']))
            cols=st.columns(2)
            for i,(name,a) in enumerate(zip(['Original','R1','R2','Recovered'],r['images'])):
                with cols[i%2]:st.image(a,caption=name,width='stretch')
            st.json(r['recovery']);st.dataframe(pd.DataFrame(r['stats']),hide_index=True)
            st.download_button('Download ciphertext bundle (NPZ)',r['bundle'],'ciphertext.npz')
            st.download_button('Download recovered PNG',png(r['images'][-1]),'recovered.png')
    else:
        file=st.file_uploader('Upload ciphertext.npz',type=['npz'])
        if st.button('Decrypt bundle'):
            if file is None:st.error('Select a ciphertext bundle first.')
            else:
                try:
                    c,n,lut,identifier=load_cipher(file);p=decrypt(c,material(key_bytes(key),n,c.shape),lut)
                    st.session_state['decrypted_png']=png(p);st.image(p,caption=identifier,width='stretch')
                    st.warning('This research transform has no authentication tag. A wrong key or modified bundle cannot be reliably detected.')
                except (ValueError,KeyError,OSError,zipfile.BadZipFile) as e:st.error(str(e))
        if 'decrypted_png' in st.session_state:st.download_button('Download decrypted PNG',st.session_state['decrypted_png'],'decrypted.png')

elif page=='Experiments':
    st.write('Run plaintext sensitivity, key sensitivity, statistics, exact recovery, and real CPU timing. Uploaded images are processed at their original resolution.')
    files=st.file_uploader('Test images (up to four per batch)',type=['png','jpg','jpeg','tif','tiff','bmp'],accept_multiple_files=True)
    key=st.text_input('Master key','00112233445566778899AABBCCDDEEFF',type='password')
    c=st.columns(5)
    trials=c[0].number_input('Plaintext trials',0,1000,100)
    kt=c[1].number_input('Key trials',0,128,30)
    warm=c[2].number_input('Warm-up runs',0,50,5)
    repeats=c[3].number_input('Timing repetitions',2,200,30)
    seed=c[4].number_input('Random seed',0,2147483647,42)
    st.caption('Without uploads, the synthetic 64 × 64 demo is used. Large images and 100 trials can take several minutes. KDF/permutation generation is excluded from timed regions.')
    if st.button('Run experiment batch',type='primary'):
        try:
            k=key_bytes(key)
            if len(files)>4:raise ValueError('Upload at most four images per batch.')
            items=[(f.name,image_from_file(f)) for f in files] if files else [('synthetic-demo',demo())]
            outputs=[];bar=st.progress(0.0)
            for j,(name,img) in enumerate(items):
                st.write('Processing: '+name)
                r=run(img,k,name,s,int(trials),int(kt),int(warm),int(repeats),int(seed),lambda p:bar.progress((j+p)/len(items)))
                outputs.append((name,r,experiment_zip(r)))
            buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
                for j,(name,r,blob) in enumerate(outputs):z.writestr(f'{j+1:02d}_'+Path(name).stem+'_results.zip',blob)
                summary=pd.DataFrame([{'image':name,**r['runtime']} for name,r,blob in outputs]);z.writestr('runtime_summary.csv',summary.to_csv(index=False))
            st.session_state['batch']={'rows':[{'image':n,**r['runtime'],'exact_recovery':r['recovery']['exact']} for n,r,b in outputs],'blob':buf.getvalue(),'env':metadata(),'details':[{'image':n,'statistics':r['statistics'],'recovery':r['recovery'],'differential':r['differential_trials'],'key_sensitivity':r['key_trials_raw'],'runtime_raw':r['runtime_raw']} for n,r,b in outputs]}
        except (ValueError,OSError,AssertionError) as e:st.error(str(e))
    if 'batch' in st.session_state:
        st.success('Measured results ready. Actual machine details are included in the report.')
        st.dataframe(pd.DataFrame(st.session_state['batch']['rows']),hide_index=True)
        st.download_button('Download complete experiment ZIP',st.session_state['batch']['blob'],'experiment_batch.zip')
        with st.expander('Execution environment'):st.json(st.session_state['batch']['env'])
        for item in st.session_state['batch']['details']:
            with st.expander('Results: '+item['image']):
                st.dataframe(pd.DataFrame(item['statistics']),hide_index=True)
                st.json(item['recovery'])
                raw=pd.DataFrame(item['differential'])
                if not raw.empty:
                    st.write('Plaintext sensitivity: mean, sample standard deviation, minimum, maximum')
                    st.dataframe(raw.groupby('round')[['NPCR','UACI','Hamming']].agg(['mean','std','min','max']))
                    st.line_chart(raw.pivot(index='trial',columns='round',values='NPCR'))
                kr=pd.DataFrame(item['key_sensitivity'])
                if not kr.empty:st.dataframe(kr[['NPCR','UACI','Hamming']].agg(['mean','std','min','max']))
                st.line_chart(pd.DataFrame(item['runtime_raw']).set_index('repeat'))

elif page=='Affine Exploration':
    st.write('Seeded sampling of invertible input/output matrices and offsets. Classical affine invariants are recomputed, while forward and inverse SAC profiles may change.')
    st.info('This is a bounded sample, not an exhaustive classification of all affine-equivalent S-boxes.')
    n=st.number_input('Candidates',1,5000,100);seed=st.number_input('Seed',0,2147483647,42)
    if st.button('Explore affine representatives'):
        with st.spinner('Evaluating candidates...'):st.session_state['affine_rows']=affine_search(int(n),int(seed))
    if 'affine_rows' in st.session_state:
        rows=st.session_state['affine_rows'];st.dataframe(pd.DataFrame(rows).drop(columns=['A','B']),hide_index=True)
        st.download_button('Download all parameters and profiles',json_bytes(rows),'affine_search.json')
