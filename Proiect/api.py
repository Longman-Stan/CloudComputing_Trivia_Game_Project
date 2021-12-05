import pika
import sys
import psycopg2
from flask import Flask, json, request, jsonify, Response, redirect
import requests
import hashlib
import time
import base64
import random

def reconnect():
    global db_connection, db_cursor
    try:
        db_connection = psycopg2.connect(host = DB_HOSTNAME, port = DB_PORT, dbname = DB_NAME, user = DB_USERNAME, password = DB_PASSWORD)
        db_cursor = db_connection.cursor()
    except Exception as e:
        print(e)
        exit(0)

def make_dict(list, elems):
    res = {}
    
    for i in range(len(list)):
        name, typeof = list[i]
        if name is None:
            continue
        res[name] = typeof(elems[i])
        
    return res


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

def get_record(list, json_file):
    rez = []
    for param in list:
        rez.append(json_file[param[NAME]])
    return tuple(rez)

AUTH_HOSTNAME = "127.0.0.1"
AUTH_PORT = 8069

PORT = 8067
app = Flask("API")


DB_HOSTNAME='127.0.0.1'
DB_PORT=5433
DB_NAME='quiz_db'
DB_USERNAME='user'
DB_PASSWORD='pass'

# DB connection
db_connection = psycopg2.connect(host = DB_HOSTNAME, port = DB_PORT, dbname = DB_NAME, user = DB_USERNAME, password = DB_PASSWORD)
db_cursor = db_connection.cursor()

# RabbitMQ connection
mq_connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = mq_connection.channel()
channel.queue_declare(queue='task_queue', durable=True)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Queries
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"Questions"
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
categories_types = [("category", str)]
questions_types = [("id", int), ("question", str), ("choicea", str),
("choiceb", str), ("choicec", str), ("choiced", str), ("category", str)]
question_answer_types = [("answer", int)]

