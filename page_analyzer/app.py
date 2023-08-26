from flask import Flask, render_template, request, flash, redirect, get_flashed_messages, url_for
import psycopg2
import os
import validators
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

app = Flask(__name__)
app.secret_key = 'secret key'

DATABASE_URL = os.getenv('DATABASE_URL')

@app.route('/')
def index():
    messages = get_flashed_messages(with_categories=True)
    return render_template("main.html", messages = messages)

@app.post('/urls')
def urls_page():
    print(request.form.to_dict())
    url_string = request.form.to_dict().get('url', '')
    if not validators.url(url_string):
        messages = [("alert alert-danger", "Некорректный URL")]
        return render_template("main.html", messages = messages), 422
    url_string = urlparse(url_string)
    url_string=f'{url_string.scheme}://{url_string.netloc}'
    if url_string:
        result_info = []
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as curs:
                get_ids_of_url_query = "SELECT id from urls WHERE name= %s;"
                curs.execute(get_ids_of_url_query, (url_string,))
                urls_tuples = curs.fetchall()
                if urls_tuples:
                    url_id = urls_tuples[0][0]
                    print('страница существует')
                    flash("Страница уже существует", "alert alert-danger")
                else:
                    add_url_query = "INSERT into urls (name, created_at) VALUES (%s, NOW()) returning id;"
                    curs.execute(add_url_query, (url_string,))
                    url_id = curs.fetchone()[0]
                    conn.commit()
                    flash("Страница успешно добавлена", "alert alert-success")
                return redirect(url_for('get_url', id=url_id)), 301
    
@app.get('/urls')
def get_urls():
    messages = get_flashed_messages(with_categories=True)
    print(f"messages = {messages}")
    result_info = []
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            sql_query = """
            SELECT
                u.id AS url_id,
                u.name AS url_name,
                COALESCE(uc.status_code, '') AS status_code,
                uc.created_at AS max_created_at
            FROM
                urls u
            LEFT JOIN (
                SELECT
                    url_id,
                    status_code,
                    created_at,
                    ROW_NUMBER() OVER (PARTITION BY url_id ORDER BY created_at DESC) AS row_num
                FROM
                    url_checks
            ) uc ON u.id = uc.url_id AND uc.row_num = 1
            ORDER BY u.created_at DESC;
            """
            cur.execute(sql_query)
            urls_tuples = cur.fetchall()
            urls_list= []
            for url_tuple in urls_tuples:
                id, name, status, date = url_tuple
                date = (date.date() if date else '')
                urls_list.append({'id': id, 'name': name, 'check_date' : date , 'status' : status})
            return render_template("urls.html", urls=urls_list, messages = messages)

@app.get('/urls/<id>')
def get_url(id):
    messages = get_flashed_messages(with_categories=True)
    print(f'messages = {messages}')
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
                    url_checks_list.append({'id': id, 'status' : status,'h1' : h1, 'title': title, 'content':content, 'date' : date.date()})
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
                req = requests.request("GET", 'name')
                status_code = resourse.status_code
                if status_code != 200:
                    raise requests.RequestException
            except:
                flash("Произошла ошибка при проверке", "alert alert-danger")
                return redirect(url_for('get_url', id=id))
            html_content = req.text
    
            soup = BeautifulSoup(html_content, 'html.parser')
            h1 = soup.find('h1')
            h1 = h1.text if h1 else ''
            title = soup.find('title')
            title = title.text if title else ''
            meta_description_tag = soup.find('meta', attrs={'name': 'description'})
            content = ''
            if meta_description_tag:
                content = meta_description_tag.get("content")
                content = content if content else ''

            params = {'check_id': id, 'status_code': req.status_code, 'title': title, 'h1': h1, 'content': content}
            request_string = "INSERT into url_checks (url_id, status_code, created_at, h1, title, content) VALUES (%s, %s, NOW(),%s,%s,%s);"
            cur.execute(request_string, (params['check_id'],params['status_code'],params['h1'],params['title'],params['content']))
            conn.commit()
            flash("Страница успешно проверена", "alert alert-success")
            return get_url(id)