import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, make_response
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    userid = session["user_id"]
    # get data from database
    row = db.execute("SELECT cash FROM users WHERE id = ?", userid)
    portfolio_db = db.execute(
        "SELECT symbol,shares FROM portfolio WHERE user_id = ?", userid)
    cash = row[0]["cash"]
    current_mp = {}
    mkv = {}
    # iterate over every stock owned
    for stock in portfolio_db:
        # get current market price
        data = lookup(stock['symbol'].upper())
        mp = float(data['price'])
        # add to dictionary
        current_mp[stock['symbol']] = mp
        # calculate market value of the stock
        mkv[stock['symbol']] = mp * stock['shares']
    total = float(sum(mkv.values()))

    return render_template("index.html", portfolio=portfolio_db, current_mp=current_mp, value=mkv, total=total, cash=cash, pfval=total + float(cash))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # check empty fields
        stock = request.form.get('symbol')
        shares = float(request.form.get('shares'))
        if not stock or not shares or shares <= 0 or shares == " ":
            return apology('stop submitting empty field')

        data = lookup(stock.upper())

        # if none return
        if data == None:
            return apology("enter correct data", 400)
        # return data
        userid = session["user_id"]
        row = db.execute("SELECT cash FROM users WHERE id = ?", userid)

        name = data['name']
        price = float(data['price'])
        symbol = data['symbol']
        cash = float(row[0]["cash"])
        transaction_value = price * shares
        date = datetime.datetime.now()
        t_type = "BUY"
        # #check purchasing power
        if transaction_value > cash:
            return apology("you're broke", 400)
        # update database
        # transaction database
        db.execute("INSERT INTO transactions (user_id,symbol,shares,price,type,date) VALUES (?,?,?,?,?,?)",
                   userid, symbol, shares, price, t_type, date)
        # cash database
        updated_cash = cash - transaction_value
        db.execute("UPDATE users SET cash = ? WHERE id = ?",
                   updated_cash, userid)
        # portfolio database
        rows = db.execute(
            "SELECT * FROM portfolio WHERE user_id = ? AND symbol = ?", userid, symbol)
        # if stock is not in portfolio
        if len(rows) != 1:
            db.execute(
                "INSERT INTO portfolio (user_id,symbol,shares) VALUES (?,?,?)", userid, symbol, shares)
            return redirect("/")
        # if stock is in portfolio
        else:
            row = db.execute(
                "SELECT shares FROM portfolio WHERE user_id = ? AND symbol = ?", userid, symbol)
            share_in_hand = row[0]["shares"]
            new_shares = share_in_hand + shares
            # update no of shares
            db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ? ",
                       new_shares, userid, symbol)
            return redirect("/")

    else:  # if user came via get
        userid = session["user_id"]
        row = db.execute("SELECT cash FROM users WHERE id = ?", userid)
        return render_template('buy.html', cash=row[0]["cash"])


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    try:
        userid = session["user_id"]
        data = db.execute(
            "SELECT date,type,symbol,shares,price FROM transactions WHERE user_id = ?", userid)
    except:
        return apology("try again later", 500)
    else:
        return render_template("history.html", transactions=data)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # check for empty fields
        ticker = request.form.get("symbol")
        if not ticker:
            return apology("stop submitting empty field")
        # lookup the stock quote
        stock = lookup(ticker.upper())

        # if none return
        if stock == None:
            return apology("check your input", 400)
        # return data
        name = stock['name']
        price = stock['price']
        symbol = stock['symbol']

        return render_template('quoted.html', name=name, price=price, symbol=symbol)

    # if user came through get
    else:
        return render_template('quote.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # if user reached via post request ie submitted a form
    if request.method == "POST":
        # get all the submitted data
        username = request.form.get("username")
        password = request.form.get("password")
        password2 = request.form.get("confirmation")
        # check for blank fields
        if not username or not password or not password2:
            return apology("Empty Field resubmit the form", 400)

        # check for password mismatch
        if password != password2:
            return apology("Please enter same password in both fields")
        # check for already taken username
        row = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(row) > 0:
            return apology("Username already taken", 400)

        # after all checks update user in database
        hashed = generate_password_hash(password)
        try:
            db.execute(
                "INSERT INTO users (username,hash) VALUES (?,?)", username, hashed)
        except:
            return apology("Server Side Eror", 500)
        else:
            # get user id
            userid = db.execute(
                "SELECT id FROM users WHERE username = ?", username)
            # save user in session
            session["user_id"] = userid
            return redirect('/login')
    # if user came via get request
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    userid = session["user_id"]
    if request.method == "GET":
        data = db.execute(
            "SELECT symbol FROM portfolio WHERE user_id = ?", userid)
        return render_template("sell.html", data=data)
    else:
        # check empty fields
        sell_symbol = request.form.get('symbol')
        sell_shares = float(request.form.get('shares'))
        if not sell_symbol or not sell_shares or sell_shares <= 0 or sell_shares == " ":
            return apology('stop submitting empty field')
        # check if user has stock and if user has shares more than sell order
        user_shares = db.execute(
            "SELECT shares FROM portfolio WHERE user_id=? AND symbol = ?", userid, sell_symbol)
        if len(user_shares) != 1 or sell_shares > float(user_shares[0]['shares']):
            return apology('Impossible Amount')

        # all data verified
        # lookup share price at Market
        data = lookup(sell_symbol.upper())
        # assign required variables
        row = db.execute("SELECT cash FROM users WHERE id = ?", userid)
        price = float(data['price'])
        transaction_val = sell_shares * price
        cash = float(row[0]["cash"])
        date = datetime.datetime.now()
        t_type = "SELL"
        # update transaction to database
        # transactions table
        db.execute("INSERT INTO transactions (user_id,symbol,shares,price,type,date) VALUES (?,?,?,?,?,?)",
                   userid, sell_symbol, sell_shares, price, t_type, date)
        # cash database
        updated_cash = cash + transaction_val
        db.execute("UPDATE users SET cash = ? WHERE id = ?",
                   updated_cash, userid)
        # portfolio database
        if user_shares[0]['shares'] == sell_shares:
            db.execute(
                "DELETE FROM portfolio WHERE user_id = ? AND symbol = ?", userid, sell_symbol)
        else:
            row = db.execute(
                "SELECT shares FROM portfolio WHERE user_id = ? AND symbol = ?", userid, sell_symbol)
            share_in_hand = row[0]["shares"]
            new_shares = share_in_hand - sell_shares
            # update no of shares
            db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND SYMBOL = ? ",
                       new_shares, userid, sell_symbol)

        return redirect('/')


@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    userid = session["user_id"]
    row = db.execute("SELECT cash FROM users WHERE id = ?", userid)
    cash_in_hand = float(row[0]["cash"])
    if request.method == "GET":
        return render_template("cash.html", cash_in_hand=cash_in_hand)
    else:
        amount = float(request.form.get('amount'))
        updated_cash = cash_in_hand + amount
        # update database
        db.execute("UPDATE users SET cash = ? WHERE id = ?",
                   updated_cash, userid)
        return redirect('/')
