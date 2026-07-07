from flask import Flask, render_template, request, send_from_directory, jsonify, session, redirect, url_for
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from datetime import datetime
import secrets
import os
import uuid
import requests
import base64

app = Flask(__name__, 
            template_folder='templates',
            static_folder='.')
app.secret_key = secrets.token_hex(16)

# ===== EMAIL CONFIGURATION =====
YOUR_EMAIL = "mecchachameleonstore@gmail.com"
YOUR_EMAIL_PASSWORD = "Malapak15."
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ===== PAYPAL STANDARD CONFIGURATION =====
PAYPAL_EMAIL = "mecchachameleonstore@gmail.com"
PAYPAL_SANDBOX = False
PAYPAL_URL = "https://www.paypal.com/cgi-bin/webscr"

# ===== PAYPAL API CONFIGURATION =====
PAYPAL_CLIENT_ID = "ARlmoa47tt-GIkbslRohxq74lrNmv7kdpo6TTk4WYzS4DkZ5VqAk1CjVDzoaCHOHeFYcy_UQdWw2OqKj"
PAYPAL_CLIENT_SECRET = "EDQ2PE-NJO4IQoivFo9_EiAiKm-LH9B5CKWAxnwAadambd5KbxaVsY9Gh3_6axdlJbDtOF84p2fqBJa4"
PAYPAL_MODE = "live"  # "sandbox" for testing

# PayPal API URL
if PAYPAL_MODE == "sandbox":
    PAYPAL_API_URL = "https://api-m.sandbox.paypal.com"
else:
    PAYPAL_API_URL = "https://api-m.paypal.com"

# ===== GET PAYPAL ACCESS TOKEN =====
def get_paypal_access_token():
    """Get PayPal OAuth access token"""
    auth = base64.b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}".encode()).decode()
    
    response = requests.post(
        f"{PAYPAL_API_URL}/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data="grant_type=client_credentials"
    )
    
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"❌ Error getting PayPal token: {response.text}")
        return None

# ===== PRODUCTS =====
PRODUCTS = {
    "8poses": {
        "id": "8poses",
        "name": "8 Poses Toy Set",
        "price": 34.99,
        "original_price": 49.99,
        "aliexpress_link": "https://nl.aliexpress.com/item/1005012606314092.html"
    },
    "18poses": {
        "id": "18poses",
        "name": "18 Poses Toy Set",
        "price": 49.99,
        "original_price": 66.99,
        "aliexpress_link": "https://nl.aliexpress.com/item/1005012633144316.html"
    }
}

# ===== SERVE CSS AND IMAGES =====
@app.route('/styles.css')
def serve_css():
    return send_from_directory('.', 'styles.css')

@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory('images', filename)

# ===== APPLE PAY DOMAIN VERIFICATION =====
@app.route('/.well-known/apple-developer-merchantid-domain-association')
def serve_apple_pay():
    """Serve Apple Pay domain verification file"""
    try:
        return send_from_directory('.', 'apple-developer-merchantid-domain-association')
    except Exception as e:
        print(f"Error serving Apple Pay verification: {e}")
        return "File not found", 404

# ===== SEND EMAIL FUNCTION =====
def send_order_email(customer_name, customer_email, customer_address, product, phone=None, order_id=None, txn_id=None):
    """Send order details to YOU and confirmation to customer"""
    
    # 1. Email to YOU
    you_subject = f"🛒 NEW ORDER - {product['name']}"
    you_body = f"""
🎉 NEW ORDER RECEIVED!

Order ID: {order_id or 'N/A'}
Product: {product['name']}
Price: €{product['price']}
Payment Method: PayPal
Transaction ID: {txn_id or 'N/A'}

CUSTOMER DETAILS:
Name: {customer_name}
Email: {customer_email}
Phone: {phone or 'Not provided'}
Address: {customer_address}

---
Order time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚡ ACTION REQUIRED: 
1. PayPal has notified you of the payment
2. Go to the AliExpress link
3. Add to cart and complete the purchase
4. Ship to the customer's address

ALIEXPRESS LINK:
{product['aliexpress_link']}
"""
    
    send_email(YOUR_EMAIL, you_subject, you_body)
    
    # 2. Confirmation to CUSTOMER
    customer_subject = f"✅ Order Confirmation - Mecha Toys"
    customer_body = f"""
Hello {customer_name},

Thank you for your order! We have received your payment successfully.

Order Details:
• Order ID: {order_id or 'N/A'}
• Product: {product['name']}
• Price: €{product['price']}
• Payment Method: PayPal

Shipping Address:
{customer_address}

Next Steps:
1. We will process your order within 24 hours
2. We will send you a tracking number via email
3. Shipping takes 7-15 business days

Questions? Reply to this email.

Thank you for choosing Mecha Toys! 🦎
"""
    
    send_email(customer_email, customer_subject, customer_body)

