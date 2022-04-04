from msilib.schema import AdminExecuteSequence
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
import time

from dotenv import load_dotenv
load_dotenv()
from werkzeug.utils import secure_filename
from flask import Flask, render_template, redirect, request, session, url_for,send_from_directory,flash
import firebase_admin
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
import cv2
import pytesseract

pytesseract.pytesseract.tesseract_cmd = 'C:/Program Files/Tesseract-OCR/tesseract.exe'

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


#########################
#using pyrebase

config = {
  "apiKey": "AIzaSyCEmFlaiGKWWho6kZnxLPtVrK0IybTMjfM",
  "authDomain": "meddetection.firebaseapp.com",
  "databaseURL": "https://meddetection-default-rtdb.firebaseio.com",
  "storageBucket": "meddetection.appspot.com"
}


##################
#trying firebase-admin

#service account credentials
cred = credentials.Certificate('key.json')
#initializing the app
firebase = firebase_admin.initialize_app(cred)
db=firestore.client()

pb = pyrebase.initialize_app(config)
auth = pb.auth()
database= pb.database()



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
        if email is None or password is None:
            return {'message': 'Error missing email or password'},400
        try:
            #signing in the user with the given information
            user = auth.sign_in_with_email_and_password(email, password)
            print(user)
            #Insert the user data in the global person
            global person
            person["is_logged_in"] = True
            person["email"] = user["email"]
            person["uid"] = user["localId"]
            #Get the name of the user
            data = database.child("users").get()
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
            user = auth.create_user_with_email_and_password(email, password)
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
            database.child("users").child(person["uid"]).set(data)
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
        return redirect(url_for('uploaded_file',filename=filename))

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
        line_thickness=3)
        display(Image.fromarray(image_np))
        im = Image.fromarray(image_np)
        #im.save('objdetImages/' + filename)
        im.save( os.path.join(app.config['OBJ_FOLDER'], filename))
        im_path= os.path.join(app.config['OBJ_FOLDER'], filename)
        print(os.path.join(app.config['OBJ_FOLDER'], filename))
        
        label_id_offset =0
        ###additional code from jupter notebook
        # This is the way I'm getting my coordinates
        boxes = output_dict['detection_boxes']
        # get all boxes from an array
        max_boxes_to_draw = boxes.shape[0]
        # get scores to get a threshold
        scores = output_dict['detection_scores']
        # this is set as a default but feel free to adjust it to your needs
        min_score_thresh=.8
        # iterate over all objects found
        dictionary ={}
        coordinates = []
        
        for i in range(min(max_boxes_to_draw, boxes.shape[0])):
            # 
            if scores is None or scores[i] > min_score_thresh:
                class_name = category_index[output_dict['detection_classes'][i]+label_id_offset]['name']
                dictionary[class_name]=list(boxes[i])
                coordinates.append({"class_name": class_name,"score": scores[i]*100})#,"box": list(boxes[i])})
        print(dictionary)
        print(coordinates)
        
        img = cv2.imread(app.config['UPLOAD_FOLDER']+filename)
        try:
            if 'medname' in dictionary:
                #print(dictionary['composition'])
                left,top,width,height=[i for i in dictionary['medname']]
        except:
            print('error')
        im_width, im_height, chn = img.shape
        x = int(left * im_width)
        y = int(top * im_height)
        width = int(width * im_width)
        height =int(height * im_height)
        print(image_path)
        im = Image.open(image_path)
        im = im.crop((y,x,height,width))
        im.save('textextract/img_0.png')
        roi = Image.open('textextract/img_0.png')
        data = pytesseract.image_to_string(roi)
        print("pytesseract:",data)
        
        
        ####Azure below####
        #read image file string data
        #print(file)
        img = Image.open('C:/Users/Rhea/Desktop/Final/textextract/img_0.png')
        ##resize values-check
        ns = (210,90)
        img = img.resize(ns)
        img.save('textextract/resize.png')
        img='C:/Users/Rhea/Desktop/Final/textextract/resize.png'
        # image requirements - Supported image formats: JPEG, PNG, GIF, BMP.Image file size must be less than 4MB.
        # Image dimensions must be between 50 x 50 and 4200 x 4200 pixels, and the image cannot be larger than 10 megapixels.
        #img ='C:/Users/Rachael/Major_project/obj_flaskapp/Counterfeit-Medicine-Detection/img_0.png'
        read_image = open(img, "rb")
        result = read_local(read_image)
        #image = Image.open(file)
        print("Azure ocr:",result)
        if result:
            for i in coordinates:
                for k,v in i.items():
                    if v=='medname':
                        #print(k,v)
                        i[k]='medname:'+result
        else:
            for i in coordinates:
                for k,v in i.items():
                    if v=='medname':
                        print(k,v)
                        i[k]='medname:'+data
        ######################################
        result= result.lower()
        
        #Note: Use of CollectionRef stream() is prefered to get()
        docs = db.collection("meds").where("name", "==", result).stream()
        text_val=""
        mydict={}
        for doc in docs:
            print(f"{doc.id} => {doc.to_dict()}")
            doc= doc.to_dict()
            for key, value in doc.items():
                if key=='image-src':
                    continue
                else:
                    mydict[key]=value
            #mydict=doc.copy()
            print(mydict)
            break
        else:
            mydict['Not Found']="No match found in the Database"
            text_val="fake"
        
        #####################################
        #real fake classification
        medlist=['Biocon_counterfeit','Emcure_counterfeit','Fresenius_counterfeit','Glenmark_counterfeit','Hetero_counterfeit','Intas_counterfeit','Neon_counterfeit','Panacea_counterfeit','Sun_Pharma_counterfeit','Zydus_counterfeit']
        for k in dictionary:
            if k in medlist:
                value = 'fake'
                break
            else:
                value = 'real'
        print("value:",value)
        
        if value=="fake" or text_val=="fake":
            value="fake"
    return render_template("home.html" , filename="uploads/"+filename, res=im_path, coordinates=coordinates, img=img, doc=mydict, name=person["name"], value=value)

    
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
    
