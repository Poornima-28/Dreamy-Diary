from flask import Flask, render_template, request, session, redirect, flash, jsonify
from flask_pymongo import PyMongo
from datetime import datetime
from bson.objectid import ObjectId
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import io
import matplotlib.pyplot as plt
import base64
from wordcloud import WordCloud, STOPWORDS, ImageColorGenerator, get_single_color_func
import requests
from PIL import Image
from io import BytesIO
import numpy as np
import nltk
import re
nltk.download('punkt')
from string import punctuation


app = Flask(__name__)
app.secret_key = "pooven"  # Set a secret key for session management
app.config['MONGO_URI'] = 'mongodb://localhost:27017/dreamydiary'  # MongoDB connection URI
mongo = PyMongo(app)


@app.route('/')
def index():
    if 'username' in session:
        return redirect('/home')
    return render_template('index.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    user = mongo.db.users.find_one({'username': username, 'password': password})
    if user:
        session['username'] = username
        return redirect('/home')
    else:
        flash('Invalid username or password', 'error')
        return redirect('/')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/home')
def home():
    if 'username' not in session:
        return redirect('/')
    username = session['username']
    return render_template('home.html', username=username)


@app.route('/dream', methods=['POST'])
def add_dream():
    if 'username' in session:
        username = session['username']
        dream_title = request.form.get('dream-title')
        dream_date = request.form.get('dream-date')  # Update the form field name to 'dream-date'
        dream_category = request.form.get('dream-category')
        dream_description = request.form.get('dream-description')
        dream_rating = request.form.get('dream-rating')

        formatted_date = datetime.strptime(dream_date, "%Y-%m-%d")  # Convert dream_date to datetime object

        dream_data = {
            'username': username,
            'dream_title': dream_title,
            'dream_date': formatted_date,
            'dream_category': dream_category,
            'dream_description': dream_description,
            'dream_rating': dream_rating
        }

        mongo.db.dreams.insert_one(dream_data)
        flash('Dream added successfully', 'success')
    return redirect('/home')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        existing_user = mongo.db.users.find_one({'username': username})
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'error')
            return redirect('/register')
        mongo.db.users.insert_one({'username': username, 'password': password})
        session['username'] = username
        return redirect('/home')
    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/')

    username = session['username']
    dreams = mongo.db.dreams.find({'username': username})
    latest_dreams = mongo.db.dreams.find({'username': username}).sort('dream_date', -1).limit(5)
    latest_dreams = list(latest_dreams)

      # Generate the chart data
    dreams_over_time_chart = dreams_over_time()

    dreams_per_category_chart = dreams_per_category()
    dreams_per_category_over_time_chart = dreams_per_category_over_time()
    dreams_per_category_over_time_percent = dreams_per_category_over_time_percent_chart()

    dreams_per_rating_chart = dreams_per_rating()
    dreams_per_rating_over_time_chart = dreams_per_rating_over_time()
    dreams_per_rating_over_time_percent = dreams_per_rating_over_time_percent_chart()
    # word_cloud_image = word_cloud()
    top_words = top_10_words()


    return render_template('dashboard.html', username=username, dreams=dreams, \
                           latest_dreams=latest_dreams, dreams_over_time_chart=dreams_over_time_chart, \
                           dreams_per_category_chart=dreams_per_category_chart,
                           dreams_per_category_over_time_chart=dreams_per_category_over_time_chart,
                           dreams_per_category_over_time_percent=dreams_per_category_over_time_percent,
                           dreams_per_rating_chart=dreams_per_rating_chart,
                           dreams_per_rating_over_time_chart=dreams_per_rating_over_time_chart,
                           dreams_per_rating_over_time_percent=dreams_per_rating_over_time_percent,
                           top_words=top_words)



@app.route('/search', methods=['POST'])
def search():
    if 'username' not in session:
        return redirect('/')

    username = session['username']
    search_query = request.json['searchQuery']
    dreams = mongo.db.dreams.find({
        'username': username,
        '$or': [
            {'dream_title': {'$regex': search_query, '$options': 'i'}},
            {'dream_description': {'$regex': search_query, '$options': 'i'}}
        ]
    })

    results = list(dreams)
    return jsonify(results)



@app.route('/get_dream', methods=['POST'])
def get_dream():
    dream_id = request.form.get('dreamId')
    dream = mongo.db.dreams.find_one({'_id': ObjectId(dream_id)})
    return jsonify(dream)

