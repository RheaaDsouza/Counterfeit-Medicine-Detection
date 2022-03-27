from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
import time

from dotenv import load_dotenv
load_dotenv()
from werkzeug.utils import secure_filename
from flask import Flask, render_template, redirect, request, session, url_for,send_from_directory,flash
from firebase_admin import credentials, firestore, initialize_app
import pyrebase
import os
from firebase_admin import auth
import json


#####obj det import here
import sys
import numpy as np
import tensorflow as tf
from PIL import Image
from inferenceutils import *

sys.path.append("..")
from object_detection.utils import label_map_util
from object_detection.utils import visualization_utils as vis_util
tf.config.set_visible_devices([], 'GPU')

# from utils import visualization_utils as vis_util
MODEL_NAME = r'C:\Users\Rhea\Desktop\Final\ssd_mobilenet_v2_fpnlite_320x320_coco17'
PATH_TO_CKPT = r'C:\Users\Rhea\Desktop\Final\ssd_mobilenet_v2_fpnlite_320x320_coco17\saved_model'
PATH_TO_LABELS = os.path.join('data', 'label_mapssdv2fpn320_5.pbtxt')
NUM_CLASSES = 22

category_index = label_map_util.create_category_index_from_labelmap(PATH_TO_LABELS, use_display_name=True)
tf.keras.backend.clear_session()
model = tf.saved_model.load(PATH_TO_CKPT)
####################################

app = Flask(__name__)

app.config['OBJ_FOLDER']='static/objdetImages/'
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.config['ALLOWED_EXTENSIONS'] = set(['png', 'jpg', 'jpeg'])


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']

####################################
# Azure stuff integration here
subscription_key = os.getenv('subscription_key')
endpoint = os.getenv('endpoint')
computervision_client = ComputerVisionClient(endpoint,CognitiveServicesCredentials(subscription_key))


dirname = os.path.dirname(__file__)

'''
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
''' 

#########################
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
    return render_template('home.html')

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
    '''
    #Note: Use of CollectionRef stream() is prefered to get()
    docs = db.collection("meds").where("manufacturer", "==", "Zydus").stream()
    
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
def upload():
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        #return render_template('home.html', filename="/uploads/"+filename)
        return redirect(url_for('uploaded_file',filename=filename))
    '''
    if request.method == 'POST':
        file = request.files['i_remote']
        #read image file string data
    result = read_local(file)
    return render_template("home.html", prediction = result)
    '''

@app.route('/<filename>')
def uploaded_file(filename):
    PATH_TO_TEST_IMAGES_DIR = app.config['UPLOAD_FOLDER']
    TEST_IMAGE_PATHS = [os.path.join(PATH_TO_TEST_IMAGES_DIR, filename.format(i)) for i in range(1, 2)]
    IMAGE_SIZE = (12, 8)

    for image_path in TEST_IMAGE_PATHS:
        image_np = load_image_into_numpy_array(image_path)
        output_dict = run_inference_for_single_image(model, image_np)
        vis_util.visualize_boxes_and_labels_on_image_array(image_np,
        output_dict['detection_boxes'],
        output_dict['detection_classes'],
        output_dict['detection_scores'],
        category_index,
        instance_masks=output_dict.get('detection_masks_reframed', None),
        use_normalized_coordinates=True,
        max_boxes_to_draw=5,
        min_score_thresh=.7,
        line_thickness=5)
        display(Image.fromarray(image_np))
        im = Image.fromarray(image_np)
        #im.save('objdetImages/' + filename)
        im.save( os.path.join(app.config['OBJ_FOLDER'], filename))
        im_path= os.path.join(app.config['OBJ_FOLDER'], filename)
        print(os.path.join(app.config['OBJ_FOLDER'], filename))
        #return send_from_directory('uploads/',filename)
        return render_template("home.html" , filename="uploads/"+filename, result=im_path)
        # return render_template("home.html" , filename="uploads/"+filename, result=im_path)
'''
@app.route('/uploaded')
def uploaded_file(filename):
    PATH_TO_TEST_IMAGES_DIR = app.config['UPLOAD_FOLDER']
    TEST_IMAGE_PATHS = [os.path.join(PATH_TO_TEST_IMAGES_DIR, filename.format(i)) for i in range(1, 2)]
    IMAGE_SIZE = (12, 8)

    for image_path in TEST_IMAGE_PATHS:
        image_np = load_image_into_numpy_array(image_path)
        output_dict = run_inference_for_single_image(model, image_np)
        vis_util.visualize_boxes_and_labels_on_image_array(
        image_np,
        output_dict['detection_boxes'],
        output_dict['detection_classes'],
        output_dict['detection_scores'],
        category_index,
        instance_masks=output_dict.get('detection_masks_reframed', None),
        use_normalized_coordinates=True,
        max_boxes_to_draw=5,
        min_score_thresh=.7,
        line_thickness=5)
        display(Image.fromarray(image_np))
        im = Image.fromarray(image_np)
        im.save('uploads/' + filename)
    img_path= app.config['UPLOAD_FOLDER']+filename
    #return send_from_directory("/upload", img_path)
    return render_template("uploaded.html",img_path=img_path)
'''
    
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
    
