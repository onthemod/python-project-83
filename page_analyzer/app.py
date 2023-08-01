from flask import Flask, render_template, request, flash, redirect, get_flashed_messages, url_for
import psycopg2
import os
import validators

app = Flask(__name__)
app.secret_key = "secret_key"
need_commit = "need commit"
page_added = "page added"
page_checked = "page checked"
connection_failed = 'Connection failed'


def post_url(curs, url, result_info = []):
    curs.execute(f"SELECT id from urls WHERE name='{url}'")
    urls_tuples = curs.fetchall()
    print(f"urls tuples = {urls_tuples}")
    if not urls_tuples:
        request_string = f"INSERT into urls (name, created_at) VALUES ('{url}', NOW())"
        print(request_string)
        curs.execute(request_string)
        result_info.append(page_added)
    else:
        result_info.append(urls_tuples[0][0])

@app.route('/')
def index():
    messages = get_flashed_messages(with_categories=True)
    return render_template("main.html", messages = messages) 

def make_db_processing(query_function, params = '', result_info = []):
    print('making processing')
    DATABASE_URL = os.getenv('DATABASE_URL')
    print(DATABASE_URL)
    try:
        conn = psycopg2.connect(DATABASE_URL)
    except:
        result_info.append(connection_failed)
        print("Эксепшен, йо")
        return 
    with conn.cursor() as curs:
        query_result = query_function(curs, params, result_info) #посмотреть, как лучше возвращать результат
        if page_added in result_info or page_checked in result_info:
            print(result_info)
            conn.commit()
    conn.close()
    return query_result

@app.post('/urls')
def urls_page():
    print(request.form.to_dict())
    url_string = request.form.to_dict().get('url', '')
    if url_string:
        if not validators.url(url_string):
            flash("Некорректный URL", "error")
            return redirect(url_for('index'))
        result_info = []
        make_db_processing(post_url, url_string, result_info)
        if page_added in result_info:
            flash("Страница успешно добавлена", "success")
            return get_urls()
        elif connection_failed in result_info:
            flash("Нет соединения с базой данных", "error")
            return redirect(url_for('index'))
        else:
            flash("Страница уже существует", "error")
            print(f"тип id существующей старницы {type(result_info[0])}")
            return redirect(url_for('get_url', id=str('id')))
    return redirect(url_for('index'))

def get_urls_list(cur, params='', result_info=[]):
    cur.execute("SELECT * FROM urls order by created_at desc")
    urls_tuples = cur.fetchall()
    urls_list= [] 
    if not urls_tuples:
        print('empty')
    else:
        print(urls_tuples)
    for url_tuple in urls_tuples:
        id, name, date = url_tuple
        cur.execute(f"SELECT max(created_at) FROM url_checks where url_id={id}")
        url_check_tuples = cur.fetchall()
        check_date = ''
        if url_check_tuples:
            check_date = url_check_tuples[0][0]
        urls_list.append({'id': id, 'name': name, 'date' : date, 'check_date' : check_date})
    return urls_list
 
def make_check(curs, params = '', result_info=[]):
    request_string = f"INSERT into url_checks (url_id, created_at) VALUES ('{params[0]}', NOW())"
    curs.execute(request_string)
    result_info.append(page_checked)

def get_url_data(cur, params='', result_info=[]):
    cur.execute(f"SELECT * FROM urls where id={params}")
    urls_tuples = cur.fetchall()
    urls_list= [] 
    if not urls_tuples:
        print('empty')
        return None
    else:
        print(urls_tuples)
    return urls_tuples[0]
    
def get_url_checks(cur, params='', result_info=[]):
    cur.execute(f"SELECT id, created_at FROM url_checks where url_id={params} order by created_at desc")
    urls_tuples = cur.fetchall()
    urls_list= [] 
    if not urls_tuples:
        print('empty')
        return None
    else:
        print(f"check tuples = {urls_tuples}")
    return urls_tuples
    
@app.get('/urls')
def get_urls():
    messages = get_flashed_messages(with_categories=True)
    print(f"messages = {messages}")
    result_info = []
    urls_list = make_db_processing(get_urls_list, result_info=result_info)
    if connection_failed in result_info:
        flash("Нет соединения с базой данных", "error")
        return redirect(url_for('index'))
    return render_template("urls.html", urls=urls_list, messages = messages)

@app.get('/urls/<id>')
def get_url(id):
    messages = get_flashed_messages(with_categories=True)
    result = make_db_processing(get_url_data, id)
    if result:
        id, name, date = result
        urls_data = {"id" : id, "name":name, "date":date}
        result = make_db_processing(get_url_checks, id)
        url_checks_list = []
        print(f"url_checks = {result}")
        for url_check_tuple in result:
            id, date = url_check_tuple
            url_checks_list.append({'id': id, 'date' : date})
        return render_template("url.html", url=urls_data, url_checks = url_checks_list, messages = messages)
    
    return redirect(url_for('index'))

@app.post('/urls/<id>/checks')
def check_url(id):
    result_info = []
    make_db_processing(make_check, id, result_info)
    if page_checked in result_info:
        flash("Страница успешно проверена", "success")
        return get_url(id)


