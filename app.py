from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import os
import random
import cv2
import numpy as np
import requests
import speech_recognition as sr
from pydub import AudioSegment

def audio_to_text(audio_path):
    recognizer = sr.Recognizer()

    try:
        wav_path = os.path.splitext(audio_path)[0] + ".wav"

        audio = AudioSegment.from_file(audio_path)
        audio = audio.set_channels(1).set_frame_rate(16000)
        audio.export(wav_path, format="wav")

        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        text = recognizer.recognize_google(audio_data)
        return text

    except sr.UnknownValueError:
        return "Could not understand the audio"

    except sr.RequestError:
        return "Speech recognition service unavailable"

    except Exception as e:
        return f"Audio processing error: {str(e)}"
    
def analyze_image(path):
    img = cv2.imread(path)

    if img is None:
        return "No image detected", 0, 0, 0

    avg_brightness = np.mean(img)
    green = np.mean(img[:, :, 1])
    red = np.mean(img[:, :, 2])
    blue = np.mean(img[:, :, 0])

    # Default values
    condition = "Healthy Plant"
    soil = 60
    temperature = 28
    humidity = 65

    # Disease check
    if green < 70:
        condition = "Leaf Disease Detected"
        soil = 35
        temperature = 30
        humidity = 55

    # Dry / low moisture
    elif avg_brightness < 80:
        condition = "Dry Plant - Irrigation Needed"
        soil = 20
        temperature = 34
        humidity = 40

    # Moderate
    elif avg_brightness < 120:
        condition = "Moderate Moisture"
        soil = 40
        temperature = 30
        humidity = 55

    # Healthy
    else:
        condition = "Healthy Plant"
        soil = 60
        temperature = 26
        humidity = 70

    return condition, soil, temperature, humidity

app = Flask(__name__)
app.secret_key = "smartagri"

# ================= DATABASE CONNECTION =================

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="smartagri_db"
)

cursor = db.cursor()

# ================= HOME =================

@app.route("/")
def home():
    return redirect(url_for("login"))

# ================= LOGIN =================

@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email,password)
        )

        user = cursor.fetchone()

        if user:
            session["user_id"] = user[0]
            session["user_name"] = user[1]

            return redirect(url_for("dashboard"))
        else:
            return "Invalid Email or Password"

    return render_template("login.html")


# ================= REGISTER =================

@app.route('/register', methods=['GET','POST'])
def register():

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # check if email already exists
        cursor.execute("SELECT * FROM users WHERE email=%s",(email,))
        existing_user = cursor.fetchone()

        if existing_user:
            return "Email already registered"

        # insert new user
        cursor.execute(
            "INSERT INTO users (name,email,password) VALUES (%s,%s,%s)",
            (name,email,password)
        )

        db.commit()

        return redirect('/login')

    return render_template("register.html")


# ================= AUDIO UPLOAD =================

@app.route("/upload-audio", methods=["POST"])
def upload_audio():
    return redirect(url_for("dashboard"))

@app.route("/analyze-audio-text", methods=["POST"])
def analyze_audio_text():

    speech_text = request.form.get("speech_text", "").lower()

    issue = "General Query"
    advice = "Please monitor the crop regularly."
    urgency = "Low"

    if "yellow" in speech_text or "turning yellow" in speech_text:
        issue = "Possible Nutrient Deficiency"
        advice = "Apply nitrogen-rich fertilizer and inspect leaf health."
        urgency = "Medium"

    elif "dry" in speech_text or "wilting" in speech_text:
        issue = "Water Stress Detected"
        advice = "Increase irrigation and check soil moisture immediately."
        urgency = "High"

    elif "spots" in speech_text or "disease" in speech_text or "fungus" in speech_text:
        issue = "Possible Leaf Disease"
        advice = "Use neem spray or fungicide and remove affected leaves."
        urgency = "High"

    elif "insect" in speech_text or "pest" in speech_text or "worms" in speech_text:
        issue = "Possible Pest Attack"
        advice = "Inspect leaves carefully and apply suitable pest control."
        urgency = "High"

    elif "slow growth" in speech_text:
        issue = "Poor Crop Growth"
        advice = "Check soil nutrients, sunlight, and watering schedule."
        urgency = "Medium"

    session["audio_text"] = speech_text
    session["audio_issue"] = issue
    session["audio_advice"] = advice
    session["audio_urgency"] = urgency

    return redirect(url_for("dashboard"))
    

