from flask import Flask, render_template, request
app = Flask(__name__)
@app.route("/")
def index():
    """Home page with links to register or login."""
    return render_template("index.html")

@app.route("/add", methods=["POST"])
def add():
    number1 = request.form.get("number1")
    number2 = request.form.get("number2")

    # Validate and convert to float (accept integers or floats)
    try:
        a = float(number1)
        b = float(number2)
    except (TypeError, ValueError):
        flash('Please enter valid numeric values for both fields.')
        return render_template('result.html', result='Invalid input')

    ans = a + b

    # Store a small history of calculations in the session (last 10)
    hist = session.get('history', [])
    hist.insert(0, f"{a} + {b} = {ans}")
    session['history'] = hist[:10]

    return render_template("result.html", result=ans)

from flask import redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

"""Simple study hub Flask app with minimal auth.

This file implements a very small study hub where users can
register, log in, view a dashboard, and log out. It uses an
in-memory user store (a dict) and Werkzeug password hashing for
demonstration purposes only. For production use a database is
required.
"""

# Flask application setup
app.secret_key = 'dev-secret-key'

# In-memory user store: {username: {password: <hashed>, ...}}
users = {}

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register a new user.

    POST: validate form, create a new user with a hashed password
    and redirect to the login page.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Username and password are required.')
            return redirect(url_for('register'))

        if username in users:
            flash('Username already exists. Choose another one.')
            return redirect(url_for('register'))

        # Hash the password before storing it
        users[username] = {'password': generate_password_hash(password)}
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Authenticate a user and create a session."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = users.get(username)
        if user and check_password_hash(user['password'], password):
            # Successful login: store username in session
            session['username'] = username
            flash('Logged in successfully.')
            return redirect(url_for('dashboard'))

        flash('Invalid username or password.')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """A simple protected dashboard view.

    This checks for a username in the session and displays a
    personalized welcome message. In a real app you'd protect
    endpoints with decorators and check permissions.
    """
    username = session.get('username')
    if not username:
        flash('Please log in to access the dashboard.')
        return redirect(url_for('login'))

    return render_template('dashboard.html', username=username)

@app.route('/logout')
def logout():
    """Clear the user's session and redirect to home."""
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)