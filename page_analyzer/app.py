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

DATABASE_URL = os.getenv('DATABASE_URL')

@app.route('/')
def index():
    messages = get_flashed_messages(with_categories=True)
    return render_template("main.html", messages = messages)

@app.post('/urls')
def urls_page():
    print(request.form.to_dict())
    url_string = request.form.to_dict().get('url', '')
    if url_string:
        if not validators.url(url_string):
            flash("Некорректный URL", "alert alert-danger")
            return redirect(url_for('index'))
        result_info = []
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as curs:
                get_ids_of_url_query = "SELECT id from urls WHERE name= %s;"
                curs.execute(get_ids_of_url_query, (url_string,))
                urls_tuples = curs.fetchall()
                if urls_tuples:
                    print('страница существует')
                    flash("Страница уже существует", "alert alert-danger")
                    return redirect(url_for('get_url', id=urls_tuples[0][0]))
                add_url_query = "INSERT into urls (name, created_at) VALUES (%s, NOW()) returning id;"
                curs.execute(add_url_query, (url_string,))
                new_id = curs.fetchone()[0]
                conn.commit()
                flash("Страница успешно добавлена", "alert alert-success")
                return redirect(url_for('get_url', id=new_id))
    
@app.get('/urls')
def get_urls():
    messages = get_flashed_messages(with_categories=True)
    print(f"messages = {messages}")
    result_info = []
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM urls order by created_at desc")
            urls_tuples = cur.fetchall()
            urls_list= [] 
            if not urls_tuples:
                print('empty')
            else:
                print(urls_tuples)
            for url_tuple in urls_tuples:
                id, name, date = url_tuple
                get_max_date_query = "SELECT max(created_at), status_code FROM url_checks where url_id=%s group by status_code;"
                cur.execute(get_max_date_query, (id,))
                url_check_tuples = cur.fetchall()
                check_date = ''
                status = ''
                if url_check_tuples:
                    check_date = url_check_tuples[0][0]
                    status = url_check_tuples[0][1]
                    if check_date:
                        check_date = check_date.date()
                    else:
                        check_date = ''
                urls_list.append({'id': id, 'name': name, 'date' : date.date(), 'check_date' : check_date, 'status' : status})
            return render_template("urls.html", urls=urls_list, messages = messages)

@app.get('/urls/<id>')
def get_url(id):
    messages = get_flashed_messages(with_categories=True)
    print('before get url data')
    print(id)
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            get_url_data_query = "SELECT * FROM urls where id=%s ;"
            cur.execute(get_url_data_query, (id,))
            urls_tuples = cur.fetchall()
            id, name, date = urls_tuples[0]
            urls_data = {"id" : id, "name":name, "date":date.date()}
            get_url_checks_data= "SELECT id, status_code, h1, title, content, created_at FROM url_checks where url_id=%s order by created_at desc;"
            cur.execute(get_url_checks_data, (id,))
            url_checks_tuples = cur.fetchall()
            url_checks_list = []
            if url_checks_tuples:
                for url_check_tuple in url_checks_tuples:
                    id, status, h1, title, content, date = url_check_tuple
                    if not status:
                        status = ''
                    if not h1:
                        h1 = ''
                    if not title:
                        title = ''
                    if not content:
                        content = ''
                    url_checks_list.append({'id': id, 'status' : status,'h1' : h1, 'title': title, 'content':content,'date' : date.date()})
            return render_template("url.html", url=urls_data, url_checks = url_checks_list, messages = messages)
   
@app.post('/urls/<id>/checks')
def check_url(id):
    result_info = []
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            get_url_data_query = "SELECT * FROM urls where id=%s ;"
            cur.execute(get_url_data_query, (id,))
            urls_tuples = cur.fetchall()
            print(urls_tuples)
            if urls_tuples:
                name = urls_tuples[0][1]
            try:
                print(f'name = {name}')
                req = requests.request("GET", name)
            except:
                flash("Произошла ошибка при проверке", "alert alert-danger")
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
            request_string = "INSERT into url_checks (url_id, status_code, created_at, h1, title, content) VALUES (%s, %s, NOW(),%s,%s,%s);"
            cur.execute(request_string, (params['check_id'],params['status_code'],params['h1'],params['title'],params['content']))
            flash("Страница успешно проверена", "alert alert-success")
            return get_url(id)