def send_email(to_email, subject, body):
    """Actually sends the email using SMTP"""
    try:
        msg = MIMEMultipart()
        msg['From'] = YOUR_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(YOUR_EMAIL, YOUR_EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

# ============================================================
# ===== PAYPAL API FUNCTIONS (como en la documentación) =====
# ============================================================

def create_paypal_order(amount, description):
    """Create a PayPal order using REST API (como en la documentación)"""
    access_token = get_paypal_access_token()
    if not access_token:
        return None
    
    order_data = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": f"GP-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "description": description,
            "amount": {
                "currency_code": "EUR",
                "value": str(amount)
            }
        }],
        "application_context": {
            "return_url": "https://mecha-toys.onrender.com/payment-success",
            "cancel_url": "https://mecha-toys.onrender.com/payment-cancel",
            "user_action": "PAY_NOW"
        }
    }
    
    response = requests.post(
        f"{PAYPAL_API_URL}/v2/checkout/orders",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        json=order_data
    )
    
    if response.status_code == 201:
        return response.json()
    else:
        print(f"❌ Error creating order: {response.text}")
        return None

def capture_paypal_order(order_id):
    """Capture a PayPal order using REST API (como en la documentación)"""
    access_token = get_paypal_access_token()
    if not access_token:
        return None
    
    response = requests.post(
        f"{PAYPAL_API_URL}/v2/checkout/orders/{order_id}/capture",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    )
    
    if response.status_code == 201:
        return response.json()
    else:
        print(f"❌ Error capturing order: {response.text}")
        return None

# ============================================================
# ===== ROUTES =====
# ============================================================

@app.route('/')
def home():
    return render_template('index.html', products=PRODUCTS)

# ============================================================
# CHECKOUT ROUTES
# ============================================================

@app.route('/checkout/<product_id>', methods=['GET'])
def checkout(product_id):
    """Show checkout with PayPal, Apple Pay and Google Pay"""
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    return render_template('checkout_with_applepay.html', 
                         product=product,
                         client_id=PAYPAL_CLIENT_ID)

@app.route('/checkout/<product_id>', methods=['POST'])
def process_checkout(product_id):
    """Process checkout (PayPal Standard)"""
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone', '')
    address = request.form.get('address')
    
    if not all([name, email, address]):
        return "Missing required fields", 400
    
    session['customer_data'] = {
        'name': name,
        'email': email,
        'phone': phone,
        'address': address,
        'product_id': product_id
    }
    
    return redirect(url_for('paypal_redirect', product_id=product_id))

