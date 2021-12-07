import pika, sys, os
from  sys import modules
import psycopg2

# ENV DB_HOSTNAME=main_db 
# ENV DB_PORT=5432
# ENV DB_NAME=quiz_db
# ENV DB_USERNAME=user
# ENV DB_PASSWORD=pass

# hostname = os.environ['DB_HOSTNAME']
# port = os.environ['DB_PORT']
# db_name = os.environ['DB_NAME']
# username = os.environ['DB_USERNAME']
# password = os.environ['DB_PASSWORD']

hostname = '127.0.0.1'
port = 5433
db_name = "quiz_db"
username = "user"
password = "pass"

db_connection = psycopg2.connect(host = hostname, port = port, dbname = db_name, user = username, password = password)
db_cursor = db_connection.cursor()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Here goes the raw sql shit
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
TO_INCREMENT_FIELD_NAME = "to_increment"
get_statistics_by_questionId = """SELECT * FROM STATISTICS WHERE Question_Id = %s"""
update_statistics_by_questionId = """UPDATE STATISTICS SET {fields} WHERE Question_Id = %s"""
insert_question_instruction = """  INSERT INTO public.questions(\
	Question, Answer, ChoiceA, ChoiceB, ChoiceC, ChoiceD, Category, Hint, Level)\
	VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) """
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Here is where the raw sql shit ends
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def update_statistics(body):
    try:
        db_cursor.execute(get_statistics_by_questionId, [body["question_id"]])
        records = db_cursor.fetchall()
        
        if len(records) == 0:
            return 

        set_parts = []
        fields = body[TO_INCREMENT_FIELD_NAME]
        for value in fields:
            set_parts.append("{val} = {val} + 1".format(val = value))

        set_string = ", ".join(set_parts)

        db_cursor.execute(update_statistics_by_questionId.format(fields = set_string), [body["question_id"]])
        db_connection.commit()
        
    except (Exception, psycopg2.Error) as error:
        db_connection.rollback()
        return

def insert_question(body):
    try:
        payload = []
        for field in ["Question", "Answer", "ChoiceA", "ChoiceB", "ChoiceC", "ChoiceD", "Category", "Hint", "Level"]:
            payload.append(body[field])

        db_cursor.execute(insert_question_instruction, payload)
        db_connection.commit()
    except (Exception, psycopg2.Error) as error:
        db_connection.rollback()
        return

def get_function(name):
    this_mod = modules[__name__]
    return getattr(this_mod, name)

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()

    channel.queue_declare(queue='task_queue', durable=True)

    def callback(ch, method, properties, body):
        print(" [x] Received %r" % body.decode())

        func = get_function(body["method"])
        data = body["body"]
        func(data)

        ch.basic_ack(delivery_tag = method.delivery_tag)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='task_queue', on_message_callback=callback, auto_ack=False)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