@app.route('/update_dream', methods=['POST'])
def update_dream():
    dream_id = request.form.get('dreamId')
    title = request.form.get('title')
    date = request.form.get('date')
    category = request.form.get('category')
    description = request.form.get('description')
    rating = request.form.get('rating')

    formatted_date = datetime.strptime(date, "%Y-%m-%d")

    mongo.db.dreams.update_one({'_id': ObjectId(dream_id)}, {'$set': {
        'dream_title': title,
        'dream_date': formatted_date,
        'dream_category': category,
        'dream_description': description,
        'dream_rating': rating
    }})

    return jsonify({'message': 'Dream updated successfully'})


@app.route('/delete_dream', methods=['POST'])
def delete_dream():
    dream_id = request.form.get('dreamId')
    result = mongo.db.dreams.delete_one({'_id': ObjectId(dream_id)})
    if result.deleted_count == 1:
        return jsonify({'message': 'Dream deleted successfully'})
    else:
        return jsonify({'message': 'Failed to delete dream'})




def dreams_over_time():
    # Fetch the dreams data from the database
    username = session['username']
    dreams = mongo.db.dreams.find({'username': username})

    # Create a DataFrame from the dreams data
    df = pd.DataFrame(dreams)

    # Group the dreams by month and count the number of dreams in each month
    df['dream_date'] = pd.to_datetime(df['dream_date'])
    # df['dream_date'] = df['dream_date']
    dreams_over_time = df.groupby(df['dream_date'].dt.to_period('M')).size()

    # Convert the Period object to string representation
    dreams_over_time.index = dreams_over_time.index.astype(str)

    # Create the line chart
    fig = go.Figure(data=go.Scatter(x=dreams_over_time.index, y=dreams_over_time.values, mode='lines'))

     # Set the background color to transparent
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False)
    )
    # Convert the chart to HTML
    chart_html = pio.to_html(fig, full_html=False)

    return chart_html


def dreams_per_category():
    # Fetch the dreams data from the database
    username = session['username']
    dreams = mongo.db.dreams.find({'username': username})

    # Create a DataFrame from the dreams data
    df = pd.DataFrame(dreams)

    # Count the number of dreams per category
    dreams_per_category = df['dream_category'].value_counts()

    # Define a list of colors for each category
    category_colors = ['red', 'green', 'blue', 'yellow', 'orange']  # Add more colors if needed

    # Create the bar chart
    fig = go.Figure(data=go.Bar(
        x=dreams_per_category.index,
        y=dreams_per_category.values,
        marker=dict(color=category_colors)
    ))

    # Set the background color to transparent
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False)
    )

    # Convert the chart to HTML
    chart_html = pio.to_html(fig, full_html=False)

    return chart_html


def dreams_per_category_over_time():
    # Fetch the dreams data from the database
    username = session['username']
    dreams = mongo.db.dreams.find({'username': username})

    # Create a DataFrame from the dreams data
    df = pd.DataFrame(dreams)

    # Group the dreams by month and category, and count the number of dreams in each category for each month
    df['dream_date'] = pd.to_datetime(df['dream_date'])
    dreams_per_category_over_time = df.groupby([df['dream_date'].dt.to_period('M'), 'dream_category']).size().unstack()

    # Convert the Period object index to string representation
    dreams_per_category_over_time.index = dreams_per_category_over_time.index.astype(str)

    # Create the line chart
    fig = go.Figure()
    for category in dreams_per_category_over_time.columns:
        fig.add_trace(go.Scatter(
            x=dreams_per_category_over_time.index,
            y=dreams_per_category_over_time[category],
            mode='lines',
            name=category
        ))

    # Set the background color to transparent
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False),
        title='Dreams per Category over Time',
        xaxis_title='Time',
        yaxis_title='Number of Dreams'
    )

    # Convert the chart to HTML
    chart_html = pio.to_html(fig, full_html=False)

    return chart_html