# ================= DASHBOARD =================


def get_soil_moisture():
    return random.randint(30, 70)

@app.route("/dashboard")
def dashboard():

    audio_text = session.get("audio_text", "No audio analyzed yet")
    audio_issue = session.get("audio_issue", "No issue detected")
    audio_advice = session.get("audio_advice", "No advice yet")
    audio_urgency = session.get("audio_urgency", "Low")

    if "user_id" not in session:
        return redirect(url_for("login"))

    temperature = 0
    humidity = 0
    soil = 0
    weather = "No Data Available"
    condition = "No Image Uploaded"
    irrigation = "No Data Available"
    recommendation = "No Recommendation Yet"
    fertilizer = "No fertilizer recommendation yet"
    files = []

    upload_folder = "static/uploads"

    if os.path.exists(upload_folder):
        files = os.listdir(upload_folder)

        if files:
            latest_file = max(
                [os.path.join(upload_folder, f) for f in files],
                key=os.path.getctime
            )

            condition, soil, temperature, humidity = analyze_image(latest_file)
            weather = "AI Field Analysis"


            if soil < 30:
                irrigation = "⚠ ALERT: Soil Moisture Very Low! Turn ON Irrigation Immediately!"
                recommendation = "Suitable Crops: Millets, Gram, Pulses"
            elif soil < 50:
                irrigation = "⚠ Soil Moisture Low! Consider Turning ON Irrigation."
                recommendation = "Suitable Crops: Wheat, Maize, Mustard"
            else:
                irrigation = "✅ Irrigation Not Needed"
                recommendation = "Suitable Crops: Rice, Sugarcane, Banana"
            
            # Fertilizer recommendation
            if soil < 30:
                fertilizer = "Apply organic compost or nitrogen fertilizer."
            elif "yellow" in audio_text.lower():
                fertilizer = "Apply Nitrogen fertilizer (Urea or Ammonium Sulfate)."
            elif "spots" in audio_text.lower() or "disease" in audio_text.lower():
                fertilizer = "Apply fungicide and potassium-rich fertilizer."
            elif "slow growth" in audio_text.lower():
                fertilizer = "Apply balanced NPK fertilizer."
            elif condition == "Dry Plant - Irrigation Needed":
                fertilizer = "Apply organic compost and improve irrigation."
            elif condition == "Moderate Moisture":
                fertilizer = "Apply balanced NPK fertilizer."
            elif condition == "Healthy Plant":
                fertilizer = "No fertilizer required. Crop is healthy."

    return render_template(
        "dashboard.html",
        temp=temperature,
        hum=humidity,
        soil=soil,
        weather=weather,
        condition=condition,
        irrigation=irrigation,
        recommendation=recommendation,
        fertilizer=fertilizer,
        files=files,
        audio_text=audio_text,
        name=session["user_name"],
        history=[],
        audio_issue=audio_issue,
        audio_advice=audio_advice,
        audio_urgency=audio_urgency
    )
    
# ================= ADD SENSOR DATA =================

@app.route("/add-data")
def add_data():

    if "user_id" not in session:
        return redirect(url_for("login"))

    temperature = random.randint(20,40)
    humidity = random.randint(40,80)
    soil = random.randint(10,60)

    cursor.execute("""
    INSERT INTO sensors(temperature,humidity,soil_moisture,user_id)
    VALUES(%s,%s,%s,%s)
    """,(temperature,humidity,soil,session["user_id"]))

    db.commit()

    return redirect(url_for("dashboard"))


# ================= PHOTO UPLOAD =================

@app.route("/upload-photo", methods=["POST"])
def upload_photo():

    photo = request.files.get("photo")

    if photo and photo.filename != "":

        upload_folder = "static/uploads"

        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        path = os.path.join(upload_folder, photo.filename)

        photo.save(path)

        session["photo_uploaded"] = True

    return redirect(url_for("dashboard"))

# ================= LOGOUT =================

@app.route("/logout")
def logout():

    upload_folder = "static/uploads"

    if os.path.exists(upload_folder):
        for f in os.listdir(upload_folder):
            os.remove(os.path.join(upload_folder, f))

    session.clear()

    return redirect(url_for("login"))

# ================= RUN APP =================

if __name__ == "__main__":
    app.run(debug=True)