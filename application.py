from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir
from decimal import *



from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    # query transaction table
    transactions = db.execute("SELECT symbol, SUM(shares) FROM transactions \
                   WHERE user_id=:user_id GROUP BY symbol", user_id=session["user_id"])
    # total user account balance
    grand_total = 0
    
    # iterate transaction rows
    for transaction in transactions:
        # lookup current stock info and add to transaction dict
        stock_info = lookup(transaction["symbol"])
        transaction.update(stock_info)
        # add total key to transaction
        transaction["total"] = transaction["price"] * transaction["SUM(shares)"]
        grand_total += transaction["total"]

    # lookup current cash balance
    cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    # add cash to grand total
    grand_total += cash[0]["cash"]

    return render_template("index.html", rows=transactions, cash=cash[0]["cash"], grand_total=grand_total)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
   
    # submit buy request
    if request.method == "POST":
        
        symbol = request.form.get("symbol").upper()
        # ensure shares is number
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("Invalid shares")
        # ensure inputs are filled in
        if not symbol:
            return apology("Missing stock symbol")
        if not shares > 0:
            return apology("Invalid shares amount")
        
        # lookup current cash balance
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        
        # get current stock price
        stock = lookup(symbol)
        
        if stock == None:
            return apology("Invalid symbol")
        
        # check if user has enough cash to purchase stocks
        user_cash = cash[0]["cash"]
        total_price = stock["price"] * shares
        
        # insufficient funds
        if user_cash < (total_price):
            return apology("Insufficient Funds")
        # purchase shares
        else:
            # update transaction table
            db.execute("INSERT INTO transactions (user_id, symbol, price, shares) VALUES \
                      (:user_id, :symbol, :price, :shares)", user_id=session["user_id"], 
                      symbol=stock["symbol"], price=stock["price"], shares=shares)
            
            # update user's cash
            db.execute("UPDATE users SET cash = cash - :price WHERE id=:id", 
                      price=total_price, id=session["user_id"])
            
            flash("Shares bought!")
            return redirect(url_for("index"))
    
    # GET route   
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    
    transactions = db.execute("SELECT * FROM transactions WHERE user_id=:user_id ORDER BY time",
                             user_id = session["user_id"])
    print(transactions)
    
    return render_template("history.html", rows=transactions)
    
    


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        flash('Logged in')
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    # on form submit
    if request.method == "POST":
       
        # validate registration fields
        if not request.form.get("username"):
            return apology("missing username")
            
        elif not request.form.get("password"):
            return apology("missing password")
            
        elif request.form.get("password") != request.form.get("confirm"):
            return apology("password mismatch")
        
        # query user database      
        usercheck = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        
        # check if username in database
        if len(usercheck) > 0:
            return apology("username taken :(")
        else:
            # creates db recort for user
            new_user = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", 
                          username=request.form.get("username"), hash = pwd_context.hash(request.form.get("password")))
            
            # rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
            session["user_id"] = new_user
            
            # send to login page and notify registration successful
            flash('Registration successful. Logged in')
            return redirect(url_for("index"))
            
    
    # GET route to page
    else:
        return render_template("register.html")


@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # form submit
    if request.method == "POST":
        # ensure stock symbol entered
        if not request.form.get("symbol"):
            return apology("Missing stock symbol")
        else:
            # lookup stock symbol from yahoo finance
            stock = lookup(request.form.get("symbol"))
           
            # check if stock is valid
            if stock == None:
                return apology("Invalid stock symbol")
            
            # show stock quote page
            return render_template("quoted.html", stock=stock)
    else:
        return render_template("quote.html")
    

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    
    # submit sell request
    if request.method == "POST":
        
        symbol = request.form.get("symbol").upper()
        # ensure shares is number
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("Invalid shares", "Enter a number")
        # ensure inputs are filled in
        if not symbol:
            return apology("Missing stock symbol")
        if not shares > 0:
            return apology("Invalid shares amount")
        # get current stock price
        stock = lookup(symbol)
        
        if stock == None:
            return apology("Invalid symbol")
            
        # lookup user's current shares
        transactions = db.execute("SELECT SUM(shares) FROM transactions WHERE \
                       user_id=:user_id AND symbol=:symbol", user_id=session["user_id"], symbol=symbol)
        
        # error handling if shares not owned 
        if len(transactions) == 0:
            return apology("Symbol not owned")
        if transactions[0]["SUM(shares)"] < shares:
            return apology("Too many shares")
         
        # total sale price   
        total_price = stock["price"] * shares
        
        # update transaction table
        db.execute("INSERT INTO transactions (user_id, symbol, price, shares) VALUES \
                 (:user_id, :symbol, :price, :shares)", user_id=session["user_id"], symbol=stock["symbol"],
                 price=stock["price"], shares=-shares)
        # update user's cash
        db.execute("UPDATE users SET cash = cash + :price WHERE id=:id", 
                  price=total_price, id=session["user_id"])
        
        flash("Shares sold!")
        return redirect(url_for("index"))
    
    # GET route   
    else:
        return render_template("sell.html")
        
        

@app.route("/funding", methods=["GET", "POST"])
@login_required
def funding():
    """Deposit/ withdrawal cash"""
    
    # get current cash balance
    db_cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    
    current_cash = db_cash[0]["cash"]
    
    
    # form submit
    if request.method == "POST":
       
        # deposit button pressed
        if "deposit-submit" in request.form:
            
            # handle invalid inputs
            try:
                dep_amount = float(request.form.get("deposit"))
            except ValueError:
                return apology("Invalid Deposit Amount")
            if not dep_amount > 0:
                return apology("Invalid Deposit Amount")
                
            # update cash field in users table    
            db_update = db.execute("UPDATE users SET cash = cash + :dep_amount WHERE id=:id", 
                      dep_amount=dep_amount, id=session["user_id"])
            # return error if db update fails
            if db_update == None or db_update == RuntimeError:
                return apology("DB on fire", "Please Help")

            # flash success message
            flash("${:,.2f} Deposited!".format(dep_amount))
            return redirect(url_for("funding"))
                
                
        # withdrawal button pressed
        elif "withdrawal-submit" in request.form:
            
            # handle invalid inputs
            try:
                with_amount = float(request.form.get("withdrawal"))
            except ValueError:
                return apology("Invalid Withdrawal Amount")
            if not with_amount > 0:
                return apology("Invalid Withdrawal Amount")
                
            
            # set Decimal precision to 2 places
            getcontext().prec = 2
            # check if withdrawal amount greater than current cash
            if Decimal(with_amount).compare(Decimal(current_cash)) > 0: 
                return apology("You don't have the cash")
            
            # update cash field in users table    
            db_update = db.execute("UPDATE users SET cash = cash - :with_amount WHERE id=:id", 
                      with_amount=with_amount, id=session["user_id"])
            # return error if db update fails
            if db_update == None or db_update == RuntimeError:
                return apology("DB on fire", "Please Help")
            
            # flash success message
            flash("${:,.2f} Withdrawn!".format(with_amount))
            return redirect(url_for("funding"))
    
    
    # GET route
    else:
        return render_template("funding.html", current_cash=current_cash)