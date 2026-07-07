from flask import Flask, render_template, request, send_from_directory, jsonify, session, redirect, url_for
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from datetime import datetime
import secrets
import os
import urllib.parse
import uuid

app = Flask(__name__, 
            template_folder='templates',
            static_folder='.')
app.secret_key = secrets.token_hex(16)

# ===== CONFIGURE YOUR EMAIL =====
YOUR_EMAIL = "mecchachameleonstore@gmail.com"
YOUR_EMAIL_PASSWORD = "Malapak15."
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ===== PAYPAL CONFIGURATION =====
PAYPAL_EMAIL = "mecchachameleonstore@gmail.com"
PAYPAL_SANDBOX = False  # Set to False for production
PAYPAL_URL = "https://www.sandbox.paypal.com/cgi-bin/webscr" if PAYPAL_SANDBOX else "https://www.paypal.com/cgi-bin/webscr"

# Your Render.com URLs
BASE_URL = "https://mecha-toys.onrender.com"
PAYPAL_RETURN_URL = f"{BASE_URL}/payment-success"
PAYPAL_CANCEL_URL = f"{BASE_URL}/payment-cancel"

# ===== YOUR PRODUCTS =====
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
PayPal Transaction ID: {txn_id or 'N/A'}

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

# ===== ROUTES =====
@app.route('/')
def home():
    return render_template('index.html', products=PRODUCTS)

@app.route('/checkout/<product_id>', methods=['GET'])
def checkout(product_id):
    """Show checkout form"""
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    return render_template('checkout.html', product=product)

