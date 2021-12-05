from flask import Flask, request, jsonify, Response
import psycopg2
from auth_err_codes import *
import time
import hashlib
import datetime as dt

PORT = 8069

DB_HOSTNAME='localhost'
DB_PORT=5432
DB_NAME='Auth_users'
DB_USERNAME='Authenticator'
DB_PASSWORD=1234
TIMEOUT_INTERVAL=3600.0

# DB queries
users_check_user = """SELECT * from Users where Username = %s"""
users_insert = """ INSERT INTO Users (Username, Password_hash) VALUES (%s,%s)"""
user_update = """UPDATE Users set Token = %s, Sess_updated = %s where Username = %s"""
update_session = """UPDATE Users set Sess_updated = %s where Username = %s"""


app = Flask("Auth_server")

try:
    db_connection = psycopg2.connect(host = DB_HOSTNAME, port = DB_PORT, dbname = DB_NAME, user = DB_USERNAME, password = DB_PASSWORD)
    db_cursor = db_connection.cursor()
except Exception as e:
    print(e)
    exit(0)

def reconnect():
    global db_connection, db_cursor
    try:
        db_connection = psycopg2.connect(host = DB_HOSTNAME, port = DB_PORT, dbname = DB_NAME, user = DB_USERNAME, password = DB_PASSWORD)
        db_cursor = db_connection.cursor()
    except Exception as e:
        print(e)
        exit(0)

def get_token(username, password):
    data_base = str(username) + str(password)
    data_base += str(time.time())
    token = hashlib.sha256(data_base.encode()).hexdigest()
    return token.encode()


NAME = 0
TYPE = 1
def check_json(list, json_file):
    for param in list:
        if param[NAME] not in json_file:
            return False
        elif param[TYPE] is not type(json_file[param[NAME]]):
            if param[TYPE] is float and type(json_file[param[NAME]]) is int:
                continue
            return False
    return True

USER_INFO = [("username", str), ("password", str)]
USER_TOKEN = [("username", str), ("token", str)]

@app.route("/hello", methods = ["GET"])
def hello():
    return jsonify("hello"), 200

@app.route("/sign_up", methods = ["GET","POST"])
def sign_up():
    payload = request.get_json(silent=True)
    if not payload:
        print("1")
        return Response(status = 400)
    if not check_json(USER_INFO, payload):
        print("2")
        return Response(status = 400)    
    username = payload['username']
    password = payload['password']

    try:
        db_cursor.execute(users_check_user, (username,))
        user_record = db_cursor.fetchone()
        if user_record is not None:
            return Response('Username already taken', status=409)
    except (Exception, psycopg2.Error) as error:
        if type(error) == psycopg2.errors.AdminShutdown:
            print("Interface error, trying to reconnect")
            time.sleep(1)
            reconnect()
        db_connection.rollback()
        print("Create account get user conflict", error)
        return Response('Create account get user conflict', status=418)

    try:
        db_cursor.execute(users_insert, (username, password,))
        db_connection.commit()
    except (Exception, psycopg2.Error) as error:
        if type(error) == psycopg2.errors.AdminShutdown:
            print("Interface error, trying to reconnect")
            time.sleep(1)
            reconnect()
        db_connection.rollback()
        print("Create account insert user conflict", error)
        return Response('Create account insert user conflict', status=418)

    return Response('Account created', status=200)

@app.route("/log_in", methods = ["GET","POST"])
def log_in():
    payload = request.get_json(silent=True)
    if not payload:
        print("sss")
        return Response(status = 400)
    if not check_json(USER_INFO, payload):
        print("sadsad")
        return Response(status = 400)    
    username = payload['username']
    password = payload['password']

    try:
        db_cursor.execute(users_check_user, (username,))
        user_record = db_cursor.fetchone()
        if user_record is None:
            return Response('Username does not exist', status=409)
    except (Exception, psycopg2.Error) as error:
        print(type(error))
        if type(error) == psycopg2.errors.AdminShutdown:
            print("Interface error, trying to reconnect")
            time.sleep(1)
            reconnect()
        db_connection.rollback()
        print('Log in get user conflict', error)
        return Response('Log in get user conflict', status=418)

    user_pass = user_record[2]
    if password != user_pass:
        return Response('Incorrect password', status=409)

    token = get_token(username, user_pass)

    try:
        db_cursor.execute(user_update, (token.decode(), str(dt.datetime.now()), username,) )
        db_connection.commit()
    except (Exception, psycopg2.Error) as error:
        if type(error) == psycopg2.errors.AdminShutdown:
            print("Interface error, trying to reconnect")
            time.sleep(1)
            reconnect()
        db_connection.rollback()
        print("conflict la update log in", error)
        return Response( "conflict la update log in", status=418)

    return Response(token, status=200)

def check_token(username, token):
    try:
        db_cursor.execute(users_check_user, (username,))
        user_record = db_cursor.fetchone()
        print(user_record)
        if user_record is None:
            return Response('Username does not exist', status=409)
    except (Exception, psycopg2.Error) as error:
        if type(error) == psycopg2.errors.AdminShutdown:
            print("Interface error, trying to reconnect")
            time.sleep(1)
            reconnect()
        db_connection.rollback()
        print('Log in get user conflict', error)
        return Response('Log in get user conflict', status=418)

    if user_record[3] != token:
        return Response('Incorrect token', status=409)

    if (dt.datetime.now() - user_record[4]).total_seconds() > TIMEOUT_INTERVAL:
        return Response('Session expired', status=409)

    try:
        db_cursor.execute(update_session, (str(dt.datetime.now()), username,) )
        db_connection.commit()
    except (Exception, psycopg2.Error) as error:
        if type(error) == psycopg2.errors.AdminShutdown:
            print("Interface error, trying to reconnect")
            time.sleep(1)
            reconnect()
        db_connection.rollback()
        print("conflict la update timestamp check in", error)
        return Response("Conflict la update timestamp in check", status=418)
    
    return Response("Good token", status=200)

@app.route("/check", methods = ["GET"])
def check():
    payload = request.get_json(silent=True)
    if not payload:
        return Response(status = 400)
    if not check_json(USER_TOKEN, payload):
        return Response(status = 400)    
    username = payload['username']
    token = payload['token']

    return check_token(username, token)

@app.route("/log_out", methods = ["GET","POST"])
def log_out():
    payload = request.get_json(silent=True)
    if not payload:
        return Response(status = 400)
    if not check_json(USER_TOKEN, payload):
        return Response(status = 400)    
    username = payload['username']
    token = payload['token']

    response = check_token(username, token)
    ret_code = response.status_code
    msg = response.response
    print(ret_code, type(ret_code), msg)

    if ret_code != 200:
        return response

    try:
        db_cursor.execute(user_update, (None, str(dt.datetime.now()), username,) )
        db_connection.commit()
    except (Exception, psycopg2.Error) as error:
        if type(error) == psycopg2.errors.AdminShutdown:
            print("Interface error, trying to reconnect")
            time.sleep(1)
            reconnect()
        db_connection.rollback()
        print("conflict la log out", error)
        return Response( "conflict la update log out", status=418)
    
    return Response('Successfully logged out', status=200)

if __name__ == "__main__":
    app.run("0.0.0.0", PORT, debug = True)