def dreams_per_category_over_time_percent_chart():
    # Fetch the dreams data from the database
    username = session['username']
    dreams = mongo.db.dreams.find({'username': username})

    # Create a DataFrame from the dreams data
    df = pd.DataFrame(dreams)

    # Group the dreams by month and category, and count the number of dreams in each category for each month
    df['dream_date'] = pd.to_datetime(df['dream_date'])
    dreams_per_category_over_time = df.groupby([df['dream_date'].dt.to_period('M'), 'dream_category']).size().unstack()

    # Convert the Period object index to string representation
    dreams_per_category_over_time.index = dreams_per_category_over_time.index.astype(str)

    # Calculate the percentage of dreams per category for each month
    dreams_per_category_over_time_percent = dreams_per_category_over_time.apply(lambda x: x / x.sum() * 100, axis=1)

    # Create the stacked bar chart
    colors = ['rgb(49,130,189)', 'rgb(204,204,204)', 'rgb(255,127,14)', 'rgb(44,160,44)', 'rgb(214,39,40)',
              'rgb(148,103,189)', 'rgb(140,86,75)', 'rgb(227,119,194)', 'rgb(127,127,127)', 'rgb(188,189,34)',
              'rgb(23,190,207)']

    fig = go.Figure()
    for category in dreams_per_category_over_time_percent.columns:
        fig.add_trace(go.Bar(
            x=dreams_per_category_over_time_percent.index,
            y=dreams_per_category_over_time_percent[category],
            name=category,
            marker_color=colors.pop(0)
        ))

    # Set the background color to transparent
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        barmode='stack',
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False),
        title='Dreams per Category over Time (Percentage)',
        xaxis_title='Time',
        yaxis_title='Percentage'
    )

    # Convert the chart to HTML
    chart_html = pio.to_html(fig, full_html=False)

    return chart_html

def dreams_per_rating():
    # Fetch the dreams data from the database
    username = session['username']
    dreams = mongo.db.dreams.find({'username': username})

    # Create a DataFrame from the dreams data
    df = pd.DataFrame(dreams)

    # Convert 'dream_rating' column to numeric type
    df['dream_rating'] = pd.to_numeric(df['dream_rating'], errors='coerce')

    # Count the number of dreams for each rating
    dreams_per_rating = df['dream_rating'].value_counts().sort_index()

    # Create the bar chart
    fig = go.Figure(data=go.Bar(x=dreams_per_rating.index, y=dreams_per_rating.values))

    # Set the background color to transparent
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False)
    )

    # Convert the chart to HTML
    chart_html = pio.to_html(fig, full_html=False)

    return chart_html


def dreams_per_rating_over_time():
    # Fetch the dreams data from the database
    username = session['username']
    dreams = mongo.db.dreams.find({'username': username})

    # Create a DataFrame from the dreams data
    df = pd.DataFrame(dreams)

    # Group the dreams by month and rating, and count the number of dreams for each rating in each month
    df['dream_date'] = pd.to_datetime(df['dream_date'])
    dreams_per_rating_over_time = df.groupby([df['dream_date'].dt.to_period('M'), 'dream_rating']).size().unstack()

    # Convert the Period object index to string representation
    dreams_per_rating_over_time.index = dreams_per_rating_over_time.index.astype(str)

    # Create the line chart
    fig = go.Figure()
    for rating in dreams_per_rating_over_time.columns:
        fig.add_trace(go.Scatter(
            x=dreams_per_rating_over_time.index,
            y=dreams_per_rating_over_time[rating],
            mode='lines',
            name=rating
        ))

    # Set the background color to transparent
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False),
        title='Dreams per Rating over Time',
        xaxis_title='Time',
        yaxis_title='Number of Dreams'
    )

    # Convert the chart to HTML
    chart_html = pio.to_html(fig, full_html=False)

    return chart_html