@app.route('/paypal-redirect/<product_id>')
def paypal_redirect(product_id):
    """Redirect to PayPal for standard payment"""
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    
    customer_data = session.get('customer_data', {})
    
    return_url = f"https://mecha-toys.onrender.com/place-order?product_id={product_id}&name={customer_data.get('name')}&email={customer_data.get('email')}&address={customer_data.get('address')}&phone={customer_data.get('phone')}"
    
    paypal_form = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Redirecting to PayPal...</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                background: white;
                padding: 50px 40px;
                border-radius: 24px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.08);
                text-align: center;
                max-width: 450px;
                width: 100%;
            }}
            .spinner {{
                width: 50px;
                height: 50px;
                border: 4px solid #f3f3f3;
                border-top: 4px solid #0070ba;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 20px;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            h2 {{ color: #1a1a2e; font-size: 1.5rem; margin-bottom: 8px; }}
            p {{ color: #636e72; margin-bottom: 20px; line-height: 1.6; }}
            .btn {{
                display: inline-block;
                padding: 14px 40px;
                background: #0070ba;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 1.1rem;
                font-weight: 700;
                cursor: pointer;
                transition: all 0.3s ease;
                box-shadow: 0 4px 20px rgba(0, 112, 186, 0.3);
                text-decoration: none;
            }}
            .btn:hover {{
                background: #003087;
                transform: translateY(-3px);
                box-shadow: 0 8px 30px rgba(0, 112, 186, 0.4);
            }}
            .info {{ margin-top: 20px; font-size: 0.85rem; color: #b2bec3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="spinner"></div>
            <h2>🔄 Redirecting to PayPal...</h2>
            <p>Please wait while we redirect you to PayPal to complete your payment.</p>
            
            <form action="{PAYPAL_URL}" method="post" id="paypal-form">
                <input type="hidden" name="cmd" value="_xclick">
                <input type="hidden" name="business" value="{PAYPAL_EMAIL}">
                <input type="hidden" name="lc" value="EN">
                <input type="hidden" name="item_name" value="{product['name']}">
                <input type="hidden" name="amount" value="{product['price']}">
                <input type="hidden" name="currency_code" value="EUR">
                <input type="hidden" name="button_subtype" value="services">
                <input type="hidden" name="no_note" value="1">
                <input type="hidden" name="tax_rate" value="0.00">
                <input type="hidden" name="shipping" value="0.00">
                <input type="hidden" name="return" value="{return_url}">
                <input type="hidden" name="cancel_return" value="https://mecha-toys.onrender.com/">
                <input type="hidden" name="rm" value="2">
            </form>
            
            <button onclick="document.getElementById('paypal-form').submit();" class="btn">💳 Go to PayPal</button>
            <p class="info">If you are not redirected automatically, click the button above.</p>
            <a href="/" style="display:block; margin-top: 15px; color: #636e72; text-decoration: none; font-size: 0.9rem;">← Back to Store</a>
        </div>
        
        <script>
            setTimeout(function() {{
                document.getElementById('paypal-form').submit();
            }}, 1500);
        </script>
    </body>
    </html>
    """
    return paypal_form

# ============================================================
# ===== APPLE PAY ROUTES =====
# ============================================================

@app.route('/create-apple-pay-order', methods=['POST'])
def create_apple_pay_order():
    """Create an order for Apple Pay"""
    try:
        data = request.json
        product_id = data.get('product_id')
        customer_name = data.get('customer_name')
        customer_email = data.get('customer_email')
        customer_phone = data.get('customer_phone', '')
        customer_address = data.get('customer_address')
        
        if not all([product_id, customer_name, customer_email, customer_address]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        product = PRODUCTS.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        session['customer_data'] = {
            'name': customer_name,
            'email': customer_email,
            'phone': customer_phone,
            'address': customer_address,
            'product_id': product_id
        }
        
        # Usar la función create_paypal_order
        order = create_paypal_order(product['price'], product['name'])
        
        if order and 'id' in order:
            return jsonify({
                'order_id': order['id'],
                'status': 'created'
            })
        else:
            return jsonify({'error': 'Failed to create order'}), 400
            
    except Exception as e:
        print(f"Error creating order: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/capture-apple-pay-order', methods=['POST'])
def capture_apple_pay_order():
    """Capture the payment after Apple Pay"""
    try:
        data = request.json
        order_id = data.get('order_id')
        
        if not order_id:
            return jsonify({'error': 'Order ID required'}), 400
        
        # Usar la función capture_paypal_order
        capture_result = capture_paypal_order(order_id)
        
        if capture_result and 'status' in capture_result and capture_result['status'] == 'COMPLETED':
            transaction_id = capture_result['purchase_units'][0]['payments']['captures'][0]['id']
            
            customer_data = session.get('customer_data', {})
            product_id = customer_data.get('product_id')
            product = PRODUCTS.get(product_id)
            
            if product:
                order_id_internal = f"MT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                order_data = {
                    'order_id': order_id_internal,
                    'product': product['name'],
                    'product_id': product['id'],
                    'customer_name': customer_data.get('name'),
                    'customer_email': customer_data.get('email'),
                    'customer_phone': customer_data.get('phone', ''),
                    'customer_address': customer_data.get('address'),
                    'aliexpress_link': product['aliexpress_link'],
                    'amount': product['price'],
                    'timestamp': datetime.now().isoformat(),
                    'status': 'paid',
                    'payment_method': 'apple_pay',
                    'paypal_transaction_id': transaction_id,
                    'paypal_order_id': order_id
                }
                
                try:
                    with open('orders.json', 'r') as f:
                        orders = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    orders = []
                
                orders.append(order_data)
                with open('orders.json', 'w') as f:
                    json.dump(orders, f, indent=2)
                
                send_order_email(
                    customer_data.get('name'),
                    customer_data.get('email'),
                    customer_data.get('address'),
                    product,
                    customer_data.get('phone'),
                    order_id_internal,
                    transaction_id
                )
            
            session.pop('customer_data', None)
            
            return jsonify({
                'success': True,
                'transaction_id': transaction_id
            })
        else:
            return jsonify({'error': 'Failed to capture payment'}), 400
            
    except Exception as e:
        print(f"Error capturing order: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# ===== GOOGLE PAY ROUTES - USANDO API REST DIRECTA =====
# ============================================================

@app.route('/create-google-pay-order', methods=['POST'])
def create_google_pay_order():
    """Create an order for Google Pay - Usando API REST directa"""
    try:
        data = request.json
        print(f"📥 Google Pay create order request: {data}")
        
        product_id = data.get('product_id')
        customer_name = data.get('customer_name')
        customer_email = data.get('customer_email')
        customer_phone = data.get('customer_phone', '')
        customer_address = data.get('customer_address')
        
        if not all([product_id, customer_name, customer_email, customer_address]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        product = PRODUCTS.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Save customer data in session
        session['customer_data'] = {
            'name': customer_name,
            'email': customer_email,
            'phone': customer_phone,
            'address': customer_address,
            'product_id': product_id
        }
        
        # Create order using the REST API function
        order = create_paypal_order(product['price'], product['name'])
        
        if order and 'id' in order:
            print(f"✅ Google Pay order created: {order['id']}")
            return jsonify({
                'order_id': order['id'],
                'status': 'created'
            })
        else:
            print(f"❌ Google Pay order creation failed: {order}")
            return jsonify({'error': 'Failed to create order'}), 400
            
    except Exception as e:
        print(f"❌ Exception creating Google Pay order: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/capture-google-pay-order', methods=['POST'])
def capture_google_pay_order():
    """Capture the payment after Google Pay - Usando API REST directa"""
    try:
        data = request.json
        print(f"📥 Google Pay capture request: {data}")
        
        order_id = data.get('order_id')
        
        if not order_id:
            return jsonify({'error': 'Order ID required'}), 400
        
        # Capture using the REST API function
        capture_result = capture_paypal_order(order_id)
        print(f"🔍 Capture result: {capture_result}")
        
        if capture_result and 'status' in capture_result and capture_result['status'] == 'COMPLETED':
            transaction_id = capture_result['purchase_units'][0]['payments']['captures'][0]['id']
            print(f"✅ Payment captured: {transaction_id}")
            
            customer_data = session.get('customer_data', {})
            product_id = customer_data.get('product_id')
            product = PRODUCTS.get(product_id)
            
            if product:
                order_id_internal = f"MT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                order_data = {
                    'order_id': order_id_internal,
                    'product': product['name'],
                    'product_id': product['id'],
                    'customer_name': customer_data.get('name'),
                    'customer_email': customer_data.get('email'),
                    'customer_phone': customer_data.get('phone', ''),
                    'customer_address': customer_data.get('address'),
                    'aliexpress_link': product['aliexpress_link'],
                    'amount': product['price'],
                    'timestamp': datetime.now().isoformat(),
                    'status': 'paid',
                    'payment_method': 'google_pay',
                    'paypal_transaction_id': transaction_id,
                    'paypal_order_id': order_id
                }
                
                try:
                    with open('orders.json', 'r') as f:
                        orders = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    orders = []
                
                orders.append(order_data)
                with open('orders.json', 'w') as f:
                    json.dump(orders, f, indent=2)
                
                send_order_email(
                    customer_data.get('name'),
                    customer_data.get('email'),
                    customer_data.get('address'),
                    product,
                    customer_data.get('phone'),
                    order_id_internal,
                    transaction_id
                )
                
                print(f"✅ Order saved: {order_id_internal}")
            
            session.pop('customer_data', None)
            
            return jsonify({
                'success': True,
                'transaction_id': transaction_id
            })
        else:
            print(f"❌ Capture failed: {capture_result}")
            return jsonify({'error': 'Failed to capture payment'}), 400
            
    except Exception as e:
        print(f"❌ Exception capturing Google Pay order: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# ===== ORDER PROCESSING ROUTES =====
# ============================================================

@app.route('/place-order')
def place_order():
    """Process order after PayPal Standard payment"""
    product_id = request.args.get('product_id')
    customer_name = request.args.get('name')
    customer_email = request.args.get('email')
    customer_phone = request.args.get('phone')
    customer_address = request.args.get('address')
    
    payment_status = request.args.get('payment_status')
    txn_id = request.args.get('txn_id')
    
    if not all([product_id, customer_name, customer_email, customer_address]):
        return "Missing customer data", 400
    
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    
    order_id = f"MT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    order_data = {
        'order_id': order_id,
        'product': product['name'],
        'product_id': product['id'],
        'customer_name': customer_name,
        'customer_email': customer_email,
        'customer_phone': customer_phone,
        'customer_address': customer_address,
        'aliexpress_link': product['aliexpress_link'],
        'amount': product['price'],
        'timestamp': datetime.now().isoformat(),
        'status': 'paid' if payment_status == 'Completed' else 'pending',
        'payment_method': 'paypal_standard',
        'paypal_txn_id': txn_id,
        'paypal_status': payment_status
    }
    
    try:
        with open('orders.json', 'r') as f:
            orders = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        orders = []
    
    orders.append(order_data)
    with open('orders.json', 'w') as f:
        json.dump(orders, f, indent=2)
    
    send_order_email(
        customer_name,
        customer_email,
        customer_address,
        product,
        customer_phone,
        order_id,
        txn_id
    )
    
    session.pop('customer_data', None)
    
    return render_template('success.html', order=order_data)

@app.route('/payment-success')
def payment_success():
    """Success page for Apple Pay / Google Pay"""
    return redirect('/orders')

@app.route('/payment-cancel')
def payment_cancel():
    """Cancel page"""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Payment Cancelled - Mecha Toys</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background: white;
            padding: 50px;
            border-radius: 24px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.1);
            text-align: center;
            max-width: 500px;
        }
        h2 { color: #fdcb6e; margin-bottom: 10px; }
        .btn {
            display: inline-block;
            margin-top: 20px;
            padding: 12px 30px;
            background: #0070ba;
            color: white;
            text-decoration: none;
            border-radius: 10px;
        }
    </style>
    </head>
    <body>
        <div class="container">
            <h2>⚠️ Payment Cancelled</h2>
            <p>Your payment was cancelled. No charges were made.</p>
            <a href="/" class="btn">← Back to Store</a>
        </div>
    </body>
    </html>
    """

@app.route('/orders')
def view_orders():
    try:
        with open('orders.json', 'r') as f:
            orders = json.load(f)
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>📦 Orders - Mecha Toys</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: 'Inter', sans-serif; padding: 40px; background: #f5f6fa; }
                .container { max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); }
                h1 { color: #1a1a2e; margin-bottom: 10px; }
                .total { color: #636e72; margin-bottom: 20px; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th { background: #0070ba; color: white; padding: 15px; text-align: left; }
                td { padding: 12px 15px; border-bottom: 1px solid #eee; }
                tr:hover { background: #f8f9fa; }
                .status-paid { color: #00b894; font-weight: 600; }
                .back-link { display: inline-block; margin-top: 20px; padding: 12px 30px; background: #0070ba; color: white; text-decoration: none; border-radius: 10px; }
                .back-link:hover { background: #003087; }
                .no-orders { text-align: center; padding: 60px; color: #636e72; }
                .no-orders h2 { font-size: 2rem; margin-bottom: 10px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📦 All Orders</h1>
                <p class="total">Total: <strong>""" + str(len(orders)) + """</strong></p>
        """
        
        if orders:
            html += """
            <table>
                <tr>
                    <th>Order ID</th>
                    <th>Product</th>
                    <th>Method</th>
                    <th>Customer</th>
                    <th>Total</th>
                    <th>Status</th>
                    <th>Date</th>
                </tr>
            """
            
            for order in reversed(orders):
                status_color = "status-paid" if order.get('status') == 'paid' else ""
                status_text = "✅ PAID" if order.get('status') == 'paid' else "⏳ PENDING"
                method = order.get('payment_method', 'paypal_standard')
                method_icon = "🍎" if method == "apple_pay" else "🤖" if method == "google_pay" else "💳"
                html += f"""
                <tr>
                    <td><strong>{order.get('order_id', 'N/A')}</strong></td>
                    <td>{order.get('product', 'N/A')}</td>
                    <td>{method_icon} {method.replace('_', ' ').title()}</td>
                    <td>{order.get('customer_name', 'N/A')}</td>
                    <td><strong>€{order.get('amount', 0)}</strong></td>
                    <td class="{status_color}">{status_text}</td>
                    <td>{order.get('timestamp', 'N/A')[:16]}</td>
                </tr>
                """
            
            html += "</table>"
        else:
            html += """
            <div class="no-orders">
                <h2>📭 No orders yet</h2>
                <p>Orders will appear here when customers make purchases.</p>
            </div>
            """
        
        html += """
            <a href="/" class="back-link">← Back to Store</a>
            </div>
        </body>
        </html>
        """
        return html
        
    except FileNotFoundError:
        return """
        <div style="text-align:center;padding:60px;">
            <h2>📭 No orders yet</h2>
            <a href="/" style="display:inline-block;margin-top:20px;padding:12px 30px;background:#0070ba;color:white;text-decoration:none;border-radius:10px;">← Back to Store</a>
        </div>
        """

if __name__ == '__main__':
    app.run(debug=True, port=5000)

application = app