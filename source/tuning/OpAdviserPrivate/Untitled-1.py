
import mysql.connector

dbconfig = {
    "host": "localhost",
    "user": "root",
    "password": "password",
    "database": "concert_singer",
    "port": 3308,
}
mydb = mysql.connector.connect(**dbconfig)