get_question_categories = """SELECT DISTINCT category FROM public.questions ORDER BY category;"""
get_question_by_level = """SELECT id, question, choicea, choiceb, choicec, choiced, category FROM public.questions where level=%s ORDER BY random() LIMIT 1;"""
get_question_by_level_categories = """SELECT id, question, choicea, choiceb, choicec, choiced, category FROM public.questions where level=%s and category in %s ORDER BY random() LIMIT 1;"""
get_question_hint_by_id = """SELECT hint FROM public.questions WHERE id = %s;"""
get_question_answer_by_id = """SELECT answer FROM public.questions WHERE id = %s;"""
insert_question_instruction = """  INSERT INTO public.questions(\
	Question, Answer, ChoiceA, ChoiceB, ChoiceC, ChoiceD, Category, Hint, Level)\
	VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"Statistics"
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
TO_INCREMENT_FIELD_NAME = "to_increment"
statistics_reprezentation = [("Id", int) , ("Question_Id", int), ("No_Answer", int), ("No_ChoiceA", int), ("No_ChoiceB", int), ("No_ChoiceC", int), ("No_ChoiceD", int)]
statistics_update_name_types_list = [(TO_INCREMENT_FIELD_NAME, list)]
statistics_increment_fields = ["No_Answer", "No_ChoiceA", "No_ChoiceB", "No_ChoiceC", "No_ChoiceD"]
get_statistics_by_questionId = """SELECT * FROM STATISTICS WHERE Question_Id = %s"""
update_statistics_by_questionId = """UPDATE STATISTICS SET {fields} WHERE Question_Id = %s"""


# Auth part

def get_pass_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route("/sign_up", methods = ["POST"])
def sign_up():
    payload = request.get_json(silent=True)
    if not payload:
        return Response("no payload", status = 400)
    if 'password' not in payload:
        return Response("no password", status = 400) 
    payload['password'] = get_pass_hash(payload['password'])
    url = f"http://{AUTH_HOSTNAME}:{AUTH_PORT}/sign_up"
    r = requests.post(url, json=payload)
    return (r.text, r.status_code, r.headers.items())

@app.route("/log_in", methods = ["POST"])
def log_in():
    payload = request.get_json(silent=True)
    if not payload:
        return Response("no payload", status = 400)
    if 'password' not in payload:
        return Response("no password", status = 400) 
    payload['password'] = get_pass_hash(payload['password'])
    url = f"http://{AUTH_HOSTNAME}:{AUTH_PORT}/log_in"
    r = requests.post(url, json=payload)
    return (r.text, r.status_code, r.headers.items())

@app.route("/log_out", methods = ["POST"])
def log_out():
    url = f"http://{AUTH_HOSTNAME}:{AUTH_PORT}/log_out"
    return redirect(url, code=307)

def check_auth(basic_auth_header):
    b64_encoded = basic_auth_header.split()[1]
    decrypted_header = base64.b64decode(b64_encoded)
    decrypted_header = decrypted_header.decode('utf-8')
    
    username, token = decrypted_header.split(':', 1)
    url = f"http://{AUTH_HOSTNAME}:{AUTH_PORT}/check"
    r = requests.get(url,json={'username':username, 'token':token})
    if r.status_code == 200:
        return True
    return False

# Test auth check

@app.route("/hello_user", methods = ["GET"])
def hello_user():
    basic_auth_header = request.headers.get("Authorization")
    if check_auth(basic_auth_header):
        return Response("Hello user", status= 200)
    else:
        return Response("You're a fraud", status= 409)

# Questions

def get_categories():
    try:
        db_cursor.execute(get_question_categories, [])
        records = db_cursor.fetchall()
    except (Exception, psycopg2.Error) as error:
        if type(error) == psycopg2.errors.AdminShutdown:
            print("Interface error, trying to reconnect")
            time.sleep(1)
            reconnect()
        db_connection.rollback()
        print("conflict la get categories", error)
        return None
    
    categories = [elems for row in records for elems in row]
    return categories

# get category list
@app.route("/question/categories", methods = ["GET"])
def get_q_categories():
    basic_auth_header = request.headers.get("Authorization")
    if not check_auth(basic_auth_header):
        print("User not logged in on server", flush=True)
        return jsonify([]), 403

    categories = get_categories()
    if categories is None:
        return Response( "conflict la get categories", status=418)
   
    return jsonify({"categories":categories}), 200

@app.route("/question/<int:level>", methods = ["GET"])
def get_question_by_level_category(level):
    basic_auth_header = request.headers.get("Authorization")
    if not check_auth(basic_auth_header):
        print("User not logged in on server", flush=True)
        return jsonify([]), 403

    requested_categories = request.args.getlist("category")

    categories = get_categories()
    if categories is None:
        return Response( "conflict la get categories", status=418)
   
    if all( category in categories for category in requested_categories):

        categories = requested_categories
        query = get_question_by_level
        params = [level]

        if categories:
            query = get_question_by_level_categories
            params = [level, categories]

        try:
            db_cursor.execute(query, params)
            records = db_cursor.fetchall()
        except (Exception, psycopg2.Error) as error:
            if type(error) == psycopg2.errors.AdminShutdown:
                print("Interface error, trying to reconnect")
                time.sleep(1)
                reconnect()
            db_connection.rollback()
            print("Problem with get random question by level", error, flush=True)
            return jsonify([]), 418
        
        result=[]
        for row in records:
            result.append(make_dict(questions_types, row))
        print("RESULTS:", result, flush=True)
        
        if result == []:
            print("GAME WON")
        return jsonify(result), 200
    else:
        return jsonify([]), 409

def get_q_answer(q_id):
    try:
        db_cursor.execute(get_question_answer_by_id, [q_id])
        records = db_cursor.fetchall()
    except (Exception, psycopg2.Error) as error:
        if type(error) == psycopg2.errors.AdminShutdown:
            print("Interface error, trying to reconnect")
            time.sleep(1)
            reconnect()
        db_connection.rollback()
        print("Problem with get question answer", error)
        return -1

    correct_answer = records[0][0]
    return correct_answer
    
@app.route("/question/answer/<int:q_id>", methods = ["GET"])
def get_question_answer(q_id):

    correct_answer = get_q_answer(q_id)
    if correct_answer == -1:
        return Response("Problem with get q answer", status=418)

    print("CORRECT ANSWER", correct_answer, flush=True)
    return jsonify({"answer":correct_answer}), 200

def get_answer_statistics(q_id, add_corect_answer = False):
    try:
        db_cursor.execute(get_statistics_by_questionId, [q_id])
        records = db_cursor.fetchall()
        
        if len(records) == 0:
            return 404    
    except (Exception, psycopg2.Error) as error:
        if type(error) == psycopg2.errors.AdminShutdown:
            print("Interface error, trying to reconnect")
            time.sleep(1)
            reconnect()
        db_connection.rollback()
        print("get question statistics error", error)
        return 418
    
    data = make_dict(statistics_reprezentation, records[0])
    
    question_stat = {}
    
    total_answers = data["No_ChoiceA"] + data["No_ChoiceB"] + data["No_ChoiceC"] + data["No_ChoiceD"]
    
    if total_answers != 0:
        if add_corect_answer:
            question_stat["No_Answer"] = round(((100 * data["No_Answer"]) / total_answers), 2)
            
        question_stat["No_ChoiceA"] = round(((100 * data["No_ChoiceA"]) / total_answers), 2)
        question_stat["No_ChoiceB"] = round(((100 * data["No_ChoiceB"]) / total_answers), 2)
        question_stat["No_ChoiceC"] = round(((100 * data["No_ChoiceC"]) / total_answers), 2)
        question_stat["No_ChoiceD"] = round(((100 * data["No_ChoiceD"]) / total_answers), 2)
    
    return question_stat

@app.route("/question/help/<int:q_id>", methods = ["GET"])
def get_question_help(q_id):
    basic_auth_header = request.headers.get("Authorization")
    if not check_auth(basic_auth_header):
        print("User not logged in on server", flush=True)
        return jsonify([]), 403

    help_type = request.args.getlist("type")[0]

    if help_type == "fifty_fifty":
        correct_answer = get_q_answer(q_id)

        if correct_answer == -1:
            return Response("Problem with get fifty-fifty q answer", status=418)

        possible_answers = [0, 1, 2, 3]
        possible_answers.remove(correct_answer)

        result = {"fifty_fifty":[correct_answer, random.choice(possible_answers)]}
        return jsonify(result), 200
    elif help_type == "hint":

        try:
            db_cursor.execute(get_question_hint_by_id, [q_id])
            records = db_cursor.fetchall()
        except (Exception, psycopg2.Error) as error:
            if type(error) == psycopg2.errors.AdminShutdown:
                print("Interface error, trying to reconnect")
                time.sleep(1)
                reconnect()
            db_connection.rollback()
            print("conflict la get categories", error)
            return Response( "conflict la get hint", status=418)
            
        hint = records[0][0]
        return jsonify({"hint":hint}), 200

    elif help_type == "ask_public":
        q_stat = get_answer_statistics(q_id)

        if type(q_stat) != dict:
            return jsonify([]), q_stat

        return jsonify(q_stat), 200

    else:
        print("Unknown help_type request", flush=True)
        return jsonify([]), 404


@app.route("/question/statistics/<int:q_id>", methods = ["GET"])
def get_question_by_id_statistics(q_id):
    print("SUNT PE GET QUESTION STATISTICS!", flush=True)

    basic_auth_header = request.headers.get("Authorization")
    if not check_auth(basic_auth_header):
        print("User not logged in on server", flush=True)
        return jsonify([]), 403
    
    q_stat = get_answer_statistics(q_id, True)
    if type(q_stat) != dict:
        return jsonify([]), q_stat
    
    return jsonify(q_stat), 200

# Publish messages

#message = ' '.join(sys.argv[1:]) or "Hello World!"
# channel.basic_publish(exchange='',
#                       routing_key='task_queue',
#                       body=message,
#                       properties=pika.BasicProperties(
#                       delivery_mode=2,  # make message persistent
#                     ))
# print(" [x] Sent %r" % message)
# connection.close()

@app.route("/question/insert", methods = ["POST"])
def insert_question():
    message = {}
    message['method'] = "insert_question"
    message['body'] = request.json
    message = json.dumps(message)
    channel.basic_publish(exchange='',
                            routing_key='task_queue',
                            body=message,
                            properties=pika.BasicProperties(
                           delivery_mode= pika.spec.PERSISTENT_DELIVERY_MODE)  # make message persistent
                        )
    return Response(status=200)

@app.route("/question/answer/<int:q_id>", methods = ["POST"])
def answer_question(q_id):

    basic_auth_header = request.headers.get("Authorization")
    if not check_auth(basic_auth_header):
        print("User not logged in on server", flush=True)
        return jsonify([]), 403
    
    payload = request.get_json(silent = True)
    if not payload:
        return Response(status = 400)
    if not check_json(question_answer_types, payload):
        return Response(status = 400)
    record = get_record(question_answer_types, payload)
    answer = int(record[0])
    print("ANSWER:", answer, flush=True)

    correct_answer = get_q_answer(q_id)
    if correct_answer == -1:
        return Response("Problem with get q answer", status=418)

    fields = ["No_ChoiceA", "No_ChoiceB", "No_ChoiceC", "No_ChoiceD"]
    fields_to_update = []
    if answer == correct_answer:
        fields_to_update.append("No_Answer")
    fields_to_update.append(fields[answer])

    upd_stat_message = {}
    upd_stat_message['method'] = "update_statistics"
    upd_stat_message['question_id'] = q_id
    upd_stat_message['body'] = {"to_increment":fields_to_update}
    upd_stat_message = json.dumps(upd_stat_message)

    channel.basic_publish(exchange='',
                            routing_key='task_queue',
                            body=upd_stat_message,
                            properties=pika.BasicProperties(
                           delivery_mode= pika.spec.PERSISTENT_DELIVERY_MODE)  # make message persistent
                        )

    return jsonify({"answer":correct_answer}), 200

if __name__ == "__main__":
    app.run("0.0.0.0",port=PORT, debug=True)