def dreams_per_rating_over_time_percent_chart():
#   Fetch the dreams data from the database
    username = session['username']
    dreams = mongo.db.dreams.find({'username': username})

    # Create a DataFrame from the dreams data
    df = pd.DataFrame(dreams)

    # Group the dreams by month and category, and count the number of dreams in each category for each month
    df['dream_date'] = pd.to_datetime(df['dream_date'])
    dreams_per_category_over_time = df.groupby([df['dream_date'].dt.to_period('M'), 'dream_category']).size().unstack()

    # Convert the Period object index to string representation
    dreams_per_category_over_time.index = dreams_per_category_over_time.index.astype(str)

    # Calculate the percentage of dreams per category for each month
    dreams_per_category_over_time_percent = dreams_per_category_over_time.apply(lambda x: x / x.sum() * 100, axis=1)

    # Convert the index to string representation
    dreams_per_category_over_time_percent.reset_index(inplace=True)
    dreams_per_category_over_time_percent['dream_date'] = dreams_per_category_over_time_percent['dream_date'].astype(str)

    # Create the stacked bar chart
    colors = ['rgb(49,130,189)', 'rgb(204,204,204)', 'rgb(255,127,14)', 'rgb(44,160,44)', 'rgb(214,39,40)',
              'rgb(148,103,189)', 'rgb(140,86,75)', 'rgb(227,119,194)', 'rgb(127,127,127)', 'rgb(188,189,34)',
              'rgb(23,190,207)']

    fig = go.Figure()
    for category in dreams_per_category_over_time_percent.columns[1:]:
        fig.add_trace(go.Bar(
            x=dreams_per_category_over_time_percent['dream_date'],
            y=dreams_per_category_over_time_percent[category],
            name=category,
            marker_color=colors.pop(0)
        ))

    # Set the background color to transparent
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        barmode='stack',
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False),
        title='Dreams per Category over Time (Percentage)',
        xaxis_title='Time',
        yaxis_title='Percentage'
    )

    # Convert the chart to HTML
    chart_html = pio.to_html(fig, full_html=False)

    return chart_html


def top_10_words():
    # Fetch the dreams data from the database
    username = session['username']
    dreams = mongo.db.dreams.find({'username': username})

    # Create a list of dream descriptions
    dream_descriptions = [dream['dream_description'] for dream in dreams]

    # Join all the dream descriptions into a single string
    text = ' '.join(dream_descriptions)

    # Tokenize the text into individual words
    words = nltk.word_tokenize(text)

    # Convert the words to lowercase and remove punctuations
    words = [word.lower() for word in words if word not in punctuation]

    # Remove common stopwords
    stop_words = set(nltk.corpus.stopwords.words('english'))
    words = [word for word in words if word not in stop_words]

    # Calculate the frequency of each word
    word_freq = nltk.FreqDist(words)

    # Get the top 10 most frequent words
    top_words = word_freq.most_common(10)

    # Create an HTML structure using <div> elements
    html = '<div class="table">'
    html += '<div class="table-row header-row">'
    html += '<div class="table-cell">Word</div>'
    html += '<div class="table-cell">Frequency</div>'
    html += '</div>'

    for i, (word, freq) in enumerate(top_words):
        row_class = 'even' if i % 2 == 0 else 'odd'  # Set row class based on row index

        html += f'<div class="table-row {row_class}">'
        html += f'<div class="table-cell">{word}</div>'
        html += f'<div class="table-cell">{freq}</div>'
        html += '</div>'

    html += '</div>'

    # Add CSS styles to create a table-like appearance
    html += '''
        <style>
            .table {
                display: table;
                width: 100%;
                border-collapse: collapse;
            }

            .table-row {
                display: table-row;
            }

            .header-row {
                font-weight: bold;
            }

            .table-cell {
                display: table-cell;
                border: 1px solid lightgray;
                padding: 5px;
            }

            .even {
                background-color: rgba(0, 0, 0, 0);
            }

            .odd {
                background-color: rgba(0, 0, 0, 0.05);
            }
        </style>
    '''

    return html







# def word_cloud():
#     # Fetch the dreams data from the database
#     username = session['username']
#     dreams = mongo.db.dreams.find({'username': username})

#     # Create a list of dream descriptions
#     dream_descriptions = [dream['dream_description'] for dream in dreams]

#     # Join all the dream descriptions into a single string
#     text = ' '.join(dream_descriptions)

#     # Create a WordCloud object with a transparent background
#     wordcloud = WordCloud(background_color='rgba(0, 0, 0, 0)',\
#      mode='RGBA', contour_color='black', collocations=False, \
#      colormap = 'Dark2').generate(text)

#     # Generate the word cloud image
#     plt.imshow(wordcloud, interpolation='bilinear')
#     plt.axis('off')
#     plt.tight_layout()

#     # Save the word cloud image to a BytesIO object with a transparent background
#     image_stream = io.BytesIO()
#     plt.savefig(image_stream, format='png', transparent=True)
#     image_stream.seek(0)

#     # Convert the image stream to base64 representation
#     image_base64 = base64.b64encode(image_stream.getvalue()).decode('utf-8')

#     return image_base64




if __name__ == '__main__':
    app.run(debug=True)
