from pymongo import MongoClient
from faker import Faker
import random
from datetime import datetime, timedelta

# ==========================================
# MongoDB Atlas Connection
# ==========================================

MONGO_URI="mongodb+srv://mohamednabil13555_db_user:qcprkeiz9h_3hKk@erp.dffbywk.mongodb.net/?retryWrites=true&w=majority&authSource=admin"

client = MongoClient(MONGO_URI)

# Database
db = client["ERP"]

# Collections
customers_collection = db["customers"]
invoices_collection = db["invoices"]

# Faker
fake = Faker()

# ==========================================
# تنظيف البيانات القديمة
# ==========================================

customers_collection.delete_many({})
invoices_collection.delete_many({})

print("🗑️ Old data deleted")

# ==========================================
# Generate Customers
# ==========================================

customers = []

for _ in range(20):

    customer = {
        "customer_id": fake.uuid4(),
        "name": fake.name(),
        "email": fake.email(),
        "phone": fake.phone_number(),
        "city": fake.city(),
        "country": fake.country(),
        "created_at": datetime.utcnow()
    }

    customers.append(customer)

# Insert Customers
customers_collection.insert_many(customers)

print("✅ Customers inserted")

# ==========================================
# Fetch Customers
# ==========================================

all_customers = list(
    customers_collection.find(
        {"customer_id": {"$exists": True}}
    )
)

# ==========================================
# Generate Invoices
# ==========================================

invoices = []

for _ in range(50):

    customer = random.choice(all_customers)

    amount = round(
        random.uniform(1000, 50000),
        2
    )

    issue_date = fake.date_between(
        start_date="-90d",
        end_date="today"
    )

    due_date = issue_date + timedelta(
        days=random.randint(7, 30)
    )

    invoice = {

        "invoice_id": fake.uuid4(),

        "customer_id": customer["customer_id"],

        "customer_name": customer["name"],

        "amount": amount,

        "status": random.choice([
            "paid",
            "pending",
            "overdue"
        ]),

        "issue_date": issue_date.isoformat(),

        "due_date": due_date.isoformat(),

        "created_at": datetime.utcnow()
    }

    invoices.append(invoice)

# Insert Invoices
invoices_collection.insert_many(invoices)

print("✅ Invoices inserted")

# ==========================================
# Final Message
# ==========================================

print("🚀 Fake ERP data generated successfully")