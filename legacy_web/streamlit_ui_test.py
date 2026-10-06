from pathlib import Path
from streamlit.testing.v1 import AppTest
APP=str(Path(__file__).resolve().parents[1]/'app.py')

def test_navigation():
    at=AppTest.from_file(APP,default_timeout=30).run()
    assert not at.exception
    for page in ['Construction','Cryptographic Analysis','Benchmark Comparison','Logic Circuits','Image Encryption','Experiments','Affine Exploration']:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, (page,at.exception)

def test_demo_round_trip_and_experiment():
    at=AppTest.from_file(APP,default_timeout=60).run()
    at.sidebar.radio[0].set_value('Image Encryption').run()
    at.button[0].click().run();assert not at.exception
    assert at.session_state['image_run']['recovery']['exact']
    at.sidebar.radio[0].set_value('Experiments').run()
    for widget in at.number_input:
        if widget.label in ['Plaintext trials','Key trials']:widget.set_value(2)
        if widget.label=='Warm-up runs':widget.set_value(0)
        if widget.label=='Timing repetitions':widget.set_value(2)
    at.button[0].click().run();assert not at.exception
    assert at.session_state['batch']['rows'][0]['exact_recovery']
