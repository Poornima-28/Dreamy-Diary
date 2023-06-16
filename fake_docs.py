from pymongo import MongoClient
from faker import Faker
import random

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['dreamydiary']
collection = db['dreams']

fake = Faker()

# Generate and insert 100 documents
for _ in range(100):
    username = random.choice(['poornima','himanshu','gracy'])
    dream_title = fake.catch_phrase()
    dream_date = fake.date_between(start_date='-1y', end_date='today')
    from datetime import datetime

    # Convert date to datetime
    dream_date = datetime(dream_date.year, dream_date.month, dream_date.day)
    dream_category = random.choice(['Adventure', 'Fantasy', 'Romance', 'Mystery', 'Sci-fi', 'Other'])
    dream_description = fake.paragraph()
    dream_rating = random.randint(1, 5)

    document = {
        'username': username,
        'dream-title': dream_title,
        'dream_date': dream_date,
        'dream_category': dream_category,
        'dream_description': dream_description,
        'dream_rating': dream_rating
    }

    collection.insert_one(document)

print("Documents inserted successfully!")
