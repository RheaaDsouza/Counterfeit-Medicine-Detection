from flask import Flask, render_template, redirect, request, session, url_for
from firebase_admin import credentials, firestore, initialize_app
import pyrebase
import os
from firebase_admin import auth

app = Flask(__name__)
config = {
  "apiKey": "your api key",
  "authDomain": "your domain",
  "databaseURL": "your database url",
  "storageBucket": "your storage bucket"
}

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()

#Initialze person as dictionary
person = {"is_logged_in": False, "name": "", "email": "", "uid": ""}


@app.route('/', methods=['GET','POST'])
def main():
    return render_template('index.html')

#Login
@app.route("/login")
def login():
    return render_template("login.html")

#Register
@app.route("/register")
def signup():
    return render_template("register.html")

#Homepage
@app.route("/home")
def home():
    if person["is_logged_in"] == True:
        return render_template("home.html", email = person["email"], name = person["name"])
    else:
        return redirect(url_for('login'))

#If someone clicks on login, they are redirected to /result
@app.route("/result", methods = ["POST", "GET"])
def result():
    if request.method == "POST":        
        result = request.form         
        email = result["email"]
        password = result["pass"]
        try:
            #signing in the user with the given information
            user = auth.sign_in_with_email_and_password(email, password)
            #Insert the user data in the global person
            global person
            person["is_logged_in"] = True
            person["email"] = user["email"]
            person["uid"] = user["localId"]
            #Get the name of the user
            data = db.child("users").get()
            person["name"] = data.val()[person["uid"]]["name"]
            #Redirect to home page
            return redirect(url_for('home'))
        except:
            #any error, redirect back to login
            return redirect(url_for('login'))
    else:
        if person["is_logged_in"] == True:
            return redirect(url_for('home'))
        else:
            return redirect(url_for('login'))

#If someone clicks on register, they are redirected to /register
@app.route("/register", methods = ["POST", "GET"])
def register():
    if request.method == "POST":       
        result = request.form          
        email = result["email"]
        password = result["pass"]
        name = result["name"]
        try:
            #creating the user account using the provided data
            auth.create_user_with_email_and_password(email, password)
            #Login the user
            user = auth.sign_in_with_email_and_password(email, password)
            #Add data to global person
            global person
            person["is_logged_in"] = True
            person["email"] = user["email"]
            person["uid"] = user["localId"]
            person["name"] = name
            #Append data to the firebase realtime database
            data = {"name": name, "email": email}
            db.child("users").child(person["uid"]).set(data)
            #Go to welcome page
            return redirect(url_for('home'))
        except:
            #any error, redirect to register
            return redirect(url_for('register'))

    else:
        if person["is_logged_in"] == True:
            return redirect(url_for('home'))
        else:
            return redirect(url_for('register'))

@app.route('/logout')
def logout():
    auth.current_user= None
    return redirect(url_for('main'))

if __name__ == "__main__":
    app.run(debug=True)