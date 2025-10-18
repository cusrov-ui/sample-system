import os
import sys
import pytest

# ensure project root (parent folder) is on sys.path so tests can import app.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
import uuid

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

def test_register_login_add_list(client):
    # register
    uname = f"testuser_{uuid.uuid4().hex[:8]}"
    rv = client.post('/register', data={'username': uname, 'password': 'pw'}, follow_redirects=True)
    assert b'Registration successful' in rv.data

    # login
    rv = client.post('/login', data={'username': uname, 'password': 'pw'}, follow_redirects=True)
    assert b'Logged in successfully' in rv.data

    # add study
    rv = client.post('/add', data={'study_name': 'Math 101'}, follow_redirects=True)
    # server flash for create uses 'Study created'
    assert b'Study created' in rv.data

    # dashboard shows study
    rv = client.get('/dashboard')
    assert b'Math 101' in rv.data