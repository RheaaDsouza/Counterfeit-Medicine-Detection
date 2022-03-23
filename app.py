from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
import time
from PIL import Image
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, redirect, request, session, url_for,send_from_directory
from firebase_admin import credentials, firestore, initialize_app
import pyrebase
import os
from firebase_admin import auth
import json


app = Flask(__name__)
####################################
# Azure stuff integration here
subscription_key = os.getenv('subscription_key')
endpoint = os.getenv('endpoint')
computervision_client = ComputerVisionClient(endpoint,CognitiveServicesCredentials(subscription_key))


dirname = os.path.dirname(__file__)

def read_local(read):
    # Call API with image and raw response (allows you to get the operation location)
    read_response = computervision_client.read_in_stream(read, raw=True)
    # Get the operation location (URL with ID as last appendage)
    read_operation_location = read_response.headers["Operation-Location"]
    # Take the ID off and use to get results
    operation_id = read_operation_location.split("/")[-1]

    # Call the "GET" API and wait for the retrieval of the results
    while True:
        read_result = computervision_client.get_read_result(operation_id)
        if read_result.status.lower () not in ['notstarted', 'running']:
            break
        
        time.sleep(5)
    l=[]
    if read_result.status == OperationStatusCodes.succeeded:
        
        for text_result in read_result.analyze_result.read_results:
            for line in text_result.lines:
                l.append(line.text)
    result=(' '.join(l))
    return result

#using pyrebase
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
    # Initialize Firestore DB using firebase admin
    cred = credentials.Certificate('key.json')
    default_app = initialize_app(cred)
    db = firestore.client()

    #Note: Use of CollectionRef stream() is prefered to get()
    docs = db.collection("meds").where("manufacturer", "==", "Zydus").stream()
    '''
    for doc in docs:
        print(f"{doc.id} => {doc.to_dict()}")
    '''
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
        if email is None or password is None:
            return {'message': 'Error missing email or password'},400
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

@app.route("/upload", methods = ['GET', 'POST'])
def get_out():
    if request.method == 'POST':
        file = request.files['i_remote']
        
        #read image file string data
    result = read_local(file)
    print(file)
    image = Image.open(file)
    return render_template("home.html", prediction = result ,img_path=image )

if __name__ == "__main__":
    app.run(debug=True)