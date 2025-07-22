from flask import Flask, jsonify
import random
import datetime
import string

app = Flask(__name__)

def generate_codCustomer():
    return f"C{str(random.randint(1, 9999999)).zfill(7)}"

def generate_orderNumber():
    return random.randint(100000, 999999)

def generate_orderToCollect():
    return random.randint(1, 10)

def generate_reference():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def generate_size():
    return float(random.choice([7, 8, 9, 10, 11, 12, 13, 14, 15, 95, 105]))

def generate_quantity():
    return random.randint(1, 10)

def generate_creationDate():
    now = datetime.datetime.now()
    return now.strftime("%d/%m/%Y %H:%M")  

def generate_waveNumber():
    return random.randint(40000, 50000)

def generate_operator():
    return f"Operator_{random.randint(1, 10)}"

def generate_fake_order():
    return {
        "codCustomer": generate_codCustomer(),
        "orderNumber": generate_orderNumber(),
        "orderToCollect": generate_orderToCollect(),
        "Reference": generate_reference(),
        "Size (US)": generate_size(),
        "quantity (units)": generate_quantity(),
        "creationDate": generate_creationDate(),
        "waveNumber": generate_waveNumber(),
        "operator": generate_operator()
    }

@app.route("/new_orders", methods=["GET"])
def new_orders():
    now = datetime.datetime.now()
    if 7 <= now.hour <= 9:
        orders = [generate_fake_order() for _ in range(20)]
    else:
        orders = [generate_fake_order() for _ in range(20)]
    return jsonify(orders)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