@app.route('/checkout/<product_id>', methods=['POST'])
def process_checkout(product_id):
    """Process checkout form and redirect to PayPal"""
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    
    # Get form data
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone', '')
    address = request.form.get('address')
    
    if not all([name, email, address]):
        return "Missing required fields", 400
    
    # Generate unique order ID
    order_id = f"MT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    
    # Store customer data in session with order_id
    session['customer_data'] = {
        'name': name,
        'email': email,
        'phone': phone,
        'address': address,
        'product_id': product_id,
        'order_id': order_id
    }
    
    # Build PayPal form with all data
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
                padding: 50px;
                border-radius: 24px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.1);
                text-align: center;
                max-width: 500px;
                width: 100%;
            }}
            .spinner {{
                width: 60px;
                height: 60px;
                border: 4px solid #f3f3f3;
                border-top: 4px solid #0070ba;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 25px;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            h2 {{
                color: #1a1a2e;
                margin-bottom: 10px;
                font-size: 1.5rem;
            }}
            p {{
                color: #636e72;
                margin-bottom: 25px;
                line-height: 1.6;
            }}
            .btn-paypal {{
                background: #0070ba;
                color: white;
                border: none;
                padding: 16px 40px;
                border-radius: 12px;
                font-size: 1.1rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(0,112,186,0.3);
                width: 100%;
            }}
            .btn-paypal:hover {{
                background: #003087;
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(0,112,186,0.4);
            }}
            .product-info {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 12px;
                margin: 20px 0;
                text-align: left;
            }}
            .product-info p {{
                margin: 5px 0;
                color: #2d3436;
            }}
            .product-info .price {{
                font-size: 1.3rem;
                font-weight: 700;
                color: #e17055;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="spinner"></div>
            <h2>🔄 Redirecting to PayPal...</h2>
            <p>Please wait while we prepare your payment.</p>
            
            <div class="product-info">
                <p><strong>Product:</strong> {product['name']}</p>
                <p class="price">Total: €{product['price']}</p>
            </div>
            
            <form action="{PAYPAL_URL}" method="post" id="paypal-form">
                <input type="hidden" name="cmd" value="_xclick">
                <input type="hidden" name="business" value="{PAYPAL_EMAIL}">
                <input type="hidden" name="lc" value="ES">
                <input type="hidden" name="item_name" value="{product['name']}">
                <input type="hidden" name="amount" value="{product['price']}">
                <input type="hidden" name="currency_code" value="EUR">
                <input type="hidden" name="button_subtype" value="services">
                <input type="hidden" name="no_note" value="1">
                <input type="hidden" name="tax_rate" value="0.00">
                <input type="hidden" name="shipping" value="0.00">
                <input type="hidden" name="return" value="{PAYPAL_RETURN_URL}">
                <input type="hidden" name="cancel_return" value="{PAYPAL_CANCEL_URL}">
                <input type="hidden" name="rm" value="2">
                <input type="hidden" name="custom" value="{order_id}">
                
                <!-- Hidden fields with customer data -->
                <input type="hidden" name="customer_data" value="{urllib.parse.quote(json.dumps(session['customer_data']))}">
                
                <button type="submit" class="btn-paypal">
                    💳 Proceed to PayPal
                </button>
            </form>
            
            <p style="margin-top: 20px; font-size: 0.85rem; color: #b2bec3;">
                You will be redirected to PayPal to complete your payment securely.
            </p>
        </div>
        
        <script>
            // Auto-submit after 2 seconds
            setTimeout(function() {{
                document.getElementById('paypal-form').submit();
            }}, 2000);
            
            // Also allow manual click
            document.querySelector('.btn-paypal').addEventListener('click', function(e) {{
                // Prevent default if already submitted
            }});
        </script>
    </body>
    </html>
    """
    
    return paypal_form

@app.route('/payment-success')
def payment_success():
    """Handle successful PayPal payment"""
    # Get data from PayPal
    txn_id = request.args.get('txn_id')
    payment_status = request.args.get('payment_status')
    payer_email = request.args.get('payer_email')
    custom = request.args.get('custom')  # This is our order_id
    
    # Get customer data from session
    customer_data = session.get('customer_data', {})
    
    if not customer_data:
        # Try to get from URL parameter if session is lost
        customer_data_json = request.args.get('customer_data')
        if customer_data_json:
            try:
                customer_data = json.loads(urllib.parse.unquote(customer_data_json))
            except:
                pass
    
    if not customer_data:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error - Mecha Toys</title>
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
                h2 { color: #e17055; margin-bottom: 10px; }
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
                <h2>❌ Error Processing Order</h2>
                <p>We couldn't find your order data. Please contact support.</p>
                <a href="/" class="btn">← Back to Store</a>
            </div>
        </body>
        </html>
        """, 400
    
    # Get product
    product_id = customer_data.get('product_id')
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    
    # Create order record
    order_id = custom or customer_data.get('order_id', f"MT-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    
    order_data = {
        'order_id': order_id,
        'product': product['name'],
        'product_id': product['id'],
        'customer_name': customer_data.get('name'),
        'customer_email': customer_data.get('email'),
        'customer_phone': customer_data.get('phone', ''),
        'customer_address': customer_data.get('address'),
        'aliexpress_link': product['aliexpress_link'],
        'amount': product['price'],
        'timestamp': datetime.now().isoformat(),
        'status': 'paid' if payment_status == 'Completed' else 'pending',
        'payment_method': 'paypal',
        'paypal_txn_id': txn_id,
        'paypal_payer_email': payer_email,
        'paypal_status': payment_status
    }
    
    # Save to orders.json
    try:
        with open('orders.json', 'r') as f:
            orders = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        orders = []
    
    orders.append(order_data)
    with open('orders.json', 'w') as f:
        json.dump(orders, f, indent=2)
    
    # Send confirmation emails
    if payment_status == 'Completed':
        send_order_email(
            customer_data.get('name'),
            customer_data.get('email'),
            customer_data.get('address'),
            product,
            customer_data.get('phone'),
            order_id,
            txn_id
        )
    
    # Clear session
    session.pop('customer_data', None)
    
    # Show success page
    return render_template('success.html', order=order_data)

@app.route('/payment-cancel')
def payment_cancel():
    """Handle cancelled PayPal payment"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payment Cancelled - Mecha Toys</title>
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
            <p style="color: #636e72; font-size: 0.9rem;">You can try again anytime.</p>
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
                    <th>Customer</th>
                    <th>Email</th>
                    <th>Total</th>
                    <th>Status</th>
                    <th>Date</th>
                    <th>AliExpress</th>
                </tr>
            """
            
            for order in reversed(orders):
                status_color = "status-paid" if order.get('status') == 'paid' else ""
                status_text = "✅ PAID" if order.get('status') == 'paid' else "⏳ PENDING"
                html += f"""
                <tr>
                    <td><strong>{order.get('order_id', 'N/A')}</strong></td>
                    <td>{order.get('product', 'N/A')}</td>
                    <td>{order.get('customer_name', 'N/A')}</td>
                    <td>{order.get('customer_email', 'N/A')}</td>
                    <td><strong>€{order.get('amount', 0)}</strong></td>
                    <td class="{status_color}">{status_text}</td>
                    <td>{order.get('timestamp', 'N/A')[:16]}</td>
                    <td><a href="{order.get('aliexpress_link', '#')}" target="_blank" style="color: #0070ba;">🔗 Buy</a></td>
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
            <a href="/" class="back-link">← Back to store</a>
            </div>
        </body>
        </html>
        """
        return html
        
    except FileNotFoundError:
        return """
        <div style="text-align:center;padding:60px;">
            <h2>📭 No orders yet</h2>
            <a href="/" style="display:inline-block;margin-top:20px;padding:12px 30px;background:#0070ba;color:white;text-decoration:none;border-radius:10px;">← Back to store</a>
        </div>
        """
    
# ===== APPLE PAY DOMAIN VERIFICATION =====
@app.route('/.well-known/apple-developer-merchantid-domain-association')
def serve_apple_pay():
    """Serve Apple Pay domain verification file"""
    try:
        return send_from_directory('.', 'apple-developer-merchantid-domain-association')
    except Exception as e:
        print(f"Error serving Apple Pay verification: {e}")
        return "File not found", 404
    
if __name__ == '__main__':
    app.run(debug=True, port=5000)

application = app