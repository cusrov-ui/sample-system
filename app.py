"""
app.py - Study Hub backend

Primary author: Adrian De Vera (Backend / API)
"""

import sqlite3
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = 'study_hub.db'

app = Flask(__name__)
app.secret_key = 'dev-secret-key'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    cur = db.cursor()
    # users, studies, games
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS studies (
        id TEXT PRIMARY KEY,
        username TEXT,
        name TEXT,
        description TEXT,
        schedule TEXT,
        public INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS games (
        id TEXT PRIMARY KEY,
        username TEXT,
        owner_id TEXT,
        board TEXT,
        turn TEXT,
        status TEXT,
        opponent TEXT DEFAULT 'human',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS study_members (
        study_id TEXT,
        username TEXT,
        status TEXT DEFAULT 'approved',
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (study_id, username)
    );
    ''')
    db.commit()

    # Ensure columns exist (for older DBs) - rudimentary migration
    cols = [r['name'] for r in db.execute("PRAGMA table_info(studies)").fetchall()]
    if 'description' not in cols:
        db.execute('ALTER TABLE studies ADD COLUMN description TEXT')
    if 'schedule' not in cols:
        db.execute('ALTER TABLE studies ADD COLUMN schedule TEXT')
    if 'public' not in cols:
        db.execute('ALTER TABLE studies ADD COLUMN public INTEGER DEFAULT 0')
    # games opponent column migration
    game_cols = [r['name'] for r in db.execute("PRAGMA table_info(games)").fetchall()]
    if 'opponent' not in game_cols:
        try:
            db.execute("ALTER TABLE games ADD COLUMN opponent TEXT DEFAULT 'human'")
        except Exception:
            pass
    if 'owner_id' not in game_cols:
        try:
            db.execute("ALTER TABLE games ADD COLUMN owner_id TEXT")
        except Exception:
            pass
    # ensure study_members has status column
    member_cols = [r['name'] for r in db.execute("PRAGMA table_info(study_members)").fetchall()]
    if 'status' not in member_cols:
        try:
            db.execute("ALTER TABLE study_members ADD COLUMN status TEXT DEFAULT 'approved'")
        except Exception:
            pass
    db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def _serialize_board(board):
    return ','.join(board)


def _deserialize_board(s):
    if s is None or s == '':
        return ['']*9
    return s.split(',')


# Initialize DB now inside an application context (safer across Flask versions)
with app.app_context():
    init_db()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/play')
def play():
    # enforce login to access play page (nav already hides link but this is strict protection)
    if not session.get('username'):
        flash('Please log in to access Play')
        return redirect(url_for('login'))
    return render_template('play.html')


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Username and password required')
            return redirect(url_for('register'))
        db = get_db()
        cur = db.execute('SELECT username FROM users WHERE username=?', (username,))
        if cur.fetchone():
            flash('Username already exists')
            return redirect(url_for('register'))
        db.execute('INSERT INTO users(username,password) VALUES(?,?)', (username, generate_password_hash(password)))
        db.commit()
        flash('Registration successful')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        db = get_db()
        cur = db.execute('SELECT username,password FROM users WHERE username=?', (username,))
        row = cur.fetchone()
        if row and check_password_hash(row['password'], password):
            session['username'] = username
            flash('Logged in successfully')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Logged out')
    return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    username = session.get('username')
    if not username:
        flash('Please log in')
        return redirect(url_for('login'))
    db = get_db()
    # owned studies (include pending member count)
    cur = db.execute('''SELECT s.id,s.name,s.description,s.schedule,s.public,s.created_at,
                        (SELECT COUNT(*) FROM study_members m WHERE m.study_id=s.id AND m.status='pending') AS pending_count
                        FROM studies s WHERE s.username=? ORDER BY s.created_at DESC LIMIT 50''', (username,))
    owned = cur.fetchall()
    # joined studies
    cur = db.execute('''SELECT s.id,s.name,s.description,s.schedule,s.public,s.created_at
                        FROM studies s JOIN study_members m ON s.id=m.study_id
                        WHERE m.username=? ORDER BY m.joined_at DESC LIMIT 50''', (username,))
    joined = cur.fetchall()
    return render_template('dashboard.html', username=username, owned=owned, joined=joined)


@app.route('/add', methods=['POST'])
def add():
    # Create a study (advanced fields)
    name = request.form.get('study_name','').strip()
    description = request.form.get('description','').strip()
    schedule = request.form.get('schedule','').strip()
    public = 1 if request.form.get('public') == 'on' else 0
    if not name:
        flash('Study name is required')
        return redirect(url_for('dashboard'))
    username = session.get('username')
    db = get_db()
    if username:
        sid = str(uuid.uuid4())
        db.execute('INSERT INTO studies(id,username,name,description,schedule,public) VALUES(?,?,?,?,?,?)', (sid, username, name, description, schedule, public))
        db.commit()
        # auto-join creator
        db.execute('INSERT OR IGNORE INTO study_members(study_id,username) VALUES(?,?)', (sid, username))
        db.commit()
        # If client expects JSON (AJAX), return JSON object; otherwise redirect
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'id': sid, 'name': name, 'description': description, 'schedule': schedule, 'public': bool(public), 'pending_count': 0})
        flash('Study created')
        return redirect(url_for('dashboard'))
    flash('You must be logged in to create a study')
    return redirect(url_for('login'))


@app.route('/clear_history', methods=['POST'])
def clear_history():
    session.pop('studies', None)
    flash('Recent studies cleared')
    return redirect(url_for('index'))


@app.route('/study/<study_id>/join', methods=['POST'])
def join_study(study_id):
    username = session.get('username')
    if not username:
        return jsonify({'error':'login required'}), 401
    db = get_db()
    # check study public flag
    cur = db.execute('SELECT public,username FROM studies WHERE id=?', (study_id,))
    s = cur.fetchone()
    if not s:
        return jsonify({'error':'not found'}), 404
    if s['public']:
        db.execute('INSERT OR IGNORE INTO study_members(study_id,username,status) VALUES(?,?,?)', (study_id, username, 'approved'))
        db.commit()
        return jsonify({'status':'joined'})
    # private study => create pending request
    db.execute('INSERT OR IGNORE INTO study_members(study_id,username,status) VALUES(?,?,?)', (study_id, username, 'pending'))
    db.commit()
    return jsonify({'status':'pending'})


@app.route('/study/<study_id>/leave', methods=['POST'])
def leave_study(study_id):
    username = session.get('username')
    if not username:
        return jsonify({'error':'login required'}), 401
    db = get_db()
    db.execute('DELETE FROM study_members WHERE study_id=? AND username=?', (study_id, username))
    db.commit()
    return jsonify({'status':'left'})


@app.route('/study/<study_id>/members')
def study_members(study_id):
    # only owner can view/manage
    username = session.get('username')
    if not username:
        return jsonify({'error':'login required'}), 401
    db = get_db()
    cur = db.execute('SELECT username,status,joined_at FROM study_members WHERE study_id=?', (study_id,))
    rows = cur.fetchall()
    out = [{'username':r['username'],'status':r['status'],'joined_at':r['joined_at']} for r in rows]
    return jsonify(out)


@app.route('/study/<study_id>/approve', methods=['POST'])
def approve_member(study_id):
    owner = session.get('username')
    if not owner:
        return jsonify({'error':'login required'}), 401
    username = request.form.get('username')
    db = get_db()
    cur = db.execute('SELECT username FROM studies WHERE id=?', (study_id,))
    r = cur.fetchone()
    if not r or r['username'] != owner:
        return jsonify({'error':'not authorized'}), 403
    db.execute('UPDATE study_members SET status=? WHERE study_id=? AND username=?', ('approved', study_id, username))
    db.commit()
    return jsonify({'status':'approved'})


@app.route('/study/<study_id>/deny', methods=['POST'])
def deny_member(study_id):
    owner = session.get('username')
    if not owner:
        return jsonify({'error':'login required'}), 401
    username = request.form.get('username')
    db = get_db()
    cur = db.execute('SELECT username FROM studies WHERE id=?', (study_id,))
    r = cur.fetchone()
    if not r or r['username'] != owner:
        return jsonify({'error':'not authorized'}), 403
    db.execute('DELETE FROM study_members WHERE study_id=? AND username=?', (study_id, username))
    db.commit()
    return jsonify({'status':'denied'})


@app.route('/study/<study_id>/delete', methods=['POST'])
def delete_study(study_id):
    username = session.get('username')
    if not username:
        flash('login required')
        return redirect(url_for('login'))
    db = get_db()
    # only owner can delete
    cur = db.execute('SELECT username FROM studies WHERE id=?', (study_id,))
    r = cur.fetchone()
    if not r or r['username'] != username:
        flash('Not authorized')
        return redirect(url_for('dashboard'))
    db.execute('DELETE FROM studies WHERE id=?', (study_id,))
    db.execute('DELETE FROM study_members WHERE study_id=?', (study_id,))
    db.commit()
    flash('Study deleted')
    return redirect(url_for('dashboard'))


@app.route('/api/studies/search')
def api_search_studies():
    q = request.args.get('q','').strip()
    db = get_db()
    if q:
        rows = db.execute("SELECT id,name,description,schedule,public FROM studies WHERE public=1 AND (name LIKE ? OR description LIKE ?) LIMIT 50", (f'%{q}%', f'%{q}%')).fetchall()
    else:
        rows = db.execute('SELECT id,name,description,schedule,public FROM studies WHERE public=1 ORDER BY created_at DESC LIMIT 50').fetchall()
    out = []
    for r in rows:
        out.append({'id':r['id'],'name':r['name'],'description':r['description'],'schedule':r['schedule'],'public':bool(r['public'])})
    return jsonify(out)


@app.route('/api/owned_studies')
def api_owned_studies():
    username = session.get('username')
    if not username:
        return jsonify({'error':'login required'}), 401
    db = get_db()
    rows = db.execute('''SELECT s.id,s.name,s.description,s.schedule,s.public,
                         (SELECT COUNT(*) FROM study_members m WHERE m.study_id=s.id AND m.status='pending') AS pending_count
                         FROM studies s WHERE s.username=? ORDER BY s.created_at DESC LIMIT 100''', (username,)).fetchall()
    out = []
    for r in rows:
        out.append({'id': r['id'], 'name': r['name'], 'description': r['description'], 'schedule': r['schedule'], 'public': bool(r['public']), 'pending_count': r['pending_count']})
    return jsonify(out)


### Games API using DB

@app.route('/api/games', methods=['GET'])
def api_list_games():
    username = session.get('username')
    if not username:
        return jsonify({'error':'login required'}), 401
    db = get_db()
    cur = db.execute('SELECT id,board,turn,status FROM games WHERE username=? ORDER BY created_at DESC', (username,))
    rows = cur.fetchall()
    out = []
    for r in rows:
        out.append({'id': r['id'], 'board': _deserialize_board(r['board']), 'turn': r['turn'], 'status': r['status']})
    return jsonify(out)


@app.route('/api/games', methods=['POST'])
def api_create_game():
    # allow anonymous creation: use session username if present, otherwise owner_id
    username = session.get('username')
    owner_id = username or session.get('actor_id')
    if not owner_id:
        # create random actor id and store in session
        owner_id = str(uuid.uuid4())
        session['actor_id'] = owner_id
    gid = str(uuid.uuid4())
    board = _serialize_board(['']*9)
    opponent = request.args.get('opponent') or request.json and request.json.get('opponent') or 'human'
    db = get_db()
    db.execute('INSERT INTO games(id,username,owner_id,board,turn,status,opponent) VALUES(?,?,?,?,?,?,?)', (gid, username, owner_id, board, 'X', 'playing', opponent))
    db.commit()
    return jsonify({'id': gid, 'game': {'board': ['']*9, 'turn': 'X', 'status': 'playing', 'opponent': opponent}})


@app.route('/api/games/<gid>', methods=['GET'])
def api_get_game(gid):
    username = session.get('username')
    db = get_db()
    if username:
        cur = db.execute('SELECT id,board,turn,status,opponent FROM games WHERE id=? AND username=?', (gid, username))
        r = cur.fetchone()
    else:
        owner_id = session.get('actor_id')
        cur = db.execute('SELECT id,board,turn,status,opponent FROM games WHERE id=? AND owner_id=?', (gid, owner_id))
        r = cur.fetchone()
    if not r:
        return jsonify({'error':'not found'}), 404
    return jsonify({'id': r['id'], 'game': {'board': _deserialize_board(r['board']), 'turn': r['turn'], 'status': r['status']}})


@app.route('/api/games/<gid>', methods=['DELETE'])
def api_delete_game(gid):
    username = session.get('username')
    db = get_db()
    if username:
        cur = db.execute('DELETE FROM games WHERE id=? AND username=?', (gid, username))
    else:
        owner_id = session.get('actor_id')
        cur = db.execute('DELETE FROM games WHERE id=? AND owner_id=?', (gid, owner_id))
    db.commit()
    if cur.rowcount:
        return jsonify({'status':'deleted'})
    return jsonify({'error':'not found'}), 404


@app.route('/api/games/<gid>/move', methods=['POST'])
def api_move(gid):
    username = session.get('username')
    if not username:
        return jsonify({'error':'login required'}), 401
    data = request.get_json() or {}
    pos = data.get('pos')
    try:
        pos = int(pos)
    except Exception:
        return jsonify({'error':'invalid pos'}), 400
    if pos < 0 or pos > 8:
        return jsonify({'error':'invalid pos'}), 400

    db = get_db()
    # prefer match by username if present, otherwise try owner_id
    if username:
        cur = db.execute('SELECT board,turn,status,opponent,owner_id FROM games WHERE id=? AND username=?', (gid, username))
        r = cur.fetchone()
    else:
        owner_id = session.get('actor_id')
        cur = db.execute('SELECT board,turn,status,opponent,owner_id FROM games WHERE id=? AND owner_id=?', (gid, owner_id))
        r = cur.fetchone()
    if not r:
        return jsonify({'error':'not found'}), 404
    board = _deserialize_board(r['board'])
    if r['status'] != 'playing':
        return jsonify({'error':'game finished', 'status': r['status']}), 400
    if board[pos]:
        return jsonify({'error':'cell occupied'}), 400

    player = r['turn']
    board[pos] = player

    # check winner
    def check_winner(b):
        lines = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
        for a,b,c in lines:
            if b[a] and b[a] == b[b] == b[c]:
                return b[a]
        if all(b):
            return 'draw'
        return None

    winner = None
    # simple check implemented without nested shadowing
    lines = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in lines:
        if board[a] and board[a] == board[b] == board[c]:
            winner = board[a]
            break
    if winner:
        status = f'{winner}_wins'
    elif all(board):
        status = 'draw'
    else:
        status = 'playing'
        player = 'O' if player == 'X' else 'X'

    db.execute('UPDATE games SET board=?,turn=?,status=? WHERE id=? AND username=?', (_serialize_board(board), player, status, gid, username))
    db.commit()

    # If opponent is bot and game still playing, let bot move using minimax
    cur = db.execute('SELECT opponent,turn,status,board,owner_id FROM games WHERE id=?', (gid,))
    row = cur.fetchone()
    if row and row['opponent'] == 'bot' and row['status'] == 'playing':
        bot_player = row['turn']
        board_state = _deserialize_board(row['board'])

        # minimax implementation
        def minimax(board, player):
            winner = check_winner(board)
            if winner == bot_player:
                return {'score': 1}
            elif winner == ('draw'):
                return {'score': 0}
            elif winner is not None:
                return {'score': -1}

            moves = []
            for i in range(9):
                if board[i] == '':
                    move = {}
                    board[i] = player
                    next_player = 'O' if player == 'X' else 'X'
                    result = minimax(board, next_player)
                    move['index'] = i
                    move['score'] = result['score']
                    board[i] = ''
                    moves.append(move)

            # choose best move
            if player == bot_player:
                best = max(moves, key=lambda m: m['score'])
            else:
                best = min(moves, key=lambda m: m['score'])
            return best

        # if board empty and bot starts, choose center
        empties = [i for i,v in enumerate(board_state) if v=='']
        if len(empties) == 9 and bot_player == 'X':
            mv = 4
        else:
            res = minimax(board_state, bot_player)
            mv = res.get('index') if res else None

        if mv is not None:
            board_state[mv] = bot_player
            winner2 = check_winner(board_state)
            if winner2 == 'draw':
                status2 = 'draw'
            elif winner2:
                status2 = f'{winner2}_wins'
            else:
                status2 = 'playing'
            next_turn = 'O' if bot_player == 'X' else 'X'
            db.execute('UPDATE games SET board=?,turn=?,status=? WHERE id=?', (_serialize_board(board_state), next_turn, status2, gid))
            db.commit()
            return jsonify({'id': gid, 'game': {'board': board_state, 'turn': next_turn, 'status': status2}})

    return jsonify({'id': gid, 'game': {'board': board, 'turn': player, 'status': status}})


@app.route('/admin/clear', methods=['POST'])
def admin_clear():
    username = session.get('username')
    if username != 'admin':
        return jsonify({'error':'admin required'}), 403
    db = get_db()
    db.execute('DELETE FROM games')
    db.execute('DELETE FROM studies')
    db.execute('DELETE FROM study_members')
    db.commit()
    return jsonify({'status':'cleared'})


if __name__ == '__main__':
    app.run(debug=True)