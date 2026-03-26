import mysql.connector

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",   # default in XAMPP
    database="smartagri"
)

cursor = db.cursor()