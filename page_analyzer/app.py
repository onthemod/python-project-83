from flask import Flask, render_template, request, flash, redirect, get_flashed_messages, url_for
import psycopg2
import os
import validators
import requests
from bs4 import BeautifulSoup

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
        cur.execute(f"SELECT max(created_at), status_code FROM url_checks where url_id={id} group by status_code")
        url_check_tuples = cur.fetchall()
        check_date = ''
        status = ''
        if url_check_tuples:
            check_date = url_check_tuples[0][0]
            status = url_check_tuples[0][1]
            if not check_date:
                check_date = ''
        urls_list.append({'id': id, 'name': name, 'date' : date, 'check_date' : check_date, 'status' : status})
    return urls_list
 
def make_check(curs, params = '', result_info=[]):
    print(f'check params = {params}')
    request_string = f"INSERT into url_checks (url_id, status_code, created_at, h1, title, content) VALUES ('{params['check_id']}', '{params['status_code']}', NOW(),'{params['h1']}','{params['title']}','{params['content']}')"
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
    cur.execute(f"SELECT id, status_code, h1, title, description, created_at FROM url_checks where url_id={params} order by created_at desc")
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
        if result:
            for url_check_tuple in result:
                id, status, h1, title, description, date = url_check_tuple
                if not status:
                    status = ''
                if not h1:
                    h1 = ''
                if not title:
                    title = ''
                if not description:
                    description = ''
                url_checks_list.append({'id': id, 'status' : status,'h1' : h1, 'title': title, 'description':description,'date' : date})
        return render_template("url.html", url=urls_data, url_checks = url_checks_list, messages = messages)
    
    return redirect(url_for('index'))


@app.post('/urls/<id>/checks')
def check_url(id):
    result_info = []
    result = make_db_processing(get_url_data, id)
    if result:
        name = result[1]
    try:
        print(f'name = {name}')
        req = requests.request("GET", name)
    except:
        flash("Произошла ошибка при проверке", "error")
        return get_url(id)
    html_content = req.text
    
    soup = BeautifulSoup(html_content, 'html.parser')
    h1 = soup.find('h1')
    if h1:
        h1 = h1.text
    else:
        h1 = ''
    title = soup.find('title')
    if title:
        title = title.text
    else:
        title = ''
    print(f'=======h1 is {h1}')
    meta_description_tag = soup.find('meta', attrs={'name': 'description'})
    content = ''
    if meta_description_tag:
        content = meta_description_tag.get("content")
        if not content:
            content = ''

    params = {'check_id': id, 'status_code': req.status_code, 'title': title, 'h1': h1, 'content': content}
    make_db_processing(make_check, params, result_info)
    if page_checked in result_info:
        flash("Страница успешно проверена", "success")
        return get_url(id)


